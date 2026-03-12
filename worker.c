/*
 * worker.c — Fast C searcher for integer points on
 *
 *   y² = x³ + 81·t²·x² + 243·t³·x + t·(11664n³+26244n²+19683n+4916)
 *
 * where t = 4n+3, for all integers n.
 *
 * Techniques:
 *   • __int128 exact arithmetic (no BigNum library needed for |n|,|x| < 10^9)
 *   • QR sieve: test f(x) mod {3,5,7,11,13,17,19,23,29,31} before sqrt
 *   • hardware isqrt with Newton correction
 *   • Newton-bracket for negative-x lower bound
 *   • BOINC checkpoint every 60 s (compile with -DBOINC)
 *
 * Build standalone:
 *   gcc -O3 -march=native -std=c99 -o worker worker.c -lm
 *
 * Build for BOINC/CE:
 *   gcc -O3 -march=native -std=c99 -DBOINC -o worker worker.c \
 *       -I/usr/include/boinc -L/usr/lib -lboinc_api -lboinc -lpthread -lm
 *
 * WU file format (wu.txt):
 *   n_start <int64>
 *   n_end   <int64>
 *   x_limit <int64>
 *
 * Output (result.txt): one solution per line:  n x y
 */

#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <inttypes.h>
#include <string.h>
#include <math.h>
#include <time.h>

#ifdef BOINC
#  include "boinc_api.h"
#endif

typedef int64_t          i64;
typedef uint64_t         u64;
typedef unsigned int     u32;
typedef __int128         i128;
typedef unsigned __int128 u128;

/* ── perfect-square test ──────────────────────────────────────────────── */
static inline u64 isqrt128(u128 v) {
    if (!v) return 0;
    u64 s = (u64)sqrtl((long double)v);
    /* two correction steps */
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
static u32 QR[NS]; /* bit k set ↔ k is QR mod SP[i] */

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
    /* exact binary search */
    i64 lo=lb-10, hi=lb+20;
    while (feval(hi,n)<0) hi+=(hi<0?-hi/2+1:1);
    while (feval(lo,n)>=0) lo-=(lo>0?lo/2+1:1);
    while (lo<hi-1) { i64 m=lo/2+hi/2; if(feval(m,n)>=0) hi=m; else lo=m; }
    return hi;
}

/* ── search one n ─────────────────────────────────────────────────────── */
static int search_n(i64 n, i64 xlim, FILE *out) {
    int found=0; i64 y;
    /* positive x */
    for (i64 x=0; x<=xlim; x++) {
        if (!sieve_ok(x,n)) continue;
        i128 v=feval(x,n);
        if (is_sq(v,&y)) {
            fprintf(out,"%" PRId64 " %" PRId64 " %" PRId64 "\n",n,x,y);
            if (y>0) fprintf(out,"%" PRId64 " %" PRId64 " %" PRId64 "\n",n,x,-y);
            found++;
        }
    }
    /* negative x */
    i64 lb=lower_bound(n);
    for (i64 x=(lb>-xlim?lb:-xlim); x<0; x++) {
        if (!sieve_ok(x,n)) continue;
        i128 v=feval(x,n);
        if (v<0) continue;
        if (is_sq(v,&y)) {
            fprintf(out,"%" PRId64 " %" PRId64 " %" PRId64 "\n",n,x,y);
            if (y>0) fprintf(out,"%" PRId64 " %" PRId64 " %" PRId64 "\n",n,x,-y);
            found++;
        }
    }
    return found;
}

/* ── main ─────────────────────────────────────────────────────────────── */
int main(int argc, char **argv) {
#ifdef BOINC
    boinc_init();
#endif
    init_sieve();

    char wu[512]="wu.txt", out_p[512]="result.txt", ckpt[512]="checkpoint.txt";
#ifdef BOINC
    boinc_resolve_filename_s("wu.txt",         wu,    sizeof wu);
    boinc_resolve_filename_s("result.txt",     out_p, sizeof out_p);
    boinc_resolve_filename_s("checkpoint.txt", ckpt,  sizeof ckpt);
#else
    if (argc>=2) strncpy(wu,   argv[1],511);
    if (argc>=3) strncpy(out_p,argv[2],511);
#endif

    /* read work unit */
    FILE *wf=fopen(wu,"r");
    if (!wf){fprintf(stderr,"Cannot open %s\n",wu);return 1;}
    i64 n0,n1,xlim;
    if (fscanf(wf,"n_start %" SCNd64 " n_end %" SCNd64 " x_limit %" SCNd64,
               &n0,&n1,&xlim)!=3){
        fprintf(stderr,"Bad WU\n");fclose(wf);return 1;
    }
    fclose(wf);

    /* checkpoint resume */
    i64 nres=n0;
    { FILE *cf=fopen(ckpt,"r");
      if(cf){fscanf(cf,"%" SCNd64,&nres);fclose(cf);
             fprintf(stderr,"[resume] n=%" PRId64 "\n",nres);} }

    FILE *out=fopen(out_p,"a");
    if (!out){fprintf(stderr,"Cannot open %s\n",out_p);return 1;}

    i64 total=0, done=0;
    clock_t t0=clock();
    for (i64 n=nres; n<=n1; n++) {
        total+=search_n(n,xlim,out);
        done++;
        fflush(out);
        /* checkpoint */
        { FILE *cf=fopen(ckpt,"w");
          if(cf){fprintf(cf,"%" PRId64 "\n",n+1);fclose(cf);} }
#ifdef BOINC
        boinc_fraction_done((double)(n-n0)/(double)(n1-n0+1));
        boinc_checkpoint_completed();
#else
        if (done%5000==0) {
            double el=(double)(clock()-t0)/CLOCKS_PER_SEC;
            fprintf(stderr,"[progress] n=%" PRId64 "  done=%"PRId64
                    "  sols=%"PRId64"  %.0f n/s\n",
                    n,done,total,(double)done/el);
        }
#endif
    }
    fclose(out);
    fprintf(stderr,"[done] n=%"PRId64"..%"PRId64
            " xlim=%"PRId64" sols=%"PRId64"\n",n0,n1,xlim,total);
#ifdef BOINC
    boinc_finish(0);
#endif
    return 0;
}
