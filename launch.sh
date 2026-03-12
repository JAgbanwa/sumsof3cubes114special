#!/bin/sh
# launch.sh — start the Python worker expanding outward from n=0
REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV_PYTHON="$REPO_DIR/../.venv/bin/python"
SYS_PYTHON="$(which python3)"
PYTHON="${VENV_PYTHON:-$SYS_PYTHON}"

mkdir -p "$REPO_DIR/output"
cd "$REPO_DIR"
rm -f checkpoint.txt output/solutions.txt output/worker.log

exec "$PYTHON" worker.py \
    --x_limit 1000000 \
    --output output/solutions.txt
