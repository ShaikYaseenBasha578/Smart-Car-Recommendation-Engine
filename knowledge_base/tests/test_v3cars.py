import pytest
from knowledge_base.ingestion.v3cars.field_map_v3cars import map_v3cars_features, parse_price
from knowledge_base.ingestion.common.resolver import validate_structured

def test_v3cars_feature_mapping():
    raw_features = [
        "Anti-Lock Braking System (ABS) : Yes",
        "Panoramic Sunroof",
        "Cruise Control"
    ]
    mapped = map_v3cars_features(raw_features)
    assert mapped.get('sunroof') == 1
    assert mapped.get('cruise_control') == 1
    assert mapped.get('heads_up_display') == 0
    
def test_v3cars_transmission_mismatch():
    mock_db = {
        'fuel_type': 'Petrol',
        'transmission': 'DCT',
        'engine_cc': 1498,
        'price_ex_showroom': 1500000
    }
    
    # Perfect match should yield NO warnings
    warnings = validate_structured(mock_db, 'Petrol', 'Automatic', 1498, 1500000)
    assert len(warnings) == 0
    
    # Mismatch on fuel should yield a fuel_mismatch warning
    warnings = validate_structured(mock_db, 'Diesel', 'Automatic', 1498, 1500000)
    assert 'fuel_mismatch' in warnings

def test_v3cars_price_parsing():
    assert parse_price("₹ 10.50 Lakh") == 1050000
    assert parse_price("₹ 1.20 Crore") == 12000000
    assert parse_price("15.00 Lakh") == 1500000
    assert parse_price(None) is None
