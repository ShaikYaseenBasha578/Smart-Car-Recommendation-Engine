"""Intent schema v2: turn a free-text car query into structured constraints.

A deterministic rule layer runs first and is the only source of HARD constraints (filters), including
negated ones: excluded fuels, bodies, makes and features, and upper bounds on numeric fields.

The existing ML parser (ml_parser/ml_intent_parser.py) only runs when the rules saw no mention (positive
or negated) of body type, fuel or use case, and only a confident (>= ML_MIN_CONFIDENCE), non-"unknown"
label counts. Its body/fuel guesses never filter: they go into out["assumed"] (soft preferences that the
response returns so the UI can show "assumed: SUV"). Its use_case guess fills use_case as before (a
ranking hint, never a filter). The ML models see the query with already-parsed feature/number/budget
phrases blanked out.

out["vague"] is True when the rules found no usable constraint or preference at all; out["unsupported_only"]
is True when the only content is a brand the catalogue does not carry. Both are judged before the ML
fallback, so an ML guess cannot make a vague query look specific.

Used by services/new_car_service.py (the KB path of /predict). Vocabularies match data/catalogue.csv.
"""

from __future__ import annotations

import csv
import re
from pathlib import Path

from services.typos import correct_typos

from services.catalogue import CATALOGUE_CSV  # same file as the engine (CARREC_CATALOGUE_DIR honoured)

BODY_TYPES = ["suv", "hatchback", "sedan", "mpv", "van", "pickup"]
FUEL_TYPES = ["petrol", "diesel", "cng", "electric", "hybrid"]
TRANSMISSION_TYPES = ["manual", "imt", "amt", "dct", "cvt", "e_cvt", "torque_converter", "single_speed_ev"]
AUTOMATIC_TYPES = {"amt", "dct", "cvt", "e_cvt", "torque_converter", "single_speed_ev"}
FEATURES = [
    "sunroof", "adas", "camera_360", "ventilated_seats", "cruise_control",
    "wireless_charging", "heads_up_display", "android_auto", "apple_carplay",
]

SOFT_PREFERENCES = ["mileage", "space", "performance", "comfort", "safety", "features"]

AROUND_BAND = 0.15  # "around 10 lakh" -> 8.5 to 11.5 lakh
ML_MIN_CONFIDENCE = 0.5

# ---------------------------------------------------------------------------
# Vocab: phrase regexes (matched on lowercased text, whole words)
# ---------------------------------------------------------------------------

FEATURE_PATTERNS = [
    ("android_auto", r"(?:wireless\s+)?android\s*auto"),
    ("apple_carplay", r"(?:wireless\s+)?(?:apple\s*)?car\s*play"),
    ("camera_360", r"360(?:\s*-?\s*(?:degree|deg|°))?\s*(?:view\s*)?(?:camera|cam)|surround\s*view(?:\s*camera)?"),
    ("adas", r"adas|level\s*-?\s*2(?:\s*adas)?|l2\s*adas|lane\s*(?:keep(?:ing)?\s*)?assist|lane\s*departure(?:\s*warning)?"
             r"|autonomous\s*emergency\s*braking"),
    ("adaptive_cruise", r"adaptive\s*cruise(?:\s*control)?"),
    ("sunroof", r"(?:panoramic|electric|single[- ]pane)?\s*(?:sun\s*roof|moon\s*roof)|panoramic(?:\s*(?:glass\s*)?roof)?"),
    ("ventilated_seats", r"(?:ventilated|cooled|cooling)\s*(?:front\s*)?seats?|seat\s*ventilation|ventilated"),
    ("cruise_control", r"cruise(?:\s*control)?"),
    ("wireless_charging", r"wireless\s*(?:phone\s*)?charg(?:er|ing)"),
    ("heads_up_display", r"hud|heads?[- ]?up(?:\s*display)?"),
]

FUEL_PATTERNS = [
    ("hybrid", r"(?:strong\s*|self[- ]charging\s*)?hybrids?"),
    ("electric", r"electric(?!\s*(?:sunroof|seats?|adjustable|mirrors?|orvms?|parking\s*brake))|e\.?v\.?s?|bev|battery\s*(?:car|gaadi)"),
    ("petrol", r"petrol|gasoline"),
    ("diesel", r"diesel"),
    ("cng", r"cng"),
]

BODY_PATTERNS = [
    ("suv", r"(?:compact\s*|mid[- ]size\s*|micro\s*)?suvs?"),
    ("hatchback", r"hatch(?:back)?s?"),
    ("sedan", r"sedans?"),
    ("mpv", r"mpvs?|muvs?|people\s*mover|minivan"),
    ("van", r"vans?"),
    ("pickup", r"pick-?ups?(?:\s*truck)?|pick\s+up\s+truck"),
]

MAKE_PATTERNS = [
    ("Maruti Suzuki", r"maruti(?:\s*suzuki)?|suzuki"),
    ("MG", r"mg|morris\s*garages?"),
    ("Volkswagen", r"volkswagen|vw"),
    ("Honda", r"honda"),
    ("Hyundai", r"hyundai"),
    ("Kia", r"kia"),
    ("Mahindra", r"mahindra"),
    ("Nissan", r"nissan"),
    ("Renault", r"renault"),
    ("Skoda", r"skoda"),
    ("Tata", r"tata"),
    ("Toyota", r"toyota"),
]

# Brands that are not in the catalogue: reported back, never used as a filter.
UNSUPPORTED_BRAND_PATTERNS = [
    ("BMW", r"bmw"),
    ("Audi", r"audi"),
    ("Mercedes-Benz", r"mercedes(?:[- ]benz)?|merc|benz"),
    ("Volvo", r"volvo"),
    ("Jeep", r"jeep"),
    ("Ford", r"ford"),
    ("Citroen", r"citro[eë]n"),
    ("BYD", r"byd"),
    ("Lexus", r"lexus"),
    ("Porsche", r"porsche"),
    ("Land Rover", r"land\s*rover|range\s*rover"),
    ("Jaguar", r"jaguar"),
    ("Mini", r"mini(?=\s*(?:cooper|countryman|clubman|brand))"),
    ("Isuzu", r"isuzu"),
    ("Force", r"force(?=\s*(?:motors|gurkha|traveller|trax|urbania))"),
    ("Fiat", r"fiat"),
    ("Chevrolet", r"chevrolet|chevy"),
    ("Datsun", r"datsun"),
]

# Vague wishes -> soft preferences (ranking boosts only, never filters).
SOFT_PREFERENCE_PATTERNS = [
    ("mileage", r"(?:good|great|better|best|high|excellent|achha|acha|achhi|achi)\s*(?:mileage|average|fuel\s*economy)"
                r"|mileage\s*(?:achha|acha|achhi|achi|good|wali|wala)|fuel[- ]efficient|fuel\s*economy|economical|kifayati"),
    ("space", r"spacious|roomy|big\s*family|large\s*family|joint\s*family|lots\s*of\s*space|big\s*boot|more\s*space"
              r"|space\s*wali|badi\s*gaadi"),
    ("performance", r"powerful|fun\s*to\s*drive|sporty|performance|fast|quick|peppy|punchy|torquey|zippy"),
    ("comfort", r"comfortable|comfort|smooth\s*ride|plush|comfy|aaramdayak"),
    ("safety", r"safe|safer|safest|safety|secure"),
    ("features", r"(?:fully\s*)?loaded|feature[- ]?(?:rich|packed|loaded)|lots\s*of\s*features|top[- ]end|tech[- ]?(?:savvy|loaded)"),
]

# A model after one of these is a reference point ("something like Creta"), not a hard filter.
REFERENCE_BEFORE = r"(?:like|similar\s*to|alternatives?\s*(?:to|for)|rivals?\s*(?:of|to)|competitors?\s*(?:of|to)" \
                   r"|instead\s*of)\s*(?:a|an|the)?\s*$"
REFERENCE_AFTER = r"^\s*(?:jaisi|jaisa|jaise|type|like|alternative|alternatives|rival|rivals)(?![a-z])"
# Common words that are also model names: only a model when the make comes right before ("honda city").
AMBIGUOUS_MODELS = {"City", "Venue", "Aura", "Elevate"}
MODEL_ALIASES = {
    "innova": ["Innova Crysta", "Innova Hycross"],
    "scorpio": ["Scorpio Classic", "Scorpio-N"],
    "carens": ["Carens Clavis", "Carens Clavis EV"],
    "clavis": ["Carens Clavis", "Carens Clavis EV"],
    "vitara": ["Grand Vitara", "e VITARA"],
    "hyryder": ["Urban Cruiser Hyryder"],
    "taisor": ["Urban Cruiser Taisor"],
    "grand i10": ["Grand i10 Nios"],
    "i10 nios": ["Grand i10 Nios"],
    "nios": ["Grand i10 Nios"],
    "alto": ["Alto K10"],
    "wagon r": ["WagonR"],
    "crysta": ["Innova Crysta"],
    "hycross": ["Innova Hycross"],
}

# Price-priority wording ("cheapest", "value for money", "paisa vasool", "sabse sasti", "kifayati" and close
# variants). The ONE list: it sets intent["cheap_intent"] (price gets a large weight in the recommender) and is also
# the "budget" use case below. A bare "budget" counts only as an adjective ("budget car", "budget friendly"), never
# as the budget cue of "budget 12 lakh" / "my budget is".
CHEAP_INTENT_PATTERN = (
    r"cheap(?:est|er|ish|ly)?|inexpensive|low[- ]?(?:cost|price[ds]?)|affordable|economy\s*car|pocket[- ]friendly"
    r"|wallet[- ]friendly|value[- ]?(?:for|4)[- ]?(?:money|mony|moneys)|vfm|paisa[- ]?vasool|paise[- ]?vasool"
    r"|sast(?:i|a|e|ha|hi)|sabse\s*sast(?:i|a|e)|kam\s*(?:daam|dam|keemat|kimat|price)(?:\s*(?:ki|ka|wali|wala))?"
    r"|kifayati|kifayat|budget[- ]?(?:friendly|car|cars|suv|suvs|hatchback|sedan|option|options|segment|wali|wala|gaadi|vehicle)"
    r"|(?:lowest|least|minimum)\s*(?:price|priced|cost)"
)

# First match wins; same label set as the ML use_case model (minus "general").
USE_CASE_PATTERNS = [
    ("premium", r"luxury|luxurious|premium"),
    ("parents", r"parents|elderly|seniors?|senior\s*citizens?|papa|mummy|mom\s*and\s*dad"),
    ("family", r"family|families|parivar|ghar\s*wal(?:e|on)"),
    ("highway", r"highway|long\s*drives?|road\s*trips?|touring|outstation"),
    ("student", r"students?|college|first\s*car"),
    ("budget", CHEAP_INTENT_PATTERN),
    ("commute", r"commute|commuting|office|daily\s*(?:use|drive|driving)"),
    ("city", r"city|traffic|shehar"),
    ("enthusiast", r"enthusiast|performance|sporty|fun\s*to\s*drive|driving\s*pleasure"),
]

# Transmission tokens -> (family, types). Short ambiguous tokens are handled separately.
TRANSMISSION_PATTERNS = [
    ("imt", r"imt|clutch\s*-?less|without\s*(?:a\s*)?clutch|bina\s*clutch"),
    ("amt", r"amt|ags|auto\s*gear\s*shift"),
    ("dct", r"dct|dsg|dual[- ]?clutch"),
    ("e_cvt", r"e-?cvt"),
    ("cvt", r"cvt|ivt"),
    ("torque_converter", r"torque\s*converter"),
    ("automatic", r"automatics?|autobox|gearless|auto(?!\s*(?:climate|ac\b|headlamps?|headlights?|wipers?|hold|rickshaw|"
                  r"dimming|fold|expo|mode))"),
    ("manual", r"manuals?|stick(?:\s*shift)?|gear\s*wali"),
]
TRANSMISSION_TYPES_FOR = {
    "imt": ["imt"], "amt": ["amt"], "dct": ["dct"], "cvt": ["cvt", "e_cvt"], "e_cvt": ["e_cvt"],
    "torque_converter": ["torque_converter"], "automatic": [], "manual": [],
}
# AT / MT / TC are only transmission words next to a context word ("AT car", "petrol AT", "in AT").
SHORT_TRANSMISSION = {"at": "automatic", "mt": "manual", "tc": "torque_converter"}
SHORT_CONTEXT_AFTER = {"car", "cars", "variant", "variants", "version", "versions", "gearbox", "transmission",
                       "model", "models", "only", "option", "chahiye", "wali", "wala", "hatchback", "sedan", "suv",
                       "automatic", "auto", "diesel", "petrol", "please"}
SHORT_CONTEXT_BEFORE = {"in", "an", "only", "prefer", "petrol", "diesel", "cng", "turbo", "want", "need", "get",
                        "with", "or", "and", "automatic", "manual"}
SHORT_STOP_AFTER = {"the", "a", "an", "my", "home", "night", "least", "most", "all", "once", "work", "office",
                    "first", "last", "any", "that", "this", "times", "max", "best", "par"}

NEGATION_BEFORE = {"no", "not", "avoid", "without", "except", "excluding", "dont", "don't", "never", "nor",
                   "hate", "na", "bina"}
NEGATION_FILLER = {"a", "an", "the", "want", "wanna", "need", "like", "any", "prefer", "please", "really", "to",
                   "have", "do", "i", "an", "using", "with",
                   # coordination: "avoid diesel and CNG" negates both (earlier terms are already blanked)
                   "and", "or", "nor", "ya", "aur", "&", "/"}
NEGATION_AFTER = {"nahi", "nahin", "nhi", "mat", "not", "na"}
ENGLISH_NOT_AFTER = {"not", "na"}
POSTFIX_NOT_TAIL = {"wanted", "needed", "required", "preferred", "desired", "please", "at", "all", "chahiye", "chaiye"}
CLAUSE_BREAK = re.compile(r"[,.;!?]|\bbut\b|\bhowever\b|\bwhile\b|\blekin\b|\bpar\b")

WORD = r"(?<![a-z0-9])(?:{})(?![a-z0-9])"


def _find(pattern: str, text: str):
    return list(re.finditer(WORD.format(pattern), text))


def _mask(text: str, match: re.Match) -> str:
    return text[:match.start()] + " " * (match.end() - match.start()) + text[match.end():]


def _is_negated(text: str, start: int, end: int) -> bool:
    before = CLAUSE_BREAK.split(text[:start])[-1].split()
    # negation word, then only fillers, then the term: "no AMT", "do not want an AMT"
    for i in range(len(before) - 1, max(len(before) - 5, -1), -1):
        word = before[i].strip("'\"")
        if word in NEGATION_BEFORE:
            return True
        if word not in NEGATION_FILLER:
            break
    # "AMT nahi", "diesel nahi chahiye", "AMT wali nahi"
    after = CLAUSE_BREAK.split(text[end:])[0].split()[:3]
    for i, word in enumerate(after):
        if word in NEGATION_AFTER:
            # English "not"/"na" after a term only negates it as "diesel not wanted"; "hybrid not Toyota" is a new negation
            if word in ENGLISH_NOT_AFTER and not set(after[i + 1:]) <= POSTFIX_NOT_TAIL:
                break
            return True
        if word not in {"chahiye", "chaiye", "wali", "wala", "hona", "chalega", "please"}:
            break
    return False


# ---------------------------------------------------------------------------
# Numbers
# ---------------------------------------------------------------------------

NUM = r"\d+(?:,\d+)*(?:\.\d+)?"
UNIT = r"lakhs?|lacs?|lac|lkh|l|k|thousand|crores?|cr"
AMOUNT = rf"(?:rs\.?\s*|inr\s*)?({NUM})\s*({UNIT})?"
UNIT_MULTIPLIER = {"l": 100_000, "k": 1_000, "thousand": 1_000, "cr": 10_000_000}


def _rupees(number: str, unit: str | None, cue: bool) -> int | None:
    value = float(number.replace(",", ""))
    if unit:
        key = "cr" if unit.startswith("cr") else "thousand" if unit == "thousand" else unit[0]
        return round(value * UNIT_MULTIPLIER[key])
    if value >= 10_000:
        return round(value)  # already rupees: "rs 750000", "7,50,000"
    if cue:
        return round(value * 100_000)  # bare number after a budget cue defaults to lakh
    return None


# a number that is followed by a currency word is a price, never a clearance / boot figure ("clearance under 8 lakh")
NOT_MONEY = r"(?!\d|\.\d|\s*(?:lakhs?|lacs?|lkh|crores?|cr|thousand)(?![a-z]))"
# a bare number followed by one of these is a measurement, never a budget ("about 40 km", "minimum 200 mm")
MEASURE_AFTER = re.compile(r"\s*(?:mm|cm|kms?|kmpl|kpl|kg|ltrs?|litres?|liters?|seats?|seaters?|airbags?|stars?|bhp|ps|hp|cc|nm"
                           r"|people|persons|years?|yrs?|months?|days?|hours?|hrs?|minutes?)(?![a-z])")

UPPER_PREFIX = r"(?:under|below|less\s*than|at\s*most|no\s*more\s*than|not\s*more\s*than|max(?:imum)?|upto|up\s*to)"
# (intent field, patterns with ONE number group each). Mileage upper bounds are handled with the mileage code below.
UPPER_BOUND_SPECS = [
    ("max_ev_range_km", [rf"(?:ev\s*)?range\s*(?:of\s*)?{UPPER_PREFIX}\s*({NUM})\s*km",
                         rf"{UPPER_PREFIX}\s*({NUM})\s*km\s*(?:of\s*)?(?:real\s*|claimed\s*|battery\s*)?range"]),
    ("max_ground_clearance_mm", [rf"(?:ground\s*)?clearance\s*(?:of\s*)?{UPPER_PREFIX}\s*({NUM}){NOT_MONEY}\s*(?:mm)?",
                                 rf"{UPPER_PREFIX}\s*({NUM})\s*mm\s*(?:of\s*)?(?:ground\s*)?clearance"]),
    ("max_boot_space_litres", [rf"(?:boot|luggage|trunk|dickey|dikki)\s*(?:space\s*)?(?:of\s*)?{UPPER_PREFIX}\s*({NUM}){NOT_MONEY}\s*(?:l|litres?|liters?|ltrs?)?",
                               rf"{UPPER_PREFIX}\s*({NUM})\s*(?:l|litres?|liters?|ltrs?)\s*(?:of\s*)?(?:boot|luggage|trunk)",
                               rf"(?:boot|luggage|trunk|dickey|dikki)\s*(?:space\s*)?({NUM})\s*(?:l|litres?|liters?|ltrs?)\s*(?:se\s*kam|ke\s*neeche)",
                               rf"({NUM})\s*(?:l|litres?|liters?|ltrs?)\s*(?:se\s*kam|ke\s*neeche)\s*(?:ka\s*|wala\s*|wali\s*|ki\s*)?(?:boot|luggage|trunk|dickey|dikki)"]),
]


def _parse_numeric_specs(text: str, out: dict, trace: list) -> str:
    specs = [
        ("seats_min", int, r"(\d+)\s*-?\s*(?:seater|seats?|seat)|(?:seating\s*(?:for|capacity\s*(?:of)?)|family\s*of)\s*(\d+)"
                           r"|(\d+)\s*(?:people|persons|log|logon|members)"
                           # verb form: "that seats 6", "seats at least 7" (not "seats 5 lakh")
                           r"|seats?\s*(?:at\s*least\s*|minimum\s*|min\s*)?(\d+)(?!\s*(?:lakhs?|lacs?|lac|l|k|cr|crores?|%)(?![a-z]))"),
        ("min_airbags", int, r"(\d+)\s*-?\s*air\s*-?bags?"),
        ("min_safety_stars", int, r"([1-5])\s*-?\s*(?:stars?|\*)(?:\s*(?:safety|rated|rating|ncap))*"
                                  r"|(?:ncap|safety)\s*rating\s*(?:of\s*)?([1-5])"),
        ("min_ev_range_km", int, r"(\d+)\s*\+?\s*km\s*(?:of\s*)?(?:real\s*|claimed\s*|battery\s*)?range"
                                 r"|range\s*(?:of\s*)?(?:at\s*least\s*|above\s*|over\s*)?(\d+)\s*\+?\s*km"),
        ("min_ground_clearance_mm", int, r"(\d+)\s*\+?\s*mm\s*(?:of\s*)?(?:ground\s*)?clearance|(\d+)\s*mm\s*gc"
                                         rf"|(?:ground\s*)?clearance\s*(?:of\s*)?(?:at\s*least\s*|above\s*|over\s*|min(?:imum)?\s*)?(\d+){NOT_MONEY}\s*(?:mm)?"),
        ("min_boot_space_litres", int, r"(\d+)\s*\+?\s*(?:l|litres?|liters?|ltrs?)\s*(?:se\s*(?:zyada|jyada|zyaada|upar|oopar)\s*(?:ka\s*|wala\s*|wali\s*|ki\s*)?)?"
                                       r"(?:of\s*)?(?:boot|luggage|trunk|dickey|dikki)"
                                       r"|(?:boot|luggage|trunk|dickey|dikki)\s*(?:space\s*)?(?:of\s*)?(?:at\s*least\s*|above\s*|over\s*|more\s*than\s*|greater\s*than\s*|min(?:imum)?\s*)?"
                                       rf"(\d+){NOT_MONEY}\s*(?:l|litres?|liters?|ltrs?)?(?:\s*se\s*(?:zyada|jyada|zyaada|upar|oopar))?"),
    ]
    # upper bounds first, so the lower-bound patterns below can't read "under 190 mm ground clearance" as a minimum
    for field, patterns in UPPER_BOUND_SPECS:
        for m in _find("|".join(patterns), text):
            value = float(next(g for g in m.groups() if g))
            if out[field] is None:
                out[field] = value
                trace.append(f"{field}={value:g} <- rule '{m.group(0).strip()}'")
            text = _mask(text, m)

    for field, cast, pattern in specs:
        for m in _find(pattern, text):
            value = cast(next(g for g in m.groups() if g))
            if out[field] is None:
                out[field] = value
                trace.append(f"{field}={value} <- rule '{m.group(0).strip()}'")
            text = _mask(text, m)

    # mileage ranges and upper bounds ("18 to 22 kmpl", "under 30 km/kg"), CNG (km/kg) and petrol/diesel (kmpl)
    # kept apart: a km/kg threshold is never compared with kmpl
    kmkg = r"(?:km\s*/\s*kg|km\s*per\s*kg|kmpkg|km\s*kg)"
    kmpl = r"(?:kmpl|km\s*/\s*l|kpl|km\s*per\s*lit(?:re|er))"
    for unit_re, lo_key, hi_key in ((kmkg, "min_mileage_km_per_kg", "max_mileage_km_per_kg"),
                                    (kmpl, "min_mileage_kmpl", "max_mileage_kmpl")):
        for m in _find(rf"(?:between\s*)?({NUM})\s*(?:to|-|and)\s*({NUM})\s*{unit_re}", text):
            lo, hi = float(m.group(1)), float(m.group(2))
            if lo < hi and out[lo_key] is None and out[hi_key] is None:
                out[lo_key], out[hi_key] = lo, hi
                trace.append(f"{lo_key}={lo:g} {hi_key}={hi:g} <- rule '{m.group(0).strip()}'")
            text = _mask(text, m)
        for m in _find(rf"(?:mileage\s*(?:of\s*)?)?{UPPER_PREFIX}\s*({NUM})\s*{unit_re}", text):
            if out[hi_key] is None:
                out[hi_key] = float(m.group(1))
                trace.append(f"{hi_key}={out[hi_key]:g} <- rule '{m.group(0).strip()}'")
            text = _mask(text, m)

    # CNG mileage lower bound: "25 km/kg", "25 km per kg", "above 25 km/kg"
    for m in _find(rf"(?:(?:above|over|at\s*least|more\s*than|min(?:imum)?)\s*)?(?:mileage\s*(?:of\s*)?)?({NUM})\s*\+?\s*{kmkg}", text):
        if out["min_mileage_km_per_kg"] is None:
            out["min_mileage_km_per_kg"] = float(m.group(1))
            trace.append(f"min_mileage_km_per_kg={out['min_mileage_km_per_kg']} <- rule '{m.group(0).strip()}'")
        text = _mask(text, m)

    # mileage lower bound: "20+ kmpl", "above 18 kmpl", "mileage above 20"
    for m in _find(rf"(?:(?:above|over|at\s*least|more\s*than|min(?:imum)?)\s*)?({NUM})\s*\+?\s*{kmpl}"
                   rf"|mileage\s*(?:of\s*)?(?:above|over|at\s*least|more\s*than)?\s*({NUM})\s*\+?\s*(?:{kmpl})?", text):
        if out["min_mileage_kmpl"] is None:
            out["min_mileage_kmpl"] = float(m.group(1) or m.group(2))
            trace.append(f"min_mileage_kmpl={out['min_mileage_kmpl']} <- rule '{m.group(0).strip()}'")
        text = _mask(text, m)
    return text


def _parse_budget(text: str, out: dict, trace: list) -> str:
    budget = out["budget"]
    cue = r"(?:budget|price|priced|cost(?:ing)?|under|below|within|upto|up\s*to)"
    # "can't go above 8 lakh", "cannot exceed", "won't spend more than": a stated ceiling, never a floor
    cant = (r"(?:can'?t|cannot|can\s*not|won'?t|wont|will\s*not|don'?t|dont|do\s*not)\s*"
            r"(?:go|spend|pay|stretch|exceed|afford|cross)?\s*(?:above|over|beyond|past|more\s*than)?")
    max_pre = (r"(?:under|below|less\s*than|within|upto|up\s*to|max(?:imum)?|not\s*more\s*than|no\s*more\s*than|<|budget\s*(?:is|of)?"
               + "|exceed(?:ing)?|" + cant + ")")
    # "8 lakh se upar nahi ja sakta": Hindi ceiling
    max_post = (r"(?:tak|ke\s*andar|ke\s*under|se\s*kam|ke\s*neeche|or\s*less|or\s*below|and\s*below|max(?:imum)?"
                r"|se\s*(?:upar|oopar|zyada|jyada|zyaada)\s*nahi(?:\s*(?:ja\s*sak\w*|jaun\w*|jan\w*|jayeg\w*|chahiye|chaiye|chalega|chalegi))?)")
    min_pre = r"(?:above|over|more\s*than|at\s*least|min(?:imum)?|starting|>)"
    min_post = r"(?:se\s*upar|se\s*zyada|and\s*above|or\s*more|plus|\+)"
    around_pre = r"(?:around|about|approx(?:imately)?\.?|roughly|near|~|lagbhag)"
    around_post = r"(?:ke\s*aas\s*-?\s*paas|ke\s*around|or\s*so)"

    def record(kind: str, m: re.Match, lo: int | None, hi: int | None):
        nonlocal text
        if kind == "around":
            lo, hi = round(lo * (1 - AROUND_BAND)), round(lo * (1 + AROUND_BAND))
        if lo is not None and budget["min"] is None:
            budget["min"] = lo
        if hi is not None and budget["max"] is None:
            budget["max"] = hi
        trace.append(f"budget {kind} min={lo} max={hi} <- rule '{m.group(0).strip()}'")
        text = _mask(text, m)

    # ranges: "10-15 lakh", "8 to 12 lakh", "between 8 and 12 lakh", "10 se 12 lakh"
    for m in _find(rf"(?:between\s*)?{AMOUNT}\s*(?:-|–|to|se|and)\s*{AMOUNT}", text):
        n1, u1, n2, u2 = m.groups()
        if "and" in m.group(0) and not m.group(0).startswith("between"):
            continue
        has_cue = bool(re.search(cue + r"\W*$", text[:m.start()]))
        if not (u1 or u2 or has_cue):
            continue
        lo, hi = _rupees(n1, u1 or u2, True), _rupees(n2, u2 or u1, True)
        if lo is not None and hi is not None and lo < hi:
            record("range", m, lo, hi)
            break

    for kind, pre, post in (("max", max_pre, max_post), ("min", min_pre, min_post), ("around", around_pre, around_post)):
        for m in _find(rf"{pre}\s*{AMOUNT}|{AMOUNT}\s*{post}", text):
            groups = [g for g in m.groups()]
            number, unit = (groups[0], groups[1]) if groups[0] else (groups[2], groups[3])
            value = _rupees(number, unit, cue=True)
            if value is None or (not unit and number and MEASURE_AFTER.match(text, m.end())):
                continue
            record(kind, m, value if kind != "max" else None, value if kind == "max" else None)

    # bare amount with an explicit currency unit ("budget 12.5L", "15 lakh") -> max
    if budget["min"] is None and budget["max"] is None:
        for m in _find(AMOUNT, text):
            number, unit = m.groups()
            explicit = unit or re.match(r"rs|inr", m.group(0))
            if not explicit:
                continue
            if unit == "l" and float(number.replace(",", "")) < 3 and not re.search(cue + r"\W*$", text[:m.start()]):
                trace.append(f"ignored '{m.group(0).strip()}': looks like engine displacement")
                continue
            value = _rupees(number, unit, cue=True)
            if value:
                record("max", m, None, value)
                break
    return text


# ---------------------------------------------------------------------------
# Categorical fields
# ---------------------------------------------------------------------------

def _parse_vocab(patterns, text: str, field: str, trace: list) -> tuple[list[str], list[str], bool, str]:
    """Return (positive labels, negated labels, any mention, masked text)."""
    found, negated, mentioned = [], [], False
    matches = []
    for label, pattern in patterns:
        for m in _find(pattern, text):
            matches.append((label, m))
            text = _mask(text, m)
    # negation is judged with every term of this vocab blanked, so list order doesn't matter
    for label, m in sorted(matches, key=lambda lm: lm[1].start()):
        mentioned = True
        if _is_negated(text, m.start(), m.end()):
            if label not in negated:
                negated.append(label)
                trace.append(f"{field}-={label} <- negated '{m.group(0).strip()}'")
        elif label not in found:
            found.append(label)
            trace.append(f"{field}+={label} <- rule '{m.group(0).strip()}'")
    found = [label for label in found if label not in negated]
    return found, negated, mentioned, text


# ---------------------------------------------------------------------------
# Typo tolerance vocabulary: word -> meaning group (see services/typos.py). Canonical spelling first in a group.
# ---------------------------------------------------------------------------

_TYPO_GROUPS = {
    "petrol": ["petrol", "gasoline"], "diesel": ["diesel"], "electric": ["electric"], "hybrid": ["hybrid", "hybrids"],
    "hatchback": ["hatchback", "hatchbacks", "hatch"], "sedan": ["sedan", "sedans"], "minivan": ["minivan"],
    "pickup": ["pickup", "pickups"],
    "automatic": ["automatic", "automatics", "autobox"], "manual": ["manual", "manuals"],
    "clutchless": ["clutchless"], "converter": ["converter"],
    "sunroof": ["sunroof", "moonroof", "panoramic"], "ventilated": ["ventilated"], "cruise": ["cruise"],
    "wireless": ["wireless"], "charging": ["charging", "charger"], "android": ["android"], "carplay": ["carplay"],
    "camera": ["camera"], "adaptive": ["adaptive"],
    "lakh": ["lakhs", "lakh"], "crore": ["crores", "crore"], "seater": ["seater", "seaters", "seats", "seating"],
    "budget": ["budget"], "mileage": ["mileage"], "airbags": ["airbags", "airbag"],
}
_typo_vocab: dict[str, str] | None = None


def _typo_vocabulary() -> dict[str, str]:
    global _typo_vocab
    if _typo_vocab is None:
        vocab: dict[str, str] = {}
        for group, words in _TYPO_GROUPS.items():
            for w in words:
                vocab.setdefault(w, group)
        _load_model_vocab()
        names = [m for m in _model_info] + [make for make, _ in MAKE_PATTERNS] + [b for b, _ in UNSUPPORTED_BRAND_PATTERNS]
        names += list(MODEL_ALIASES) + [info["make"] for info in _model_info.values()]
        for name in names:
            for w in re.findall(r"[a-z]+", name.lower()):
                if len(w) >= 5:
                    vocab.setdefault(w, "name:" + w)
        _typo_vocab = vocab
    return _typo_vocab


def _model_regex(name: str) -> str:
    # "XUV 3XO" -> xuv[\s.-]*3[\s.-]*xo : matches "xuv 3xo", "xuv3xo", "XUV-3XO"
    chunks = re.findall(r"[a-z]+|\d+", name.lower())
    return r"[\s.\-]*".join(chunks)


_model_vocab: list[tuple[str, str, list[str]]] | None = None  # (regex, needs_make, models)
_model_info: dict[str, dict] = {}


def _load_model_vocab() -> list[tuple[str, str | None, list[str]]]:
    global _model_vocab
    if _model_vocab is None:
        with CATALOGUE_CSV.open(encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                _model_info.setdefault(row["model"], {"make": row["make"], "body_type": row["body_type"]})
        make_regex = dict(MAKE_PATTERNS)
        vocab = []
        for model, info in _model_info.items():
            needs_make = make_regex[info["make"]] if model in AMBIGUOUS_MODELS else None
            vocab.append((_model_regex(model), needs_make, [model]))
        for alias, models in MODEL_ALIASES.items():
            models = [m for m in models if m in _model_info]
            if models:
                vocab.append((_model_regex(alias), None, models))
        # longest pattern first: "scorpio classic" before the "scorpio" alias, "thar roxx" before "thar"
        _model_vocab = sorted(vocab, key=lambda v: -len(v[0]))
    return _model_vocab


def _parse_models(text: str, out: dict, trace: list) -> tuple[list[str], str]:
    """Hard model filters into out["models"]; returns (reference models, masked text)."""
    any_make = "|".join(p for _, p in MAKE_PATTERNS)
    references = []
    for pattern, needs_make, models in _load_model_vocab():
        for m in _find(pattern, text):
            before = text[:m.start()]
            if needs_make and not re.search(rf"(?<![a-z0-9])(?:{needs_make})\s*$", before):
                continue
            before = re.sub(rf"(?<![a-z0-9])(?:{any_make})\s*$", "", before)
            if re.search(REFERENCE_BEFORE, before) or re.match(REFERENCE_AFTER, text[m.end():]):
                references += [x for x in models if x not in references]
                trace.append(f"reference model {models} <- '{m.group(0).strip()}' (similar-to, not a filter)")
            else:
                out["models"] += [x for x in models if x not in out["models"]]
                trace.append(f"models+={models} <- rule '{m.group(0).strip()}'")
            text = _mask(text, m)
    return references, text


def _short_transmission_tokens(text: str):
    words = list(re.finditer(r"[a-z0-9'+]+", text))
    for i, w in enumerate(words):
        if w.group(0) not in SHORT_TRANSMISSION:
            continue
        prev_w = words[i - 1].group(0) if i > 0 and not CLAUSE_BREAK.search(text[words[i - 1].end():w.start()]) else None
        next_w = words[i + 1].group(0) if i + 1 < len(words) and not CLAUSE_BREAK.search(text[w.end():words[i + 1].start()]) else None
        if next_w in SHORT_CONTEXT_AFTER or (
            prev_w in SHORT_CONTEXT_BEFORE and next_w not in SHORT_STOP_AFTER and not (next_w or "").isdigit()
        ):
            yield SHORT_TRANSMISSION[w.group(0)], w


def _parse_transmission(text: str, out: dict, trace: list) -> str:
    hits = []  # (label, negated, match)
    for label, pattern in TRANSMISSION_PATTERNS:
        for m in _find(pattern, text):
            hits.append((label, _is_negated(text, m.start(), m.end()), m))
            text = _mask(text, m)
    for label, m in list(_short_transmission_tokens(text)):
        hits.append((label, _is_negated(text, m.start(), m.end()), m))
        text = _mask(text, m)

    families, include, exclude = set(), [], []
    for label, negated, m in sorted(hits, key=lambda h: h[2].start()):
        types = TRANSMISSION_TYPES_FOR[label]
        trace.append(f"transmission {'NOT ' if negated else ''}{label} <- rule '{m.group(0).strip()}'")
        if label in ("automatic", "manual"):
            other = "manual" if label == "automatic" else "automatic"
            families.add(other if negated else label)
            continue
        if negated:
            exclude.extend(t for t in types if t not in exclude)
            if any(t in AUTOMATIC_TYPES for t in types):
                families.add("automatic")  # "no AMT" -> some other automatic
        else:
            include.extend(t for t in types if t not in include)
            families.add("manual" if types == ["imt"] else "automatic")

    include = [t for t in include if t not in exclude]
    if len(families) > 1:
        trace.append("transmission: both families requested, family left open")
        if include and "manual" in families:
            include += [t for t in ("manual", "imt") if t not in include and t not in exclude]
        family = None
    else:
        family = families.pop() if families else None
    out["transmission"] = {
        "family": family,
        "include_types": [t for t in TRANSMISSION_TYPES if t in include],
        "exclude_types": [t for t in TRANSMISSION_TYPES if t in exclude],
    }
    return text


# ---------------------------------------------------------------------------
# ML fallback
# ---------------------------------------------------------------------------

_ml_parser = None
_ml_unavailable = False


def _ml_predict(query: str) -> dict[str, tuple[str, float]] | None:
    """{field: (label, probability)} from the existing ML models, or None if they can't load."""
    global _ml_parser, _ml_unavailable
    if _ml_unavailable:
        return None
    if _ml_parser is None:
        try:
            from ml_parser.ml_intent_parser import MLIntentParser
            _ml_parser = MLIntentParser()
        except Exception:  # missing models / deps: run rules-only
            _ml_unavailable = True
            return None
    preds = {}
    for field, model in (("body", _ml_parser.body_type_model), ("fuel", _ml_parser.fuel_type_model),
                         ("use_case", _ml_parser.use_case_model)):
        proba = model.predict_proba([query])[0]
        best = int(proba.argmax())
        preds[field] = (str(model.classes_[best]), float(proba[best]))
    return preds


def _apply_ml(query: str, out: dict, mentioned: dict, trace: list) -> None:
    """Fill unmentioned body/fuel/use_case from the ML models. Body and fuel guesses are only ever
    "assumed" (soft, shown to the user, never a filter); use_case is a ranking hint as before."""
    need = [f for f in ("body", "fuel", "use_case") if not mentioned[f]]
    if not need:
        return
    preds = _ml_predict(query)
    if preds is None:
        trace.append("ml: unavailable, rules only")
        return
    for field in need:
        label, p = preds[field]
        label = "mpv" if label == "muv" else label
        if label in ("unknown", "general") or p < ML_MIN_CONFIDENCE:
            continue
        if field == "body" and label in BODY_TYPES:
            out["assumed"]["body_types"] = [label]
        elif field == "fuel" and label in FUEL_TYPES:
            out["assumed"]["fuel_types"] = [label]
        elif field == "use_case":
            out["use_case"] = label
        else:
            continue
        trace.append(f"{field}={label} <- ml p={p:.2f}" + (" (assumed, not a filter)" if field != "use_case" else ""))


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

_CONTENT_LIST_FIELDS = ["body_types", "fuel_types", "makes", "models", "reference_models", "required_features",
                        "exclude_features", "exclude_makes", "exclude_fuel_types", "exclude_body_types",
                        "soft_preferences"]
_CONTENT_SCALAR_FIELDS = ["seats_min", "min_airbags", "min_safety_stars", "min_boot_space_litres",
                          "min_ground_clearance_mm", "min_ev_range_km", "min_mileage_kmpl", "min_mileage_km_per_kg",
                          "max_ev_range_km", "max_ground_clearance_mm", "max_boot_space_litres", "max_mileage_kmpl",
                          "max_mileage_km_per_kg", "use_case"]


def _classify_content(out: dict) -> tuple[bool, bool]:
    """(vague, unsupported_only), judged on what the rules found. Vague: no constraint or preference of any
    kind. Unsupported only: nothing but a brand the catalogue does not carry."""
    trans = out["transmission"]
    has_content = (
        any(out[f] for f in _CONTENT_LIST_FIELDS)
        or any(out[f] is not None for f in _CONTENT_SCALAR_FIELDS)
        or out["cheap_intent"]
        or out["budget"]["min"] is not None or out["budget"]["max"] is not None
        or bool(trans["family"] or trans["include_types"] or trans["exclude_types"])
    )
    if has_content:
        return False, False
    return (not out["unsupported_terms"]), bool(out["unsupported_terms"])


def parse_intent(text: str, use_ml: bool = True) -> dict:
    return parse_intent_ex(text, use_ml)[0]


def parse_intent_ex(text: str, use_ml: bool = True) -> tuple[dict, str]:
    """parse_intent plus the RESIDUAL: the lower-cased (typo-corrected) query with every span the rules consumed
    (brands, models, features, numbers, budgets, gearbox, fuel, body, makes) blanked out. Soft-preference and use-case
    words are not blanked here (they only set weights); services/recsys/llm_parse.py decides what is "unexplained"."""
    out = {
        "budget": {"min": None, "max": None},
        "body_types": [],
        "fuel_types": [],
        "transmission": {"family": None, "include_types": [], "exclude_types": []},
        "seats_min": None,
        "makes": [],
        "required_features": [],
        "min_airbags": None,
        "min_safety_stars": None,
        "min_boot_space_litres": None,
        "min_ground_clearance_mm": None,
        "min_ev_range_km": None,
        "min_mileage_kmpl": None,
        "min_mileage_km_per_kg": None,
        "max_ev_range_km": None,
        "max_ground_clearance_mm": None,
        "max_boot_space_litres": None,
        "max_mileage_kmpl": None,
        "max_mileage_km_per_kg": None,
        "use_case": None,
        "cheap_intent": False,
        "exclude_features": [],
        "exclude_makes": [],
        "exclude_fuel_types": [],
        "exclude_body_types": [],
        "models": [],
        "reference_models": [],
        "unsupported_terms": [],
        "corrections": [],
        "soft_preferences": [],
        "assumed": {"body_types": [], "fuel_types": []},
        "vague": False,
        "unsupported_only": False,
        "trace": [],
    }
    trace = out["trace"]
    work = " " + re.sub(r"\s+", " ", (text or "").lower().replace("₹", " rs ")) + " "
    work, out["corrections"] = correct_typos(work, _typo_vocabulary())
    for c in out["corrections"]:
        trace.append(f"typo: read '{c['from']}' as '{c['to']}'")

    # brands we don't carry and model names go first, so "Mini Cooper" / "XUV 3XO" can't leak into other fields
    unsupported, _, _, work = _parse_vocab(UNSUPPORTED_BRAND_PATTERNS, work, "unsupported", trace)
    out["unsupported_terms"] = sorted(unsupported)
    references, work = _parse_models(work, out, trace)
    out["models"] = sorted(out["models"])
    out["reference_models"] = sorted(references)
    # use case reads this (only models blanked): "family of 5" is both seats_min and a family use case
    use_case_text = work

    # then features, so "android auto" / "360 camera" / "level 2" can't leak into other fields
    features, no_features, _, work = _parse_vocab(FEATURE_PATTERNS, work, "feature", trace)
    if "adaptive_cruise" in features:
        features += ["adas", "cruise_control"]
    out["required_features"] = [f for f in FEATURES if f in features]
    # "no sunroof", "without ADAS", "sunroof nahi chahiye" (a negated adaptive cruise names no single feature: ignored)
    out["exclude_features"] = [f for f in FEATURES if f in no_features and f not in out["required_features"]]

    work = _parse_numeric_specs(work, out, trace)
    work = _parse_budget(work, out, trace)
    # ML sees the text with feature/number/budget phrases removed, so "budget 12 lakh" can't become use_case=budget
    ml_text = work
    soft, _, _, _ = _parse_vocab(SOFT_PREFERENCE_PATTERNS, work, "soft", trace)
    out["soft_preferences"] = [s for s in SOFT_PREFERENCES if s in soft]
    work = _parse_transmission(work, out, trace)

    fuels, no_fuels, fuel_mentioned, work = _parse_vocab(FUEL_PATTERNS, work, "fuel", trace)
    out["fuel_types"] = [f for f in FUEL_TYPES if f in fuels]
    out["exclude_fuel_types"] = [f for f in FUEL_TYPES if f in no_fuels]
    bodies, no_bodies, body_mentioned, work = _parse_vocab(BODY_PATTERNS, work, "body", trace)
    out["body_types"] = [b for b in BODY_TYPES if b in bodies]
    out["exclude_body_types"] = [b for b in BODY_TYPES if b in no_bodies]
    if references and not body_mentioned:
        # "something like Creta": use the reference model's body type, nothing else
        ref_bodies = {_model_info[m]["body_type"] for m in references}
        out["body_types"] = [b for b in BODY_TYPES if b in ref_bodies]
        body_mentioned = True
        trace.append(f"body_types={out['body_types']} <- reference model {references}")
    makes, no_makes, _, work = _parse_vocab(MAKE_PATTERNS, work, "make", trace)
    out["makes"] = sorted(makes)
    out["exclude_makes"] = sorted(no_makes)  # "not Tata", "Maruti nahi chahiye"

    use_case_mentioned = False
    for label, pattern in USE_CASE_PATTERNS:
        m = next(iter(_find(pattern, use_case_text)), None)
        if m:
            use_case_mentioned = True
            out["use_case"] = label
            trace.append(f"use_case={label} <- rule '{m.group(0).strip()}'")
            break

    cheap = next(iter(_find(CHEAP_INTENT_PATTERN, use_case_text)), None)
    if cheap:
        out["cheap_intent"] = True
        trace.append(f"cheap_intent <- rule '{cheap.group(0).strip()}'")

    out["vague"], out["unsupported_only"] = _classify_content(out)

    if use_ml:
        _apply_ml(ml_text, out, {"body": body_mentioned, "fuel": fuel_mentioned, "use_case": use_case_mentioned}, trace)
    return out, work
