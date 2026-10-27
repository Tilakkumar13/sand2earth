"""Download global elevation and build the searchable terrain index.

Examples
  # quick first run: Alps + surroundings at higher detail (~5 min)
  python build_index.py --zoom 7 --bbox 4 43 17 49 --name alps

  # the whole land surface at zoom 6 (~3,300 tiles, ~20-40 min, ~1 GB disk)
  python build_index.py --zoom 6 --name world_z6

  # offline test world, no internet needed
  python build_index.py --synthetic --name synthetic
"""
import argparse
import os

from s2e.tiles import build_terrarium_mosaic, synthetic_mosaic
from s2e.index import build_index

p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
p.add_argument("--zoom", type=int, default=6, help="Terrain Tiles zoom (6 = global ~2.4 km/px, 7 = ~1.2 km/px)")
p.add_argument("--bbox", type=float, nargs=4, metavar=("LON_MIN", "LAT_MIN", "LON_MAX", "LAT_MAX"),
               default=[-180, -60, 180, 78], help="region to index (default: all land except Antarctica)")
p.add_argument("--levels", type=int, nargs="+", default=[1, 2, 4],
               help="window scales: 1 = 64 px, 2 = 128 px, 4 = 256 px of the mosaic")
p.add_argument("--stride", type=int, default=16)
p.add_argument("--min-relief", type=float, default=40.0, help="skip flatter patches (metres std)")
p.add_argument("--synthetic", action="store_true", help="fake planet for offline testing")
p.add_argument("--name", default="world_z6")
p.add_argument("--data", default="data")
a = p.parse_args()

os.makedirs(a.data, exist_ok=True)
if a.synthetic:
    hdr = synthetic_mosaic(a.data)
else:
    hdr = build_terrarium_mosaic(a.zoom, a.bbox, a.data)
build_index(hdr, os.path.join(a.data, a.name), levels=tuple(a.levels),
            stride=a.stride, min_relief=a.min_relief)
