# kbpipe reviews run reviews_text_pilot_themes_2026-11-15

Started 2026-11-14T20:33:44Z. Mode: no-write.

**Stopped / status:** --no-write: staged and gated, the KB was not touched

## Per model

| Model | Autocar overall (review date) | CarWale overall (ratings) | Notes kept / dropped | Themes kept / dropped | Text |
|---|---|---|---|---|---|
| Honda Amaze | 8.0 (2025-06-11) | 4.61 (207) | 5 / 2 | 5 / 0 | ok; ok |
| Hyundai Creta | 9.0 (2025-10-09) | 4.6 (736) | 7 / 0 | 5 / 0 | ok; ok |
| Kia Seltos | 8.0 (2025-10-16) | 4.45 (230) | 7 / 0 | 4 / 1 | ok; ok |
| Kia Syros | 9.0 (2025-10-03) | 4.71 (30) | 7 / 0 | 0 / 0 | ok; only 8 owner reviews sampled (minimum 20) |
| Mahindra XUV 3XO | 8.0 (2025-08-19) | 4.65 (959) | 7 / 0 | 4 / 0 | ok; ok |
| Maruti Suzuki Ertiga | 8.0 (2025-09-01) | 4.58 (901) | 7 / 0 | 6 / 0 | ok; ok |
| Maruti Suzuki Swift | 8.0 (2025-10-16) | 4.53 (635) | 4 / 0 | 6 / 0 | ok; ok |
| Skoda Kylaq | 8.0 (2025-08-06) | 4.73 (641) | 6 / 0 | 1 / 2 | ok; ok |
| Tata Nexon | 8.0 (2025-07-04) | 4.59 (1068) | 7 / 0 | 5 / 0 | ok; ok |
| Toyota Innova Hycross | 8.0 (2025-07-04) | 4.58 (400) | 7 / 0 | 0 / 0 | ok; text failed: writer call failed: claude cli: {"duration_api_ms":0,"stop_reason":"stop_sequence","session_id":"95a2f02b-6e31-4864-b78c |

## Text verification (source: run.json, text_audit.jsonl)

- autocar: 64 of 66 checked claims supported
- carwale: 36 of 39 checked claims supported (withheld: below bar)
- writer model(s): sonnet; checker model(s): claude-opus-5-5, openai/gpt-oss-120b; independent: True
- checker backend gemini_alt ran out and was skipped: gemini_alt: HTTP 429 {
  "error": {
    "code": 429,
    "message": "You exceeded your current quota, please check your plan and billing details. For more infor
- numbers re-check autocar: 79 of 80 scores confirmed on the page (10 models)
- numbers re-check carwale: 70 of 70 scores confirmed on the page (9 models)

## Counts

- change-set ops: 158 (changeset.json)
- LLM calls made: 20 (writer 8, checker 12; llm_calls.jsonl); cache hits: writer 10, checker 29
- fetches: {"network": 0, "cache": 67, "failed": 0, "bytes": 0}
- flags: 10 (flags.tsv)
- gates: {"schema": true, "provenance": true, "rows": true, "explained": true, "reviews": true}; idempotent: True
