"""Template summary of one model, built only from its catalogue rows (no LLM, no opinions).

2-4 sentences: body/seats + price range; engines (fuel, cc, bhp) + exact transmission labels;
mileage in its own units (kmpl / km/kg / EV range km) + boot space; Bharat NCAP + ADAS count.
Unknown facts are left out (never "Not listed"). Every number printed is a catalogue value of
the model's rows or a min/max of them, shown at a fixed precision (tests/test_summary.py).
"""

from __future__ import annotations

import math

import pandas as pd

from services.ranking_adapter import trusted_kmpl

TRANSMISSION_ORDER = ["manual", "imt", "amt", "dct", "cvt", "e_cvt", "torque_converter", "single_speed_ev"]
FUEL_ORDER = ["petrol", "diesel", "cng", "hybrid", "electric"]
FUEL_WORDS = {"petrol": "petrol", "diesel": "diesel", "cng": "CNG", "hybrid": "petrol-hybrid", "electric": "electric"}
BODY_WORDS = {"suv": "SUV", "hatchback": "hatchback", "sedan": "sedan", "mpv": "MPV", "van": "van", "pickup": "pickup"}


def _values(series) -> list[float]:
    return sorted(v for v in series if v is not None and not (isinstance(v, float) and math.isnan(v)))


def _num(value: float, digits: int) -> str:
    return f"{value:.{digits}f}" if digits else str(int(round(value)))


def _span(values: list[float], digits: int = 0, joiner: str = "–") -> str:
    lo, hi = _num(values[0], digits), _num(values[-1], digits)
    return lo if lo == hi else f"{lo}{joiner}{hi}"


def _lakh(rupees: float) -> str:
    return f"₹{rupees / 1e5:.2f}".rstrip("0").rstrip(".") + " lakh"


def _join(words: list[str]) -> str:
    return words[0] if len(words) == 1 else ", ".join(words[:-1]) + " and " + words[-1]


def _article(word: str) -> str:
    return "an" if word[0].lower() in "aeiou" or word.startswith(("SUV", "MPV")) else "a"


def build_summary(rows: pd.DataFrame, transmission_labels: dict[str, str]) -> str:
    first = rows.iloc[0]
    name = f"{first['make']} {first['model']}"
    n = len(rows)
    sentences = []

    # 1. body, seats, price range
    seats = _values(rows["seats"])
    body = BODY_WORDS.get(first["body_type"], first["body_type"])
    prices = _values(rows["price_ex_showroom"])
    seat_text = f"{_span(seats)}-seat " if seats else ""
    lead = f"{name} is {_article(seat_text or body)} {seat_text}{body}"
    if prices:
        price_text = _lakh(prices[0]) if prices[0] == prices[-1] else f"{_lakh(prices[0])} to {_lakh(prices[-1])}"
        lead += f" priced at {price_text} (ex-showroom)" if prices[0] == prices[-1] else f" priced from {price_text} (ex-showroom)"
    lead += f" across {n} variant{'s' if n != 1 else ''}."
    sentences.append(lead)

    # 2. engines and transmissions
    fuels = [f for f in FUEL_ORDER if f in set(rows["fuel_type"])]
    parts = []
    cc = _values(rows.loc[rows["fuel_type"] != "electric", "engine_cc"])
    bhp = _values(rows["power_bhp"])
    fuel_words = _join([FUEL_WORDS[f] for f in fuels])
    if fuels == ["electric"]:
        engine = "It is electric"
    else:
        engine = f"It has {fuel_words} power"
        if cc:
            engine += f" from a {_span(cc)} cc engine" if cc[0] == cc[-1] else f" from {_span(cc)} cc engines"
    if bhp:
        engine += f", making {_span(bhp)} bhp"
    trans = [transmission_labels[t] for t in TRANSMISSION_ORDER if t in set(rows["transmission_type"])]
    if trans:
        engine += f", with {_join(trans)} transmission{'s' if len(trans) > 1 else ''}"
    parts.append(engine + ".")
    sentences.extend(parts)

    # 3. efficiency (own units) and boot space
    kmpl = _values([trusted_kmpl(r) for _, r in rows.iterrows()])
    kmkg = _values(rows["mileage_km_per_kg"])
    rng = _values(rows["ev_range_km"])
    boot = _values(rows["boot_space_litres"])
    mileage = [f"{_span(kmpl, 1)} kmpl"] if kmpl else []
    if kmkg:
        mileage.append(f"{_span(kmkg, 1)} km/kg on CNG")
    clauses = [f"ARAI mileage is {' and '.join(mileage)}"] if mileage else []
    if rng:
        clauses.append(f"claimed range is {_span(rng)} km")
    if boot:
        clauses.append(f"boot space is {_span(boot)} litres")
    if clauses:
        text = "; ".join(clauses) + "."
        sentences.append(text[0].upper() + text[1:])

    # 4. safety rating and ADAS availability
    safety = []
    stars = _values(rows["safety_stars_adult"])
    if stars:
        year = _values(rows["safety_test_year"])
        safety.append(f"It has a {_num(stars[-1], 0)}-star Bharat NCAP adult rating"
                      + (f" ({_num(year[-1], 0)})" if year else ""))
    adas = rows["adas_available"]
    yes, unknown = int((adas == True).sum()), int(adas.isna().sum())  # noqa: E712 (object column)
    if yes:
        adas_text = f"ADAS is fitted on {yes} of {n} variants" if yes < n else "every variant has ADAS"
        if unknown:
            adas_text += f" ({unknown} unconfirmed)"
        safety.append(adas_text)
    elif not unknown:
        safety.append("no variant has ADAS")
    if safety:
        text = safety[0] if len(safety) == 1 else f"{safety[0]}, and {safety[1]}"
        sentences.append(text[0].upper() + text[1:] + ".")

    return " ".join(sentences[:4])
