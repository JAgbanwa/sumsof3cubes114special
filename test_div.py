#!/usr/bin/env python3
"""Quick test of worker_div on n=[-200,200] x_limit=2M"""
import subprocess, time, pathlib

d = pathlib.Path('/tmp/divtest2')
d.mkdir(exist_ok=True)
for f in ['checkpoint.txt', 'result.txt']:
    (d / f).unlink(missing_ok=True)
(d / 'wu.txt').write_text('n_start -200\nn_end   200\nx_limit 2000000\n')

WORKER = '/Users/jamalmac/Desktop/sumsof3cubes/sumsof3cubes114special/worker_div'
t0 = time.time()
r = subprocess.run([WORKER, str(d / 'wu.txt'), str(d / 'result.txt')],
                   capture_output=True, text=True, cwd=str(d))
elapsed = time.time() - t0

print(f"elapsed: {elapsed:.2f}s  returncode={r.returncode}")
print("STDERR:", r.stderr[-400:])
result = (d / 'result.txt').read_text().strip()
print("RESULTS:", result if result else "(none found in n=[-200,200])")
