"""Webcam/photo -> heightmap.

Primary method: Depth Anything V2 (monocular depth, runs on Apple Silicon via
PyTorch MPS). It outputs relative inverse depth: larger = closer to the camera
= higher terrain when the camera looks down at the sand.
"""
import cv2
import numpy as np

_pipe = None
MODEL = "depth-anything/Depth-Anything-V2-Small-hf"


def depth_anything(img_bgr, model=MODEL):
    global _pipe
    if _pipe is None:
        import torch
        from transformers import pipeline
        if torch.backends.mps.is_available():
            dev = "mps"
        elif torch.cuda.is_available():
            dev = "cuda"
        else:
            dev = "cpu"
        print(f"[depth] loading {model} on {dev} (first run downloads ~100 MB)")
        _pipe = pipeline("depth-estimation", model=model, device=dev)
    from PIL import Image
    out = _pipe(Image.fromarray(cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)))
    d = out["predicted_depth"].squeeze().float().cpu().numpy()
    return cv2.resize(d, (img_bgr.shape[1], img_bgr.shape[0]), interpolation=cv2.INTER_CUBIC)


def shading_depth(img_bgr):
    """Crude no-ML fallback (brightness ~ height). Only for testing the plumbing."""
    g = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY).astype(np.float32)
    return cv2.GaussianBlur(g, (0, 0), max(img_bgr.shape[:2]) / 60)


def detrend(h, order=1):
    """Remove the camera-tilt plane (order 1) or a quadratic bowl (order 2).
    Careful: order 2 also flattens a single central mountain."""
    H, W = h.shape
    yy, xx = np.mgrid[0:H, 0:W]
    x = xx.ravel() / W - 0.5
    y = yy.ravel() / H - 0.5
    cols = [np.ones_like(x), x, y]
    if order >= 2:
        cols += [x * x, x * y, y * y]
    A = np.stack(cols, 1)
    coef, *_ = np.linalg.lstsq(A, h.ravel(), rcond=None)
    return (h.ravel() - A @ coef).reshape(h.shape)


def to_heightmap(depth, invert=False, detrend_order=1, size=128):
    h = -depth if invert else depth
    lo, hi = np.percentile(h, [1, 99])
    h = np.clip(h, lo, hi).astype(np.float64)
    if detrend_order:
        h = detrend(h, detrend_order)
    h = cv2.resize(h.astype(np.float32), (size, size), interpolation=cv2.INTER_AREA)
    return (h - h.min()) / (h.max() - h.min() + 1e-9)


def square_crop(img, roi=None):
    if roi is not None:
        x, y, w, h = roi
        img = img[y:y + h, x:x + w]
    H, W = img.shape[:2]
    s = min(H, W)
    y0, x0 = (H - s) // 2, (W - s) // 2
    return img[y0:y0 + s, x0:x0 + s]
