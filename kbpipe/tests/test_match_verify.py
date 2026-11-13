import ast
import json
import os

from kbpipe import llm, match, verify


def test_link_needs_equal_identity_not_overlap():
    kb = [{"name": "Adventure Petrol Manual", "fuel": "Petrol", "transmission": "Manual", "price": 776990},
          {"name": "Adventure (S) Petrol Manual", "fuel": "Petrol", "transmission": "Manual", "price": 811990}]
    hit, _ = match.link({"name": "Adventure Plus Petrol Manual", "fuel": "Petrol", "transmission": "Manual", "price": 800000}, kb, "Tata Punch")
    assert hit is None                                           # shares "adventure" with both; equal to neither
    hit, _ = match.link({"name": "Punch Adventure S", "fuel": "Petrol", "transmission": "Manual", "price": 811990}, kb, "Tata Punch")
    assert hit is kb[1]


def test_same_identity_twice_is_settled_only_by_exact_price():
    pool = [{"name": "Punch Adventure", "fuel": "Petrol", "transmission": "Manual", "price": 776990},
            {"name": "Punch Adventure Turbo", "fuel": "Petrol", "transmission": "Manual", "price": 846990}]
    t = {"name": "Adventure Petrol Turbo 6 Speed Manual", "fuel": "Petrol", "transmission": "Manual", "price": 846990}
    assert match.link(t, pool, "Tata Punch", need_price=True)[0] is pool[1]
    assert match.link(dict(t, price=800000), pool, "Tata Punch", need_price=True)[0] is None


def test_fuel_and_gearbox_must_agree():
    pool = [{"name": "Punch Pure CNG", "fuel": "CNG", "transmission": "Manual", "price": 767990}]
    assert match.link({"name": "Pure Petrol Manual", "fuel": "Petrol", "transmission": "Manual", "price": 767990}, pool, "Tata Punch")[0] is None
    assert match.link({"name": "Pure CNG Automatic", "fuel": "CNG", "transmission": "AMT", "price": 767990}, pool, "Tata Punch")[0] is None


def test_verifier_imports_nothing_from_extraction():
    src = open(os.path.join(os.path.dirname(verify.__file__), "verify.py")).read()
    names = set()
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, ast.ImportFrom):
            names |= {a.name for a in node.names} | ({node.module} if node.module else set())
        elif isinstance(node, ast.Import):
            names |= {a.name for a in node.names}
    assert not names & {"extract", "plan", "reconcile", "match", "discover", "sources", "carwale", "cardekho", "common", "pipeline"}
    assert "extraction_method" not in verify.PROMPT and "reason" not in verify.PROMPT


PAGE = '<script id="initial-state" type="application/json">%s</script>' % json.dumps({"modelPage": {"versions": [
    {"versionId": 7, "versionName": "Pure Petrol Manual", "specsSummary": [{"itemName": "Fuel Type", "value": "Petrol", "unitType": ""}],
     "featureSpecs": [{"itemName": "Airbags", "value": "6"}, {"itemName": "Cruise Control", "value": "No"},
                      {"itemName": "Sunroof Type", "value": "No"}, {"itemName": "Seating Capacity", "value": "5"}]},
    {"versionId": 8, "versionName": "Other", "specsSummary": [], "featureSpecs": [{"itemName": "Airbags", "value": "2"}]}]}})


class F:
    def get(self, url, max_age_days=None, binary=False):
        return (PAGE, {"fetched_at": "x", "sha256": "y"}) if "ok" in url else (None, None)


def cell(url="https://ok/punch/#vid=7"):
    return {"variant_id": 1, "field_name": "airbags", "full_name": "Tata Punch Pure Petrol Manual", "value": 6, "group": "safety",
            "cls": "aggregator", "source": "carwale", "source_url": url, "raw_payload": "{}"}


def backend(reply):
    verify._MEMO.clear()
    b = llm.Backend("mock", {"kind": "mock"})
    seen = {}
    def mock(prompt, images):
        seen["prompt"] = prompt
        return json.dumps(reply)
    b.mock = mock
    return {"text": b, "image": b}, seen


def test_verifier_sees_only_the_variants_own_source_lines(cfg):
    be, seen = backend({"verdict": "match", "source_value": "6", "evidence": "Airbags: 6"})
    r = verify.check_cell(cell(), cfg, F(), be)
    assert r["verdict"] == "match"
    assert "Airbags: 6" in seen["prompt"] and "Airbags: 2" not in seen["prompt"]        # the other version is not shown


def test_evidence_must_be_in_the_source(cfg):
    be, _ = backend({"verdict": "match", "source_value": "6", "evidence": "Airbags: six, trust me"})
    assert verify.check_cell(cell(), cfg, F(), be)["verdict"] == "verifier_error"


def test_unreachable_source_and_missing_version(cfg):
    be, _ = backend({"verdict": "match", "evidence": "Airbags: 6"})
    assert verify.check_cell(cell("https://down/punch/#vid=7"), cfg, F(), be)["verdict"] == "unreachable"
    assert verify.check_cell(cell("https://ok/punch/#vid=99"), cfg, F(), be)["verdict"] == "unreachable"


def test_results_file_is_append_only_read_only_and_drives_the_numbers(cfg, tmp_path):
    be, _ = backend({"verdict": "mismatch", "source_value": "6", "evidence": "Airbags: 6"})
    out = str(tmp_path / "verify")
    verify.run([cell()], cfg, F(), be, out, lambda *a: None, batch="b1")
    verify.run([cell()], cfg, F(), be, out, lambda *a: None, batch="b2")                # same cell again: not re-judged
    rows = verify.load(out)
    assert len(rows) == 1 and not os.access(os.path.join(out, "results.jsonl"), os.W_OK)
    s = verify.summarise(rows)
    assert s["overall"]["accuracy"] == 0.0 and s["by_group"]["safety"]["mismatch"] == 1
