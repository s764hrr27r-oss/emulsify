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
import json, os, sys, time, hashlib, io, traceback, subprocess, tempfile, threading, multiprocessing
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

# ---------------------------------------------------------------- THE ROLL (b242): a clip becomes film
# The phone records a clip and sends it with the finder's window as fractions of the frame. Here ffmpeg cuts
# that window out of every frame at the film's frame rate and hands each one to the lab as a JPEG negative.
# Frames develop in parallel, one lab per process (trap 1), then ffmpeg joins the prints into an H.264 MP4.
#
# THE ROLL RULE: one seed for the whole roll decides the stock's character - the mineral beds (speed, contrast)
# and the strata colour bias - so the look does not flicker; the grain field and the emulsion fields are re-rolled
# for every frame (grain seed + frame * 1000003, field seed + frame * 7777), so the grain is alive the way film
# grain is.
#
# THE SHOT (w3.25, kit 4): a still times itself - meter, drift balancer, exposure, fixer - from its own pixels.
# Frame by frame that is flicker: the exposure and colour follow whatever walked into the frame. Film times a
# shot. So every frame is probed first (_shot_probe: the same measurements, no developing), the measurements are
# smoothed along the roll - a slow meter, ROLL_SMOOTH_S seconds wide - and each frame develops with the smoothed
# timing (_SHOT). The fixer's colour trim is read off frame 0 and held for the roll. timing=frame in the job turns
# this off (every frame for itself, as b242 did); timing=lock holds the roll's median timing throughout.
#
# THE FIELDS (kit 4): the emulsion fields - three +-1%, frame-wide undulations with a radial pull - re-rolled every
# frame were the flicker you could see in a sky: a 24 px patch wobbled 0.8 levels frame to frame; held, it wobbles
# 0.14 (grain alone). So under shot timing the fields are HELD for the roll, the way a printer's gate and a shot's
# emulsion batch are one thing for the length of a shot. (A cos/sin drift between two draws was tried and measured
# first: the draws share a radial pull, so the blend swelled 41% mid-turn and the frame breathed 25 levels - worse
# than the flicker it replaced. Measured, rejected.) Grain still re-rolls every frame.
#
# Nothing of a roll touches this machine's disk except the encoder's scratch file (H.264 in MP4 needs a seekable
# output for the moov atom), which is overwritten with zeros and removed the moment its bytes are in memory. The
# clip itself is decoded from memory through a pipe; if the container cannot be read from a pipe (an MP4 with its
# index at the end), it is spooled to a scratch file that is wiped the same way.
ROLL = CFG.get("roll", {})
ROLL_PROCS = int(ROLL.get("procs", max(1, min(8, (os.cpu_count() or 2) - 2))))
ROLL_MAX_FRAMES = int(ROLL.get("max_frames", 480))
ROLL_CRF = int(ROLL.get("crf", 18))
ROLL_SMOOTH_S = float(ROLL.get("smooth_seconds", 0.6))
ROLL_FIELDS = str(ROLL.get("fields", "hold"))          # hold (the roll's) or roll (a fresh draw every frame, b242)
_NS = None
def _roll_init(lab):
    global _NS
    sys.path.insert(0, lab); os.chdir(lab)
    import golden
    _NS = golden.harness(os.path.join(lab, "lab-worker.js"))
    _NS["_grain_z0"] = _NS["_grain_z"]; _NS["_make_fields0"] = _NS["_make_fields"]
def _roll_probe(task):
    i, jpg, size, mm, ana = task
    ns = _NS; ns["_LENS_MM"] = mm; ns["_ANA"] = ana; ns["_BAND_MIN_PX"] = 0
    return i, ns["_shot_probe"](jpg, size)
def _roll_frame(task):
    i, jpg, seed, size, mm, ana, dc, build, shot, hold_fields = task
    ns = _NS
    ns["_LEAK"] = 0.0; ns["_LENS_MM"] = mm; ns["_BUILD"] = build; ns["_ANA"] = ana; ns["_DC_ON"] = dc
    ns["_BAND_MIN_PX"] = 0                       # film always develops on the streamed path, the one the probe measures
    og, of = ns["_grain_z0"], ns["_make_fields0"]
    ns["_grain_z"] = lambda h, w, y0, s, tag: og(h, w, y0, s + i * 1000003, tag)
    ns["_make_fields"] = of if hold_fields else (lambda h, w, s: of(h, w, s + i * 7777))   # held for the roll, or b242's fresh draw per frame
    ns["_SHOT"][0] = shot
    try: r = ns["develop"](jpg, "honey", seed, size)
    finally: measured = dict(ns["_SHOT_MEASURED"]); ns["_SHOT"][0] = None
    return i, r["jpg"], float(r["secs"]), measured
def _smooth(series, sigma):
    """gaussian along the roll, edges reflected; sigma in frames (0 -> the series' median, held)"""
    import numpy as np
    a = np.asarray(series, np.float64)
    if a.ndim == 1: a = a[:, None]
    if sigma <= 0: return np.repeat(np.median(a, 0, keepdims=True), len(a), 0)
    r = int(3 * sigma) + 1; k = np.exp(-0.5 * (np.arange(-r, r + 1) / sigma) ** 2); k /= k.sum()
    pad = np.pad(a, ((r, r), (0, 0)), mode="reflect")
    return np.stack([np.convolve(pad[:, c], k, mode="valid") for c in range(a.shape[1])], 1)
def time_the_shot(probes, fps, timing):
    """per-frame shot dicts from the probes: smoothed (shot), held at the median (lock), or none (frame)"""
    n = len(probes)
    if timing == "frame": return [None] * n
    sigma = 0 if timing == "lock" else ROLL_SMOOTH_S * fps
    taus = _smooth([p["taus"] for p in probes], sigma); gains = _smooth([p["gains"] for p in probes], sigma)
    warm = _smooth([p["warmbias"] for p in probes], sigma)[:, 0]; ev = _smooth([p["ev"] for p in probes], sigma)[:, 0]
    return [{"taus": [float(x) for x in taus[i]], "gains": [float(x) for x in gains[i]], "warmbias": float(warm[i]), "ev": float(ev[i])} for i in range(n)]
_POOL = None
def roll_pool():
    global _POOL
    if _POOL is None:
        log("agent: warming %d lab processes for film" % ROLL_PROCS)
        _POOL = multiprocessing.get_context("spawn").Pool(ROLL_PROCS, initializer=_roll_init, initargs=(LAB,))
    return _POOL
def ffmpeg_exe():
    try:
        import imageio_ffmpeg; return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception as e:
        raise RuntimeError("no ffmpeg on the lab PC (pip install imageio-ffmpeg): %s" % e)
def wipe(path):
    try:
        n = os.path.getsize(path)
        with open(path, "r+b") as f: f.write(b"\0" * n); f.flush(); os.fsync(f.fileno())
    except Exception: pass
    try: os.remove(path)
    except Exception: pass
def split_mjpeg(buf):
    out, i = [], 0
    while True:
        a = buf.find(b"\xff\xd8", i)
        if a < 0: break
        b = buf.find(b"\xff\xd9", a + 2)
        if b < 0: break
        out.append(bytes(buf[a:b + 2])); i = b + 2
    return out
def cut_frames(ff, clip, ctype, fps, crop, size):
    """the finder's window out of every frame, at fps, long edge = size, as JPEG negatives - all in memory"""
    cx, cy, cw, ch = crop
    vf = "fps=%g,crop=w=iw*%.6f:h=ih*%.6f:x=iw*%.6f:y=ih*%.6f,scale=w='if(gte(iw,ih),%d,-2)':h='if(gte(iw,ih),-2,%d)'" % (fps, cw, ch, cx, cy, size, size)
    base = [ff, "-hide_banner", "-loglevel", "error", "-nostdin"]
    def run(src_args, feed):
        p = subprocess.Popen(base + src_args + ["-vf", vf, "-f", "image2pipe", "-vcodec", "mjpeg", "-q:v", "2", "pipe:1"], stdin=subprocess.PIPE if feed else subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if feed:
            def pump():
                try: p.stdin.write(clip); p.stdin.close()
                except Exception: pass
            threading.Thread(target=pump, daemon=True).start()
        out, err = p.communicate(timeout=600)
        return p.returncode, out, err.decode("utf-8", "replace")
    rc, out, err = run(["-i", "pipe:0"], True)
    frames = split_mjpeg(out) if rc == 0 else []
    how = "from memory"
    if not frames:                                   # an MP4 whose index sits at the end cannot be read from a pipe
        d = tempfile.mkdtemp(prefix="emulsify-"); fn = os.path.join(d, "clip.bin")
        try:
            with open(fn, "wb") as f: f.write(clip)
            rc, out, err = run(["-i", fn], False)
            frames = split_mjpeg(out) if rc == 0 else []
        finally:
            wipe(fn)
            try: os.rmdir(d)
            except Exception: pass
        how = "spooled and wiped"
    if not frames: raise RuntimeError("ffmpeg could not read the clip (%s): %s" % (ctype, err.strip()[-300:]))
    return frames, how
def join_frames(ff, prints, fps):
    """the prints into one MP4 (H.264, yuv420p, faststart) via a scratch file that is wiped"""
    d = tempfile.mkdtemp(prefix="emulsify-"); fn = os.path.join(d, "roll.mp4")
    try:
        p = subprocess.Popen([ff, "-hide_banner", "-loglevel", "error", "-nostdin", "-y", "-f", "image2pipe", "-vcodec", "mjpeg", "-r", "%g" % fps, "-i", "pipe:0",
                              "-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2", "-c:v", "libx264", "-preset", "veryfast", "-crf", str(ROLL_CRF), "-pix_fmt", "yuv420p", "-movflags", "+faststart", "-r", "%g" % fps, fn],
                             stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        for jpg in prints: p.stdin.write(jpg)
        p.stdin.close(); err = p.stderr.read().decode("utf-8", "replace"); p.wait(timeout=600)
        if p.returncode != 0: raise RuntimeError("ffmpeg could not write the film: " + err.strip()[-300:])
        with open(fn, "rb") as f: return f.read()
    finally:
        wipe(fn)
        try: os.rmdir(d)
        except Exception: pass
def develop_roll(job):
    p = job["params"]; jid = job["id"]
    fps = float(p.get("fps", 24)); size = int(float(p.get("size", 720))); seed = int(float(p.get("seed", 1)))
    mm = int(float(p.get("mm", 33))); ana = float(p.get("ana", 1)); dc = str(p.get("dc", "1")) in ("1", "true", "True"); build = int(float(p.get("build", 0)))
    try: crop = [float(x) for x in str(p.get("crop", "0,0,1,1")).split(",")]; assert len(crop) == 4
    except Exception: crop = [0.0, 0.0, 1.0, 1.0]
    ff = ffmpeg_exe()
    t0 = time.time(); clip = call("GET", "/agent/jobs/%s/neg" % jid, timeout=300)
    frames, how = cut_frames(ff, clip, p.get("ctype", ""), fps, crop, size)
    if len(frames) > ROLL_MAX_FRAMES: frames = frames[:ROLL_MAX_FRAMES]
    n = len(frames); del clip
    timing = str(p.get("timing", "shot"))
    log("agent: roll %s %s: %d frames at %g fps, film frame %dpx, clip %s, %d labs, timing %s" % (jid[:8], p.get("who", "?"), n, fps, size, how, ROLL_PROCS, timing))
    call("POST", "/agent/jobs/%s/progress" % jid, ("timing %d" % n).encode())
    pool = roll_pool()
    probes = [None] * n
    if timing != "frame":
        for i, pr in pool.imap_unordered(_roll_probe, [(i, f, size, mm, ana) for i, f in enumerate(frames)]): probes[i] = pr
    shots = time_the_shot(probes, fps, timing)
    if timing != "frame":
        ev = [s["ev"] for s in shots]; raw = [pr["ev"] for pr in probes]
        log("agent: roll %s timed as a shot: ev %.2f..%.2f (frames measured %.2f..%.2f), warm %.2f..%.2f" % (jid[:8], min(ev), max(ev), min(raw), max(raw), min(s["warmbias"] for s in shots), max(s["warmbias"] for s in shots)))
    call("POST", "/agent/jobs/%s/progress" % jid, ("0/%d" % n).encode())
    prints = [None] * n; lab_secs = 0.0; last = time.time(); done = 0
    # frame 0 first and alone: its fixer trim is the roll's
    hold = (timing != "frame") and ROLL_FIELDS != "roll"
    i0, jpg0, secs0, meas0 = pool.apply(_roll_frame, ((0, frames[0], seed, size, mm, ana, dc, build, shots[0], hold),))
    prints[0] = jpg0; lab_secs += secs0; done = 1
    call("POST", "/agent/jobs/%s/poster" % jid, jpg0)
    g0 = meas0.get("g")
    if timing != "frame" and g0 is not None:
        for sh in shots[1:]: sh["g"] = [float(x) for x in g0]
    for i, jpg, secs, _m in pool.imap_unordered(_roll_frame, [(i, frames[i], seed, size, mm, ana, dc, build, shots[i], hold) for i in range(1, n)]):
        prints[i] = jpg; lab_secs += secs; done += 1
        if time.time() - last > 2.5: call("POST", "/agent/jobs/%s/progress" % jid, ("%d/%d" % (done, n)).encode()); last = time.time()
    del frames
    call("POST", "/agent/jobs/%s/progress" % jid, ("%d/%d joining" % (n, n)).encode())
    mp4 = join_frames(ff, prints, fps); del prints
    return mp4, lab_secs, n, time.time() - t0

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
                if job["params"].get("kind") == "roll":
                    mp4, secs, frames, wall = develop_roll(job)
                    req = request.Request(LOBBY + "/agent/jobs/%s/print?secs=%.2f" % (job["id"], secs), data=mp4, method="POST", headers={"X-Agent-Key": KEY, "Content-Type": "video/mp4"})
                    with request.urlopen(req, timeout=300) as r: r.read()
                    log("agent[%d]: roll %s %s -> %d frames, %d KB of film in %.0fs wall (lab %.0fs); scratch wiped" % (n, job["id"][:8], job["params"].get("who", "?"), frames, len(mp4) // 1024, wall, secs))
                    continue
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
                quiet = subprocess.DEVNULL if extra else None          # with --log the children write the file themselves; without it they share this console
                procs[i] = subprocess.Popen([sys.executable, os.path.abspath(__file__), "--worker", str(i)] + extra, stdin=subprocess.DEVNULL, stdout=quiet, stderr=quiet)
        time.sleep(3)

if __name__ == "__main__":
    if "--gate" in sys.argv: sys.exit(0 if gate() else 1)
    if "--worker" in sys.argv: worker(int(sys.argv[sys.argv.index("--worker") + 1]))
    else: supervise()
