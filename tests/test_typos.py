"""Typo tolerance (services/typos.py + intent_v2). General-rule tests; no network."""
import pytest

from services.intent_v2 import parse_intent
from services.typos import closest_word, correct_typos, max_distance

VOCAB = {"petrol": "petrol", "diesel": "diesel", "automatic": "automatic", "manual": "manual",
         "seater": "seater", "seats": "seater", "sunroof": "sunroof", "hatchback": "hatchback",
         "hatch": "hatchback", "lakhs": "lakh", "tiago": "n:tiago", "tigor": "n:tigor", "swift": "n:swift"}


def fix(text, vocab=VOCAB):
    return correct_typos(text, vocab)


def test_distance_thresholds():
    assert [max_distance(n) for n in (3, 4, 5, 6, 7, 10)] == [0, 0, 1, 1, 2, 2]


@pytest.mark.parametrize("typo,want", [
    ("diesl", "diesel"),            # 5 letters, one deletion
    ("petrl", "petrol"),            # 5 letters
    ("pteroll", "petrol"),          # 7 letters: transposition + insertion, distance 2
    ("sunrof", "sunroof"),          # 6 letters, one deletion
    ("automtic", "automatic"),      # 8 letters
    ("hatchbk", "hatchback"),       # 7 letters, two deletions
    ("manaul", "manual"),           # transposition counts as ONE edit
])
def test_corrects_within_threshold(typo, want):
    out, corr = fix(f"i want {typo} car")
    assert want in out.split() and corr == [{"from": typo, "to": want}]


def test_two_edits_not_allowed_for_short_words():
    assert closest_word("ptrl", VOCAB) is None          # 4 letters: never
    assert closest_word("dsel", VOCAB) is None
    assert closest_word("pterl", VOCAB) is None          # 5 letters, distance 2 > 1
    assert closest_word("sunrf", VOCAB) is None


def test_short_words_untouched():
    out, corr = fix("hach tiag swif lakh")
    assert corr == [] and out == "hach tiag swif lakh"


def test_valid_vocabulary_words_untouched():
    out, corr = fix("petrol diesel tiago tigor swift hatch seats")
    assert corr == []


def test_never_valid_word_into_another():
    # "tigor" and "tiago" are both valid names; neither may become the other. Protected everyday words stay.
    assert closest_word("tigor", VOCAB) is None
    assert closest_word("shift", VOCAB) is None          # one edit from "swift", but an everyday word


def test_ambiguous_untouched():
    vocab = {"hector": "n:hector", "vector": "n:vector"}
    assert closest_word("hecter", vocab) == "hector"      # unique closest (vector differs in the first letter anyway)
    vocab = {"harrer": "a", "harrow": "b"}
    assert closest_word("harrew", vocab) is None          # harrer and harrow are one edit away and mean different things
    assert closest_word("tigar", {"tigor": "a", "tiger": "b"}) is None


def test_variants_of_one_meaning_are_not_ambiguous():
    out, corr = fix("seatr")  # seats and seater are both one edit from "seatr"; same meaning -> first listed
    assert corr == [{"from": "seatr", "to": "seater"}]


def test_first_letter_must_match():
    assert closest_word("detrol", VOCAB) is None


def test_non_alpha_tokens_untouched():
    out, corr = fix("xuv3xo 7-seater s-presso 12.5l")
    assert corr == []


def test_number_words_only_before_a_number_context():
    out, corr = fix("seven seats and ten lakhs, five-seater")
    assert out == "7 seats and 10 lakhs, 5-seater"
    out, corr = fix("one more thing, the one with a sunroof, two of us")
    assert corr == [] and "1" not in out and "2" not in out


def test_number_word_before_typo_unit():
    out, corr = fix("seven seatr")
    assert out == "7 seater" and {"from": "seven", "to": "7"} in corr


def test_corrections_recorded_in_intent_and_used():
    out = parse_intent("automtic hatchbk 7 lakh with sunrof diesl", use_ml=False)
    assert out["corrections"] == [{"from": "automtic", "to": "automatic"}, {"from": "hatchbk", "to": "hatchback"},
                                  {"from": "sunrof", "to": "sunroof"}, {"from": "diesl", "to": "diesel"}]
    assert out["transmission"]["family"] == "automatic" and out["body_types"] == ["hatchback"]
    assert out["required_features"] == ["sunroof"] and out["fuel_types"] == ["diesel"]
    assert out["budget"]["max"] == 700_000


def test_intent_seven_seats_word_and_make_typo():
    out = parse_intent("diesel suv with seven seats, mahindr", use_ml=False)
    assert out["seats_min"] == 7 and out["makes"] == ["Mahindra"]


def test_clean_query_has_no_corrections():
    out = parse_intent("petrol automatic hatchback under 9 lakh with sunroof", use_ml=False)
    assert out["corrections"] == []


def test_everyday_words_not_turned_into_models():
    out = parse_intent("i shift gears often, extra punch for lunch", use_ml=False)
    assert out["corrections"] == [] and out["models"] == []
