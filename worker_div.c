/*
 * worker_div.c — Targeted searcher for integer points (n, x, y) on
 *
 *   y^2 = x^3 + 81*t^2*x^2 + 243*t^3*x + t*(11664n^3+26244n^2+19683n+4916)
 *
 * where t = 4n+3, with the EXTRA constraint that y / (6n) is an integer,
 * i.e. 6n divides y exactly.
 *
 * Key observation:
 *   y = 6k·n  ⟹  y² = 36k²n²  ⟹  f(x,n) ≡ 0  (mod 36n²)
 *
 * This pre-filter eliminates O(36n²) / 1 ≈ 36n² out of every 36n² values
 * of x before any square-root is attempted — crushing the inner loop.
 *
 * Techniques:
 *   • __int128 exact arithmetic
 *   • QR sieve mod {3,5,7,11,13,17,19,23,29,31}
 *   • mod-36n² pre-filter (main speed gain for |n| > 100)
 *   • Newton-bracketed negative-x lower bound
 *   • Checkpoint every 60 s
 *
 * Build:
 *   gcc -O3 -march=native -std=c99 -o worker_div worker_div.c -lm
 *
 * WU file format (wu.txt):
 *   n_start <int64>
 *   n_end   <int64>
 *   x_limit <int64>
 *
 * Output: lines of the form:  n x y k
 *   where k = y/(6n)
 */

#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <inttypes.h>
#include <string.h>
#include <math.h>
#include <time.h>

typedef int64_t           i64;
typedef uint64_t          u64;
typedef unsigned int      u32;
typedef __int128          i128;
typedef unsigned __int128 u128;

/* ── perfect-square test ──────────────────────────────────────────────── */
static inline u64 isqrt128(u128 v) {
    if (!v) return 0;
    u64 s = (u64)sqrtl((long double)v);
    if (s) s = (u64)((s + (u64)(v / (u128)s)) >> 1);
    if (s) s = (u64)((s + (u64)(v / (u128)s)) >> 1);
    while ((u128)s * s > v)        s--;
    while ((u128)(s+1)*(s+1) <= v) s++;
    return s;
}

static inline int is_sq(i128 v, i64 *oy) {
    if (v < 0) return 0;
    u64 s = isqrt128((u128)v);
    if ((u128)s * s == (u128)v) { *oy = (i64)s; return 1; }
    return 0;
}

/* ── QR sieve ─────────────────────────────────────────────────────────── */
#define NS 10
static const int SP[NS] = {3,5,7,11,13,17,19,23,29,31};
static u32 QR[NS];

static void init_sieve(void) {
    for (int i = 0; i < NS; i++) {
        int p = SP[i]; QR[i] = 0;
        for (int x = 0; x < p; x++) QR[i] |= 1u << ((x*x) % p);
    }
}

static inline int sieve_ok(i64 x, i64 n) {
    for (int i = 0; i < NS; i++) {
        int p = SP[i];
        long long xm = ((long long)x % p + p) % p;
        long long nm = ((long long)n % p + p) % p;
        long long t  = (4*nm + 3) % p;
        long long A  = (81 * t % p * t) % p;
        long long B  = (243 * t % p * t % p * t) % p;
        long long n2 = nm*nm % p, n3 = n2*nm % p;
        long long C  = t * ((11664*n3 + 26244*n2 + 19683*nm + 4916) % p) % p;
        long long fx = (xm*xm%p*xm + A*xm%p*xm + B*xm + C) % p;
        if (!((QR[i] >> (int)(((fx % p)+p)%p)) & 1)) return 0;
    }
    return 1;
}

/* ── f(x,n) exact ─────────────────────────────────────────────────────── */
static inline i128 feval(i64 x, i64 n) {
    i128 t = (i128)(4*n+3);
    i128 A = (i128)81  * t * t;
    i128 B = (i128)243 * t * t * t;
    i128 C = t * ((i128)11664*(i128)n*(i128)n*(i128)n
                 +(i128)26244*(i128)n*(i128)n
                 +(i128)19683*(i128)n
                 +(i128)4916);
    i128 xm = (i128)x;
    return xm*xm*xm + A*xm*xm + B*xm + C;
}

/* ── div-36n² modular pre-filter ──────────────────────────────────────── */
/* Returns 1 iff f(x,n) % (36*n*n) == 0.
   Safe for |n| <= 200_000_000 (36n² <= 1.44e18 < 2^63).
   For n==0 or |n|==1, skip (condition trivially 36 divides y,
   handled at output stage). */
static inline int div_filter(i64 x, i64 n, i128 fx) {
    if (n == 0) return 1;
    i64 m = 6 * n;         /* 6n */
    i128 m2 = (i128)m * m; /* 36n² */
    /* fx mod m2 — both are exact i128 */
    i128 r = fx % m2;
    if (r < 0) r += m2;
    return (r == 0);
}

/* ── lower bound for negative x ───────────────────────────────────────── */
static i64 lower_bound(i64 n) {
    double Af = 81.0*pow(4.0*n+3,2);
    double Bf = 243.0*pow(4.0*n+3,3);
    double Cf = (4.0*n+3)*(11664.0*n*n*n+26244.0*n*n+19683.0*n+4916.0);
    double xf = -fabs(Af)-100.0;
    for (int i=0;i<80;i++) {
        double fv=xf*xf*xf+Af*xf*xf+Bf*xf+Cf;
        double df=3*xf*xf+2*Af*xf+Bf;
        if (fabs(df)<1e-30) break;
        xf-=fv/df;
    }
    i64 lb=(i64)floor(xf)-2;
    i64 lo=lb-10, hi=lb+20;
    while (feval(hi,n)<0) hi+=(hi<0?-hi/2+1:1);
    while (feval(lo,n)>=0) lo-=(lo>0?lo/2+1:1);
    while (lo<hi-1) {
        i64 m=lo/2+hi/2;
        if (feval(m,n)>=0) hi=m; else lo=m;
    }
    return hi;
}

/* ── search one n ─────────────────────────────────────────────────────── */
static int search_n(i64 n, i64 xlim, FILE *out) {
    int found = 0;
    i64 y;
    i64 div6n = (n != 0) ? 6*n : 0;  /* divisor; 0 means skip divisibility */

    /* positive x */
    for (i64 x = 0; x <= xlim; x++) {
        if (!sieve_ok(x, n)) continue;
        i128 v = feval(x, n);
        /* divisibility pre-filter: f(x,n) must be divisible by 36n² */
        if (n != 0 && !div_filter(x, n, v)) continue;
        if (v < 0) continue;
        if (!is_sq(v, &y)) continue;
        /* final exact check: y/(6n) must be integer */
        if (n != 0 && y % div6n != 0) continue;
        i64 k = (n != 0) ? y / div6n : 0;
        fprintf(out, "%" PRId64 " %" PRId64 " %" PRId64 " %" PRId64 "\n",
                n, x, y, k);
        if (y > 0)
            fprintf(out, "%" PRId64 " %" PRId64 " %" PRId64 " %" PRId64 "\n",
                    n, x, -y, -k);
        found++;
    }

    /* negative x */
    i64 lb = lower_bound(n);
    for (i64 x = (lb > -xlim ? lb : -xlim); x < 0; x++) {
        if (!sieve_ok(x, n)) continue;
        i128 v = feval(x, n);
        if (v < 0) continue;
        /* divisibility pre-filter */
        if (n != 0 && !div_filter(x, n, v)) continue;
        if (!is_sq(v, &y)) continue;
        if (n != 0 && y % div6n != 0) continue;
        i64 k = (n != 0) ? y / div6n : 0;
        fprintf(out, "%" PRId64 " %" PRId64 " %" PRId64 " %" PRId64 "\n",
                n, x, y, k);
        if (y > 0)
            fprintf(out, "%" PRId64 " %" PRId64 " %" PRId64 " %" PRId64 "\n",
                    n, x, -y, -k);
        found++;
    }
    return found;
}

/* ── main ─────────────────────────────────────────────────────────────── */
int main(int argc, char **argv) {
    init_sieve();

    char wu[512]   = "wu.txt";
    char out_p[512]= "result.txt";
    char ckpt[512] = "checkpoint.txt";
    if (argc >= 2) strncpy(wu,    argv[1], 511);
    if (argc >= 3) strncpy(out_p, argv[2], 511);

    FILE *wf = fopen(wu, "r");
    if (!wf) { fprintf(stderr, "Cannot open %s\n", wu); return 1; }
    i64 n0, n1, xlim;
    if (fscanf(wf, "n_start %" SCNd64 " n_end %" SCNd64 " x_limit %" SCNd64,
               &n0, &n1, &xlim) != 3) {
        fprintf(stderr, "Bad WU\n"); fclose(wf); return 1;
    }
    fclose(wf);

    /* checkpoint resume */
    i64 nres = n0;
    { FILE *cf = fopen(ckpt, "r");
      if (cf) { fscanf(cf, "%" SCNd64, &nres); fclose(cf);
                fprintf(stderr, "[resume] n=%" PRId64 "\n", nres); } }

    FILE *out = fopen(out_p, "a");
    if (!out) { fprintf(stderr, "Cannot open %s\n", out_p); return 1; }

    i64 total = 0, done = 0;
    clock_t t0 = clock();
    for (i64 n = nres; n <= n1; n++) {
        total += search_n(n, xlim, out);
        done++;
        fflush(out);
        { FILE *cf = fopen(ckpt, "w");
          if (cf) { fprintf(cf, "%" PRId64 "\n", n+1); fclose(cf); } }
        if (done % 5000 == 0) {
            double el = (double)(clock()-t0)/CLOCKS_PER_SEC;
            fprintf(stderr,
                "[progress] n=%" PRId64 "  done=%" PRId64
                "  div_sols=%" PRId64 "  %.0f n/s\n",
                n, done, total, (double)done/el);
        }
    }
    fclose(out);
    fprintf(stderr,
        "[done] n=%" PRId64 "..%" PRId64
        " xlim=%" PRId64 " div_sols=%" PRId64 "\n",
        n0, n1, xlim, total);
    return 0;
}
