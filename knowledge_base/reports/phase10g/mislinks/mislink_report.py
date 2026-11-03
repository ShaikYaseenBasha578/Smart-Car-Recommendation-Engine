import sqlite3, sys
db = sqlite3.connect(sys.argv[1])
lines = [l.rstrip("\n").split("|") for l in open("mislinks3.txt") if l.startswith("TRACED")]
# fields: 1 vid, 2 model, 3 KB name, 4 field, 5 canonical, 6 fp, 7 "obsN source", 8 raw name, 9 mismatch, 10 other support
FALSE_POS = {207, 208, 826}                      # "Smart Hybrid" = mild hybrid; the KB stores these as Petrol
TRIM_REAL = {34, 36, 50, 146, 306, 629, 630, 631, 632, 819, 821, 823, 825, 828, 830, 831}
TRIM_AMBIG = {416, 628, 804, 806}
real, ambig, noise = [], [], []
for l in lines:
    vid, why = int(l[1][1:]), l[9]
    strong = ("fuel:" in why or "gearbox:" in why) and vid not in FALSE_POS
    (real if strong or vid in TRIM_REAL else ambig if vid in TRIM_AMBIG else noise).append(l)
obs_of = lambda l: int(l[7].split()[0][3:])
obs_real = sorted({obs_of(l) for l in real})
ids = ",".join(map(str, obs_real))
cd = db.execute(f"""with a as (select variant_id, field_name, count(distinct source_id) n from v_live_evidence where decision in ('accepted','confirmed') group by 1,2),
  b as (select variant_id, field_name, count(distinct source_id) n from v_live_evidence where decision in ('accepted','confirmed') and observation_id not in ({ids}) group by 1,2)
  select a.variant_id, a.field_name, a.n, coalesce(b.n,0) from a left join b using(variant_id, field_name) where coalesce(b.n,0) < a.n order by 1,2""").fetchall()
out = []
w = out.append
w("# 10G pre-go: canonical cells traced to resolver mislinks (report only, no writes)\n")
w("DB: `work.db`, a byte copy of prod `dedefb537ce36cec5e422c6688a3a85373030b39`. Scripts: `mislinks.py`, `mislinks_v3.py`, `mislink_report.py`; raw output `mislinks3.txt`.\n")
w("Method: an aggregator observation (91wheels / v3cars / carwale) is *flagged* when its raw name contradicts the resolved variant on fuel, gearbox or trim. "
  "A canonical cell is *traced* when an `accepted`, un-quarantined field_provenance row cites a flagged observation and its value equals the cell in `v_variant_canonical_q`. Trim hits were reviewed by hand.\n")
w("- **Price: no cell.** All 812 `price_ex_showroom` provenance rows are v6_migration [VERIFIED].")
w("- **Named mislinks:** Nexon obs 885/888/897 have no provenance rows. Exter obs 1966/1970/1974/1975/1977 (HX3–HX8 → v655 HX 2) have 40 `confirmed` rows (zeros and Manual) and no `accepted` row, so no canonical cell depends on them [VERIFIED].\n")
for title, rs in (("A. Real mislinks: canonical cell depends on them", real), ("B. Ambiguous trim (needs a human)", ambig)):
    w(f"## {title}: {len(rs)} cells\n")
    w("| variant | model / KB name | field | canonical | fp | obs (source): raw name | mismatch | other support |")
    w("|---|---|---|---|---|---|---|---|")
    for l in rs:
        w(f"| {l[1]} | {l[2]} / {l[3]} | {l[4]} | {l[5]} | {l[6]} | {l[7]}: {l[8]} | {l[9]} | {l[10].replace('other=', '')} |")
    w("")
w(f"## C. Excluded as naming noise: {len(noise)} traced cells\n")
w("For example 'HX 4' = 'HX4', 'Mid Range' = 'MR', '5Str', and glued v3cars names. Listed in `mislinks3.txt`.\n")
w(f"## D. Corroboration counts that drop if the {len(obs_real)} A-set observations are excluded: {len(cd)} cells\n")
for r in cd: w(f"- v{r[0]} {r[1]}: {r[2]} → {r[3]} sources")
w("\nThe 677 trim-only flags outside the traced set were not hand-reviewed; they affect only `confirmed`/`rejected` rows.")
open("MISLINK_REPORT.md", "w").write("\n".join(out) + "\n")
print(len(real), len(ambig), len(noise), len(cd))
