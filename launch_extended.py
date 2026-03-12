#!/usr/bin/env python3
"""
launch_extended.py
==================
Launches additional C workers covering n ∈ ±5M … ±200M.
Each slab runs in its own subdirectory under output/ so checkpoint.txt
is isolated.  Solutions land in output/slab_*/result.txt and are merged
by merge_solutions.py.

Usage:
    python3 launch_extended.py            # launch all extended slabs
    python3 launch_extended.py --status   # show running workers + solutions
    python3 launch_extended.py --kill     # stop all /worker processes
"""

import argparse, os, subprocess, sys, time
from pathlib import Path

REPO       = Path(__file__).parent
WORKER_BIN = REPO / "worker"
OUTPUT_DIR = REPO / "output"

# (label, n_start, n_end, x_limit)
# x_limit deliberately conservative for large |n| — solutions cluster near
# the curve's minimum which stays within a modest x window even for big n.
EXTENDED_SLABS = [
    # ── n < 0 ───────────────────────────────────────────────────────────────
    ("neg5M_neg1M_A",    -5_000_000,  -3_000_001,  300_000),
    ("neg5M_neg1M_B",    -3_000_000,  -1_000_001,  300_000),
    ("neg20M_neg5M_A",  -20_000_000, -12_500_001,  200_000),
    ("neg20M_neg5M_B",  -12_500_000,  -5_000_001,  200_000),
    ("neg50M_neg20M_A", -50_000_000, -35_000_001,  150_000),
    ("neg50M_neg20M_B", -35_000_000, -20_000_001,  150_000),
    ("neg200M_neg50M_A",-200_000_000,-125_000_001, 100_000),
    ("neg200M_neg50M_B",-125_000_000, -50_000_001, 100_000),
    # ── n > 0 ───────────────────────────────────────────────────────────────
    ("5M_20M_A",          5_000_001,  12_500_000,  200_000),
    ("5M_20M_B",         12_500_001,  20_000_000,  200_000),
    ("20M_50M_A",        20_000_001,  35_000_000,  150_000),
    ("20M_50M_B",        35_000_001,  50_000_000,  150_000),
    ("50M_200M_A",       50_000_001, 125_000_000,  100_000),
    ("50M_200M_B",      125_000_001, 200_000_000,  100_000),
]


def launch_slab(label, n_start, n_end, x_limit):
    slab_dir = OUTPUT_DIR / f"slab_{label}"
    slab_dir.mkdir(parents=True, exist_ok=True)

    wu = slab_dir / "wu.txt"
    wu.write_text(f"n_start {n_start}\nn_end   {n_end}\nx_limit {x_limit}\n")

    result = slab_dir / "result.txt"
    log    = slab_dir / "worker.log"

    cmd = [str(WORKER_BIN), str(wu), str(result)]
    with open(log, "a") as lf:
        proc = subprocess.Popen(cmd, stdout=lf, stderr=lf, cwd=str(slab_dir))

    print(f"[launch] {label:<28}  n=[{n_start:>14},{n_end:>14}]  "
          f"x_limit={x_limit:>8,}  pid={proc.pid}")
    return proc


def running_pids():
    r = subprocess.run(["pgrep", "-f", str(WORKER_BIN)],
                       capture_output=True, text=True)
    return [int(p) for p in r.stdout.split() if p.strip()]


def show_status():
    pids = running_pids()
    print(f"=== {len(pids)} WORKER(S) RUNNING ===")
    for p in pids:
        print(f"  pid={p}")

    print("\n=== CHECKPOINTS ===")
    for ck in sorted(OUTPUT_DIR.glob("slab_*/checkpoint.txt")):
        n = ck.read_text().strip()
        wu = (ck.parent / "wu.txt").read_text()
        n1 = [l.split()[1] for l in wu.splitlines() if l.startswith("n_end")][0]
        print(f"  {ck.parent.name:<36}  n={n:>14} / {n1}")

    print("\n=== SOLUTIONS (all slabs) ===")
    subprocess.run(["python3", str(REPO / "merge_solutions.py")])


def kill_all():
    for pid in running_pids():
        os.kill(pid, 15)
        print(f"[kill] {pid}")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--status", action="store_true")
    p.add_argument("--kill",   action="store_true")
    args = p.parse_args()

    if args.kill:   kill_all();    return
    if args.status: show_status(); return

    if not WORKER_BIN.exists():
        print(f"ERROR: {WORKER_BIN} missing — run: make", file=sys.stderr)
        sys.exit(1)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Launching {len(EXTENDED_SLABS)} extended workers\n")

    procs = []
    for args_slab in EXTENDED_SLABS:
        p = launch_slab(*args_slab)
        procs.append(p)
        time.sleep(0.05)

    print(f"\nAll {len(procs)} extended workers launched.")
    print("Monitor : python3 launch_extended.py --status")
    print("Merge   : python3 merge_solutions.py && git add solutions.txt && git commit -m 'solutions update' && git push")


if __name__ == "__main__":
    main()
