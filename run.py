"""Sculpt -> capture -> find it on Earth.

Live webcam (default):
  python run.py --index data/world_z6
    SPACE  capture + search        R  draw a region (sandbox) with the mouse
    I      invert height           Q  quit

From a photo (e.g. taken with your phone straight from above):
  python run.py --index data/world_z6 --image sculpture.jpg

From a ready heightmap (.npy or 16-bit/8-bit grayscale .png):
  python run.py --index data/world_z6 --heightmap my_dem.png

Each search writes output/<time>/report.html (+ result.json for TouchDesigner)
and mirrors it to output/latest/.
"""
import argparse
import datetime as dt
import os
import shutil
import time
import webbrowser

import cv2
import numpy as np

from s2e.index import Index
from s2e.depth import depth_anything, shading_depth, to_heightmap, square_crop
from s2e.report import write_outputs
from s2e.terrain import render, rotate, zscore

p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
p.add_argument("--index", required=True, help="index prefix, e.g. data/world_z6")
src = p.add_mutually_exclusive_group()
src.add_argument("--camera", type=int, default=0)
src.add_argument("--image")
src.add_argument("--heightmap")
p.add_argument("--depth", choices=["dav2", "shading"], default="dav2",
               help="dav2 = Depth Anything V2 (recommended); shading = crude test fallback")
p.add_argument("--invert", action="store_true", help="use if hills come out as valleys")
p.add_argument("--detrend", type=int, default=1, choices=[0, 1, 2])
p.add_argument("--flip", action="store_true", help="also test mirrored matches")
p.add_argument("-k", type=int, default=5)
p.add_argument("--out", default="output")
p.add_argument("--no-browser", action="store_true")
a = p.parse_args()

print("[run] loading index ...")
idx = Index(a.index)
print(f"[run] {len(idx.desc):,} terrain patches ready")


def estimate(img):
    d = depth_anything(img) if a.depth == "dav2" else shading_depth(img)
    return to_heightmap(d, invert=a.invert, detrend_order=a.detrend)


def search_and_report(height, photo=None):
    t0 = time.time()
    q, res = idx.search(height, k=a.k, allow_flip=a.flip)
    stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    out = os.path.join(a.out, stamp)
    path = write_outputs(out, idx, q, res, photo)
    latest = os.path.join(a.out, "latest")
    shutil.rmtree(latest, ignore_errors=True)
    shutil.copytree(out, latest)
    print(f"[run] search {time.time() - t0:.1f}s -> {path}")
    for i, r in enumerate(res, 1):
        print(f"   #{i}  {r['lat']:8.3f}, {r['lon']:8.3f}  ~{r['size_km']:.0f} km  "
              f"match {r['ncc']:.2f}  top edge -> {r['top_edge_bearing_deg']:.0f} deg")
    if not a.no_browser:
        webbrowser.open("file://" + os.path.abspath(path))
    return q, res


def preview(q, res):
    qz = zscore(q)[0]
    r = res[0]
    left = render(rotate(qz, r["rotation_deg"], r["flipped"]), 320)
    right = render(idx.patch(r["x"], r["y"], r["level"]), 320)
    pane = np.hstack([left, right])
    cv2.putText(pane, f"{r['lat']:.2f}, {r['lon']:.2f}  ~{r['size_km']:.0f} km",
                (10, 305), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
    cv2.imshow("best match (sculpture | Earth)", pane)


def load_heightmap(path):
    if path.endswith(".npy"):
        return np.load(path).astype(np.float32)
    return cv2.imread(path, cv2.IMREAD_UNCHANGED).astype(np.float32)


if a.heightmap:
    search_and_report(square_crop(load_heightmap(a.heightmap)))
elif a.image:
    img = square_crop(cv2.imread(a.image))
    search_and_report(estimate(img), img)
else:
    cap = cv2.VideoCapture(a.camera, cv2.CAP_AVFOUNDATION) if os.uname().sysname == "Darwin" \
        else cv2.VideoCapture(a.camera)
    if not cap.isOpened():
        raise SystemExit("Could not open the camera. On macOS allow camera access for your "
                         "terminal app in System Settings > Privacy & Security > Camera.")
    roi = None
    print("[run] SPACE = capture, R = select sandbox region, I = invert, Q = quit")
    while True:
        ok, frame = cap.read()
        if not ok:
            continue
        view = frame.copy()
        if roi:
            x, y, w, h = roi
            cv2.rectangle(view, (x, y), (x + w, y + h), (80, 160, 224), 2)
        cv2.putText(view, "SPACE capture  R region  I invert" + ("  [inverted]" if a.invert else ""),
                    (12, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        cv2.imshow("Sand -> Earth", view)
        key = cv2.waitKey(1) & 0xFF
        if key in (ord("q"), 27):
            break
        if key == ord("i"):
            a.invert = not a.invert
        if key == ord("r"):
            r = cv2.selectROI("Sand -> Earth", frame, showCrosshair=False)
            roi = r if r[2] > 10 and r[3] > 10 else None
        if key == ord(" "):
            # average a few frames to cut sensor noise
            frames = [frame.astype(np.float32)]
            for _ in range(4):
                ok2, f2 = cap.read()
                if ok2:
                    frames.append(f2.astype(np.float32))
            img = square_crop(np.mean(frames, 0).astype(np.uint8), roi)
            print("[run] estimating depth ...")
            q, res = search_and_report(estimate(img), img)
            preview(q, res)
    cap.release()
    cv2.destroyAllWindows()
