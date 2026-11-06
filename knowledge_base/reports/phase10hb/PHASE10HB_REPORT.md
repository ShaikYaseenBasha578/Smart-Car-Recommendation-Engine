# Phase 10H-b — quarantine 3 more resolver mislinks

**Status: APPLIED to prod (2026-11-06 14:55 UTC).** Prod SHA-1 `8074a9dd67829042ba04a16bbe9c5a26702c88c6` → `9bf0bc7a23bc95508968abe2025ceae3787a1bed`. Owner decision 4 (2026-11-06).

## 0. Access
P11: only the read-only VM holder (FD 2613r); no `-wal`/`-shm`; SHA-1 rechecked right before the apply (`access_before.txt`, `apply_prod_log.txt`).

## 1. Backup
`knowledge_base/backups/pre_phase10hb_20261106T145518Z.db`, `.backup` from a verified byte copy; `.sha3sum` `234d049f…` equal (`backup_log.txt`).

## 2. Change table
| Observation | Source says | Linked to | Mismatch | Right variant |
|---|---|---|---|---|
| 955 | 91wheels "X-Line (A) G1.5 Smartstream T-GDI 7AT (DCT)" | 206 X-Line(A) 1.5 Diesel AT | fuel | 191 |
| 1151 | 91wheels "AX7L Diesel 4WD AT (TC)" | 690 AX7 L 2WD Automatic | drivetrain | 693 |
| 1157 | 91wheels "AX7L 4WD MOCHA INTRS Diesel" | 691 AX7 L 2WD Manual | drivetrain | 694 |

Reason code `H1_RESOLVER_MISLINK`, phase `10H-b`. A fresh blind subagent judged all three mislinks. They carry **no provenance rows**, so no cell is left without evidence and no canonical value changes. Fewer than 20 rows; the validation was done anyway.

## 3. Verification
- Dry run on a fresh copy: 3 inserts, schema identical, diff = 3 quarantine rows + sequence counter. Idempotency re-run: 0 inserts, empty diff.
- In-transaction invariants: every other table unchanged, canonical view identical, schema identical, 1,386 active, integrity ok, 297 FK orphans.
- Prod: same result; `integrity_check` ok; `foreign_key_check` 297; checkpoint 0|0|0. Prod-vs-before diff equals the dry-run diff (timestamps masked).

## 6. Schema
None.

## 7. App
No catalogue value changes, so no export and no PR.

## 8. Prod SHA-1
Before `8074a9dd…`; after `9bf0bc7a…`.

## 9. Message for the ranking track
KB 10H-b: 3 more mislinked observations quarantined; no value changed; no app PR.

## 10. Deferred
Re-linking waits for re-ingestion (P15).
