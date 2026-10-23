#!/usr/bin/env python3
"""EMULSIFY LOBBY - the droplet's half of the remote lab.

The lobby develops nothing. It holds negatives for the lab PC and prints for the phone:

  phone  POST /jobs?seed=..&size=..&mm=..&ana=..&leak=..&dc=..&build=..   body: the negative (JPEG)
                headers X-Who: RG   X-Key: <lobby key>            -> {"id": ..}
  phone  GET  /jobs/<id>                                            -> {"state": queued|working|done|failed, "secs": ..}
  phone  GET  /jobs/<id>/print                                      -> the print (JPEG)
  agent  POST /agent/claim          header X-Agent-Key               -> {"id", "params"} or {} when nothing waits
  agent  GET  /agent/jobs/<id>/neg  header X-Agent-Key               -> the negative
  agent  POST /agent/jobs/<id>/print?secs=..  header X-Agent-Key     -> stores the print, state -> done
  agent  POST /agent/jobs/<id>/fail  header X-Agent-Key   body: why  -> state -> failed
  anyone GET  /health                                                -> {"ok": true, "queued": n, "agent_seen": secs ago}

Everything lives under $EMULSIFY_DATA/jobs/<id>/ (neg.jpg, params.json, state, print.jpg). Jobs older than
$EMULSIFY_KEEP_HOURS are swept. Standard library only; one small process; binds 127.0.0.1 and lets Caddy do TLS.

Keys. The phone's key is sha256("emulsify-lobby:" + password.strip().lower()) - a hash the page never contains, so
reading index.html does not get you in. profiles.json maps initials -> list of accepted keys. The agent's key is a
random string shared between $EMULSIFY_AGENT_KEY here and agent.json on the lab PC.
"""
import json, os, sys, time, uuid, shutil, threading
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

HOST = os.environ.get("EMULSIFY_HOST", "127.0.0.1")
PORT = int(os.environ.get("EMULSIFY_PORT", "8766"))
DATA = os.environ.get("EMULSIFY_DATA", "/var/lib/emulsify")
KEEP_H = float(os.environ.get("EMULSIFY_KEEP_HOURS", "24"))
AGENT_KEY = os.environ.get("EMULSIFY_AGENT_KEY", "")
PROFILES = os.environ.get("EMULSIFY_PROFILES", os.path.join(os.path.dirname(os.path.abspath(__file__)), "profiles.json"))
ORIGINS = set(filter(None, os.environ.get("EMULSIFY_ORIGINS", "https://s764hrr27r-oss.github.io,http://127.0.0.1:8765,http://localhost:8765").split(",")))
MAX_NEG = 40 * 1024 * 1024            # a 4032x3024 JPEG is well under this; a roll will come as many frames
JOBS = os.path.join(DATA, "jobs")
PARAM_KEYS = ("seed", "size", "mm", "ana", "leak", "dc", "build", "profile")
lock = threading.Lock()
agent_seen = 0.0

def load_profiles():
    try:
        with open(PROFILES) as f: return json.load(f)
    except Exception as e:
        print("lobby: no profiles (%s) - nobody can sign in" % e, flush=True); return {}
profiles = load_profiles()

def jdir(i): return os.path.join(JOBS, i)
def read(i, name, mode="r"):
    with open(os.path.join(jdir(i), name), mode) as f: return f.read()
def write(i, name, data, mode="w"):
    tmp = os.path.join(jdir(i), name + ".tmp")
    with open(tmp, mode) as f: f.write(data)
    os.replace(tmp, os.path.join(jdir(i), name))
def state(i):
    try: return read(i, "state").strip()
    except FileNotFoundError: return ""
def sweep():
    cut = time.time() - KEEP_H * 3600
    for i in os.listdir(JOBS) if os.path.isdir(JOBS) else []:
        try:
            if os.path.getmtime(jdir(i)) < cut: shutil.rmtree(jdir(i), ignore_errors=True)
        except FileNotFoundError: pass
def queued():
    n = 0
    for i in (os.listdir(JOBS) if os.path.isdir(JOBS) else []):
        if state(i) == "queued": n += 1
    return n
def oldest_queued():
    best = None
    for i in (os.listdir(JOBS) if os.path.isdir(JOBS) else []):
        if state(i) == "queued":
            t = os.path.getmtime(os.path.join(jdir(i), "state"))
            if best is None or t < best[0]: best = (t, i)
    return best[1] if best else None
def safe_id(i): return i and all(c in "0123456789abcdef" for c in i) and len(i) == 32

class H(BaseHTTPRequestHandler):
    server_version = "emulsify-lobby/1"
    def log_message(self, *a): pass
    # -- plumbing
    def cors(self):
        o = self.headers.get("Origin", "")
        if o in ORIGINS:
            self.send_header("Access-Control-Allow-Origin", o)
            self.send_header("Access-Control-Allow-Headers", "X-Who, X-Key, Content-Type")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Max-Age", "600")
            self.send_header("Vary", "Origin")
    def out(self, code, body=b"", ctype="application/json"):
        if isinstance(body, (dict, list)): body = json.dumps(body).encode()
        self.send_response(code); self.cors()
        self.send_header("Content-Type", ctype); self.send_header("Content-Length", str(len(body))); self.send_header("Cache-Control", "no-store")
        self.end_headers(); self.wfile.write(body)
    def body(self, limit=MAX_NEG):
        n = int(self.headers.get("Content-Length", "0") or 0)
        if n > limit: self.out(413, {"error": "too big"}); return None
        return self.rfile.read(n)
    def phone_ok(self):
        who = (self.headers.get("X-Who") or "").upper().strip(); key = (self.headers.get("X-Key") or "").strip()
        return bool(who) and key in profiles.get(who, [])
    def agent_ok(self):
        global agent_seen
        ok = bool(AGENT_KEY) and self.headers.get("X-Agent-Key", "") == AGENT_KEY
        if ok: agent_seen = time.time()
        return ok
    def do_OPTIONS(self): self.out(204)
    # -- routes
    def do_GET(self):
        u = urlparse(self.path); p = u.path.rstrip("/").split("/")
        if u.path == "/health":
            return self.out(200, {"ok": True, "queued": queued(), "agent_seen": round(time.time() - agent_seen) if agent_seen else None, "profiles": sorted(profiles)})
        if len(p) == 3 and p[1] == "jobs" and safe_id(p[2]):
            if not self.phone_ok(): return self.out(401, {"error": "sign in"})
            st = state(p[2])
            if not st: return self.out(404, {"error": "no such job"})
            r = {"state": st}
            if st == "done":
                try: r["secs"] = json.loads(read(p[2], "done.json"))["secs"]
                except Exception: pass
            if st == "failed":
                try: r["error"] = read(p[2], "error.txt")[:300]
                except Exception: pass
            return self.out(200, r)
        if len(p) == 4 and p[1] == "jobs" and safe_id(p[2]) and p[3] == "print":
            if not self.phone_ok(): return self.out(401, {"error": "sign in"})
            if state(p[2]) != "done": return self.out(409, {"error": "not done"})
            return self.out(200, read(p[2], "print.jpg", "rb"), "image/jpeg")
        if len(p) == 5 and p[1] == "agent" and p[2] == "jobs" and safe_id(p[3]) and p[4] == "neg":
            if not self.agent_ok(): return self.out(401, {"error": "agent key"})
            if not state(p[3]): return self.out(404, {"error": "no such job"})
            return self.out(200, read(p[3], "neg.jpg", "rb"), "image/jpeg")
        self.out(404, {"error": "lobby: no such door"})
    def do_POST(self):
        global agent_seen
        u = urlparse(self.path); q = parse_qs(u.query); p = u.path.rstrip("/").split("/")
        if u.path == "/jobs":
            if not self.phone_ok(): return self.out(401, {"error": "sign in"})
            neg = self.body()
            if neg is None: return
            if len(neg) < 1000 or neg[:2] != b"\xff\xd8": return self.out(400, {"error": "not a JPEG negative"})
            i = uuid.uuid4().hex
            params = {k: q[k][0] for k in PARAM_KEYS if k in q}; params["who"] = (self.headers.get("X-Who") or "").upper().strip()
            os.makedirs(jdir(i), exist_ok=True)
            write(i, "neg.jpg", neg, "wb"); write(i, "params.json", json.dumps(params)); write(i, "state", "queued")
            sweep()
            return self.out(201, {"id": i, "queued": queued(), "agent_seen": round(time.time() - agent_seen) if agent_seen else None})
        if u.path == "/agent/claim":
            if not self.agent_ok(): return self.out(401, {"error": "agent key"})
            with lock:
                i = oldest_queued()
                if not i: return self.out(200, {})
                write(i, "state", "working")
            return self.out(200, {"id": i, "params": json.loads(read(i, "params.json"))})
        if len(p) == 5 and p[1] == "agent" and p[2] == "jobs" and safe_id(p[3]) and p[4] in ("print", "fail"):
            if not self.agent_ok(): return self.out(401, {"error": "agent key"})
            if not state(p[3]): return self.out(404, {"error": "no such job"})
            b = self.body()
            if b is None: return
            if p[4] == "print":
                write(p[3], "print.jpg", b, "wb"); write(p[3], "done.json", json.dumps({"secs": float(q.get("secs", ["0"])[0])})); write(p[3], "state", "done")
            else:
                write(p[3], "error.txt", b.decode("utf-8", "replace")[:2000]); write(p[3], "state", "failed")
            try: os.remove(os.path.join(jdir(p[3]), "neg.jpg"))     # the negative has done its job
            except FileNotFoundError: pass
            return self.out(200, {"ok": True})
        self.out(404, {"error": "lobby: no such door"})

if __name__ == "__main__":
    os.makedirs(JOBS, exist_ok=True)
    if not AGENT_KEY: print("lobby: EMULSIFY_AGENT_KEY is empty - the lab PC cannot connect until it is set", flush=True)
    print("lobby: %s:%d  data %s  profiles %s  origins %s" % (HOST, PORT, DATA, sorted(profiles), sorted(ORIGINS)), flush=True)
    ThreadingHTTPServer((HOST, PORT), H).serve_forever()
