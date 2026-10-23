"""gpulab.py - THE GPU LAB (kit 7). The same lab, the same Python, run on the 4090 through CuPy.

The lab is written against numpy and scipy.ndimage. CuPy is numpy's twin on the GPU, so the lab is loaded with
`numpy` resolving to a shim that hands everything to CuPy except the parts that must stay on the CPU:

  - the dice. Every seeded draw (default_rng, RandomState, Generator(Philox)) runs on numpy's generators, exactly as
    on the phone, and the numbers are moved to the GPU afterwards. CuPy's generators are different generators;
    the grain would be different grain.
  - the edges. PIL images become GPU arrays on the way in; GPU arrays come back to the CPU for Image.fromarray.

Nothing in the lab's source changes. Whether the result is the lab is decided by the same gate as any other
machine: the golden chart developed here must sit within float noise of the reference print.

    make_lab(lab_dir)      -> the lab namespace on the GPU (raises if CuPy or the GPU is missing)
    make_lab(lab_dir, backend=(numpy, scipy)) -> the same shim over numpy itself: proves the plumbing without a GPU
"""
import sys, types, os, importlib

def _rng_proxy(gen, cp, np):
    """numpy's generator, its arrays delivered as GPU arrays"""
    class P:
        def __init__(self, g): self._g = g
        def __getattr__(self, name):
            f = getattr(self._g, name)
            if not callable(f): return f
            def call(*a, **k):
                r = f(*a, **k)
                return cp.asarray(r) if isinstance(r, np.ndarray) else r
            return call
    return P(gen)

def make_lab(lab_dir, backend=None):
    import numpy as np, scipy.ndimage, scipy.special
    from PIL import Image
    if backend is None:
        import cupy as cp, cupyx.scipy.ndimage as cnd, cupyx.scipy.special as csp
        cp.cuda.Device(0).use()
    else:
        cp, sci = backend; cnd, csp = sci.ndimage, sci.special          # the shim over numpy itself: a plumbing test
    is_gpu = lambda o: isinstance(o, cp.ndarray)

    # ---- numpy, as the lab sees it
    gnp = types.ModuleType("numpy")
    def _conv(o):
        if is_gpu(o) or isinstance(o, (int, float, bool, complex)) or o is None: return o
        if isinstance(o, np.ndarray) or hasattr(o, "__array_interface__") or isinstance(o, Image.Image): return cp.asarray(np.asarray(o))
        if isinstance(o, (list, tuple)) and o and any(is_gpu(x) for x in o): return cp.stack([cp.asarray(x) for x in o]) if all(getattr(x, "shape", None) == getattr(o[0], "shape", None) for x in o) else o
        return o
    def array(o, *a, **k): return cp.array(_conv(o), *a, **k)
    def asarray(o, *a, **k): return cp.asarray(_conv(o), *a, **k)
    gnp.array = array; gnp.asarray = asarray
    gnp.ndarray = cp.ndarray
    rnd = types.ModuleType("numpy.random")
    rnd.default_rng = lambda *a, **k: _rng_proxy(np.random.default_rng(*a, **k), cp, np)
    rnd.RandomState = lambda *a, **k: _rng_proxy(np.random.RandomState(*a, **k), cp, np)
    rnd.Generator = lambda bitgen: _rng_proxy(np.random.Generator(bitgen), cp, np)
    for name in ("Philox", "PCG64", "MT19937", "SFC64", "SeedSequence"): setattr(rnd, name, getattr(np.random, name))
    gnp.random = rnd
    def __getattr__(name):
        if hasattr(cp, name): return getattr(cp, name)
        return getattr(np, name)                                       # dtypes and the odd helper CuPy lacks
    gnp.__getattr__ = __getattr__

    # ---- PIL takes GPU arrays back to the CPU
    _fromarray = Image.fromarray
    def fromarray(obj, *a, **k): return _fromarray(obj.get() if (is_gpu(obj) and hasattr(obj, "get")) else obj, *a, **k)

    # ---- load the lab with numpy and scipy.ndimage pointing at the GPU
    sys.path.insert(0, lab_dir); cwd = os.getcwd(); os.chdir(lab_dir)
    import golden                                                       # on real numpy: its chart() and pixels() stay CPU
    saved = {k: sys.modules.get(k) for k in ("numpy", "scipy.ndimage", "scipy.special")}
    for m in ("emulsify2", "honey_sr", "canon_profiles"): sys.modules.pop(m, None)   # they must import the shim, not a cached CPU copy
    try:
        sys.modules["numpy"] = gnp; sys.modules["scipy.ndimage"] = cnd; sys.modules["scipy.special"] = csp
        Image.fromarray = fromarray
        ns = golden.harness(os.path.join(lab_dir, "lab-worker.js"))
    finally:
        for k, v in saved.items():
            if v is not None: sys.modules[k] = v
        os.chdir(cwd)
    # the lab keeps the shimmed modules in its own globals; PIL stays patched (the lab's prints come off the GPU)
    ns["__gpu__"] = backend is None
    ns["__cp__"] = cp
    return ns

def device_name():
    try:
        import cupy as cp
        p = cp.cuda.runtime.getDeviceProperties(0); return p["name"].decode() if isinstance(p["name"], bytes) else str(p["name"])
    except Exception as e:
        return "no GPU: %s" % e
