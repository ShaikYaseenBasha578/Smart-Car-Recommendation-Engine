"""Optional review evidence: expert assessments and owner themes (plan section 3).

Files (both optional; missing, empty or partial files are fine, the engine just has no data):
  data/assessments.csv   make, model, aspect, rating (1-5), quote, source_name, source_url,
                         published_on, variant_scope
  data/owner_themes.csv  make, model, theme, label, direction (positive|negative|mixed), mentions,
                         posts_sampled, period, sample_urls, source_name

Criteria produced (model level; every variant of a model shares them):
  expert_<aspect> = (mean rating - 1) / 4, in [0, 1]; also the number of source rows.
  owner_<theme>   = 0.5 + 0.5 * sign * min(1, share / OWNER_SATURATION_SHARE), where
                    share = mentions / posts_sampled, sign = +1 positive, -1 negative, 0 mixed.
                    0.5 = neutral/no signal; a theme mentioned by a quarter of sampled posts is at full
                    strength. Several rows for one theme (other labels or sources) are averaged weighted by
                    posts_sampled. Rows with posts_sampled < OWNER_MIN_POSTS are ignored (-> unknown).

Review files exported from the KB (scripts/export_reviews_from_kb.py), the format the v3 engine reads by default:
  data/assessments.csv    model, aspect, value (0-1), source, url, published_on, n_sources, raw_score, scale_max,
                          source_aspect   (the legacy layout above is still accepted)
  data/owner_ratings.csv  model, aspect, value (0-1), rating_count, low_confidence, source, url, observed_at,
                          raw_score, scale_max, source_aspect
  expert_<aspect> = mean value of the rows. An 'overall' row is only a fallback for a model with no aspect rows: it
                    fills every expert criterion, and the model's expert class weight is multiplied by
                    config.OVERALL_FALLBACK_SCALE.
  owner_<aspect>  = value shrunk toward the segment mean: w x value + (1 - w) x segment mean, w = count / (count +
                    OWNER_SAMPLE_K). Segment = body type of the model (all models when a segment has fewer than
                    MIN_SEGMENT_MODELS rated models). A rating with no count uses OWNER_NO_COUNT_SCALE as w.
  Environment RECSYS_ASSESSMENTS_CSV / RECSYS_OWNER_RATINGS_CSV point the default loader at other files (a missing
  file = no data), used by the eval.
Rows with an aspect/theme outside the fixed lists, a bad rating/direction, or non-numeric counts are
dropped with a logged warning.
"""

from __future__ import annotations

import json
import logging
import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd

from services.recsys import config
from services.recsys.common import is_unknown

log = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parents[2] / "data"
ASSESSMENTS_CSV = Path(os.environ.get("RECSYS_ASSESSMENTS_CSV") or DATA_DIR / "assessments.csv")
OWNER_THEMES_CSV = DATA_DIR / "owner_themes.csv"
OWNER_RATINGS_CSV = Path(os.environ.get("RECSYS_OWNER_RATINGS_CSV") or DATA_DIR / "owner_ratings.csv")

ASPECTS = ["ride_comfort", "handling", "engine_performance", "refinement", "city_driveability",
           "highway_stability", "front_space", "rear_seat_comfort", "boot_practicality",
           "real_world_mileage", "build_quality", "features_tech", "value_for_money"]
THEMES = ["reliability", "service_cost", "service_experience", "real_world_mileage", "build_issues",
          "recurring_fault", "resale", "satisfaction", "comfort", "performance", "value", "features"]
# owner aspects that are exported but never scored (CarWale "Design and Styling")
UNSCORED_OWNER_ASPECTS = {"design"}
DIRECTIONS = {"positive": 1.0, "negative": -1.0, "mixed": 0.0}

EXPERT_CRITERIA = [f"expert_{a}" for a in ASPECTS]
OWNER_CRITERIA = [f"owner_{t}" for t in THEMES]

ASSESSMENT_COLS = ["make", "model", "aspect", "rating", "quote", "source_name", "source_url",
                   "published_on", "variant_scope"]
OWNER_COLS = ["make", "model", "theme", "label", "direction", "mentions", "posts_sampled", "period",
              "sample_urls", "source_name"]
REVIEW_ASSESSMENT_COLS = ["model", "aspect", "value", "source", "url", "published_on", "n_sources", "raw_score",
                          "scale_max", "source_aspect"]
OWNER_RATING_COLS = ["model", "aspect", "value", "rating_count", "low_confidence", "source", "url", "observed_at",
                     "raw_score", "scale_max", "source_aspect"]
NO_MAKE = ""  # review files carry no make column: their rows are keyed by model name alone


def _label(name: str) -> str:
    return name.split("_", 1)[1].replace("_", " ")


def criterion_label(criterion: str) -> str:
    if criterion.startswith("expert_"):
        return "Experts: " + _label(criterion)
    if criterion.startswith("owner_"):
        return "Owners: " + _label(criterion)
    return criterion


def _read(path: Path, cols: List[str]) -> pd.DataFrame:
    try:
        if path is None or not Path(path).exists() or Path(path).stat().st_size == 0:
            return pd.DataFrame(columns=cols)
        df = pd.read_csv(path, dtype=str, keep_default_na=False)
    except Exception as exc:  # unreadable file: behave as if absent
        log.warning("evidence: cannot read %s (%s); ignoring", path, exc)
        return pd.DataFrame(columns=cols)
    missing = [c for c in cols if c not in df.columns]
    if missing:
        log.warning("evidence: %s lacks columns %s; ignoring file", path, missing)
        return pd.DataFrame(columns=cols)
    return df[cols]


def _read_assessments(path: Path) -> pd.DataFrame:
    """Assessments in either layout: the review-file layout (has a `value` column) or the legacy one."""
    try:
        if path is not None and Path(path).exists() and Path(path).stat().st_size > 0:
            head = pd.read_csv(path, dtype=str, keep_default_na=False, nrows=0)
            if "value" in head.columns:
                return _read(path, REVIEW_ASSESSMENT_COLS)
    except Exception as exc:
        log.warning("evidence: cannot read %s (%s); ignoring", path, exc)
        return pd.DataFrame(columns=ASSESSMENT_COLS)
    return _read(path, ASSESSMENT_COLS)


def _is_review_frame(df: Optional[pd.DataFrame]) -> bool:
    return df is not None and "value" in df.columns and "rating" not in df.columns


def clean_review_assessments(df: pd.DataFrame) -> pd.DataFrame:
    """Review-file layout: value in [0, 1], a model name, an aspect from the fixed list or 'overall'."""
    keep, vals = [], []
    for i, r in df.iterrows():
        try:
            v = float(r["value"])
        except (TypeError, ValueError):
            v = None
        if r["aspect"] not in ASPECTS and r["aspect"] != "overall":
            log.warning("assessments row %s: aspect %r not in the fixed list; dropped", i, r["aspect"])
        elif v is None or not (0.0 <= v <= 1.0):
            log.warning("assessments row %s: value %r not in 0-1; dropped", i, r["value"])
        elif not r["model"]:
            log.warning("assessments row %s: missing model; dropped", i)
        else:
            keep.append(i)
            vals.append(v)
    out = df.loc[keep].copy()
    out["value"] = vals
    out["make"] = NO_MAKE
    out["source_name"] = out["source"]
    out["source_url"] = out["url"]
    out["n_sources"] = pd.to_numeric(out["n_sources"], errors="coerce").fillna(1).astype(int)
    return out.reset_index(drop=True)


def clean_owner_ratings(df: pd.DataFrame) -> pd.DataFrame:
    keep, vals = [], []
    for i, r in df.iterrows():
        try:
            v = float(r["value"])
        except (TypeError, ValueError):
            v = None
        if r["aspect"] in UNSCORED_OWNER_ASPECTS:
            continue
        if r["aspect"] not in THEMES:
            log.warning("owner_ratings row %s: aspect %r not in the fixed list; dropped", i, r["aspect"])
        elif v is None or not (0.0 <= v <= 1.0):
            log.warning("owner_ratings row %s: value %r not in 0-1; dropped", i, r["value"])
        elif not r["model"]:
            log.warning("owner_ratings row %s: missing model; dropped", i)
        else:
            keep.append(i)
            vals.append(v)
    out = df.loc[keep].copy()
    out["value"] = vals
    out["rating_count"] = pd.to_numeric(out["rating_count"], errors="coerce")
    out["make"] = NO_MAKE
    return out.reset_index(drop=True)


def clean_assessments(df: pd.DataFrame) -> pd.DataFrame:
    keep = []
    for i, r in df.iterrows():
        try:
            rating = float(r["rating"])
        except (TypeError, ValueError):
            rating = None
        if r["aspect"] not in ASPECTS:
            log.warning("assessments row %s: aspect %r not in the fixed list; dropped", i, r["aspect"])
        elif rating is None or not (1 <= rating <= 5):
            log.warning("assessments row %s: rating %r not in 1-5; dropped", i, r["rating"])
        elif not r["make"] or not r["model"]:
            log.warning("assessments row %s: missing make/model; dropped", i)
        else:
            keep.append(i)
    out = df.loc[keep].copy()
    out["rating"] = out["rating"].astype(float)
    return out.reset_index(drop=True)


def clean_owner_themes(df: pd.DataFrame) -> pd.DataFrame:
    keep = []
    for i, r in df.iterrows():
        try:
            mentions, posts = int(float(r["mentions"])), int(float(r["posts_sampled"]))
        except (TypeError, ValueError):
            mentions = posts = None
        if r["theme"] not in THEMES:
            log.warning("owner_themes row %s: theme %r not in the fixed list; dropped", i, r["theme"])
        elif r["direction"] not in DIRECTIONS:
            log.warning("owner_themes row %s: direction %r invalid; dropped", i, r["direction"])
        elif mentions is None or posts is None or posts <= 0 or mentions < 0:
            log.warning("owner_themes row %s: mentions/posts_sampled invalid; dropped", i)
        elif not r["make"] or not r["model"]:
            log.warning("owner_themes row %s: missing make/model; dropped", i)
        else:
            keep.append(i)
    out = df.loc[keep].copy()
    out["mentions"] = out["mentions"].astype(float).astype(int)
    out["posts_sampled"] = out["posts_sampled"].astype(float).astype(int)
    return out.reset_index(drop=True)


def owner_theme_value(rows: pd.DataFrame) -> Optional[Dict[str, Any]]:
    """Value in [0,1] for one (model, theme) from its rows, or None if no row has enough posts."""
    rows = rows[rows["posts_sampled"] >= config.OWNER_MIN_POSTS]
    if rows.empty:
        return None
    total_posts = float(rows["posts_sampled"].sum())
    acc = 0.0
    for _, r in rows.iterrows():
        share = min(1.0, r["mentions"] / r["posts_sampled"])
        strength = min(1.0, share / config.OWNER_SATURATION_SHARE)
        acc += r["posts_sampled"] * (0.5 + 0.5 * DIRECTIONS[r["direction"]] * strength)
    return {"value": acc / total_posts, "rows": rows}


def owner_scale_for_count(count: Optional[float]) -> float:
    """count / (count + OWNER_SAMPLE_K); OWNER_NO_COUNT_SCALE when no count is available."""
    if count is None or not count > 0:
        return config.OWNER_NO_COUNT_SCALE
    return float(count) / (float(count) + config.OWNER_SAMPLE_K)


class Evidence:
    """Holds the evidence frames and answers per-model criterion lookups."""

    def __init__(self, assessments: Optional[pd.DataFrame] = None, owner_themes: Optional[pd.DataFrame] = None,
                 owner_ratings: Optional[pd.DataFrame] = None, segments: Optional[Dict[str, str]] = None):
        """`segments` maps model name -> segment (body type), used to shrink owner ratings toward a segment mean."""
        review = _is_review_frame(assessments) and len(assessments) > 0
        if review:
            self.assessments = clean_review_assessments(assessments)
        elif assessments is not None and len(assessments) and not _is_review_frame(assessments):
            self.assessments = clean_assessments(assessments)
        else:
            self.assessments = pd.DataFrame(columns=ASSESSMENT_COLS)
        self.owner_themes = clean_owner_themes(owner_themes) if owner_themes is not None and len(owner_themes) \
            else pd.DataFrame(columns=OWNER_COLS)
        self.owner_ratings = clean_owner_ratings(owner_ratings) if owner_ratings is not None and len(owner_ratings) \
            else pd.DataFrame(columns=OWNER_RATING_COLS)
        self.segments = dict(segments or {})
        self._expert: Dict[tuple, dict] = {}
        self._expert_overall: Dict[tuple, dict] = {}  # (make, model) -> overall-only fallback, models with no aspect row
        self._owner: Dict[tuple, dict] = {}
        if len(self.assessments):
            if review:
                self._build_expert_reviews()
            else:
                for (make, model, aspect), g in self.assessments.groupby(["make", "model", "aspect"]):
                    self._expert[(make, model, aspect)] = {
                        "value": (g["rating"].mean() - 1.0) / 4.0, "mean_rating": float(g["rating"].mean()),
                        "n_sources": int(len(g)), "rows": g}
        for (make, model, theme), g in self.owner_themes.groupby(["make", "model", "theme"]):
            res = owner_theme_value(g)
            if res is not None:
                self._owner[(make, model, theme)] = res
        self._build_owner_ratings()  # ratings win over themes for the same criterion

    def _build_expert_reviews(self) -> None:
        df = self.assessments
        for (make, model, aspect), g in df[df["aspect"] != "overall"].groupby(["make", "model", "aspect"]):
            self._expert[(make, model, aspect)] = {
                "value": float(g["value"].mean()), "mean_rating": None,
                "n_sources": int(max(g["n_sources"].max(), g["source_name"].nunique())), "rows": g}
        have = {(mk, md) for (mk, md, _a) in self._expert}
        for (make, model), g in df[df["aspect"] == "overall"].groupby(["make", "model"]):
            if (make, model) not in have:
                self._expert_overall[(make, model)] = {
                    "value": float(g["value"].mean()), "mean_rating": None,
                    "n_sources": int(max(g["n_sources"].max(), g["source_name"].nunique())), "rows": g,
                    "fallback": True}

    def _segment_means(self, raw: Dict[tuple, float]) -> Dict[tuple, float]:
        """{(segment, aspect): mean of the models' raw values}; a segment with fewer than MIN_SEGMENT_MODELS rated
        models falls back to the mean over all models (segment '*')."""
        by_seg: Dict[tuple, List[float]] = {}
        for (model, aspect), v in raw.items():
            by_seg.setdefault((self.segments.get(model, "*"), aspect), []).append(v)
            by_seg.setdefault(("*", aspect), []).append(v)
        out = {}
        for (seg, aspect), vals in by_seg.items():
            if seg == "*" or len(vals) >= config.MIN_SEGMENT_MODELS:
                out[(seg, aspect)] = sum(vals) / len(vals)
        return out

    def _build_owner_ratings(self) -> None:
        df = self.owner_ratings
        if df.empty:
            return
        raw: Dict[tuple, float] = {}
        groups = {}
        for (model, aspect), g in df.groupby(["model", "aspect"]):
            raw[(model, aspect)] = float(g["value"].mean())
            groups[(model, aspect)] = g
        means = self._segment_means(raw)
        for (model, aspect), g in groups.items():
            seg = self.segments.get(model, "*")
            mean = means.get((seg, aspect), means[("*", aspect)])
            count = pd.to_numeric(g["rating_count"], errors="coerce").dropna().max() if len(g) else None
            w = owner_scale_for_count(None if count is None or pd.isna(count) else float(count))
            self._owner[(NO_MAKE, model, aspect)] = {
                "value": w * raw[(model, aspect)] + (1.0 - w) * mean, "raw_value": raw[(model, aspect)],
                "segment_mean": mean, "shrink_weight": w, "rows": g, "kind": "rating"}

    # -- lookups: review files carry no make, so a (make, model) lookup falls back to the make-less key ------------
    def _hit(self, table: Dict[tuple, dict], make: str, model: str, key: str) -> Optional[dict]:
        return table.get((make, model, key)) or table.get((NO_MAKE, model, key))

    def _overall_hit(self, make: str, model: str) -> Optional[dict]:
        return self._expert_overall.get((make, model)) or self._expert_overall.get((NO_MAKE, model))

    # -- how much evidence a car has (scales the class weights in score.py) ---------------------------------
    @staticmethod
    def _source_key(row: pd.Series) -> str:
        return (str(row.get("source_name") or "").strip() or str(row.get("source_url") or "").strip() or "anonymous")

    def expert_scale(self, make: str, model: str, relevant_aspects: List[str]) -> Optional[float]:
        """scale in [0, 1] for the expert class weight of one model, or None when it has no expert row.
        (relevant aspects the model has a value for / relevant aspects) x n_sources / (n_sources + EXPERT_SOURCE_K),
        n_sources = distinct sources behind those covered aspects."""
        covered = [a for a in relevant_aspects if self._hit(self._expert, make, model, a)]
        if not any(self._hit(self._expert, make, model, a) for a in ASPECTS):
            fb = self._overall_hit(make, model)
            if fb is None:
                return None
            if not relevant_aspects:
                return 0.0
            n = fb["n_sources"]  # the overall score stands for every aspect, at a low weight
            return config.OVERALL_FALLBACK_SCALE * n / (n + config.EXPERT_SOURCE_K)
        if not covered or not relevant_aspects:
            return 0.0
        sources = {self._source_key(r) for a in covered
                   for _, r in self._hit(self._expert, make, model, a)["rows"].iterrows()}
        n = len(sources)
        return (len(covered) / len(relevant_aspects)) * (n / (n + config.EXPERT_SOURCE_K))

    def owner_sample(self, make: str, model: str) -> Optional[int]:
        """Number of posts behind the model's owner themes: the largest per-theme sum of posts_sampled (themes of
        one sample repeat the same posts), or None when no count is available."""
        best: Optional[int] = None
        for t in THEMES:
            hit = self._hit(self._owner, make, model, t)
            if hit is None:
                continue
            col = "posts_sampled" if "posts_sampled" in hit["rows"].columns else "rating_count"
            if col not in hit["rows"].columns:
                continue
            total = pd.to_numeric(hit["rows"][col], errors="coerce").dropna().sum()
            if total > 0:
                best = max(best or 0, int(total))
        return best

    def owner_scale(self, make: str, model: str) -> Optional[float]:
        """scale in [0, 1] for the owner class weight (count / (count + OWNER_SAMPLE_K)), None without owner rows."""
        if not any(self._hit(self._owner, make, model, t) for t in THEMES):
            return None
        return owner_scale_for_count(self.owner_sample(make, model))

    @classmethod
    def load(cls, assessments_path: Any = None, owner_path: Any = None, ratings_path: Any = None,
             segments: Optional[Dict[str, str]] = None) -> "Evidence":
        """Evidence from the data files. `segments` defaults to model -> body type from the catalogue."""
        if segments is None:
            segments = catalogue_segments()
        return cls(_read_assessments(assessments_path or ASSESSMENTS_CSV),
                   _read(owner_path or OWNER_THEMES_CSV, OWNER_COLS),
                   _read(ratings_path or OWNER_RATINGS_CSV, OWNER_RATING_COLS), segments=segments)

    @property
    def empty(self) -> bool:
        return not self._expert and not self._owner and not self._expert_overall

    def expert(self, make: str, model: str, aspect: str) -> Optional[dict]:
        return self._hit(self._expert, make, model, aspect) or self._overall_hit(make, model)

    def owner(self, make: str, model: str, theme: str) -> Optional[dict]:
        return self._hit(self._owner, make, model, theme)

    def values_for(self, df: pd.DataFrame) -> pd.DataFrame:
        """expert_* and owner_* values (NaN unknown) per row of `df`."""
        cols = EXPERT_CRITERIA + OWNER_CRITERIA
        out = pd.DataFrame(index=df.index, columns=cols, dtype=float)
        if self.empty:
            return out
        for i, (make, model) in zip(df.index, zip(df["make"], df["model"])):
            for a in ASPECTS:
                hit = self.expert(make, model, a)
                if hit:
                    out.at[i, f"expert_{a}"] = hit["value"]
            for t in THEMES:
                hit = self.owner(make, model, t)
                if hit:
                    out.at[i, f"owner_{t}"] = hit["value"]
        return out

    def detail_for(self, make: str, model: str, criterion: str) -> Optional[dict]:
        """Numbers and a source link behind one expert_/owner_ value, for explanations."""
        if criterion.startswith("expert_"):
            hit = self.expert(make, model, criterion[len("expert_"):])
            if not hit:
                return None
            rows = hit["rows"]
            urls = [u for u in rows["source_url"] if u]
            out = {"mean_rating": hit["mean_rating"], "n_sources": hit["n_sources"],
                   "source_url": urls[0] if urls else None,
                   "quote": next((q for q in rows["quote"] if q), None) if "quote" in rows.columns else None}
            if "value" in rows.columns:  # review-file rows: raw score on the source's scale, label and date
                r = rows.iloc[0]
                out.update(kind="review", fallback=bool(hit.get("fallback")), source=r["source_name"],
                           raw_score=float(r["raw_score"]), scale_max=float(r["scale_max"]),
                           source_aspect=r["source_aspect"], published_on=r["published_on"] or None)
            return out
        if criterion.startswith("owner_"):
            hit = self.owner(make, model, criterion[len("owner_"):])
            if not hit:
                return None
            rows = hit["rows"]
            if hit.get("kind") == "rating":
                r = rows.iloc[0]
                count = pd.to_numeric(rows["rating_count"], errors="coerce").max()
                return {"kind": "rating", "raw_score": float(r["raw_score"]), "scale_max": float(r["scale_max"]),
                        "rating_count": None if pd.isna(count) else int(count),
                        "low_confidence": str(r["low_confidence"]).lower() == "true", "source": r["source"],
                        "observed_at": r["observed_at"] or None, "source_aspect": r["source_aspect"],
                        "source_url": r["url"] or None}
            top = rows.sort_values("posts_sampled", ascending=False).iloc[0]
            urls: List[str] = []
            try:
                urls = [u for u in json.loads(top["sample_urls"] or "[]") if u]
            except (TypeError, ValueError):
                urls = []
            return {"direction": top["direction"], "mentions": int(rows["mentions"].sum()),
                    "posts_sampled": int(rows["posts_sampled"].sum()), "period": top["period"] or None,
                    "label": top["label"] or None, "source_url": urls[0] if urls else None}
        return None


def catalogue_segments() -> Dict[str, str]:
    """model name -> body type (first variant's), the segment owner ratings are shrunk toward. {} if unavailable."""
    try:
        from services.catalogue import get_catalogue
        cat = get_catalogue()
        return {m: str(b) for m, b in zip(cat["model"], cat["body_type"]) if b is not None}
    except Exception as exc:  # no catalogue: one global segment
        log.warning("evidence: no catalogue segments (%s)", exc)
        return {}


@lru_cache(maxsize=1)
def _default() -> Evidence:
    return Evidence.load()


def get_evidence(refresh: bool = False) -> Evidence:
    """Evidence from the two data files (cached; refresh=True re-reads them)."""
    if refresh or os.environ.get("RECSYS_NO_EVIDENCE_CACHE"):
        _default.cache_clear()
    return _default()
