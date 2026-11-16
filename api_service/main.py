"""FastAPI service for the v3 recommender.

Reads the engine only through services.recsys.api (and, for compare, the existing intent parser). Run:
    uvicorn api_service.main:app
"""

from __future__ import annotations

from api_service.config import apply_process_env

apply_process_env()  # before any services.* import: services.catalogue reads CARREC_CATALOGUE_DIR at import

import copy  # noqa: E402
import datetime as dt  # noqa: E402
import json  # noqa: E402
import logging  # noqa: E402
import os  # noqa: E402
import threading  # noqa: E402
from contextlib import contextmanager  # noqa: E402
from pathlib import Path  # noqa: E402
from typing import Any, Dict, List, Optional  # noqa: E402

import pandas as pd  # noqa: E402
from fastapi import FastAPI, HTTPException, Request  # noqa: E402
from fastapi.exceptions import RequestValidationError  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from fastapi.responses import JSONResponse  # noqa: E402
from starlette.exceptions import HTTPException as StarletteHTTPException  # noqa: E402

from api_service import config, schemas  # noqa: E402
from services import catalogue as catalogue_mod  # noqa: E402
from services.intent_v2 import parse_intent_ex  # noqa: E402
from services.recsys import evidence as evidence_mod  # noqa: E402
from services.recsys.api import recommend as engine_recommend  # noqa: E402

log = logging.getLogger("api_service")

# The engine reads process env (LLM_PARSER) and shared frames; one request at a time keeps both consistent.
_ENGINE_LOCK = threading.Lock()


def _now() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


@contextmanager
def _llm_setting(on: bool):
    """LLM_PARSER is on only for a request that asked for it AND only when a key is configured; restored afterwards."""
    previous = os.environ.get("LLM_PARSER")
    os.environ["LLM_PARSER"] = "on" if on else "off"
    try:
        yield
    finally:
        if previous is None:
            os.environ.pop("LLM_PARSER", None)
        else:
            os.environ["LLM_PARSER"] = previous


def _file_date(path: Path) -> Optional[str]:
    try:
        return dt.datetime.fromtimestamp(path.stat().st_mtime, dt.timezone.utc).strftime("%Y-%m-%d")
    except OSError:
        return None


def _jsonable(value: Any) -> Any:
    if isinstance(value, float) and value != value:
        return None
    return value


def _records(df: pd.DataFrame) -> List[Dict[str, Any]]:
    out = []
    for rec in df.to_dict("records"):
        out.append({k: _jsonable(v) for k, v in rec.items()})
    return out


def _read_csv(path: Path) -> pd.DataFrame:
    try:
        return pd.read_csv(path, dtype=str, keep_default_na=False)
    except (OSError, ValueError):
        return pd.DataFrame(columns=["model"])


def _typed(rec: Dict[str, Any], numeric: List[str]) -> Dict[str, Any]:
    for key in numeric:
        if key in rec and rec[key] not in (None, ""):
            try:
                rec[key] = float(rec[key])
            except ValueError:
                pass
        elif key in rec:
            rec[key] = None
    return rec


def _blank_to_none(rec: Dict[str, Any]) -> Dict[str, Any]:
    return {k: (None if v == "" else v) for k, v in rec.items()}


def _find_model(name: str) -> Optional[Dict[str, str]]:
    df = catalogue_mod.get_catalogue()
    hit = df[df["model"].str.lower() == name.strip().lower()]
    if hit.empty:
        return None
    return {"make": str(hit.iloc[0]["make"]), "model": str(hit.iloc[0]["model"])}


def _error(status: int, code: str, detail: Any = None) -> JSONResponse:
    return JSONResponse(status_code=status, content={"error": code, "detail": detail})


def create_app() -> FastAPI:
    app = FastAPI(title="CarRec recommender API", version="1.0.0",
                  description="The v3 car recommender as a typed service. Same engine as the website.",
                  docs_url="/docs", redoc_url=None)

    origins = config.cors_origins()
    if origins:
        app.add_middleware(CORSMiddleware, allow_origins=origins, allow_methods=["GET", "POST"],
                           allow_headers=["Content-Type"])

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, exc: RequestValidationError):
        detail = [{"field": ".".join(str(p) for p in e.get("loc", ()) if p != "body"), "message": e.get("msg", "invalid")}
                  for e in exc.errors()]
        return _error(422, "invalid_request", detail)

    @app.exception_handler(StarletteHTTPException)
    async def _http(_: Request, exc: StarletteHTTPException):
        return _error(exc.status_code, "not_found" if exc.status_code == 404 else "http_error", exc.detail)

    @app.exception_handler(Exception)
    async def _unexpected(_: Request, exc: Exception):
        log.exception("unhandled error")  # the trace stays in the server log, never in the response
        return _error(500, "internal_error", "The recommender failed on this request.")

    @app.get("/health", response_model=schemas.HealthResponse)
    def health():
        df = catalogue_mod.get_catalogue()
        meta = catalogue_mod.get_meta()
        data_files = {
            "catalogue_export_utc": meta.get("export_utc"),
            "kb_latest_phase": meta.get("kb_latest_phase"),
            "catalogue_csv": _file_date(catalogue_mod.CATALOGUE_CSV),
            "assessments_csv": _file_date(evidence_mod.ASSESSMENTS_CSV),
            "owner_ratings_csv": _file_date(evidence_mod.OWNER_RATINGS_CSV),
            "owner_themes_csv": _file_date(evidence_mod.OWNER_THEMES_CSV),
        }
        return {"status": "ok", "engine": config.ENGINE_VERSION, "catalogue_rows": int(len(df)),
                "catalogue_models": int(df["model"].nunique()), "data_files": data_files,
                "llm_available": config.llm_key_present()}

    @app.post("/v1/recommend", response_model=schemas.RecommendResponse)
    def recommend(req: schemas.RecommendRequest):
        use_llm = bool(req.llm and config.llm_key_present())
        with _ENGINE_LOCK, _llm_setting(use_llm):
            payload = engine_recommend(req.query)
        cards = payload.get("recommendations", [])[: req.limit]
        return {"engine": payload.get("engine", config.ENGINE_VERSION), "query_understood": payload.get("intent", {}),
                "results": cards, "relaxed": payload.get("relaxation"), "generated_at": _now(),
                "message": payload.get("message"), "data_as_of": payload.get("data_as_of"), "llm": payload.get("llm")}

    @app.get("/v1/models/{model}/evidence", response_model=schemas.EvidenceResponse)
    def model_evidence(model: str):
        if len(model) > 60:
            raise HTTPException(status_code=404, detail="Unknown model.")
        found = _find_model(model)
        name = found["model"] if found else model.strip()
        key = name.lower()

        def rows(path: Path) -> pd.DataFrame:
            df = _read_csv(path)
            return df[df["model"].str.lower() == key] if "model" in df.columns else df.iloc[0:0]

        expert = [_typed(_blank_to_none(r), ["value", "raw_score", "scale_max", "n_sources"])
                  for r in _records(rows(evidence_mod.ASSESSMENTS_CSV))]
        ratings = [_typed(_blank_to_none(r), ["value", "rating_count", "raw_score", "scale_max"])
                   for r in _records(rows(evidence_mod.OWNER_RATINGS_CSV))]
        themes = []
        for r in _records(rows(evidence_mod.OWNER_THEMES_CSV)):
            r = _typed(_blank_to_none(r), ["mentions", "posts_sampled", "share"])
            try:
                r["sample_urls"] = json.loads(r["sample_urls"]) if r.get("sample_urls") else []
            except ValueError:
                r["sample_urls"] = []
            themes.append(r)
        if not found and not (expert or ratings or themes):
            raise HTTPException(status_code=404, detail="Unknown model.")
        return {"model": name, "make": found["make"] if found else None, "in_catalogue": bool(found),
                "expert_rows": expert, "owner_ratings": ratings, "owner_themes": themes}

    @app.post("/v1/compare", response_model=schemas.CompareResponse)
    def compare(req: schemas.CompareRequest):
        """The engine has no compare function. For each model: parse the query once with the existing parser, pin the
        intent to that model, and call services.recsys.api.recommend with the supplied intent (nothing in services/ changes)."""
        resolved = [(m, _find_model(m)) for m in req.models]
        unknown = [m for m, hit in resolved if hit is None]
        if unknown:
            return _error(404, "unknown_model", {"models": unknown})
        entries: List[Dict[str, Any]] = []
        with _ENGINE_LOCK, _llm_setting(False):
            base, _ = parse_intent_ex(req.query or "")
            understood = None
            data_as_of = None
            for _, hit in resolved:
                intent = copy.deepcopy(base)
                intent.update({"models": [hit["model"]], "makes": [], "reference_models": [], "exclude_makes": []})
                payload = engine_recommend(req.query or "", intent=intent)
                data_as_of = payload.get("data_as_of")
                cards = payload.get("recommendations", [])
                if understood is None:
                    understood = {k: v for k, v in base.items() if k not in ("models", "makes", "reference_models", "exclude_makes", "trace")}
                if cards:
                    entries.append({"model": hit["model"], "found": True, "card": cards[0]})
                else:
                    entries.append({"model": hit["model"], "found": False,
                                    "message": payload.get("message") or "No variant of this model meets the requirements."})
        return {"engine": config.ENGINE_VERSION, "query_understood": understood, "models": entries,
                "generated_at": _now(), "data_as_of": data_as_of}

    return app


app = create_app()
