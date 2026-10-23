#!/usr/bin/env python3
"""python3 make-profiles.py > profiles.json
Lobby keys: sha256("emulsify-lobby:" + password.strip().lower()). The page sends this; the page never contains it.
Add a person: one line below. Passwords here are the same ones the page accepts."""
import hashlib, json
def k(pw): return hashlib.sha256(("emulsify-lobby:" + pw.strip().lower()).encode()).hexdigest()
P = {
  "RG":   ["banjo", "loon", "love", "choke", "magnet", "hug", "alien", "puke", "levity", "490110", "stability", "stable"],
  "RITA": ["enemyofman"],
}
print(json.dumps({who: [k(pw) for pw in pws] for who, pws in P.items()}, indent=1))
