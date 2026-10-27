# Sand → Earth

Sculpt a landscape out of sand or clay, point your Mac's camera at it, and find
the place on Earth whose real terrain looks most like what you built. Results
open as a map over Sentinel-2 imagery, with the sandbox outline and its
orientation drawn on the real location.

```
webcam ──► Depth Anything V2 ──► heightmap ──► rotation-invariant search ──► NCC re-ranking ──► report + result.json
 (CV)          (CV, MPS)          (64×64)        over a global DEM index       (finds the angle)     (Sentinel-2 map)
```

## Setup (macOS, Apple Silicon)

```bash
cd sand2earth
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

Allow camera access for your terminal app: System Settings → Privacy & Security → Camera.

## 1. Build the terrain index (once)

Start with one region, which takes a few minutes:

```bash
python build_index.py --zoom 7 --bbox 4 43 17 49 --name alps
```

Then index the whole planet. This downloads about 3,300 tiles, takes 20–40 minutes and uses about 1 GB of disk:

```bash
python build_index.py --zoom 6 --name world_z6
```

Elevation comes from the public [AWS Terrain Tiles](https://registry.opendata.aws/terrain-tiles/)
(Terrarium PNGs, built from SRTM, ETOPO1 and national DEMs). It needs no account or API key.
The index slides a window over the DEM at three scales (`--levels 1 2 4`). At zoom 6 those
windows cover roughly 150 km, 300 km and 600 km at the equator, so your sandbox can stand in
for a valley or for a whole mountain range.

## 2. Check that the matching works

```bash
python selftest.py --index data/alps            # add --crude to simulate rough sculptures
```

This takes real places from the index and distorts each one: a random rotation, ±15 % scale,
a non-linear height curve, tilt, blur and noise. It then checks whether the search finds the
original place again.

Results in crude-sculpture mode (`--crude`, 60 queries, MacBook with Apple Silicon):

| index | windows | right place first | in top 5 | rotation error | search time |
|---|---|---|---|---|---|
| Alps, zoom 7 | 6,709 | 83 % | 95 % | ~2° | 58 ms |
| World, zoom 6 | 179,472 | 77 % | 80 % | ~2° | 109 ms |

### Known issue: polar bias

Web Mercator stretches high latitudes, so the index currently has far more windows per km²
near the poles than near the equator, and Greenland or Svalbard win more often than they
should. A latitude-aware window spacing is the planned fix.

## 3. Sculpt and search

### Option A: upload a photo (easiest)

```bash
python app.py --index data/world_z6
```

This opens a page at `http://localhost:8000`. Drop in a top-down photo of your sculpture and
press **Find it on Earth**. The results report opens in the same tab.

To shoot with your phone, start the app with `--lan`, then open the printed
`http://<your-mac-ip>:8000` address on your phone (both devices on the same Wi-Fi) and tap
**Take photo**. Without `--lan`, the app is only reachable from your Mac.

### Option B: live webcam

```bash
python run.py --index data/world_z6
```

Keyboard controls in the camera window:

| key | action |
|---|---|
| R | drag a box around the sandbox |
| SPACE | capture and search |
| I | invert the heightmap, if hills come out as valleys |
| Q | quit |

You can also search from a photo taken straight from above, for example with your phone:

```bash
python run.py --index data/world_z6 --image sculpture.jpg
```

Each search writes `output/<time>/report.html` and `result.json`. The same files are also
copied to `output/latest/`, which TouchDesigner can watch with a File In DAT.

## Tips for good captures

- Point the camera straight down, use even diffuse light, and keep hands out of the frame.
- Build big, clear forms such as ridges, valleys and peaks. Fine texture is smoothed away anyway.
- Depth from a single camera is relative, so only the shape matters, not the height. The pipeline removes camera tilt with a plane fit (`--detrend 1`).
- Matte, light-colored modelling clay works better than shiny or wet sand.
- `--flip` also tries mirror images, which helps if your webcam image is mirrored.

## How the matching works

1. **Normalize.** Every window is resized to 64×64, smoothed, and z-scored. After that, a 10 cm hill and a 3,000 m mountain are directly comparable.
2. **Describe without orientation.** The search must work no matter which way the sandbox faces north, so each window is described by rotation-invariant features: polar rings with FFT magnitudes along the angle (in the spirit of Fourier–Mellin), plus histograms of height (hypsometry), slope and curvature inside a circular mask.
3. **Shortlist.** A cosine-similarity scan of all windows keeps the 1,500 best candidates.
4. **Re-rank.** Each candidate is compared with the query rotated in 6° steps using normalized cross-correlation. This gives the final score and the angle, which tells you which compass direction the sandbox's top edge faces.

## Prior work to cite

- Augmented Reality Sandbox (Kreylos, UC Davis): scans sand with a depth camera and projects onto it.
- Tangible Landscape (NC State): sculpts sand to match a known place.
- Content-based landscape retrieval (Jasiewicz, Netzel & Stepinski, 2013) and LSE Wisconsin (Haffner et al., 2023): query-by-example DEM search, but digital and regional.
- terravector (GitHub): DEM patch similarity search with HNSW.
- US patent 11,961,183: game heightmap → real-world terrain search.

None of these close the loop of physical sculpture → global search → real place.

## Next steps

- **Projection:** feed `output/latest/result.json` into TouchDesigner and project the Sentinel-2 tile back onto the sand, rotated by `rotation_deg`.
- **Learned descriptor:** train a Siamese network on (synthetic sculpture, real DEM) pairs and swap it in for `describe()`.
- **Continuous mode:** rerun the search every few seconds while someone sculpts, so the matched place changes live.
- **Mars and Moon:** swap in a planetary DEM such as MOLA or LOLA.

Imagery: Sentinel-2 cloudless 2016 by EOX IT Services GmbH (contains modified Copernicus Sentinel data), CC BY 4.0.
