# Phase 10L — warranty provenance, Grand Vitara correction, export wiring (backlog item 6)

**Status: APPLIED to prod (2026-11-06).** Prod SHA-1 `459e4a995ad5a52622e98e26449f36772dcd28ae` → `acf32b47e19c711d9f8bdc332132c5df6510c489`.

## 0. Access / 1. Backup
P11 held; backup verified (`apply_prod_log.txt`, `backup_log.txt`). All PDF SHA-1s were computed at build time; exact values are in `apply_phase10l.py`.

## 2. Change table
No DDL: provenance goes in the existing `warranty.source` and `source_url` columns, each change logged in `evidence_amendment`.

| Row | Figures | Result | Source |
|---|---|---|---|
| 12 Grand Vitara | 2 / 40,000 → **3 / 100,000** | corrected; 2 10E quarantines released | GV brochure p15 |
| New: Grand i10 Nios, Aura | 3 / 100,000 | model rows added (they contradict Hyundai's make row) | p13, p14 |
| New: Exter | 3 / unlimited | model row added | p14 |
| 2 Mahindra, 3 Maruti, 5 Tata, 7 Kia, 8 Honda, 9 Toyota, 13 Skoda, 14 VW, 15 Nissan | unchanged | cited | one model's brochure each (`apply_phase10l.py`) |
| 6 Nexon EV, 16 Tiago EV, 17 Punch EV, 18 Clavis EV | unchanged | cited, battery included | p38, p33, p24, p11 |
| 11 Hyryder | unchanged | cited; the brochure gives battery years, no km | p13, p2 |

**Not cited (no change, P9):** 1 Hyundai make row (contradicted for 2 models, supported for 1), 4 MG (no vehicle warranty figure on disk), 10 Renault (Triber's is CNG-specific, Duster gives years only). GV battery figures: not in its brochure.

A make-wide row is cited from one model's brochure and applies to the other models of that make through the existing make-level design. It isn't a cross-model value write: the figures were already in the KB and nothing contradicts them (P3).

## 3. Verification
Dry run and prod: 15 rows cited, 2 cells corrected, 3 rows added, 2 quarantines released, 35 amendments; 1,378 active. `EXCEPT` diff: only warranty, amendments, quarantine rows, sequence; schema and canonical view identical. Idempotency: empty diff. Prod diff equals the dry-run diff (timestamps masked). `integrity_check` ok; 297 FK orphans. P13: no paper field touched.

## 6. Schema
None. `has_provenance` in `v_warranty_q` stays constant 0 (changing it is DDL); the citation is in `source_url`.

## 7. App
`app/kb-10l-warranty`, stacked on `app/kb-10k-export`, with screenshots. Catalogue SHA-1 `708a6769…`, two identical runs. Whitelist: 4 new columns; **no existing column changed** (checked). `pytest` 353 passed.

## 8. Prod SHA-1
`459e4a99…` → `acf32b47…`.

## 10. Noted
e VITARA prints an 8 years / 1,60,000 km battery warranty (p23) with no KB row. Adding one is cheap but outside this item's 18 rows; left for a later pass.
