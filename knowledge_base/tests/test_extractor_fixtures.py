import pytest
import os
import json
from knowledge_base.ingestion.source_91wheels.extractor_91wheels import extract_all

@pytest.fixture
def creta_html():
    fixture_path = os.path.join(os.path.dirname(__file__), 'fixtures', 'creta_rsc_payload.html')
    if not os.path.exists(fixture_path):
        pytest.skip("Fixture not found")
    with open(fixture_path, 'r') as f:
        return f.read()

def test_extract_all_diagnostics(creta_html):
    res = extract_all(creta_html)
    assert res['status'] in ['SUCCESS_COMPLETE', 'SUCCESS_PARTIAL']
    assert len(res['variants']) > 0
    assert 'v_variant_id' in res['variants'][0]
    
    assert len(res['v_specs_blocks']) >= 2
    for b in res['v_specs_blocks']:
        assert b['v_variant_id'] is not None
        total_fields = sum(len(cat) for cat in b['v_specs'].values() if isinstance(cat, dict))
        assert total_fields >= 20

def test_extract_all_missing_payload():
    res = extract_all("<html><body>No payload here</body></html>")
    assert res['status'] == 'NO_PAYLOAD'
    assert len(res['variants']) == 0

def test_extract_all_no_container():
    html = '<html><script>self.__next_f.push([1,"junk data without valid arrays"])</script></html>'
    res = extract_all(html)
    assert res['status'] == 'NO_CONTAINER'
