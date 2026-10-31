"""
All settings in one place.

HOW SETTINGS ARE READ
    Every field below has a default. To change one, set an environment variable
    with the same name in UPPER CASE, usually by adding a line to backend/.env:

        GOOGLE_FACTCHECK_API_KEY=abc123      ->  settings.google_factcheck_api_key == "abc123"
        RATE_LIMIT=10/minute                 ->  settings.rate_limit == "10/minute"

    pydantic-settings does this automatically and converts types for you
    ("true" -> True, "30" -> 30). In Docker, docker-compose.yml passes
    backend/.env into the container, so the same file works there too.

    Nothing is hardcoded to localhost, which is what makes the app deployable.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

# The backend/ folder (this file is backend/app/config.py, so go up two levels).
BACKEND_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    # Read backend/.env if it exists; ignore unknown variables instead of crashing.
    model_config = SettingsConfigDict(env_file=BACKEND_DIR / ".env", extra="ignore")

    app_name: str = "MisInfo AI"
    version: str = "2.0.0"
    environment: Literal["dev", "prod", "test"] = "dev"

    # CORS: which website addresses may call the API from a browser (comma-separated).
    # 5173 = Vite dev server, 8080 = the Docker frontend.
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173,http://localhost:8080"

    # --- Storage ---------------------------------------------------------------
    data_dir: Path = BACKEND_DIR / "data"  # database + web-search cache live here
    database_url: str = ""  # empty = SQLite file in data_dir; or e.g. a Postgres URL
    store_input_text: bool = True  # False = history keeps verdicts but not what people pasted

    # --- AI model (LLM) ----------------------------------------------------------
    # anthropic = Claude (best), ollama = free local model, none = no AI (fact-check matching only)
    llm_provider: Literal["anthropic", "ollama", "none"] = "anthropic"
    anthropic_api_key: str = ""
    llm_model: str = "claude-opus-5-5"  # the careful model that judges each claim
    llm_fast_model: str = "claude-haiku-5-5"  # the quick, cheap model that finds claims and writes summaries
    llm_web_search: bool = True  # allow Claude to run its own web searches while judging
    llm_max_searches_per_claim: int = 3  # caps cost: each search is billed
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.1:8b"

    # --- Evidence sources (all optional) -----------------------------------------
    google_factcheck_api_key: str = ""  # free key; searches published fact-checks
    brave_api_key: str = ""  # optional paid web search
    tavily_api_key: str = ""  # optional paid web search
    enable_wikipedia: bool = True  # free, no key needed

    # --- Live monitor (Live page): reads public Bluesky posts; off unless switched on
    monitor_enabled: bool = False

    # --- Optional trained style model (made by the scripts in training/) ---------
    style_model_dir: Path = BACKEND_DIR / "models" / "style"

    # --- Limits (protect speed, cost and the server) -----------------------------
    max_input_chars: int = 20_000  # longest text accepted
    max_claims: int = 5  # most claims checked per request
    http_timeout_s: float = 8.0  # give up on a slow evidence source after this long
    pipeline_budget_s: float = 75.0  # whole check must finish within this many seconds
    cache_ttl_s: int = 6 * 3600  # reuse identical web lookups for 6 hours
    rate_limit: str = "30/minute"  # checks allowed per visitor
    max_upload_mb: int = 8  # biggest screenshot accepted

    # Properties are computed values built from the settings above.

    @property
    def origins(self) -> list[str]:
        """CORS_ORIGINS as a list."""
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def db_url(self) -> str:
        """Where the database is. Defaults to a SQLite file: backend/data/misinfo.db."""
        if self.database_url:
            return self.database_url
        self.data_dir.mkdir(parents=True, exist_ok=True)
        return f"sqlite:///{self.data_dir / 'misinfo.db'}"

    @property
    def llm_enabled(self) -> bool:
        """True when an AI model is actually usable (e.g. Claude needs a key)."""
        if self.llm_provider == "anthropic":
            return bool(self.anthropic_api_key)
        return self.llm_provider == "ollama"


@lru_cache  # build Settings once and reuse it everywhere (reading .env every time would be wasteful)
def get_settings() -> Settings:
    return Settings()
