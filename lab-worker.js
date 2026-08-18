// lab-worker.js — v1.1. Verbatim canon; smaller develop size + JPEG prints
// + garbage collection to keep iOS Safari happy.

importScripts("https://cdn.jsdelivr.net/pyodide/v0.26.1/full/pyodide.js");

let pyodide = null, develop = null;

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

LONG_EDGE = 1100   # phone-friendly memory + speed; the look holds

# ---- KINETIC STABILIZER (documented addendum to the frozen canon) ----
# The negative meters its own development: each layer's rate leans gently
# against exposure error and color cast (max ~ +/-6% color, +/-15% time).
# Deterministic — driven only by the image. Rescued frames carry a trace
# of push character, as real rescued rolls did.
_TAUS = [1.0, 1.0, 1.0]; _CALL = [0]; _FIELDS = [None, None, None]

def _make_fields(h, w, seed):
    """LIVING DEVELOPMENT: each layer develops in its own zero-mean weather
    (offset development center + organic drift). Spatial variation only —
    zero-mean by construction, so it can never introduce a color cast.
    Deterministic per seed."""
    import numpy as np
    from scipy.ndimage import gaussian_filter as _gf
    rng = np.random.default_rng(seed*7919 + 13)
    yy, xx = np.mgrid[0:h, 0:w]
    fields = []
    for i in range(3):
        cx = w*(0.5 + float(rng.uniform(-0.07, 0.07)))
        cy = h*(0.5 + float(rng.uniform(-0.07, 0.07)))
        R = np.sqrt(((xx-cx)/(w/2))**2 + ((yy-cy)/(h/2))**2)/np.sqrt(2)
        n = rng.normal(0, 1, (h, w))
        n = _gf(n, max(w, h)/6.0); n /= max(n.std(), 1e-6)
        f = -0.014*R + 0.010*n
        f -= f.mean()
        fields.append(np.clip(1.0 + f, 0.97, 1.035))
    return fields

def _dev_kinetic(light, st, um, rng, gain, ms, gs):
    import numpy as np
    from scipy.ndimage import gaussian_filter as _gf
    i = _CALL[0] % 3
    tau = _TAUS[i]; F = _FIELDS[i]; _CALL[0] += 1
    soft = _gf(light, sigma=st.film_mtf_um*ms/um)
    H = np.log10(np.maximum(soft*(st.iso/100.0)*gain, 1e-8)); Hm = np.log10(0.18)
    spread = np.where(H < Hm, 0.58, 1.40)
    p = np.clip(st.toe + (1-st.toe)*(0.5*(1+erf((H-Hm)/(spread*np.sqrt(2))))), 0, 1)
    tau_xy = tau*(F if F is not None else 1.0)
    p = 1.0 - np.power(1.0 - p, tau_xy)          # living kinetics
    r = np.clip((p - 0.04)/0.55, 0, 1)**0.7      # crystal resolve: dev completeness
    dev = 0.0
    for size, frac, amp in ((st.crystal_fine_um*gs, 1-st.coarse_frac, 0.85),
                            (st.crystal_coarse_um*gs, st.coarse_frac, 0.55)):
        area = np.pi*(size/2)**2*np.exp(2*st.crystal_sigma**2)
        n = max((um**2)*0.40*frac/area, 6.0)
        pop = rng.binomial(int(round(n)), p)/round(n)
        s0 = max(1.6*size/um, 0.4)*0.5
        pe = r*_gf(pop, s0) + (1-r)*_gf(pop, s0*2.6)   # resolved=crisp, thin=mushy
        dev = dev + frac*(p + (pe-p)*amp*(0.94 + 0.06*tau)*(0.72 + 0.45*r))
    return np.clip(dev, 0, 1)
E._develop_layer = _dev_kinetic

def _meter(lin):
    import numpy as np
    lum = lin.mean(-1)
    sat = lin.max(-1) - lin.min(-1)
    # casts are read from NEAR-NEUTRAL midtones only; saturated content
    # (grass, sky, fabric) never counts as a cast
    neutral = (lum > 0.03) & (lum < 0.6) & (sat < 0.10*np.maximum(lum, 1e-6) + 0.03)
    mid = neutral
    if mid.sum() < 400:
        mid = (lum > 0.03) & (lum < 0.6)
        if mid.sum() < 500: return [1.0, 1.0, 1.0]
        # no neutral witness: exposure correction only
        med = float(np.median(lum[lum > 0.01]))
        ev = float(np.clip(np.log2(0.16/med), -2.5, 3.0))
        exc = max(ev - 0.6, 0.0) - max(-ev - 1.3, 0.0)
        t = float(np.clip(1.0 + 0.08*exc, 0.93, 1.14))
        return [round(t, 3)]*3
    m = np.maximum(np.array([np.median(lin[..., c][mid]) for c in range(3)]), 1e-5)
    med = float(np.median(lum[lum > 0.01]))
    ev = float(np.clip(np.log2(0.16/med), -2.5, 3.0))
    # dead zones: rescue engages past +0.6 stop under; pulls only past 1.3 over.
    # a fine frame gets tau = 1.0 exactly — canon, untouched.
    exc = max(ev - 0.6, 0.0) - max(-ev - 1.3, 0.0)
    t_exp = np.clip(1.0 + 0.08*exc, 0.93, 1.14)
    # cast vs content: zero color correction in bright scenes, and
    # sub-6% channel deviation is scene, not cast.
    wcol = float(np.clip(1.0 - (med - 0.12)*5.0, 0.0, 1.0))
    dev = m/m.mean() - 1.0
    devx = np.sign(dev)*np.maximum(np.abs(dev) - 0.06, 0)
    t_col = np.clip((1.0 + devx)**(-0.12*wcol), 0.94, 1.06)
    return [float(x) for x in np.round(t_exp*t_col, 3)]

def _dodge(pos, strength=0.25):
    if strength <= 0: return pos
    lum = pos.mean(-1)
    mask = np.clip(1.0 - lum*3.0, 0, 1)**1.5
    mask = gaussian_filter(mask, pos.shape[1]/9.0)
    lift = 1.0/(1.0 + strength*mask)
    return np.clip(pos**lift[..., None], 0, 1)

def develop(neg_bytes, profile, seed):
    import time as _t
    _t0 = _t.time()
    src = ImageOps.exif_transpose(Image.open(io.BytesIO(bytes(neg_bytes)))).convert("RGB")
    if src.width >= src.height:
        w = LONG_EDGE; h = round(src.height*LONG_EDGE/src.width)
    else:
        h = LONG_EDGE; w = round(src.width*LONG_EDGE/src.height)
    arr = np.array(src.resize((w, h), Image.LANCZOS)); src.close()
    _FIELDS[:] = _make_fields(arr.shape[0], arr.shape[1], int(seed))
    if profile == "scope":
        light = unrender(arr)
        _TAUS[:] = _meter(np.clip(light, 0, 1)); _CALL[0] = 0
        out = SCOPE70_CANON(light, seed=int(seed))
    else:
        lin = E.srgb_to_linear(arr)
        _TAUS[:] = _meter(lin); _CALL[0] = 0
        out = HONEY70_CANON(lin, seed=int(seed))
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
`);
  develop = pyodide.globals.get("develop");
  postMessage({ ready: true });
})();

onmessage = async (e) => {
  const { id, neg, profile, seed } = e.data;
  try {
    await boot;
    const result = develop(new Uint8Array(neg), profile, seed);
    const obj = result.toJs({ dict_converter: Object.fromEntries });
    result.destroy();
    const bytes = obj.jpg instanceof Uint8Array ? obj.jpg : new Uint8Array(obj.jpg);
    postMessage({ id, ok: true, result: bytes, secs: obj.secs }, [bytes.buffer]);
  } catch (err) {
    postMessage({ id, ok: false, error: String(err) });
  }
};
