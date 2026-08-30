"""Central configuration, loaded from environment / .env."""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=(".env", "../.env"), extra="ignore")

    # Database
    mongodb_uri: str = "mongodb://localhost:27017"
    mongodb_db: str = "reconagent"

    # LLM failover chain
    llm_primary: str = "gemini/gemini-2.5-flash"
    llm_fallbacks: str = ""
    llm_triage: str | None = None
    embeddings_model: str | None = None

    gemini_api_key: str | None = None
    groq_api_key: str | None = None
    openrouter_api_key: str | None = None
    github_models_token: str | None = None

    # Routing policy
    auto_resolve_min_confidence: float = 0.90
    auto_resolve_max_impact_inr: float = 500.0
    auto_resolve_allowed_codes: str = "TIMING_GAP,DUPLICATE,FEE_MISMATCH"

    # Settlement assumptions
    settlement_sla_days: int = 2
    default_mdr_percent: float = 2.0
    default_gst_percent: float = 18.0

    redis_url: str | None = None
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    log_level: str = "INFO"

    @property
    def llm_chain(self) -> list[str]:
        chain = [self.llm_primary] + [
            m.strip() for m in self.llm_fallbacks.split(",") if m.strip()
        ]
        return [m for m in chain if m]

    @property
    def allowed_auto_codes(self) -> set[str]:
        return {c.strip() for c in self.auto_resolve_allowed_codes.split(",") if c.strip()}

    @property
    def llm_available(self) -> bool:
        return any(
            [self.gemini_api_key, self.groq_api_key, self.openrouter_api_key, self.github_models_token]
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
