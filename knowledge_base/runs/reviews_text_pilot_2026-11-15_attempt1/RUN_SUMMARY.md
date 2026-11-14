# kbpipe reviews run reviews_text_pilot_2026-11-15

Started 2026-11-14T19:49:13Z. Mode: no-write.

**Stopped / status:** --no-write: staged and gated, the KB was not touched

## Per model

| Model | Autocar overall (review date) | CarWale overall (ratings) | Notes kept / dropped | Themes kept / dropped | Text |
|---|---|---|---|---|---|
| Honda Amaze | 8.0 (2025-06-11) | 4.61 (207) | 0 / 7 | 0 / 6 | ok; checker failed: checker call failed: groq failed: HTTP 400 {"error":{"message":"Failed to validate JSON. Please adjust your prompt. See 'failed_generation' for more details.","type":"invalid_request_error","code":"json_validate_failed"," |
| Hyundai Creta | 9.0 (2025-10-09) | 4.6 (736) | 1 / 6 | 0 / 5 | ok; checker failed: checker call failed: groq failed: HTTP 400 {"error":{"message":"Failed to validate JSON. Please adjust your prompt. See 'failed_generation' for more details.","type":"invalid_request_error","code":"json_validate_failed"," |
| Kia Seltos | 8.0 (2025-10-16) | 4.45 (230) | 2 / 5 | 0 / 5 | ok; checker failed: checker call failed: groq failed: HTTP 400 {"error":{"message":"Failed to validate JSON. Please adjust your prompt. See 'failed_generation' for more details.","type":"invalid_request_error","code":"json_validate_failed"," |
| Kia Syros | 9.0 (2025-10-03) | 4.71 (30) | 5 / 2 | 0 / 0 | ok; only 8 owner reviews sampled (minimum 20) |
| Mahindra XUV 3XO | 8.0 (2025-08-19) | 4.65 (959) | 4 / 3 | 0 / 6 | ok; checker failed: checker call failed: groq failed: HTTP 400 {"error":{"message":"Failed to validate JSON. Please adjust your prompt. See 'failed_generation' for more details.","type":"invalid_request_error","code":"json_validate_failed"," |
| Maruti Suzuki Ertiga | 8.0 (2025-09-01) | 4.58 (901) | 1 / 6 | 0 / 6 | ok; checker failed: checker call failed: groq failed: HTTP 400 {"error":{"message":"Failed to validate JSON. Please adjust your prompt. See 'failed_generation' for more details.","type":"invalid_request_error","code":"json_validate_failed"," |
| Maruti Suzuki Swift | 8.0 (2025-10-16) | 4.53 (635) | 4 / 0 | 0 / 6 | ok; checker failed: checker call failed: groq failed: HTTP 400 {"error":{"message":"Failed to validate JSON. Please adjust your prompt. See 'failed_generation' for more details.","type":"invalid_request_error","code":"json_validate_failed"," |
| Skoda Kylaq | 8.0 (2025-08-06) | 4.73 (641) | 4 / 2 | 0 / 4 | ok; checker failed: checker call failed: groq failed: HTTP 400 {"error":{"message":"Failed to validate JSON. Please adjust your prompt. See 'failed_generation' for more details.","type":"invalid_request_error","code":"json_validate_failed"," |
| Tata Nexon | 8.0 (2025-07-04) | 4.59 (1068) | 3 / 4 | 0 / 5 | ok; checker failed: checker call failed: groq failed: HTTP 400 {"error":{"message":"Failed to validate JSON. Please adjust your prompt. See 'failed_generation' for more details.","type":"invalid_request_error","code":"json_validate_failed"," |
| Toyota Innova Hycross | 8.0 (2025-07-04) | 4.58 (400) | 2 / 5 | 0 / 6 | ok; checker failed: checker call failed: groq failed: HTTP 400 {"error":{"message":"Failed to validate JSON. Please adjust your prompt. See 'failed_generation' for more details.","type":"invalid_request_error","code":"json_validate_failed"," |

## Text verification (source: run.json, text_audit.jsonl)

- autocar: 26 of 31 checked claims supported (withheld: below bar)
- carwale: 0 of 0 checked claims supported
- writer model(s): sonnet; checker model(s): gemini-3.5-flash-lite, openai/gpt-oss-120b; independent: True
- numbers re-check autocar: 79 of 80 scores confirmed on the page (10 models)
- numbers re-check carwale: 78 of 78 scores confirmed on the page (10 models)

## Counts

- change-set ops: 158 (changeset.json)
- LLM calls made: 49 (writer 19, checker 30; llm_calls.jsonl); cache hits: writer 0, checker 0
- fetches: {"network": 37, "cache": 30, "failed": 0, "bytes": 37651940}
- flags: 53 (flags.tsv)
- gates: {"schema": true, "provenance": true, "rows": true, "explained": true, "reviews": true}; idempotent: True
