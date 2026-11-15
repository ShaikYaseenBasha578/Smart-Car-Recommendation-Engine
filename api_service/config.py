"""Process configuration of the API service. Nothing here touches files outside this process."""

from __future__ import annotations

import os
from pathlib import Path
from typing import List

ROOT = Path(__file__).resolve().parents[1]
ENGINE_VERSION = "v3"
MAX_QUERY_CHARS = 500
MAX_LIMIT = 20
DEFAULT_LIMIT = 8


def apply_process_env(environ=None) -> dict:
    """Set the env the v3 engine reads, only where the operator has not already set it. Must run before
    `services.catalogue` is imported (it reads CARREC_CATALOGUE_DIR at import). Set API_SERVICE_NO_ENV=1 to skip
    (tests that share a process with the rest of the suite). Returns what was set."""
    env = os.environ if environ is None else environ
    if env.get("API_SERVICE_NO_ENV") == "1":
        return {}
    applied = {}
    defaults = {"RANKER": "v3", "CARREC_CATALOGUE_DIR": str(ROOT / "data" / "catalogue_v3")}
    for key, value in defaults.items():
        if not env.get(key):
            env[key] = value
            applied[key] = value
    return applied


def cors_origins(environ=None) -> List[str]:
    """API_CORS_ORIGINS="https://a.example,https://b.example"; empty or unset = CORS off."""
    env = os.environ if environ is None else environ
    return [o.strip() for o in env.get("API_CORS_ORIGINS", "").split(",") if o.strip() and o.strip() != "*"]


def llm_key_present(environ=None) -> bool:
    """True when the LLM parser's API key variable (same rule as services/recsys/llm_parse.py) holds a value. The key
    itself is never read into this service's state."""
    env = os.environ if environ is None else environ
    base_url = env.get("LLM_PARSER_BASE_URL", "").strip()
    provider = env.get("LLM_PARSER_PROVIDER", "openai" if base_url else "gemini").strip().lower()
    key_env = env.get("LLM_PARSER_KEY_ENV", "").strip() or ("GEMINI_API_KEY" if provider == "gemini" else "")
    return bool(key_env and env.get(key_env, "").strip())
