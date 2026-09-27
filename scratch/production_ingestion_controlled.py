#!/usr/bin/env python3
"""
PHASE 6 OEM CONTROLLED PRODUCTION INGESTION
Authorized single-run production ingestion into knowledge_base/carrec_kb.db.
Mirrors strict_shadow_ingestion.py calling conventions exactly.
"""
import os
import json
import sqlite3
import shutil
import traceback
from collections import defaultdict

from knowledge_base.ingestion.oem.extractor.classifier import classify_layout
from knowledge_base.ingestion.oem.extractor.extractor import OEMBrochureExtractor
from knowledge_base.ingestion.oem.extractor.profiler import profile_pdf
from knowledge_base.ingestion.oem.ingest_oem import process_oem_payload, resolve_oem_generation

PROD_DB        = "knowledge_base/carrec_kb.db"
BACKUP_DB      = "scratch/carrec_kb_phase6_final_preproduction_backup.db"
IDEM_DB        = "scratch/carrec_kb_phase6_postproduction_idempotency.db"
MANIFEST_PATH  = "knowledge_base/sources/oem/brochure_manifest.json"
EXPECTED_CHECKSUM = "6ea3b931f7c157880445688665c500fb368a0c7b"
TABLES         = ['manufacturer', 'model', 'generation', 'variant',
                  'powertrain', 'source_observation', 'field_provenance']

# ── helpers ────────────────────────────────────────────────────────────────────

def sha1(path):
    import hashlib
    h = hashlib.sha1()
    with open(path, 'rb') as f:
        while True:
            chunk = f.read(65536)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()

def integrity(db_path):
    conn = sqlite3.connect(db_path)
    r = conn.execute("PRAGMA integrity_check;").fetchone()[0]
    conn.close()
    return r

def row_counts(db_path):
    conn = sqlite3.connect(db_path)
    counts = {}
    for t in TABLES:
        counts[t] = conn.execute(f"SELECT count(*) FROM {t}").fetchone()[0]
    conn.close()
    return counts

def get_table_snapshot(db_path, table):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute(f"SELECT * FROM {table}")
    rows = {row['id']: dict(row) for row in c.fetchall()}
    conn.close()
    return rows

def diff_snapshots(snap_before, snap_after):
    diffs = {'added': [], 'deleted': [], 'modified': []}
    for k in snap_after:
        if k not in snap_before:
            diffs['added'].append(snap_after[k])
        elif snap_before[k] != snap_after[k]:
            mods = {}
            for col in snap_after[k]:
                if snap_after[k][col] != snap_before[k][col]:
                    mods[col] = {'old': snap_before[k][col], 'new': snap_after[k][col]}
            if mods:
                diffs['modified'].append({'id': k, 'changes': mods})
    for k in snap_before:
        if k not in snap_after:
            diffs['deleted'].append(snap_before[k])
    return diffs

# ── ingestion pass ─────────────────────────────────────────────────────────────

def run_ingestion_pass(db_path, pass_name, fatal_on_unexpected=True):
    """Run the OEM ingestion pass against db_path.
    Mirrors strict_shadow_ingestion.py exactly.
    Returns per-model status dict.
    """
    with open(MANIFEST_PATH, 'r') as f:
        manifest = json.load(f)

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.isolation_level = None  # manual transaction control

    statuses = {}

    for key, info in manifest.items():
        artifact_path = info.get('artifact_path')
        make  = info['manufacturer']
        model = info['model']

        # ── PDF availability & text check ─────────────────────────────────────
        if not artifact_path or not os.path.exists(artifact_path):
            statuses[key] = 'PDF_TEXT_FAILURE'
            print(f"[PDF_TEXT_FAILURE] {key}: artifact path missing")
            continue

        try:
            sig = profile_pdf(artifact_path)
            if sig.is_cid_corrupted or not (sig.text_pages > 0):
                statuses[key] = 'PDF_TEXT_FAILURE'
                print(f"[PDF_TEXT_FAILURE] {key}: no extractable text")
                continue

            strategy = classify_layout(artifact_path, make, model)
            extractor = OEMBrochureExtractor(strategy)
            payloads  = extractor.execute(artifact_path)

        except Exception as e:
            err_str = str(e)
            if "Unsupported" in err_str or "Failed" in err_str or "Cannot" in err_str or "quarantine" in err_str.lower():
                statuses[key] = 'CLASSIFICATION_UNKNOWN'
                print(f"[CLASSIFICATION_UNKNOWN] {key}: {err_str}")
            elif "borderless" in err_str.lower() or "structurally locate" in err_str.lower():
                statuses[key] = 'EXTRACTION_FAILURE'
                print(f"[EXTRACTION_FAILURE] {key}: {err_str}")
            else:
                print(f"[UNEXPECTED_ERROR] {key} (Extraction):")
                traceback.print_exc()
                statuses[key] = 'UNEXPECTED_ERROR'
                if fatal_on_unexpected:
                    conn.close()
                    raise RuntimeError(f"Unexpected extraction error on {key}: {e}")
            continue

        if not payloads:
            statuses[key] = 'EXTRACTION_FAILURE'
            print(f"[EXTRACTION_FAILURE] {key}: extractor returned no payloads")
            continue

        # ── DB ingestion with explicit transaction ─────────────────────────────
        try:
            conn.execute('BEGIN TRANSACTION')

            make_slug  = make.lower().replace(" ", "-")
            model_slug = model.lower().replace(" ", "-")

            gen_id = resolve_oem_generation(conn, make, model, None)

            process_oem_payload(conn, payloads, make_slug, model_slug, 1, gen_id)

            conn.execute('COMMIT')
            statuses[key] = 'SUCCESS'
            print(f"[SUCCESS] {key}")

        except Exception as e:
            try:
                conn.execute('ROLLBACK')
            except Exception:
                pass
            err_str = str(e)
            if "Generation Pinning Failed" in err_str or "0 matches found" in err_str:
                statuses[key] = 'RESOLUTION_FAILURE'
                print(f"[RESOLUTION_FAILURE] {key}: {err_str}")
            else:
                print(f"[UNEXPECTED_ERROR] {key} (Ingestion):")
                traceback.print_exc()
                statuses[key] = 'UNEXPECTED_ERROR'
                if fatal_on_unexpected:
                    conn.close()
                    raise RuntimeError(f"Unexpected ingestion error on {key}: {e}")

    conn.close()

    # summary
    counts = defaultdict(int)
    for s in statuses.values():
        counts[s] += 1
    print(f"\n--- {pass_name} MODEL STATUSES ---")
    for k in sorted(counts):
        print(f"  {k}: {counts[k]}")
    return statuses

# ── main ───────────────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("PHASE 6 OEM CONTROLLED PRODUCTION INGESTION")
    print("=" * 60)

    # ── 1. PRE-RUN SAFETY ─────────────────────────────────────────────────────
    prod_cksum = sha1(PROD_DB)
    backup_cksum = sha1(BACKUP_DB)
    print(f"\nPre-run production checksum : {prod_cksum}")
    print(f"Backup checksum             : {backup_cksum}")

    if prod_cksum != EXPECTED_CHECKSUM:
        raise RuntimeError(
            f"ABORT: Production checksum mismatch!\n"
            f"  expected: {EXPECTED_CHECKSUM}\n"
            f"  actual  : {prod_cksum}"
        )
    print("Checksum: VERIFIED (matches expected pristine)")

    prod_integrity = integrity(PROD_DB)
    backup_integrity = integrity(BACKUP_DB)
    print(f"\nProduction PRAGMA integrity_check: {prod_integrity}")
    print(f"Backup PRAGMA integrity_check    : {backup_integrity}")
    if prod_integrity != 'ok':
        raise RuntimeError(f"ABORT: Production DB integrity check failed: {prod_integrity}")
    if backup_integrity != 'ok':
        raise RuntimeError(f"ABORT: Backup DB integrity check failed: {backup_integrity}")

    pre_counts = row_counts(PROD_DB)
    print("\nPre-run row counts:")
    for t, c in pre_counts.items():
        print(f"  {t}: {c}")

    # ── 2. CAPTURE PRE-RUN SNAPSHOT ───────────────────────────────────────────
    print("\nCapturing pre-run logical snapshot...")
    snap0 = {t: get_table_snapshot(PROD_DB, t) for t in TABLES}
    print("Snapshot captured.")

    # ── 3. CONTROLLED INGESTION ───────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("STARTING CONTROLLED PRODUCTION INGESTION")
    print("=" * 60)

    # fatal_on_unexpected=False so that expected extraction failures (PDF, borderless, quarantine)
    # do NOT abort the run, but true unexpected DB errors still propagate after logging.
    # We raise only from the DB transaction block.
    try:
        statuses = run_ingestion_pass(PROD_DB, "PRODUCTION INGESTION", fatal_on_unexpected=True)
    except RuntimeError as e:
        print(f"\nFATAL: Production ingestion aborted: {e}")
        print("Restoring backup...")
        shutil.copy2(BACKUP_DB, PROD_DB)
        restored_cksum = sha1(PROD_DB)
        print(f"Restored checksum: {restored_cksum}")
        if restored_cksum != EXPECTED_CHECKSUM:
            print("ERROR: Restore checksum mismatch! Manual intervention required.")
        return

    # ── 5. POST-INGESTION LOGICAL DIFF ────────────────────────────────────────
    print("\nCapturing post-run logical snapshot...")
    snap1 = {t: get_table_snapshot(PROD_DB, t) for t in TABLES}

    print("\n--- POST-INGESTION DIFFS ---")
    diffs = {}
    has_unexpected_canonical_mutation = False
    for t in TABLES:
        d = diff_snapshots(snap0[t], snap1[t])
        diffs[t] = d
        print(f"Table {t}: {len(d['added'])} added, {len(d['deleted'])} deleted, {len(d['modified'])} modified")
        if t in ('variant', 'powertrain') and d['modified']:
            for m in d['modified']:
                print(f"  {t.capitalize()} ID={m['id']} mutations: {m['changes']}")
        if t in ('manufacturer', 'model', 'generation', 'powertrain'):
            if d['added'] or d['deleted'] or d['modified']:
                print(f"  UNEXPECTED CANONICAL MUTATION IN {t.upper()}!")
                has_unexpected_canonical_mutation = True

    # Verify the one expected variant mutation
    var_mods = diffs['variant']['modified']
    expected_mutation_ok = False
    if len(var_mods) == 1:
        m = var_mods[0]
        if (m['id'] == 669
                and 'paddle_shifters' in m['changes']
                and m['changes']['paddle_shifters']['old'] is None
                and m['changes']['paddle_shifters']['new'] == 0):
            expected_mutation_ok = True
            print(f"\n[CANONICAL MUTATION] EXPECTED: variant_id=669 paddle_shifters NULL->0 ✓")
    elif len(var_mods) == 0:
        print("\n[CANONICAL MUTATION] variant_id=669 paddle_shifters was NOT applied — missing expected mutation")
    else:
        print(f"\n[CANONICAL MUTATION] UNEXPECTED: {len(var_mods)} variant modifications found")
        for m in var_mods:
            print(f"  Variant {m['id']}: {m['changes']}")
        has_unexpected_canonical_mutation = True

    # ── 6. PROVENANCE RECONCILIATION ──────────────────────────────────────────
    new_prov = diffs['field_provenance']['added']
    new_obs  = diffs['source_observation']['added']

    prov_accepted  = sum(1 for p in new_prov if p.get('decision','').lower() == 'accepted')
    prov_rejected  = sum(1 for p in new_prov if p.get('decision','').lower() == 'rejected')
    prov_confirmed = sum(1 for p in new_prov if p.get('decision','').lower() == 'confirmed')
    prov_other     = len(new_prov) - prov_accepted - prov_rejected - prov_confirmed

    print(f"\n--- PROVENANCE RECONCILIATION ---")
    print(f"  Total new field_provenance rows : {len(new_prov)}")
    print(f"  Accepted  : {prov_accepted}")
    print(f"  Confirmed : {prov_confirmed}")
    print(f"  Rejected  : {prov_rejected}")
    print(f"  Other     : {prov_other}")

    print(f"\n--- SOURCE OBSERVATION RECONCILIATION ---")
    print(f"  Total new source_observation rows: {len(new_obs)}")

    # ── 8. POST-PRODUCTION IDEMPOTENCY CHECK ──────────────────────────────────
    print(f"\nCreating idempotency copy: {IDEM_DB}")
    shutil.copy2(PROD_DB, IDEM_DB)

    print("Running idempotency pass (Pass 2) against isolated copy...")
    run_ingestion_pass(IDEM_DB, "IDEMPOTENCY PASS", fatal_on_unexpected=True)

    snap2 = {t: get_table_snapshot(IDEM_DB, t) for t in TABLES}

    print("\n--- IDEMPOTENCY DIFFS (EXPECT ALL ZERO) ---")
    idempotent = True
    for t in TABLES:
        d = diff_snapshots(snap1[t], snap2[t])
        print(f"Table {t}: {len(d['added'])} added, {len(d['deleted'])} deleted, {len(d['modified'])} modified")
        if d['added'] or d['deleted'] or d['modified']:
            idempotent = False
    print(f"IDEMPOTENCY: {'TRUE' if idempotent else 'FALSE'}")

    # ── 9. FINAL PRODUCTION VALIDATION ────────────────────────────────────────
    post_integrity = integrity(PROD_DB)
    post_cksum     = sha1(PROD_DB)
    print(f"\nPost-run production PRAGMA integrity_check: {post_integrity}")
    print(f"Post-run production checksum: {post_cksum}")

    # ── 10. VERDICT ───────────────────────────────────────────────────────────
    unexpected_err_count = sum(1 for s in statuses.values() if s == 'UNEXPECTED_ERROR')
    verdict_ok = (
        post_integrity == 'ok'
        and idempotent
        and expected_mutation_ok
        and not has_unexpected_canonical_mutation
        and unexpected_err_count == 0
    )

    verdict = "PRODUCTION_INGESTION_SUCCESS" if verdict_ok else "PRODUCTION_INGESTION_FAILED"

    if not verdict_ok:
        print("\nRollback triggered: restoring backup...")
        shutil.copy2(BACKUP_DB, PROD_DB)
        restored_cksum = sha1(PROD_DB)
        print(f"Restored checksum: {restored_cksum}")
        if restored_cksum != EXPECTED_CHECKSUM:
            print("ERROR: Restore checksum mismatch!")
        else:
            print("Rollback verified: production DB restored to pristine checksum.")

    # ── Build results dict for report ─────────────────────────────────────────
    results = {
        'pre_run_checksum'    : prod_cksum,
        'backup_checksum'     : backup_cksum,
        'post_run_checksum'   : post_cksum,
        'pre_integrity'       : prod_integrity,
        'post_integrity'      : post_integrity,
        'statuses'            : statuses,
        'source_obs_added'    : len(new_obs),
        'field_prov_added'    : len(new_prov),
        'prov_accepted'       : prov_accepted,
        'prov_confirmed'      : prov_confirmed,
        'prov_rejected'       : prov_rejected,
        'prov_other'          : prov_other,
        'canonical_mutation_ok': expected_mutation_ok,
        'unexpected_canonical' : has_unexpected_canonical_mutation,
        'unexpected_errors'   : unexpected_err_count,
        'idempotent'          : idempotent,
        'variant_mods'        : var_mods,
        'pre_row_counts'      : pre_counts,
        'verdict'             : verdict,
        'new_prov_sample'     : new_prov[:10],
        'new_obs_sample'      : new_obs[:10],
    }

    with open('scratch/production_ingestion_results.json', 'w') as f:
        import json as _json
        _json.dump(results, f, indent=2, default=str)

    print(f"\n{'=' * 60}")
    print(f"FINAL VERDICT: {verdict}")
    print(f"{'=' * 60}")
    return results

if __name__ == '__main__':
    main()
