# PHASE 6 OEM FINAL GATE REPORT

## 1. PRODUCTION DB NON-MUTATION
- **Checksum Before:** `6ea3b931f7c157880445688665c500fb368a0c7b`
- **Checksum After:** `6ea3b931f7c157880445688665c500fb368a0c7b`
- **Integrity Check:** `ok`
- **Verdict:** PASS.

## 2. PROVENANCE RECONCILIATION
The complete shadow execution generated exactly 46 new provenance rows, perfectly reconciling to:
- **Total:** 46
- **Confirmed:** 30
- **Rejected:** 16
- **Accepted:** 0
- **Other:** 0
- **Verdict:** PASS.

## 3. TRUE CANONICAL DIFF
A strict logical diff of the `variant` and `powertrain` tables was conducted across Pass 1.
- **Variant:** 0 additions, 0 deletions, 0 modifications.
- **Powertrain:** 0 additions, 0 deletions, 0 modifications.
- **Verdict:** PASS.

## 4. TRUE IDEMPOTENCY
A strict logical diff of all relevant tables (including `source_observation` and `field_provenance`) across Pass 2 confirmed exact idempotency.
- **Pass 2 Additions:** 0
- **Pass 2 Deletions:** 0
- **Pass 2 Modifications:** 0
- **Verdict:** PASS.

## 5. BOOLEAN SEMANTICS AUDIT
Audited boolean normalizers and executed explicit test cases.
- **Issue Discovered & Fixed:** `normalize_sunroof` originally mapped explicit negative values (`"no"`, `"false"`, `"0"`) to `None` in an attempt to protect the DB from literal overwrites. However, treating explicit OEM absence as "Unknown" bypasses conflict resolution logic. We updated `normalize_sunroof` to return `0`, fully aligning its contract with `normalize_boolean`.
- **Contract Defined:**
  - Explicitly present (`"yes"`, `"true"`, `"1"`, `"standard"`) -> `1` / `"Standard"`
  - Explicitly absent (`"no"`, `"false"`, `"0"`, `"not available"`) -> `0`
  - Unknown/Unreported/Ambiguous (`"-"`, `"available"`, `"unknown"`, `None`) -> `None`
- **Verdict:** PASS.

## 6. SCRIPT SAFETY AUDIT
- The audit harness `scratch/audit_shadow_ingestion.py` was stripped of silent exception handling and cleanly executed without raising hidden errors.
- The production script `scratch/final_production_ingestion.py` was rewritten to calculate actual pre/post DB row deltas rather than looping counters. Model-level transaction rollbacks (`BEGIN`/`ROLLBACK`) are guaranteed.
- **Verdict:** PASS.

## 7. CORPUS LEVEL MAPPING AUDIT
A script was run across all 62 models to collect every unmapped field.
- **Total Extracted Non-Identity:** 11,518
- **Total Mapped:** 393
- **Total Unmapped:** 11,125
- **Unique Unmapped Field Names:** 1,321

**Critical Findings:** While many unmapped fields are legitimately marketing text, several definitively CANONICALIZABLE fields are being silently dropped due to slight string variations.
- `'electronic stability control (esc)'` (Count: 39)
- `'tyre pressure monitoring system(tpms) highline'` (Count: 25)
- `'abs(anti-lock braking system) with ebd'` (Count: 25)
- `'isofix'` (Count: 25)
- `'keyless entry system'` (Count: 28)
- `'automatic headlamps'` (Count: 32)
- `'rear defogger'` (Count: 45)

Because these are explicit canonical DB fields being dropped silently, this constitutes a blocker.

- **Verdict:** FAIL.

## FINAL GATE VERDICT
**NOT_READY**

### Exact Reasons:
While isolation, idempotency, provenance math, boolean semantics, and script safety were all mathematically proven to perform flawlessly, the corpus-level field mapping is silently dropping highly prevalent, strictly canonicalizable fields due to missing synonyms in `OEM_FIELD_RULES`.

### Remaining Blockers:
1. Missing mapping rules in `OEM_FIELD_RULES` for heavily requested safety/convenience fields (ESC, ABS, Isofix, TPMS variations).

### Production Ingestion Script:
The rewritten `scratch/final_production_ingestion.py` is fully transaction-safe and correctly calculates DB deltas instead of looping counters. It will be safe to authorize once the mapping blocker is resolved.
