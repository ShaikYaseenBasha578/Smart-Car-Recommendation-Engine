"""Phase 10L: warranty provenance and corrections (backlog item 6). Usage: apply_phase10l.py <db>
No DDL: provenance goes in the existing warranty.source / source_url columns, each change logged in evidence_amendment.
- 14 rows: the brochure confirms the figures; source now cites PDF, page and SHA-1.
- Grand Vitara (id 12): years 2 -> 3, km 40000 -> 100000; the 10E quarantines on those cells are released.
  Its battery figures are not in the brochure and stay as they were.
- Hyundai make-wide row says Unlimited, which the Nios and Aura brochures contradict: model rows added for them and Exter.
Rows left unverified: Hyundai make row (1), MG (4), Renault (10): no brochure on disk settles them for the make.
One BEGIN IMMEDIATE transaction, foreign_keys=ON, idempotent, invariants before COMMIT."""
import sqlite3, sys
PHASE = "10L"; SRC = "OEM brochure (10L)"; REASON = "OEM_BROCHURE_PROVENANCE"; FIX = "OEM_BROCHURE_MISMATCH"
VERIFIED = [
    (2, 'mahindra/xuv_3xo/latest/brochures/mahindra_xuv_3xo_brochure.pdf', '12, 16', '73015a758e9bba7e3961bcdea749b62603d682e5', '3-year standard warranty (p12); UNLIMITED km WARRANTY (p16)'),
    (3, 'maruti_suzuki/baleno/latest/brochures/Baleno_Brochure.pdf', '11', '1d39274a6caebb0e61ec1b732ec017c880a24a57', '3 years or 1 00 000 km warranty - whichever is earlier'),
    (5, 'tata/harrier/latest/brochures/tata_harrier_brochure.pdf', '20', '93f7bf425f168db0f7a2a4b65b981ad21c7dd135', 'Warranty cover for 3 Years / 1 Lakh Kms, whichever ends earlier'),
    (6, 'tata/nexon_ev/latest/brochures/tata_nexon_ev_brochure.pdf', '38', '58523570196746ecf571af3cedb4cd0cd272ef73', 'Vehicle warranty 3 Year or 1,25,000 km; HV battery 8 years or 1,60,000 km'),
    (7, 'kia/carens_clavis/latest/brochures/kia_carens_clavis_brochure.pdf', '9', '28d5f1a99bc9e049de4b59d605786abdaec73edd', '3 Years Warranty for Unlimited km'),
    (8, 'honda/amaze/latest/brochures/honda_amaze_brochure.pdf', '31', '6785506d40494ff77b00b47c3acc65f223758f73', '3 YEAR UNLIMITED KILOMETERS STANDARD WARRANTY (rendered)'),
    (9, 'toyota/innova_hycross/latest/brochures/e-brochure-hycross.pdf', '1', 'b2360b0cd53691d6c36a371a8a7605c62146152a', 'WARRANTY UP TO 3 YEARS / 1 00 000 KM'),
    (11, 'toyota/urban_cruiser_hyryder/latest/brochures/toyota_urban_cruiser_hyryder_brochure.pdf', '13, 2', 'ec7984cef43e032e39ebe70bb496c9477befb5d1', 'WARRANTY UP TO 3 YEARS / 1,00,000 KM (p13); 8-year hybrid battery warranty (p2); battery km not printed'),
    (13, 'skoda/kushaq/latest/brochures/cartrade/kushaq_brochure.pdf', '28', '291ac68611472bb47017da2560c456f322bb171f', 'covered by warranty for a period of 4 years or 100,000 km'),
    (14, 'volkswagen/taigun/latest/brochures/volkswagen_taigun_brochure.pdf', '14', 'b2a396b599758b80a6643ad479eb21426eaa2c3c', '4 year / 100,000 km warranty'),
    (15, 'nissan/gravite/latest/brochures/nissan_gravite_brochure.pdf', '8', '8a6d94e92c2bc0b16d98e6e52cbe518624b03e3c', 'Standard warranty of 3 years or 100K kms whichever comes earlier'),
    (16, 'tata/tiago_ev/latest/brochures/tiago-brochure-evf-final.pdf', '33', 'c2aa56c0a2176ff75b381037466e2228b600cdc8', 'Vehicle Warranty 3 Year or 1,25,000 km; Battery Pack 8 Year or 1,60,000 km'),
    (17, 'tata/punch_ev/latest/brochures/tata_punch_ev_brochure.pdf', '24', 'a15a4187083a334de6653570864a1cba206dffd4', 'Vehicle Warranty 3 years or 1,25,000 km; Battery Pack 8 years or 1,60,000 km'),
    (18, 'kia/carens_clavis_ev/latest/brochures/kia_carens_clavis_ev_brochure.pdf', '11', '951ae4baf6eb4875e1ce2825232414b2634bb3f9', '3 Years Warranty for Unlimited km; High Voltage Battery Warranty of 8 years/ 1 60 000 km'),
]
GV = ('maruti_suzuki/grand_vitara/latest/brochures/maruti_suzuki_grand_vitara_brochure.pdf', '15', '023ce2e3d22ca4bd3a2cd1a9aded193273482e91', '3 YEARS/1 00 000 KM WARRANTY')
NEW_ROWS = [
    ('Grand i10 Nios', '100000.0', 'hyundai/grand_i10_nios/latest/brochures/Grand_i10_Nios_Brochure.pdf', '13', '352bd5977f225145e35687450ee4635e0d7416aa', 'Warranty upto 3 Years or 1 00 000 kms whichever occurs earlier'),
    ('Aura', '100000.0', 'hyundai/aura/latest/brochures/Aura_Brochure.pdf', '14', '410b212239fcb9c554f31b4975ce44a84ddbc981', 'Warranty upto 3 Years or 1 00 000 kms whichever occurs earlier'),
    ('Exter', 'Unlimited', 'hyundai/exter/latest/brochures/hyundai_exter_brochure.pdf', '14', '19da8e83686ae02be56cf6200d604906bc2b3779', 'Warranty upto 3 Years or unlimited km whichever occurs earlier'),
]
url = lambda p, pg, sha: f"offline_brochure:knowledge_base/sources/oem/{p}#page={pg};sha1={sha}"
c = sqlite3.connect(sys.argv[1], isolation_level=None); c.execute("PRAGMA foreign_keys=ON"); one = lambda q, *a: c.execute(q, a).fetchone()
tables = [r[0] for r in c.execute("select name from sqlite_master where type='table' and name<>'sqlite_sequence'")]
snap = lambda t: {r[0]: r for r in c.execute(f'select * from "{t}"')}
n = dict(rows_cited=0, cells_fixed=0, rows_added=0, released=0, amend=0)
def amend(wid, col, old, new, why):
    c.execute("insert into evidence_amendment(target_table,target_id,column_name,old_value,new_value,reason_code,phase) values ('warranty',?,?,?,?,?,?)", (wid, col, None if old is None else str(old), str(new), why, PHASE)); n["amend"] += 1
def cite(wid, p, pg, sha, printed):
    old = one("select source, source_url from warranty where id=?", wid); new = url(p, pg, sha)
    if old[1] == new: return
    c.execute("update warranty set source=?, source_url=? where id=?", (f"{SRC}: {printed}", new, wid)); n["rows_cited"] += 1
    amend(wid, "source", old[0], f"{SRC}: {printed}", REASON); amend(wid, "source_url", old[1], new, REASON)
c.execute("BEGIN IMMEDIATE")
try:
    before = {t: snap(t) for t in tables}
    schema = c.execute("select name, sql from sqlite_master where name not like 'sqlite_%' order by 1").fetchall(); canon = c.execute("select * from v_variant_canonical_q").fetchall()
    for wid, p, pg, sha, printed in VERIFIED: cite(wid, p, pg, sha, printed)
    p, pg, sha, printed = GV
    y, km = one("select warranty_years, warranty_km from warranty where id=12")
    if y != 3.0:
        assert (y, km) == (2.0, "40000.0"), (y, km)
        c.execute("update warranty set warranty_years=3.0, warranty_km='100000.0' where id=12"); n["cells_fixed"] += 2
        amend(12, "warranty_years", y, 3.0, FIX); amend(12, "warranty_km", km, "100000.0", FIX)
    cite(12, p, pg, sha, printed + "; battery figures not in this brochure")
    n["released"] += c.execute("update evidence_quarantine set released_at=datetime('now'), released_reason=? where target_table='warranty' and target_id=12 and released_at is null", (f"{PHASE}: corrected from brochure p15",)).rowcount
    for model, km, p, pg, sha, printed in NEW_ROWS:
        mid, mf = one("select id, manufacturer_id from model where name=?", model)
        if not one("select count(*) from warranty where model_id=?", mid)[0]:
            wid = c.execute("insert into warranty(manufacturer_id,model_id,warranty_years,warranty_km,source,source_url) values (?,?,3.0,?,?,?)", (mf, mid, km, f"{SRC}: {printed}", url(p, pg, sha))).lastrowid; n["rows_added"] += 1
            amend(wid, "warranty_km", None, km, "OEM_BROCHURE_MODEL_ROW_ADDED")
    after = {t: snap(t) for t in tables}
    for t in tables:
        if t == "evidence_amendment": assert set(before[t]) <= set(after[t]) and all(after[t][k] == before[t][k] for k in before[t])
        elif t == "warranty": assert set(before[t]) <= set(after[t])
        elif t == "evidence_quarantine":
            assert set(before[t]) == set(after[t])
            for k in before[t]:
                if after[t][k] != before[t][k]: assert after[t][k][1] == "warranty" and after[t][k][2] == 12
        else: assert after[t] == before[t], t
    assert c.execute("select name, sql from sqlite_master where name not like 'sqlite_%' order by 1").fetchall() == schema; assert c.execute("select * from v_variant_canonical_q").fetchall() == canon
    assert one("select warranty_years, warranty_km from v_warranty_q where id=12") == (3.0, "100000.0")
    assert one("select count(*) from warranty")[0] == 21 and one("select count(*) from v_active_quarantine where target_table='warranty'")[0] == 0
    assert one("pragma integrity_check")[0] == "ok"; assert len(c.execute("pragma foreign_key_check").fetchall()) == 297
    c.execute("COMMIT"); print("COMMITTED;", n, "active", one("select count(*) from v_active_quarantine")[0])
except Exception as ex:
    c.execute("ROLLBACK"); import traceback; traceback.print_exc(); print("ROLLBACK:", repr(ex)); sys.exit(1)
