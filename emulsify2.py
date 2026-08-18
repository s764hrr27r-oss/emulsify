"""
EMULSIFY v2 — research-informed emulsion engine.

Changes from v1, each tied to a finding:
 1. FOVEON/FILM STACK: three layers with spectral CROSSTALK at exposure
    (overlapping sensitivities), then DIR INTER-IMAGE correction during
    development that re-purifies color — the push-pull that makes film color.
 2. DIR ADJACENCY EFFECT: inhibitor diffuses locally; edges develop harder.
    Film's organic acutance — replaces any digital sharpening.
 3. SUBTRACTIVE DENSITY-SPACE PRINT: negative densities -> transmittance ->
    print stock characteristic curve. Dense blacks, clean whites, no fade.
 4. MULTI-SCALE GRAIN: two crystal populations (fine + coarse clumps).
 5. TWO-COMPONENT HALATION: tight intense core + long faint tail, red-orange.
 6. No baked-in vintage fade. 'Look' is now a thin parameter layer on a
    physically dense image.
"""

import numpy as np
from scipy.ndimage import gaussian_filter
from scipy.special import erf


GAUGE_WIDTH_MM = {8: 4.8, 16: 10.26, 35: 22.0}


class Stock2:
    def __init__(self, iso=250, gauge_mm=16,
                 crystal_fine_um=0.55, crystal_coarse_um=1.6, coarse_frac=0.30,
                 crystal_sigma=0.40, film_mtf_um=5.5, toe=0.05,
                 neg_gamma=0.62, dmax=2.6,
                 # DIR coupler strengths
                 interimage=0.42, adjacency=0.45, adjacency_um=14.0,
                 # halation
                 hal_thresh=0.65, hal_core=0.55, hal_tail=0.30,
                 hal_core_um=45.0, hal_tail_um=420.0,
                 # print stock
                 print_gamma=2.05, print_dmax=2.35):
        for k, v in locals().items():
            if k != "self":
                setattr(self, k, v)


def srgb_to_linear(x):
    x = x.astype(np.float64) / 255.0 if x.dtype == np.uint8 else x.astype(np.float64)
    return np.where(x <= 0.04045, x / 12.92, ((x + 0.055) / 1.055) ** 2.4)


def linear_to_srgb(x):
    x = np.clip(x, 0, 1)
    return np.where(x <= 0.0031308, x * 12.92, 1.055 * x ** (1 / 2.4) - 0.055)


# Spectral crosstalk (rows = layers R,G,B; cols = light R,G,B).
# Film layers have overlapping sensitivities (like Foveon silicon depth
# separation). DIR inter-image later corrects this — the correction is what
# creates film's characteristic color separation.
XTALK = np.array([[0.88, 0.09, 0.03],
                  [0.07, 0.86, 0.07],
                  [0.03, 0.10, 0.87]])


def _develop_layer(light, st, um_per_px, rng, iso_gain, mtf_scale, gscale):
    """Expose + develop one layer with two crystal populations."""
    light_soft = gaussian_filter(light, sigma=st.film_mtf_um * mtf_scale / um_per_px)

    H = np.log10(np.maximum(light_soft * (st.iso / 100.0) * iso_gain, 1e-8))
    Hm = np.log10(0.18)
    spread = np.where(H < Hm, 0.58, 1.40)
    p = 0.5 * (1 + erf((H - Hm) / (spread * np.sqrt(2))))
    p = st.toe + (1 - st.toe) * p
    p = np.clip(p, 0, 1)

    # dye clouds are partial-opacity: grain noise contrast < binary silver
    dev = 0.0
    for size_um, frac, amp in (
            (st.crystal_fine_um * gscale, 1 - st.coarse_frac, 0.85),
            (st.crystal_coarse_um * gscale, st.coarse_frac, 0.55)):
        area = np.pi * (size_um / 2) ** 2 * np.exp(2 * st.crystal_sigma ** 2)
        n = max((um_per_px ** 2) * 0.40 * frac / area, 6.0)
        pop = rng.binomial(int(round(n)), p) / round(n)
        clump_px = max(1.6 * size_um / um_per_px, 0.4)
        pop = gaussian_filter(pop, clump_px * 0.5)
        dev = dev + frac * (p + (pop - p) * amp)   # scaled grain around mean
    return np.clip(dev, 0, 1)


def emulsify2(rgb_lin, st: Stock2, exposure_ev=0.0, seed=0,
              warmth=0.0, fade=0.0, glow=0.0):
    """Full pipeline. warmth/fade/glow are the thin 'look' layer (0 = neutral)."""
    h, w, _ = rgb_lin.shape
    um_per_px = GAUGE_WIDTH_MM[st.gauge_mm] * 1000.0 / w
    rng = np.random.default_rng(seed)
    light = np.clip(rgb_lin, 0, None) * 2.0 ** exposure_ev

    # ---- HALATION: core + tail bounce into red (and a little green) ----
    lum = light.mean(-1)
    hot = np.maximum(lum - st.hal_thresh, 0)
    core = gaussian_filter(hot, st.hal_core_um / um_per_px)
    tail = gaussian_filter(hot, st.hal_tail_um / um_per_px)
    light = light.copy()
    light[..., 0] += st.hal_core * core + st.hal_tail * tail
    light[..., 1] += 0.35 * (st.hal_core * core + st.hal_tail * tail)

    # ---- EXPOSE through crosstalk, DEVELOP three layers ----
    lr = np.tensordot(light, XTALK.T, axes=1)  # layer exposures
    cfg = [(1.00, 1.20, 1.10),   # RED: deepest, softest, coarser
           (1.06, 1.00, 1.00),   # GREEN: gain bump (cures magenta highlight drift)
           (0.97, 0.90, 0.85)]   # BLUE: top, finest
    dev = np.stack([_develop_layer(lr[..., i], st, um_per_px, rng, g, m, gs)
                    for i, (g, m, gs) in enumerate(cfg)], axis=-1)

    # ---- DIR COUPLER EFFECTS (in developed-fraction space) ----
    adj_px = st.adjacency_um / um_per_px
    dev_s = np.stack([gaussian_filter(dev[..., i], max(adj_px * 0.25, 0.6))
                      for i in range(3)], -1)   # grain-scale reference
    dev_l = np.stack([gaussian_filter(dev[..., i], adj_px) for i in range(3)], -1)
    # adjacency: inhibitor diffuses away from edges -> edges develop harder
    # (band-passed so single-crystal noise isn't amplified)
    dev = dev + st.adjacency * (dev_s - dev_l)
    # inter-image: each layer suppressed by the *others'* local development ->
    # push each layer away from the neutral mean -> saturation & purity
    mean_l = dev_l.mean(-1, keepdims=True)
    dev = dev + st.interimage * (dev_l - mean_l)
    dev = np.clip(dev, 0, 1)

    # ---- NEGATIVE DENSITY -> PRINT (subtractive, density space) ----
    Dneg = st.dmax * dev ** 0.92
    # print exposure through the negative
    logE = -Dneg                       # log10 print exposure (up to constants)
    # print stock characteristic curve: sigmoid in logE, mid anchored so that
    # a mid-gray negative prints to ~0.18 linear
    Dmid = st.dmax * (0.5 ** 0.92)
    x = (logE + Dmid) * st.print_gamma
    Dprint = st.print_dmax / (1.0 + 10.0 ** (-(x + 0.30)))
    positive = 10.0 ** (-Dprint)       # transmittance of the print = image

    # ---- luma-dominant grain: dye-cloud color noise is subtler than
    # silver luminance noise at viewing scale ----
    sig = np.stack([gaussian_filter(positive[..., c], 2.2) for c in range(3)], -1)
    gr = positive - sig
    gl = gr.mean(-1, keepdims=True)
    positive = np.clip(sig + gl + (gr - gl) * 0.30, 0, 1)

    # ---- thin look layer ----
    if warmth:
        positive[..., 0] *= (1 + 0.05 * warmth)
        positive[..., 2] *= (1 - 0.045 * warmth)
    if fade:
        positive = positive * (1 - 0.10 * fade) + 0.045 * fade
    if glow:
        bl = np.stack([gaussian_filter(positive[..., c], 9.0) for c in range(3)], -1)
        positive = positive * (1 - 0.14 * glow) + bl * 0.14 * glow

    # final dye-cloud softness
    clump = max(1.6 * st.crystal_fine_um / um_per_px, 0.45)
    for c in range(3):
        positive[..., c] = gaussian_filter(positive[..., c], clump)
    return np.clip(positive, 0, 1)


# ---- stock presets ----
DAYLIGHT_250_16 = Stock2()
NIGHT_500_16 = Stock2(iso=500, crystal_fine_um=0.7, crystal_coarse_um=2.0,
                      coarse_frac=0.38, film_mtf_um=6.5, toe=0.06,
                      hal_thresh=0.50)
FINE_100_16 = Stock2(iso=100, crystal_fine_um=0.45, crystal_coarse_um=1.2,
                     coarse_frac=0.25, film_mtf_um=4.8)
