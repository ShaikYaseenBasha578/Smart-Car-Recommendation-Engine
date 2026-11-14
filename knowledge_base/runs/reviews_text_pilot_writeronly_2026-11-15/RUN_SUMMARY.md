# kbpipe reviews run reviews_text_pilot_writeronly_2026-11-15

Started 2026-11-14T20:14:39Z. Mode: no-write.

**Stopped / status:** --no-write: staged and gated, the KB was not touched

## Per model

| Model | Autocar overall (review date) | CarWale overall (ratings) | Notes kept / dropped | Themes kept / dropped | Text |
|---|---|---|---|---|---|
| Honda Amaze | 8.0 (2025-06-11) | 4.61 (207) | 0 / 0 | 0 / 0 | write-only: checks pending; write-only: checks pending |
| Hyundai Creta | 9.0 (2025-10-09) | 4.6 (736) | 0 / 0 | 0 / 0 | write-only: checks pending; write-only: checks pending |
| Kia Seltos | 8.0 (2025-10-16) | 4.45 (230) | 0 / 0 | 0 / 0 | write-only: checks pending; write-only: checks pending |
| Kia Syros | 9.0 (2025-10-03) | 4.71 (30) | 0 / 0 | 0 / 0 | write-only: checks pending; only 8 owner reviews sampled (minimum 20) |
| Mahindra XUV 3XO | 8.0 (2025-08-19) | 4.65 (959) | 0 / 0 | 0 / 0 | write-only: checks pending; write-only: checks pending |
| Maruti Suzuki Ertiga | 8.0 (2025-09-01) | 4.58 (901) | 0 / 0 | 0 / 0 | write-only: checks pending; write-only: checks pending |
| Maruti Suzuki Swift | 8.0 (2025-10-16) | 4.53 (635) | 0 / 0 | 0 / 1 | write-only: checks pending; write-only: checks pending |
| Skoda Kylaq | 8.0 (2025-08-06) | 4.73 (641) | 0 / 0 | 0 / 1 | write-only: checks pending; write-only: checks pending |
| Tata Nexon | 8.0 (2025-07-04) | 4.59 (1068) | 0 / 0 | 0 / 0 | write-only: checks pending; write-only: checks pending |
| Toyota Innova Hycross | 8.0 (2025-07-04) | 4.58 (400) | 0 / 0 | 0 / 0 | write-only: checks pending; write-only: checks pending |

## Text verification (source: run.json, text_audit.jsonl)

- autocar: 0 of 0 checked claims supported
- carwale: 0 of 0 checked claims supported
- writer model(s): sonnet; checker model(s): ; independent: True

## Counts

- change-set ops: 158 (changeset.json)
- LLM calls made: 19 (writer 19, checker 0; llm_calls.jsonl); cache hits: writer 0, checker 0
- fetches: {"network": 0, "cache": 67, "failed": 0, "bytes": 0}
- flags: 5 (flags.tsv)
- gates: {"schema": true, "provenance": true, "rows": true, "explained": true, "reviews": true}; idempotent: True
