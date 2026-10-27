"""Measure how well the search recovers known places from distorted "sculptures".

Each query is a real indexed location that has been randomly rotated,
rescaled (+-15 %), bent by a non-linear height curve (like monocular depth),
tilted, blurred and made noisy. A hit = a returned match centred within half a
window of the true spot.

  python selftest.py --index data/synthetic      (offline)
  python selftest.py --index data/world_z6       (on real Earth data)
"""
import argparse
import math
import time

import cv2
import numpy as np

from s2e.index import Index
from s2e.terrain import PATCH, render, rotate, zscore

p = argparse.ArgumentParser()
p.add_argument("--index", required=True)
p.add_argument("-n", type=int, default=60)
p.add_argument("--seed", type=int, default=1)
p.add_argument("--examples", default="selftest_examples.png")
p.add_argument("--crude", action="store_true",
               help="heavier smoothing, like a rough hand-made sculpture")
a = p.parse_args()

idx = Index(a.index)
rng = np.random.default_rng(a.seed)
H, W = idx.mosaic.shape


def make_query(x, y, f):
    s = PATCH * f
    scale = rng.uniform(0.85, 1.15)
    ang = rng.uniform(0, 360)
    span = int(s * scale)
    pad = int(span * 0.8)
    cx, cy = x + s // 2, y + s // 2
    x0, y0 = max(cx - pad, 0), max(cy - pad, 0)
    reg = np.asarray(idx.mosaic[y0:min(cy + pad, H), x0:min(cx + pad, W)], np.float32)
    rcx, rcy = cx - x0, cy - y0
    M = cv2.getRotationMatrix2D((float(rcx), float(rcy)), ang, 1.0)
    rot = cv2.warpAffine(reg, M, (reg.shape[1], reg.shape[0]), borderMode=cv2.BORDER_REFLECT)
    crop = rot[rcy - span // 2: rcy + span // 2, rcx - span // 2: rcx + span // 2]
    q = cv2.resize(crop, (128, 128), interpolation=cv2.INTER_AREA)
    q = (q - q.min()) / (q.max() - q.min() + 1e-9)
    q = q ** rng.uniform(0.7, 1.4)                       # non-linear depth response
    yy, xx = np.mgrid[0:128, 0:128] / 128.0
    q += rng.normal(0, 0.08) * (xx - .5) + rng.normal(0, 0.08) * (yy - .5)  # residual tilt
    blur = rng.uniform(3.0, 6.0) if a.crude else rng.uniform(0.5, 2.0)
    q = cv2.GaussianBlur(q.astype(np.float32), (0, 0), blur)
    q += rng.normal(0, 0.04 if a.crude else 0.02, q.shape)  # sensor noise
    return q.astype(np.float32), ang, (cx, cy)


# keep away from the mosaic border so the rotated crop has real data around it
s_ = PATCH * idx.meta[:, 2]
cx_, cy_ = idx.meta[:, 0] + s_ // 2, idx.meta[:, 1] + s_ // 2
m_ = (s_ * 1.15 * 0.8).astype(int) + 2
ok = (cx_ - m_ >= 0) & (cy_ - m_ >= 0) & (cx_ + m_ < W) & (cy_ + m_ < H)
picks = rng.choice(np.nonzero(ok)[0], a.n, replace=False)
hits1 = hits5 = 0
ang_err, times, examples = [], [], []
for qi, i in enumerate(picks):
    x, y, f = (int(v) for v in idx.meta[i])
    q, ang, (cx, cy) = make_query(x, y, f)
    t0 = time.time()
    qp, res = idx.search(q, k=5)
    times.append(time.time() - t0)
    found = None
    for rank, r in enumerate(res):
        rx, ry = r["x"] + PATCH * r["level"] / 2, r["y"] + PATCH * r["level"] / 2
        if math.hypot(rx - cx, ry - cy) < 0.5 * PATCH * max(f, r["level"]):
            found = rank
            break
    if found is not None:
        hits5 += 1
        hits1 += found == 0
        if found == 0:
            expected = (360 - ang) % 360
            d = abs((res[0]["rotation_deg"] - expected + 180) % 360 - 180)
            ang_err.append(d)
    if len(examples) < 6:
        r = res[0]
        examples.append(np.hstack([render(q, 180),
                                   render(rotate(zscore(qp)[0], r["rotation_deg"]), 180),
                                   render(idx.patch(r["x"], r["y"], r["level"]), 180)]))
    print(f"query {qi + 1:3d}/{a.n}: level x{f}  {'top-1' if found == 0 else ('top-%d' % (found + 1) if found is not None else 'miss')}")

print("\n=== results ===")
print(f"index size        {len(idx.meta):,} patches")
print(f"recall@1          {hits1 / a.n:.0%}")
print(f"recall@5          {hits5 / a.n:.0%}")
if ang_err:
    print(f"rotation error    median {np.median(ang_err):.0f} deg (top-1 hits)")
print(f"search time       median {np.median(times) * 1000:.0f} ms")
if examples:
    grid = np.vstack(examples)
    cv2.putText(grid, "distorted query | turned to north | best match", (8, 18),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
    cv2.imwrite(a.examples, grid)
    print(f"examples          {a.examples}")
