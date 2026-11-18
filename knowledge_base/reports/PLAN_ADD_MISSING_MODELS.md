# Plan: add the 16 models the pipeline finds but cannot add

Status: **waiting for owner approval** (18 Nov 2026). Nothing is built.

## 1. The problem, measured

Discovery finds 16 current models on both CarWale and CarDekho that are not in the KB: ZR-V, Creta Electric, Syros EV, Comet EV, Hector Tomahawk EV, Hector Tomahawk PHEV, ZS EV, BE 6 Sporteq, XUV 3XO EV, XUV400, Invicto, X-Trail, Tigor EV, Camry, Fortuner Legender, Urban Cruiser Ebella.

A model is added only through variants that link on both sites (the two-site rule). For all 16, **both sites list the variants** (for example Creta Electric 29 and 29, ZR-V 1 and 1), but **zero variants link**. Rebuilt from cached pages on 18 Nov, the blocks are:

| Block | Example (CarWale vs CarDekho) | Models hit |
|---|---|---|
| **A. Battery size in one name only.** CarWale puts it in the variant name, CarDekho in a separate field. The linker treats "42.0 kWh" as a trim word, so identities differ | "Executive 42.0 kWh" vs "Executive" (42 kWh in the sub-line) | Creta Electric, Syros EV, Comet EV, Tomahawk EV, ZS EV, BE 6 Sporteq, XUV 3XO EV, Tigor EV |
| **B. Battery size spelled differently on the variant page.** The page-name check rejects the page | "34.5 kWh" vs "345 kWh" | XUV400 |
| **C. Strong hybrid labelled "Petrol" by CarDekho.** Fuel differs, so identities differ | "Petrol Hybrid" vs "Petrol" | Invicto, Camry, ZR-V, Tomahawk PHEV |
| **D. Descriptor words in one name only.** Fuel, gearbox and drive words that are already compared as attributes | "Zeta Plus Hybrid (Electric + Petrol) Automatic 7 STR" vs "Zeta Plus 7Str"; "4X2 2WD Diesel Turbo Automatic" vs "4x2 AT" | Invicto, Camry, Fortuner Legender, X-Trail, ZR-V |
| **E. Prices differ beyond 0.5%.** The linker requires agreeing prices | Creta Electric Executive ₹14.57 lakh vs ₹18.03 lakh; Comet Executive ₹6.48 lakh vs ₹7.90 lakh | Creta Electric, Comet EV, ZR-V, and probably other EVs |
| **F. Genuinely different names** | "Elegant" vs "Elegance"; "STD" vs "Mild Hybrid CVT Petrol Automatic"; "Neo Drive" | Camry, X-Trail, Fortuner Legender |

Correction: an earlier message said the cause was mostly battery-size spelling ("34.5" vs "345"). That is block B and affects only XUV400.

## 2. What I propose

Each change is narrow, fails closed, and keeps the rule that a variant needs two agreeing sites.

1. **Battery size as an attribute (fixes A, B).** Read the kWh figure from both sides (CarWale name; CarDekho sub-line or name). It must agree within 0.05 kWh, so Comet's 17.3 and 17.4 stay distinct. Then drop it from the trim words. Normalise "345 kWh" to "34.5 kWh" in the page-name check only when the sub-line confirms 34.5.
2. **Strong-hybrid fuel (fixes C).** Treat CarDekho "Petrol" as compatible with CarWale "Petrol Hybrid" only when **every** current CarWale version of that model is a strong hybrid, and the CarDekho sub-line or spec page does not contradict it. Fuel is written from CarWale and the brochure, never from CarDekho in this case.
3. **Descriptor words (fixes D).** Remove words already compared as attributes before comparing trims: "Hybrid (Electric + Petrol)", "Automatic/AT", "Manual/MT", "Diesel Turbo", "e:HEV", "2WD/4WD" when the 4x2/4x4 token is present. "7 STR" and "7Str" become the same seat token. The word list is fixed and tested; no fuzzy matching.
4. **Prices (E): owner decision D1 below.**
5. **Different names (F): unchanged.** They stay unlinked and go to the review file as "possible same variant". No fuzzy spelling match ("Elegant" vs "Elegance" is left to you).

## 3. Decisions for the owner

- **D1. When the identity matches but the prices disagree.** EV prices differ a lot between the sites (probably subsidies, battery rental or city pricing).
  - **Recommended:** link on a unique identity match, write every non-price field, and send the price to the review file with both figures. No price is written until you tick one.
  - Alternative: keep requiring agreeing prices. Most EVs then stay out.
- **D2. One-variant models** (ZR-V, X-Trail). Recommended: no special rule. X-Trail's prices agree and needs only rule 3; ZR-V follows D1.
- **D3. Scope.** Recommended: these rules apply to every model in future runs, not only the 16, since the same mismatches will recur. Existing links can't change, because linking only adds.

## 4. Safeguards (KB policy)

- **P12 blind check.** The new rules will decide more than 20 links, so a fresh subagent that never sees the rules checks a stratified sample (by block A–E, at least 10 per block, or all where fewer) against the two pages. **Agreement must be at least 95% in every block, or nothing is written.**
- **Regression.** The 50-of-50 blind link set and `links.tsv` from earlier runs must still link identically: no existing link may change or disappear.
- **Write path unchanged:** dry run, gates, backup, apply, idempotency re-run, integrity and foreign-key checks, changelog.
- **Brochures:** the 16 models' brochures were already read on 17 Nov and cached. Once variants exist, cells attach from that cache at little cost.

## 5. Steps

1. Diagnostic report (no write): each CarWale version, its best CarDekho candidate, and the block that stops it, for all 16 models. Gives exact counts per block.
2. Rules 1–3 (and 4 per D1) in `kbpipe/match.py` and `kbpipe/extract.py`, each with unit tests from the real names above.
3. Regression on earlier link files; must be identical.
4. No-write run limited to the 16 models: variants linked per model, what is held, and why.
5. Blind check (P12) on the new links.
6. Report to the owner with counts; on approval, write through `kbpipe update`, then export and a pull request.

**Expected result:** most of the 16 gain variants. I can't promise a number before step 1. Models whose names differ outright (block F) may stay partial.

**Effort:** steps 1–4 are code and offline runs; step 5 is one blind subagent; the write costs no LLM calls beyond the cached brochures.
