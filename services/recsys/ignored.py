"""Car attributes a shopper may ask for that the catalogue cannot filter on.

An allow-list on purpose: only phrases from LEXICON are ever reported, and only when they are still present in the rule
parser's residual (the query with every span the parser used blanked out). Filler words ("lena", "chalega") never match.
"""

import re
from typing import List

from services.recsys.llm_parse import _SOFT_SPANS  # soft-preference / use-case phrases: used as weights, never "ignored"

MAX_IGNORED = 4

# (label shown to the shopper, regex alternatives)
LEXICON = [
    ("convertible", r"convertible|cabriolet|cabrio|soft ?top|drop ?top"),
    ("coupe", r"coupe|coupé"),
    ("roadster", r"roadster"),
    ("pickup", r"pick[- ]?up(?: truck)?"),
    ("truck", r"truck"),
    ("van", r"van|minivan"),
    ("wagon", r"station wagon|estate car|wagon"),
    ("limousine", r"limousine|limo"),
    ("supercar", r"supercar|super car"),
    ("sports car", r"sports ?car"),
    ("turbo", r"turbo|turbocharged"),
    ("supercharged", r"supercharged"),
    ("V6 / V8 / V12", r"v6|v8|v12"),
    ("4x4 / AWD", r"awd|4wd|4x4|all[- ]wheel drive|four[- ]wheel drive"),
    ("RWD", r"rwd|rear[- ]wheel drive"),
    ("left-hand drive", r"lhd|left[- ]hand drive"),
    ("hydrogen", r"hydrogen"),
    ("LPG", r"lpg"),
    ("off-road", r"off[- ]?road(?:er|ing)?"),
    ("camper", r"caravan|camper(?: ?van)?|motorhome|motor home|rv"),
    ("colour", r"white|black|red|blue|silver|grey|gray|green|yellow|orange|maroon|brown|beige|golden|colou?r"),
    ("size", r"compact|parking (?:spot|space|slot)|length|lambai|metres?|meters?|(?:\d+(?:\.\d+)? ?)?(?:m|metres?|meters?|mtr) (?:long|length)|sub[- ]?4 ?(?:m|metres?|meters?)"
               r"|(?:under|below|less than|within) \d+(?:\.\d+)? ?(?:m|metres?|meters?|mtr)"),
    ("ground clearance", r"(?:high |good |more )?ground clearance"),
    ("captain seats", r"captain(?:'s)? seats?|captain chairs?"),
    ("fast charging", r"fast[- ]charg(?:ing|er|e)|dc charg(?:ing|er)|quick charg(?:ing|e)"),
    ("easy entry", r"easy (?:entry|ingress|to get in(?:to)?)|high seating"),
]

_COMPILED = [(label, re.compile(r"(?<![\w-])(?:" + alts + r")(?![\w-])", re.IGNORECASE)) for label, alts in LEXICON]


def ignored_terms(residual: str) -> List[str]:
    """Labels of lexicon attributes still present in the residual, in query order, de-duplicated, at most MAX_IGNORED."""
    if not residual:
        return []
    residual = _SOFT_SPANS.sub(" ", residual)
    found = []
    for label, rx in _COMPILED:
        m = rx.search(residual)
        if m:
            found.append((m.start(), label))
    return [label for _, label in sorted(found)][:MAX_IGNORED]
