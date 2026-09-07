"""bandcheck.py - the fifth ritual, for the banding rewrite.

Banding is only safe if a strip of the picture develops to exactly the same
pixels as the whole picture would. Three things can break that, and this
harness finds each of them before a stage is converted:

  1. REACH.   Any blur reads pixels outside the strip. Too little overlap and
              the seam shows. This measures the overlap each sigma needs.
  2. GLOBALS. A stage that reads the whole frame (a mean, a median, the neutral
              search) cannot see it from inside a strip. Those must be computed
              once, before banding, and passed in.
  3. NOISE.   Grain drawn from a running generator depends on how many numbers
              were drawn before it, so a strip and a frame disagree. Noise must
              become a function of POSITION, not of call order.

Usage:  python3 bandcheck.py            - run the whole suite
        band(fn, arr, h, ov)            - apply fn in strips, return the result
"""
import numpy as np
from scipy.ndimage import gaussian_filter

TOL = 0.0            # exact is the standard; anything else is a seam waiting


def band(fn, arr, strip_h, overlap):
    """Apply fn in horizontal strips with overlap, keeping only the valid middle."""
    H = arr.shape[0]
    out = np.empty_like(arr)
    y = 0
    while y < H:
        y1 = min(H, y + strip_h)
        a = max(0, y - overlap)
        b = min(H, y1 + overlap)
        piece = fn(arr[a:b])
        out[y:y1] = piece[y - a: y - a + (y1 - y)]
        y = y1
    return out


def report(name, whole, banded):
    d = np.abs(whole - banded)
    worst_row = int(np.argmax(d.max(axis=tuple(range(1, d.ndim)))))
    ok = d.max() <= TOL
    print(f"  {'PASS' if ok else 'FAIL'}  {name:44s} max diff {d.max():.3e}"
          + ("" if ok else f"   worst at row {worst_row}"))
    return ok


def suite():
    rng = np.random.default_rng(4)
    a = rng.random((1100, 880, 3))
    print("1. REACH - how much overlap each blur in the pipeline needs")
    # scipy's gaussian_filter reads out to truncate*sigma (default 4.0)
    for sigma, what in ((2.2, "grain reference (emulsify2:139)"),
                        (9.0, "glow (emulsify2:151)"),
                        (14.0 / (70000.0 / 1100), "DIR adjacency at 1100px"),
                        (45.0 / (70000.0 / 1100), "halation core 45um"),
                        (420.0 / (70000.0 / 1100), "halation tail 420um")):
        need = int(np.ceil(4.0 * sigma)) + 1
        f = lambda x, s=sigma: gaussian_filter(x, (s, s, 0))
        report(f"sigma {sigma:6.2f}  {what:34s} overlap {need:4d}",
               f(a), band(f, a, 256, need))
    print("\n   and what happens with too little overlap:")
    s = 9.0
    f = lambda x: gaussian_filter(x, (s, s, 0))
    for ov in (36, 18, 8, 0):
        d = np.abs(f(a) - band(f, a, 256, ov)).max()
        print(f"     overlap {ov:3d}  max diff {d:.3e}" + ("   <- seam" if d > 0 else "   exact"))

    print("\n2. GLOBALS - a stage that reads the whole frame cannot see it from a strip")
    def with_global_mean(x):
        return x / max(x.mean(), 1e-6)
    report("normalising by the frame mean", with_global_mean(a), band(with_global_mean, a, 256, 0))
    m = a.mean()
    def with_passed_mean(x, m=m):
        return x / max(m, 1e-6)
    report("the same, with the mean computed once and passed in",
           with_passed_mean(a), band(with_passed_mean, a, 256, 0))

    print("\n3. NOISE - order-dependent vs position-dependent")
    def running_noise(x):
        r = np.random.default_rng(7)
        return x + r.normal(0, 0.01, x.shape)
    report("grain from a running generator", running_noise(a), band(running_noise, a, 256, 0))

    # position-addressed noise: the value at (y,x) depends only on (y,x)
    def positional_noise(x, y0=[0]):
        raise NotImplementedError

    def make_positional(H, W, C, seed):
        """One field, generated once, indexed by absolute position."""
        return np.random.default_rng(seed).normal(0, 0.01, (H, W, C))

    field = make_positional(*a.shape, 7)
    def band_positional(fn, arr, strip_h, overlap, field):
        H = arr.shape[0]; out = np.empty_like(arr); y = 0
        while y < H:
            y1 = min(H, y + strip_h)
            out[y:y1] = arr[y:y1] + field[y:y1]
            y = y1
        return out
    report("grain addressed by position", a + field, band_positional(None, a, 256, 0, field))


if __name__ == "__main__":
    print("BANDCHECK - strip equivalence, the precondition for banding\n")
    suite()
    print("\nStandard: exact. A stage may only be banded once it passes here.")
