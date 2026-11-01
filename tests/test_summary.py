"""services/summary.py: every number in every model's summary is a catalogue value of that model's
rows, or a min/max of them, at the precision printed (prices in lakh)."""

import re

import pandas as pd
import pytest

from services.catalogue import NUMERIC_COLUMNS, get_catalogue
from services.new_car_service import TRANSMISSION_LABELS
from services.ranking_adapter import trusted_kmpl
from services.summary import build_summary

CATALOGUE = get_catalogue()
MODELS = sorted(CATALOGUE["model"].unique())
SUBJECTIVE = re.compile(r"\b(best|great|ideal|perfect|premium|excellent|amazing|superb|top-notch)\b", re.I)
NUMBER = re.compile(r"\d[\d,]*(?:\.\d+)?")


def allowed_values(rows: pd.DataFrame) -> list[float]:
    values = []
    for col in NUMERIC_COLUMNS:
        values += [float(v) for v in rows[col].dropna()]
    values += [float(v) / 1e5 for v in rows["price_ex_showroom"].dropna()]  # shown in lakh
    values += [float(len(rows)), float((rows["adas_available"] == True).sum()),  # noqa: E712
               float(rows["adas_available"].isna().sum())]  # variant counts in the ADAS sentence
    return values


@pytest.mark.parametrize("model", MODELS)
def test_summary_numbers_come_from_the_model_rows(model):
    rows = CATALOGUE[CATALOGUE["model"] == model]
    summary = build_summary(rows, TRANSMISSION_LABELS)
    allowed = allowed_values(rows)
    facts = summary.replace(f"{rows.iloc[0]['make']} {model}", "")  # "Alto K10", "XUV 3XO" aren't facts
    for token in NUMBER.findall(facts):
        number = float(token.replace(",", ""))
        digits = len(token.split(".")[1]) if "." in token else 0
        assert any(round(v, digits) == number for v in allowed), (model, token, summary)


@pytest.mark.parametrize("model", MODELS)
def test_summary_shape(model):
    rows = CATALOGUE[CATALOGUE["model"] == model]
    summary = build_summary(rows, TRANSMISSION_LABELS)
    sentences = [s for s in re.split(r"(?<=\.)\s+(?=[A-Z])", summary) if s]
    assert 2 <= len(sentences) <= 4, summary
    assert not SUBJECTIVE.search(summary), summary
    assert "not listed" not in summary.lower() and "nan" not in summary.lower()
    for label in TRANSMISSION_LABELS.values():  # transmissions use the exact labels
        if label in summary:
            assert any(TRANSMISSION_LABELS[t] == label for t in rows["transmission_type"])


def test_mileage_units_are_kept_apart():
    for model in MODELS:
        rows = CATALOGUE[CATALOGUE["model"] == model]
        summary = build_summary(rows, TRANSMISSION_LABELS)
        kmpl = [trusted_kmpl(r) for _, r in rows.iterrows()]
        if all(pd.isna(v) for v in kmpl):
            assert "kmpl" not in summary, (model, summary)
        if rows["mileage_km_per_kg"].isna().all():
            assert "km/kg" not in summary, (model, summary)
        if rows["ev_range_km"].isna().all():
            assert "range" not in summary.lower(), (model, summary)


def test_rated_models_mention_bharat_ncap():
    for model in MODELS:
        rows = CATALOGUE[CATALOGUE["model"] == model]
        rated = rows["safety_stars_adult"].notna().any()
        assert ("Bharat NCAP" in build_summary(rows, TRANSMISSION_LABELS)) == rated, model
