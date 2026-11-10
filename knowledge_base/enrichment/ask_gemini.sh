#!/bin/bash
# ask_gemini.sh — the only sanctioned bridge from Claude Code to Gemini (agy).
#
# Usage: ask_gemini.sh <prompt_file> [label]
#   Prints the call number (NNN) on stdout; raw agy JSON is in $SCR/calls/NNN.json.
#
# Isolation (all supported agy features, no ~/.gemini edits):
#   --agent extractor   project agent in $SCR/agy_cwd/.agents/agents/extractor.md with
#                       excludeDefaultComponents: true and tools: [] (no built-in tools)
#   --settings          session-only: toolPermission=strict, allowNonWorkspaceAccess=false,
#                       enableTerminalSandbox=true
#   --sandbox           terminal sandbox
#   the 4 API/Vertex env variables are removed so agy stays in Google sign-in mode.
#   never --dangerously-skip-permissions.
#
# Exit codes: 0 ok · 2 usage · 3 call cap reached · 4 timeout after retry ·
#             5 agy failure · 42 billing/API-key/auth-mode stop condition.
set -u
SCR="${ENRICH_SCRATCH:-$HOME/carrec_kb_scratch/enrich_flash}"
CWD="$SCR/agy_cwd"
CALLS="$SCR/calls"
LOG="$SCR/conversation.log"
CAP=80; [ -n "${ENRICH_CAP:-}" ] && [ "$ENRICH_CAP" -lt 80 ] && CAP=$ENRICH_CAP   # a round may only lower the total cap
AGY="$HOME/.local/bin/agy"
SETTINGS='{"toolPermission":"strict","allowNonWorkspaceAccess":false,"enableTerminalSandbox":true}'

[ $# -ge 1 ] && [ -f "$1" ] || { echo "usage: $0 <prompt_file> [label]" >&2; exit 2; }
PROMPT_FILE="$(cd "$(dirname "$1")" && pwd)/$(basename "$1")"; LABEL="${2:-}"
[ -s "$PROMPT_FILE" ] || { echo "empty prompt file" >&2; exit 2; }
mkdir -p "$CALLS"

# --- call counter (every agy invocation counts, retries included) ---
next_call() {
  while ! mkdir "$CALLS/.lock" 2>/dev/null; do sleep 0.2; done
  local n; n=$(cat "$CALLS/.count" 2>/dev/null || echo 0)
  if [ "$n" -ge "$CAP" ]; then rmdir "$CALLS/.lock"; echo "CAP"; return; fi
  n=$((n+1)); echo "$n" > "$CALLS/.count"; rmdir "$CALLS/.lock"
  printf '%03d' "$n"
}

ts() { date -u +%Y-%m-%dT%H:%M:%SZ; }

run_once() {  # $1 = NNN
  local id="$1" t0 t1 rc
  {
    printf '\n════ CLAUDE → GEMINI [#%s] %s %s ════\n' "$id" "$(ts)" "$LABEL"
    head -n 40 "$PROMPT_FILE"
    local nl; nl=$(wc -l < "$PROMPT_FILE" | tr -d ' ')
    [ "$nl" -gt 40 ] && printf '… [%s more lines truncated]\n' "$((nl-40))"
  } >> "$LOG"
  t0=$(python3 -c 'import time;print(time.time())')
  local prompt; prompt="$(cat "$PROMPT_FILE")"
  ( cd "$CWD" && env -u GEMINI_API_KEY -u GOOGLE_API_KEY -u GOOGLE_GENAI_USE_VERTEXAI -u GOOGLE_CLOUD_PROJECT \
      "$AGY" -p "$prompt" --agent extractor --sandbox --settings "$SETTINGS" \
      --effort low --output-format json --print-timeout 300s \
      --log-file "$CALLS/$id.agy.log" ) > "$CALLS/$id.json" 2> "$CALLS/$id.err" < /dev/null
  rc=$?
  t1=$(python3 -c 'import time;print(time.time())')
  local secs; secs=$(python3 -c "print(f'{$t1-$t0:.1f}')")
  cp "$PROMPT_FILE" "$CALLS/$id.prompt.txt"
  python3 - "$CALLS/$id.json" "$rc" "$secs" "$id" "$LABEL" >> "$CALLS/index.tsv" <<'PY'
import json,sys
p,rc,secs,i,label=sys.argv[1:]
try: d=json.load(open(p))
except Exception: d={}
print("\t".join([i,label,rc,secs,str(d.get("status","")),str(d.get("duration_seconds","")),
                 json.dumps(d.get("denied_actions",[]))]))
PY
  local answer
  answer=$(python3 -c "
import json,sys
try: d=json.load(open('$CALLS/$id.json'))
except Exception as e: print('[no JSON on stdout: %s]'%e); sys.exit()
print(d.get('response') if d.get('response') is not None else json.dumps(d)[:4000])
if d.get('denied_actions'): print('[denied_actions] '+json.dumps(d['denied_actions']))
")
  {
    printf '════ GEMINI → CLAUDE [#%s] (%ss) rc=%s ════\n' "$id" "$secs" "$rc"
    printf '%s\n' "$answer"
  } >> "$LOG"
  echo "$rc"
}

stop_check() {  # $1 = NNN ; billing / API key / auth-mode stop condition
  local id="$1"
  if grep -i -q -E 'billing|api[ _-]?key|paid plan|purchase|upgrade your plan' "$CALLS/$id.json" "$CALLS/$id.err" 2>/dev/null; then
    echo "STOP: billing/API-key wording in agy output for call $id" | tee -a "$LOG" >&2; return 1
  fi
  if ! grep -q 'authMethod=consumer' "$CALLS/$id.agy.log" 2>/dev/null; then
    echo "STOP: agy log for call $id does not show authMethod=consumer (Google sign-in)" | tee -a "$LOG" >&2; return 1
  fi
  return 0
}

is_timeout() {
  grep -q -E 'DEADLINE_EXCEEDED|timed out|print-timeout' "$CALLS/$1.json" "$CALLS/$1.err" 2>/dev/null
}

ID=$(next_call); [ "$ID" = "CAP" ] && { echo "REFUSED: $CAP-call cap reached" | tee -a "$LOG" >&2; exit 3; }
RC=$(run_once "$ID")
stop_check "$ID" || { echo "$ID"; exit 42; }
if [ "$RC" != "0" ] && is_timeout "$ID"; then
  echo "[#$ID timed out; retrying once]" >> "$LOG"
  ID2=$(next_call); [ "$ID2" = "CAP" ] && { echo "REFUSED: $CAP-call cap reached" | tee -a "$LOG" >&2; echo "$ID"; exit 3; }
  echo "$ID2" > "$CALLS/$ID.retry"
  RC=$(run_once "$ID2"); ID="$ID2"
  stop_check "$ID" || { echo "$ID"; exit 42; }
  if [ "$RC" != "0" ] && is_timeout "$ID"; then echo "$ID"; exit 4; fi
fi
echo "$ID"
[ "$RC" = "0" ] || exit 5
exit 0
