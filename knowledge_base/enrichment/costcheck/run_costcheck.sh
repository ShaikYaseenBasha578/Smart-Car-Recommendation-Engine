#!/bin/bash
# Cost check runner (pre-registered). 12 measured headless Sonnet runs + 2 overhead-baseline runs.
# Each run: its own folder under costcheck/runs/ holding only that run's inputs; Read tool only,
# confined to that folder (--restricted), no MCP, no slash commands, no settings files, no session
# persistence, dontAsk with prompts denied, budget cap per run.
set -u
S="$HOME/carrec_kb_scratch/enrich_flash/costcheck"; E="$(cd "$(dirname "$0")" && pwd)"
FLAGS=(--model sonnet --output-format json --restricted --tools Read --strict-mcp-config --disable-slash-commands
       --setting-sources "" --no-session-persistence --permission-mode dontAsk --permission-prompts none --max-budget-usd 2)
run() {  # $1=dir  $2=prompt-file
  ( cd "$1" && t0=$(python3 -c 'import time;print(time.time())') &&
    claude -p "$(cat "$2")" "${FLAGS[@]}" > out.json 2> err.txt < /dev/null; rc=$?
    t1=$(python3 -c 'import time;print(time.time())'); echo "rc=$rc wall_shell_s=$(python3 -c "print(round($t1-$t0,1))")" > run.meta )
}
mkdir -p "$S/runs" "$S/prompts"
for k in 1 2; do  # baseline overhead: same harness, trivial prompt
  d="$S/runs/baseline_r$k"; [ -s "$d/out.json" ] && continue
  mkdir -p "$d"; echo "Reply with the single word OK." > "$S/prompts/baseline.txt"; run "$d" "$S/prompts/baseline.txt"; echo "baseline_r$k: $(cat $d/run.meta)"
done
for rep in 1 2; do for page in syros_p7 victoris_p16 venue_p20; do for arm in extract verify; do
  d="$S/runs/${page}_${arm}_r$rep"; [ -s "$d/out.json" ] && continue
  rm -rf "$d"; mkdir -p "$d"; cp "$S/inputs/$page"/* "$d/"
  [ "$arm" = extract ] && rm -f "$d/candidates.json"
  cat "$E/prompt_common.txt" "$E/prompt_$arm.txt" "$E/prompt_output.txt" > "$S/prompts/${page}_${arm}.txt"
  run "$d" "$S/prompts/${page}_${arm}.txt"
  ls "$d" > "$S/runs/${page}_${arm}_r$rep.files_after"   # expected: the inputs + out.json err.txt run.meta only
  echo "${page}_${arm}_r$rep: $(cat $d/run.meta)"
done; done; done
