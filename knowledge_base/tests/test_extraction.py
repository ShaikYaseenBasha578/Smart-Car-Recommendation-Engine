import pytest
from knowledge_base.ingestion.source_91wheels.field_map_91wheels import safe_float, safe_bool, normalize_summary_specs, normalize_detailed_specs

def test_safe_float():
    assert safe_float("433 Liters") == 433.0
    assert safe_float("1,497 cc") == 1497.0
    assert safe_float("NA") is None
    assert safe_float("1199-1497 cc") is None # ranges rejected
    assert safe_float("10.5 Lakh") == 1050000.0
    assert safe_float("1.2 Cr") == 12000000.0

def test_safe_bool():
    assert safe_bool("Yes") == 1
    assert safe_bool("True") == 1
    assert safe_bool("No") == 0
    assert safe_bool("False") == 0
    assert safe_bool("Not Available") is None
    assert safe_bool("") is None

def test_normalization():
    summ = {
        "displacement": "1497",
        "seating_capacity": "5",
        "tyre_pressure_monitoring_system": "Yes",
        "sunroof": "No"
    }
    norm_s = normalize_summary_specs(summ)
    assert norm_s['engine_cc'] == 1497.0
    assert norm_s['seating_capacity'] == 5
    assert norm_s['tyre_pressure_monitoring_system'] == 1
    assert norm_s['sunroof'] == 0
    
    det = {
        "Comfort": {
            "ventilated_seats": {"specs_label": "Ventilated Seats", "specs_value": "No"},
            "cruise_control": {"specs_label": "Cruise Control", "specs_value": "Yes"}
        }
    }
    norm_d = normalize_detailed_specs(det)
    assert norm_d['ventilated_front_seats'] == 0
    assert norm_d['cruise_control'] == 1
