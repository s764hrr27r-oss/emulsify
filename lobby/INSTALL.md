# EMULSIFY LOBBY — install (b241)

**The one-script way (what you actually run):** on the lab PC, in PowerShell,

    powershell -ExecutionPolicy Bypass -File .\emulsify-setup.ps1

`emulsify-setup.ps1` carries every file below inside it and does all three parts in order, checking before each
change (safe to re-run). It needs the droplet's root password only if your ssh key is not on the droplet yet, and
may ask for a GitHub sign-in when it pushes index.html. Everything below is what it does, for the record.

Phone → `emulsify.gibsoncttools.com` (the lobby, on the droplet) → lab PC polls, develops, posts the print back.
The droplet develops nothing. The two CTForge Caddy blocks, `ctforge-web`, port 8765, `/opt/ctforge`,
`/var/lib/ctforge`, `/etc/ctforge` are not touched.

## 1. Droplet (10 minutes, as root)

```sh
ssh root@24.199.126.36
free -m; df -h; systemctl status ctforge-web caddy --no-pager | head -20     # before: the box is small

adduser --system --group --home /opt/emulsify emulsify
mkdir -p /opt/emulsify /var/lib/emulsify /etc/emulsify
# copy lobby.py, profiles.json into /opt/emulsify  (scp from the PC, or paste)
chown -R emulsify:emulsify /opt/emulsify /var/lib/emulsify

cp lobby.env.example /etc/emulsify/lobby.env && chmod 600 /etc/emulsify/lobby.env
python3 -c "import secrets;print(secrets.token_hex(24))"      # -> paste as EMULSIFY_AGENT_KEY in /etc/emulsify/lobby.env
cp emulsify-lobby.service /etc/systemd/system/
systemctl daemon-reload && systemctl enable --now emulsify-lobby && systemctl status emulsify-lobby --no-pager
curl -s http://127.0.0.1:8766/health          # {"ok": true, "queued": 0, "agent_seen": null, "profiles": ["RG","RITA"]}
```

Caddy: append `Caddyfile.emulsify` to `/etc/caddy/Caddyfile`, then

```sh
caddy validate --config /etc/caddy/Caddyfile && systemctl reload caddy
curl -s https://gibsoncttools.com/api/health      # the lobby site must still answer {"ok":true,...}
```

Cloudflare DNS for the zone: **A record** `emulsify` → `24.199.126.36`, **DNS only (grey cloud)**, TTL auto.
About five minutes later Caddy fetches the certificate on the first request:

```sh
curl -s https://emulsify.gibsoncttools.com/health
```

## 2. Lab PC (Windows, the 4090 box)

Needs Python 3.11+, Node (for the worker-template harness), and a clone of the repo.

```bat
git clone https://github.com/s764hrr27r-oss/emulsify C:\emulsify
cd C:\emulsify && pip install numpy scipy pillow
copy lobby\agent.json.example lobby\agent.json      :: edit: agent_key = the EMULSIFY_AGENT_KEY from the droplet, repo = C:\emulsify
python lobby\emulsify-agent.py
```

The first lines it prints are the gate:

```
agent: golden 4be892e9e27c70ec  v21 4be892e9e27c70ec -> HOLDS
```

If it says CHANGED it refuses to serve — the PC's numpy/scipy produce a different print than the phone's and that
has to be understood first, not worked around. To keep it running when nobody is logged in, wrap it in a
scheduled task at logon (same shape as the CTForge agent), or `nssm install emulsify-agent`.

`workers` in agent.json is how many frames develop at once; 2 is right to start, raise it for FILM.

## 3. Phone

`index.html` b241 already points at `https://emulsify.gibsoncttools.com`. Signed in with a password (RG, RITA),
every frame goes through the lobby; the finder says `DEVELOPING · AT THE LOBBY` then `· AT THE LAB`. Signed out,
or if the lobby does not answer within 15 s, it flashes `LOBBY UNREACHABLE - DEVELOPING HERE` and the phone's own
bath runs as it always has. Nothing is stored on the phone about the lobby; the key dies with the session.

Adding a person: add their line to `make-profiles.py`, regenerate `profiles.json`, restart `emulsify-lobby`,
and give them the same password in the page's THEMED table (or a plain profile with `pw:` only — a theme is optional).

## Keys, plainly

- Phone key = `sha256("emulsify-lobby:" + password)`. The page contains `sha256(password)` for sign-in, a different
  hash, so reading the page does not get into the lobby.
- Agent key = one random string in `/etc/emulsify/lobby.env` and `agent.json`. Nothing else.
- Negatives leave the phone only for signed-in people, sit on the droplet until the print is posted (then are
  deleted), prints are swept after 24 h.

## Ritual

`python3 e2e-lobby.py` runs the page against a local lobby and a stand-in agent (`EMULSIFY_AGENT_STANDIN=1`, which
resizes instead of developing — pipe test only). The real lab is proven by the agent's golden gate on the PC.
