#!/usr/bin/env python3
"""EMULSIFY golden ritual — the seed-99 proof.

Rebuilds the canonical synthetic chart, develops it at fixed seed 99 through
the worker's embedded harness, and prints the SHA-256 of the resulting pixel
buffer. A change that should not alter rendering must reproduce the previous
golden exactly.

Recovered 2026-08-24 from session history after the generator was found to
exist nowhere in the repo or the boot document. Identity is confirmed by the
chart's own hash: sha256(jpeg bytes)[:12] must read 63d93286cc18. The shadow
field is a sin texture, NOT the linear gradient used by an earlier variant,
and the chart is JPEG q95, NOT PNG - all four combinations were tested and
only one reproduces the recorded hash.

    python3 golden.py [path/to/lab-worker.js]

ONE WORKER PER PROCESS. Two instances in one process share the canon modules
and the second wraps the first's already-patched functions (see boot doc
trap 1). Never import this alongside another harness load.
"""
import sys, io, os, hashlib, time
import numpy as np
from PIL import Image

CHART_SHA  = "63d93286cc18"
GOLDEN_V11 = "5ea19a4ea48e310f"
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

def chart():
    W, H = 880, 1100
    img = np.zeros((H, W, 3), np.float64)
    yy, xx = np.mgrid[0:H, 0:W]
    sky_h = int(H*0.42); t = (yy[:sky_h]/sky_h)[..., None]
    img[:sky_h] = (1-t)*np.array([0.36,0.55,0.86]) + t*np.array([0.92,0.88,0.78])
    cy, cx, r0 = int(H*0.10), int(W*0.72), 46
    d = np.sqrt((yy-cy)**2 + (xx-cx)**2); img[d < r0] = [1.0, 0.97, 0.90]
    ry0, ry1 = sky_h, int(H*0.58)
    steps = np.floor(xx[0]/(W/16))/15.0
    img[ry0:ry1] = np.repeat(steps[None, :, None], 3, axis=2)
    patches = [(222,178,152),(200,60,50),(70,120,55),(60,170,60),(50,80,180),(230,200,80)]
    py0, py1 = ry1, int(H*0.74); pw = W//len(patches)
    for i, c in enumerate(patches):
        img[py0:py1, i*pw:(i+1)*pw] = np.array(c)/255.0
    tex = 0.5 + 0.5*np.sin(xx/17.0)*np.sin(yy/23.0)
    img[py1:] = (0.05 + 0.10*tex[py1:])[..., None]*np.array([1.0, 0.95, 0.88])
    buf = io.BytesIO()
    Image.fromarray((np.clip(img,0,1)*255).astype(np.uint8)).save(buf, "JPEG", quality=95)
    return buf.getvalue()

def harness(path):
    src = open(path, encoding="utf-8").read()
    py = src.split("runPythonAsync(`", 1)[1].rsplit("`);", 1)[0]
    ns = {}; exec(compile(py, path, "exec"), ns)
    ns["_post_stage"] = lambda *a: None      # suppress the mid-develop watcher
    ns["_BUILD"] = 0; ns["_EV_BIAS"] = 0.0
    ns["_ANA"] = 1.0; ns["_LENS_MM"] = 33     # spherical, no glass
    for k, v in (("_OPTIC", ""), ("_TINT", ""), ("_TINT_S", 0.0)):
        if k in ns: ns[k] = v
    return ns

def pixels(jpg):
    return np.asarray(Image.open(io.BytesIO(jpg)).convert("RGB"))

def main():
    wf = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "lab-worker.js")
    neg = chart()
    cs = hashlib.sha256(neg).hexdigest()[:12]
    print(f"chart   {len(neg)} bytes  sha {cs}  " +
          ("OK" if cs == CHART_SHA else f"MISMATCH (expected {CHART_SHA}) - STOP"))
    if cs != CHART_SHA:
        sys.exit(2)
    print(f"worker  {os.path.basename(wf)}  {open(wf,encoding='utf-8').readline().strip()[:60]}")
    ns = harness(wf)
    t = time.time(); a = pixels(ns["develop"](neg, "honey", 99, 1100)["jpg"]); t1 = time.time()-t
    t = time.time(); b = pixels(ns["develop"](neg, "honey", 99, 1100)["jpg"]); t2 = time.time()-t
    g = hashlib.sha256(a.tobytes()).hexdigest()[:16]
    print(f"\ngolden  {g}   ({t1:.1f}s, {t2:.1f}s)   shape {a.shape}")
    print(f"        v11 = {GOLDEN_V11}  ->  {'HOLDS' if g == GOLDEN_V11 else 'CHANGED'}")
    print(f"determinism  same input twice byte-identical: {np.array_equal(a, b)}")
    return 0 if g == GOLDEN_V11 else 1

if __name__ == "__main__":
    sys.exit(main())
