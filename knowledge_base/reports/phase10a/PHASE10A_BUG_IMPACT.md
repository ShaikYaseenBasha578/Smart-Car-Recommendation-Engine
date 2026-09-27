# Phase 10A: Bug Impact Analysis (read-only)

**Date:** 2026-09-27. **Branch:** kb/phase-10-0-versioning.

**Production DB:** `knowledge_base/carrec_kb.db`. SHA-1 `1e3eb6795452860276eca24e7dd1f52e85e67a93` at start and at end, and `lsof` was empty both times.

**Method:**
- Every query ran on `/tmp/carrec_audit/p10a/carrec_kb.db`, a byte-identical copy of production.
- The query scripts are saved next to this report: `b1.py`, `b2.py`, `b3.py`. B4–B6 were one-off inline queries; each one is quoted where it is used below.

**Tags:**
- **[VERIFIED]** means the query result is reproducible from the named CSV and script.
- **UNDETERMINABLE** means the DB cannot settle it. Real-world correctness always needs an external source.

**Terms used below:**
- **Live evidence** means a `field_provenance` row whose `source_observation` still exists.
- **Sole-source** means the canonical value has no `accepted` or `confirmed` provenance from any other source.

**Scope change approved by the user:** B3 grew from the 35 rows the audit stated to the full CarWale structural mis-resolution set of 333 observations (see B3).

---

## B1: "Not mentioned" written as 0 (V3Cars and 91wheels)

**1. Affected rows** (`B1_affected.csv`) [VERIFIED, b1.py]
- 410 `field_provenance` rows with `decision='accepted' AND accepted_value='0'` from source 3 (V3Cars, 285 rows) or source 2 (91wheels, 125 rows). This matches the audit's counts.
- 410 canonical `variant` cells hold these values. All 410 are still 0 today.
- By field:

| Field | Rows |
|---|---|
| heads_up_display | 153 |
| wireless_charging | 131 |
| cruise_control | 93 |
| ventilated_front_seats | 21 |
| tyre_pressure_monitoring_system | 12 |

**2 and 3. Canonical contamination and classification** [VERIFIED]

| Class | V3Cars | 91wheels | Total |
|---|---|---|---|
| SOLE-SOURCE: no other source for this variant and field | 221 | 58 | **279** |
| CORROBORATED: another source gives 0 | 42 | 62 | **104** |
| CONTRADICTED: another source gives a non-zero value | 22 | 5 | **27** |

Caveats on the CORROBORATED and CONTRADICTED classes:
- **25 of the 91wheels CORROBORATED rows** are corroborated only by a V3Cars absent→0 row, which is itself a B1 row. That corroboration is weak.
- **Interaction with B3:** 6 CORROBORATED rows and 5 CONTRADICTED rows rely only on evidence from CarWale observations flagged in B3. Their classification is therefore UNDETERMINABLE until B3 is fixed.
- **91wheels mechanism is UNDETERMINABLE.** V3Cars converts absence to 0 in code (`field_map_v3cars.py:24`). For 91wheels, the DB cannot show whether a 0 came from an explicit "No" or from a missing value.

**4. Authority effects**
None directly: every B1 decision is `new_field`.

**5. Candidate fix class**
- **Quarantine:** set the 279 SOLE-SOURCE values and the 27 CONTRADICTED values back to NULL (unknown).
- **Needs-human-review:** the 27 CONTRADICTED values. Keep the 104 CORROBORATED values and re-classify them after B3 is fixed.

**6. Reversibility and proof**
- The fix is reversible: the original 0s stay recorded in `field_provenance`, and the backup keeps the prior canonical values.
- **Proof of a correct fix:** a per-cell diff of `variant`, backup vs post-fix. It must contain exactly the approved (variant, field) pairs, each going 0→NULL, and no other cell may change.

## B2: 52 OEM brochure observations filed under source_id 1

**1. Affected rows** (`B2_affected.csv`) [VERIFIED, b2.py]
- 52 `source_observation` rows (ids 3669–3720, `source_url='offline_brochure'`).
- 133 `field_provenance` rows: 104 confirmed, 28 rejected, 1 accepted.
- Total: 185 rows.

**2. Canonical contamination**
- 1 canonical value comes solely from OEM evidence: `paddle_shifters=0` [VERIFIED].
- The other 132 rows did not change any canonical value.

**4. Authority effects if OEM were tier 1**
In the current updater logic (tier 1 < every other tier), all 28 rejections would flip to *accepted* [VERIFIED]. The flips are listed in the CSV with the value `WOULD_FLIP_TO_ACCEPTED`. They include:
- **Junk values (UNDETERMINABLE by design, extraction artifacts):**
  - `sunroof='Standard'`: variants 142 and 145.
  - `sunroof='[Vector:Curve]'`: variants 637, 638 and 642.
- **Value reversals:**
  - 0→1: hill_assist on 7 variants, TPMS on 3, and rear_ac_vents, HUD, cruise_control and ventilated_front_seats (on 145).
  - 1→0: TPMS, hill_assist, android_auto and apple_carplay on variants 669, 671 and 677; connected_car_features on 142.
- Whether the brochure value or the current value is correct is **UNDETERMINABLE** from the DB. The observation `raw_name`s ("V O O", "SV - - -") show that column alignment is unreliable.

**5. Candidate fix class**
- **Re-attribute** `source_id` from 1 to 6 **without** re-running any decisions.
- Mark all 52 observations for **needs-human-review** before any re-evaluation of authority.
- **Never** simply re-tier: that would push junk values into canonical.

**6. Reversibility and proof**
- Reversible: the change is a single-column UPDATE on 52 rows.
- **Proof of a correct fix:** a diff showing only `source_observation.source_id` changed on ids 3669–3720, with 0 changes to `field_provenance` or `variant`.

## B3 (expanded): CarWale structural mis-resolution

**1. Affected rows** (`B3_affected.csv`) [VERIFIED, b3.py]

333 CarWale observations are affected across 147 variants:

| Category | Observations |
|---|---|
| Transmission contradicts the resolved variant (e.g. obs 2820 "V Petrol Automatic" → variant 647 "V Petrol Manual") | 226 |
| Fuel contradicts (e.g. obs 2858 "SX Premium Petrol…" → variant 23 "…Diesel…") | 70 |
| Both contradict (e.g. obs 2928 "HX 5 Diesel 1.5L Turbo Automatic (TC)" → variant 152 "HX5 1.0 Turbo Petrol MT") | 33 |
| Creta E/EX swap (obs 2842 and 2843) | 2 |
| Resolved to variant 820 (overlaps the categories above) | 33 |

These observations carry **2,089 `field_provenance` rows**. A further **264** observations have name-only mismatches on variants with several CarWale observations. They are listed in `B3_loose_name_mismatch_UNDETERMINABLE.csv`; naming style alone cannot settle whether they are wrong.

**2. Canonical contamination** [VERIFIED]

| Effect | Provenance rows |
|---|---|
| **SOLE_SOURCE_CANONICAL**: accepted, with no other live accepted or confirmed evidence | 14 |
| Accepted but supported elsewhere | 5 |
| **CONFIRMATION_ONLY**: false corroboration that inflates evidence counts | 1,638 |
| REJECTED_INERT | 432 |

- The main damage is to the evidence ledger, not to canonical values: 1,638 confirmations come from the wrong vehicle configuration. This also weakens B1's CORROBORATED class.
- **Probable mechanism (UNDETERMINABLE as a proven cause):**
  - The CarWale adapter passes no fuel, cc or price.
  - `validate_structured` skips null comparisons, so fuel/transmission checks never fire.
  - The resolver matches through the 91wheels alias table.

**5. Candidate fix class**
- **Quarantine:** set `resolution_status` to a review state on the 333 observations, and exclude their provenance from corroboration counts.
- **Needs-human-review:** the 14 SOLE_SOURCE canonical values.
- The Creta swap pair is a candidate for a deterministic re-link, but only after human confirmation.

**6. Reversibility and proof**
- Reversible: status and flag changes only; no provenance rows are deleted.
- **Proof of a correct fix:** a diff limited to the listed observation ids, plus an unchanged `variant` table except for the approved sole-source cells.

## B4: Edition identity errors (variants 833, 814, 826)

**1. Affected rows** (`B4_affected.csv`) [VERIFIED, inline query]
- 3 `variant` rows:
  - 833: name says "1.5L Turbo DCT", but it sits on the 1.0L 114 bhp TC powertrain.
  - 814: "ZX … Black Edition", with base 649 "VX Petrol Manual".
  - 826: "Alpha Plus … Smart Hybrid", with base 218 "Alpha MT".
- 85 `field_provenance` rows on these variants.

**2. Canonical contamination** [VERIFIED]
- The variants' own values: 833 has boot_space and TPMS; 814 has boot_space and cruise_control; 826 has boot_space. These come from CarWale edition observations, and some of those observations are also B3-flagged (e.g. 814 receives "ZX Petrol Automatic Black Edition").
- **Derived contamination:** through `v_effective_variant`, each variant inherits 33–34 fields from its base (price, dimensions, airbags, mileage). For 833 the powertrain and transmission themselves contradict the name.
- Whether the inherited values apply is **UNDETERMINABLE**.

**5. Candidate fix class**
**Needs-human-review.** The correct base, powertrain and transmission need external evidence. The interim step would be to quarantine the rows as UNRESOLVED_EDITION.

**6. Reversibility and proof**
Each fix is a small set of column changes on 3 variant rows, so the diff is fully enumerable.

## B5: BNCAP test 27 (Harrier.EV) mapped to ICE-only model 30

**1. Affected rows** (`B5_affected.csv`) [VERIFIED]
- `safety_test` 27 (RESOLVED, 5★/5★, justification "Matched manufacturer and model systematically.").
- `safety_test_applicability` 14 (model 30, gen 50, MODEL_LEVEL).
- `source_observation` 3747.
- Model 30 has only Diesel (14) and Petrol (12) variants.

**2. Contamination**
- Harrier appears to have 2 BNCAP results: test 27 (EV) and test 33 (FAMILY_LEVEL Safari/Harrier). An EV crash result is applied to ICE vehicles.
- No canonical `variant` fields are affected. The recommender does not read the KB, so there is no live user impact [VERIFIED in the audit].

**5. Candidate fix class**
Set NO_MATCH: `safety_test.resolution_status` → NO_MATCH, delete applicability row 14, and sync observation 3747. Deleting the row is acceptable because it is fully backed up; the alternative is a flag.

**6. Reversibility and proof**
The fix is fully captured by one row delete plus 2 status updates.

## B6: 3 BNCAP observations stale after 9B

**1. Affected rows** (`B6_affected.csv`) [VERIFIED]
- `source_observation` 3729, 3736 and 3737 are UNRESOLVED.
- `safety_test` 9, 16 and 17 are RESOLVED, with applicability rows 21, 22 and 23.
- There are no other mismatches between BNCAP tests and their observations.

**2. Contamination**
None to canonical values. Queries that filter on the observation status get the wrong answer.

**5. Candidate fix class**
Status sync: set the 3 observations to RESOLVED.

**6. Reversibility and proof**
A 3-row diff on `resolution_status` only.

---

## Proposed Phase 10B fix order (by contamination severity)

1. **B3 quarantine.** It is the largest: 333 mis-resolved observations and 1,638 false confirmations corrupt the evidence ledger, and B1's classification depends on it.
2. **B1 quarantine of 279 sole-source and 27 contradicted zeros.** These 306 canonical facts were never stated by any source; this directly breaks PRECISION > COVERAGE.
3. **B5 set to NO_MATCH.** A wrong-powertrain safety result is a high-stakes error that would surface as soon as any consumer reads the KB.
4. **B2 re-attribute only (no re-tier) and human review.** This fixes the evidence class. Re-evaluating authority must wait until extraction quality is reviewed.
5. **B4 human review of 3 edition variants.** The scope is small but external evidence is required; about 100 derived values depend on it.
6. **B6 status sync.** It is trivial and has no canonical impact, so it can be bundled with B5 in one BNCAP transaction.
