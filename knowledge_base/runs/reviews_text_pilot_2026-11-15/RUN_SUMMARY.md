# kbpipe reviews run reviews_text_pilot_2026-11-15

Started 2026-11-14T20:21:33Z. Mode: no-write.

**Stopped / status:** --no-write: staged and gated, the KB was not touched

## Per model

| Model | Autocar overall (review date) | CarWale overall (ratings) | Notes kept / dropped | Themes kept / dropped | Text |
|---|---|---|---|---|---|
| Honda Amaze | 8.0 (2025-06-11) | 4.61 (207) | 5 / 2 | 5 / 0 | ok; ok |
| Hyundai Creta | 9.0 (2025-10-09) | 4.6 (736) | 7 / 0 | 5 / 0 | ok; ok |
| Kia Seltos | 8.0 (2025-10-16) | 4.45 (230) | 7 / 0 | 4 / 1 | ok; ok |
| Kia Syros | 9.0 (2025-10-03) | 4.71 (30) | 7 / 0 | 0 / 0 | ok; only 8 owner reviews sampled (minimum 20) |
| Mahindra XUV 3XO | 8.0 (2025-08-19) | 4.65 (959) | 7 / 0 | 3 / 1 | ok; ok |
| Maruti Suzuki Ertiga | 8.0 (2025-09-01) | 4.58 (901) | 7 / 0 | 6 / 0 | ok; ok |
| Maruti Suzuki Swift | 8.0 (2025-10-16) | 4.53 (635) | 4 / 0 | 5 / 1 | ok; ok |
| Skoda Kylaq | 8.0 (2025-08-06) | 4.73 (641) | 6 / 0 | 2 / 2 | ok; ok |
| Tata Nexon | 8.0 (2025-07-04) | 4.59 (1068) | 7 / 0 | 5 / 0 | ok; ok |
| Toyota Innova Hycross | 8.0 (2025-07-04) | 4.58 (400) | 7 / 0 | 5 / 1 | ok; ok |

## Text verification (source: run.json, text_audit.jsonl)

- autocar: 64 of 66 checked claims supported
- carwale: 40 of 44 checked claims supported (withheld: below bar)
- writer model(s): ; checker model(s): claude-opus-5-5; independent: True
- numbers re-check autocar: 79 of 80 scores confirmed on the page (10 models)
- numbers re-check carwale: 78 of 78 scores confirmed on the page (10 models)

## Counts

- change-set ops: 158 (changeset.json)
- LLM calls made: 33 (writer 0, checker 33; llm_calls.jsonl); cache hits: writer 19, checker 20
- fetches: {"network": 0, "cache": 67, "failed": 0, "bytes": 0}
- flags: 12 (flags.tsv)
- gates: {"schema": true, "provenance": true, "rows": true, "explained": true, "reviews": true}; idempotent: True
