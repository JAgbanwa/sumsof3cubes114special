#!/usr/bin/env bash
# monitor.sh — polls every 60s, merges solutions, prints progress
REPO=/Users/jamalmac/Desktop/sumsof3cubes/sumsof3cubes114special
OUT=$REPO/output/solutions.txt

while true; do
    # Merge all slab result files
    for f in "$REPO"/output/slab_*/result.txt; do
        [ -f "$f" ] && cat "$f"
    done | sort -k1,1n -k2,2n -u > /tmp/_all_sols.txt

    total=$(wc -l < /tmp/_all_sols.txt)
    echo "$(date '+%H:%M:%S')  solutions=$total"

    # Show NEW solutions not yet in master
    if [ -f "$OUT" ]; then
        comm -13 <(sort "$OUT") <(sort /tmp/_all_sols.txt) | while IFS= read -r line; do
            echo "  *** NEW: $line"
        done
    fi

    cp /tmp/_all_sols.txt "$OUT"

    # Per-slab progress
    for ckpt in "$REPO"/output/slab_*/checkpoint.txt; do
        slab=$(basename "$(dirname "$ckpt")")
        n=$(cat "$ckpt" 2>/dev/null)
        echo "  $slab: n=$n"
    done
    echo "----"
    sleep 60
done
