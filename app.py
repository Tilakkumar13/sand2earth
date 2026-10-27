"""Photo-upload web app: drop a photo of your sculpture, get the matching place on Earth.

  python app.py --index data/world_z6            # http://localhost:8000 on this Mac
  python app.py --index data/world_z6 --lan      # also reachable from your phone on the same Wi-Fi

With --lan, open the printed address on your phone and use "Take photo" to shoot
the sculpture straight from above. Only standard-library web serving is used.
"""
import argparse
import datetime as dt
import json
import os
import socket
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs, unquote

import cv2
import numpy as np

from s2e.index import Index
from s2e.depth import depth_anything, shading_depth, to_heightmap, square_crop
from s2e.report import write_outputs
from s2e.page import render_page

p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
p.add_argument("--index", required=True)
p.add_argument("--port", type=int, default=8000)
p.add_argument("--lan", action="store_true", help="listen on the local network (phone access)")
p.add_argument("--depth", choices=["dav2", "shading"], default="dav2")
p.add_argument("--out", default="output")
p.add_argument("--no-browser", action="store_true")
a = p.parse_args()

print("[app] loading index ...")
IDX = Index(a.index)
print(f"[app] {len(IDX.desc):,} terrain patches ready")
LOCK = threading.Lock()  # one depth model, one search at a time
OUT = os.path.abspath(a.out)
MAX_UPLOAD = 25 * 1024 * 1024
PAGE = render_page(len(IDX.desc))


def run_search(data, invert, flip, detrend):
    img = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("Could not read that image. Try a JPG or PNG.")
    long_side = max(img.shape[:2])
    if long_side > 1600:  # phone photos are huge; depth model works at ~518 px anyway
        s = 1600 / long_side
        img = cv2.resize(img, None, fx=s, fy=s, interpolation=cv2.INTER_AREA)
    img = square_crop(img)
    with LOCK:
        d = depth_anything(img) if a.depth == "dav2" else shading_depth(img)
        h = to_heightmap(d, invert=invert, detrend_order=detrend)
        q, res = IDX.search(h, k=5, allow_flip=flip)
        stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
        write_outputs(os.path.join(OUT, stamp), IDX, q, res, img)
    return stamp, res


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass

    def _send(self, code, body, ctype):
        if isinstance(body, str):
            body = body.encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = urlparse(self.path).path
        if path in ("/", "/index.html"):
            return self._send(200, PAGE, "text/html; charset=utf-8")
        if path.startswith("/out/"):
            rel = unquote(path[len("/out/"):])
            full = os.path.abspath(os.path.join(OUT, rel))
            if not full.startswith(OUT + os.sep) or not os.path.isfile(full):
                return self._send(404, "not found", "text/plain")
            ext = os.path.splitext(full)[1].lower()
            ctype = {".html": "text/html; charset=utf-8", ".png": "image/png", ".jpg": "image/jpeg",
                     ".json": "application/json"}.get(ext, "application/octet-stream")
            with open(full, "rb") as f:
                return self._send(200, f.read(), ctype)
        self._send(404, "not found", "text/plain")

    def do_POST(self):
        u = urlparse(self.path)
        if u.path != "/search":
            return self._send(404, "not found", "text/plain")
        n = int(self.headers.get("Content-Length", 0))
        if n <= 0 or n > MAX_UPLOAD:
            return self._send(413, json.dumps({"error": "Photo missing or larger than 25 MB."}), "application/json")
        data = self.rfile.read(n)
        qs = parse_qs(u.query)
        flag = lambda k: qs.get(k, ["0"])[0] == "1"
        try:
            detrend = int(qs.get("detrend", ["1"])[0])
            stamp, res = run_search(data, flag("invert"), flag("flip"), detrend if detrend in (0, 1, 2) else 1)
        except Exception as e:  # report the problem to the page instead of a blank 500
            print(f"[app] error: {e}")
            return self._send(400, json.dumps({"error": str(e)}), "application/json")
        top = res[0] if res else {}
        print(f"[app] {stamp}: best {top.get('lat', 0):.2f}, {top.get('lon', 0):.2f}")
        self._send(200, json.dumps({"report": f"/out/{stamp}/report.html", "results": res}),
                   "application/json")




def lan_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except OSError:
        return None


host = "0.0.0.0" if a.lan else "127.0.0.1"
srv = ThreadingHTTPServer((host, a.port), Handler)
url = f"http://localhost:{a.port}"
print(f"[app] open {url}")
if a.lan and lan_ip():
    print(f"[app] on your phone (same Wi-Fi): http://{lan_ip()}:{a.port}")
if not a.no_browser:
    webbrowser.open(url)
try:
    srv.serve_forever()
except KeyboardInterrupt:
    print("\n[app] stopped")
