import pytest
import sqlite3
import os
from knowledge_base.ingestion.oem.extractor.classifier import classify_layout

SWIFT_PDF = "knowledge_base/sources/oem/maruti_suzuki/swift/gen4_2024/brochures/Maruti_Suzuki_Swift_Gen4_2024_Official_Brochure.pdf"
FRONX_PDF = "knowledge_base/sources/oem/maruti_suzuki/fronx/latest/brochures/Fronx_Brochure.pdf"

def get_configs(pdf_path, make, model):
    strategy = classify_layout(pdf_path, make, model)
    return strategy.extract(pdf_path)

def test_swift_extraction_count_and_determinism():
    """Verify Swift exactly 12 configurations, run twice to ensure deterministic idempotency"""
    configs1 = get_configs(SWIFT_PDF, "Maruti Suzuki", "Swift")
    assert len(configs1) == 12, "Swift must have exactly 12 configurations extracted"
    
    # Check determinism
    configs2 = get_configs(SWIFT_PDF, "Maruti Suzuki", "Swift")
    
    assert [c.raw_variant_name for c in configs1] == [c.raw_variant_name for c in configs2]
    assert [c.powertrain_type for c in configs1] == [c.powertrain_type for c in configs2]
    assert [c.transmission for c in configs1] == [c.transmission for c in configs2]
    
    # Verify expected variants
    expected_combos = [
        ("LXi", "Petrol", "MT"),
        ("VXi", "Petrol", "MT"),
        ("VXi", "Petrol", "AMT"),
        ("VXi", "CNG", "MT"),
        ("VXi (O)", "Petrol", "MT"),
        ("VXi (O)", "Petrol", "AMT"),
        ("VXi (O)", "CNG", "MT"),
        ("ZXi", "Petrol", "MT"),
        ("ZXi", "Petrol", "AMT"),
        ("ZXi", "CNG", "MT"),
        ("ZXi+", "Petrol", "MT"),
        ("ZXi+", "Petrol", "AMT")
    ]
    actual_combos = [(c.raw_variant_name, c.powertrain_type, c.transmission) for c in configs1]
    for combo in expected_combos:
        assert combo in actual_combos, f"Missing expected Swift combo: {combo}"

def test_swift_identity_and_evidence():
    """Verify exact fields, boolean semantics, and missing data for Swift"""
    configs = get_configs(SWIFT_PDF, "Maruti Suzuki", "Swift")
    zxi_plus_amt = next(c for c in configs if c.raw_variant_name == "ZXi+" and c.transmission == "AMT")
    
    fields = {f.field_name: f.raw_value for f in zxi_plus_amt.fields}
    
    # Check representative boolean / text fields
    assert "Wireless Charger" in fields
    assert fields["Wireless Charger"] == "Standard", "Must preserve normalized OEM symbol for True"
    
    assert "Wide-angle Rear Parking Camera" in fields
    assert fields["Wide-angle Rear Parking Camera"] == "Standard"

def test_swift_boolean_and_missing():
    """Verify missing values are accurately captured and NOT defaulted to False silently"""
    configs = get_configs(SWIFT_PDF, "Maruti Suzuki", "Swift")
    lxi = next(c for c in configs if c.raw_variant_name == "LXi" and c.powertrain_type == "Petrol")
    fields = {f.field_name: f.raw_value for f in lxi.fields}
    
    assert "Wireless Charger" in fields
    assert fields["Wireless Charger"] == "-", "Must preserve explicit absence (-)"
    
def test_fronx_extraction_count():
    """Verify Fronx generic layout extraction accurately reconstructs multi-line headers"""
    configs = get_configs(FRONX_PDF, "Maruti Suzuki", "Fronx")
    assert len(configs) == 12, "Fronx must correctly expand to 12 powertrain configurations"
    
    # Check that generic parsing perfectly reconstructed the multi-line header
    delta_plus_amt = next((c for c in configs if c.raw_variant_name == "Delta+" and c.transmission == "AMT"), None)
    assert delta_plus_amt is not None
    assert delta_plus_amt.engine_name == "1.2L", "Parsed engine correctly from generic regex"
    
    zeta = next((c for c in configs if c.raw_variant_name == "Zeta" and c.transmission == "AT"), None)
    assert zeta is not None
    assert zeta.engine_name == "1.0L Turbo", "Zeta engine successfully parsed across multi-line headers"

def test_generic_header_parsing():
    """Synthetic regression test for generic header structural expansion"""
    from knowledge_base.ingestion.oem.extractor.families.variant_column_matrix import VariantColumnMatrixStrategy
    strat = VariantColumnMatrixStrategy()
    
    # Test combinations without hardcoding OEM/model logic
    configs = strat._expand_header("TestTrim 1.5L CRDi MT/AMT & 1.0L Turbo AT CNG")
    
    assert len(configs) == 3
    assert configs[0]["engine"] == "1.5L CRDi"
    assert configs[0]["trans"] == "MT"
    assert configs[0]["fuel"] == "Petrol"
    
    assert configs[1]["engine"] == "1.5L CRDi"
    assert configs[1]["trans"] == "AMT"
    
    assert configs[2]["engine"] == "1.0L Turbo"
    assert configs[2]["trans"] == "AT"
    assert configs[2]["fuel"] == "CNG"

def test_variant_column_matrix_fail_closed():
    """Verify strategy safely fails closed on missing/malformed PDF"""
    from knowledge_base.ingestion.oem.extractor.families.variant_column_matrix import VariantColumnMatrixStrategy
    strat = VariantColumnMatrixStrategy()
    with pytest.raises((ValueError, FileNotFoundError)):
        strat.extract("non_existent_brochure.pdf")
from knowledge_base.ingestion.oem.extractor.families.variant_column_matrix import VariantColumnMatrixStrategy
def test_false_positive_rejection():
    strat = VariantColumnMatrixStrategy()
    
    # Simulate a dimension table that should be rejected
    dim_matrix = [
        ["Dimensions", "Overall Length", "Overall Width", "Wheelbase"],
        ["Value", "4295", "1770", "2600"],
        ["Ground Clearance", "190", "190", "190"]
    ]
    
    # We test _score_candidate directly to verify it fails
    score = strat._score_candidate(0, dim_matrix[0], dim_matrix[1:])
    assert score < 20, f"Dimension table scored too high: {score}"
    
    # Simulate an engine table that should be rejected
    engine_matrix = [
        ["Engine Type", "1.0 TSI", "1.5 TSI"],
        ["Displacement", "999", "1498"],
        ["Max Power", "85 kW", "110 kW"]
    ]
    score = strat._score_candidate(0, engine_matrix[0], engine_matrix[1:])
    assert score < 20, f"Engine table scored too high: {score}"

    # Simulate a valid feature matrix that should pass
    valid_matrix = [
        ["Features", "Sigma", "Delta"],
        ["Airbags", "Y", "Y"],
        ["Sunroof", "-", "Y"],
        ["Alloy Wheels", "-", "-"]
    ]
    score = strat._score_candidate(0, valid_matrix[0], valid_matrix[1:])
    assert score >= 20, f"Valid feature table scored too low: {score}"
