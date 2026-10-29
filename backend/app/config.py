"""Central configuration. Every value can be overridden by an environment variable
(or a .env file next to the backend). Nothing is hardcoded to localhost."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BACKEND_DIR / ".env", extra="ignore")

    app_name: str = "MisInfo AI"
    version: str = "2.0.0"
    environment: Literal["dev", "prod", "test"] = "dev"

    # CORS: comma-separated list of allowed frontend origins
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173,http://localhost:8080"

    # Storage
    data_dir: Path = BACKEND_DIR / "data"
    database_url: str = ""  # defaults to sqlite in data_dir
    store_input_text: bool = True  # set False for privacy-first deployments

    # LLM provider: anthropic | ollama | none
    llm_provider: Literal["anthropic", "ollama", "none"] = "anthropic"
    anthropic_api_key: str = ""
    llm_model: str = "claude-opus-5-5"  # the reasoning / verification model
    llm_fast_model: str = "claude-haiku-5-5"  # claim extraction
    llm_web_search: bool = True  # let Claude run its own web searches
    llm_max_searches_per_claim: int = 3
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.1:8b"

    # Evidence sources (all optional; the free ones work without keys)
    google_factcheck_api_key: str = ""
    brave_api_key: str = ""
    tavily_api_key: str = ""
    enable_wikipedia: bool = True

    # Style model (fine-tuned transformer exported to ONNX, or sklearn baseline)
    style_model_dir: Path = BACKEND_DIR / "models" / "style"

    # Limits
    max_input_chars: int = 20_000
    max_claims: int = 5
    http_timeout_s: float = 8.0
    pipeline_budget_s: float = 75.0
    cache_ttl_s: int = 6 * 3600
    rate_limit: str = "30/minute"
    max_upload_mb: int = 8

    @property
    def origins(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def db_url(self) -> str:
        if self.database_url:
            return self.database_url
        self.data_dir.mkdir(parents=True, exist_ok=True)
        return f"sqlite:///{self.data_dir / 'misinfo.db'}"

    @property
    def llm_enabled(self) -> bool:
        if self.llm_provider == "anthropic":
            return bool(self.anthropic_api_key)
        return self.llm_provider == "ollama"


@lru_cache
def get_settings() -> Settings:
    return Settings()
