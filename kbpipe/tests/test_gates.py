import shutil
import sqlite3

import pytest

from kbpipe import changeset, gates, kb
from kbpipe.tests.conftest import good_changeset


def staged(kbfile, tmp_path, cs=None):
    after = str(tmp_path / "staged.db")
    shutil.copyfile(kbfile, after)
    log = changeset.apply(after, cs or good_changeset())
    return after, log


def test_good_changeset_passes_every_gate_and_is_idempotent(kbfile, tmp_path, cfg):
    after, log = staged(kbfile, tmp_path)
    ok, res = gates.run_all(kbfile, after, log, cfg)
    assert ok, res
    assert changeset.apply(after, good_changeset()) == []                  # second apply changes nothing
    c = sqlite3.connect(after)
    assert c.execute("select count(*) from variant").fetchone()[0] == 3
    assert c.execute("select sunroof, price_ex_showroom from variant where name='Pure Petrol Manual'").fetchone() == ("False", 664990.0)


def test_schema_gate_fails_on_ddl(kbfile, tmp_path, cfg):
    after, log = staged(kbfile, tmp_path)
    c = sqlite3.connect(after); c.execute("create table extra(x)"); c.commit(); c.close()
    assert gates.gate_schema(kbfile, after, cfg)[0] is False


def test_provenance_gate_fails_on_a_value_without_evidence(kbfile, tmp_path, cfg):
    after, log = staged(kbfile, tmp_path)
    c = sqlite3.connect(after); c.execute("update variant set boot_space_litres=366 where name='Pure Petrol Manual'"); c.commit(); c.close()
    ok, detail = gates.gate_provenance(kbfile, after, cfg)
    assert ok is False and "boot_space_litres" in detail[0]


def test_provenance_gate_fails_when_the_observation_has_no_url(kbfile, tmp_path, cfg):
    after, log = staged(kbfile, tmp_path)
    c = sqlite3.connect(after); c.execute("update source_observation set source_url='' where extraction_method like 'kbpipe%'"); c.commit(); c.close()
    assert gates.gate_provenance(kbfile, after, cfg)[0] is False


def test_rows_gate_fails_when_a_row_is_deleted(kbfile, tmp_path, cfg):
    after = str(tmp_path / "after.db")
    shutil.copyfile(kbfile, after)
    c = sqlite3.connect(after); c.execute("delete from variant where id=2"); c.commit(); c.close()
    assert gates.gate_rows(kbfile, after, cfg)[0] is False
    assert gates.gate_explained(kbfile, after, [], cfg)[0] is False        # a removal is never "explained"
    swapped, log = staged(kbfile, tmp_path / "..")                          # one row added, one deleted: the count hides it
    c = sqlite3.connect(swapped); c.execute("delete from variant where id=2"); c.commit(); c.close()
    assert gates.gate_explained(kbfile, swapped, log, cfg)[0] is False


def test_explained_gate_fails_on_an_unlogged_change(kbfile, tmp_path, cfg):
    after, log = staged(kbfile, tmp_path)
    c = sqlite3.connect(after); c.execute("update variant set airbags=2 where id=1"); c.commit(); c.close()
    ok, detail = gates.gate_explained(kbfile, after, log, cfg)
    assert ok is False and "not in the run log" in detail[0]


def test_apply_refuses_to_overwrite_an_unexpected_value(kbfile, tmp_path):
    cs = {"run": "t", "ts": "2026-11-13 00:00:00", "observations": good_changeset()["observations"], "ops": [
        {"op": "cell", "make": "Tata", "model": "Nexon", "variant": "Smart Petrol Manual", "field": "airbags", "value": 2,
         "expect_old": 4, "reason": "X", "evidence": [{"obs": "a", "decision": "accepted", "value": 2}]}]}
    with pytest.raises(changeset.ApplyError):
        changeset.apply(kbfile, cs)
    assert sqlite3.connect(kbfile).execute("select airbags from variant where id=1").fetchone()[0] == 6   # rolled back


def test_apply_rejects_out_of_range_and_unknown_fields(kbfile):
    base = good_changeset()
    for field, value in (("airbags", 40), ("made_up", 1)):
        cs = dict(base, ops=base["ops"][:2] + [dict(base["ops"][-2], field=field, value=value)])
        with pytest.raises(changeset.ApplyError):
            changeset.apply(kbfile, cs)


def test_discontinue_marks_and_never_deletes(kbfile, tmp_path, cfg):
    cs = {"run": "t", "ts": "2026-11-13 00:00:00", "observations": {}, "ops": [
        {"op": "discontinue", "make": "Tata", "model": "Nexon", "variant": "Smart Petrol Manual", "reason": "NOT_IN_CURRENT_LISTING", "evidence": []}]}
    after, log = staged(kbfile, tmp_path, cs)
    c = sqlite3.connect(after)
    assert c.execute("select count(*), sum(is_discontinued) from variant").fetchone() == (2, 1)
    assert gates.gate_rows(kbfile, after, cfg)[0] and gates.gate_explained(kbfile, after, log, cfg)[0]
