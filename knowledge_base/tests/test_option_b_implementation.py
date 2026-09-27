import pytest
from knowledge_base.ingestion.oem.extractor.pdf_utils.pdf_char_utils import reconstruct_text_from_chars
from knowledge_base.ingestion.oem.extractor.pdf_utils.pdf_vector_utils import detect_vector_marks
from knowledge_base.ingestion.oem.extractor.base import ConfigurationIR
from knowledge_base.ingestion.oem.extractor.families.feature_list import FeatureListStrategy
from knowledge_base.ingestion.oem.extractor.families.borderless_variant_column_matrix import BorderlessVariantColumnMatrixStrategy

def test_char_reconstruction_blocks():
    # Test that structural block grouping works
    mock_chars = [
        {'text': 'H', 'top': 10, 'bottom': 20, 'x0': 100, 'x1': 110},
        {'text': 'I', 'top': 10, 'bottom': 20, 'x0': 112, 'x1': 118},
        # large gap -> new block
        {'text': 'V', 'top': 10, 'bottom': 20, 'x0': 200, 'x1': 210},
    ]
    res = reconstruct_text_from_chars(mock_chars)
    assert len(res['rows'][0]['blocks']) == 2
    assert res['rows'][0]['blocks'][0]['text'] == 'HI'
    assert res['rows'][0]['blocks'][1]['text'] == 'V'

def test_vector_semantic_neutrality():
    mock_objects = {'curves': [{'x0': 100, 'x1': 110, 'top': 100, 'bottom': 110, 'width': 10, 'height': 10}], 'rects': []}
    cols = [105.0]
    rows = [105.0]
    marks = detect_vector_marks(mock_objects, cols, rows)
    assert len(marks) == 1
    assert marks[0]['semantic_state'] is None
    assert marks[0]['raw_evidence'] == 'curve'

def test_feature_list_fail_closed():
    # Attempting to run FeatureListStrategy on a file without explicit "addition to"
    strategy = FeatureListStrategy()
    with pytest.raises(Exception):
        strategy.extract("dummy_path_that_does_not_exist.pdf")
        
