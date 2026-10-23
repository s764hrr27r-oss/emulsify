# EMULSIFY LOBBY + FILM — install (b245 / w3.25, lobby kit 5)

**The one-script way (what you actually run):** on the lab PC, in PowerShell,

    powershell -ExecutionPolicy Bypass -File .\emulsify-setup.ps1

`emulsify-setup.ps1` carries every file below inside it and does all three parts in order, checking before each
change (safe to re-run). It also installs `imageio-ffmpeg`, the ffmpeg that cuts and joins film. It needs the droplet's root password only if your ssh key is not on the droplet yet, and
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

## FILM (b242)

Hold the shutter on the phone (signed in with a password) and it records, up to 8 s; let go and the clip goes to
the lobby as a **roll** with the finder's window as fractions of the frame. On the lab PC the agent:

1. cuts that window out of every frame at 24 fps with ffmpeg (from memory; an MP4 with its index at the end is
   spooled to a scratch file that is overwritten with zeros and removed),
2. develops the frames in parallel - `roll.procs` lab processes, one lab per process (golden.py trap 1) -
   under THE ROLL RULE: one seed per roll for the stock's character (mineral beds, strata colour bias), the grain
   field and emulsion fields re-rolled every frame (grain seed + frame * 1000003, field seed + frame * 7777),
   so the look holds and the grain lives. Frame 0 is exactly the still that negative would make,
3. joins the prints into an H.264 MP4 (yuv420p, faststart) through a scratch file that is wiped the same way,
   posts the film and a poster (the first frame) to the lobby, and keeps nothing.

The phone polls in the background (the strip shows `FILM 37/192`), stores the film beside its prints with a play
mark, plays it in the print view, and tells the lobby to forget the job. Film frame 720 px long edge (576 x 720),
24 fps, 8 s max: tune `FILM` in index.html; `?film=size,fps,max` overrides it for rituals.

## THE SHOT (w3.25, kit 4): film does not flicker

A still times itself from its own pixels: the meter's push, the drift balancer's colour gains and warm bias, the
exposure from the median, the fixer's colour trim. Frame by frame that is flicker. In w3.25 the lab has `_SHOT`:
when set, `_develop_streamed` uses the shot's timing instead of measuring, and `_shot_probe` measures a frame
without developing it. Inert for stills (golden v21 holds byte for byte). The agent probes every frame first,
smooths the measurements along the roll (a gaussian `roll.smooth_seconds` = 0.6 s wide; `timing=lock` holds
the roll's median instead; `timing=frame` is b242's every-frame-for-itself), reads the fixer trim off frame 0
and holds it, and holds the emulsion fields for the roll (`roll.fields` = hold; `roll` re-draws them every frame
as b242 did). Grain still re-rolls every frame.

Measured (`filmcheck.py`, a 4 s pan and a 4 s static shot of a real photograph): exposure response wobble
4.95% -> 1.88%, colour timing wobble 0.206 -> 0.075 levels, 24 px patch boil 0.67 -> 0.17 levels, grain life
1.92 -> 1.81 (94% kept). A drifting blend of two field draws was tried first and rejected by the same ritual:
the draws share a radial pull, the blend swelled mid-turn and the frame breathed 25 levels.

Throughput: a 720 px frame is ~3 s of lab time here, ~4 s on the lab PC; 8 s of film = 192 frames, so with
8 lab processes a roll comes back in about two minutes. `roll.procs` in agent.json sets the parallelism
(default: cores - 2, capped at 8); each lab process needs ~400 MB while it develops.

Rituals: `python3 e2e-film.py` (page on 8765, lobby on 8766, the real agent polling it; includes the STILL/FILM mode) and `python3 filmcheck.py` (the flicker numbers above).

## THE SHELF (b245)

Every finished roll is also kept on the droplet for its owner (`$EMULSIFY_DATA/shelf/<WHO>/`), never swept.
Signed in, the phone asks `GET /shelf` and pulls down any film it does not have, so a person's films are in her
gallery on whichever phone she signs into. Stills are not shelved (they develop on the phone when the lab is away
and belong to the phone). Profiles: RG, RITA, LUCA (make-profiles.py).

## The lab light (b244) and landscape (b244)

Signed in, a dot in the top bar: green LAB (the lab PC answered the lobby in the last 20 s), amber LAB ASLEEP
(lobby up, lab away: stills develop on the phone, film waits), red NO LOBBY. Landscape: `#gate` needed
`min-width:0` - Safari gave it the finder's aspect-ratio width as a minimum and pushed the foot off-screen.
