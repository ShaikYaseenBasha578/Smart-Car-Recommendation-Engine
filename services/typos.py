"""Typo tolerance for the rule parser (no LLM).

`correct_typos(text, vocabulary)` maps each token that is not an exact vocabulary word to the closest vocabulary word
when ALL of these hold:

* the token is letters only and has at least 5 letters (shorter words are never touched);
* Damerau-Levenshtein (optimal string alignment) distance is at most 1 for 5-6 letters, 2 for 7 or more;
* the first letter is unchanged (typos rarely hit the first letter; this removes many look-alike words);
* it is not itself a vocabulary word, and not a protected everyday word (never turn one valid word into another);
* exactly one vocabulary MEANING is closest. Two words of different meaning at the same distance leave the token
  alone. Spelling variants of one meaning ("seats" / "seater") are not ambiguous: the first-listed wins.

Number words one..ten become digits, but only in front of a word that takes a number ("seven seats", "ten lakh").

The vocabulary maps word -> group (its meaning). Corrections are returned as [{"from": ..., "to": ...}].
"""

from __future__ import annotations

import re
from typing import Dict, List, Optional, Tuple

MIN_LEN = 5
NUMBER_WORDS = {"one": "1", "two": "2", "three": "3", "four": "4", "five": "5", "six": "6", "seven": "7",
                "eight": "8", "nine": "9", "ten": "10"}
# a number word is read as a digit only in front of one of these ("seven seats", "five star", "ten lakh")
NUMBER_CONTEXT = {"seater", "seaters", "seat", "seats", "seating", "people", "persons", "airbag", "airbags", "star",
                  "stars", "lakh", "lakhs", "lac", "lacs", "crore", "crores", "litre", "litres", "liter", "liters"}
# everyday words that sit one edit from a vocabulary word (model names mostly); never rewritten
PROTECTED = {
    "shift", "shifts", "extra", "enter", "after", "eater", "create", "created", "tiger", "nexus", "lunch", "punch",
    "bunch", "heart", "hectic", "dusty", "buster", "tribe", "tribes", "sweet", "other", "water", "right", "light",
    "night", "sight", "might", "price", "prices", "brand", "grand", "urban", "great", "steel", "seeds", "heads",
    "autos", "audio", "radio", "motor", "motors", "power", "tower", "lower", "never", "ever", "every", "money",
    "needs", "wants", "which", "where", "there", "these", "those", "think", "thing", "about", "above", "below",
    "under", "again", "start", "state", "stage", "small", "smart", "sport", "sports", "space", "spare", "speed",
    "drive", "drives", "diesel", "wagon", "agree", "alone", "along", "among", "build", "built", "check", "cheap",
    "class", "clear", "close", "color", "colour", "could", "would", "should", "first", "front", "fresh", "usage",
    "using", "while", "whole", "worth", "years", "young", "metro", "tonne", "range", "ranger", "paper", "voice",
    "maybe", "model", "models", "daily", "family", "luxury", "budget", "quite", "looks", "looking", "mostly",
    "better", "street", "weeks", "months", "which", "kinda", "gaadi", "gadi", "gaadiyan", "chahiye", "chaiye",
    "batao", "bataiye", "dikhao", "mujhe", "hamare", "humare", "apna", "apni", "wala", "wali", "wale", "kitna",
    "kitni", "zyada", "jyada", "thoda", "thodi", "bahut", "accha", "achha", "achhi", "sasta", "sasti", "paisa",
    "paise", "andar", "neeche", "upar", "aaspaas", "liye", "sirf", "bilkul", "suggest", "recommend", "please",
}


def _osa(a: str, b: str, limit: int) -> int:
    """Optimal-string-alignment (restricted Damerau-Levenshtein) distance; returns limit+1 when above `limit`."""
    if abs(len(a) - len(b)) > limit:
        return limit + 1
    prev2: Optional[List[int]] = None
    prev = list(range(len(b) + 1))
    for i in range(1, len(a) + 1):
        cur = [i] + [0] * len(b)
        for j in range(1, len(b) + 1):
            cost = 0 if a[i - 1] == b[j - 1] else 1
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + cost)
            if prev2 is not None and i > 1 and j > 1 and a[i - 1] == b[j - 2] and a[i - 2] == b[j - 1]:
                cur[j] = min(cur[j], prev2[j - 2] + 1)
        if min(cur) > limit:
            return limit + 1
        prev2, prev = prev, cur
    return prev[-1]


def max_distance(length: int) -> int:
    """Allowed edits for a token of this length (0 = never corrected)."""
    if length < MIN_LEN:
        return 0
    return 1 if length <= 6 else 2


def closest_word(token: str, vocabulary: Dict[str, str]) -> Optional[str]:
    """The vocabulary word `token` should be read as, or None (valid word, too short, too far, ambiguous)."""
    limit = max_distance(len(token))
    if not limit or not token.isalpha() or token in vocabulary or token in PROTECTED:
        return None
    best: List[Tuple[int, str]] = []
    best_d = limit + 1
    for word in vocabulary:  # dict order = listing order: canonical spelling first within a group
        if word[0] != token[0]:
            continue
        d = _osa(token, word, limit)
        if d < best_d:
            best_d, best = d, [(d, word)]
        elif d == best_d and d <= limit:
            best.append((d, word))
    if not best or best_d > limit:
        return None
    if len({vocabulary[w] for _, w in best}) > 1:
        return None  # two different meanings equally close
    return best[0][1]


_TOKEN = re.compile(r"(?<![a-z0-9])[a-z]+(?![a-z0-9])")


def correct_typos(text: str, vocabulary: Dict[str, str]) -> Tuple[str, List[dict]]:
    """(corrected lower-case text, [{"from", "to"}, ...]). `text` must already be lower-cased."""
    corrections: List[dict] = []
    out: List[str] = []
    pos = 0
    tokens = list(_TOKEN.finditer(text))
    for k, m in enumerate(tokens):
        word = m.group(0)
        new = None
        if word in NUMBER_WORDS:
            tail = re.match(r"\s*-?\s*([a-z]+)", text[m.end():])
            nxt = tail.group(1) if tail else ""
            if nxt not in NUMBER_CONTEXT:
                nxt = closest_word(nxt, vocabulary) or nxt  # "seven seatr"
            if nxt in NUMBER_CONTEXT:
                new = NUMBER_WORDS[word]
        else:
            new = closest_word(word, vocabulary)
        if new and new != word:
            corrections.append({"from": word, "to": new})
            out.append(text[pos:m.start()])
            out.append(new)
            pos = m.end()
    out.append(text[pos:])
    return "".join(out), corrections
