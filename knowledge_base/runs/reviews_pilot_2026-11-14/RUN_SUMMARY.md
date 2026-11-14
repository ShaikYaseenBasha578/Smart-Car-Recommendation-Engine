# kbpipe reviews run reviews_pilot_2026-11-14

Started 2026-11-14T17:41:05Z. Mode: no-write.

**Stopped / status:** --no-write: staged and gated, the KB was not touched

## Per model

| Model | Autocar overall (review date) | CarWale overall (ratings) | Notes kept / dropped | Themes kept / dropped | Text |
|---|---|---|---|---|---|
| Honda Amaze | 8.0 (2025-06-11) | 4.61 (207) | 0 / 0 | 0 / 0 | text stopped: gemini_alt: HTTP 429 {
  "error": {
    "code": 429,
    "message": "You exceeded your current quota, please check your ; text stopped: groq failed: HTTP 400 {"error":{"message":"Failed to validate JSON. Please adjust your prompt. See 'failed_generation' f |
| Hyundai Creta | 9.0 (2025-10-09) | 4.6 (736) | 0 / 0 | 5 / 0 | text stopped: groq failed: HTTP 413 {"error":{"message":"Request too large for model `openai/gpt-oss-120b` in organization `org_01m6vr; ok |
| Kia Seltos | 8.0 (2025-10-16) | 4.45 (230) | 0 / 0 | 0 / 0 | text stopped: every backend for this role is out of quota: groq: HTTP 429 {"error":{"message":"Rate limit reached for model `openai/gp |
| Kia Syros | 9.0 (2025-10-03) | 4.71 (30) | 0 / 0 | 0 / 0 | - |
| Mahindra XUV 3XO | 8.0 (2025-08-19) | 4.65 (959) | 0 / 0 | 0 / 0 | - |
| Maruti Suzuki Ertiga | 8.0 (2025-09-01) | 4.58 (901) | 0 / 0 | 0 / 0 | - |
| Maruti Suzuki Swift | 8.0 (2025-10-16) | 4.53 (635) | 0 / 0 | 0 / 0 | - |
| Skoda Kylaq | 8.0 (2025-08-06) | 4.73 (641) | 0 / 0 | 0 / 0 | - |
| Tata Nexon | 8.0 (2025-07-04) | 4.59 (1068) | 0 / 0 | 0 / 0 | - |
| Toyota Innova Hycross | 8.0 (2025-07-04) | 4.58 (400) | 0 / 0 | 0 / 0 | - |

## Verification (source: run.json)

- carwale: 5 of 5 sampled items supported
- extractor model(s): gemini-3.5-flash-lite, openai/gpt-oss-120b; verifier model(s): openai/gpt-oss-120b; independent: False

## Counts

- change-set ops: 163 (changeset.json)
- LLM calls: 8 (llm_calls.jsonl)
- fetches: {"network": 0, "cache": 28, "failed": 0, "bytes": 0}
- flags: 7 (flags.tsv)
- gates: {"schema": true, "provenance": true, "rows": true, "explained": true, "reviews": true}; idempotent: True
