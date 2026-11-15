"""Request and response models. Cards are passed through from services.recsys.api unchanged, so they are typed by
their identifying keys and allow every other key (extra="allow")."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from api_service.config import DEFAULT_LIMIT, MAX_LIMIT, MAX_QUERY_CHARS


def _clean_text(value: str) -> str:
    value = " ".join(value.split())
    if not value:
        raise ValueError("must not be empty")
    return value


class RecommendRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    query: str = Field(..., max_length=MAX_QUERY_CHARS, description="What the buyer wants, in plain words.")
    limit: int = Field(DEFAULT_LIMIT, ge=1, le=MAX_LIMIT, description="Maximum number of cars returned.")
    llm: bool = Field(False, description="Allow the optional LLM parser (only if the server has an API key).")

    @field_validator("query")
    @classmethod
    def _query(cls, v: str) -> str:
        return _clean_text(v)


class Card(BaseModel):
    """One recommended car (the v3 card). Other keys (scores, reasons, expert_notes, owner_notes, caveats ...) pass through."""
    model_config = ConfigDict(extra="allow")
    Make: str
    Model: str
    Variant: Optional[str] = None
    variant_id: Optional[int] = None
    ranking_score: Optional[float] = None
    match_label: Optional[str] = None


class RecommendResponse(BaseModel):
    engine: str
    query_understood: Dict[str, Any] = Field(description="The parsed intent the engine ranked against.")
    results: List[Card]
    relaxed: Optional[Dict[str, Any]] = Field(None, description="Set when no car met every requirement; says what was loosened.")
    generated_at: str
    message: Optional[str] = None
    data_as_of: Optional[Dict[str, Any]] = None
    llm: Optional[Dict[str, Any]] = Field(None, description="Whether the optional LLM parser ran.")


class CompareRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    models: List[str] = Field(..., min_length=2, max_length=4, description="Model names as in the catalogue, e.g. Creta.")
    query: Optional[str] = Field(None, max_length=MAX_QUERY_CHARS)

    @field_validator("models")
    @classmethod
    def _models(cls, v: List[str]) -> List[str]:
        out = [_clean_text(m) for m in v]
        if len({m.lower() for m in out}) != len(out):
            raise ValueError("models must be distinct")
        if any(len(m) > 60 for m in out):
            raise ValueError("model name too long")
        return out

    @field_validator("query")
    @classmethod
    def _query(cls, v: Optional[str]) -> Optional[str]:
        return None if v is None or not v.strip() else _clean_text(v)


class CompareEntry(BaseModel):
    model: str
    found: bool
    card: Optional[Card] = None
    message: Optional[str] = None


class CompareResponse(BaseModel):
    engine: str
    query_understood: Optional[Dict[str, Any]] = None
    models: List[CompareEntry]
    generated_at: str
    data_as_of: Optional[Dict[str, Any]] = None


class HealthResponse(BaseModel):
    status: str
    engine: str
    catalogue_rows: int
    catalogue_models: int
    data_files: Dict[str, Optional[str]]
    llm_available: bool


class EvidenceResponse(BaseModel):
    model: str
    make: Optional[str] = None
    in_catalogue: bool
    expert_rows: List[Dict[str, Any]]
    owner_ratings: List[Dict[str, Any]]
    owner_themes: List[Dict[str, Any]]


class ErrorResponse(BaseModel):
    error: str
    detail: Optional[Any] = None
