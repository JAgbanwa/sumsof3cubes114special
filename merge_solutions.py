#!/usr/bin/env python3
"""
merge_solutions.py
Collects all found solutions from per-slab result files and the legacy
output/solutions.txt, deduplicates, and writes to top-level solutions.txt
(which IS tracked by git).
"""
from pathlib import Path

REPO = Path(__file__).parent
seen = {}

sources = (
    list(REPO.glob("output/slab_*/result.txt")) +
    [REPO / "output/solutions.txt"]
)

for f in sources:
    if not f.exists():
        continue
    for line in f.read_text().splitlines():
        parts = line.strip().split()
        if len(parts) == 3:
            try:
                n, x, y = int(parts[0]), int(parts[1]), int(parts[2])
            except ValueError:
                continue
            key = (n, x, abs(y))
            if key not in seen:
                seen[key] = (n, x, abs(y))

# Sort by |n|, then n, then x
rows = sorted(seen.values(), key=lambda k: (abs(k[0]), k[0], k[1]))

header = "# n x |y|   (solutions come in ±y pairs)"
lines = [header] + [f"n={n}  x={x}  y=\xb1{y}" for n, x, y in rows]

out = REPO / "solutions.txt"
out.write_text("\n".join(lines) + "\n")

print(f"solutions.txt: {len(rows)} solution families")
for n, x, y in rows:
    print(f"  n={n:>10}  x={x:>15}  y=\xb1{y}")
