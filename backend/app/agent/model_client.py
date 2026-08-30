"""Provider-agnostic LLM access with free-tier failover.

The rest of the codebase only ever imports `ModelClient`. Swapping providers is
a config change (LLM_PRIMARY / LLM_FALLBACKS), never a code change. If no
provider key is configured, `ModelUnavailable` is raised and the pipeline routes
the cluster to a human instead.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any

from ..config import get_settings


class ModelUnavailable(RuntimeError):
    """No configured LLM provider could answer (no keys, or all failed)."""


@dataclass
class ModelResult:
    content: str
    model: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    latency_ms: int = 0
    attempts: list[str] = field(default_factory=list)

    def json(self) -> dict[str, Any]:
        text = self.content.strip()
        if text.startswith("```"):
            text = text.split("```", 2)[1].removeprefix("json").strip()
        return json.loads(text)


class ModelClient:
    def __init__(self, chain: list[str] | None = None) -> None:
        s = get_settings()
        self.chain = chain or s.llm_chain
        self._available = s.llm_available

    @property
    def available(self) -> bool:
        return self._available

    def complete(
        self,
        system: str,
        user: str,
        *,
        temperature: float = 0.0,
        max_tokens: int = 1200,
        response_json: bool = True,
    ) -> ModelResult:
        if not self._available:
            raise ModelUnavailable("no LLM provider key configured")

        import litellm  # imported lazily so the package is optional at import time

        litellm.drop_params = True
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]
        errors: list[str] = []
        attempts: list[str] = []

        for model in self.chain:
            attempts.append(model)
            started = time.perf_counter()
            try:
                kwargs: dict[str, Any] = dict(
                    model=model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
                if response_json:
                    kwargs["response_format"] = {"type": "json_object"}
                resp = litellm.completion(**kwargs)
                usage = getattr(resp, "usage", None)
                return ModelResult(
                    content=resp.choices[0].message.content or "",
                    model=model,
                    prompt_tokens=getattr(usage, "prompt_tokens", 0) or 0,
                    completion_tokens=getattr(usage, "completion_tokens", 0) or 0,
                    latency_ms=int((time.perf_counter() - started) * 1000),
                    attempts=attempts.copy(),
                )
            except Exception as exc:  # noqa: BLE001 — we genuinely want to try the next provider
                errors.append(f"{model}: {type(exc).__name__}: {exc}")
                continue

        raise ModelUnavailable("all providers failed -> " + " | ".join(errors))
