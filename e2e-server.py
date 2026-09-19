"""Static files + POST /develop -> the worker's own Python develop(), via the golden harness."""
import sys, json, base64, io, os
sys.path.insert(0, "/home/claude/emulsify")
from http.server import HTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import golden
NS = golden.harness("/home/claude/emulsify/lab-worker.js")
class H(SimpleHTTPRequestHandler):
    def __init__(self, *a, **k): super().__init__(*a, directory="/home/claude/emulsify", **k)
    def log_message(self, *a): pass
    def do_POST(self):
        u = urlparse(self.path); q = parse_qs(u.query)
        n = int(self.headers.get("Content-Length", "0")); neg = self.rfile.read(n)
        NS["_LEAK"] = float(q.get("leak", ["0"])[0]); NS["_LENS_MM"] = int(q.get("mm", ["33"])[0]); NS["_BUILD"] = int(q.get("build", ["0"])[0])
        NS["_DC_ON"] = True
        r = NS["develop"](neg, "honey", int(q.get("seed", ["1"])[0]), int(q.get("size", ["1100"])[0]))
        body = json.dumps({"jpg": base64.b64encode(r["jpg"]).decode(), "secs": r["secs"]}).encode()
        self.send_response(200); self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)
HTTPServer(("127.0.0.1", 8765), H).serve_forever()
