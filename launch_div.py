#!/usr/bin/env python3
"""
launch_div.py
=============
Launches worker_div (divisibility-specialized, 36n² pre-filter) across
the full n range. Because f(x,n) ≡ 0 (mod 36n²) kills ~36n² out of every
36n² candidates, we can afford large x_limit at no extra cost for big n.

Usage:
    python3 launch_div.py            # launch all slabs
    python3 launch_div.py --status   # live status
    python3 launch_div.py --kill     # stop all worker_div processes
"""
import argparse, os, subprocess, sys, time
from pathlib import Path

REPO       = Path(__file__).parent
BIN        = REPO / "worker_div"
OUTPUT_DIR = REPO / "output"

# (label, n_start, n_end, x_limit)
# x_limit is generous because 36n² pre-filter is tight for large n
SLABS = [
    # ── small n: exhaustive ─────────────────────────────────────────────
    ("div_neg10k_0",           -10_000,          -1,  10_000_000),
    ("div_0_10k",                    0,      10_000,  10_000_000),
    # ── medium n ────────────────────────────────────────────────────────
    ("div_neg100k_neg10k",     -100_000,     -10_001,   5_000_000),
    ("div_10k_100k",             10_001,     100_000,   5_000_000),
    # ── large n ─────────────────────────────────────────────────────────
    ("div_neg1M_neg100k",    -1_000_000,    -100_001,   2_000_000),
    ("div_100k_1M",             100_001,   1_000_000,   2_000_000),
    # ── very large n ────────────────────────────────────────────────────
    ("div_neg10M_neg1M",    -10_000_000,  -1_000_001,   1_000_000),
    ("div_1M_10M",            1_000_001,  10_000_000,   1_000_000),
    # ── extreme n ───────────────────────────────────────────────────────
    ("div_neg100M_neg10M",  -100_000_000, -10_000_001,    500_000),
    ("div_10M_100M",          10_000_001, 100_000_000,    500_000),
    ("div_neg1B_neg100M",  -1_000_000_000,-100_000_001,   200_000),
    ("div_100M_1B",          100_000_001,1_000_000_000,   200_000),
]


def launch_slab(label, n_start, n_end, x_limit):
    slab_dir = OUTPUT_DIR / f"slab_{label}"
    slab_dir.mkdir(parents=True, exist_ok=True)
    wu     = slab_dir / "wu.txt"
    result = slab_dir / "result.txt"
    log    = slab_dir / "worker.log"
    wu.write_text(f"n_start {n_start}\nn_end   {n_end}\nx_limit {x_limit}\n")
    cmd = [str(BIN), str(wu), str(result)]
    with open(log, "a") as lf:
        proc = subprocess.Popen(cmd, stdout=lf, stderr=lf, cwd=str(slab_dir))
    print(f"[div]  {label:<28}  n=[{n_start:>14},{n_end:>14}]  "
          f"x_limit={x_limit:>10,}  pid={proc.pid}")
    return proc


def running_pids():
    r = subprocess.run(["pgrep", "-f", str(BIN)],
                       capture_output=True, text=True)
    return [int(p) for p in r.stdout.split() if p.strip()]


def show_status():
    pids = running_pids()
    print(f"=== {len(pids)} worker_div process(es) running ===")
    print("\n=== CHECKPOINTS ===")
    for ck in sorted(OUTPUT_DIR.glob("slab_div_*/checkpoint.txt")):
        n = ck.read_text().strip()
        wu = (ck.parent / "wu.txt").read_text()
        n1 = [l.split()[1] for l in wu.splitlines() if l.startswith("n_end")][0]
        pct = ""
        try:
            nc, ne = int(n), int(n1)
            wu_start = int([l.split()[1] for l in wu.splitlines()
                            if l.startswith("n_start")][0])
            total = ne - wu_start
            done  = nc - wu_start
            pct = f"  ({100*done//max(total,1)}%)" if total > 0 else ""
        except Exception:
            pass
        print(f"  {ck.parent.name:<36}  n={n:>14} / {n1}{pct}")

    print("\n=== DIV-SOLUTIONS (y/(6n) integer) ===")
    seen = {}
    for f in sorted(OUTPUT_DIR.glob("slab_div_*/result.txt")):
        for line in f.read_text().splitlines():
            parts = line.strip().split()
            if len(parts) == 4:
                try:
                    n, x, y, k = int(parts[0]),int(parts[1]),int(parts[2]),int(parts[3])
                    key = (n, x, abs(y))
                    seen[key] = (n, x, abs(y), abs(k))
                except ValueError:
                    pass
    rows = sorted(seen.values(), key=lambda r: (abs(r[0]), r[0], r[1]))
    for n, x, y, k in rows:
        print(f"  n={n:>12}  x={x:>15}  y=±{y:<25}  y/(6n)=±{k}")
    print(f"  Total: {len(rows)} family/families")


def kill_all():
    for pid in running_pids():
        try:
            os.kill(pid, 15)
            print(f"[kill] {pid}")
        except ProcessLookupError:
            pass


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--status", action="store_true")
    p.add_argument("--kill",   action="store_true")
    args = p.parse_args()

    if args.kill:   kill_all();    return
    if args.status: show_status(); return

    if not BIN.exists():
        print(f"ERROR: {BIN} missing.\nRun: gcc -O3 -march=native -std=c99 "
              f"-o worker_div worker_div.c -lm", file=sys.stderr)
        sys.exit(1)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Launching {len(SLABS)} worker_div slabs (36n² pre-filter active)\n")

    procs = []
    for s in SLABS:
        procs.append(launch_slab(*s))
        time.sleep(0.05)

    print(f"\nAll {len(procs)} div-workers launched.")
    print("Monitor : python3 launch_div.py --status")
    print("Solutions will appear in output/slab_div_*/result.txt")
    print("Also run: python3 filter_divisible.py  (checks all workers combined)")


if __name__ == "__main__":
    main()
