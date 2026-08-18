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

LONG_EDGE = 1100   # phone-friendly memory + speed; the look holds

def _dodge(pos, strength=0.25):
    if strength <= 0: return pos
    lum = pos.mean(-1)
    mask = np.clip(1.0 - lum*3.0, 0, 1)**1.5
    mask = gaussian_filter(mask, pos.shape[1]/9.0)
    lift = 1.0/(1.0 + strength*mask)
    return np.clip(pos**lift[..., None], 0, 1)

def develop(neg_bytes, profile, seed):
    src = ImageOps.exif_transpose(Image.open(io.BytesIO(bytes(neg_bytes)))).convert("RGB")
    if src.width >= src.height:
        w = LONG_EDGE; h = round(src.height*LONG_EDGE/src.width)
    else:
        h = LONG_EDGE; w = round(src.width*LONG_EDGE/src.height)
    arr = np.array(src.resize((w, h), Image.LANCZOS)); src.close()
    if profile == "scope":
        out = SCOPE70_CANON(unrender(arr), seed=int(seed))
    else:
        out = HONEY70_CANON(E.srgb_to_linear(arr), seed=int(seed))
    out = _dodge(out, 0.25)
    img = Image.fromarray((E.linear_to_srgb(out)*255).astype(np.uint8))
    buf = io.BytesIO(); img.save(buf, "JPEG", quality=93)
    del arr, out, img
    gc.collect()
    return buf.getvalue()
`);
  develop = pyodide.globals.get("develop");
  postMessage({ ready: true });
})();

onmessage = async (e) => {
  const { id, neg, profile, seed } = e.data;
  try {
    await boot;
    const result = develop(new Uint8Array(neg), profile, seed);
    const bytes = result.toJs();
    result.destroy();
    postMessage({ id, ok: true, result: bytes }, [bytes.buffer]);
  } catch (err) {
    postMessage({ id, ok: false, error: String(err) });
  }
};
