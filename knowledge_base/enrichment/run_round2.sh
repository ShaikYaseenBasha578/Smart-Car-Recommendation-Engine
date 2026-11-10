#!/bin/bash
# Round 2: one agy call per gold page via ask_gemini.sh (isolation unchanged). Round cap: 40 calls,
# enforced as a total cap of (calls used before the round + 40), never above 80.
set -u
S="$HOME/carrec_kb_scratch/enrich_flash"; E="$(cd "$(dirname "$0")" && pwd)"
START=$(cat "$S/calls/.count"); export ENRICH_CAP=$(( START + 40 < 80 ? START + 40 : 80 ))
echo "round 2: calls used before = $START, cap = $ENRICH_CAP"
for f in "$S"/prompts_r2/*.prompt.txt; do
  b=$(basename "$f" .prompt.txt)
  [ -s "$S/prompts_r2/$b.callid" ] && { echo "$b already done"; continue; }
  id=$("$E/ask_gemini.sh" "$f" "r2 $b"); rc=$?
  echo "$b -> call $id rc=$rc"
  [ $rc -eq 0 ] && echo "$id" > "$S/prompts_r2/$b.callid"
  [ $rc -eq 42 ] || [ $rc -eq 3 ] && { echo "STOP rc=$rc"; exit $rc; }
done
