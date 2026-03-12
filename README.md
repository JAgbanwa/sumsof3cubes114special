# sumsof3cubes114special

Exhaustive integer-point search for the elliptic curve family:

    y² = x³ + (36n+27)²·x² + 243·(4n+3)³·x + (4n+3)·(11664n³+26244n²+19683n+4916)

parameterised by all integers n.

## Algebraic structure (t = 4n+3)

    A(n) = 81·t²
    B(n) = 243·t³
    C(n) = t·(11664n³+26244n²+19683n+4916)

## Solutions found (all independently verified)

| n    | x       | y          | verified |
|------|---------|------------|----------|
|  -1  |      18 | ±167       | ✓        |
| -64  |  144840 | ±333523318 | ✓        |
|  94  |    -562 | ±17722     | ✓        |
| -110 |     646 | ±40812     | ✓        |

Search is ongoing — more solutions will appear in `output/solutions.txt`.

## Quick start

    make              # build fast C searcher
    make test         # test n∈[0,500], |x|≤100000
    python3 worker.py # endless Python search (auto-resumes)

## Charity Engine

    docker build -t sumsof3cubes114special .
    docker run --rm -e N_START=0 -e N_END=1000000 -e X_LIMIT=10000000 \
               -v $(pwd)/output:/output sumsof3cubes114special