# Phase 10I-1a — Finding C blast-radius audit (read-only)

Date: 2026-11-06. Read-only on a byte copy of prod `8074a9dd67829042ba04a16bbe9c5a26702c88c6`. Access per P11 (`access.txt`). Scripts: `audit.py` → `audit.txt`, `rwarn_cells.tsv`.

## 1. Variants created through the edition-candidate path [VERIFIED]
Exactly the 20 known editions, ids 814–833, all created 2026-09-09. None has a v6 observation, and no other row has `base_variant_id` or `edition_classification`. **Not beyond the known set.**

Reading each edition's name against its base found two wrong bases that were not on record:
| Edition | Name | Base now | Effect |
|---|---|---|---|
| 815 | Exter HX 6 Petrol Manual Dual Tone | 656 HX 2 Petrol Manual | inherits HX 2's price (₹5.80 lakh; HX 6 is ₹7.95 lakh) and features |
| 816 | Exter HX 10 Petrol Automatic Dual Tone | 658 HX 3 Petrol Automatic | inherits HX 3's price (₹6.91 lakh; HX 10 is ₹9.42 lakh) and features |

The Exter brochure (`hyundai_exter_brochure.pdf`, SHA-1 `19da8e83…`, p11, p13, rendered and read) says only "DT-Dual Tone Option is available on select trims". It doesn't name HX 6 or HX 10. Under P8 they can't be re-based, so both are held (NEEDS_YOU N4). With 821 and 833 that makes 4 editions with identity contradictions.

Paper (P13, byte copy of the frozen snapshot; `paper_815_816.txt`): F019 (SUV ≤ ₹7 lakh) matches both at the inherited price. At the named trim's price neither would match, but F019 keeps 10 other non-excluded matches. **No verdict flips.**

## 2. Canonical cells from "resolved with warning" matches [VERIFIED]
- 1,245 provenance rows sit on these observations: 1,005 confirmed, 142 rejected, 98 accepted.
- Of the 98 accepted: 57 live and equal to the canonical value, 36 live but superseded, 5 on quarantined observations.
- The 57 cells come from 42 observations, all 91wheels, all in 10H's OK class (which 10H did not blind-check). 40 of the 57 have no other agreeing live evidence: km/l 28, boot space 5, cruise control 2, ventilated seats 2, wireless charging 2, HUD 1.
- **Blind validation:** a fresh subagent, with no classes or reasons, judged all 42 **correct links** (`validation/judgements.tsv`). It also judged 955, 1151 and 1157 mislinks.

**Not beyond the known set:** no quarantine phase is inserted. Under P3/P6 these values stay; the 40 aggregator-only ones are candidates for item 8 (brochure enrichment).

## 3. Conclusion
Neither count goes beyond the known set. The defect in the code stays dangerous and is fixed in 1c.
