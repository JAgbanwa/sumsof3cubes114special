#!/bin/sh
# run.sh — Charity Engine / Docker entrypoint
#
# Preference order for persistence:
#   1. /output (mounted by CE or docker -v)
#   2. /data   (legacy mount)
#   3. /app    (fallback, in-container only)
#
# Environment variables forwarded straight to worker.py:
#   N_START, N_END, X_LIMIT, CONTAINER_ID, TOTAL_SHARDS

set -e

# Pick a writable output dir
for d in /output /data /app; do
    if mkdir -p "$d" 2>/dev/null && touch "$d/.wtest" 2>/dev/null; then
        rm -f "$d/.wtest"
        OUTPUT_DIR="$d"
        break
    fi
done
export OUTPUT_DIR="${OUTPUT_DIR:-/app}"

# Build checkpoint path from CONTAINER_ID (default 0)
CID="${CONTAINER_ID:-0}"
export CHECKPOINT_FILE="${CHECKPOINT_FILE:-${OUTPUT_DIR}/checkpoint_${CID}.json}"
export SOLUTIONS_FILE="${SOLUTIONS_FILE:-${OUTPUT_DIR}/solutions.txt}"

echo "[run.sh] OUTPUT_DIR=$OUTPUT_DIR"
echo "[run.sh] CHECKPOINT_FILE=$CHECKPOINT_FILE"
echo "[run.sh] SOLUTIONS_FILE=$SOLUTIONS_FILE"
echo "[run.sh] CONTAINER_ID=${CONTAINER_ID:-0}  TOTAL_SHARDS=${TOTAL_SHARDS:-1}"
echo "[run.sh] X_LIMIT=${X_LIMIT:-10000000}"

# If a C binary exists use it via wu.txt; otherwise fall back to Python worker.
# The Python worker is CE-compatible and handles its own checkpoint/shard.

if [ -x /app/worker ] && [ -n "${N_START}" ] && [ -n "${N_END}" ]; then
    echo "[run.sh] Using C worker for n=${N_START}..${N_END}"
    printf "n_start %s\nn_end   %s\nx_limit %s\n" \
        "${N_START}" "${N_END}" "${X_LIMIT:-10000000}" > /tmp/wu.txt
    export CHECKPOINT_FILE="${CHECKPOINT_FILE}"
    exec /app/worker /tmp/wu.txt "${SOLUTIONS_FILE}"
else
    echo "[run.sh] Using Python worker (endless mode)"
    ARGS=""
    [ -n "${N_START}" ]  && ARGS="$ARGS --n_start ${N_START}"
    [ -n "${N_END}" ]    && ARGS="$ARGS --n_end ${N_END}"
    [ -n "${X_LIMIT}" ]  && ARGS="$ARGS --x_limit ${X_LIMIT}"
    ARGS="$ARGS --output ${SOLUTIONS_FILE}"
    exec python /app/worker.py $ARGS
fi
