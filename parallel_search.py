#!/usr/bin/env python3
"""
parallel_search.py
==================
Launches multiple C worker processes in parallel, each covering a distinct
slab of n-space.  All solutions appended to a single unified file.

Coverage plan (change SLABS if you want bigger ranges):
  Slab  0:  n ∈ [        -5 000 000,         -1 000 001]   x_limit  500 000
  Slab  1:  n ∈ [        -1 000 000,           -100 001]   x_limit  750 000
  Slab  2:  n ∈ [          -100 000,            -10 001]   x_limit 1 000 000
  Slab  3:  n ∈ [           -10 000,                  0]   x_limit 2 000 000
  Slab  4:  n ∈ [                 1,             10 000]   x_limit 2 000 000
  Slab  5:  n ∈ [            10 001,            100 000]   x_limit 1 000 000
  Slab  6:  n ∈ [           100 001,          1 000 000]   x_limit  750 000
  Slab  7:  n ∈ [         1 000 001,          5 000 000]   x_limit  500 000

Extends automatically — uncomment EXTEND_SLABS lines or pass --extend to add
slabs up to ±50 million.

Usage:
    python3 parallel_search.py              # launch all slabs
    python3 parallel_search.py --status     # show running workers + solutions
    python3 parallel_search.py --extend     # add slabs up to ±50M
    python3 parallel_search.py --kill       # stop all workers
"""

import argparse
import os
import sys
import subprocess
import time
import stat
from pathlib import Path

REPO = Path(__file__).parent
WORKER_BIN  = REPO / "worker"
OUTPUT_DIR  = REPO / "output"
MASTER_FILE = OUTPUT_DIR / "solutions.txt"

# Each slab: (label, n_start, n_end, x_limit)
BASE_SLABS = [
    ("neg5M_neg1M",        -5_000_000,   -1_000_001,   500_000),
    ("neg1M_neg100k",      -1_000_000,     -100_001,   750_000),
    ("neg100k_neg10k",       -100_000,      -10_001, 1_000_000),
    ("neg10k_0",              -10_000,           -1, 2_000_000),
    ("0_10k",                       0,       10_000, 2_000_000),
    ("10k_100k",               10_001,      100_000, 1_000_000),
    ("100k_1M",               100_001,    1_000_000,   750_000),
    ("1M_5M",               1_000_001,    5_000_000,   500_000),
]

EXTEND_SLABS = [
    ("neg50M_neg5M",       -50_000_000,  -5_000_001,   250_000),
    ("5M_50M",              5_000_001,   50_000_000,   250_000),
]


def build_binary():
    """Ensure the C worker is compiled and up to date."""
    src = REPO / "worker.c"
    if not src.exists():
        print(f"ERROR: {src} not found", file=sys.stderr)
        sys.exit(1)
    print(f"[build] Compiling {src} ...")
    r = subprocess.run(
        ["gcc", "-O3", "-march=native", "-std=c99", "-Wall",
         "-o", str(WORKER_BIN), str(src), "-lm"],
        capture_output=True, text=True, cwd=REPO
    )
    if r.returncode != 0:
        print(f"[build] FAILED:\n{r.stderr}", file=sys.stderr)
        sys.exit(1)
    print(f"[build] OK → {WORKER_BIN}")


def make_wu(label, n_start, n_end, x_limit):
    wu_path = OUTPUT_DIR / f"wu_{label}.txt"
    wu_path.write_text(f"n_start {n_start}\nn_end   {n_end}\nx_limit {x_limit}\n")
    return wu_path


def launch_slab(label, n_start, n_end, x_limit):
    # Each slab gets its OWN subdirectory so checkpoint.txt doesn't collide
    slab_dir = OUTPUT_DIR / f"slab_{label}"
    slab_dir.mkdir(parents=True, exist_ok=True)

    # WU file inside slab dir (worker reads "wu.txt" from cwd by default,
    # but we pass the absolute path so it works regardless of cwd)
    wu = slab_dir / "wu.txt"
    wu.write_text(f"n_start {n_start}\nn_end   {n_end}\nx_limit {x_limit}\n")

    result = slab_dir / "result.txt"
    log    = slab_dir / "worker.log"

    # argv[1]=wu, argv[2]=result (absolute paths); cwd=slab_dir → checkpoint.txt
    # stays isolated in that subdir
    cmd = [str(WORKER_BIN), str(wu), str(result)]

    with open(log, "a") as lf:
        proc = subprocess.Popen(
            cmd,
            stdout=lf, stderr=lf,
            cwd=str(slab_dir)   # checkpoint.txt written here, isolated
        )
    print(f"[launch] slab={label:<22} n=[{n_start:>12},{n_end:>12}]  "
          f"x_limit={x_limit:>9,}  pid={proc.pid}")
    return proc


def get_all_solutions():
    """Merge all per-slab result files into the master file."""
    seen = set()
    all_lines = []

    # existing master
    if MASTER_FILE.exists():
        for line in MASTER_FILE.read_text().splitlines():
            if line and not line.startswith("#"):
                all_lines.append(line)
                seen.add(line)

    # per-slab results (now live in OUTPUT_DIR/slab_<label>/result.txt)
    for rfile in sorted(OUTPUT_DIR.glob("slab_*/result.txt")):
        for line in rfile.read_text().splitlines():
            line = line.strip()
            if line and line not in seen:
                all_lines.append(line)
                seen.add(line)

    return all_lines


def merge_solutions():
    lines = get_all_solutions()
    # Parse and de-dup by (n, x, |y|)
    unique = {}
    for l in lines:
        parts = l.split()
        if len(parts) == 3:
            try:
                n, x, y = int(parts[0]), int(parts[1]), int(parts[2])
                key = (n, x, abs(y))
                if key not in unique:
                    unique[key] = l
            except ValueError:
                pass
    # Sort by n, then x
    sorted_keys = sorted(unique.keys(), key=lambda k: (abs(k[0]), k[0], k[1]))
    MASTER_FILE.write_text("\n".join(unique[k] for k in sorted_keys) + "\n")
    return len(unique)


def show_status():
    """Print running workers, progress, and all solutions."""
    import subprocess as sp
    r = sp.run(["ps", "ax", "-o", "pid,etime,command"],
               capture_output=True, text=True)
    workers = [l for l in r.stdout.splitlines()
               if "worker" in l and "worker.py" not in l
               and "mdworker" not in l and "fontworker" not in l
               and "Code" not in l and "grep" not in l]
    print("=== RUNNING C WORKERS ===")
    for w in workers:
        print(" ", w.strip())

    print("\n=== LAST LOG LINES PER SLAB ===")
    for log in sorted(OUTPUT_DIR.glob("slab_*/worker.log")):
        lines = log.read_text().strip().splitlines()
        last = lines[-1] if lines else "(empty)"
        label = log.parent.name
        print(f"  {label}: {last}")

    print("\n=== SOLUTIONS ===")
    count = merge_solutions()
    for line in MASTER_FILE.read_text().strip().splitlines():
        print(" ", line)
    print(f"  Total unique solution families: {count}")


def kill_all():
    import signal as sig
    import subprocess as sp
    r = sp.run(["ps", "ax", "-o", "pid,command"],
               capture_output=True, text=True)
    killed = 0
    for l in r.stdout.splitlines():
        if str(WORKER_BIN) in l or "./worker" in l:
            pid = int(l.split()[0])
            try:
                os.kill(pid, sig.SIGTERM)
                print(f"[kill] pid={pid}")
                killed += 1
            except ProcessLookupError:
                pass
    print(f"[kill] terminated {killed} workers")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--status",  action="store_true")
    parser.add_argument("--kill",    action="store_true")
    parser.add_argument("--extend",  action="store_true",
                        help="Add slabs ±5M–50M")
    parser.add_argument("--rebuild", action="store_true",
                        help="Force recompile worker.c")
    args = parser.parse_args()

    if args.kill:
        kill_all(); return

    if args.status:
        show_status(); return

    # Build binary
    if args.rebuild or not WORKER_BIN.exists():
        build_binary()
    elif not WORKER_BIN.exists():
        build_binary()

    slabs = BASE_SLABS + (EXTEND_SLABS if args.extend else [])

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"[parallel_search] Launching {len(slabs)} workers")
    print(f"[parallel_search] Solutions → {MASTER_FILE}")
    print()

    procs = []
    for (label, n0, n1, xlim) in slabs:
        p = launch_slab(label, n0, n1, xlim)
        procs.append((label, p))
        time.sleep(0.1)

    print(f"\n[parallel_search] All {len(procs)} workers launched.")
    print( "[parallel_search] Monitor: python3 parallel_search.py --status")
    print( "[parallel_search] Stop:    python3 parallel_search.py --kill")
    print()

    # Watch loop: merge solutions every 30 s
    try:
        while any(p.poll() is None for _, p in procs):
            time.sleep(30)
            n = merge_solutions()
            still = sum(1 for _, p in procs if p.poll() is None)
            print(f"[watcher] running={still}/{len(procs)}  solutions={n}",
                  flush=True)
    except KeyboardInterrupt:
        print("\n[parallel_search] Interrupted. Workers continue in background.")
        print("[parallel_search] Run --status to check, --kill to stop.")

    # Final merge
    n = merge_solutions()
    print(f"[parallel_search] Final solutions written: {n}")


if __name__ == "__main__":
    main()
