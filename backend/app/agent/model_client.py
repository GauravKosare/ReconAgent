"""Provider-agnostic LLM access with free-tier failover.

The rest of the codebase only ever imports `ModelClient`. Swapping providers is
a config change (LLM_PRIMARY / LLM_FALLBACKS), never a code change. If no
provider key is configured, `ModelUnavailable` is raised and the pipeline routes
the cluster to a human instead.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from typing import Any

from ..config import get_settings

# Map settings fields -> the env var name each provider SDK / LiteLLM expects.
_PROVIDER_ENV = {
    "gemini_api_key": "GEMINI_API_KEY",
    "groq_api_key": "GROQ_API_KEY",
    "openrouter_api_key": "OPENROUTER_API_KEY",
    "github_models_token": "GITHUB_API_KEY",
}


def _export_provider_keys() -> None:
    """LiteLLM reads credentials from os.environ; pydantic-settings only fills the
    Settings object. Bridge the two so a key in .env is enough."""
    s = get_settings()
    for field_name, env_name in _PROVIDER_ENV.items():
        val = getattr(s, field_name, None)
        if val and not os.environ.get(env_name):
            os.environ[env_name] = val


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
        """Best-effort JSON extraction.

        Handles clean JSON, ```json fences, and reasoning models that emit a
        chain-of-thought preamble before the object (e.g. Nemotron Lightning).
        """
        text = self.content.strip()
        if text.startswith("```"):
            text = text.split("```", 2)[1].removeprefix("json").strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
        # Scan for the first balanced {...} object (handles a reasoning preamble
        # and trailing prose around the JSON).
        start = text.find("{")
        if start != -1:
            depth = 0
            in_str = False
            esc = False
            for i in range(start, len(text)):
                ch = text[i]
                if in_str:
                    esc = ch == "\\" and not esc
                    if ch == '"' and not esc:
                        in_str = False
                    continue
                if ch == '"':
                    in_str = True
                elif ch == "{":
                    depth += 1
                elif ch == "}":
                    depth -= 1
                    if depth == 0:
                        return json.loads(text[start : i + 1])
        raise ValueError(f"no parseable JSON object in model output: {text[:300]!r}")


class ModelClient:
    def __init__(self, chain: list[str] | None = None) -> None:
        s = get_settings()
        _export_provider_keys()
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
        timeout: float = 45.0,
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
            for use_json in ([True, False] if response_json else [False]):
                try:
                    kwargs: dict[str, Any] = dict(
                        model=model,
                        messages=messages,
                        temperature=temperature,
                        max_tokens=max_tokens,
                        timeout=timeout,
                    )
                    if use_json:
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
                except Exception as exc:  # noqa: BLE001 — try next (json-off, then next provider)
                    name = type(exc).__name__
                    errors.append(f"{model}({'json' if use_json else 'plain'}): {name}: {exc}")
                    # only the json->plain retry is worth doing on the same model;
                    # anything else, move to the next provider
                    if use_json and "BadRequest" in name:
                        continue
                    break

        raise ModelUnavailable("all providers failed -> " + " | ".join(errors))
