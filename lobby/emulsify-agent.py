#!/usr/bin/env python3
"""EMULSIFY AGENT - the lab, running on the PC. Polls the lobby, develops, posts prints.

    python emulsify-agent.py              supervisor: runs the gate, then keeps N worker processes alive
    python emulsify-agent.py --gate       run the golden gate alone and exit 0 (HOLDS) / 1 (CHANGED)
    python emulsify-agent.py --worker K   one worker process (the supervisor starts these)
    ... --log FILE                        append everything to FILE (for a scheduled task with no console)

Reads agent.json next to it:  {"lobby": url, "agent_key": str, "lab": dir, "workers": 2, "poll_seconds": 1.5, "path_prepend": []}
The lab dir holds lab-worker.js, emulsify2.py, honey_sr.py, canon_profiles.py (the repo's own files) and golden.py.
Needs numpy, scipy, pillow and node on the PATH (golden.harness runs the worker's template through node so this
is the exact program the phone runs).

ONE LAB PER PROCESS. The harness patches the canon modules in place, so a second harness in the same process is
not the lab (golden.py, trap 1). Workers are therefore processes, not threads.

THE GATE: before anything is served the supervisor develops the golden chart (seed 99, 1100 px) and compares the
print, pixel for pixel, with golden-v21.png - the reference print from the machine that set golden v21
(4be892e9e27c70ec). Byte-identical is the ideal and is reported when it happens; across machines numpy, scipy and
libjpeg builds round differently in the last bit, so the gate accepts float noise - PSNR >= 40 dB and 99% of
pixels within 3 levels - and refuses anything structural (a different grain field, tone curve or geometry sits
far below that). The print it made is saved next to agent.json as gate-print.png for the record."""
import json, os, sys, time, hashlib, io, traceback, subprocess
from urllib import request, error, parse

if "--log" in sys.argv:
    LOGF = open(sys.argv[sys.argv.index("--log") + 1], "a", buffering=1, encoding="utf-8"); sys.stdout = sys.stderr = LOGF
HERE = os.path.dirname(os.path.abspath(__file__))
CFG = json.load(open(os.path.join(HERE, "agent.json")))
LOBBY = CFG["lobby"].rstrip("/"); KEY = CFG["agent_key"]; LAB = CFG.get("lab", HERE)
POLL = float(CFG.get("poll_seconds", 1.5)); WORKERS = int(CFG.get("workers", 2))
STANDIN = os.environ.get("EMULSIFY_AGENT_STANDIN") == "1"   # pipe tests on a box without the chemistry: NOT the lab
for d in CFG.get("path_prepend", []): os.environ["PATH"] = d + os.pathsep + os.environ.get("PATH", "")   # node, when a scheduled task's PATH is stale
sys.path.insert(0, LAB); os.chdir(LAB)

def log(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)

def call(method, path, body=None, q=None, timeout=60):
    url = LOBBY + path + ("?" + parse.urlencode(q) if q else "")
    req = request.Request(url, data=body, method=method, headers={"X-Agent-Key": KEY, "Content-Type": "application/octet-stream"})
    with request.urlopen(req, timeout=timeout) as r:
        ct = r.headers.get("Content-Type", ""); b = r.read()
        return json.loads(b) if ct.startswith("application/json") else b

def make_lab():
    if STANDIN:
        from PIL import Image
        def dev(neg, stock, seed, size):
            im = Image.open(io.BytesIO(neg)).convert("RGB").resize((size * 4 // 5, size)); b = io.BytesIO(); im.save(b, "JPEG", quality=85); time.sleep(1.0); return {"jpg": b.getvalue(), "secs": 1.0}
        return {"develop": dev}
    import golden
    return golden.harness(os.path.join(LAB, "lab-worker.js"))

GATE_PSNR_MIN, GATE_WITHIN3_MIN = 40.0, 0.99
def gate():
    if STANDIN: log("agent: STAND-IN MODE - resizing, not developing. Pipe test only. Never run this against the real lobby."); return True
    import golden, numpy as np
    from PIL import Image
    ns = make_lab(); neg = golden.chart()
    cs = hashlib.sha256(neg).hexdigest()[:12]
    if cs != golden.CHART_SHA: log("agent: the golden chart itself does not reproduce (%s) - PIL JPEG differs on this machine" % cs); return False
    t = time.time(); a = golden.pixels(ns["develop"](neg, "honey", 99, 1100)["jpg"]); secs = time.time() - t
    g = hashlib.sha256(a.tobytes()).hexdigest()[:16]
    try: Image.fromarray(a).save(os.path.join(HERE, "gate-print.png"))
    except Exception: pass
    if g == golden.GOLDEN_V17:
        log("agent: golden %s = v21 byte for byte -> HOLDS   (%.1fs for the chart at 1100)" % (g, secs)); return True
    ref_path = os.path.join(LAB, "golden-v21.png")
    if not os.path.exists(ref_path):
        log("agent: golden %s differs from v21 %s and there is no golden-v21.png to measure against -> CHANGED" % (g, golden.GOLDEN_V17)); return False
    ref = np.asarray(Image.open(ref_path).convert("RGB"))
    if ref.shape != a.shape: log("agent: print is %s, the reference is %s -> CHANGED" % (a.shape, ref.shape)); return False
    d = np.abs(a.astype(np.int16) - ref.astype(np.int16))
    mse = float((d.astype(np.float64) ** 2).mean()); psnr = 99.0 if mse == 0 else 10 * np.log10(255.0 ** 2 / mse)
    within1 = float((d <= 1).mean()); within3 = float((d <= 3).mean()); mx = int(d.max())
    ok = psnr >= GATE_PSNR_MIN and within3 >= GATE_WITHIN3_MIN
    log("agent: golden %s vs reference v21: PSNR %.1f dB, within 1 level %.3f%%, within 3 %.3f%%, max |d| %d -> %s   (%.1fs for the chart at 1100)"
        % (g, psnr, 100 * within1, 100 * within3, mx, "HOLDS (float noise of this machine's numpy/scipy/libjpeg)" if ok else "CHANGED: not float noise, something structural", secs))
    return ok

def develop(ns, job):
    p = job["params"]
    ns["_LEAK"] = float(p.get("leak", 0)); ns["_LENS_MM"] = int(float(p.get("mm", 33))); ns["_BUILD"] = int(float(p.get("build", 0)))
    ns["_ANA"] = float(p.get("ana", 1)); ns["_DC_ON"] = str(p.get("dc", "1")) in ("1", "true", "True")
    neg = call("GET", "/agent/jobs/%s/neg" % job["id"])
    r = ns["develop"](neg, p.get("profile", "honey"), int(float(p.get("seed", 1))), int(float(p.get("size", 1100))))
    return r["jpg"], float(r["secs"])

def worker(n):
    ns = make_lab()
    log("agent[%d]: lab loaded, polling %s" % (n, LOBBY))
    while True:
        try:
            job = call("POST", "/agent/claim", b"")
            if not job: time.sleep(POLL); continue
            t = time.time()
            try:
                jpg, secs = develop(ns, job)
                call("POST", "/agent/jobs/%s/print" % job["id"], jpg, {"secs": "%.2f" % secs}, timeout=120)
                log("agent[%d]: %s %s %dpx -> %d bytes in %.1fs (lab %.1fs)" % (n, job["id"][:8], job["params"].get("who", "?"), int(float(job["params"].get("size", 1100))), len(jpg), time.time() - t, secs))
            except Exception as e:
                traceback.print_exc()
                try: call("POST", "/agent/jobs/%s/fail" % job["id"], str(e).encode())
                except Exception: pass
        except error.URLError as e:
            log("agent[%d]: lobby unreachable (%s), retrying" % (n, e)); time.sleep(5)
        except Exception:
            traceback.print_exc(); time.sleep(5)

def supervise():
    log("agent: lobby %s  lab %s  workers %d" % (LOBBY, LAB, WORKERS))
    try: log("agent: lobby health", call("GET", "/health"))
    except Exception as e: log("agent: lobby not answering yet (%s) - will keep trying" % e)
    if not gate(): log("agent: this is not the lab. Refusing to serve."); sys.exit(1)
    procs = {}
    while True:
        for i in range(WORKERS):
            p = procs.get(i)
            if p is None or p.poll() is not None:
                if p is not None: log("agent: worker %d exited (%s), restarting" % (i, p.returncode))
                extra = ["--log", sys.argv[sys.argv.index("--log") + 1]] if "--log" in sys.argv else []
                procs[i] = subprocess.Popen([sys.executable, os.path.abspath(__file__), "--worker", str(i)] + extra, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)   # the children log to the file themselves
        time.sleep(3)

if __name__ == "__main__":
    if "--gate" in sys.argv: sys.exit(0 if gate() else 1)
    if "--worker" in sys.argv: worker(int(sys.argv[sys.argv.index("--worker") + 1]))
    else: supervise()
