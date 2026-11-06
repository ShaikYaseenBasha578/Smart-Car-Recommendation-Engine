"""Phase 10I resolver fix. Runs entirely on in-memory DBs, by explicit path only (see CLAUDE.md).
The fixture holds every aggregator observation resolved in 2026, labelled by the blind-validated 10H classification."""
import json, os, sqlite3
import pytest
from knowledge_base.ingestion.carwale import ingest_carwale
from knowledge_base.ingestion.carwale.ingest_carwale import resolve_carwale_version, served_page_matches
from knowledge_base.ingestion.common.identity import HELD_VARIANT_IDS, attributes_of, compatible, identity_of, same_identity
from knowledge_base.ingestion.common.resolver import resolve_variant
from knowledge_base.ingestion.common.updater import update_canonical

FX = json.load(open(os.path.join(os.path.dirname(__file__), "fixtures", "resolver_10i_fixture.json")))
CASES = {c["obs"]: c for c in FX["cases"]}
MISLINKED = {"MISLINK_TARGET", "MISLINK_NONE", "EDITION_NOT_IN_KB"}


def build_db():
    c = sqlite3.connect(":memory:"); c.row_factory = sqlite3.Row
    c.executescript("""
      CREATE TABLE source (id INTEGER PRIMARY KEY, name TEXT);
      CREATE TABLE manufacturer (id INTEGER PRIMARY KEY, name TEXT);
      CREATE TABLE model (id INTEGER PRIMARY KEY, manufacturer_id INTEGER, name TEXT);
      CREATE TABLE powertrain (id INTEGER PRIMARY KEY, model_id INTEGER, fuel_type TEXT, engine_cc REAL, power_bhp REAL);
      CREATE TABLE variant (id INTEGER PRIMARY KEY, model_id INTEGER, generation_id INTEGER, powertrain_id INTEGER, name TEXT, transmission TEXT,
                            drivetrain TEXT, price_ex_showroom REAL, base_variant_id INTEGER, is_discontinued INTEGER, boot_space_litres REAL, sunroof INTEGER, edition_classification TEXT);
      CREATE TABLE variant_alias (variant_id INTEGER, source_id INTEGER, alias_name TEXT, needs_review INTEGER, is_verified INTEGER);
      CREATE TABLE source_observation (id INTEGER PRIMARY KEY, source_id INTEGER, raw_name TEXT, raw_payload TEXT, source_url TEXT, extraction_method TEXT, resolved_variant_id INTEGER, resolution_status TEXT);
      CREATE TABLE field_provenance (id INTEGER PRIMARY KEY, variant_id INTEGER, field_name TEXT, accepted_value TEXT, source_observation_id INTEGER, decision TEXT, decision_reason TEXT, decided_at TEXT);""")
    for t in ("source", "manufacturer", "model", "powertrain", "variant_alias"):
        for r in FX[t]:
            c.execute(f'insert into {t} values ({",".join("?" * len(r))})', r)
    for r in FX["variant"]:
        c.execute("insert into variant (id,model_id,generation_id,powertrain_id,name,transmission,drivetrain,price_ex_showroom,base_variant_id,is_discontinued) values (?,?,?,?,?,?,?,?,?,?)", r)
    c.commit()
    return c


@pytest.fixture(scope="module")
def db():
    return build_db()


def replay(db, c):
    if c["src"] == "carwale":
        if not served_page_matches(c["name"], c.get("served")):
            return None
        return resolve_carwale_version(db, c["make"], c["model"], c["name"], c["slug"])
    return resolve_variant(db, c["make"], c["model"], c["name"], c["slug"], c["fuel"], c["trans"], c["cc"], c["price"], source_name=c["src"])


def test_no_mislink_keeps_its_old_variant(db):
    bad = [c["obs"] for c in FX["cases"] if c["cls"] in MISLINKED and (r := replay(db, c)) is not None and r[0] == c["linked"]]
    assert bad == []


def test_auto_accept_is_only_identity_exact_and_never_held(db):
    for c in FX["cases"]:
        r = replay(db, c)
        if r is None: continue
        assert (r[0] is not None) == (r.match_type == "identity_exact"), c["obs"]
        assert r[0] not in HELD_VARIANT_IDS, c["obs"]


@pytest.mark.parametrize("obs,target", [(1151, 693), (1157, 694), (955, 191)])
def test_owner_regressions_relink_correctly(db, obs, target):
    r = replay(db, CASES[obs])
    assert r[0] == target and r.match_type == "identity_exact"


def test_dual_tone_creta_15_16(db):
    # the source says DT -> the DT variant; the source is silent -> the base (owner decision 2)
    dt = resolve_variant(db, "hyundai", "creta", "CretaSX Premium Dual Tone1.5L  Petrol Manual", "", "Petrol", "Manual", None, None)
    plain = resolve_variant(db, "hyundai", "creta", "CretaSX Premium1.5L  Petrol Manual", "", "Petrol", "Manual", None, None)
    assert dt[0] == 16 and plain[0] == 15


def test_dual_tone_does_not_settle_an_unstated_gearbox(db):
    r = replay(db, CASES[1101])  # 'HX8 Turbo GDi DT': manual DT edition exists, but so does a DCT
    assert r[0] is None and r.match_type == "ambiguous"


def test_held_edition_1248_goes_to_review(db):
    r = replay(db, CASES[1248])  # 'ZXi DT': never auto-linked to held edition 821
    assert r[0] is None and r[1] == "needs_review"
    held = resolve_variant(db, "maruti-suzuki", "brezza", "ZXi DT Manual", "", "Petrol", "Manual", None, None)
    assert held[0] is None and held.match_type == "held_edition" and held.suggested_variant_id == 821


def test_unclear_3302_is_not_auto_accepted(db):
    assert replay(db, CASES[3302])[0] is None


def test_kia_a_is_adas_not_automatic():
    kb, src = identity_of("GTX(A) 1.5 Petrol IVT", "Seltos"), identity_of("GTX Petrol 1.5L Automatic (CVT)", "Seltos")
    assert not same_identity(kb, src, "Seltos", True)


def test_tata_a_means_automatic():
    kb, src = identity_of("Pure+ A CNG AMT", "Tiago"), identity_of("TiagoPure Plus1.2L CNG Automatic", "Tiago")
    assert same_identity(kb, src, "Tiago", True)


def test_trailing_edition_words_count():
    assert identity_of("Pure X Petrol 1.5L Turbo Manual Dark Edition", "Harrier").editions == {"dark"}


def test_drivetrain_and_gearbox_kind_are_hard_filters():
    row = {"fuel_type": "Diesel", "transmission": "Torque Converter", "engine_cc": 2184.0, "drivetrain": "RWD"}
    class R(dict):
        keys = dict.keys
    assert not compatible(R(row), attributes_of("AX7L Diesel 4WD AT (TC)"))
    assert compatible(R(row), attributes_of("AX7L Diesel 2WD AT (TC)"))
    assert not compatible(R(row), attributes_of("AX7L Diesel 2WD AT (DCT)"))


def test_carwale_page_check():
    assert served_page_matches("V Petrol Manual", " v  petrol manual")
    assert not served_page_matches("V Petrol Automatic", "V Petrol Manual")
    assert not served_page_matches("", "")


def test_carwale_mismatched_page_writes_nothing(monkeypatch, tmp_path):
    path = tmp_path / "kb.db"
    disk = sqlite3.connect(path); mem = build_db(); mem.backup(disk); disk.close()
    versions = [{"versionName": "HX 6 Petrol Automatic", "versionMaskingName": "hx-6-petrol-automatic", "priceOverview": {"price": 855000}},
                {"versionName": "HX 2 Petrol Manual", "versionMaskingName": "hx-2-petrol-manual", "priceOverview": {"price": 580000}}]
    monkeypatch.setattr(ingest_carwale, "fetch_carwale_state", lambda url: {"modelPage": {"versions": versions}})
    served = {"hx-6-petrol-automatic": "HX 6 Petrol Manual", "hx-2-petrol-manual": "HX 2 Petrol Manual"}  # the first page is the wrong one
    monkeypatch.setattr(ingest_carwale, "extract_variant", lambda url: ({"v_variant_name": served[url.rstrip("/").split("/")[-1]], "ex_showroom_price": 1, "features": {"Fuel Type": "Petrol"}}, "SUCCESS"))
    monkeypatch.setattr(ingest_carwale, "ensure_source_registered", lambda conn: None)
    monkeypatch.setattr(ingest_carwale.time, "sleep", lambda s: None)
    ingest_carwale.ingest_model_pilot("hyundai", "exter", "exter", str(path))
    c = sqlite3.connect(path)
    rows = dict(c.execute("select raw_name, resolution_status from source_observation").fetchall())
    assert rows == {"HX 6 Petrol Automatic": "page_mismatch", "HX 2 Petrol Manual": "resolved"}
    assert c.execute("select resolved_variant_id from source_observation where raw_name='HX 6 Petrol Automatic'").fetchone()[0] is None


def _obs(conn):
    return conn.execute("select resolved_variant_id, resolution_status from source_observation order by id desc limit 1").fetchone()


def test_updater_never_creates_a_variant_for_an_edition():
    c = build_db(); n = c.execute("select count(*) from variant").fetchone()[0]
    update_canonical(c, None, 2, "u", "HX 6 Knight", {}, "edition_candidate", {"sunroof": 1}, base_variant_id=665, match_type="edition_candidate")
    assert c.execute("select count(*) from variant").fetchone()[0] == n
    assert tuple(_obs(c)) == (None, "edition_candidate")
    assert c.execute("select count(*) from field_provenance").fetchone()[0] == 0


@pytest.mark.parametrize("status,match", [("needs_review", "fuzzy"), ("resolved_with_warning", "alias"), ("resolved", None), ("resolved", "fuzzy")])
def test_updater_gate_blocks_everything_but_identity_exact(status, match):
    c = build_db()
    obs, updates = update_canonical(c, 1, 2, "u", "x", {}, status, {"boot_space_litres": 433.0}, match_type=match)
    assert updates == 0 and c.execute("select count(*) from field_provenance").fetchone()[0] == 0


def test_aggregator_only_corroborates_P2():
    c = build_db()
    _, updates = update_canonical(c, 1, 2, "u", "x", {}, "resolved", {"boot_space_litres": 433.0}, match_type="identity_exact")
    assert updates == 0
    assert c.execute("select boot_space_litres from variant where id=1").fetchone()[0] is None
    assert tuple(c.execute("select decision, decision_reason from field_provenance").fetchone()) == ("pending", "aggregator_corroborates_only_P2")


def test_oem_writes_a_base_variant_but_never_an_edition_P8():
    c = build_db(); oem = c.execute("select id from source where name='oem'").fetchone()[0]
    _, updates = update_canonical(c, 1, oem, "u", "x", {}, "resolved", {"boot_space_litres": 433.0}, match_type="identity_exact")
    assert updates == 1 and c.execute("select boot_space_litres from variant where id=1").fetchone()[0] == 433.0
    _, updates = update_canonical(c, 833, oem, "u2", "y", {}, "resolved", {"boot_space_litres": 433.0}, match_type="identity_exact")
    assert updates == 0 and c.execute("select boot_space_litres from variant where id=833").fetchone()[0] is None


def test_ingest_91wheels_imports_and_runs(monkeypatch):
    """It used to fail at import (relative imports of moved modules), then at unpacking 2 of 3 resolver values."""
    from knowledge_base.ingestion.source_91wheels import ingest_91wheels as w
    monkeypatch.setattr(w, "fetch_model_page", lambda make, model: ("<html>", 200, "https://x"))
    monkeypatch.setattr(w, "extract_all", lambda html: {"status": "OK", "v_specs_blocks": [], "variants": [
        {"v_variant_id": 1, "v_variant_name": "HX 2 Petrol Manual", "v_variant_slug": "hx-2-petrol-manual", "v_variant_fuel_type": "Petrol", "variant_price": {}, "specs": {}}]})
    c = build_db()
    res = w.ingest_model(c, "hyundai", "exter")
    assert res["observations"] == 1 and res["resolved"] == 1
    assert tuple(_obs(c)) == (656, "resolved")
