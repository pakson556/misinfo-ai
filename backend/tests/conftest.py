import os
import tempfile

import pytest

# Isolate every test run: temp data dir, no keys, no outbound network sources.
_tmp = tempfile.mkdtemp(prefix="misinfo-test-")
os.environ.update(
    {
        "ENVIRONMENT": "test",
        "DATA_DIR": _tmp,
        "DATABASE_URL": "",
        "LLM_PROVIDER": "none",
        "ANTHROPIC_API_KEY": "",
        "GOOGLE_FACTCHECK_API_KEY": "",
        "BRAVE_API_KEY": "",
        "TAVILY_API_KEY": "",
        "ENABLE_WIKIPEDIA": "false",
        "STYLE_MODEL_DIR": os.path.join(_tmp, "no-model"),
        "RATE_LIMIT": "1000/minute",
    }
)


@pytest.fixture(autouse=True)
def _fresh_settings():
    from app.config import get_settings
    from app.llm import get_provider

    get_settings.cache_clear()
    get_provider.cache_clear()
    yield
    get_settings.cache_clear()
    get_provider.cache_clear()
