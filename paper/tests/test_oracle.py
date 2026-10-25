"""Oracle unit tests on hand-built fixture rows (no DB)."""
import pytest

from oracle.feasibility import (FUEL_MAP, TRANSMISSION_MAP, UnmappedValueError, build_row, find_matches)


def raw(vid, body="SUV", fuel="Petrol", trans="Manual", seats=5, price=800000, model_id=1, model="M"):
    return {"variant_id": vid, "manufacturer": "Mfr", "model_id": model_id, "model": model, "variant_name": "V",
            "full_name": "Mfr M V", "body_type": body, "fuel_raw": fuel, "transmission_raw": trans,
            "seats": seats, "price": price}


@pytest.mark.parametrize("value,expected", [
    ("Torque Converter", "automatic"), ("AMT", "automatic"), ("DCT", "automatic"), ("CVT", "automatic"),
    ("e-CVT", "automatic"), ("Automatic", "automatic"), ("Manual", "manual"), ("iMT", "manual"),
])
def test_transmission_mapping(value, expected):
    assert build_row(raw(1, trans=value))["transmission"] == expected


def test_transmission_map_is_exactly_the_spec_set():
    assert set(TRANSMISSION_MAP) == {"Torque Converter", "AMT", "DCT", "CVT", "e-CVT", "Automatic", "Manual", "iMT"}


@pytest.mark.parametrize("value,expected", [
    ("Petrol", "petrol"), ("Diesel", "diesel"), ("Diesel Mild Hybrid", "diesel"), ("CNG", "cng"),
    ("Electric", "electric"), ("Petrol Hybrid", "hybrid"), ("Flex Fuel", None),
])
def test_fuel_mapping(value, expected):
    assert build_row(raw(1, fuel=value))["fuel"] == expected


def test_fuel_map_is_exactly_the_spec_set():
    assert set(FUEL_MAP) == {"Petrol", "Diesel", "Diesel Mild Hybrid", "CNG", "Electric", "Petrol Hybrid",
                             "Flex Fuel"}


@pytest.mark.parametrize("field,value", [("transmission", "Semi-Auto"), ("fuel", "LPG"), ("body", "Coupe")])
def test_unknown_values_raise(field, value):
    kwargs = {{"transmission": "trans"}.get(field, field): value}
    with pytest.raises(UnmappedValueError):
        build_row(raw(1, **kwargs))


@pytest.mark.parametrize("field", ["price", "seats", "body_type", "fuel_raw", "transmission_raw"])
def test_null_constraint_field_raises(field):
    r = raw(1)
    r[field] = None
    with pytest.raises(UnmappedValueError):
        build_row(r)


def test_flex_fuel_never_matches_a_fuel_constraint_but_matches_without_one():
    cat = [build_row(raw(1, fuel="Flex Fuel"))]
    for fuel in ("petrol", "diesel", "cng", "electric", "hybrid"):
        assert find_matches({"body_type": "SUV", "fuel": fuel}, cat) == []
    assert find_matches({"body_type": "SUV"}, cat) == [(1, 800000.0)]


def test_imt_is_manual_not_automatic():
    cat = [build_row(raw(1, trans="iMT"))]
    assert find_matches({"transmission": "manual"}, cat) == [(1, 800000.0)]
    assert find_matches({"transmission": "automatic"}, cat) == []


def test_diesel_mild_hybrid_is_diesel_not_hybrid():
    cat = [build_row(raw(1, fuel="Diesel Mild Hybrid", trans="Torque Converter"))]
    assert find_matches({"fuel": "diesel", "transmission": "automatic"}, cat) == [(1, 800000.0)]
    assert find_matches({"fuel": "hybrid"}, cat) == []


def test_body_type_from_model_and_seats_at_least():
    cat = [build_row(raw(1, body="MPV", seats=7)), build_row(raw(2, body="MPV", seats=6)),
           build_row(raw(3, body="SUV", seats=7))]
    assert [h[0] for h in find_matches({"body_type": "MPV", "min_seats": 7}, cat)] == [1]
    assert [h[0] for h in find_matches({"body_type": "MPV", "min_seats": 6}, cat)] == [1, 2]


def test_budget_is_inclusive_ex_showroom_and_sorted_by_price():
    cat = [build_row(raw(1, price=800000)), build_row(raw(2, price=800001)), build_row(raw(3, price=500000))]
    assert find_matches({"max_budget": 800000}, cat) == [(3, 500000.0), (1, 800000.0)]


def test_excluded_models_count_in_full_catalogue_only():
    cat = [build_row(raw(1, model_id=7, model="Brezza"), frozenset({7})), build_row(raw(2, body="Sedan"))]
    assert find_matches({"body_type": "SUV"}, cat) == [(1, 800000.0)]
    assert find_matches({"body_type": "SUV"}, cat, include_excluded=False) == []


def test_unknown_constraint_key_rejected():
    with pytest.raises(ValueError):
        find_matches({"colour": "red"}, [])
