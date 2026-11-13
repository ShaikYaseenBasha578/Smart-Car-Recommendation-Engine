import json
import os
import re
import sqlite3

import fitz
import pytest

from kbpipe import brochure, llm, plan
from kbpipe import fields as F
from kbpipe.tests.conftest import make_kb

SPEC = ("Tata Nexon specifications Smart Creative dimensions wheelbase 2498 mm airbags kerb weight fuel tank boot "
        "power kW torque Nm sunroof cruise control mileage ARAI km/l ground clearance")
FEAT = "Tata Nexon features Smart Creative trim sunroof airbags cruise control climate camera android carplay"


def make_pdf(path, pages):
    d = fitz.open()
    for t in pages:
        pg = d.new_page()
        pg.insert_textbox(fitz.Rect(30, 30, 560, 800), t, fontsize=10)
    d.save(path)
    d.close()
    return path


class Mock:
    """Mock LLM. `script(read_no, prompt)` returns the cells list for the reply."""
    def __init__(self, script):
        self.script, self.n = script, 0

    def __call__(self, prompt, images):
        self.n += 1
        read = int(re.search(r"Read number (\d+)\.", prompt).group(1))
        return json.dumps({"page_columns": [], "cells": self.script(read, prompt)})

    def chain(self):
        b = llm.Backend("mock", {"kind": "mock", "model": "mockm"})
        b.mock = self
        return llm.Chain([b])


def cell(field, value, unit, variants, source="line"):
    return {"field": field, "value": value, "unit": unit, "qualifier": "", "source": source, "variants": variants}


ALL = ["Smart Petrol Manual", "Creative Petrol Automatic"]


@pytest.fixture
def env(tmp_path, cfg, kbfile):
    root = tmp_path / "repo"
    oem = root / "knowledge_base" / "sources" / "oem"
    oem.mkdir(parents=True)
    pdf = make_pdf(str(oem / "nexon.pdf"), ["Welcome to the Nexon story. Drive.", SPEC, FEAT])
    rel = os.path.relpath(pdf, str(root))
    man = {"Tata_Nexon": {"model_id": 1, "artifact_path": rel, "sha256": brochure._sha(pdf, "sha256")}}
    (oem / "brochure_manifest.json").write_text(json.dumps(man))
    cfg.update(oem_dir=str(oem), oem_new_dir=str(root / "knowledge_base" / "sources" / "oem_kbpipe"))
    cfg["brochure"] = {"enabled": True, "index_dir": str(tmp_path / "noindex")}
    conn = sqlite3.connect(kbfile)
    conn.row_factory = sqlite3.Row
    item = {"make": "Tata", "model": "Nexon", "in_kb": True, "kb_model_id": 1, "key": "nexon"}

    def bundle(names=ALL):
        vs = []
        for n in names:
            gear = "Manual" if "Manual" in n else "AMT"
            vs.append({"name": n, "special": False, "fields_cw": {"fuel_type": "Petrol", "transmission": gear, "price_ex_showroom": 800000},
                       "fields_cd": None, "obs_cw": {}, "obs_cd": None})
        return {"versions": vs, "problems": [], "brochure": None}
    return {"cfg": cfg, "conn": conn, "item": item, "bundle": bundle, "pdf": pdf, "tmp": tmp_path, "root": root}


def run(env, script, name="r1", bundle=None, chain=None):
    m = Mock(script)
    b = bundle or env["bundle"]()
    logs = []
    rd = str(env["tmp"] / name)
    os.makedirs(rd, exist_ok=True)
    s = brochure.enrich(env["item"], b, env["conn"], env["cfg"], None, lambda *a: logs.append(" ".join(map(str, a))), rd, chain=m.chain())
    return s, b, m, logs


def attached(b):
    return {(v["name"], x["field"]): x for v in b["versions"] for x in v["brochure"]}


def test_page_finder_picks_spec_page(env):
    texts = brochure.page_texts(env["pdf"], "x", env["cfg"])
    vinfo = [{"name": n, "fuel": "Petrol", "transmission": "Manual"} for n in ALL]
    pages, scores = brochure.find_pages(texts, vinfo, "Nexon", 6, 5)
    assert pages == [2, 3]
    assert scores[1] == 0 and scores[2] > scores[3]
    assert brochure.find_pages(texts, vinfo, "Nexon", 1, 5)[0] == [2]


def test_two_reads_must_agree(env):
    def script(read, prompt):
        air = 6 if read == 1 else 4                      # reads disagree on airbags, agree on wheelbase
        return [cell("wheelbase_mm", 2498, "mm", ALL), cell("airbags", air, "count", [ALL[0]]),
                cell("sunroof", 1, "bool", [ALL[1]]) if read == 1 else cell("abs", 1, "bool", ALL)]   # one-sided cells
    s, b, m, _ = run(env, script)
    a = attached(b)
    assert (ALL[0], "wheelbase_mm") in a and (ALL[1], "wheelbase_mm") in a
    assert (ALL[0], "airbags") not in a
    assert not any(k[1] in ("sunroof", "abs") for k in a)
    assert s["cells_dropped_disagree"] >= 1 and s["cells_dropped_single_read"] >= 1
    assert m.n == 2 * s["pages_read"]


def test_units_kw_and_ps():
    assert brochure.to_value("power_bhp", 110, "kW") == (147.51, None)
    assert brochure.to_value("power_bhp", 100, "PS") == (98.63, None)
    assert brochure.to_value("power_bhp", 120, "bhp") == (120.0, None)
    assert brochure.to_value("power_bhp", 120, "hp")[0] is None
    assert brochure.to_value("mileage_arai_kmpl", 20, "km/kg")[0] is None      # km/l and km/kg are never mixed
    assert brochure.to_value("mileage_arai_km_per_kg", 26.5, "km/kg") == (26.5, None)


def test_unit_conversion_reaches_the_cell(env):
    s, b, _, _ = run(env, lambda r, p: [cell("power_bhp", 110, "kW", ALL)])
    assert attached(b)[(ALL[0], "power_bhp")]["value"] == 147.51


def test_unknown_variant_names_dropped(env):
    s, b, _, _ = run(env, lambda r, p: [cell("wheelbase_mm", 2498, "mm", ALL + ["Fearless Plus"])])
    assert {k[0] for k in attached(b)} == set(ALL)
    assert s["drops"].get("variant not in the bundle", 0) >= 1


def test_cells_already_brochure_backed_are_skipped(env):
    c = env["conn"]
    c.execute("insert into source_observation(id,source_id,raw_name,source_url,extraction_method,resolved_variant_id) values (900,6,'Smart','file:x','brochure',1)")
    c.execute("insert into field_provenance(variant_id,field_name,accepted_value,source_observation_id,decision) values (1,'wheelbase_mm','2498',900,'accepted')")
    # an aggregator-backed cell is NOT brochure-backed and must not be skipped
    c.execute("insert into source_observation(id,source_id,raw_name,source_url,extraction_method,resolved_variant_id) values (901,4,'Smart','u','json',1)")
    c.execute("insert into field_provenance(variant_id,field_name,accepted_value,source_observation_id,decision) values (1,'airbags','6',901,'accepted')")
    s, b, _, _ = run(env, lambda r, p: [cell("wheelbase_mm", 2498, "mm", ALL), cell("airbags", 6, "count", ALL)])
    a = attached(b)
    assert (ALL[0], "wheelbase_mm") not in a and (ALL[1], "wheelbase_mm") in a
    assert (ALL[0], "airbags") in a
    assert s["cells_skipped_existing"] == 1
    assert [x for x in s["cells"] if x["kb_has_brochure_value"]][0]["field"] == "wheelbase_mm"


def test_wrong_year_guard_text(env):
    make_pdf(env["pdf"] + ".new", ["Tata Nexon specifications Alpha Beta Gamma dimensions wheelbase airbags kerb weight fuel tank boot power torque"])
    os.replace(env["pdf"] + ".new", env["pdf"])
    man = os.path.join(env["cfg"]["oem_dir"], "brochure_manifest.json")
    m = json.load(open(man))
    m["Tata_Nexon"]["sha256"] = brochure._sha(env["pdf"], "sha256")
    json.dump(m, open(man, "w"))
    s, b, mock, logs = run(env, lambda r, p: [cell("wheelbase_mm", 2498, "mm", ALL)])
    assert mock.n == 0 and not attached(b)
    assert any("does not match the current listing" in l for l in logs)


def test_wrong_year_guard_after_reads(env):
    # the page text names the trims, but the reads place the values on at most one of the two catalogue variants -> still fine
    # (1 of 2 = 50%); a brochure whose reads name none of the variants is dropped
    s, b, _, logs = run(env, lambda r, p: [cell("wheelbase_mm", 2498, "mm", ["Nope"])])
    assert not attached(b) and any("does not match the current listing" in l for l in logs)


def test_observation_keys_do_not_collide_across_pages(env):
    def script(read, prompt):
        if "FEATURES" in prompt.upper() and "sunroof cruise control climate" in prompt:
            return [cell("sunroof", 1, "bool", [ALL[1]]), cell("airbags", 6, "count", ALL)]
        return [cell("wheelbase_mm", 2498, "mm", ALL), cell("airbags", 6, "count", ALL)]
    s, b, _, _ = run(env, script)
    obs = [x["obs"] for v in b["versions"] for x in v["brochure"] if v["name"] == ALL[1]]
    keys = {plan.okey(o) for o in obs}
    assert len({(o["url"]) for o in obs}) == len({o["payload"]["page"] for o in obs}) >= 2
    assert len(keys) == len({o["payload"]["page"] for o in obs})
    # same url and name but a different page in the payload still gives a different key
    o1 = dict(obs[0]); o2 = dict(o1, payload=dict(o1["payload"], page=o1["payload"]["page"] + 5))
    assert plan.okey(o1) != plan.okey(o2)
    assert all("#page=" in o["url"] and o["url"].startswith("file:sources/oem/") for o in obs)
    assert obs[0]["payload"]["pdf_path"].startswith("knowledge_base/sources/oem/") and len(obs[0]["payload"]["pdf_sha1"]) == 40


def test_read_cache_prevents_second_llm_call(env):
    script = lambda r, p: [cell("wheelbase_mm", 2498, "mm", ALL)]
    s1, b1, m1, _ = run(env, script, name="r1")
    assert m1.n > 0
    s2, b2, m2, _ = run(env, script, name="r2")
    assert m2.n == 0 and attached(b2).keys() == attached(b1).keys()


def test_budget_stops_reading(env):
    env["cfg"]["brochure"]["max_page_reads_per_run"] = 1
    s, b, m, logs = run(env, lambda r, p: [cell("wheelbase_mm", 2498, "mm", ALL)])
    assert m.n == 1 and not attached(b) and any("budget" in l for l in logs)


def test_disabled_and_editions(env):
    env["cfg"]["brochure"]["enabled"] = False
    s, b, m, _ = run(env, lambda r, p: [])
    assert s["status"] == "disabled" and m.n == 0
    env["cfg"]["brochure"]["enabled"] = True
    bb = env["bundle"]()
    bb["versions"][1]["special"] = True
    s, b, m, _ = run(env, lambda r, p: [cell("wheelbase_mm", 2498, "mm", ALL)], name="r3", bundle=bb)
    assert {k[0] for k in attached(b)} == {ALL[0]}


def test_new_model_download_and_name_check(env, tmp_path):
    pdf_bytes = open(make_pdf(str(tmp_path / "p.pdf"), ["Tata Punch specifications Smart Creative wheelbase airbags kerb weight fuel tank boot power torque dimensions"]), "rb").read()
    other = open(make_pdf(str(tmp_path / "o.pdf"), ["Tata Harrier specifications Smart Creative wheelbase airbags"]), "rb").read()

    class Fetch:
        def __init__(self, body): self.body, self.urls = body, []
        def get(self, url, max_age_days=None, binary=False):
            self.urls.append(url)
            return self.body, {"fetched_at": "2026-11-13T00:00:00Z"}
    item = {"make": "Tata", "model": "Punch", "in_kb": False, "kb_model_id": None, "key": "punch"}
    b = env["bundle"]()
    b["brochure"] = "f/brochure/16/3135/x.pdf"
    m = Mock(lambda r, p: [cell("wheelbase_mm", 2445, "mm", ALL)])
    f = Fetch(pdf_bytes)
    s = brochure.enrich(item, b, env["conn"], env["cfg"], f, lambda *a: None, str(tmp_path / "n1"), chain=m.chain())
    assert f.urls == ["https://stc.aeplcdn.com/f/brochure/16/3135/x.pdf"]
    man = json.load(open(os.path.join(env["cfg"]["oem_new_dir"], "brochure_manifest.json")))
    assert man["Tata/Punch"]["bytes"] == len(pdf_bytes) and os.path.exists(os.path.join(env["cfg"]["oem_new_dir"], "tata", "punch", man["Tata/Punch"]["sha1"] + ".pdf"))
    o = attached(b)[(ALL[0], "wheelbase_mm")]["obs"]
    assert o["url"].startswith("https://stc.aeplcdn.com/") and o["url"].endswith("#page=1") and "oem_kbpipe" in o["payload"]["pdf_path"]
    # a PDF that does not name the model is skipped
    b2 = env["bundle"]()
    b2["brochure"] = "f/other.pdf"
    logs = []
    brochure.enrich(item, b2, env["conn"], env["cfg"], Fetch(other), lambda *a: logs.append(a), str(tmp_path / "n2"), chain=m.chain())
    assert not attached(b2) and any("does not mention the model" in " ".join(l) for l in logs)
