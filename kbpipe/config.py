"""Configuration: defaults, overridden by kbpipe.config.json (repo root) and KBPIPE_* environment variables.
API keys are read from the environment only and never stored."""
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DEFAULTS = {
    # paths ("~" allowed). prod_db is the only production file the tool writes, through write.py only.
    "prod_db": "~/Car_recommender_app/Flask Based App with Used Cars Function/knowledge_base/carrec_kb.db",
    "backup_dir": "~/Car_recommender_app/Flask Based App with Used Cars Function/knowledge_base/backups",
    "oem_dir": "~/Car_recommender_app/Flask Based App with Used Cars Function/knowledge_base/sources/oem",
    "oem_new_dir": "~/Car_recommender_app/Flask Based App with Used Cars Function/knowledge_base/sources/oem_kbpipe",
    "runs_dir": os.path.join(ROOT, "knowledge_base", "runs"),
    "cache_dir": "~/carrec_kb_cache",
    "history_repo": "~/carrec_kb_history",
    "changelog": os.path.join(ROOT, "knowledge_base", "KB_CHANGELOG.md"),
    # fetching
    "user_agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36",
    "min_seconds_between_requests": 4.0,
    "fetch_timeout": 30,
    "fetch_retries": 2,
    # incremental refresh thresholds (days)
    "refresh_days": {"listing": 0.5, "model_page": 1, "price": 30, "spec": 90, "brochure": 90},
    "link_price_tolerance": 0.005,
    "agree_tolerance": 0.01,
    "model_aliases": {},
    # scope (D-scope in the design spec): makes already in the KB, base price cap in rupees
    "scope_makes": ["Honda", "Hyundai", "Kia", "MG", "Mahindra", "Maruti Suzuki", "Nissan", "Renault", "Skoda",
                    "Tata", "Toyota", "Volkswagen"],
    "scope_max_base_price": 5000000,
    "held_models": ["Seltos", "Brezza", "Baleno", "WagonR", "Jimny", "Kylaq"],   # P7: every change goes to review
    "max_new_models_per_run": 40,
    # reconciliation
    "numeric_tolerance": 0.02,          # relative disagreement above this is a conflict
    # verification
    "verify_every_models": 5,
    "verify_batch_fraction": 0.03,
    "verify_batch_min": 30,
    "verify_bar": 0.95,
    "verify_stop_min_n": 20,
    "audit_per_stratum": 25,
    "human_sheet_n": 30,
    "planted_errors": 20,
    "seed": 20261113,
    # LLM backends: name -> settings. "extract" and "verify" pick one each; they should differ.
    "llm": {
        "extract": ["gemini", "gemini_alt"],          # brochure pages (first that answers is used)
        "verify": ["gemini_alt", "groq"],             # web sources (text)
        "verify_image": ["gemini_alt", "gemini"],     # brochure pages (image)
        "backends": {
            "gemini": {"kind": "gemini", "model": "gemini-3.8-flash", "key_env": "GEMINI_API_KEY", "rpm": 8, "daily_calls": 400},
            "gemini_alt": {"kind": "gemini", "model": "gemini-3.5-flash-lite", "key_env": "GEMINI_API_KEY", "rpm": 12, "daily_calls": 3000},
            "groq": {"kind": "openai", "base_url": "https://api.groq.com/openai/v1", "model": "openai/gpt-oss-120b",
                     "key_env": "GROQ_API_KEY", "rpm": 3, "daily_calls": 900},
            "ollama": {"kind": "ollama", "base_url": "http://localhost:11434", "model": "llama3.2", "rpm": 600, "daily_calls": 100000},
            "claude_cli": {"kind": "claude_cli", "model": "sonnet", "rpm": 30, "daily_calls": 500},
            "mock": {"kind": "mock"}
        }
    },
    "schema_sha256": None,              # pinned by `kbpipe pin-schema`; the schema gate compares against it
}


def _merge(a, b):
    for k, v in b.items():
        if isinstance(v, dict) and isinstance(a.get(k), dict):
            _merge(a[k], v)
        else:
            a[k] = v
    return a


def load(path=None):
    cfg = json.loads(json.dumps(DEFAULTS))
    path = path or os.environ.get("KBPIPE_CONFIG") or os.path.join(ROOT, "kbpipe.config.json")
    if os.path.exists(path):
        with open(path) as f:
            _merge(cfg, json.load(f))
    for k in ("prod_db", "backup_dir", "oem_dir", "oem_new_dir", "runs_dir", "cache_dir", "history_repo", "changelog"):
        env = os.environ.get("KBPIPE_" + k.upper())
        if env:
            cfg[k] = env
        cfg[k] = os.path.abspath(os.path.expanduser(cfg[k]))
    cfg["_path"] = path
    return cfg
