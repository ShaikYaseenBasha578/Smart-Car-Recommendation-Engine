"""Small shared helpers: unknown-value handling, percentile ranks, JSON-safe conversion."""

from __future__ import annotations

import math
from typing import Any, Iterable, List, Optional

import numpy as np


def is_unknown(value: Any) -> bool:
    """True for None / NaN / pandas NA. A blank is unknown, never 0 and never False."""
    if value is None:
        return True
    try:
        if isinstance(value, (float, np.floating)) and math.isnan(value):
            return True
    except TypeError:
        pass
    try:
        import pandas as pd
        return bool(pd.isna(value)) if not isinstance(value, (list, tuple, set, frozenset, dict, np.ndarray)) else False
    except Exception:
        return False


def num(value: Any) -> Optional[float]:
    """float or None (unknown)."""
    if is_unknown(value) or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def pct_rank(value: float, group: Iterable[float]) -> float:
    """Mid-rank percentile of `value` among the known `group` values, in [0, 1].

    (number below + half the number equal) / n. Ties share the middle, so a group of identical
    values (or a single member) scores 0.5. Why percentile: robust to outliers and units, and
    needs no hand-set point values."""
    vals: List[float] = [v for v in group if v is not None]
    if not vals:
        return 0.5
    below = sum(1 for v in vals if v < value)
    equal = sum(1 for v in vals if v == value)
    return (below + 0.5 * equal) / len(vals)


def to_jsonable(value: Any) -> Any:
    """Recursively convert numpy / pandas / sets / NaN into plain JSON values (NaN -> None)."""
    if isinstance(value, dict):
        return {str(k): to_jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [to_jsonable(v) for v in value]
    if isinstance(value, (set, frozenset)):
        return sorted(to_jsonable(v) for v in value)
    if isinstance(value, np.ndarray):
        return [to_jsonable(v) for v in value.tolist()]
    if isinstance(value, (bool, np.bool_)):
        return bool(value)
    if isinstance(value, (int, np.integer)):
        return int(value)
    if isinstance(value, (float, np.floating)):
        f = float(value)
        return None if math.isnan(f) or math.isinf(f) else f
    if value is None or isinstance(value, str):
        return value
    if is_unknown(value):
        return None
    return str(value)
