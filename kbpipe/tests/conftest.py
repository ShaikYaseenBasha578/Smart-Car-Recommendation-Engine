import json
import os
import sqlite3
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
from kbpipe import config  # noqa: E402


def make_kb(path):
    """A tiny KB with the real schema (KB_SCHEMA.sql) and two variants of one model."""
    c = sqlite3.connect(path)
    with open(os.path.join(ROOT, "KB_SCHEMA.sql")) as f:
        c.executescript(f.read())
    c.executescript("""
    insert into source(id,name,source_type,authority_tier) values (1,'v6_migration','migration',2),(4,'carwale','aggregator',3),
      (5,'cardekho','aggregator',3),(6,'oem','oem',1);
    insert into manufacturer(id,name) values (1,'Tata');
    insert into model(id,manufacturer_id,name,body_type) values (1,1,'Nexon','SUV');
    insert into generation(id,model_id,name) values (1,1,'Gen 1 (V6 Import)');
    insert into powertrain(id,model_id,fuel_type,engine_cc,power_bhp,torque_nm,description) values (1,1,'Petrol',1199,118,170,'x');
    insert into variant(id,model_id,generation_id,powertrain_id,name,full_name,transmission,drivetrain,price_ex_showroom,airbags,sunroof)
      values (1,1,1,1,'Smart Petrol Manual','Tata Nexon Smart Petrol Manual','Manual','FWD',800000,6,'False'),
             (2,1,1,1,'Creative Petrol Automatic','Tata Nexon Creative Petrol Automatic','AMT','FWD',1100000,6,'True');
    """)
    c.commit()
    c.close()
    return path


@pytest.fixture
def cfg(tmp_path):
    c = config.load(path=str(tmp_path / "none.json"))
    c.update(cache_dir=str(tmp_path / "cache"), runs_dir=str(tmp_path / "runs"), history_repo=str(tmp_path / "hist"),
             backup_dir=str(tmp_path / "backups"), prod_db=str(tmp_path / "kb.db"), changelog=str(tmp_path / "CHANGELOG.md"),
             min_seconds_between_requests=0)
    return c


@pytest.fixture
def kbfile(tmp_path):
    return make_kb(str(tmp_path / "kb.db"))


def obs(source, url, name, payload=None):
    return {"source": source, "raw_name": name, "url": url, "observed_at": "2026-11-13T00:00:00Z",
            "method": "kbpipe/1.0 test", "payload": payload or {"k": name}}


def good_changeset():
    o = {"a": obs("carwale", "https://cw/punch#vid=1", "Pure Petrol Manual"), "b": obs("cardekho", "https://cd/punch-pure", "Punch Pure")}
    ev = lambda v: [{"obs": "a", "decision": "accepted", "value": v}, {"obs": "b", "decision": "confirmed", "value": v}]
    cell = lambda f, v, exp=None: {"op": "cell", "make": "Tata", "model": "Punch", "variant": "Pure Petrol Manual", "field": f,
                                   "value": v, "expect_old": exp, "reason": "AGGREGATOR_AGREED_UNVERIFIED", "evidence": ev(v)}
    return {"run": "test", "ts": "2026-11-13 00:00:00", "observations": o, "ops": [
        {"op": "add_model", "make": "Tata", "model": "Punch", "body_type": "SUV", "note": "t"},
        {"op": "add_variant", "make": "Tata", "model": "Punch", "name": "Pure Petrol Manual", "full_name": "Tata Punch Pure Petrol Manual",
         "transmission": "Manual", "drivetrain": "FWD", "powertrain": {"fuel_type": "Petrol", "engine_cc": 1199, "power_bhp": 87.0, "torque_nm": 115.0}},
        cell("fuel_type", "Petrol"), cell("transmission", "Manual", "Manual"), cell("drivetrain", "FWD", "FWD"), cell("engine_cc", 1199),
        cell("power_bhp", 87.0), cell("torque_nm", 115.0), cell("price_ex_showroom", 664990), cell("airbags", 6), cell("sunroof", 0),
    ]}
