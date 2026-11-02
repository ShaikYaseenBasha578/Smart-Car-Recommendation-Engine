"""Phase 10F (KB unit and mislabel corrections): one controlled write covering scope A-C.

Usage: python3 apply_phase10f.py <db_path> [--oem <knowledge_base/sources/oem>]
One BEGIN IMMEDIATE transaction with foreign_keys=ON. No DDL. Every invariant is checked before COMMIT; any
failure rolls back. Idempotent: a re-run on an already-corrected DB makes no change.
--oem: re-hash every cited brochure (read-only) and refuse to run if any SHA-1 differs.

Write mechanism (Phase 10E pattern):
  - corrected cells: UPDATE + one evidence_amendment row each (old, new, reason, phase '10F');
  - provenance for each asserted new value: one OEM source_observation per (brochure, variant) whose raw_payload
    carries the PDF path, PDF SHA-1, page and printed text, plus one field_provenance row (decision 'accepted');
  - contradicting live field_provenance rows: quarantined (never modified).
Scope:
  A PS stored as bhp: 16 powertrains -> power_bhp = brochure kW x 1.34102 (2 dp; PS x 0.98632 where only PS is
    printed), description figure updated; one power_bhp provenance row per base variant (editions share the
    powertrain row and are never written).
  B Victoris 558, 562 km/kg 26.6 -> 27.02 (p16); v6 fp rows 17208, 17338 quarantined (as 556 in 10E).
  C CNG km/kg scan: no further writes. Owner decisions at the checkpoint: WagonR 225 (33.54 vs brochure 33.47) is
    held as CATALOG_CURRENCY; Grand Vitara 548/549 (26.6, no CNG data in its brochure) stay unverified, not
    quarantined.
"""
import hashlib
import json
import os
import sqlite3
import sys
from decimal import ROUND_HALF_UP, Decimal

PHASE = "10F"
OEM_SOURCE_ID = 6
METHOD = "manual_brochure_10F"
FP_REASON = "OEM_BROCHURE_VERIFIED_10F"
KW_TO_HP = Decimal("1.34102")
PS_TO_HP = Decimal("0.98632")
BRO = {  # brochure -> (path under knowledge_base/sources/oem, SHA-1), hashed in 10F step 1
    "fronx": ("maruti_suzuki/fronx/latest/brochures/Fronx_Brochure.pdf", "2c9ad3ada13052599439059a68f466a6f5241e80"),
    "taisor": ("toyota/urban_cruiser_taisor/latest/brochures/toyota_urban_cruiser_taisor_brochure.pdf", "b2afc7a7e17807ccbb8f6986977e3e8facf162dd"),
    "hyryder": ("toyota/urban_cruiser_hyryder/latest/brochures/toyota_urban_cruiser_hyryder_brochure.pdf", "ec7984cef43e032e39ebe70bb496c9477befb5d1"),
    "grand_vitara": ("maruti_suzuki/grand_vitara/latest/brochures/maruti_suzuki_grand_vitara_brochure.pdf", "023ce2e3d22ca4bd3a2cd1a9aded193273482e91"),
    "victoris": ("maruti_suzuki/victoris/latest/brochures/maruti_suzuki_victoris_brochure.pdf", "94f94973736c150efdf2cc5ae6c40845d8e856a3"),
    "s_presso": ("maruti_suzuki/s_presso/latest/brochures/maruti_suzuki_s_presso_brochure.pdf", "76d42865c1c7bae65bd2656bb490cc01c9c8fba0"),
    "alto_k10": ("maruti_suzuki/alto_k10/latest/brochures/maruti_suzuki_alto_k10_brochure.pdf", "2a87ea04a071ffccf7e157916a91dc07e562494d"),
    "duster": ("renault/duster/latest/brochures/renault_duster_brochure.pdf", "10f1f3b6bfbf5e1b73ba22ca498d458f97342a3a"),
}

# ---- A: (pt, model_id, fuel, cc, old_bhp, kW or None, PS or None, brochure, page, printed, base-variant users, editions)
POWERTRAINS = [
    (70, 34, "Petrol", 1197.0, 89.7, "66", None, "taisor", 21, "Max Power: 66 kW(89.73 PS)@100 s-1 (Petrol)",
     (485, 487, 488, 489, 490), ()),
    (71, 34, "CNG", 1197.0, 77.5, "57", None, "taisor", 21, "Max Power: 57 kW(77.5PS) @100 s-1 (CNG)", (486,), ()),
    (72, 34, "Petrol", 998.0, 100.1, "73.6", None, "taisor", 21, "Max Power: 73.6 kW(100.06PS)@91.6 s-1 (1.0L K-Series Turbo)",
     (491, 492, 493, 494), ()),
    (73, 35, "Petrol", 1197.0, 89.7, "66", None, "fronx", 19, "Max Power: 66 kW@6000rpm or 89.73 PS@6000rpm (1.2 L K-Series Petrol)",
     (495, 497, 498, 500, 501), ()),
    (74, 35, "CNG", 1197.0, 77.5, "57", None, "fronx", 19, "Max Power: 57 kW@6000rpm or 77.5 PS @6000 rpm (CNG)", (496, 499), ()),
    (75, 35, "Petrol", 998.0, 100.1, "73.6", None, "fronx", 19, "Max Power: 73.6 kW@5500rpm or 100.06 PS@5500rpm (1.0L K-Series Turbo)",
     (502, 503, 504, 505, 506), (822,)),
    (77, 36, "CNG", 998.0, 56.7, "41.7", None, "s_presso", 5, "Power (K10C CNG): CNG Mode: 41.7kW (56.696 PS) @ 5300 rpm",
     (510, 513), ()),
    (79, 37, "CNG", 998.0, 56.7, "41.7", None, "alto_k10", 5, "Maximum Power (kW@rpm) (K10C CNG): CNG Mode: 41.7 kW @ 5300 rpm",
     (518, 521), ()),
    (80, 38, "Petrol", 1462.0, 103.1, "75.8", None, "hyryder", 14, "Max. Power (BS6 Ph2 Petrol): 75.8 kW (103.06 PS) @ 6000 rpm",
     (523, 524, 525, 529, 530, 532, 533, 534), ()),
    (81, 38, "CNG", 1462.0, 87.8, "64.6", None, "hyryder", 14, "Max. Power (BS6 Ph2 Petrol + CNG): 64.6kW (87.8 PS) @ 5500 rpm [CNG mode]",
     (526, 528), ()),
    (82, 38, "Petrol Hybrid", 1490.0, 115.6, "85", None, "hyryder", 14, "Hybrid System: Total system Max.Power 85 kW (115.56PS)",
     (527, 531, 535), ()),
    (83, 39, "Petrol", 1462.0, 103.1, "75.8", None, "grand_vitara", 15, "Max Power [1 kW = 1.35962 PS] (Petrol): 75.8 @ 6000 [103.06 PS @ 6000 rpm]",
     (536, 537, 538, 539, 540, 541, 542, 543, 544, 545, 546, 547), (823,)),
    (85, 39, "Petrol Hybrid", 1490.0, 115.6, "85", None, "grand_vitara", 15, "HYBRID Total System Max. Power [1 kW = 1.35962 PS]: 85 kW [115.56 PS]",
     (550, 551, 552, 553, 554), ()),
    (86, 40, "Petrol", 1462.0, 103.1, "75.8", None, "victoris", 16, "Max Power (Petrol, K15C Smart Hybrid): 75.8 kW (103.06 Ps) @ 6000 rpm",
     (555, 557, 559, 560, 561, 563, 564, 565, 566, 568, 569, 572, 573), (825,)),
    (87, 40, "CNG", 1462.0, 87.8, "64.6", None, "victoris", 16, "Max Power (Petrol+CNG): 64.6 kW (87.8 Ps) @ 5500 rpm - CNG Mode",
     (556, 558, 562), ()),
    (117, 55, "Petrol", 1333.0, 163.0, None, "163", "duster", 20, "max power output (ps @ rpm): Turbo TCe 160 MT & DCT 163 @ 5250 (no kW printed)",
     (707, 708, 709, 710, 712, 713, 714, 715), ()),
]

# ---- B: (variant, column, old, new, reason, brochure, page, printed, contradicted v6 fp id)
KMKG_UPDATES = [
    (558, "mileage_arai_km_per_kg", 26.6, 27.02, "OEM_BROCHURE_MISMATCH", "victoris", 16,
     "Fuel Efficiency (Petrol+CNG): 27.02 km/kg", 17208),
    (562, "mileage_arai_km_per_kg", 26.6, 27.02, "OEM_BROCHURE_MISMATCH", "victoris", 16,
     "Fuel Efficiency (Petrol+CNG): 27.02 km/kg", 17338),
]


def target_hp(kw, ps):
    v = Decimal(kw) * KW_TO_HP if kw is not None else Decimal(ps) * PS_TO_HP
    return float(v.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def desc(cc, bhp, fuel):
    return f"{cc:.0f}cc {bhp}bhp {fuel}"


def obs_payload(brochure, page, printed, fields, variant_name):
    path, sha1 = BRO[brochure]
    return json.dumps({"phase": PHASE, "method": "human-verified brochure read (10F, rendered and visually confirmed)",
                       "pdf_path": f"knowledge_base/sources/oem/{path}", "pdf_sha1": sha1, "page": page,
                       "printed": printed, "variant": variant_name, "fields": fields}, sort_keys=True)


def main():
    args = sys.argv[1:]
    db = args[0]
    if "--oem" in args:
        root = args[args.index("--oem") + 1]
        for k, (path, sha1) in BRO.items():
            got = hashlib.sha1(open(os.path.join(root, path), "rb").read()).hexdigest()
            assert got == sha1, f"brochure {k}: sha1 {got} != {sha1}"
    c = sqlite3.connect(db, isolation_level=None)
    c.execute("PRAGMA foreign_keys=ON")
    one = lambda sql, *a: c.execute(sql, a).fetchone()
    tables = [r[0] for r in c.execute("select name from sqlite_master where type='table' and name<>'sqlite_sequence'")]
    snap = lambda t: {r[0]: r for r in c.execute(f'select * from "{t}"')}
    counts = dict(update=0, amend=0, obs=0, fp=0, quar=0)
    c.execute("BEGIN IMMEDIATE")
    try:
        before = {t: snap(t) for t in tables}
        schema_before = {r[0]: r[1] for r in c.execute("select name, sql from sqlite_master where name not like 'sqlite_%'")}
        canon_cols = [d[0] for d in c.execute("select * from v_variant_canonical_q limit 0").description]
        canon_before = {r[0]: r for r in c.execute("select * from v_variant_canonical_q")}

        def amend(table, tid, col, old, new, reason):
            c.execute("""insert into evidence_amendment(target_table,target_id,column_name,old_value,new_value,reason_code,phase)
                         values (?,?,?,?,?,?,?)""", (table, tid, col, None if old is None else str(old),
                                                     None if new is None else str(new), reason, PHASE))
            counts["amend"] += 1

        def provenance(vid, brochure, page, printed, fields):
            name = one("select full_name from variant where id=?", vid)[0]
            payload = obs_payload(brochure, page, printed, fields, name)
            if one("select count(*) from source_observation where source_id=? and resolved_variant_id=? and raw_payload=?",
                   OEM_SOURCE_ID, vid, payload)[0]:
                return  # idempotent
            cur = c.execute("""insert into source_observation(source_id,raw_name,raw_payload,source_url,extraction_method,
                               resolved_variant_id,resolution_status) values (?,?,?,?,?,?,'resolved')""",
                            (OEM_SOURCE_ID, name, payload, "offline_brochure", METHOD, vid))
            counts["obs"] += 1
            for f, v in fields.items():
                c.execute("""insert into field_provenance(variant_id,field_name,accepted_value,source_observation_id,decision,decision_reason)
                             values (?,?,?,?,'accepted',?)""", (vid, f, str(v), cur.lastrowid, FP_REASON))
                counts["fp"] += 1

        def quarantine(table, tid, field, reason, note):
            if one("select count(*) from evidence_quarantine where target_table=? and target_id=? and ifnull(target_field,'')=ifnull(?, '') and reason_code=? and released_at is null",
                   table, tid, field, reason)[0]:
                return
            c.execute("insert into evidence_quarantine(target_table,target_id,target_field,reason_code,phase,note) values (?,?,?,?,?,?)",
                      (table, tid, field, reason, PHASE, note))
            counts["quar"] += 1

        # ---------------- A: PS stored as bhp
        for pt, mid, fuel, cc, old, kw, ps, bro, page, printed, users, editions in POWERTRAINS:
            new = target_hp(kw, ps)
            d_old, d_new = desc(cc, old, fuel), desc(cc, new, fuel)
            row = one("select model_id, fuel_type, engine_cc, power_bhp, description from powertrain where id=?", pt)
            if row[3] != new:
                assert row == (mid, fuel, cc, old, d_old), f"powertrain {pt}: drift {row}"
                assert one("select count(*) from powertrain where model_id=? and fuel_type=? and engine_cc=? and power_bhp=?",
                           mid, fuel, cc, new)[0] == 0, f"powertrain {pt}: UNIQUE collision at {new}"
                c.execute("update powertrain set power_bhp=?, description=? where id=?", (new, d_new, pt))
                counts["update"] += 1
                amend("powertrain", pt, "power_bhp", old, new, "OEM_UNIT_PS_AS_BHP")
                amend("powertrain", pt, "description", d_old, d_new, "OEM_UNIT_PS_AS_BHP")
            assert one("select description from powertrain where id=?", pt)[0] == d_new
            got_users = tuple(r[0] for r in c.execute("select id from variant where powertrain_id=? and base_variant_id is null order by id", (pt,)))
            got_eds = tuple(r[0] for r in c.execute("select id from variant where powertrain_id=? and base_variant_id is not null order by id", (pt,)))
            assert got_users == users and got_eds == editions, (pt, got_users, got_eds)
            conv = f"{kw} kW x 1.34102" if kw is not None else f"{ps} PS x 0.98632"
            for vid in users:
                provenance(vid, bro, page, f"{printed} ({conv} = {new} hp)", {"power_bhp": new})

        # ---------------- B: km/kg corrections
        for vid, col, old, new, reason, bro, page, printed, fid in KMKG_UPDATES:
            assert one("select base_variant_id from variant where id=?", vid)[0] is None, f"{vid} is an edition"
            cur = one(f'select "{col}" from variant where id=?', vid)[0]
            if cur != new:
                assert cur == old, f"variant {vid}.{col}: expected {old!r}, found {cur!r}"
                c.execute(f'update variant set "{col}"=? where id=?', (new, vid))
                counts["update"] += 1
                amend("variant", vid, col, old, new, reason)
            provenance(vid, bro, page, printed, {col: new})
            row = one("""select fp.variant_id, fp.field_name, fp.accepted_value, s.name from field_provenance fp
                         join source_observation so on so.id=fp.source_observation_id join source s on s.id=so.source_id where fp.id=?""", fid)
            assert row == (vid, col, str(old), "v6_migration"), f"fp {fid}: drift {row}"
            path, sha1 = BRO[bro]
            quarantine("field_provenance", fid, None, "CONTRADICTED_BY_OEM_BROCHURE",
                       f"fp_id={fid}; variant_id={vid}; field={col}; source=v6_migration; accepted_value={old}; contradicted by "
                       f"knowledge_base/sources/oem/{path} sha1 {sha1} p{page}")

        # ================= invariants before COMMIT =================
        pts = {p[0] for p in POWERTRAINS}
        allowed_variant = {(v, col) for v, col, *_ in KMKG_UPDATES}
        vcols = [r[1] for r in c.execute("pragma table_info(variant)")]
        pcols = [r[1] for r in c.execute("pragma table_info(powertrain)")]
        after = {t: snap(t) for t in tables}
        for t in tables:
            b, a = before[t], after[t]
            if t in ("evidence_amendment", "evidence_quarantine", "source_observation", "field_provenance"):
                assert set(b) <= set(a) and all(a[k] == b[k] for k in b), f"{t}: existing rows changed"
                new_rows = [a[k] for k in set(a) - set(b)]
                if t == "evidence_quarantine":
                    assert all(r[5] == PHASE for r in new_rows) and len(new_rows) == counts["quar"]
                elif t == "evidence_amendment":
                    assert all(r[7] == PHASE for r in new_rows) and len(new_rows) == counts["amend"]
                elif t == "source_observation":
                    assert all(r[1] == OEM_SOURCE_ID and r[6] == METHOD for r in new_rows) and len(new_rows) == counts["obs"]
                else:
                    assert all(r[5] == "accepted" and r[6] == FP_REASON for r in new_rows) and len(new_rows) == counts["fp"]
                continue
            assert set(a) == set(b), f"{t}: rows added/deleted"
            for k in b:
                if a[k] == b[k]:
                    continue
                if t == "variant":
                    diff = {vcols[j] for j in range(len(vcols)) if a[k][j] != b[k][j] or type(a[k][j]) is not type(b[k][j])}
                    assert {(k, col) for col in diff} <= allowed_variant, f"variant {k}: unexpected {diff}"
                elif t == "powertrain":
                    diff = {pcols[j] for j in range(len(pcols)) if a[k][j] != b[k][j]}
                    assert k in pts and diff <= {"power_bhp", "description"}, f"powertrain {k}: {diff}"
                else:
                    raise AssertionError(f"{t} {k}: unexpected change")
        schema_after = {r[0]: r[1] for r in c.execute("select name, sql from sqlite_master where name not like 'sqlite_%'")}
        assert schema_after == schema_before, "schema changed"
        for vid, row in ((r[0], r) for r in c.execute("select * from v_variant_canonical_q")):
            for j, col in enumerate(canon_cols):
                if row[j] != canon_before[vid][j]:
                    assert (vid, col) in allowed_variant, f"canonical {vid}.{col} changed unexpectedly"
        assert one("select count(*) from variant")[0] == 832
        assert one("pragma integrity_check")[0] == "ok"
        fk = c.execute("pragma foreign_key_check").fetchall()
        assert len(fk) == 297 and all(r[0] == "field_provenance" and r[2] == "source_observation" for r in fk), len(fk)
        for pt, mid, fuel, cc, old, kw, ps, *_ in POWERTRAINS:
            exp = target_hp(kw, ps)
            assert one("select power_bhp from powertrain where id=?", pt)[0] == exp
            assert exp == round((float(kw) * 1.34102) if kw is not None else (float(ps) * 0.98632), 2)
        for vid, col, old, new, *_ in KMKG_UPDATES:
            assert one(f'select "{col}" from v_variant_canonical_q where id=?', vid)[0] == new
        c.execute("COMMIT")
        print(f"COMMITTED; {json.dumps(counts)}")
    except Exception as ex:
        c.execute("ROLLBACK")
        import traceback
        traceback.print_exc()
        print("ROLLBACK:", repr(ex))
        sys.exit(1)


if __name__ == "__main__":
    main()
