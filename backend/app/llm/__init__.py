"""
The AI layer ("LLM" = large language model).

Three interchangeable "providers" do the same three jobs in different ways:

    job                 AnthropicProvider (Claude)   OllamaProvider (local)   HeuristicProvider (no AI)
    extract_claims      Claude Haiku                 local model              sentence rules
    verify_claim        Claude Opus + web search     local model              match published fact-checks
    summarize           Claude Haiku                 local model              (none; uses default text)

The rest of the app only ever calls get_provider() and those three methods, so
switching between them is just LLM_PROVIDER=... in backend/.env. No code changes.
"""

from __future__ import annotations

import logging
from functools import lru_cache

from ..config import get_settings
from .base import LLMProvider
from .heuristic_provider import HeuristicProvider

log = logging.getLogger(__name__)


@lru_cache  # build the provider once and reuse it
def get_provider() -> LLMProvider:
    """Pick the provider from settings. Falls back to the no-AI provider if Claude has no key."""
    s = get_settings()
    if s.llm_provider == "anthropic":
        if s.anthropic_api_key:
            from .anthropic_provider import AnthropicProvider

            return AnthropicProvider(
                api_key=s.anthropic_api_key,
                model=s.llm_model,
                fast_model=s.llm_fast_model,
                web_search=s.llm_web_search,
                max_searches=s.llm_max_searches_per_claim,
            )
        log.warning("LLM_PROVIDER=anthropic but ANTHROPIC_API_KEY is empty; using heuristic mode.")
    elif s.llm_provider == "ollama":
        from .ollama_provider import OllamaProvider

        return OllamaProvider(s.ollama_base_url, s.ollama_model)
    return HeuristicProvider()
