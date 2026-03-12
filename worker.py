#!/usr/bin/env python3
"""
worker.py — Endless Python worker for sumsof3cubes114special.

Searches all integers n (expanding outward from 0) for solutions to:

    y² = x³ + 81·(4n+3)²·x² + 243·(4n+3)³·x
           + (4n+3)·(11664n³ + 26244n² + 19683n + 4916)

Designed to run as a Charity Engine Docker app or standalone.

Environment variables (CE interface):
    N_START      — start of n range (default: expand from 0)
    N_END        — end of n range   (default: forever)
    X_LIMIT      — max |x| to test per n (default: 10_000_000)
    CONTAINER_ID — CE shard ID (default: 0)
    TOTAL_SHARDS — total CE shards (default: 1)
    OUTPUT_DIR   — where to write results (default: /output or ./output)
    CHECKPOINT_FILE — checkpoint path

Usage:
    python3 worker.py
    python3 worker.py --n_start 0 --n_end 100000 --x_limit 5000000
"""

import os, sys, time, math, json, signal, argparse
from pathlib import Path

# ── gmpy2 for fast isqrt ──────────────────────────────────────────────────────
try:
    from gmpy2 import mpz, isqrt_rem
    def _isqrt(v):
        s, r = isqrt_rem(mpz(v))
        return int(s), (r == 0)
    USE_GMPY = True
except ImportError:
    import math as _math
    def _isqrt(v):
        s = _math.isqrt(v)
        return s, (s * s == v)
    USE_GMPY = False

# ── Config ────────────────────────────────────────────────────────────────────
CONTAINER_ID   = int(os.environ.get("CONTAINER_ID",   "0"))
TOTAL_SHARDS   = int(os.environ.get("TOTAL_SHARDS",   "1"))
X_LIMIT        = int(os.environ.get("X_LIMIT",        "10000000"))
_out_default   = "/output" if Path("/output").exists() else "./output"
OUTPUT_DIR     = Path(os.environ.get("OUTPUT_DIR", _out_default))
CKPT_FILE      = os.environ.get("CHECKPOINT_FILE",
                                str(OUTPUT_DIR / f"checkpoint_{CONTAINER_ID}.json"))
SOLUTIONS_FILE = str(OUTPUT_DIR / "solutions.txt")
PROGRESS_INTERVAL = 2000          # print progress every N n-values

# ── Graceful shutdown ──────────────────────────────────────────────────────────
_running = True
def _stop(sig, _):
    global _running; _running = False
    print("\n[worker] Shutdown signal — finishing current n...", flush=True)
signal.signal(signal.SIGTERM, _stop)
signal.signal(signal.SIGINT,  _stop)

# ── Arithmetic ────────────────────────────────────────────────────────────────
SIEVE_PRIMES = [3, 5, 7, 11, 13, 17, 19, 23, 29, 31]
QR = {p: frozenset((x*x) % p for x in range(p)) for p in SIEVE_PRIMES}

def coeff(n):
    t = 4*n + 3
    A = 81  * t * t
    B = 243 * t * t * t
    C = t * (11664*n**3 + 26244*n**2 + 19683*n + 4916)
    return A, B, C

def fval(x, A, B, C):
    return x*x*x + A*x*x + B*x + C

def sieve_pass(x, A, B, C, n):
    for p in SIEVE_PRIMES:
        xm = x % p; Am = A % p; Bm = B % p; Cm = C % p
        fm = (xm*xm*xm + Am*xm*xm + Bm*xm + Cm) % p
        if fm not in QR[p]:
            return False
    return True

def lower_bound(n, A_f, B_f, C_f):
    xf = -abs(A_f) - 10.0
    for _ in range(80):
        fv = xf**3 + A_f*xf**2 + B_f*xf + C_f
        df = 3*xf**2 + 2*A_f*xf + B_f
        if abs(df) < 1e-40: break
        xf -= fv / df
    return int(math.floor(xf)) - 3

def search_n(n, xlim):
    A, B, C = coeff(n)
    Af, Bf, Cf = float(A), float(B), float(C)
    sols = []

    for x in range(0, xlim + 1):
        if not sieve_pass(x, A, B, C, n): continue
        v = fval(x, A, B, C)
        if v < 0: continue
        s, exact = _isqrt(v)
        if exact:
            sols.append((n, x,  s))
            if s: sols.append((n, x, -s))

    lb = lower_bound(n, Af, Bf, Cf)
    for x in range(max(-xlim, lb), 0):
        if not sieve_pass(x, A, B, C, n): continue
        v = fval(x, A, B, C)
        if v < 0: continue
        s, exact = _isqrt(v)
        if exact:
            sols.append((n, x,  s))
            if s: sols.append((n, x, -s))
    return sols

# ── Checkpoint ────────────────────────────────────────────────────────────────
def load_ckpt():
    try:
        with open(CKPT_FILE) as f:
            return json.load(f).get("next_n", None)
    except Exception:
        return None

def save_ckpt(next_n, total_done, total_sols):
    with open(CKPT_FILE, "w") as f:
        json.dump({"next_n": next_n, "total_done": total_done,
                   "total_sols": total_sols, "ts": time.time()}, f)

# ── n iterator ────────────────────────────────────────────────────────────────
def n_iter(n_start, n_end, shard_id, total_shards):
    """
    If n_start/n_end given: iterate that range, taking every total_shards-th n.
    Otherwise: expand outward from 0, taking every total_shards-th value.
    """
    if n_start is not None and n_end is not None:
        for n in range(n_start + shard_id, n_end + 1, total_shards):
            yield n
        return
    radius = shard_id
    step   = total_shards
    while True:
        if radius == 0:
            yield 0
            radius += step
            continue
        yield -radius
        yield  radius
        radius += step

# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    global X_LIMIT, SOLUTIONS_FILE, CKPT_FILE

    parser = argparse.ArgumentParser()
    parser.add_argument("--n_start",  type=int, default=None)
    parser.add_argument("--n_end",    type=int, default=None)
    parser.add_argument("--x_limit",  type=int, default=X_LIMIT)
    parser.add_argument("--output",   default=SOLUTIONS_FILE)
    args = parser.parse_args()

    X_LIMIT        = args.x_limit
    SOLUTIONS_FILE = args.output
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print(f"[worker] shard={CONTAINER_ID}/{TOTAL_SHARDS}  x_limit={X_LIMIT:,}")
    print(f"[worker] output → {SOLUTIONS_FILE}")
    print(f"[worker] gmpy2={'yes' if USE_GMPY else 'no (slower)'}")

    # Resume
    resume_n = load_ckpt()
    done = 0; total_sols = 0
    t0 = time.time()

    with open(SOLUTIONS_FILE, "a", buffering=1) as sf:
        for n in n_iter(args.n_start, args.n_end, CONTAINER_ID, TOTAL_SHARDS):
            if not _running: break

            # Honour checkpoint resume in the expanding-outward mode
            if resume_n is not None:
                if n != resume_n:
                    done += 1
                    continue
                resume_n = None  # unlocked

            sols = search_n(n, X_LIMIT)
            done += 1

            if sols:
                for (nv, xv, yv) in sols:
                    line = f"n={nv} x={xv} y={yv}\n"
                    sf.write(line)
                    print(f"*** SOLUTION: {line}", end="", flush=True)
                    total_sols += 1

            if done % PROGRESS_INTERVAL == 0:
                save_ckpt(n + 1, done, total_sols)
                elapsed = time.time() - t0
                print(f"[progress] done={done:,}  last n={n}"
                      f"  rate={done/elapsed:.0f} n/s"
                      f"  solutions={total_sols}", flush=True)

    save_ckpt(0, done, total_sols)
    print(f"[worker] finished. done={done:,} solutions={total_sols}")

if __name__ == "__main__":
    main()
