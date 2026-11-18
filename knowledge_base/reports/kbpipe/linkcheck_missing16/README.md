# Blind check of the missing-models linking rules (P12), 2026-11-18

- **Population:** every link that the new rules make and the original linker did not, from cached pages. That is 167 links: 72 on the 16 models missing from the KB, and 95 on models already in the KB. `build.py` rebuilds them.
- **Sample:** stratified by rule class: at least 12 per class, or all where a class is smaller (XUV400 page spelling 5, strong hybrid 3, descriptor words 1). 57 real links in all, plus 6 planted wrong pairs (a variant's CarWale side paired with another variant's CarDekho side of the same model). The 63 rows were shuffled (seed 20261118) under opaque ids.
- **What the checker saw:** `sheet.tsv`: each site's name, fuel, gearbox, price, engine size, battery size, seats, spec line and URL. **What it did not see:** the code, the rules, the rule class, or `key.json`.
- **Checker:** a fresh subagent (Claude Opus; the rules were written by Claude Sonnet). It judged from the sheet and its own knowledge, and opened no pages. Verdicts are in `verdicts.tsv`.
- **Result:** every class 100%.

| Class | Agreed |
|---|---|
| battery | 12 of 12 |
| price differs (D1) | 12 of 12 |
| price differs + battery | 12 of 12 |
| dual tone on one site | 12 of 12 |
| page spelling (XUV400) | 5 of 5 |
| strong hybrid | 3 of 3 |
| descriptor words | 1 of 1 |
| planted wrong pairs, rejected | 6 of 6 |

  The bar was 95% in every class (P12).
- **Checker's notes:**
  - BE 6 Sporteq and XEV 9S are listed about ₹4.5–5 lakh lower on CarWale, which says "No Charger".
  - Harrier Adventure X Plus Dark diesel manual is ₹23.45 lakh on CarWale and ₹19.40 lakh on CarDekho.

  Under D1, no price is written for these variants; both prices go to the review file.
- **Limits:**
  - The sample has 57 of 167 links, and the small classes are thin (strong hybrid 3, descriptor 1).
  - The checker judged from listed facts, not from the maker's documents.
  - It measures wrong links, not missed ones.
