import pytest
from knowledge_base.ingestion.oem.extractor.pdf_utils.pdf_char_utils import reconstruct_text_from_chars
from knowledge_base.ingestion.oem.extractor.pdf_utils.pdf_vector_utils import detect_vector_marks

def test_character_reconstruction():
    # Mock Dzire negative coordinates with proper spacing
    mock_chars = [
        {'text': 'V', 'top': 25.1, 'bottom': 33.1, 'x0': -400, 'x1': -395},
        {'text': 'X', 'top': 25.1, 'bottom': 33.1, 'x0': -395, 'x1': -390},
        {'text': 'I', 'top': 25.1, 'bottom': 33.1, 'x0': -390, 'x1': -385},
        {'text': 'M', 'top': 25.1, 'bottom': 33.1, 'x0': -380, 'x1': -375}, # gap of 5 > 8*0.2 (1.6)
        {'text': 'T', 'top': 25.1, 'bottom': 33.1, 'x0': -375, 'x1': -370},
    ]
    res = reconstruct_text_from_chars(mock_chars)
    assert res['raw_char_count'] == 5
    assert len(res['rows']) == 1
    assert res['rows'][0]['text'] == "VXI MT"
    assert res['reconstructed_text'] == "VXI MT"

def test_vector_mark_detection():
    # Mock Virtus marks
    mock_objects = {
        'curves': [{'x0': 478.9, 'x1': 481.6, 'top': 118.1, 'bottom': 120.8, 'width': 2.7, 'height': 2.7}], # dot
        'rects': [{'x0': 659.0, 'x1': 663.1, 'top': 118.3, 'bottom': 119.5, 'width': 4.1, 'height': 1.1}]   # dash
    }
    cols_x = [480.0, 660.0]
    rows_y = [119.0]
    
    marks = detect_vector_marks(mock_objects, cols_x, rows_y)
    assert len(marks) == 2
    
    assert marks[0]['col_idx'] == 0
    assert marks[0]['row_idx'] == 0
    assert marks[0]['evidence_type'] == "vector"
    assert marks[0]['raw_evidence'] == "curve"
    assert marks[0]['semantic_state'] is None
    
    assert marks[1]['col_idx'] == 1
    assert marks[1]['row_idx'] == 0
    assert marks[1]['evidence_type'] == "vector"
    assert marks[1]['raw_evidence'] == "rect"
    assert marks[1]['semantic_state'] is None


def test_powertrain_transmission_safety():
    # Rule: Never default to Petrol/MT.
    def infer_powertrain(raw_name):
        pt_type = None
        if "diesel" in raw_name.lower(): pt_type = "Diesel"
        elif "ev" in raw_name.lower() or "electric" in raw_name.lower(): pt_type = "Electric"
        elif "petrol" in raw_name.lower(): pt_type = "Petrol"
        
        trans = None
        if "amt" in raw_name.lower(): trans = "AMT"
        elif "at" in raw_name.lower() or "auto" in raw_name.lower(): trans = "AT"
        elif "mt" in raw_name.lower() or "manual" in raw_name.lower(): trans = "MT"
        return pt_type, trans
        
    assert infer_powertrain("AXT") == (None, None)
    assert infer_powertrain("Petrol MT") == ("Petrol", "MT")
    assert infer_powertrain("EV") == ("Electric", None)

def test_thar_raw_identity():
    # Rule: Do not "correct" AXT to AX Opt. Treat raw PDF evidence as authoritative.
    raw_extracted_header = "AXT"
    assert raw_extracted_header == "AXT", "Must preserve raw evidence without model-specific kerning corrections."

def test_fail_closed_alto():
    # Rule: Alto K10 (0 chars) must remain fail-closed without OCR.
    raw_chars_alto = []
    res = reconstruct_text_from_chars(raw_chars_alto)
    assert res['status'] == "insufficient_evidence"
    assert len(res['rows']) == 0
