#!/bin/bash
# watch.sh — live view of the Claude ⇄ Gemini conversation for the owner.
# Usage: watch.sh   (run in a second tmux pane)
LOG="${ENRICH_SCRATCH:-$HOME/carrec_kb_scratch/enrich_flash}/conversation.log"
touch "$LOG"
C=$'\033[1;36m'; G=$'\033[1;32m'; R=$'\033[1;31m'; Y=$'\033[0;33m'; N=$'\033[0m'
tail -n 200 -f "$LOG" | while IFS= read -r line; do
  case "$line" in
    "════ CLAUDE → GEMINI"*) printf '%s%s%s\n' "$C" "$line" "$N" ;;
    "════ GEMINI → CLAUDE"*) printf '%s%s%s\n' "$G" "$line" "$N" ;;
    STOP:*|REFUSED:*)        printf '%s%s%s\n' "$R" "$line" "$N" ;;
    "["*)                    printf '%s%s%s\n' "$Y" "$line" "$N" ;;
    *)                       printf '%s\n' "$line" ;;
  esac
done
