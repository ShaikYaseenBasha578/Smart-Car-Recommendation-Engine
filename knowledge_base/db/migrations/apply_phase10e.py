"""Phase 10E (KB corrections, Pass B): one controlled write covering approved items 1-6.

Usage: python3 apply_phase10e.py <db_path>
One BEGIN IMMEDIATE transaction with foreign_keys=ON. DDL (items 4, 5) runs inside it. Every invariant is checked
before COMMIT; any failure rolls back. Idempotent: a re-run on an already-corrected DB makes no change.

Write mechanism (Phase 10B-W6 pattern):
  - corrected cells: UPDATE + one evidence_amendment row each (old, new, reason, phase '10E');
  - provenance for each asserted new value: one OEM source_observation per (brochure, variant) whose raw_payload
    carries the PDF path, PDF SHA-1, page and printed text, plus one field_provenance row (decision 'accepted');
  - contradicting live field_provenance rows: quarantined (never modified);
  - cells that cannot be verified: variant-cell quarantine.
Items:
  1 CNG mileage: 5 variants (245, 213, 591, 556, 217) kmpl -> NULL, km/kg -> brochure value; 345 kmpl quarantined.
  2 Paddle shifters: 9 EXPLICIT_ABSENT variants 1 -> 0; 4 XL6 NOT_MENTIONED cells quarantined. Kushaq/Jimny untouched.
  3 Glanza petrol power: powertrain 68 power_bhp 89.7 -> 88.51 (66 kW), first power provenance rows.
  4 evidence_quarantine CHECK rebuilt to allow 'warranty' (old table renamed aside; new table from today's exact
    stored text + CHECK; ux_quarantine_active recreated); v_warranty_q created (has_provenance constant 0: no
    provenance table can reference a warranty row); warranty row 12 cells warranty_years/warranty_km quarantined.
  5 v_variant_canonical_q redefined without adas_tier (raw column kept).
  6 Edition rebases: 814 base 649 -> 652 (ZX); 826 base 218 -> 220 (Alpha+); OEM observation + base_variant_id fp row each.
"""
import json
import sqlite3
import sys

PHASE = "10E"
OEM_SOURCE_ID = 6
BRO = {  # brochure -> (path under knowledge_base/sources/oem, SHA-1) - re-verified against the files in Pass B
    "eeco": ("maruti_suzuki/eeco/latest/brochures/maruti_suzuki_eeco_brochure.pdf", "d964c7b53a8136234131c0d5c165c647ae1f2a11"),
    "ertiga": ("maruti_suzuki/ertiga/latest/brochures/maruti_suzuki_ertiga_brochure.pdf", "d5a10fb1556e2ad77abd66a5747471bed3df5d2d"),
    "rumion": ("toyota/rumion/latest/brochures/toyota_rumion_brochure.pdf", "c1d41f62df6331b12d505f05032fdf4425e3da80"),
    "victoris": ("maruti_suzuki/victoris/latest/brochures/maruti_suzuki_victoris_brochure.pdf", "94f94973736c150efdf2cc5ae6c40845d8e856a3"),
    "xl6": ("maruti_suzuki/xl6/latest/brochures/NEXA-Xl6-Brochure.pdf", "e66cbeecb310f06cd6f0205f2772f152a5b6a891"),
    "altroz": ("tata/altroz/latest/brochures/tata_altroz_brochure.pdf", "5cbbf8b65224b23bb027ff078fe5e4721f793d25"),
    "creta": ("hyundai/creta/gen2_facelift_2024/brochures/Hyundai_Creta_Brochure_Official.pdf", "cc5b2fbc3490e16d1e5de56d61b49eb7372ce362"),
    "venue": ("hyundai/venue/latest/brochures/hyundai_venue_brochure.pdf", "00eabf1c73ad06d076b7e3928d9ca54d9b4cb1c4"),
    "taigun": ("volkswagen/taigun/latest/brochures/volkswagen_taigun_brochure.pdf", "b2a396b599758b80a6643ad479eb21426eaa2c3c"),
    "glanza": ("toyota/glanza/latest/brochures/toyota_glanza_brochure.pdf", "fd682f602d0fe869b41128fe8e7b96d8268f029f"),
    "grand_vitara": ("maruti_suzuki/grand_vitara/latest/brochures/maruti_suzuki_grand_vitara_brochure.pdf", "023ce2e3d22ca4bd3a2cd1a9aded193273482e91"),
    "elevate": ("honda/elevate/latest/brochures/honda_elevate_brochure.pdf", "3b794463eeda84b292eab3a1b9e07ab65a40ccfc"),
}

# ---- item 1 / 2: variant cell updates. (variant, column, old, new, reason, brochure, page, printed, provenance?)
CELL_UPDATES = [
    (245, "mileage_arai_kmpl", 26.78, None, "OEM_UNIT_KMKG_IN_KMPL", "eeco", 2, "CNG (km/kg) 26.78", False),
    (245, "mileage_arai_km_per_kg", None, 26.78, "OEM_UNIT_KMKG_IN_KMPL", "eeco", 2, "CNG (km/kg) 26.78", True),
    (213, "mileage_arai_kmpl", 26.11, None, "OEM_UNIT_KMKG_IN_KMPL", "ertiga", 7, "26.11 km/kg CNG - VXi MT, ZXi MT", False),
    (213, "mileage_arai_km_per_kg", None, 26.11, "OEM_UNIT_KMKG_IN_KMPL", "ertiga", 7, "26.11 km/kg CNG - VXi MT, ZXi MT", True),
    (591, "mileage_arai_kmpl", 26.11, None, "OEM_UNIT_KMKG_IN_KMPL", "rumion", 6, "CNG S MT 26.11 km/kg", False),
    (556, "mileage_arai_kmpl", 27.02, None, "OEM_UNIT_KMKG_IN_KMPL", "victoris", 16, "PETROL/CNG Fuel Efficiency 27.02 km/kg", False),
    (556, "mileage_arai_km_per_kg", 26.6, 27.02, "OEM_SPOTCHECK_VERIFIED", "victoris", 16, "PETROL/CNG Fuel Efficiency 27.02 km/kg", True),
    (217, "mileage_arai_kmpl", 26.23, None, "OEM_UNIT_KMKG_IN_KMPL", "xl6", 15, "CNG Fuel Efficiency 26.23 km/kg", False),
    (217, "mileage_arai_km_per_kg", None, 26.23, "OEM_UNIT_KMKG_IN_KMPL", "xl6", 15, "CNG Fuel Efficiency 26.23 km/kg", True),
] + [
    (v, "paddle_shifters", 1, 0, "OEM_BROCHURE_AT_ONLY", b, p, txt, True)
    for v, b, p, txt in [
        (5, "creta", 14, "Paddle shifters: EX '-'"),
        (15, "creta", 14, "Paddle shifters: SX Premium 'S*'; footnote '* iVT/AT/DCT only'"),
        (16, "creta", 14, "Paddle shifters: SX Premium 'S*'; footnote '* iVT/AT/DCT only'"),
        (21, "creta", 14, "Paddle shifters: SX Premium 'S*'; footnote '* iVT/AT/DCT only'"),
        (23, "creta", 14, "Paddle shifters: SX Premium 'S*'; footnote '* iVT/AT/DCT only'"),
        (158, "venue", 20, "Paddle shifters: HX 5 'S^'; footnote 'S^ - DCT/AT only'"),
        (561, "victoris", 16, "Paddle Shifters: Zxi/Zxi(O) '6AT'"),
        (566, "victoris", 16, "Paddle Shifters: Zxi+/Zxi+(O) '6AT'"),
        (627, "taigun", 10, "Paddle Shifter: GT Line '● (AT only)'"),
    ]
]
# contradicting live fp rows to quarantine: (fp_id, variant, field, expected accepted_value, source name)
FP_QUARANTINE = [
    (26233, 245, "mileage_arai_kmpl", "26.78", "91wheels", "eeco", 2),
    (26338, 213, "mileage_arai_kmpl", "26.11", "91wheels", "ertiga", 7),
    (27737, 591, "mileage_arai_kmpl", "26.11", "91wheels", "rumion", 6),
    (26621, 556, "mileage_arai_kmpl", "27.02", "91wheels", "victoris", 16),
    (26695, 217, "mileage_arai_kmpl", "26.23", "91wheels", "xl6", 15),
    (17141, 556, "mileage_arai_km_per_kg", "26.6", "v6_migration", "victoris", 16),
    (164, 5, "paddle_shifters", "True", "v6_migration", "creta", 14),
    (504, 15, "paddle_shifters", "True", "v6_migration", "creta", 14),
    (538, 16, "paddle_shifters", "True", "v6_migration", "creta", 14),
    (708, 21, "paddle_shifters", "True", "v6_migration", "creta", 14),
    (776, 23, "paddle_shifters", "True", "v6_migration", "creta", 14),
    (5110, 158, "paddle_shifters", "True", "v6_migration", "venue", 20),
    (17321, 561, "paddle_shifters", "True", "v6_migration", "victoris", 16),
    (17480, 566, "paddle_shifters", "True", "v6_migration", "victoris", 16),
    (19382, 627, "paddle_shifters", "True", "v6_migration", "taigun", 10),
]
# variant-cell quarantines: (variant, field, expected current raw value, reason, note)
CELL_QUARANTINE = [
    (345, "mileage_arai_kmpl", 26.2, "UNIT_SUSPECT_SOURCE_MISLABEL",
     "Altroz CNG kmpl 26.2 (91wheels fp 27188). The same 91wheels source stored a km/kg figure as kmpl on the 5 "
     "brochure-verified CNG siblings (245, 213, 591, 556, 217). The Altroz brochure prints no fuel-efficiency figure "
     f"(p23 Technical Specifications; whole document has 0 km/kg|km/l|kmpl): {BRO['altroz'][0]} sha1 {BRO['altroz'][1]}."),
] + [
    (v, "paddle_shifters", 1, "PADDLE_ON_MT_NOT_MENTIONED",
     "XL6 MT paddle_shifters=1 (v6_migration). Brochure p15 feature list has no paddle row; p10 ties paddle shifters "
     f"to the 6-speed AT but does not state MT absence. Not mentioned = unknown, not 0. {BRO['xl6'][0]} sha1 {BRO['xl6'][1]}.")
    for v in (216, 217, 218, 220)
]
# item 3
PT_ID, PT_OLD, PT_NEW = 68, 89.7, 88.51
PT_DESC_OLD, PT_DESC_NEW = "1197cc 89.7bhp Petrol", "1197cc 88.51bhp Petrol"
GLANZA_PETROL_VARIANTS = (476, 477, 478, 480, 481, 483, 484)
# item 4
WARRANTY_ID = 12
WARRANTY_EXPECTED = (2.0, "40000.0")
# item 6
REBASES = [  # edition, old base, new base, brochure, page, printed
    (814, 649, 652, "elevate", 48, "ZX Black Edition (Over ZX); footnote: ZX Black Edition refers to ELEVATE ZX MT/CVT R BLK (i-VTEC)"),
    (826, 218, 220, "xl6", 15, "Glossy Black Outside Mirrors: Zeta '—' / Alpha '—' / Alpha+ '(Dual Tone)': dual tone on Alpha+ only"),
]

CHECK_EDITS = [  # exact substrings of today's stored evidence_quarantine definition -> new CHECK text
    ("'safety_test','safety_test_applicability'))", "'safety_test','safety_test_applicability','warranty'))"),
    ("CHECK (target_table <> 'variant' OR target_field IS NOT NULL)",
     "CHECK (target_table NOT IN ('variant','warranty') OR target_field IS NOT NULL)"),
]
UX_SQL = """CREATE UNIQUE INDEX ux_quarantine_active
  ON evidence_quarantine(target_table, target_id, IFNULL(target_field,''), reason_code)
  WHERE released_at IS NULL"""
WARRANTY_VIEW = """CREATE VIEW v_warranty_q AS
  SELECT
    w.id,
    w.manufacturer_id,
    w.model_id,
    CASE WHEN w.model_id IS NULL THEN 'MAKE' ELSE 'MODEL' END AS grain,
    CASE WHEN EXISTS (SELECT 1 FROM v_active_quarantine q WHERE q.target_table='warranty' AND q.target_id=w.id AND q.target_field IN ('warranty_years','*')) THEN NULL ELSE w.warranty_years END AS warranty_years,
    CASE WHEN EXISTS (SELECT 1 FROM v_active_quarantine q WHERE q.target_table='warranty' AND q.target_id=w.id AND q.target_field IN ('warranty_km','*')) THEN NULL ELSE w.warranty_km END AS warranty_km,
    CASE WHEN EXISTS (SELECT 1 FROM v_active_quarantine q WHERE q.target_table='warranty' AND q.target_id=w.id AND q.target_field IN ('battery_warranty_years','*')) THEN NULL ELSE w.battery_warranty_years END AS battery_warranty_years,
    CASE WHEN EXISTS (SELECT 1 FROM v_active_quarantine q WHERE q.target_table='warranty' AND q.target_id=w.id AND q.target_field IN ('battery_warranty_km','*')) THEN NULL ELSE w.battery_warranty_km END AS battery_warranty_km,
    CASE WHEN EXISTS (SELECT 1 FROM v_active_quarantine q WHERE q.target_table='warranty' AND q.target_id=w.id AND q.target_field IN ('extended_warranty_available','*')) THEN NULL ELSE w.extended_warranty_available END AS extended_warranty_available,
    w.source,
    w.source_url,
    0 AS has_provenance  -- constant: field_provenance/source_observation reference variant rows only (no schema change made)
  FROM warranty w"""


def obs_payload(brochure, page, printed, fields, variant_name):
    path, sha1 = BRO[brochure]
    return json.dumps({"phase": PHASE, "method": "human-verified brochure read (Pass A, re-verified Pass B)",
                       "pdf_path": f"knowledge_base/sources/oem/{path}", "pdf_sha1": sha1, "page": page,
                       "printed": printed, "variant": variant_name, "fields": fields}, sort_keys=True)


def main():
    db = sys.argv[1]
    c = sqlite3.connect(db, isolation_level=None)
    c.execute("PRAGMA foreign_keys=ON")
    one = lambda sql, *a: c.execute(sql, a).fetchone()
    tables = [r[0] for r in c.execute("select name from sqlite_master where type='table' and name<>'sqlite_sequence'")]
    snap = lambda t: {r[0]: r for r in c.execute(f'select * from "{t}"')}
    counts = dict(update=0, amend=0, obs=0, fp=0, quar=0, ddl=[])
    c.execute("BEGIN IMMEDIATE")
    try:
        before = {t: snap(t) for t in tables}
        schema_before = {r[0]: r[1] for r in c.execute("select name, sql from sqlite_master where name not like 'sqlite_%'")}
        canon_cols_before = [d[0] for d in c.execute("select * from v_variant_canonical_q limit 0").description]
        canon_before = {r[0]: dict(zip(canon_cols_before, r)) for r in c.execute("select * from v_variant_canonical_q")}

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
                            (OEM_SOURCE_ID, name, payload, "offline_brochure", "manual_brochure_10E", vid))
            counts["obs"] += 1
            for f, v in fields.items():
                c.execute("""insert into field_provenance(variant_id,field_name,accepted_value,source_observation_id,decision,decision_reason)
                             values (?,?,?,?,'accepted','OEM_BROCHURE_VERIFIED_10E')""", (vid, f, str(v), cur.lastrowid))
                counts["fp"] += 1

        def quarantine(table, tid, field, reason, note):
            if one("select count(*) from evidence_quarantine where target_table=? and target_id=? and ifnull(target_field,'')=ifnull(?, '') and reason_code=? and released_at is null",
                   table, tid, field, reason)[0]:
                return
            c.execute("insert into evidence_quarantine(target_table,target_id,target_field,reason_code,phase,note) values (?,?,?,?,?,?)",
                      (table, tid, field, reason, PHASE, note))
            counts["quar"] += 1

        # ---------------- item 4a: evidence_quarantine CHECK rebuild (first, so 'warranty' rows are accepted)
        eq_sql = one("select sql from sqlite_master where name='evidence_quarantine'")[0]
        if "'warranty'" not in eq_sql:
            n_before = one("select count(*) from evidence_quarantine")[0]
            new_eq_sql = eq_sql
            for a, b in CHECK_EDITS:
                assert new_eq_sql.count(a) == 1, a
                new_eq_sql = new_eq_sql.replace(a, b)
            # Rename the OLD table aside so the new table is created under the original name from today's exact
            # stored text: the stored definition then differs only in the CHECK (RENAME of the new table would
            # store the name quoted). legacy_alter_table: views keep referring to evidence_quarantine by name.
            c.execute("PRAGMA legacy_alter_table=ON")
            c.execute("ALTER TABLE evidence_quarantine RENAME TO evidence_quarantine_old")
            c.execute(new_eq_sql)
            c.execute("INSERT INTO evidence_quarantine SELECT * FROM evidence_quarantine_old")
            c.execute("DROP TABLE evidence_quarantine_old")
            c.execute("PRAGMA legacy_alter_table=OFF")
            c.execute(UX_SQL)
            assert one("select count(*) from evidence_quarantine")[0] == n_before
            counts["ddl"].append("evidence_quarantine rebuilt (CHECK +warranty), ux_quarantine_active recreated")

        # ---------------- items 1 + 2: cell updates with amendment + provenance
        for vid, col, old, new, reason, bro, page, printed, prov in CELL_UPDATES:
            cur = one(f'select "{col}" from variant where id=?', vid)[0]
            if cur == new and type(cur) is type(new):
                pass  # already applied
            else:
                assert cur == old, f"variant {vid}.{col}: expected {old!r}, found {cur!r}"
                c.execute(f'update variant set "{col}"=? where id=?', (new, vid))
                counts["update"] += 1
                amend("variant", vid, col, old, new, reason)
            if prov:
                provenance(vid, bro, page, printed, {col: new})
        for fid, vid, field, val, src, bro, page in FP_QUARANTINE:
            row = one("""select fp.variant_id, fp.field_name, fp.accepted_value, s.name from field_provenance fp
                         join source_observation so on so.id=fp.source_observation_id join source s on s.id=so.source_id where fp.id=?""", fid)
            assert row == (vid, field, val, src), f"fp {fid}: drift {row}"
            path, sha1 = BRO[bro]
            quarantine("field_provenance", fid, None, "CONTRADICTED_BY_OEM_BROCHURE",
                       f"fp_id={fid}; variant_id={vid}; field={field}; source={src}; accepted_value={val}; contradicted by "
                       f"knowledge_base/sources/oem/{path} sha1 {sha1} p{page}")
        for vid, field, expected, reason, note in CELL_QUARANTINE:
            cur = one(f'select "{field}" from variant where id=?', vid)[0]
            assert cur == expected, f"variant {vid}.{field}: expected {expected!r}, found {cur!r}"
            quarantine("variant", vid, field, reason, note)

        # ---------------- item 3: Glanza petrol power
        pt = one("select model_id, fuel_type, engine_cc, power_bhp, description from powertrain where id=?", PT_ID)
        if pt[3] != PT_NEW:
            assert pt == (33, "Petrol", 1197.0, PT_OLD, PT_DESC_OLD), f"powertrain {PT_ID}: drift {pt}"
            assert one("select count(*) from powertrain where model_id=33 and fuel_type='Petrol' and engine_cc=1197.0 and power_bhp=?", PT_NEW)[0] == 0
            c.execute("update powertrain set power_bhp=?, description=? where id=?", (PT_NEW, PT_DESC_NEW, PT_ID))
            counts["update"] += 1
            amend("powertrain", PT_ID, "power_bhp", PT_OLD, PT_NEW, "OEM_UNIT_PS_AS_BHP")
            amend("powertrain", PT_ID, "description", PT_DESC_OLD, PT_DESC_NEW, "OEM_UNIT_PS_AS_BHP")
        users = tuple(r[0] for r in c.execute("select id from variant where powertrain_id=? order by id", (PT_ID,)))
        assert users == GLANZA_PETROL_VARIANTS, users
        for vid in users:
            provenance(vid, "glanza", 1, "Technical Specifications: Max. power Petrol 66kw@6000rpm (66 kW x 1.34102 = 88.51 hp)",
                       {"power_bhp": PT_NEW})

        # ---------------- item 4b/4c: v_warranty_q + Grand Vitara row quarantine
        if not one("select count(*) from sqlite_master where name='v_warranty_q'")[0]:
            c.execute(WARRANTY_VIEW)
            counts["ddl"].append("v_warranty_q created")
        w = one("select model_id, warranty_years, warranty_km from warranty where id=?", WARRANTY_ID)
        assert w[1:] == WARRANTY_EXPECTED and one("select name from model where id=?", w[0])[0] == "Grand Vitara", w
        path, sha1 = BRO["grand_vitara"]
        for col, val in (("warranty_years", "2.0"), ("warranty_km", "40000.0")):
            quarantine("warranty", WARRANTY_ID, col, "CONTRADICTED_BY_OEM_BROCHURE",
                       f"warranty row {WARRANTY_ID} (Grand Vitara) {col}={val}; brochure p15 prints '3 YEARS/1 00 000 KM "
                       f"WARRANTY': knowledge_base/sources/oem/{path} sha1 {sha1}. Value not changed; cell masked in v_warranty_q.")

        # ---------------- item 5: v_variant_canonical_q without adas_tier
        vsql = one("select sql from sqlite_master where name='v_variant_canonical_q'")[0]
        lines = vsql.split("\n")
        adas = [i for i, l in enumerate(lines) if l.rstrip().endswith("AS adas_tier,")]
        if adas:
            assert len(adas) == 1, adas
            new_sql = "\n".join(l for i, l in enumerate(lines) if i != adas[0])
            c.execute("DROP VIEW v_variant_canonical_q")
            c.execute(new_sql)
            counts["ddl"].append("v_variant_canonical_q recreated without adas_tier")

        # ---------------- item 6: edition rebases
        for ed, old_base, new_base, bro, page, printed in REBASES:
            cur = one("select base_variant_id from variant where id=?", ed)[0]
            assert one("select base_variant_id from variant where id=?", new_base)[0] is None, f"{new_base} is itself an edition"
            assert one("select model_id from variant where id=?", new_base)[0] == one("select model_id from variant where id=?", ed)[0]
            if cur != new_base:
                assert cur == old_base, f"edition {ed}: base {cur}, expected {old_base}"
                c.execute("update variant set base_variant_id=? where id=?", (new_base, ed))
                counts["update"] += 1
                amend("variant", ed, "base_variant_id", old_base, new_base, "EDITION_REBASE_OEM_BROCHURE")
            name = one("select full_name from variant where id=?", ed)[0]
            payload = obs_payload(bro, page, printed, {"base_variant_id": new_base}, name)
            if not one("select count(*) from source_observation where source_id=? and resolved_variant_id=? and raw_payload=?",
                       OEM_SOURCE_ID, ed, payload)[0]:
                c.execute("""insert into source_observation(source_id,raw_name,raw_payload,source_url,extraction_method,
                             resolved_variant_id,resolution_status) values (?,?,?,?,?,?,'resolved')""",
                          (OEM_SOURCE_ID, name, payload, "offline_brochure", "manual_brochure_10E", ed))
                counts["obs"] += 1
                obs_id = one("select last_insert_rowid()")[0]
                c.execute("""insert into field_provenance(variant_id,field_name,accepted_value,source_observation_id,decision,decision_reason)
                             values (?,'base_variant_id',?,?,'accepted','OEM_BROCHURE_VERIFIED_10E')""", (ed, str(new_base), obs_id))
                counts["fp"] += 1

        # ================= invariants before COMMIT =================
        allowed_variant = {(v, col) for v, col, *_ in CELL_UPDATES} | {(e, "base_variant_id") for e, *_ in REBASES}
        vcols = [r[1] for r in c.execute("pragma table_info(variant)")]
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
                    assert all(r[1] == OEM_SOURCE_ID and r[6] == "manual_brochure_10E" for r in new_rows) and len(new_rows) == counts["obs"]
                else:
                    assert all(r[5] == "accepted" and r[6] == "OEM_BROCHURE_VERIFIED_10E" for r in new_rows) and len(new_rows) == counts["fp"]
                continue
            assert set(a) == set(b), f"{t}: rows added/deleted"
            for k in b:
                if a[k] == b[k]:
                    continue
                if t == "variant":
                    diff = {vcols[j] for j in range(len(vcols)) if a[k][j] != b[k][j] or type(a[k][j]) is not type(b[k][j])}
                    assert {(k, col) for col in diff} <= allowed_variant, f"variant {k}: unexpected {diff}"
                elif t == "powertrain":
                    assert k == PT_ID, f"powertrain {k} changed"
                else:
                    raise AssertionError(f"{t} {k}: unexpected change")
        # schema: only the three approved objects (+ the recreated index, byte-identical)
        schema_after = {r[0]: r[1] for r in c.execute("select name, sql from sqlite_master where name not like 'sqlite_%'")}
        changed = {n for n in set(schema_before) | set(schema_after) if schema_before.get(n) != schema_after.get(n)}
        assert changed <= {"evidence_quarantine", "v_warranty_q", "v_variant_canonical_q"}, changed
        assert schema_after.get("ux_quarantine_active") == schema_before.get("ux_quarantine_active")
        exp_eq = schema_before["evidence_quarantine"]
        for a, b in CHECK_EDITS:
            exp_eq = exp_eq.replace(a, b)
        assert schema_after["evidence_quarantine"] == exp_eq, "evidence_quarantine stored DDL differs beyond the CHECK"
        # canonical view: adas_tier gone; other columns change only on approved cells or rebased editions
        canon_cols = [d[0] for d in c.execute("select * from v_variant_canonical_q limit 0").description]
        assert "adas_tier" not in canon_cols and canon_cols == [x for x in canon_cols_before if x != "adas_tier"]
        canon_after = {r[0]: dict(zip(canon_cols, r)) for r in c.execute("select * from v_variant_canonical_q")}
        rebased = {e for e, *_ in REBASES}
        quarantined_cells = {(v, f) for v, f, *_ in CELL_QUARANTINE}
        for vid, row in canon_after.items():
            for col in canon_cols:
                if row[col] != canon_before[vid][col]:
                    assert vid in rebased or (vid, col) in allowed_variant or (vid, col) in quarantined_cells \
                        or (vid, col) == (826, "paddle_shifters"), f"canonical {vid}.{col} changed unexpectedly"
        # data invariants
        assert one("select count(*) from variant")[0] == 832
        assert one("pragma integrity_check")[0] == "ok"
        fk = c.execute("pragma foreign_key_check").fetchall()
        assert len(fk) == 297 and all(r[0] == "field_provenance" and r[2] == "source_observation" for r in fk), len(fk)
        cng = """select count(*) from v_variant_canonical_q q join powertrain p on p.id=q.powertrain_id where p.fuel_type='CNG' and """
        assert one(cng + "q.mileage_arai_kmpl = q.mileage_arai_km_per_kg")[0] == 0, "CNG invariant (a)"
        assert one(cng + "q.mileage_arai_kmpl > 25")[0] == 0, "CNG invariant (b)"
        paddle = {r[0] for r in c.execute("select id from v_variant_canonical_q where transmission='Manual' and paddle_shifters=1")}
        assert paddle == {599, 605, 824}, f"paddle invariant: {sorted(paddle)}"
        assert one("select power_bhp from powertrain where id=?", PT_ID)[0] == PT_NEW
        assert one("select count(*) from field_provenance where field_name='power_bhp' and accepted_value='88.51'")[0] == len(GLANZA_PETROL_VARIANTS)
        wq = one("select warranty_years, warranty_km, battery_warranty_years, battery_warranty_km, extended_warranty_available from v_warranty_q where id=?", WARRANTY_ID)
        raw = one("select battery_warranty_years, battery_warranty_km, extended_warranty_available from warranty where id=?", WARRANTY_ID)
        assert wq == (None, None) + raw, wq
        assert one("select count(*) from (select id,manufacturer_id,model_id,warranty_years,warranty_km,battery_warranty_years,battery_warranty_km,extended_warranty_available,source,source_url from warranty where id<>? except select id,manufacturer_id,model_id,warranty_years,warranty_km,battery_warranty_years,battery_warranty_km,extended_warranty_available,source,source_url from v_warranty_q)", WARRANTY_ID)[0] == 0
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
