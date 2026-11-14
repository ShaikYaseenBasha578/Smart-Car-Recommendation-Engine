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
        "extract": ["claude_sonnet", "gemini", "gemini_alt"],   # brochure pages (first that answers is used)
        "verify": ["gemini_alt", "groq"],                   # web sources (text). Haiku is NOT used: on 2026-11-13 it called 16 exact matches "mismatch"
        "verify_image": ["gemini_alt"],
        # review layers (kbpipe/reviews.py, review_text.py): Claude Sonnet writes, the free chain checks. Never the same backend, never Haiku.
        "reviews_write": ["claude_sonnet"],
        "reviews_check": ["claude_opus", "gemini_alt", "groq"],
        "backends": {
            "gemini": {"kind": "gemini", "model": "gemini-3.8-flash", "key_env": "GEMINI_API_KEY", "rpm": 8, "daily_calls": 400},
            "gemini_alt": {"kind": "gemini", "model": "gemini-3.5-flash-lite", "key_env": "GEMINI_API_KEY", "rpm": 12, "daily_calls": 3000},
            "groq": {"kind": "openai", "base_url": "https://api.groq.com/openai/v1", "model": "openai/gpt-oss-120b",
                     "key_env": "GROQ_API_KEY", "rpm": 3, "daily_calls": 900},
            "ollama": {"kind": "ollama", "base_url": "http://localhost:11434", "model": "llama3.2", "rpm": 600, "daily_calls": 100000},
            "claude_sonnet": {"kind": "claude_cli", "model": "sonnet", "rpm": 20, "daily_calls": 1000},
            "claude_cli": {"kind": "claude_cli", "model": "sonnet", "rpm": 30, "daily_calls": 500},
            "claude_opus": {"kind": "claude_cli", "model": "claude-opus-5-5", "rpm": 20, "daily_calls": 1000},
            "claude_haiku": {"kind": "claude_cli", "model": "haiku", "rpm": 60, "daily_calls": 4000},
            "mock": {"kind": "mock"}
        }
    },
    # brochure layer (kbpipe/brochure.py); see DEFAULTS there for the remaining keys
    "brochure": {"enabled": True, "max_pages_per_brochure": 6, "max_page_reads_per_run": 400},
    # review layers (REVIEW_LAYERS_PLAN.md). Off switch: reviews.sources.autocar.enabled
    "reviews": {
        "sources": {"autocar": {"enabled": True}, "carwale": {"enabled": True}},
        "refresh_days": 90,                 # a page / rows older than this are read again
        "carwale_max_text_pages": 6,        # written-review pages (10 reviews each) read per model for themes
        "themes_enabled": True,      # false (or --no-themes): Autocar notes only, no CarWale written-review reading
        "carwale_max_reviews": 60, "carwale_chunk_size": 60, "carwale_review_chars": 500, "carwale_check_max_chars": 9000,   # cap per model; reviews per writer call; text kept per review
        "min_reviews_sampled": 20, "min_theme_mentions": 3, "low_confidence_ratings": 30,
        "max_note_words": 25, "max_quote_words": 25,
        "verify_fraction": 0.25,            # share of notes/themes re-checked by the verifier (pilot: 1.0)
        "verify_bar": 0.95, "max_llm_calls": 1500,
        "numbers_fraction": 0.15, "numbers_min": 15, "numbers_bar": 0.98,   # independent re-check of the stored scores (plan section 5)
        "saved_pages_dir": "~/carrec_saved_pages/teambhp",
        "autocar_slugs": {"Maruti Suzuki WagonR": "wagon-r", "MG Windsor EV": "windsor", "Mahindra Bolero Neo Plus": "bolero-neoplus",
                          "Mahindra Thar": "thar-og"},   # found 2026-11-15 from the 308 Location headers and Autocar's make listings
        # models with no expert review of their own (checked 2026-11-15; do not guess a neighbour's page): Kia Sorento (hub page has none),
        # Tata Tigor (redirects to Aeris), Hyundai Venue N Line / i20 N Line / Creta N Line (not listed), MG Hector Plus (only Hector is reviewed)
        "autocar_no_review": ["Kia Sorento", "Tata Tigor", "Hyundai Venue N Line", "Hyundai i20 N Line", "Hyundai Creta N Line", "MG Hector Plus"],
        "autocar_page_names": {"Mahindra Thar": "Mahindra Thar OG", "MG Windsor EV": "MG Windsor", "Maruti Suzuki WagonR": "Maruti Suzuki Wagon R",
                               "Mahindra Bolero Neo Plus": "Mahindra Bolero Neo+"},   # KB model name -> the name Autocar's page carries when it differs
        "carwale_slugs": {},     # KB model name -> slug, when the default (lower-case, hyphens) is wrong
        "generation_dates": {},             # KB model name -> ISO date of a facelift/replacement; older reviews become stale_generation
        # source label -> engine aspect(s); used by the export step (not built yet), kept here so a label change is a one-line fix
        "aspect_map": {
            "autocar": {"Performance And Refinement": ["engine_performance", "refinement"],
                        "Ride Comfort And Handling": ["ride_comfort", "handling"],
                        "Interior Space And Comfort": ["front_space", "rear_seat_comfort"],
                        "Mileage / Range And Efficiency": ["real_world_mileage"], "Features And Safety": ["features_tech"],
                        "Value For Money": ["value_for_money"], "Exterior Design And Engineering": ["build_quality"]},
            "carwale": {"Comfort and Space": ["owner_comfort"], "Performance": ["owner_performance"],
                        "Fuel Economy": ["owner_real_world_mileage"], "Value for Money": ["owner_value"],
                        "Features and Technology": ["owner_features"], "After Sales Cost and Experience": ["owner_after_sales"],
                        "overall": ["owner_satisfaction"], "Design and Styling": []},
        },
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
