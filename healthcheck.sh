#!/bin/sh
# healthcheck.sh — HEALTHCHECK CMD for Docker / Charity Engine
# Passes if the checkpoint or solutions file was updated in the last 15 minutes.
set -e

CID="${CONTAINER_ID:-0}"
CKPT="${CHECKPOINT_FILE:-/output/checkpoint_${CID}.json}"
SOLS="${SOLUTIONS_FILE:-/output/solutions.txt}"

MAX_AGE=900  # 15 minutes

check_age() {
    FILE="$1"
    if [ ! -f "$FILE" ]; then return 1; fi
    AGE=$(( $(date +%s) - $(date -r "$FILE" +%s 2>/dev/null || echo 0) ))
    [ "$AGE" -lt "$MAX_AGE" ]
}

if check_age "$CKPT" || check_age "$SOLS"; then
    exit 0
fi

echo "[healthcheck] Neither checkpoint nor solutions updated in ${MAX_AGE}s"
exit 1
