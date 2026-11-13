# Blind check of kbpipe's variant links (P15 condition), 2026-11-13

- Population: the links made by the full dry run (`runs/dry_full/links.tsv`): 1,231 CarWale–CarDekho links and 611 CarWale–KB links.
- Sample: 50 drawn at random (seed 20261113), 25 of each kind, shuffled. `blind_pairs.tsv` is what the checker saw: names, fuel, gearbox and price only. `key.json` holds the kind and the linker's reason, which the checker did not see.
- Checker: a fresh subagent (Claude Sonnet) with no access to the linker's code or rules. Its verdicts: `verdicts.tsv`.
- Result: 50 same, 0 different, 0 unclear = 100%. Bar: 98%.
- Limits: one sample of 50; the checker saw equal prices on most site links, which makes those easy. It measures wrong links, not missed ones (about a quarter of listed variants stay unlinked).
