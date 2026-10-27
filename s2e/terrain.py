"""Terrain descriptors, rotation-aware matching and hillshading.

Every terrain patch (a real DEM window or your sculpture) is turned into a
64x64 grid, smoothed, and z-scored (mean 0, std 1). That makes matching
independent of absolute height and vertical exaggeration -- a 10 cm sand hill
can match a 3000 m mountain.

The descriptor is rotation invariant (a sandbox has no "north"):
  * polar rings + FFT magnitude along the angle axis (Fourier-Mellin style)
  * hypsometry (height distribution), slope and curvature histograms,
    all computed inside a circular mask
A second, exact stage (`refine`) tries every rotation of the query against the
shortlisted candidates with normalised cross-correlation and returns the best
angle, which tells you how the sandbox is oriented relative to true north.
"""
import numpy as np
import cv2

PATCH = 64
N_RINGS = 16
N_ANG = 64
N_HARM = 8
NBINS = 16
BLUR_SIGMA = 1.0

_c = (PATCH - 1) / 2.0
_R_MAX = PATCH / 2.0 - 1.0
_yy, _xx = np.mgrid[0:PATCH, 0:PATCH]
MASK = ((_xx - _c) ** 2 + (_yy - _c) ** 2) <= (PATCH / 2.0 - 0.5) ** 2
MASK_FLAT = MASK.ravel()

WEIGHTS = dict(rings=1.0, hyps=0.6, slope=0.5, curv=0.4)
SLOPE_RANGE = (0.0, 0.45)
CURV_RANGE = (-0.06, 0.06)


def _build_polar():
    radii = np.linspace(2.0, _R_MAX, N_RINGS)
    ang = np.linspace(0, 2 * np.pi, N_ANG, endpoint=False)
    rr, aa = np.meshgrid(radii, ang, indexing="ij")
    xs = _c + rr * np.cos(aa)
    ys = _c + rr * np.sin(aa)
    x0 = np.floor(xs).astype(np.int64)
    y0 = np.floor(ys).astype(np.int64)
    fx = (xs - x0).astype(np.float32)
    fy = (ys - y0).astype(np.float32)
    idx = [y0 * PATCH + x0, y0 * PATCH + x0 + 1,
           (y0 + 1) * PATCH + x0, (y0 + 1) * PATCH + x0 + 1]
    w = [(1 - fx) * (1 - fy), fx * (1 - fy), (1 - fx) * fy, fx * fy]
    return [i.ravel() for i in idx], [x.ravel() for x in w]


_PIDX, _PW = _build_polar()


def prep(height):
    """Any square heightmap -> smoothed PATCH x PATCH float32 grid."""
    h = np.asarray(height, np.float32)
    if h.shape != (PATCH, PATCH):
        h = cv2.resize(h, (PATCH, PATCH), interpolation=cv2.INTER_AREA)
    return cv2.GaussianBlur(h, (0, 0), BLUR_SIGMA, borderType=cv2.BORDER_REFLECT)


def zscore(patches):
    """(N,P,P) or (P,P) -> (N,P,P) with mean 0 / std 1 inside the circular mask."""
    p = np.asarray(patches, np.float32)
    if p.ndim == 2:
        p = p[None]
    flat = p.reshape(len(p), -1)
    m = flat[:, MASK_FLAT]
    mu = m.mean(1, keepdims=True)
    sd = m.std(1, keepdims=True)
    return ((flat - mu) / (sd + 1e-6)).reshape(p.shape)


def _hist(v, lo, hi):
    n = v.shape[0]
    b = np.clip(((v - lo) * (NBINS / (hi - lo))).astype(np.int64), 0, NBINS - 1)
    off = (np.arange(n)[:, None] * NBINS + b).ravel()
    h = np.bincount(off, minlength=n * NBINS).reshape(n, NBINS).astype(np.float32)
    return np.sqrt(h / v.shape[1])  # Hellinger mapping


def _l2(x):
    return x / (np.linalg.norm(x, axis=1, keepdims=True) + 1e-9)


def describe(z):
    """z-scored patches (N,P,P) -> L2-normalised rotation-invariant descriptors."""
    z = np.asarray(z, np.float32)
    if z.ndim == 2:
        z = z[None]
    n = len(z)
    flat = z.reshape(n, -1)
    polar = sum(flat[:, i] * w for i, w in zip(_PIDX, _PW)).reshape(n, N_RINGS, N_ANG)
    spec = np.abs(np.fft.rfft(polar, axis=2))[:, :, :N_HARM] / N_ANG
    spec[:, :, 0] = polar.mean(2)  # signed radial profile (peak vs. basin)
    rings = spec.reshape(n, -1)

    gy, gx = np.gradient(z, axis=(1, 2))
    curv = np.gradient(gx, axis=2) + np.gradient(gy, axis=1)
    slope = np.hypot(gx, gy).reshape(n, -1)[:, MASK_FLAT]
    curv = curv.reshape(n, -1)[:, MASK_FLAT]
    hyps = flat[:, MASK_FLAT]

    parts = [
        WEIGHTS["rings"] * _l2(rings),
        WEIGHTS["hyps"] * _l2(_hist(hyps, -2.5, 2.5)),
        WEIGHTS["slope"] * _l2(_hist(slope, *SLOPE_RANGE)),
        WEIGHTS["curv"] * _l2(_hist(curv, *CURV_RANGE)),
    ]
    return _l2(np.concatenate(parts, 1)).astype(np.float32)


def rotate(img, angle_deg, flip=False):
    """Rotate counter-clockwise (as seen on screen) about the patch centre."""
    if flip:
        img = img[:, ::-1]
    c = ((img.shape[1] - 1) / 2.0, (img.shape[0] - 1) / 2.0)
    M = cv2.getRotationMatrix2D(c, angle_deg, 1.0)
    return cv2.warpAffine(np.ascontiguousarray(img, np.float32), M,
                          (img.shape[1], img.shape[0]),
                          flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)


def _masked_unit(P):
    v = P.reshape(len(P), -1)[:, MASK_FLAT]
    v = v - v.mean(1, keepdims=True)
    return v / (np.linalg.norm(v, axis=1, keepdims=True) + 1e-9)


def refine(qz, cands_z, step=6, allow_flip=False):
    """Best normalised cross-correlation of the query over all rotations.

    Returns (ncc[K], angle_deg[K], flipped[K]). Rotating the query by
    `angle` (counter-clockwise on screen) aligns it with the north-up candidate.
    """
    angles = np.arange(0, 360, step)
    flips = [False, True] if allow_flip else [False]
    variants, labels = [], []
    for fl in flips:
        for a in angles:
            variants.append(rotate(qz, a, fl))
            labels.append((a, fl))
    Q = _masked_unit(np.stack(variants))
    C = _masked_unit(np.asarray(cands_z, np.float32))
    S = C @ Q.T
    best = S.argmax(1)
    ang = np.array([labels[b][0] for b in best])
    fl = np.array([labels[b][1] for b in best])
    return S.max(1), ang, fl


# ---------------------------------------------------------------- visuals
_LUT_STOPS = [(0.0, (60, 110, 40)), (0.35, (140, 170, 80)), (0.6, (200, 180, 110)),
              (0.8, (150, 110, 80)), (1.0, (245, 245, 245))]


def _terrain_lut():
    lut = np.zeros((256, 3), np.float32)
    for i in range(256):
        t = i / 255
        for (t0, c0), (t1, c1) in zip(_LUT_STOPS[:-1], _LUT_STOPS[1:]):
            if t0 <= t <= t1:
                k = (t - t0) / (t1 - t0)
                lut[i] = np.array(c0) * (1 - k) + np.array(c1) * k
                break
    return lut[:, ::-1].astype(np.uint8)  # to BGR


_LUT = _terrain_lut()


def hillshade(h, z_factor=None, az=315, alt=45):
    h = np.asarray(h, np.float32)
    if z_factor is None:
        rng = float(h.max() - h.min()) or 1.0
        z_factor = 0.35 * h.shape[0] / rng
    gy, gx = np.gradient(h * z_factor)
    slope = np.pi / 2 - np.arctan(np.hypot(gx, gy))
    aspect = np.arctan2(-gx, gy)
    azr = np.radians(360 - az + 90)
    altr = np.radians(alt)
    hs = np.sin(altr) * np.sin(slope) + np.cos(altr) * np.cos(slope) * np.cos(azr - aspect)
    return np.clip(hs, 0, 1)


def render(h, size=256):
    """Colour-relief + hillshade BGR image of any heightmap."""
    h = np.asarray(h, np.float32)
    h = cv2.resize(h, (size, size), interpolation=cv2.INTER_CUBIC)
    n = (h - h.min()) / (h.max() - h.min() + 1e-9)
    col = _LUT[(n * 255).astype(np.uint8)].astype(np.float32)
    hs = hillshade(h)[..., None]
    return np.clip(col * (0.35 + 0.75 * hs), 0, 255).astype(np.uint8)
