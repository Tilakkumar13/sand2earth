"""Write result.json (for TouchDesigner) and the HTML results sheet."""
import base64
import datetime as dt
import html
import json
import os

import cv2
import numpy as np

from .terrain import render, rotate, zscore
from .style import FONTS, BASE_CSS, MARK_SVG

S2_URL = "https://tiles.maps.eox.at/wmts/1.0.0/s2cloudless_3857/default/g/{z}/{y}/{x}.jpg"
S2_ATTR = ('<a href="https://s2maps.eu">Sentinel-2 cloudless 2016</a> by EOX IT Services GmbH '
           '(contains modified Copernicus Sentinel data 2016)')
ESRI_URL = "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
TOPO_URL = "https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png"

COMPASS = ["north", "north-east", "east", "south-east", "south", "south-west", "west", "north-west"]


def _b64(img, ext=".png"):
    ok, buf = cv2.imencode(ext, img)
    mime = "image/png" if ext == ".png" else "image/jpeg"
    return f"data:{mime};base64," + base64.b64encode(buf.tobytes()).decode()


def _coord(lat, lon):
    return f"{abs(lat):.2f}° {'N' if lat >= 0 else 'S'}, {abs(lon):.2f}° {'E' if lon >= 0 else 'W'}"


def _facing(bearing):
    return COMPASS[int(((bearing % 360) + 22.5) // 45) % 8]


def write_outputs(out_dir, index, query, results, photo=None):
    os.makedirs(out_dir, exist_ok=True)
    synthetic = index.h.get("synthetic", False)
    qz = zscore(query)[0]

    rows = []
    for i, r in enumerate(results, 1):
        real = index.patch(r["x"], r["y"], r["level"])
        aligned = rotate(qz, r["rotation_deg"], r["flipped"])
        r["match_png"] = f"match_{i}.png"
        cv2.imwrite(os.path.join(out_dir, r["match_png"]), render(real, 512))
        big = i == 1
        size = 360 if big else 120
        gm = f"https://www.google.com/maps/@{r['lat']:.5f},{r['lon']:.5f},{_gz(r['size_km'])}z/data=!3m1!1e3"
        ge = (f"https://earth.google.com/web/@{r['lat']:.5f},{r['lon']:.5f},0a,"
              f"{r['size_km'] * 1400:.0f}d,35y,0h,45t,0r")
        links = "" if synthetic else (f'<a href="{gm}" target="_blank" rel="noopener">Satellite view</a>'
                                      f'<a href="{ge}" target="_blank" rel="noopener">Google Earth in 3D</a>')
        rows.append(dict(
            i=i, lat=r["lat"], lon=r["lon"], coord=_coord(r["lat"], r["lon"]),
            km=round(r["size_km"]), agree=round(max(r["ncc"], 0) * 100),
            facing=_facing(r["top_edge_bearing_deg"]), bearing=round(r["top_edge_bearing_deg"]),
            flipped=r["flipped"], links=links,
            mine=_b64(render(aligned, size)), real=_b64(render(real, size))))

    res_json = dict(time=dt.datetime.now().isoformat(timespec="seconds"),
                    synthetic=synthetic, results=results, imagery_tile_url=S2_URL)
    with open(os.path.join(out_dir, "result.json"), "w") as f:
        json.dump(res_json, f, indent=2)
    cv2.imwrite(os.path.join(out_dir, "query_heightmap.png"), render(query, 512))
    np.save(os.path.join(out_dir, "query_heightmap.npy"), query)
    if photo is not None:
        cv2.imwrite(os.path.join(out_dir, "photo.jpg"), photo)

    best = rows[0] if rows else None
    others = rows[1:]
    photo_img = (f'<figure><img src="{_b64(cv2.resize(photo, (240, 240)), ".jpg")}" alt="">'
                 f'<figcaption>Your photo</figcaption></figure>') if photo is not None else ""
    lead = ""
    if best:
        mirror = " The match uses the mirror image of your photo." if best["flipped"] else ""
        lead = f"""
      <section class="best">
        <div class="best-text">
          <p class="kicker">Best match</p>
          <h1 class="place" data-geo="0">{best['coord']}</h1>
          <p class="coord num" data-coord="0" hidden>{best['coord']}</p>
          <p class="explain">A stretch of terrain about <b class="num">{best['km']} km</b> across that agrees with your sculpture's shape at
            <b class="num">{best['agree']}%</b>. Placed on the map, the top edge of your sandbox faces
            <b>{best['facing']}</b> <span class="num">({best['bearing']}°)</span>.{mirror}</p>
          <div class="links">{best['links']}</div>
        </div>
        <div class="pair">
          <figure><img src="{best['mine']}" alt="Your sculpture as terrain, turned to north"><figcaption>Your sculpture, turned to north</figcaption></figure>
          <figure><img src="{best['real']}" alt="The matching real terrain"><figcaption>The real terrain</figcaption></figure>
        </div>
      </section>"""

    other_html = "".join(f"""
        <li class="row" data-i="{o['i'] - 1}" tabindex="0">
          <span class="rank num">{o['i']}</span>
          <span class="thumbs"><img src="{o['mine']}" alt=""><img src="{o['real']}" alt=""></span>
          <span class="where"><span class="place" data-geo="{o['i'] - 1}">{o['coord']}</span>
            <span class="sub num" data-coord="{o['i'] - 1}" hidden>{o['coord']}</span></span>
          <span class="stat num">{o['km']} km<small>across</small></span>
          <span class="stat num">{o['agree']}%<small>shape agreement</small></span>
          <span class="go">{o['links']}</span>
        </li>""" for o in others)

    page = (TEMPLATE
            .replace("%%FONTS%%", FONTS).replace("%%CSS%%", BASE_CSS).replace("%%MARK%%", MARK_SVG)
            .replace("%%PHOTO%%", photo_img)
            .replace("%%QUERY%%", _b64(render(query, 240)))
            .replace("%%WHEN%%", dt.datetime.now().strftime("%d %b %Y, %H:%M"))
            .replace("%%BEST%%", lead)
            .replace("%%MAP%%", "" if synthetic else '<div class="map-wrap neatline"><div id="map"></div></div>')
            .replace("%%OTHERS%%", other_html)
            .replace("%%HAS_OTHERS%%", "" if others else "hidden")
            .replace("%%POLYS%%", json.dumps([[[c[1], c[0]] for c in r["corners_lonlat"]] for r in results]))
            .replace("%%POINTS%%", json.dumps([[r["lat"], r["lon"]] for r in results]))
            .replace("%%SYNTH%%", "true" if synthetic else "false")
            .replace("%%S2%%", S2_URL).replace("%%ESRI%%", ESRI_URL).replace("%%TOPO%%", TOPO_URL)
            .replace("%%S2ATTR%%", html.escape(S2_ATTR, quote=True)))
    path = os.path.join(out_dir, "report.html")
    with open(path, "w") as f:
        f.write(page)
    return path


def _gz(km):
    return max(5, min(13, int(round(14.5 - np.log2(max(km, 1))))))


TEMPLATE = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Your match · Sand to Earth</title>
%%FONTS%%
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.css">
<script src="https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.js"></script>
<style>
%%CSS%%
.wrap { max-width: 1240px; margin: 0 auto; padding: 0 28px; }
.top { display: flex; justify-content: space-between; align-items: center; padding: 22px 0; gap: 16px; }
.top .btn { padding: 11px 16px; font-size: 15px; }
.input { display: flex; gap: 16px; align-items: flex-end; padding: 10px 0 30px; border-bottom: 1px solid var(--ink); flex-wrap: wrap; }
.input figure { margin: 0; }
.input img { width: 112px; height: 112px; object-fit: cover; border-radius: var(--radius-s); display: block; }
figcaption { font-size: 13px; color: var(--ink-3); margin-top: 6px; }
.input .when { margin-left: auto; color: var(--ink-3); font-size: 14px; }

.best { display: grid; grid-template-columns: minmax(0, 5fr) minmax(0, 7fr); gap: 48px; align-items: center; padding: 46px 0 40px; }
.kicker { margin: 0 0 6px; color: var(--forest); font-weight: 600; font-size: 16px; }
.best h1 { font-size: clamp(34px, 4.4vw, 60px); line-height: 1.02; margin: 0 0 10px; letter-spacing: -0.01em; }
.coord { margin: 0 0 22px; color: var(--ink-3); font-size: 15px; }
.explain { color: var(--ink-2); font-size: 18px; margin: 0 0 22px; max-width: 30em; }
.explain b { color: var(--ink); font-weight: 600; }
.links { display: flex; gap: 20px; flex-wrap: wrap; font-weight: 500; }
.pair { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }
.pair figure { margin: 0; }
.pair img { width: 100%; aspect-ratio: 1; display: block; border-radius: 3px; }

.map-wrap { margin: 6px 0 50px; }
#map { height: 520px; }
.leaflet-container { font: 13px var(--sans); background: var(--paper); }

.others h2 { font-size: 24px; font-weight: 700; letter-spacing: -0.015em; margin: 0 0 6px; }
.others > p { margin: 0 0 18px; color: var(--ink-3); }
.others[hidden] { display: none; }
ol.list { list-style: none; margin: 0; padding: 0; border-top: 1px solid var(--rule); }
.row { display: grid; grid-template-columns: 34px 252px minmax(0, 1fr) 90px 120px auto; gap: 18px; align-items: center;
       padding: 14px 6px; border-bottom: 1px solid var(--rule); cursor: pointer; border-radius: 2px; }
.row:hover, .row.active { background: color-mix(in srgb, var(--glacier) 6%, transparent); }
.rank { color: var(--ink-3); font-weight: 600; }
.thumbs { display: flex; gap: 6px; }
.thumbs img { width: 120px; height: 120px; border-radius: 2px; display: block; }
.where .place { display: block; font-size: 21px; line-height: 1.2; }
.where .sub { display: block; font-size: 13.5px; color: var(--ink-3); margin-top: 3px; }
.stat { color: var(--ink-2); font-size: 15px; }
.go { display: flex; flex-direction: column; gap: 4px; font-size: 14px; }
.stat small { display: block; font-size: 12.5px; color: var(--ink-3); }
[hidden] { display: none !important; }

footer { border-top: 1px solid var(--rule); margin-top: 70px; }
footer .wrap { padding-top: 22px; padding-bottom: 36px; color: var(--ink-3); font-size: 14px; }

@media (max-width: 900px) {
  .wrap { padding: 0 16px; }
  .best { grid-template-columns: 1fr; gap: 26px; padding-top: 30px; }
  #map { height: 380px; }
  .row { grid-template-columns: 26px minmax(0, 1fr) auto; grid-template-areas: "r t t" "r w s"; row-gap: 10px; }
  .rank { grid-area: r; align-self: start; }
  .thumbs { grid-area: t; } .thumbs img { width: 96px; height: 96px; }
  .where { grid-area: w; } .stat:nth-of-type(1) { grid-area: s; } .stat + .stat, .go { display: none; }
}
</style></head>
<body>
<div class="wrap">
  <header class="top">
    <a class="mark" href="/" id="home">%%MARK%%Sand to Earth</a>
    <a class="btn" href="/" id="again">Try another photo</a>
  </header>
  <div class="input">
    %%PHOTO%%
    <figure><img src="%%QUERY%%" alt=""><figcaption>Read as terrain</figcaption></figure>
    <span class="when">%%WHEN%%</span>
  </div>
  %%BEST%%
  %%MAP%%
  <section class="others" %%HAS_OTHERS%%>
    <h2>Other close matches</h2>
    <p>Select one to show it on the map.</p>
    <ol class="list">%%OTHERS%%</ol>
  </section>
</div>
<footer><div class="wrap">
  Imagery: Sentinel-2 cloudless 2016 by EOX IT Services GmbH, CC BY 4.0. Elevation: AWS Terrain Tiles.
  Place names: OpenStreetMap contributors via Nominatim.
</div></footer>
<script>
const synthetic = %%SYNTH%%, polys = %%POLYS%%, points = %%POINTS%%;
// When opened as a file (webcam mode), there is no app to go back to.
if (location.protocol === "file:") { document.getElementById("again").style.display = "none"; document.getElementById("home").removeAttribute("href"); }

let shapes = [], map = null;
if (!synthetic && window.L) {
  const css = getComputedStyle(document.documentElement);
  const best = css.getPropertyValue("--forest").trim(), other = "#ffffff", edge = css.getPropertyValue("--contour").trim();
  const s2 = L.tileLayer("%%S2%%", {maxZoom: 15, attribution: "%%S2ATTR%%"});
  const esri = L.tileLayer("%%ESRI%%", {maxZoom: 18, attribution: "Imagery © Esri"});
  const topo = L.tileLayer("%%TOPO%%", {maxZoom: 17, subdomains: "abc", attribution: "© OpenTopoMap (CC-BY-SA)"});
  map = L.map("map", {layers: [s2], worldCopyJump: true, scrollWheelZoom: false});
  L.control.layers({"Sentinel-2": s2, "Esri imagery": esri, "Topographic": topo}).addTo(map);
  L.control.scale({imperial: false}).addTo(map);
  shapes = polys.map((p, i) => {
    const poly = L.polygon(p, {color: i ? other : best, weight: i ? 1.5 : 3, fillOpacity: i ? .04 : .12, dashArray: i ? "4 4" : null})
      .bindTooltip(i ? "Match " + (i + 1) : "Best match").addTo(map);
    L.polyline([p[0], p[1]], {color: "#E3B23C", weight: 5, opacity: .95}).bindTooltip("Top edge of your sandbox").addTo(map);
    return poly;
  });
  map.fitBounds(shapes[0].getBounds().pad(1.4));
}
document.querySelectorAll(".row").forEach(row => {
  const pick = () => {
    document.querySelectorAll(".row").forEach(r => r.classList.remove("active")); row.classList.add("active");
    if (map) { map.fitBounds(shapes[+row.dataset.i].getBounds().pad(1.4)); document.getElementById("map").scrollIntoView({behavior: "smooth", block: "center"}); }
  };
  row.addEventListener("click", e => { if (e.target.tagName !== "A") pick(); });
  row.addEventListener("keydown", e => { if (e.key === "Enter") pick(); });
});

// Name the places (OpenStreetMap Nominatim; one request per second, as its usage policy asks).
if (!synthetic) (async () => {
  for (let i = 0; i < points.length; i++) {
    const [lat, lon] = points[i];
    try {
      const r = await fetch(`https://nominatim.openstreetmap.org/reverse?format=jsonv2&zoom=6&accept-language=en&lat=${lat}&lon=${lon}`);
      const j = await r.json(), a = j.address || {};
      const near = a.state || a.region || a.county || a.province || a.archipelago || a.island;
      const name = [near, a.country].filter(Boolean).join(", ");
      if (name) document.querySelectorAll(`[data-geo="${i}"]`).forEach(el => {
        el.textContent = name;
        if (i === 0) document.title = name + " · Sand to Earth";
      });
      if (name) document.querySelectorAll(`[data-coord="${i}"]`).forEach(el => el.hidden = false);
    } catch (e) { /* keep the coordinates */ }
    await new Promise(res => setTimeout(res, 1100));
  }
})();
</script>
</body></html>
"""
