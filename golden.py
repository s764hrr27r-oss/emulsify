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
GOLDEN_V11 = "ea38f54333e5b038"   # v15: position-addressed grain, w3.18
GOLDEN_V12 = "f835a9981ce01f83"   # v16 THE STREAMED DEVELOP (w3.20): the honey profile, meter,
                                  # fixer, dodge, pre-flash, sandwich, coat merge and encode all run
                                  # in 64px-overlapped bands; the only whole-frame arrays are single-
                                  # channel plus one float32 print. 2200px peaks at 321 MB (was 2400).
                                  # Matches the whole-frame path to 0.1/255 per channel; the tooth is
                                  # position-addressed like the grain, so its arrangement differs.
                                  # Previous: v15 POSITION-ADDRESSED GRAIN (w3.18): the crystal draw is a
                                  # function of absolute position, not call order, so a strip develops
                                  # identically to a whole frame. The precondition for banding, and the
                                  # route past 1100px. Same statistics (grain 11.09 vs 11.10), different
                                  # arrangement. Approved by the owner from crops. Previous:
                                  # v14 THE SEAM (w3.16): strata-light band offsets interpolated, so a
                                  # smooth gradient no longer picks up a 10 deg hue cliff at a band edge.
                                  # A BUG FIX, not a new look; the stock is unchanged. v13 was c4e7911e38e3f69f.
                                  # v13 THE STOCK TINT (w3.15): magenta baseline, _STOCK_M = 0.070,
                                  # chosen by the owner from grids on nine real prints. Previous stock above.
                                  # (0.050 was c4-less 88eefc06947458d3, never shipped.)
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
    # The template is a JavaScript template literal. JavaScript interprets the
    # backslash escapes BEFORE Python sees the source, so the harness must run
    # it through JavaScript too, or it tests a different program than the phone
    # runs (b151-b157: a b"\\x00" became a real NUL byte and the lab never booted).
    import subprocess, json, tempfile
    js = ("const fs=require('fs');const s=fs.readFileSync(process.argv[1],'utf8');"
          "const m=s.split('runPythonAsync(`')[1];const t=m.slice(0,m.lastIndexOf('`);'));"
          "process.stdout.write(eval('`'+t+'`'));")
    py = subprocess.run(["node", "-e", js, path], capture_output=True, text=True, check=True).stdout
    if "\x00" in py: raise SystemExit("HARNESS: the template as JavaScript delivers it contains NUL bytes; Pyodide will refuse it")
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
    print(f"        v16 = {GOLDEN_V12}  ->  {'HOLDS' if g == GOLDEN_V12 else 'CHANGED'}   (v15 was {GOLDEN_V11})")
    print(f"determinism  same input twice byte-identical: {np.array_equal(a, b)}")
    return 0 if g == GOLDEN_V12 else 1

if __name__ == "__main__":
    sys.exit(main())
