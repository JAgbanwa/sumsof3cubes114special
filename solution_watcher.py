#!/usr/bin/env python3
"""
solution_watcher.py
Polls all slab result files every N seconds. When new solutions appear,
merges them into solutions.txt and pushes to GitHub automatically.
Run in the background:
    nohup python3 solution_watcher.py &
"""
import time, subprocess, hashlib
from pathlib import Path

REPO       = Path(__file__).parent
INTERVAL   = 300   # seconds between polls
GIT        = ["git", "-C", str(REPO)]


def collect_raw():
    lines = set()
    for f in REPO.glob("output/slab_*/result.txt"):
        for l in f.read_text().splitlines():
            parts = l.strip().split()
            if len(parts) == 3:
                try:
                    n, x, y = int(parts[0]), int(parts[1]), int(parts[2])
                    lines.add((n, x, abs(y)))
                except ValueError:
                    pass
    return lines


def write_solutions(rows):
    rows = sorted(rows, key=lambda k: (abs(k[0]), k[0], k[1]))
    header = "# n x |y|   (solutions come in ±y pairs)"
    lines  = [header] + [f"n={n}  x={x}  y=\xb1{y}" for n, x, y in rows]
    (REPO / "solutions.txt").write_text("\n".join(lines) + "\n")
    return rows


def git_push(count):
    subprocess.run(GIT + ["add", "solutions.txt"], check=False)
    subprocess.run(GIT + ["commit", "-m",
        f"Auto-update: {count} solution families found by workers"],
        check=False)
    subprocess.run(GIT + ["push", "origin", "main"], check=False)


def worker_count():
    r = subprocess.run(["pgrep", "-f", str(REPO / "worker")],
                       capture_output=True, text=True)
    return len([p for p in r.stdout.split() if p.strip()])


known = collect_raw()
write_solutions(known)
print(f"[watcher] starting — {len(known)} known solutions, "
      f"{worker_count()} workers running")

while True:
    time.sleep(INTERVAL)
    current = collect_raw()
    wc      = worker_count()
    if current != known:
        new = current - known
        print(f"[watcher] {len(new)} NEW solution(s): {sorted(new)}")
        rows = write_solutions(current)
        git_push(len(rows))
        known = current
    else:
        print(f"[watcher] tick — {len(current)} solutions, {wc} workers running")
    if wc == 0:
        print("[watcher] all workers done — final merge + push")
        rows = write_solutions(current)
        git_push(len(rows))
        break
