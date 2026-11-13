from kbpipe import reconcile as R

CFG = {"numeric_tolerance": 0.02, "agree_tolerance": 0.01}
A = lambda v: {"source": "carwale", "cls": "aggregator", "value": v, "obs": "a"}
B = lambda v: {"source": "cardekho", "cls": "aggregator", "value": v, "obs": "b"}
O = lambda v: {"source": "oem", "cls": "oem", "value": v, "obs": "o"}


def test_two_aggregators_agree_is_written_with_first_source_value():
    d = R.decide("power_bhp", [A(87), B(86.6)], CFG)
    assert d["status"] == "VALUE" and d["value"] == 87 and d["reason"] == "AGGREGATOR_AGREED_UNVERIFIED"
    assert [e["decision"] for e in d["evidence"]] == ["accepted", "confirmed"]


def test_single_aggregator_never_decides():
    d = R.decide("boot_space_litres", [B(366)], CFG)
    assert d["status"] == "NULL" and d["reason"] == "SINGLE_SOURCE" and d["conflict"] is None


def test_same_aggregator_twice_is_still_one_source():
    assert R.decide("airbags", [A(6), A(6)], CFG)["reason"] == "SINGLE_SOURCE"


def test_boolean_disagreement_is_a_high_conflict_and_stays_null():
    d = R.decide("sunroof", [A(1), B(0)], CFG)
    assert d["status"] == "NULL" and d["reason"] == "CONFLICT" and d["conflict"]["high"] is True


def test_small_numeric_gap_is_a_logged_low_conflict():
    d = R.decide("length_mm", [A(3995), B(3940)], CFG)          # 1.4%: beyond rounding, under the review threshold
    assert d["status"] == "NULL" and d["conflict"]["high"] is False


def test_large_numeric_gap_is_high():
    assert R.decide("price_ex_showroom", [A(800000), B(900000)], CFG)["conflict"]["high"] is True


def test_counts_must_match_exactly():
    assert R.decide("airbags", [A(6), B(2)], CFG)["status"] == "NULL"
    assert R.decide("seating_capacity", [A(7), B(7)], CFG)["status"] == "VALUE"


def test_brochure_beats_aggregators_and_logs_the_conflict():
    d = R.decide("fuel_tank_litres", [A(44), B(44), O(45)], CFG)
    assert d["status"] == "VALUE" and d["value"] == 45 and d["reason"] == "OEM_BROCHURE"
    assert d["conflict"]["kind"] == "oem_over_aggregator"
    assert sorted(e["decision"] for e in d["evidence"]) == ["accepted", "rejected", "rejected"]


def test_brochure_alone_is_enough():
    assert R.decide("cruise_control", [O(1)], CFG)["value"] == 1


def test_two_brochure_values_that_differ_are_not_resolved():
    assert R.decide("mileage_arai_kmpl", [O(18.5), O(20.1)], CFG)["reason"] == "OEM_CONFLICT"


def test_no_source_is_null_never_a_default():
    d = R.decide("heads_up_display", [A(None), B("")], CFG)
    assert d["status"] == "NULL" and d["value"] is None and d["reason"] == "NO_SOURCE"


def test_routing():
    val = R.decide("airbags", [A(6), B(6)], CFG)
    assert R.route(val, False, None, "airbags") == "WRITE"                 # new row
    assert R.route(val, True, 6, "airbags") == "CONFIRM"                   # existing value agrees: evidence only
    assert R.route(val, True, 2, "airbags") == "REVIEW_CHANGE"             # P2: aggregators never change an existing value
    assert R.route(val, True, None, "airbags") == "REVIEW_FILL"
    assert R.route(val, True, 2, "airbags", edition=True) == "SKIP"        # P8
    conflict = R.decide("sunroof", [A(1), B(0)], CFG)
    assert R.route(conflict, False, None, "sunroof") == "REVIEW_CONFLICT"
    single = R.decide("airbags", [A(6)], CFG)
    assert R.route(single, False, None, "airbags") == "FLAG_NULL"


def test_generic_automatic_supports_a_specific_gearbox_and_is_logged():
    d = R.decide("transmission", [A("Torque Converter"), B("Automatic")], CFG)
    assert d["status"] == "VALUE" and d["value"] == "Torque Converter"
    assert d["conflict"]["kind"] == "generic_vs_specific" and d["conflict"]["high"] is False
    assert [e["decision"] for e in d["evidence"]] == ["accepted", "confirmed"]
    assert R.decide("transmission", [A("Automatic"), B("DCT")], CFG)["value"] == "DCT"
    assert R.decide("transmission", [A("e-CVT"), B("CVT")], CFG)["value"] == "e-CVT"


def test_real_gearbox_disagreements_are_still_conflicts():
    assert R.decide("transmission", [A("Manual"), B("Automatic")], CFG)["status"] == "NULL"
    assert R.decide("transmission", [A("DCT"), B("CVT")], CFG)["status"] == "NULL"
    assert R.decide("transmission", [A("AMT"), B("Manual")], CFG)["conflict"]["high"] is True
