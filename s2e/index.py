"""Build and query the terrain index."""
import json
import math
import time

import cv2
import numpy as np
from numpy.lib.stride_tricks import sliding_window_view

from .terrain import PATCH, BLUR_SIGMA, prep, zscore, describe, refine
from .tiles import px_to_lonlat, meters_per_px


def build_index(header, prefix, levels=(1, 2, 4), stride=16,
                min_land=0.7, min_relief=40.0, rows_per_chunk=4, batch=4096):
    """Slide a PATCH window over the mosaic at several scales and describe each
    land patch with enough relief. Writes <prefix>.json/_desc.npy/_meta.npy."""
    M = np.load(header["mosaic"], mmap_mode="r")
    H, W = M.shape
    descs, metas = [], []
    t0 = time.time()
    for f in levels:
        Hl, Wl = H // f, W // f
        if Hl < PATCH or Wl < PATCH:
            continue
        ys = list(range(0, Hl - PATCH + 1, stride))
        kept_lvl = 0
        for ci in range(0, len(ys), rows_per_chunk):
            yy = ys[ci:ci + rows_per_chunk]
            a = max(yy[0] - 8, 0)
            b = min(yy[-1] + PATCH + 8, Hl)
            raw = np.asarray(M[a * f:b * f, :Wl * f], np.float32)
            if f > 1:
                raw = cv2.resize(raw, (Wl, b - a), interpolation=cv2.INTER_AREA)
            sm = cv2.GaussianBlur(raw, (0, 0), BLUR_SIGMA, borderType=cv2.BORDER_REFLECT)
            rows = [y - a for y in yy]
            wr = sliding_window_view(raw, (PATCH, PATCH))[:, ::stride][rows]
            ws = sliding_window_view(sm, (PATCH, PATCH))[:, ::stride][rows]
            nr, nc = wr.shape[:2]
            wr = wr.reshape(nr * nc, PATCH, PATCH)
            ws = ws.reshape(nr * nc, PATCH, PATCH)
            land = (wr > 0).mean((1, 2))
            relief = wr.std((1, 2))
            keep = np.nonzero((land >= min_land) & (relief >= min_relief))[0]
            if len(keep) == 0:
                continue
            gy = np.repeat(np.array(yy), nc)[keep]
            gx = np.tile(np.arange(nc) * stride, nr)[keep]
            for s in range(0, len(keep), batch):
                sel = keep[s:s + batch]
                descs.append(describe(zscore(ws[sel])).astype(np.float16))
            metas.append(np.stack([gx * f, gy * f, np.full_like(gx, f)], 1).astype(np.int32))
            kept_lvl += len(keep)
        print(f"[index] level x{f}: {kept_lvl} patches  ({time.time() - t0:.0f}s)")
    desc = np.concatenate(descs)
    meta = np.concatenate(metas)
    np.save(prefix + "_desc.npy", desc)
    np.save(prefix + "_meta.npy", meta)
    hdr = dict(header, levels=list(levels), stride=stride, patch=PATCH, count=int(len(desc)))
    with open(prefix + ".json", "w") as fh:
        json.dump(hdr, fh, indent=2)
    print(f"[index] total {len(desc)} patches -> {prefix}_*.npy")
    return hdr


class Index:
    def __init__(self, prefix):
        with open(prefix + ".json") as fh:
            self.h = json.load(fh)
        self.desc = np.load(prefix + "_desc.npy", mmap_mode="r")
        self.meta = np.load(prefix + "_meta.npy")
        self.mosaic = np.load(self.h["mosaic"], mmap_mode="r")
        self.levels = set(self.h["levels"])

    def raw_patch(self, x, y, f, pad=0):
        H, W = self.mosaic.shape
        s = PATCH * f
        y0, y1 = max(y - pad, 0), min(y + s + pad, H)
        x0, x1 = max(x - pad, 0), min(x + s + pad, W)
        return np.asarray(self.mosaic[y0:y1, x0:x1], np.float32)

    def patch(self, x, y, f):
        return prep(self.raw_patch(x, y, f))

    def geo(self, cx, cy):
        """Mosaic pixel -> (lon, lat). Synthetic worlds return fake coordinates."""
        z = self.h["zoom"]
        return px_to_lonlat(cx + self.h["px0"], cy + self.h["py0"], z)

    def search(self, height, k=5, shortlist=1500, rot_step=6, allow_flip=False,
               levels=None, w_desc=0.3):
        q = prep(height)
        qz = zscore(q)[0]
        qd = describe(qz)[0]
        N = len(self.desc)
        sims = np.empty(N, np.float32)
        for s in range(0, N, 250_000):
            sims[s:s + 250_000] = np.asarray(self.desc[s:s + 250_000], np.float32) @ qd
        if levels:
            sims[~np.isin(self.meta[:, 2], list(levels))] = -9
        sl = min(shortlist, N)
        top = np.argpartition(-sims, sl - 1)[:sl]
        cands = np.stack([self.patch(*self.meta[i]) for i in top])
        ncc, ang, fl = refine(qz, zscore(cands), rot_step, allow_flip)
        score = w_desc * sims[top] + (1 - w_desc) * ncc
        order = np.argsort(-score)

        results, kept = [], []
        for j in order:
            x, y, f = (int(v) for v in self.meta[top[j]])
            cx, cy = x + PATCH * f / 2, y + PATCH * f / 2
            if any(math.hypot(cx - kx, cy - ky) < 0.6 * PATCH * max(f, kf) for kx, ky, kf in kept):
                continue
            kept.append((cx, cy, f))
            results.append(self._result(x, y, f, float(score[j]), float(ncc[j]),
                                        float(sims[top[j]]), int(ang[j]), bool(fl[j])))
            if len(results) == k:
                break
        return q, results

    def _result(self, x, y, f, score, ncc, sim, angle, flipped):
        s = PATCH * f
        cx, cy = x + s / 2, y + s / 2
        lon, lat = self.geo(cx, cy)
        z = self.h["zoom"]
        km = s * meters_per_px(lat, z) / 1000.0
        # Sandbox corners (TL, TR, BR, BL) rotated CCW by `angle` on the map grid.
        a = math.radians(angle)
        corners = []
        for dx, dy in [(-1, -1), (1, -1), (1, 1), (-1, 1)]:
            ox, oy = dx * s / 2, dy * s / 2
            if flipped:
                ox = -ox
            rx = ox * math.cos(a) + oy * math.sin(a)
            ry = -ox * math.sin(a) + oy * math.cos(a)
            corners.append(self.geo(cx + rx, cy + ry))
        top_bearing = (360 - angle) % 360  # compass direction the sandbox's top edge faces
        return dict(lon=lon, lat=lat, x=x, y=y, level=f, size_km=km, score=score,
                    ncc=ncc, desc_sim=sim, rotation_deg=angle, flipped=flipped,
                    top_edge_bearing_deg=top_bearing,
                    corners_lonlat=[[c[0], c[1]] for c in corners])
