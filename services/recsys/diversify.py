"""One variant per model, then MMR across models (plan section 7).

1. best_variant_per_model: for each (make, model) the best-scoring variant that passed the filter
   (ties: lower price, then lower variant_id), not the lowest id.
2. mmr_select: Maximal Marginal Relevance over the models. relevance = overall score min-max scaled to
   [0, 1] across the models; similarity(a, b) = SIM_WEIGHTS . (same make, same body type,
   1 - min(1, |ln(price_a / price_b)| / ln 2)), so cars twice the price apart are fully dissimilar.
   pick argmax  lambda x relevance - (1 - lambda) x max similarity to the already picked.
   Skipped (pure score order) when the user named a make or model.
3. Display order: MMR only decides WHICH models are shown. The chosen rows are returned sorted by overall
   score, descending (ties: lower variant_id), so a weaker match never appears above a stronger one. Each row
   carries `selection_order` (1 = picked first by MMR).
4. twins (services.twins): when both models of a confirmed twin pair are picked the limit grows by one.
   Behind use_twins, default on. Max MAX_MODELS models otherwise.
"""

from __future__ import annotations

import math
from typing import Any, List, Optional

import pandas as pd

from services.recsys import config
from services.twins import complete_twin_pairs


def best_variant_per_model(scored: pd.DataFrame) -> pd.DataFrame:
    """`scored` has overall (+ make, model, price_ex_showroom, variant_id). One best row per model."""
    df = scored.assign(_o=scored["overall"].astype(float).fillna(-1.0))
    df = df.sort_values(["_o", "price_ex_showroom", "variant_id"], ascending=[False, True, True])
    best = df.drop_duplicates(subset=["make", "model"], keep="first")
    return best.drop(columns="_o").sort_values(["overall", "variant_id"], ascending=[False, True])


def similarity(a: pd.Series, b: pd.Series) -> float:
    w = config.SIM_WEIGHTS
    same_make = 1.0 if a["make"] == b["make"] else 0.0
    same_body = 1.0 if a["body_type"] == b["body_type"] else 0.0
    pa, pb = a["price_ex_showroom"], b["price_ex_showroom"]
    if pd.isna(pa) or pd.isna(pb) or pa <= 0 or pb <= 0:
        price_sim = 0.0
    else:
        price_sim = 1.0 - min(1.0, abs(math.log(pa / pb)) / config.PRICE_DISTANCE_CAP_LOG)
    return w["make"] * same_make + w["body"] * same_body + w["price"] * price_sim


def _limit(selected: List[pd.Series], max_models: int, use_twins: bool) -> int:
    if not use_twins:
        return max_models
    return max_models + complete_twin_pairs([(c["make"], c["model"]) for c in selected])


def mmr_select(models: pd.DataFrame, max_models: int = config.MAX_MODELS, lam: float = config.MMR_LAMBDA,
               use_twins: bool = config.USE_TWINS) -> List[pd.Series]:
    """MMR over one-row-per-model frame (sorted by score). Deterministic."""
    rows = [r for _, r in models.iterrows()]
    if not rows:
        return []
    scores = [float(r["overall"]) if not pd.isna(r["overall"]) else 0.0 for r in rows]
    lo, hi = min(scores), max(scores)
    rel = [(s - lo) / (hi - lo) if hi > lo else 1.0 for s in scores]
    remaining = list(range(len(rows)))
    picked: List[int] = []
    while remaining and len(picked) < _limit([rows[i] for i in picked], max_models, use_twins):
        def mmr(i: int) -> float:
            sim = max((similarity(rows[i], rows[j]) for j in picked), default=0.0)
            return lam * rel[i] - (1 - lam) * sim
        best = max(remaining, key=lambda i: (round(mmr(i), 12), -i))  # ties: earlier (better-scoring) row
        picked.append(best)
        remaining.remove(best)
    return [rows[i] for i in picked]


def score_order_select(models: pd.DataFrame, max_models: int = config.MAX_MODELS,
                       use_twins: bool = config.USE_TWINS) -> List[pd.Series]:
    selected: List[pd.Series] = []
    for _, r in models.iterrows():
        if len(selected) >= _limit(selected, max_models, use_twins):
            break
        selected.append(r)
    return selected


def named_make_or_model(intent: Any) -> bool:
    get = intent.get if isinstance(intent, dict) else (lambda k, d=None: getattr(intent, k, d))
    return bool(get("makes", None) or get("models", None))


def diversify(scored: pd.DataFrame, intent: Any, max_models: int = config.MAX_MODELS, lam: float = config.MMR_LAMBDA,
              use_twins: bool = config.USE_TWINS) -> List[pd.Series]:
    """`scored`: candidate rows joined with the score table (column `overall`).
    Returns the chosen rows sorted by overall score descending, each with `selection_order` set."""
    if scored.empty:
        return []
    models = best_variant_per_model(scored)
    if named_make_or_model(intent):
        picked = score_order_select(models, max_models, use_twins)
    else:
        picked = mmr_select(models, max_models, lam, use_twins)
    out = []
    for i, row in enumerate(picked, start=1):
        row = row.copy()
        row["selection_order"] = i
        out.append(row)
    return sorted(out, key=lambda r: (-(float(r["overall"]) if not pd.isna(r["overall"]) else -1.0), r["variant_id"]))
