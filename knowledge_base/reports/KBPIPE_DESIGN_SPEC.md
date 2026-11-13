# kbpipe — design spec (PLAN, nothing built, nothing written to the KB)

Date: 2026-11-13. Status: waiting for owner approval. Evidence tags as in CLAUDE.md.

## 1. What I found (and where the handover is out of date)

| Handover says | Repo says |
|---|---|
| Main dataset is `carrec_recommendation_dataset.csv` | The KB is `knowledge_base/carrec_kb.db` (SQLite). That CSV is deleted in the working tree. [VERIFIED git status, sqlite_master] |
| KB about 90% complete | 832 variants, 62 models, 12 makes. CarWale's Tata page alone lists Punch, Curvv, Curvv EV, Safari, Harrier EV and Sierra, none of which are in the KB. [VERIFIED query + fetch 2026-11-13] My estimate is 25–35 in-scope models missing; discovery will give the real number. |
| No provenance audit exists | Per-batch blind checks exist for brochure phases 10N–11P (P12). There is no audit of the KB as a whole. Correct in substance. |
| Schema may need a provenance change | It doesn't. `source_observation` has `source_url`, `observed_at`, `extraction_method`, `raw_payload`; `field_provenance` links each cell to it. "Model used" goes in `extraction_method` and `raw_payload`. No DDL. [VERIFIED] |
| Policy is to be written | A strict policy already exists (P1–P18). Several rules conflict with the tool as specified. See §3. |

Other facts that shape the design:

- **Latest state is on `kb/enrich-claude`, not `paper/v0`.** Prod SHA-1 `b174b0ac…` is the documented post-11P state. [VERIFIED changelog on that branch] The `CLAUDE.md` on `paper/v0` is one week behind (it still has the old P11 side-file rule).
- **Traceability gap.** 24,955 accepted cells trace only to `v6_migration` observations, which have no URL (812 of 812 null). 358 `transmission` cells have no provenance row at all. [VERIFIED] Only 37 of 62 models have any brochure-verified cell. The paper's "traceable provenance for every field" is not true today for most of the KB.
- **Free LLMs: your own evidence is negative.** The Flash pilot stopped at 93.3% blind agreement with 6.3% recall, and the cost check chose ALL-CLAUDE. [VERIFIED `PILOT_REPORT_R2.md`, `COSTCHECK_REPORT.md`] Whether a free backend reaches 95% on brochure pages is unproven.
- **Machine:** M2, 8 GB RAM, Python 3.9.6 with no third-party packages, no Ollama, no poppler. `GEMINI_API_KEY` and `GROQ_API_KEY` are set. [VERIFIED]
- **Sources reachable today** with a plain HTTP fetch (200, full HTML): CarWale, CarDekho, 91wheels, v3cars brand pages. robots.txt on CarWale and CarDekho does not disallow brand/model paths for generic agents (I read the first 25 rules of each). I have not read any site's terms of use. [VERIFIED fetch; terms UNKNOWN]
- **Resolver:** PR #19 is merged (2026-11-07). The P15 blind check (≥98% on 50 links) has not been run. [VERIFIED gh, NEEDS_YOU N6]

## 2. Design

### Layout
- Code: `kbpipe/` Python package on a new branch `kb/kbpipe` cut from `kb/enrich-claude`, in its own worktree. Never `main`, never pushed.
- Stdlib first (`sqlite3`, `urllib`, `argparse`, `json`). Two dependencies in a local venv: PyMuPDF (PDF text + page render) and pytest. A `kbpipe` shell entry point.
- Per-run output: `knowledge_base/runs/<date>/` (git-ignored data, tracked reports).
- Cache: `~/carrec_kb_cache/` keyed by URL, storing body, fetch time, ETag and SHA-256. Brochures are saved to a new `knowledge_base/sources/oem_kbpipe/` (P17 forbids writing in `sources/oem/`).

### Commands
`kbpipe run [--full] [--stage X] [--max-models N]` · `kbpipe apply-review REVIEW_<date>.md` · `kbpipe agreement <sheet.csv>` · `kbpipe status`.

### Stages
1. **Discovery.** Fetch brand listing pages from two aggregators (CarWale + CarDekho). A model is "on sale" only if both list it as current with a price. Diff against the KB → new model, new variant, missing-from-listings (discontinued candidate), price change. Scope filter is a config file: the 12 current makes, base price ≤ ₹50 lakh; anything else goes to review, not into the KB.
2. **Extraction.**
   - Aggregator pages: deterministic parsers of the embedded JSON payloads. No LLM. This covers price, dimensions, engine and most features.
   - OEM brochures: located from the OEM site, downloaded, SHA-pinned. Text layer first; LLM reads rendered page tiles only when needed. Prompt reuses `enrichment/GLOSSARY.md`.
   - Every cell becomes a `source_observation` (URL or file + page + SHA, `observed_at`, `extraction_method` such as `kbpipe/1.0 brochure_page llm=gemini-…`).
3. **Reconciliation.** Pure function, fully tested. Precedence is decision D5 below. Every conflict is logged to `conflicts.tsv` with all values and sources. Unit rules from P4 are enforced in code.
4. **Verification.** Separate module with no import of extraction code. It receives (cell, value, source pointer), re-fetches or re-renders the source, and asks a different model: match / mismatch / unreachable, with a quoted evidence string. Output is written once to `runs/<date>/verify/` and chmod 444. Accuracy numbers are computed only from those files.
5. **Gates + report.** Scripted: `integrity_check`; `foreign_key_check` (only the 297 known orphans); live schema hash equals the pinned one; 100% of changed cells have a provenance row with URL, date and method; no table's row count drops; every row of the `EXCEPT` diff maps to a run-log entry. Then `RUN_SUMMARY.md`, `REVIEW_<date>.md`, the 30-row human sheet.

### Write path (implements P10 and P11 in code)
`lsof` check → SHA-1 → `.backup` to `backups/` → dump committed to a local history repo and tagged `kb-run-<date>` → change-set applied to a scratch copy → gates → re-apply (must be 0 changes) → same change-set to prod in one transaction → `integrity_check`, checkpoint, new SHA-1 → changelog entry.

- The history repo (`~/carrec_kb_history/`, no remote) stores a sorted SQL text dump, not the 40 MB binary: diffs are readable and the repo stays small. The binary backup stays in `backups/` as now.
- "Staging" is a change-set file per run, not a second long-lived DB. Clear items apply; review items stay in `pending.jsonl` until `apply-review`.
- Nothing is deleted. Discontinued = `variant.is_discontinued = 1` with an amendment row, and only after review.

### Always sent to review, never auto-applied
New model whose name matches an existing one (facelift vs new) · any change to a model held under P7 (Seltos, Brezza, Baleno, WagonR, Jimny, Kylaq) · editions (P8) · discontinuations · conflicts above the threshold (numeric > 2%, any boolean or categorical disagreement between two sources of the same tier) · any change to body type, fuel, transmission, seats or price on a variant that exists in the paper snapshot (P13).

### Incremental
Listing pages are fetched every run. A model is reprocessed only if its listing hash changed, a source is older than the refresh threshold, or a brochure's SHA changed. A second run right after the first should fetch about 30 listing pages and write nothing.

### Tests
Reconciliation (precedence, units, thresholds), each gate (one failing fixture per gate), incremental detection (unchanged, changed, new, vanished), verifier isolation (it cannot import extractor modules), and the resolver regression fixture `phase10h/links.tsv`.

## 3. Decisions for you

**D1. LLM backends.** Aggregator extraction needs no LLM, so the LLM is used for brochure pages and for verification.
1. *(Recommended)* Extract with Gemini (free tier), verify with a different model: Groq-hosted open model for text evidence, a second Gemini model for page images. Before any real use, a pre-registered bake-off on cells already brochure-verified in 11A–11P decides whether each backend clears 95%. If none does, the tool still runs, the report says so, and brochure cells stay in review.
2. Add a `claude -p` adapter as an optional backend. It is the only one with measured ≥95% results here, but it is not free.
3. Ollama. Supported by the adapter, but 8 GB RAM rules out a vision model good enough for brochure tables. Not recommended on this machine.
- I don't know the current free-tier limits; they change. The tool handles 429s and a daily budget, so a first full run may take several days of wall time. The paper runner uses the same Gemini quota; use a separate key or don't run both the same day.

**D2. Sources.**
- Discovery: CarWale + CarDekho brand pages (plain fetch, 1 request per 4 s, cached).
- Specs: 91wheels and CarWale payloads, as before; v3cars as third opinion.
- Brochures: OEM sites; fragile (URLs change, some are image-only). Missing brochure → cells stay aggregator-tier.
- Journalist sources (Team-BHP, reviews): I recommend leaving them out. Free text needs an LLM, adds little for spec fields, and reviews are out of scope.
- Legal: robots.txt permits these paths; I have not read the terms of use and can't tell you they allow automated access. This goes to `NEEDS_YOU.md`. The fallback if you say no is brochures + OEM price pages only, which leaves gaps.

**D3. Refresh threshold and sample size.**
- Refresh: prices 30 days, aggregator specs 90 days, brochures on SHA change. *(Recommended.)*
- First-run audit: 600 cells = 25 per (8 field groups × 3 source classes: brochure, aggregator, legacy v6). That gives about ±1.7 points on the overall figure and about ±5 on each field group. Per-group numbers are coarse; tightening them to ±3 needs about 200 per group.
- In-run: every 5 models, 10% of new cells, minimum 30. A field group stops when it is below 95% on at least 20 samples.
- Later runs: all changed cells up to 200, then sampled.

**D4. Scheduling.** Manual only. *(Recommended; the paper needs a stable KB until January.)*

**D5. Aggregator-only values (conflicts with P2).** P2 says an aggregator is never the sole basis for a value. Brochures rarely print prices, and new models may have no brochure.
1. *(Recommended)* Keep P2 for existing values. For new rows only, accept a value when two aggregators agree exactly, with `decision_reason = AGGREGATOR_AGREED_UNVERIFIED`. Aggregators copy each other, so this is weaker than it looks; the audit reports this class separately.
2. Strict P2: new models get brochure cells only. Price is mostly null, which makes them useless for budget constraints.
3. Handover rule as written (brochure > aggregator > journalist, single aggregator enough).

**D6. Does the audit cover the legacy KB?** The 95% bar in the handover applies to new and changed fields. The paper needs the number for the KB it actually uses.
1. *(Recommended)* Include a legacy stratum and report it separately. It may come in under 95%, partly from model-year drift since June. Better to know now.
2. Audit only what the tool writes.

**D7. Other standing rules that need your amendment for a tool that runs without Claude Code.**
- P12: "fresh subagent" becomes "the tool's verifier, different model, isolated inputs".
- P14: no app export or PR from the tool (your handover forbids touching the remote).
- P15: I run the blind resolver check once at build start; approving this plan is the go for fetching (N6).
- P17/P18: the tool writes brochures to `sources/oem_kbpipe/` and appends to the changelog itself.

**D8. Paper snapshot.** The paper reads the frozen `8592508` snapshot. The tool never touches it. Whether its output becomes a paper v1 snapshot is your call after the first run.

## 4. Build order and timebox

Order is chosen so a cut-off still leaves something the paper needs.
1. Skeleton, config, gates, write path, tests. P15 check.
2. Verification + audit of the existing KB (delivers methodology item 2 on its own).
3. Discovery (report only).
4. Aggregator extraction + reconciliation; pilot on 3 new models.
5. Brochure extraction, backend bake-off.
6. Full first run, README, summary.

Timebox: 3 build sessions. If the 3-model pilot does not pass the gates by the end of session 2, I stop, commit and report. First full run capped at 40 new models.

Effort: Fable for design, reconciliation, gates and the write path; Sonnet subagents for parsers, fixtures and README; the first run itself uses no Claude at all.

## 5. Risks, plainly
- The free backend may not reach 95% on brochure pages. Prior evidence says it didn't.
- Aggregator page formats break. The README will say what to do; the tool fails closed (no write).
- Adding 25–35 models is about a 50% growth of the KB two months before the preprint. The audit stage is the part the paper cannot do without; the expansion is optional for it.
- No model-year dimension (schema proposal S3 is unapproved), so a changed spec overwrites the old one. The old value survives only in `evidence_amendment`.

## 6. Proposed CLAUDE.md addition (build session)

```
## kbpipe build session (owner-approved <date>)
- Decide and log (KB_CHANGELOG.md): implementation details, stdlib and library choices already listed in the spec, retry logic, file layout.
- NEEDS_YOU.md and continue: any source or legal uncertainty, schema questions, scope changes, a backend below 95% in the bake-off.
- Hard stops: deleting KB data; any DDL; any paid service; touching main, the remote or the deploy; the same failure 3 times; any holder other than P11's; a non-empty -wal.
- kbpipe is the only code allowed to write prod outside a hand-run phase, and only through its P10 write path.
- P2, P12, P14, P15, P17, P18 as amended in decisions D5 and D7.
- Timebox: 3 sessions; stop at the end of session 2 if the 3-model pilot fails its gates.
```
