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
OWNER_THEMES_CSV = Path(os.environ.get("RECSYS_OWNER_THEMES_CSV") or DATA_DIR / "owner_themes.csv")
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
# optional text columns of the review-file layout (older files lack them: no notes then)
ASSESSMENT_TEXT_COLS = ["note", "quote"]
# owner_themes.csv exported from the KB (no make column; `source` instead of `source_name`; share = mentions / posts)
EXPORT_THEME_COLS = ["model", "theme", "label", "direction", "mentions", "posts_sampled", "share", "note",
                     "sample_urls", "source", "period"]
NO_MAKE = ""  # review files carry no make column: their rows are keyed by model name alone


def _label(name: str) -> str:
    return name.split("_", 1)[1].replace("_", " ")


def criterion_label(criterion: str) -> str:
    if criterion.startswith("expert_"):
        return "Experts: " + _label(criterion)
    if criterion.startswith("owner_"):
        return "Owners: " + _label(criterion)
    return criterion


def _read(path: Path, cols: List[str], optional: Optional[List[str]] = None) -> pd.DataFrame:
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
        return pd.DataFrame(columns=cols + list(optional or []))
    for c in optional or []:
        if c not in df.columns:
            df[c] = ""
    return df[cols + list(optional or [])]


def _read_assessments(path: Path) -> pd.DataFrame:
    """Assessments in either layout: the review-file layout (has a `value` column) or the legacy one."""
    try:
        if path is not None and Path(path).exists() and Path(path).stat().st_size > 0:
            head = pd.read_csv(path, dtype=str, keep_default_na=False, nrows=0)
            if "value" in head.columns:
                return _read(path, REVIEW_ASSESSMENT_COLS, ASSESSMENT_TEXT_COLS)
    except Exception as exc:
        log.warning("evidence: cannot read %s (%s); ignoring", path, exc)
        return pd.DataFrame(columns=ASSESSMENT_COLS)
    return _read(path, ASSESSMENT_COLS)


def _read_themes(path: Path) -> pd.DataFrame:
    """Owner themes in either layout: the KB export (no make column, has `share`) or the legacy one."""
    try:
        if path is not None and Path(path).exists() and Path(path).stat().st_size > 0:
            head = pd.read_csv(path, dtype=str, keep_default_na=False, nrows=0)
            if "make" not in head.columns and "model" in head.columns:
                return _read(path, EXPORT_THEME_COLS)
    except Exception as exc:
        log.warning("evidence: cannot read %s (%s); ignoring", path, exc)
        return pd.DataFrame(columns=EXPORT_THEME_COLS)
    return _read(path, OWNER_COLS)


def _is_export_theme_frame(df: Optional[pd.DataFrame]) -> bool:
    return df is not None and "model" in df.columns and "make" not in df.columns and "share" in df.columns


def clean_export_themes(df: pd.DataFrame) -> pd.DataFrame:
    """Exported theme rows: a model, a theme from the fixed list, a direction, 0 <= mentions <= posts_sampled."""
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
        elif mentions is None or posts is None or posts <= 0 or mentions < 0 or mentions > posts:
            log.warning("owner_themes row %s: mentions/posts_sampled invalid; dropped", i)
        elif not r["model"]:
            log.warning("owner_themes row %s: missing model; dropped", i)
        else:
            keep.append(i)
    out = df.loc[keep].copy()
    out["mentions"] = out["mentions"].astype(float).astype(int)
    out["posts_sampled"] = out["posts_sampled"].astype(float).astype(int)
    return out.reset_index(drop=True)


def theme_strength(mentions: int, posts: int) -> float:
    """Strength in [0, 1] of one theme row: share of the sampled reviews that mention it (full at
    OWNER_SATURATION_SHARE) times posts / (posts + OWNER_SAMPLE_K), so a small sample counts for less."""
    if posts <= 0:
        return 0.0
    share = min(1.0, mentions / posts)
    return min(1.0, share / config.OWNER_SATURATION_SHARE) * posts / (posts + config.OWNER_SAMPLE_K)


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
    for c in ASSESSMENT_TEXT_COLS:  # files without the text columns: no notes, no quotes
        if c not in out.columns:
            out[c] = ""
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
        # exported themes (model-keyed, see EXPORT_THEME_COLS) feed a capped adjustment of the owner sub-score and the
        # explanations; the legacy layout (make-keyed) keeps feeding the owner_<theme> criteria
        self.themes = clean_export_themes(owner_themes) if _is_export_theme_frame(owner_themes) and len(owner_themes) \
            else pd.DataFrame(columns=EXPORT_THEME_COLS)
        legacy = owner_themes if owner_themes is not None and not _is_export_theme_frame(owner_themes) else None
        self.owner_themes = clean_owner_themes(legacy) if legacy is not None and len(legacy) \
            else pd.DataFrame(columns=OWNER_COLS)
        self.owner_ratings = clean_owner_ratings(owner_ratings) if owner_ratings is not None and len(owner_ratings) \
            else pd.DataFrame(columns=OWNER_RATING_COLS)
        self.segments = dict(segments or {})
        self._expert: Dict[tuple, dict] = {}
        self._expert_overall: Dict[tuple, dict] = {}  # (make, model) -> overall-only fallback, models with no aspect row
        self._overall_all: Dict[tuple, dict] = {}     # (make, model) -> the model's overall row(s), every model that has one
        self._neutral_cache: Dict[tuple, Any] = {}
        self._owner: Dict[tuple, dict] = {}
        self._themes: Dict[str, List[dict]] = {}
        for r in self.themes.to_dict("records"):
            self._themes.setdefault(r["model"], []).append(r)
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
            self._overall_all[(make, model)] = {"value": float(g["value"].mean()), "rows": g}
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

    @property
    def data_aspects(self) -> set:
        """Expert aspects with at least one row for any model (the only ones a model can be rated on)."""
        if not hasattr(self, "_data_aspects"):
            self._data_aspects = {a for (_m, _n, a) in self._expert}
        return self._data_aspects

    def _overall_hit_any(self, make: str, model: str) -> Optional[dict]:
        """The model's overall expert row (review layout), whether or not it also has aspect rows."""
        hit = self._overall_all.get((make, model)) or self._overall_all.get((NO_MAKE, model))
        if hit is None:
            return None
        rows = hit["rows"]
        return {"value": hit["value"], "n_sources": int(max(rows["n_sources"].max(), rows["source_name"].nunique())),
                "rows": rows}

    @staticmethod
    def _group_key(aspect: str, hit: dict) -> tuple:
        """Aspects one source label feeds together share a key (review layout); every other aspect is its own."""
        rows = hit["rows"]
        if "source_aspect" in rows.columns and len(rows):
            r = rows.iloc[0]
            label = str(r.get("source_aspect") or "")
            src = str(r.get("source_name") if "source_name" in rows.columns else r.get("source") or "")
            if label:
                return (src, label)
        return (aspect,)

    def class_sub(self, kind: str, make: str, model: str, aspect_w: Optional[Dict[str, float]]) -> Optional[float]:
        """The model's expert or owner sub-score in [0, 1], or None when it has no usable row.
        aspect_w: {aspect: query weight} (weights.review_aspect_weights); None = the query states no preference, so
        only the 'overall' rows count (expert overall; owner satisfaction), falling back to the aspects at equal
        weight when the model has no such row. Aspects fed by one source label count once (the mean of their weights),
        aspects with weight 0 count not at all."""
        if kind == "expert":
            table, names, overall_name = self._expert, ASPECTS, config.EXPERT_OVERALL_ASPECT
        else:
            table, names, overall_name = self._owner, THEMES, config.OWNER_OVERALL_ASPECT
        hits = {a: h for a in names if (h := self._hit(table, make, model, a))}
        if kind == "expert":
            ov = self._overall_hit_any(make, model)
            if not hits:
                return None if ov is None else ov["value"]       # overall-only model: it stands for every aspect
            if aspect_w is None and ov is not None:
                return ov["value"]
        elif not hits:
            return None
        elif aspect_w is None and overall_name in hits:
            return hits[overall_name]["value"]
        if aspect_w is None:                                     # no overall row to use: all aspects at equal weight
            aspect_w = {a: 1.0 for a in hits}
        groups: Dict[tuple, List[tuple]] = {}
        for a, h in hits.items():
            w = aspect_w.get(a, 0.0)
            if w > 0:
                groups.setdefault(self._group_key(a, h), []).append((w, h["value"]))
        if not groups:
            return None
        num = den = 0.0
        for members in groups.values():
            gw = sum(w for w, _ in members) / len(members)       # the group counts once
            num += gw * (sum(v for _, v in members) / len(members))
            den += gw
        return num / den if den > 0 else None

    # -- owner themes (text-derived) and expert notes --------------------------------------------------------------
    def theme_rows(self, model: str) -> List[dict]:
        return list(self._themes.get(model, []))

    def theme_adjustment(self, model: str, aspect_w: Optional[Dict[str, float]]) -> float:
        """Signed change to the model's owner sub-score from its themes, within +-THEME_ADJUST_CAP x the sub-score range
        (1.0). Each theme row is signal = direction (+1 / 0 / -1) x theme_strength; a row counts with the query weight of
        its theme (the same OWNER_THEME_CRITERIA weights the ratings use; a query with no preference counts only the
        satisfaction theme; weight 0 = not counted). The adjustment is cap x the weighted mean signal of the rows the
        model has, so a model with no themes (or none relevant) gets exactly 0: neutral, not penalised."""
        rows = self._themes.get(model)
        if not rows:
            return 0.0
        weight = {config.OWNER_OVERALL_ASPECT: 1.0} if aspect_w is None else aspect_w
        num = den = 0.0
        for r in rows:
            w = weight.get(r["theme"], 0.0)
            if w <= 0:
                continue
            num += w * DIRECTIONS[r["direction"]] * theme_strength(int(r["mentions"]), int(r["posts_sampled"]))
            den += w
        if den <= 0:
            return 0.0
        return config.THEME_ADJUST_CAP * max(-1.0, min(1.0, num / den))

    def expert_notes(self, model: str) -> List[dict]:
        """One entry per source label of the model that has a note (review layout), with the engine aspects it feeds:
        {source, source_aspect, aspects, raw_score, scale_max, published_on, source_url, note, quote}. Text is exactly
        as exported."""
        df = self.assessments
        if df.empty or "note" not in df.columns or "source_aspect" not in df.columns:
            return []
        g = df[(df["model"] == model) & (df["aspect"] != "overall") & (df["note"].astype(str) != "")]
        out: Dict[tuple, dict] = {}
        for _, r in g.iterrows():
            k = (r["source_name"], r["source_aspect"])
            if k not in out:
                out[k] = {"source": r["source_name"], "source_aspect": r["source_aspect"], "aspects": [],
                          "raw_score": float(r["raw_score"]), "scale_max": float(r["scale_max"]),
                          "published_on": r["published_on"] or None, "source_url": r["source_url"] or None,
                          "note": r["note"], "quote": r["quote"] or None}
            out[k]["aspects"].append(r["aspect"])
        return [out[k] for k in sorted(out)]

    # -- standing within the segment (display only; never read by the score) -------------------------------------
    def _standing_populations(self, kind: str) -> Dict[str, List[float]]:
        """{segment: sorted raw ratings (as a share of the scale) of the segment's rated models}: owners' overall
        (satisfaction) rating, or Autocar's overall score. Same segments as the owner-rating shrinkage."""
        cache = self.__dict__.setdefault("_standing_pops", {})
        if kind not in cache:
            pops: Dict[str, List[float]] = {}
            for model, v in self._standing_values(kind).items():
                pops.setdefault(self.segments.get(model, "*"), []).append(v)
            cache[kind] = {seg: sorted(vals) for seg, vals in pops.items()}
        return cache[kind]

    def _standing_values(self, kind: str) -> Dict[str, float]:
        out: Dict[str, float] = {}
        if kind == "owner":
            df = self.owner_ratings
            if not df.empty:
                for _, r in df[df["aspect"] == config.OWNER_OVERALL_ASPECT].iterrows():
                    out[r["model"]] = round(float(r["raw_score"]) / float(r["scale_max"]), 4)
        else:
            df = self.assessments
            if len(df) and "raw_score" in df.columns:
                for model, g in df[df["aspect"] == config.EXPERT_OVERALL_ASPECT].groupby("model"):
                    share = (pd.to_numeric(g["raw_score"], errors="coerce") / pd.to_numeric(g["scale_max"], errors="coerce")).dropna()
                    if len(share):
                        out[model] = round(float(share.mean()), 4)
        return out

    def standing(self, kind: str, model: str) -> Optional[dict]:
        """{"value": 0-100 or None, "band": top|upper|lower|bottom|small_segment, "segment", "n_models"} for a model with an
        overall rating of this kind, else None. value is the mid-rank percentile of the model's overall rating among the
        rated models of its segment (ties count half); None when the segment has fewer than MIN_SEGMENT_MODELS rated models."""
        mine = self._standing_values(kind).get(model)
        if mine is None:
            return None
        seg = self.segments.get(model, "*")
        pop = self._standing_populations(kind).get(seg, [])
        out = {"value": None, "band": "small_segment", "segment": seg, "n_models": len(pop)}
        if seg == "*" or len(pop) < config.MIN_SEGMENT_MODELS:
            return out
        below = sum(1 for v in pop if v < mine - 1e-9)
        level = sum(1 for v in pop if abs(v - mine) <= 1e-9)
        value = int(round(100.0 * (below + 0.5 * level) / len(pop)))
        band = next((b for t, b in config.STANDING_BANDS if value >= t), config.STANDING_BOTTOM_BAND)
        return {**out, "value": value, "band": band}

    def owner_rating_row(self, model: str, aspect: str) -> Optional[pd.Series]:
        df = self.owner_ratings
        if df.empty:
            return None
        g = df[(df["model"] == model) & (df["aspect"] == aspect)]
        return None if g.empty else g.iloc[0]

    def reviewed_models(self, kind: str) -> List[tuple]:
        """(make, model) of every model with at least one row of this kind."""
        if kind == "expert":
            return sorted(set((mk, md) for (mk, md, _a) in self._expert) | set(self._expert_overall)
                          | set(self._overall_all))
        return sorted(set((mk, md) for (mk, md, _t) in self._owner))

    def neutral_class(self, kind: str, segment: str, aspect_w: Optional[Dict[str, float]],
                      relevant: List[str]) -> Optional[tuple]:
        """(neutral sub-score, neutral class scale) for a model with no review rows of this kind: the mean over the
        reviewed models of its segment (all reviewed models when the segment has fewer than MIN_SEGMENT_MODELS) of their
        sub-score and of their class scale, under the same query weights. None when no model is reviewed."""
        key = (kind, segment, None if aspect_w is None else tuple(sorted(aspect_w.items())), tuple(relevant))
        if key in self._neutral_cache:
            return self._neutral_cache[key]
        rows = []
        for make, model in self.reviewed_models(kind):
            sub = self.class_sub(kind, make, model, aspect_w)
            if sub is None:
                continue
            scale = self.expert_scale(make, model, relevant) if kind == "expert" else self.owner_scale(make, model)
            rows.append((self.segments.get(model, "*"), sub, 1.0 if scale is None else scale))
        in_seg = [r for r in rows if r[0] == segment] if segment != "*" else []
        use = in_seg if len(in_seg) >= config.MIN_SEGMENT_MODELS else rows
        out = (sum(r[1] for r in use) / len(use), sum(r[2] for r in use) / len(use)) if use else None
        if len(self._neutral_cache) > 512:
            self._neutral_cache.clear()
        self._neutral_cache[key] = out
        return out

    # -- how much evidence a car has (scales the class weights in score.py) ---------------------------------
    @staticmethod
    def _source_key(row: pd.Series) -> str:
        return (str(row.get("source_name") or "").strip() or str(row.get("source_url") or "").strip() or "anonymous")

    def expert_scale(self, make: str, model: str, relevant_aspects: List[str]) -> Optional[float]:
        """scale in [0, 1] for the expert class weight of one model, or None when it has no expert row.
        (relevant aspects the model has a value for / relevant aspects) x n_sources / (n_sources + EXPERT_SOURCE_K),
        n_sources = distinct sources behind those covered aspects."""
        if list(relevant_aspects) == [config.EXPERT_OVERALL_ASPECT]:   # no preference: the overall row stands for the model
            ov = self._overall_hit_any(make, model)
            if ov is not None:
                n = ov["n_sources"]
                return n / (n + config.EXPERT_SOURCE_K)
            relevant_aspects = [a for a in ASPECTS if self._hit(self._expert, make, model, a)]
        asked = list(relevant_aspects)
        # only aspects the data file has a row for (for any model) can be covered: counting the others in the
        # denominator would cap the scale of even a fully rated car
        relevant_aspects = [a for a in asked if a in self.data_aspects]
        covered = [a for a in relevant_aspects if self._hit(self._expert, make, model, a)]
        if not any(self._hit(self._expert, make, model, a) for a in ASPECTS):
            fb = self._overall_hit(make, model)
            if fb is None:
                return None
            if not asked:
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
        """scale in [0, 1] for the owner class weight, None without owner rows. Owner RATINGS are already pulled
        toward the segment mean by their count (value shrinkage), so they are not discounted again: 1.0. Owner themes
        (owner_themes.csv, no shrinkage) keep count / (count + OWNER_SAMPLE_K)."""
        hits = [h for t in THEMES if (h := self._hit(self._owner, make, model, t))]
        if not hits:
            return None
        if any(h.get("kind") == "rating" for h in hits):
            return 1.0
        return owner_scale_for_count(self.owner_sample(make, model))

    @classmethod
    def load(cls, assessments_path: Any = None, owner_path: Any = None, ratings_path: Any = None,
             segments: Optional[Dict[str, str]] = None) -> "Evidence":
        """Evidence from the data files. `segments` defaults to model -> body type from the catalogue."""
        if segments is None:
            segments = catalogue_segments()
        return cls(_read_assessments(assessments_path or ASSESSMENTS_CSV),
                   _read_themes(owner_path or OWNER_THEMES_CSV),
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
