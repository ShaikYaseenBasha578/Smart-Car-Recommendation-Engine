# kbpipe reviews run reviews_text_pilot_2026-11-15

Started 2026-11-14T20:19:00Z. Mode: no-write.

**Stopped / status:** --no-write: staged and gated, the KB was not touched

## Per model

| Model | Autocar overall (review date) | CarWale overall (ratings) | Notes kept / dropped | Themes kept / dropped | Text |
|---|---|---|---|---|---|
| Honda Amaze | 8.0 (2025-06-11) | 4.61 (207) | 0 / 0 | 0 / 0 | text stopped: checker: every backend for this role is out of quota: groq: HTTP 429 {"error":{"message":"Rate limit reached for model `openai/gpt-oss-120b` in organization `org_01m6vry2nke7xvs6e2qvnfqskr` service tier `on_de |

## Text verification (source: run.json, text_audit.jsonl)

- no text extraction ran
- writer model(s): ; checker model(s): ; independent: True
- checker backend gemini_alt ran out and was skipped: gemini_alt: HTTP 429 {
  "error": {
    "code": 429,
    "message": "You exceeded your current quota, please check your plan and billing details. For more infor
- checker backend groq ran out and was skipped: groq: HTTP 429 {"error":{"message":"Rate limit reached for model `openai/gpt-oss-120b` in organization `org_01m6vry2nke7xvs6e2qvnfqskr` service tier `on_demand`
- **text stopped** (checker out: every backend for this role is out of quota: groq: HTTP 429 {"error":{"message":"Rate limit reached for model `openai/gpt-oss-120b` in organization `org_01m6vry2nke7xvs6e2qvnfqskr` service tier `on_de) at Honda Amaze. 9 models not reached; rerun with the same command to resume from the cache.

## Counts

- change-set ops: 16 (changeset.json)
- LLM calls made: 0 (writer 0, checker 0; llm_calls.jsonl); cache hits: writer 1, checker 0
- fetches: {"network": 0, "cache": 4, "failed": 0, "bytes": 0}
- flags: 0 (flags.tsv)
- gates: {"schema": true, "provenance": true, "rows": true, "explained": true, "reviews": true}; idempotent: True
