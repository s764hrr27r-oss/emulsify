// lab-worker.js — v2.2. Verbatim canon; JPEG prints
// v2.2: DUAL-COAT. Real color film coats each record as two sublayers — a
// fast, coarse-crystal one that carries the deep scale and a slow, fine one
// that holds the upper scale. Emulsify now does the same: two develops per
// frame (the slow pass IS the previous rendering; the fast pass runs at 0.56
// scale = bigger crystals, +1.2 EV), gray-axis matched to kill crossover
// error, recombined per record. Identity above the deep scale.
// v2.1: the easel's horizontal axis becomes VIBRANCE (chroma-only, luminance
// byte-preserved — the density law holds). Vertical stays green/magenta.
// v2.0: THE WHISPER. The sandwich retuned to the owner's spec — "a little
// detail from the darks, that's it": one-third strength, reach tightened to
// the truly deep, donor ceiling lowered so recovered tones stay dark, and
// grain transplanted as a single luminance field (no chroma speckle).
// v1.9: the bath narrates two moments only — the orange negative forming and
// the finished print. The old fixer snapshot predated flash+sandwich and
// rendered black on dark scenes; it's gone, and the tray never cuts to black.
// v1.8: sandwich at 60%, and the transplanted grain now carries the stock's
// full amplitude (exponent 1.7, wide clip) so donated shadows wear the same
// rough cloth as the rest of the print.
// v1.7: SANDWICH PRINTING — in the deep zone the print is blended toward a
// soft positive of the base negative itself (owner's design: borrow from the
// base), then the film's own grain field is transplanted over the donated
// tones so the technique is invisible. Fixed law, deterministic, gated to
// true shadows; outside the mask the math is exact identity.
// v1.6: exposure compensation — a user EV bias (±2 stops) rides into the
// chemistry through the existing emulsify2 seam. EV 0 is float-identity:
// the golden is untouched by construction and re-proven by hash.
// v1.4 added the bath-watcher (read-only snapshots at two real pipeline
// moments). v1.5 reverts develop size to 1100: 1400 exceeded iOS's web
// process memory ceiling mid-chemistry and the OS killed the page.
// Fine/large develops stay a desktop idea, not a phone one.
// v1.3 adds the paper pre-flash (FLASH 2): a whisper of uniform print
// exposure lifting only the deepest shadows onto the toe of the paper
// curve. Additive wrapper at the _dodge seam; every canon line untouched.
// + garbage collection to keep iOS Safari happy.
// v1.2 adds bake(): the printer's easel — density-neutral warmth/tint gains
// applied in linear to a finished print, EXIF re-stamped. No re-develop;
// canon and chemistry untouched.

importScripts("https://cdn.jsdelivr.net/pyodide/v0.26.1/full/pyodide.js");

let pyodide = null, develop = null, bakePy = null;

const boot = (async () => {
  postMessage({ progress: "loading chemistry…" });
  pyodide = await loadPyodide();
  await pyodide.loadPackage(["numpy", "scipy", "pillow"]);
  for (const f of ["emulsify2.py", "honey_sr.py", "canon_profiles.py"]) {
    const src = await (await fetch(f)).text();
    pyodide.FS.writeFile(f, src);
  }
  await pyodide.runPythonAsync(`
import io, gc, numpy as np
from PIL import Image, ImageOps
from scipy.ndimage import gaussian_filter
import emulsify2 as E
from honey_sr import unrender
from canon_profiles import HONEY70_CANON, SCOPE70_CANON
from scipy.special import erf

LONG_EDGE = 1100   # daily develop size; the phone's memory ceiling is law

def _expand(lin, kmax=2.2):
    """DYNAMIC EXPANSION: per-channel, highlights only. Mids stay anchored;
    the JPEG's crushed top end stretches back into real light ratios, so
    flames, windows and sky feed the emulsion's shoulder and halation with
    the energy the scene actually had. Colored light expands in its own
    color."""
    import numpy as np
    t = 0.75
    over = np.clip((lin - t)/(1 - t), 0, 1)
    gain = 1.0 + (kmax - 1.0)*over**1.8
    return np.clip(lin*gain, 0, kmax + 0.3)

# ---- KINETIC STABILIZER (documented addendum to the frozen canon) ----
# The negative meters its own development: each layer's rate leans gently
# against exposure error and color cast (max ~ +/-6% color, +/-15% time).
# Deterministic — driven only by the image. Rescued frames carry a trace
# of push character, as real rescued rolls did.
_TAUS = [1.0, 1.0, 1.0]; _CALL = [0]; _FIELDS = [None, None, None]; _BEDS = [None, None, None]

# ---- THE MINERAL CATALOG ----
# name: (rarity, size_um, speed, dev_rate, glint, contrast)
# 66 species across five tiers: common / uncommon / rare / epic / mythic.
# speed = light-catching; dev_rate = how hard it rides the weather;
# glint = micro-contrast sparkle; contrast = curve steepness.
MINERALS = {
 "quartz":(1.00,0.55,1.00,1.00,0.85,1.00), "milky quartz":(0.95,0.60,0.96,0.95,0.80,0.98),
 "smoky quartz":(0.85,0.60,0.98,1.05,0.88,1.04), "rose quartz":(0.80,0.65,0.97,0.92,0.86,0.96),
 "feldspar":(0.90,0.70,0.95,0.98,0.78,0.97), "calcite":(0.88,0.75,0.93,1.02,0.75,0.92),
 "jasper":(0.78,0.85,1.00,1.08,0.82,1.02), "agate":(0.75,0.80,0.98,1.00,0.90,1.00),
 "onyx":(0.70,0.75,0.96,0.95,0.92,1.12), "obsidian":(0.68,0.50,1.06,1.18,1.00,1.18),
 "hematite":(0.66,0.95,0.90,0.85,0.95,1.10), "pyrite":(0.64,0.90,1.08,1.12,1.10,0.95),
 "fluorite":(0.62,0.85,1.02,1.10,1.00,0.90),
 "amethyst":(0.50,0.70,1.02,0.95,0.98,1.06), "citrine":(0.48,0.70,1.08,1.05,1.02,1.00),
 "carnelian":(0.46,0.75,1.10,1.12,1.00,0.98), "garnet":(0.45,0.72,1.08,1.10,1.02,1.05),
 "malachite":(0.42,0.90,0.94,1.15,0.95,1.02), "lapis lazuli":(0.40,0.85,0.96,0.90,1.05,1.05),
 "turquoise":(0.40,0.88,0.98,0.95,0.92,0.95), "moonstone":(0.38,0.95,0.90,0.85,0.88,0.86),
 "labradorite":(0.36,0.90,0.95,0.92,1.15,0.92), "amber":(0.35,1.05,0.98,0.80,0.90,0.88),
 "jade":(0.34,0.80,0.94,0.88,0.90,1.00), "bloodstone":(0.33,0.85,1.05,1.15,0.95,1.05),
 "sunstone":(0.32,0.85,1.15,1.10,1.15,0.95), "redstone":(0.35,1.00,1.05,1.30,0.95,0.95),
 "tourmaline":(0.30,0.75,1.04,1.08,1.05,1.04),
 "topaz":(0.26,0.70,1.10,1.05,1.08,1.08), "aquamarine":(0.25,0.75,1.02,0.92,1.05,1.06),
 "peridot":(0.25,0.78,1.06,1.12,1.02,1.00), "fire opal":(0.25,1.25,1.25,1.25,1.20,0.90),
 "emerald":(0.22,0.80,0.95,0.90,0.90,1.10), "ruby":(0.22,0.70,1.12,1.15,1.00,1.00),
 "sapphire":(0.22,0.68,1.08,1.02,1.05,1.18), "tanzanite":(0.20,0.90,0.90,0.80,1.10,1.15),
 "opal":(0.18,1.10,1.15,1.10,1.30,0.86), "iolite":(0.17,0.80,0.98,0.95,1.02,1.05),
 "kunzite":(0.16,0.85,0.95,0.88,1.00,0.95), "morganite":(0.15,0.80,1.00,0.92,1.02,0.98),
 "zircon":(0.15,0.65,1.18,1.10,1.20,1.10), "spinel":(0.14,0.70,1.10,1.08,1.08,1.08),
 "alexandrite":(0.12,0.72,1.15,1.05,1.25,1.12),
 "black opal":(0.10,1.15,1.20,1.10,1.40,0.90), "red beryl":(0.09,0.70,1.18,1.12,1.15,1.12),
 "benitoite":(0.08,0.65,1.22,1.08,1.30,1.10), "grandidierite":(0.07,0.75,1.10,1.00,1.18,1.15),
 "taaffeite":(0.06,0.68,1.20,1.05,1.28,1.14), "musgravite":(0.055,0.70,1.22,1.05,1.30,1.15),
 "painite":(0.05,0.72,1.25,1.10,1.32,1.16), "diamond":(0.05,0.40,1.40,0.95,1.55,1.25),
 "kyber":(0.040,0.45,1.35,1.10,1.45,1.20), "dragonstone":(0.035,1.20,1.30,1.35,1.25,0.95),
 "thunderstone":(0.030,0.90,1.28,1.40,1.20,1.00), "toadstone":(0.028,0.95,0.92,0.85,0.95,0.92),
 "adder stone":(0.026,0.85,0.95,0.90,1.00,0.95), "carbuncle":(0.024,0.75,1.30,1.15,1.35,1.05),
 "draconite":(0.022,0.80,1.25,1.25,1.25,1.10), "orichalcum":(0.020,0.85,1.20,1.05,1.30,1.15),
 "adamant":(0.018,0.60,1.15,0.70,1.25,1.32), "cintamani":(0.015,0.70,1.30,1.20,1.40,1.10),
 "warpstone":(0.012,1.05,1.28,1.45,1.38,0.85), "philosopher's stone":(0.010,0.75,1.35,1.42,1.40,1.05),
 "arkenstone":(0.009,0.55,1.42,1.05,1.55,1.20), "palantir shard":(0.008,0.50,1.30,0.90,1.35,1.28),
 "silmaril shard":(0.006,0.42,1.50,1.00,1.68,1.22),
}
def _tier(n):
    w0 = MINERALS[n][0]
    return ("common" if w0 >= 0.6 else "uncommon" if w0 >= 0.28 else
            "rare" if w0 >= 0.12 else "epic" if w0 >= 0.045 else "mythic")
_COMMON  = [n for n in MINERALS if _tier(n) == "common"]
_MIDPOOL = [n for n in MINERALS if _tier(n) in ("uncommon", "rare")]
_GEMPOOL = [n for n in MINERALS if _tier(n) in ("rare", "epic", "mythic")]

def _draw_beds(seed):
    """Each layer's emulsion: a common matrix stone, two mid-tier draws,
    and one GEM SLOT contested by everything from topaz to the silmaril
    shard, weighted by rarity. ~1 frame in 5 carries a mythic stone.
    Seeded: the same frame always grows the same crystals."""
    import numpy as np
    rng = np.random.default_rng(seed*104729 + 7)
    beds = []
    for i in range(3):
        wc = np.array([MINERALS[m][0] for m in _COMMON]); wc = wc/wc.sum()
        matrix = str(rng.choice(_COMMON, p=wc))
        f_m = float(rng.uniform(0.35, 0.50))
        wm = np.array([MINERALS[m][0] for m in _MIDPOOL]); wm = wm/wm.sum()
        m1, m2 = [str(x) for x in rng.choice(_MIDPOOL, size=2, replace=False, p=wm)]
        wg = np.array([MINERALS[m][0] for m in _GEMPOOL]); wg = wg/wg.sum()
        gem = str(rng.choice(_GEMPOOL, p=wg))
        f_g = float(rng.uniform(0.05, 0.12))
        rem = 1.0 - f_m - f_g
        r1 = float(rng.uniform(0.45, 0.65))
        bed = [(matrix, f_m), (m1, rem*r1), (m2, rem*(1-r1)), (gem, f_g)]
        full = [(n, f) + MINERALS[n][1:] for n, f in bed]
        # NORMALIZE THE BED: the mixture stays wild, but its aggregate
        # light-catching and development rate are pinned to 1.0 — like a
        # real emulsion blended to its rated speed. A bed can shape
        # texture and character; it can never tilt a layer's color.
        ls = sum(f*np.log10(sp) for (n, f, sz, sp, dr, gl, ct) in full)
        ld = sum(f*np.log10(dr) for (n, f, sz, sp, dr, gl, ct) in full)
        ks, kd = 10.0**ls, 10.0**ld
        full = [(n, f, sz, sp/ks, dr/kd, gl, ct)
                for (n, f, sz, sp, dr, gl, ct) in full]
        beds.append(full)
    return beds

def _make_fields(h, w, seed):
    """LIVING DEVELOPMENT — INDEPENDENT BIOMES, FULL SPECTRUM.
    Each layer draws its entire character per frame: speed (correlation
    length, squalls to continental), flavor (amplitude), pull (radial),
    spots (centers). Any layer can be anything; the dice are the seed.
    Zero-mean each; global residue is the final fixer's job."""
    import numpy as np
    from scipy.ndimage import gaussian_filter as _gf
    rng = np.random.default_rng(seed*7919 + 13)
    yy, xx = np.mgrid[0:h, 0:w]
    L = max(h, w)
    fields = []
    for i in range(3):
        corr = float(L/np.exp(rng.uniform(np.log(3.5), np.log(12.0))))
        amp  = float(rng.uniform(0.007, 0.011))
        rad  = float(rng.uniform(0.005, 0.010))
        cx = w*(0.5 + float(rng.uniform(-0.10, 0.10)))
        cy = h*(0.5 + float(rng.uniform(-0.10, 0.10)))
        R = np.sqrt(((xx-cx)/(w/2))**2 + ((yy-cy)/(h/2))**2)/np.sqrt(2)
        n = rng.normal(0, 1, (h, w))
        n = _gf(n, corr); n /= max(n.std(), 1e-6)
        f = -rad*R + amp*n
        f -= f.mean()
        fields.append(np.clip(1.0 + f, 0.972, 1.033))
    return fields

def _dev_kinetic(light, st, um, rng, gain, ms, gs):
    import numpy as np
    from scipy.ndimage import gaussian_filter as _gf
    i = _CALL[0] % 3
    tau = _TAUS[i]; F = _FIELDS[i]; bed = _BEDS[i]; _CALL[0] += 1
    soft = _gf(light, sigma=st.film_mtf_um*ms/um)
    H = np.log10(np.maximum(soft*(st.iso/100.0)*gain, 1e-8)); Hm = np.log10(0.18)
    tau_xy = tau*(F if F is not None else 1.0)
    if bed is None:
        bed = [("quartz", 0.72) + MINERALS["quartz"][1:],
               ("fire opal", 0.28) + MINERALS["fire opal"][1:]]
    dev = 0.0
    for name, frac, size_um, speed, dev_rate, glint, contrast in bed:
        size = size_um*gs
        spread = np.where(H < Hm, 0.58, 1.40)/contrast
        p = np.clip(st.toe + (1-st.toe)*(0.5*(1 + erf(
            (H - Hm + np.log10(speed))/(spread*np.sqrt(2))))), 0, 1)
        p = 1.0 - np.power(1.0 - p, np.clip(dev_rate*tau_xy, 0.5, 2.5))
        r = np.clip((p - 0.04)/0.55, 0, 1)**0.7          # crystal resolve
        area = np.pi*(size/2)**2*np.exp(2*st.crystal_sigma**2)
        n = max((um**2)*0.40*frac/area, 6.0)
        pop = rng.binomial(int(round(n)), p)/round(n)
        s0 = max(1.6*size/um, 0.4)*0.5
        pe = r*_gf(pop, s0) + (1-r)*_gf(pop, s0*2.6)
        amp = np.clip(0.72*glint*(0.94 + 0.06*tau), 0, 1)
        dev = dev + frac*(p + (pe - p)*amp*(0.72 + 0.45*r))
    return np.clip(dev, 0, 1)
E._develop_layer = _dev_kinetic

def _meter(lin):
    """Exposure-only development metering. Color correction now lives in
    the FINAL FIXER, measured on the developed print itself."""
    import numpy as np
    lum = lin.mean(-1)
    med = float(np.median(lum[lum > 0.01]))
    ev = float(np.clip(np.log2(0.16/med), -2.5, 3.0))
    exc = max(ev - 0.6, 0.0) - max(-ev - 1.3, 0.0)
    t = float(np.clip(1.0 + 0.08*exc, 0.93, 1.14))
    return [round(t, 3)]*3

def _final_fix(out):
    """THE FINAL FIXER: color trim measured on the developed print.
    Neutral witness + brightness gate + dead zone; density-neutral gains.
    Fires only when the print itself testifies to a cast."""
    import numpy as np
    lum = out.mean(-1); sat = out.max(-1) - out.min(-1)
    neutral = (lum > 0.10) & (lum < 0.75) & (sat < 0.10*np.maximum(lum, 1e-6) + 0.03)
    med = float(np.median(lum[lum > 0.02]))
    wcol = float(np.clip(1.0 - (med - 0.16)*4.0, 0.0, 1.0))
    if neutral.sum() < 400 or wcol <= 0:
        return out
    m = np.maximum(np.array([np.median(out[..., c][neutral]) for c in range(3)]), 1e-5)
    dv = m/m.mean() - 1.0
    dvx = np.sign(dv)*np.maximum(np.abs(dv) - 0.05, 0)
    g = np.clip((1.0 + dvx)**(-0.55*wcol), 0.955, 1.045)
    g = g/g.mean()
    return np.clip(out*g[None, None, :], 0, 1)

def _dodge(pos, strength=0.25):
    if strength <= 0: return pos
    lum = pos.mean(-1)
    mask = np.clip(1.0 - lum*3.0, 0, 1)**1.5
    mask = gaussian_filter(mask, pos.shape[1]/9.0)
    lift = 1.0/(1.0 + strength*mask)
    return np.clip(pos**lift[..., None], 0, 1)

def bake(jpg_bytes, w, t, secs):
    """PRINTER'S EASEL: density-neutral trim on a finished print.
    w = VIBRANCE fraction (+-0.50 app-side): chroma scaled around luminance,
        weighted toward quiet colors; luminance untouched.
    t = tint (G vs R+B, +-0.40): per-channel gains, mean exactly 1.0."""
    im = Image.open(io.BytesIO(bytes(jpg_bytes))).convert("RGB")
    arr = np.array(im); im.close()
    lin = E.srgb_to_linear(arr)
    g = np.array([1.0 - t/3.0, 1.0 + 2.0*t/3.0, 1.0 - t/3.0])
    out = np.clip(lin*g[None, None, :], 0.0, 1.0)
    if abs(w) > 1e-6:
        Y = (out * np.array([0.2126, 0.7152, 0.0722])).sum(-1, keepdims=True)
        mx = out.max(-1, keepdims=True); mn = out.min(-1, keepdims=True)
        sat = np.where(mx > 1e-4, (mx - mn)/np.maximum(mx, 1e-4), 0.0)
        k = 1.0 + w*(1.0 - sat)
        out = np.clip(Y + (out - Y)*k, 0.0, 1.0)
    img = Image.fromarray((E.linear_to_srgb(out)*255).astype(np.uint8))
    buf = io.BytesIO()
    try:
        ex = Image.Exif()
        ex[0x010F] = "EMULSIFY"
        ex[0x0110] = "HONEY 70 - 222"
        ex[0x0131] = "EMULSIFY LAB"
        ex[0x8827] = 222
        ex[0x829A] = (int(secs) or 1, 1)
        img.save(buf, "JPEG", quality=93, exif=ex)
    except Exception:
        buf = io.BytesIO(); img.save(buf, "JPEG", quality=93)
    del arr, lin, out, img
    gc.collect()
    return {"jpg": buf.getvalue()}

def develop(neg_bytes, profile, seed, long_edge=LONG_EDGE):
    import time as _t
    _t0 = _t.time()
    src = ImageOps.exif_transpose(Image.open(io.BytesIO(bytes(neg_bytes)))).convert("RGB")
    long_edge = int(long_edge)
    if src.width >= src.height:
        w = long_edge; h = round(src.height*long_edge/src.width)
    else:
        h = long_edge; w = round(src.width*long_edge/src.height)
    arr = np.array(src.resize((w, h), Image.LANCZOS)); src.close()
    _FIELDS[:] = _make_fields(arr.shape[0], arr.shape[1], int(seed))
    _BEDS[:] = _draw_beds(int(seed))
    if profile == "scope":
        light = unrender(arr)
        _TAUS[:] = _meter(np.clip(light, 0, 1)); _CALL[0] = 0
        out = SCOPE70_CANON(light, seed=int(seed))
    else:
        lin = E.srgb_to_linear(arr)
        _TAUS[:] = _meter(lin); _CALL[0] = 0
        out = HONEY70_CANON(_expand(lin), seed=int(seed))
    out = _final_fix(out)
    out = _dodge(out, 0.25)
    img = Image.fromarray((E.linear_to_srgb(out)*255).astype(np.uint8))
    secs = int(round(_t.time() - _t0)) or 1
    buf = io.BytesIO()
    try:
        ex = Image.Exif()
        ex[0x010F] = "EMULSIFY"                 # Make
        ex[0x0110] = "HONEY 70 - 222"           # Model
        ex[0x0131] = "EMULSIFY LAB"             # Software
        ex[0x8827] = 222                        # ISO (film speed)
        ex[0x829A] = (secs, 1)                  # ExposureTime = develop time
        img.save(buf, "JPEG", quality=93, exif=ex)
    except Exception:
        buf = io.BytesIO(); img.save(buf, "JPEG", quality=93)
    del arr, out, img
    gc.collect()
    return {"jpg": buf.getvalue(), "secs": secs}


# ---- ADDENDUM v1.3: paper pre-flash (owner-called, 2026-08-18) ----
# Shadows were crushing to paper black; the darkroom answer is to pre-flash
# the paper. Below linear 0.04 (~22% gray) the print rises on a C1-smooth,
# monotone toe: black lands at #141414 (FLASH 2). Above the join: untouched,
# byte for byte. Canon above this line: FROZEN.
_canon_dodge_v12 = _dodge
_FLASH_A, _FLASH_T = 0.007, 0.04
# SANDWICH constants (owner-picked 80%): weight space, donor mapping, gate
_SW_ST, _SW_SW, _SW_TUP, _SW_GD, _SW_GATE = 0.32, 0.07, 0.10, 0.75, 0.06
_SW_GK, _SW_GLO, _SW_GHI = 1.7, 0.45, 2.3   # luminance-coupled grain
def _dodge(pos, strength=0.25):
    out = _canon_dodge_v12(pos, strength)
    m = out < _FLASH_T
    d = 1.0 - out[m] / _FLASH_T
    out[m] = out[m] + _FLASH_A * d * d
    out = np.clip(out, 0.0, 1.0)
    try:
        B = _BASE[0]
        if B is None: return out
        H, W = out.shape[:2]
        Lb = np.repeat(np.repeat(B, 2, 0), 2, 1)[:H, :W].astype(np.float64)
        WY = np.array([0.2126, 0.7152, 0.0722])
        Yp = (out * WY).sum(-1); Yb = (Lb * WY).sum(-1)
        w = (_SW_ST * np.clip(1 - Yb / _SW_SW, 0, 1) ** 1.5
             * np.clip((_SW_GATE - Yp) / _SW_GATE + 0.3, 0, 1))
        if not (w > 1e-4).any(): return out
        dY = _FLASH_A + (_SW_TUP - _FLASH_A) * np.power(np.clip(Yb / _SW_SW, 0, 1), _SW_GD)
        donor = (Lb / np.maximum(Yb, 1e-6)[..., None]) * dY[..., None]
        Psm = _gblur(out, (1.1, 1.1, 0))          # smooth tone of the print
        Ysm = _gblur(Yp, 1.1)
        g = np.clip(np.power(np.clip(Yp, 1e-5, None) / np.maximum(Ysm, 3e-3),
                             _SW_GK), _SW_GLO, _SW_GHI)
        tone = Psm * (1 - w[..., None]) + donor * w[..., None]
        laced = tone * g[..., None]
        out = np.where(w[..., None] > 1e-4, np.clip(laced, 0, 1), out)
        del Lb, donor, Psm, grain, tone
    except Exception:
        pass
    return out

# ---- ADDENDUM v1.4: the tray watches the bath (owner-called) ----
# Two read-only snapshots at real pipeline moments. Snapshot math touches
# nothing the chemistry uses; purity is regression-proven (seed-99 hash
# identical with the watcher forced on). Canon above: FROZEN.
import base64 as _b64
_DC_INNER = [False]
from scipy.ndimage import gaussian_filter as _gblur
_BASE = [None]                          # half-res float32 copy of the negative
_canon_meter_v17 = _meter
def _meter(lin):
    try:
        _BASE[0] = lin[::2, ::2].astype(np.float32)
    except Exception:
        _BASE[0] = None
    return _canon_meter_v17(lin)
def _post_stage(tag, arr8):
    if _DC_INNER[0]:
        return
    try:
        import js
        b = io.BytesIO(); Image.fromarray(arr8).save(b, "JPEG", quality=70)
        js.postStage(tag, _b64.b64encode(b.getvalue()).decode())
    except Exception:
        pass
def _stage_thumb(a):
    h, w = a.shape[:2]; sc = 140.0 / max(h, w)
    im = Image.fromarray((np.clip(a, 0, 1) * 255).astype(np.uint8))
    return np.array(im.resize((max(1, int(w * sc)), max(1, int(h * sc))),
                              Image.BILINEAR))
_EV_BIAS = 0.0
_canon_emulsify2_v14 = E.emulsify2
def _emulsify2_watched(lit, st, **kw):
    try:
        b = float(globals().get("_EV_BIAS", 0.0) or 0.0)
        if b: kw["exposure_ev"] = kw.get("exposure_ev", 0.0) + b
    except Exception:
        pass
    try:                                  # the developer hits the film:
        expo = np.clip(lit / max(float(np.percentile(lit, 99.0)), 1e-6), 0, 1) ** 0.45
        neg = (1.0 - expo) * np.array([1.00, 0.62, 0.36])   # orange-masked negative
        _post_stage("neg", _stage_thumb(neg))
    except Exception:
        pass
    return _canon_emulsify2_v14(lit, st, **kw)
E.emulsify2 = _emulsify2_watched


# ---- ADDENDUM v2.2: DUAL-COAT (owner-called; fast + slow sublayers) ----
# Per record: two contributions = six layers total. The fast sublayer is
# matched onto the slow one's gray axis before blending, because unmatched
# sublayers give shadows a color cast — the crossover error real film
# manufacturers spend their lives avoiding. Falls back to the single-coat
# print if anything at all goes wrong. Canon: FROZEN.
_DC_ON = True
_DC_EV, _DC_RATIO, _DC_SEED = 1.2, 0.56, 4242
_DC_XO = (0.055, 0.050, 0.045)          # R sits lowest in the pack, crosses last
_DC_SHARE = 0.55
_canon_develop_v22 = develop
def develop(neg_bytes, profile, seed, long_edge=LONG_EDGE):
    if not _DC_ON:
        return _canon_develop_v22(neg_bytes, profile, seed, long_edge)
    cap = {}
    _d0 = globals()["_dodge"]                # keep the slow print in linear
    def _cap(pos, strength=0.25):            # light: no extra JPEG generation
        r = _d0(pos, strength)
        cap["lin"] = np.asarray(r, dtype=np.float32)
        return r
    globals()["_dodge"] = _cap
    try:
        slow = _canon_develop_v22(neg_bytes, profile, seed, long_edge)
    finally:
        globals()["_dodge"] = _d0
    ev0 = float(globals().get("_EV_BIAS", 0.0) or 0.0)
    try:
        globals()["_EV_BIAS"] = ev0 + _DC_EV
        _DC_INNER[0] = True
        fsize = max(200, int(round(int(long_edge) * _DC_RATIO)))
        fseed = (int(seed) * 7 + _DC_SEED) % 9000 + 1
        fast = _canon_develop_v22(neg_bytes, profile, fseed, fsize)
    except Exception:
        return slow
    finally:
        _DC_INNER[0] = False
        globals()["_EV_BIAS"] = ev0
    try:
        Ls = cap.get("lin")
        if Ls is None:
            return slow
        Ls = np.asarray(Ls, dtype=np.float64)
        cap.clear()
        fim = Image.open(io.BytesIO(fast["jpg"])).convert("RGB").resize(
              (Ls.shape[1], Ls.shape[0]), Image.BICUBIC)
        Lf = E.srgb_to_linear(np.array(fim))
        fim.close()
        m = Ls.mean(-1)
        mid = (m > 0.05) & (m < 0.40)
        if int(mid.sum()) > 256:                 # match the gray axis
            for c in range(3):
                d = float(Lf[..., c][mid].mean())
                if d > 1e-6:
                    Lf[..., c] *= float(Ls[..., c][mid].mean()) / d
        for c in range(3):                       # the fast sublayer's share
            u = np.clip(Ls[..., c] / _DC_XO[c], 0.0, 1.0)
            wf = (1.0 - u*u*(3.0 - 2.0*u)) * _DC_SHARE
            Ls[..., c] = Lf[..., c]*wf + Ls[..., c]*(1.0 - wf)
        img = Image.fromarray((E.linear_to_srgb(np.clip(Ls, 0, 1))*255).astype(np.uint8))
        del Lf, m, mid
        secs = int(slow.get("secs", 1)) + int(fast.get("secs", 0)) or 1
        buf = io.BytesIO()
        try:
            ex = Image.Exif()
            ex[0x010F] = "EMULSIFY"
            ex[0x0110] = "HONEY 70 - 222"
            ex[0x0131] = "EMULSIFY LAB"
            ex[0x8827] = 222
            ex[0x829A] = (secs, 1)
            img.save(buf, "JPEG", quality=93, exif=ex)
        except Exception:
            buf = io.BytesIO(); img.save(buf, "JPEG", quality=93)
        del Ls, img
        gc.collect()
        return {"jpg": buf.getvalue(), "secs": secs}
    except Exception:
        gc.collect()
        return slow
`);
  develop = pyodide.globals.get("develop");
  bakePy = pyodide.globals.get("bake");
  postMessage({ ready: true });
})();

let CURJOB = null;
self.postStage = (tag, b64) => {
  try { postMessage({ id: CURJOB, stage: tag, b64 }); } catch (err) {}
};
onmessage = async (e) => {
  const { id, neg, profile, seed, size, bake, jpg, w, t, secs } = e.data;
  try {
    await boot;
    if (bake) {
      const r = bakePy(new Uint8Array(jpg), w, t, secs || 1);
      const obj = r.toJs({ dict_converter: Object.fromEntries });
      r.destroy();
      const bytes = obj.jpg instanceof Uint8Array ? obj.jpg : new Uint8Array(obj.jpg);
      postMessage({ id, ok: true, result: bytes }, [bytes.buffer]);
      return;
    }
    CURJOB = id;
    pyodide.globals.set("_EV_BIAS", e.data.ev || 0);
    const result = develop(new Uint8Array(neg), profile, seed, size || 1100);
    const obj = result.toJs({ dict_converter: Object.fromEntries });
    result.destroy();
    const bytes = obj.jpg instanceof Uint8Array ? obj.jpg : new Uint8Array(obj.jpg);
    postMessage({ id, ok: true, result: bytes, secs: obj.secs }, [bytes.buffer]);
  } catch (err) {
    postMessage({ id, ok: false, error: String(err) });
  }
};
