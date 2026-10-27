"""Global elevation source: AWS Terrain Tiles (Terrarium PNG, public, no key).

The tiles are a Web Mercator pyramid built from SRTM, Copernicus/ETOPO1 and
national DEMs. Zoom 6 gives a ~16k x 13k pixel world (~2.4 km/px at the
equator); zoom 7 doubles that. Tiles are cached, then stitched into one int16
.npy file that is memory-mapped, so it never has to fit in RAM.
"""
import concurrent.futures as cf
import json
import math
import os
import time
import urllib.error
import urllib.request

import cv2
import numpy as np

TERRARIUM = "https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png"
TILE = 256
EARTH_CIRC = 40075016.686


def lonlat_to_px(lon, lat, z):
    n = TILE * 2 ** z
    lat = max(min(lat, 85.0511), -85.0511)
    x = (lon + 180.0) / 360.0 * n
    y = (1 - math.log(math.tan(math.radians(lat)) + 1 / math.cos(math.radians(lat))) / math.pi) / 2 * n
    return x, y


def px_to_lonlat(x, y, z):
    n = TILE * 2 ** z
    lon = x / n * 360.0 - 180.0
    lat = math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * y / n))))
    return lon, lat


def meters_per_px(lat, z):
    return EARTH_CIRC * math.cos(math.radians(lat)) / (TILE * 2 ** z)


def _fetch(url, path, tries=4):
    if os.path.exists(path):
        return path
    for t in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "sand2earth/0.1"})
            with urllib.request.urlopen(req, timeout=30) as r:
                data = r.read()
            tmp = path + ".part"
            with open(tmp, "wb") as f:
                f.write(data)
            os.replace(tmp, path)
            return path
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            time.sleep(1.5 * (t + 1))
        except Exception:
            time.sleep(1.5 * (t + 1))
    return None


def decode_terrarium(path):
    img = cv2.imread(path, cv2.IMREAD_COLOR)
    if img is None:
        return None
    b, g, r = (img[:, :, i].astype(np.float32) for i in range(3))
    return r * 256.0 + g + b / 256.0 - 32768.0


def build_terrarium_mosaic(z, bbox, out_dir, workers=16):
    """bbox = (lon_min, lat_min, lon_max, lat_max). Returns header dict."""
    lon0, lat0, lon1, lat1 = bbox
    xa, yb = lonlat_to_px(lon0, lat0, z)
    xb, ya = lonlat_to_px(lon1, lat1, z)
    nt = 2 ** z
    tx0, tx1 = max(int(xa // TILE), 0), min(int((xb - 1e-6) // TILE), nt - 1)
    ty0, ty1 = max(int(ya // TILE), 0), min(int((yb - 1e-6) // TILE), nt - 1)
    ntx, nty = tx1 - tx0 + 1, ty1 - ty0 + 1

    cache = os.path.join(out_dir, "tiles", str(z))
    os.makedirs(cache, exist_ok=True)
    jobs = [(x, y) for y in range(ty0, ty1 + 1) for x in range(tx0, tx1 + 1)]
    print(f"[tiles] zoom {z}: {ntx} x {nty} = {len(jobs)} tiles -> {cache}")

    def job(xy):
        x, y = xy
        p = os.path.join(cache, f"{x}_{y}.png")
        return xy, _fetch(TERRARIUM.format(z=z, x=x, y=y), p)

    mosaic_path = os.path.join(out_dir, f"mosaic_z{z}.npy")
    M = np.lib.format.open_memmap(mosaic_path, mode="w+", dtype=np.int16,
                                  shape=(nty * TILE, ntx * TILE))
    done, t0 = 0, time.time()
    with cf.ThreadPoolExecutor(workers) as ex:
        for (x, y), p in ex.map(job, jobs):
            e = decode_terrarium(p) if p else None
            r, c = (y - ty0) * TILE, (x - tx0) * TILE
            M[r:r + TILE, c:c + TILE] = 0 if e is None else np.clip(np.round(e), -32000, 32000)
            done += 1
            if done % 200 == 0 or done == len(jobs):
                print(f"[tiles] {done}/{len(jobs)}  ({time.time() - t0:.0f}s)")
    M.flush()
    del M
    return dict(source="terrarium", synthetic=False, zoom=z,
                px0=tx0 * TILE, py0=ty0 * TILE, mosaic=os.path.abspath(mosaic_path))


def synthetic_mosaic(out_dir, size=2048, seed=0):
    """Fake planet (fractal continents + ridged mountains) for offline testing."""
    rng = np.random.default_rng(seed)
    ky = np.fft.fftfreq(size)[:, None]
    kx = np.fft.rfftfreq(size)[None, :]
    k = np.sqrt(kx ** 2 + ky ** 2)
    k[0, 0] = 1.0

    def fbm(beta):
        spec = (rng.normal(size=k.shape) + 1j * rng.normal(size=k.shape)) * k ** (-beta / 2)
        spec[0, 0] = 0
        f = np.fft.irfft2(spec, s=(size, size))
        return (f - f.mean()) / f.std()

    base = fbm(3.4)
    detail = fbm(2.3)
    ridged = 1.0 - np.abs(fbm(2.7))
    belts = np.clip(fbm(3.1), 0, None)
    elev = 900 * base + 180 * detail + 2600 * belts * ridged ** 2
    elev -= np.percentile(elev, 58)  # ~42 % land
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, "mosaic_synthetic.npy")
    np.save(path, np.clip(elev, -9000, 9000).astype(np.int16))
    return dict(source="synthetic", synthetic=True, zoom=3, px0=0, py0=0,
                mosaic=os.path.abspath(path))


def save_header(h, path):
    with open(path, "w") as f:
        json.dump(h, f, indent=2)
