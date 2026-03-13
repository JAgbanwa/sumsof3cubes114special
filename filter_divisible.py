#!/usr/bin/env python3
"""
filter_divisible.py
===================
Scans all slab result files and the master solutions.txt for solutions (n,x,y)
where y / (6*n) is an integer (i.e. 6n divides y exactly).

Writes matching solutions to:  solutions_div6n.txt   (tracked by git)

Also verifies the equation holds exactly.
"""
from pathlib import Path

REPO = Path(__file__).parent


def feval(n, x):
    t = 4 * n + 3
    A = 81 * t * t
    B = 243 * t * t * t
    C = t * (11664 * n**3 + 26244 * n**2 + 19683 * n + 4916)
    return x**3 + A * x**2 + B * x + C


def collect_all():
    """Return set of (n, x, |y|) from every result file."""
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
                    key = (n, x, abs(y))
                    seen[key] = (n, x, abs(y))
                except ValueError:
                    pass
    return list(seen.values())


def main():
    all_sols = collect_all()
    print(f"Total integer solutions loaded: {len(all_sols)}")

    print("\nChecking y % (6n) == 0 ...")
    matching = []
    for n, x, y in sorted(all_sols, key=lambda t: (abs(t[0]), t[0])):
        if n == 0:
            continue
        if y % (6 * n) == 0:
            k = y // (6 * n)
            # verify equation
            lhs = y * y
            rhs = feval(n, x)
            ok = (lhs == rhs)
            matching.append((n, x, y, k, ok))
            print(f"  *** MATCH  n={n}  x={x}  y=±{y}  y/(6n)={k}  eq_ok={ok}")
        else:
            rem = y % (6 * n)
            # uncomment to see all misses:
            # print(f"  miss  n={n}  x={x}  y={y}  rem={rem}")

    print(f"\nAll known solutions vs y/(6n) integer:")
    for n, x, y in sorted(all_sols, key=lambda t: (abs(t[0]), t[0])):
        if n == 0:
            continue
        ratio = y / (6 * n)
        print(f"  n={n:>12}  x={x:>15}  y=±{y:<22}  y/(6n) = {ratio:.6f}")

    # Write results
    out = REPO / "solutions_div6n.txt"
    if matching:
        lines = ["# Solutions where y/(6n) is an integer"]
        lines += [f"n={n}  x={x}  y=±{y}  k=y/(6n)={k}  verified={ok}"
                  for n, x, y, k, ok in matching]
        out.write_text("\n".join(lines) + "\n")
        print(f"\nWritten {len(matching)} matching solutions to solutions_div6n.txt")
    else:
        out.write_text("# No solutions with y/(6n) integer found yet.\n")
        print("\nNo solutions satisfy y/(6n) integer among currently known solutions.")
        print("Workers are still running — more solutions will be found.")


if __name__ == "__main__":
    main()
