"""The upload page served by app.py."""
from .style import FONTS, BASE_CSS, MARK_SVG

_PAGE = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Sand to Earth</title>
<meta name="description" content="Sculpt a landscape, photograph it, and find where it already exists on Earth.">
%%FONTS%%
<style>
%%CSS%%
/* ---------- hero: live contour sheet ---------- */
.hero { position: relative; min-height: min(100svh, 980px); padding: 18px; display: flex; }
.sheet-frame { position: relative; flex: 1; display: flex; flex-direction: column; overflow: hidden; }
#relief { position: absolute; inset: 0; width: 100%; height: 100%; display: block; }
.top { position: relative; z-index: 2; display: flex; justify-content: space-between; align-items: center;
       padding: 22px 28px; gap: 16px; }
.top nav a { color: var(--ink-2); text-decoration: none; font-weight: 500; margin-left: 22px; }
.top nav a:hover { color: var(--ink); }
.hero-body { position: relative; z-index: 2; flex: 1; display: grid; grid-template-columns: minmax(0, 7fr) minmax(0, 5fr);
             gap: 48px; align-items: end; padding: 24px 28px 34px; }
.lede { max-width: 640px; padding-bottom: 8px; }
/* label halos, as printed on topographic maps */
.lede h1, .lede p { text-shadow: 0 0 3px var(--paper), 0 0 6px var(--paper), 0 0 12px var(--paper); }
h1 { font-weight: 800; font-size: clamp(44px, 6.4vw, 92px); line-height: .94; letter-spacing: -0.035em; margin: 0 0 26px; }
.lede p { font-size: 19px; color: var(--ink-2); max-width: 34em; margin: 0; }
.lede p + p { margin-top: 12px; }
.readout { position: absolute; z-index: 2; left: 28px; top: 50%; transform: translateY(-50%);
           font-size: 13px; color: var(--ink-3); opacity: 0; transition: opacity .2s; pointer-events: none; }
.readout b { color: var(--contour); font-weight: 600; font-variant-numeric: tabular-nums; }
.hero:hover .readout { opacity: 1; }

/* ---------- the inset: upload panel ---------- */
.inset { background: var(--sheet); border-radius: 2px; box-shadow: 0 1px 0 var(--rule); }
.inset-inner { padding: 24px; }
.inset h2 { font-size: 21px; font-weight: 700; margin: 0 0 4px; letter-spacing: -0.01em; }
.inset .hint { color: var(--ink-3); font-size: 15px; margin: 0 0 18px; }
#drop { position: relative; border: 1.5px dashed var(--rule); border-radius: var(--radius-m); min-height: 210px;
        display: grid; place-items: center; text-align: center; padding: 18px; cursor: pointer;
        transition: border-color .15s, background .15s; }
#drop.over { border-color: var(--glacier); background: color-mix(in srgb, var(--glacier) 6%, transparent); }
#drop .empty p { margin: 10px 0 14px; color: var(--ink-2); }
#drop svg.icon { width: 46px; height: 46px; color: var(--contour); }
#drop .pick { display: flex; gap: 10px; justify-content: center; flex-wrap: wrap; }
#drop .pick .btn { padding: 11px 16px; font-size: 15px; }
#preview { display: none; width: 100%; }
#preview .ph { position: relative; aspect-ratio: 1; width: 100%; max-width: 300px; margin: 0 auto;
               border-radius: var(--radius-s); overflow: hidden; background: var(--paper); }
#preview img { width: 100%; height: 100%; object-fit: cover; display: block; }
#preview .ph::after { /* the square the search uses */
  content: ""; position: absolute; inset: 0; box-shadow: inset 0 0 0 2px var(--glacier); border-radius: inherit; }
#preview .meta { display: flex; justify-content: space-between; align-items: center; gap: 12px; margin-top: 10px;
                 font-size: 14px; color: var(--ink-3); max-width: 300px; margin-inline: auto; }
#preview .meta span { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.linkish { background: none; border: none; font: inherit; color: var(--glacier); cursor: pointer; padding: 0; }
input[type=file] { position: absolute; width: 1px; height: 1px; opacity: 0; pointer-events: none; }
.opts { display: grid; gap: 10px; margin: 18px 0 20px; font-size: 15px; color: var(--ink-2); }
.opts label { display: flex; gap: 10px; align-items: flex-start; cursor: pointer; }
.opts input { accent-color: var(--glacier); width: 17px; height: 17px; margin: 3px 0 0; flex: none; }
.opts small { display: block; color: var(--ink-3); font-size: 13px; }
#go { width: 100%; padding: 17px; font-size: 17px; }

/* progress: the three real stages of a search */
#progress { display: none; list-style: none; margin: 18px 0 0; padding: 0; font-size: 15px; }
#progress li { display: flex; gap: 12px; align-items: center; padding: 5px 0; color: var(--ink-3); transition: color .2s; }
#progress li i { width: 10px; height: 10px; border-radius: 50%; border: 1.5px solid currentColor; flex: none; }
#progress li.on { color: var(--ink); }
#progress li.on i { border-color: var(--glacier); background: var(--glacier); animation: pulse 1.1s ease-in-out infinite; }
#progress li.done { color: var(--ink-2); }
#progress li.done i { background: var(--forest); border-color: var(--forest); }
@keyframes pulse { 50% { transform: scale(.6); opacity: .6; } }
#error { display: none; margin-top: 14px; color: var(--error); font-size: 15px; }

/* ---------- about ---------- */
.about { max-width: 1240px; margin: 0 auto; padding: 110px 46px 40px; }
.about-head { display: grid; grid-template-columns: minmax(0, 5fr) minmax(0, 7fr); gap: 48px; align-items: end;
              padding-bottom: 34px; border-bottom: 1px solid var(--ink); }
.about-head h2 { font-size: clamp(34px, 4vw, 54px); line-height: 1; letter-spacing: -0.03em; margin: 0; font-weight: 800; }
.about-head p { margin: 0; color: var(--ink-2); font-size: 19px; max-width: 36em; }
.cols { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 0; }
.col { padding: 30px 32px 10px 0; }
.col + .col { padding-left: 32px; border-left: 1px solid var(--rule); }
.col h3 { font-size: 26px; font-weight: 700; letter-spacing: -0.02em; margin: 0 0 14px; }
.col p { margin: 0 0 14px; color: var(--ink-2); font-size: 16.5px; line-height: 1.6; }
.col p strong { color: var(--ink); font-weight: 600; }

/* pipeline drawn as a profile line: photo -> depth -> search -> match */
.profile { max-width: 1240px; margin: 0 auto; padding: 30px 46px 90px; }
.profile svg { width: 100%; height: auto; display: block; color: var(--ink); }
.profile .st { font: 600 15px var(--sans); fill: var(--ink); }
.profile .sd { font: 400 13.5px var(--sans); fill: var(--ink-3); }

footer { border-top: 1px solid var(--rule); }
footer .in { max-width: 1240px; margin: 0 auto; padding: 26px 46px 40px; display: flex; justify-content: space-between;
             gap: 24px; flex-wrap: wrap; color: var(--ink-3); font-size: 14px; }
footer p { margin: 0; max-width: 60em; }

@media (max-width: 940px) {
  .hero { padding: 10px; min-height: auto; }
  .hero-body { grid-template-columns: 1fr; gap: 28px; padding: 30px 18px 22px; }
  .top { padding: 16px 18px; } .top nav a { margin-left: 16px; }
  .readout { display: none; }
  .about { padding: 70px 16px 24px; }
  .about-head { grid-template-columns: 1fr; gap: 16px; }
  .cols { grid-template-columns: 1fr; }
  .col, .col + .col { padding: 24px 0 4px; border-left: none; }
  .col + .col { border-top: 1px solid var(--rule); }
  .profile { padding: 10px 16px 60px; overflow-x: auto; }
  .profile svg { min-width: 640px; }
  footer .in { padding: 22px 16px 32px; }
}
</style></head>
<body>
<section class="hero">
  <div class="sheet-frame neatline">
    <canvas id="relief" aria-hidden="true"></canvas>
    <header class="top">
      <a class="mark" href="/">%%MARK%%Sand to Earth</a>
      <nav><a href="#about">About</a><a href="#upload">Try it</a></nav>
    </header>
    <div class="readout">Elevation under the cursor <b id="elev">0 m</b></div>
    <div class="hero-body">
      <div class="lede">
        <h1>Shape a landscape. Find where it already exists.</h1>
        <p>Press hills and valleys into sand or clay, take one photo from above, and this tool searches
           <span class="num">%%COUNT%%</span> stretches of real terrain for the one that matches your shape.</p>
      </div>
      <div class="inset neatline" id="upload">
        <div class="inset-inner">
          <h2>Your sculpture</h2>
          <p class="hint">A photo taken straight down works best.</p>
          <div id="drop" tabindex="0" role="button" aria-label="Add a photo of your sculpture">
            <div class="empty" id="empty">
              <svg class="icon" viewBox="0 0 48 48" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" aria-hidden="true">
                <path d="M4 38c7-1 10-14 20-16s14 10 20 9"/><path d="M11 38c4-1 6-8 13-9s9 5 13 5" opacity=".6"/>
                <path d="M18 38c2 0 4-3 6-3s4 2 6 2" opacity=".35"/><path d="M24 4v12M18 10l6-6 6 6"/></svg>
              <p>Drop a photo here, or</p>
              <div class="pick">
                <label class="btn">Choose a photo<input id="pick" type="file" accept="image/*"></label>
                <label class="btn">Use camera<input id="snap" type="file" accept="image/*" capture="environment"></label>
              </div>
            </div>
            <div id="preview">
              <div class="ph"><img id="pimg" alt="Your photo, cropped to the square that will be searched"></div>
              <div class="meta"><span id="pname"></span><button class="linkish" id="change" type="button">Change</button></div>
            </div>
          </div>
          <div class="opts">
            <label><input type="checkbox" id="invert"><span>Swap hills and valleys<small>Use this if a result shows your peaks as pits.</small></span></label>
            <label><input type="checkbox" id="flip"><span>Also check the mirror image<small>Helps when the camera flips the picture.</small></span></label>
          </div>
          <button class="btn btn-primary" id="go" disabled>Find the match</button>
          <ol id="progress" aria-live="polite">
            <li><i></i>Reading depth from the photo</li>
            <li><i></i>Comparing it with <span class="num">%%COUNT%%</span> places</li>
            <li><i></i>Turning the best ones to line them up</li>
          </ol>
          <p id="error" role="alert"></p>
        </div>
      </div>
    </div>
  </div>
</section>

<section class="about" id="about">
  <div class="about-head">
    <h2>About the project</h2>
    <p>Sand to Earth is an experiment at the meeting point of GIS, computer vision and remote sensing:
       a physical sculpture goes in, a real place on the planet comes out.</p>
  </div>
  <div class="cols">
    <div class="col">
      <h3>Why</h3>
      <p>Landforms repeat. The same erosion, uplift and drainage carve similar shapes on every continent,
         so a ridge pressed into clay on a café table very likely exists somewhere at full size.</p>
      <p>Projected sandboxes can show contour lines on sand, and tangible GIS tools can rebuild a known place
         in sand. None of them asks the reverse question: <strong>given a shape made by hand, where on Earth is it?</strong></p>
    </div>
    <div class="col">
      <h3>What it does</h3>
      <p>A depth model (Depth Anything V2) reads the photo as a height map. That shape is compared with windows
         of real elevation data about <strong>150, 300 and 600 km</strong> across.</p>
      <p>The comparison ignores absolute height and compass direction, because a sandbox has neither. The strongest
         candidates are then turned through every angle, which also tells you which way your sandbox would face on the map.</p>
    </div>
    <div class="col">
      <h3>Where</h3>
      <p>Elevation comes from the open <a href="https://registry.opendata.aws/terrain-tiles/">AWS Terrain Tiles</a>
         (SRTM, ETOPO1 and national surveys). Matches are shown on
         <a href="https://s2maps.eu">Sentinel-2 cloudless</a> imagery by EOX.</p>
      <p>Everything runs on this computer. Your photo is never uploaded anywhere.</p>
      <p>Built by Tilak Kumar, MSc Geospatial Technologies, Institute for Geoinformatics, University of Münster.</p>
    </div>
  </div>
</section>

<section class="profile" aria-label="How a search works">
  <svg viewBox="0 0 1150 215" role="img" aria-labelledby="pt">
    <title id="pt">A photo becomes a height map, is compared with global terrain, and the best match is aligned and mapped.</title>
    <path d="M10 150 C 120 150, 160 80, 290 98 S 450 160, 580 126 S 760 78, 870 92 S 1060 140, 1140 120"
          fill="none" stroke="var(--contour)" stroke-width="2"/>
    <path d="M10 170 C 140 168, 190 110, 300 122 S 460 176, 590 150 S 770 104, 880 116 S 1060 160, 1140 150"
          fill="none" stroke="var(--contour-soft)" stroke-width="1"/>
    <g>
      <circle cx="40" cy="149" r="6" fill="var(--paper)" stroke="var(--ink)" stroke-width="2"/>
      <text class="st" x="40" y="40">Photo</text><text class="sd" x="40" y="60">one shot from above</text>
      <line x1="40" y1="70" x2="40" y2="140" stroke="var(--rule)"/>
    </g>
    <g>
      <circle cx="330" cy="99" r="6" fill="var(--paper)" stroke="var(--ink)" stroke-width="2"/>
      <text class="st" x="330" y="182">Height map</text><text class="sd" x="330" y="202">depth model on this computer</text>
      <line x1="330" y1="110" x2="330" y2="164" stroke="var(--rule)"/>
    </g>
    <g>
      <circle cx="620" cy="111" r="6" fill="var(--paper)" stroke="var(--ink)" stroke-width="2"/>
      <text class="st" x="620" y="40">Search</text><text class="sd" x="620" y="60">%%COUNT%% windows of terrain</text>
      <line x1="620" y1="70" x2="620" y2="101" stroke="var(--rule)"/>
    </g>
    <g>
      <circle cx="905" cy="94" r="7" fill="var(--forest)" stroke="var(--ink)" stroke-width="2"/>
      <text class="st" x="905" y="182">Match</text><text class="sd" x="905" y="202">aligned and mapped</text>
      <line x1="905" y1="104" x2="905" y2="164" stroke="var(--rule)"/>
    </g>
  </svg>
</section>

<footer><div class="in">
  <p>Elevation: AWS Terrain Tiles (Mapzen / Tilezen). Imagery: Sentinel-2 cloudless 2016 by EOX IT Services GmbH,
     contains modified Copernicus Sentinel data, CC BY 4.0. Depth: Depth Anything V2.</p>
  <p>Sand to Earth, 2026</p>
</div></footer>

<script>
/* ---------- contour sheet ---------- */
(() => {
  const cv = document.getElementById("relief"), ctx = cv.getContext("2d");
  const elev = document.getElementById("elev");
  const reduce = matchMedia("(prefers-reduced-motion: reduce)").matches;
  const CELL = 9, LEVELS = 22, TOP_M = 3400;
  let G = null, gw = 0, gh = 0, seed = 7;

  function rand() { seed = (seed * 16807) % 2147483647; return seed / 2147483647; }
  function build(w, h) {
    gw = Math.ceil(w / CELL) + 1; gh = Math.ceil(h / CELL) + 1;
    seed = 7;
    const blobs = Array.from({length: 11}, () => ({
      x: rand() * gw, y: rand() * gh, a: (rand() * 1.2 + .3) * (rand() < .25 ? -1 : 1),
      sx: (rand() * .18 + .07) * gw, sy: (rand() * .18 + .07) * gw, r: rand() * Math.PI }));
    G = new Float32Array(gw * gh);
    let lo = Infinity, hi = -Infinity;
    for (let j = 0; j < gh; j++) for (let i = 0; i < gw; i++) {
      let v = .35 * Math.sin(i * .045 + j * .02) + .2 * Math.sin(i * .013 - j * .051);
      for (const b of blobs) {
        const dx = i - b.x, dy = j - b.y, c = Math.cos(b.r), s = Math.sin(b.r);
        const u = (dx * c + dy * s) / b.sx, t = (-dx * s + dy * c) / b.sy;
        v += b.a * Math.exp(-(u * u + t * t));
      }
      G[j * gw + i] = v; lo = Math.min(lo, v); hi = Math.max(hi, v);
    }
    for (let k = 0; k < G.length; k++) G[k] = (G[k] - lo) / (hi - lo);
  }
  function segments(level) {
    const segs = [];
    for (let j = 0; j < gh - 1; j++) for (let i = 0; i < gw - 1; i++) {
      const a = G[j*gw+i], b = G[j*gw+i+1], c = G[(j+1)*gw+i+1], d = G[(j+1)*gw+i];
      const idx = (a > level) | (b > level) << 1 | (c > level) << 2 | (d > level) << 3;
      if (idx === 0 || idx === 15) continue;
      const x = i * CELL, y = j * CELL, f = (p, q) => (level - p) / (q - p);
      const T = [x + f(a, b) * CELL, y], R = [x + CELL, y + f(b, c) * CELL],
            B = [x + f(d, c) * CELL, y + CELL], L = [x, y + f(a, d) * CELL];
      const map = {1:[L,T],2:[T,R],3:[L,R],4:[R,B],5:[L,T,R,B],6:[T,B],7:[L,B],8:[B,L],9:[T,B],10:[T,R,B,L],
                   11:[R,B],12:[R,L],13:[T,R],14:[T,L]}[idx];
      segs.push([map[0], map[1]]); if (map.length === 4) segs.push([map[2], map[3]]);
    }
    return segs;
  }
  function draw(upto) {
    const css = getComputedStyle(document.documentElement);
    const main = css.getPropertyValue("--contour").trim(), soft = css.getPropertyValue("--contour-soft").trim();
    ctx.clearRect(0, 0, cv.width, cv.height);
    ctx.lineCap = "round";
    for (let k = 1; k <= Math.min(upto, LEVELS - 1); k++) {
      const index = k % 5 === 0;
      ctx.strokeStyle = index ? main : soft; ctx.lineWidth = index ? 1.5 : .8;
      ctx.globalAlpha = index ? .75 : .7;
      ctx.beginPath();
      for (const [p, q] of LV[k]) { ctx.moveTo(p[0], p[1]); ctx.lineTo(q[0], q[1]); }
      ctx.stroke();
    }
    ctx.globalAlpha = 1;
  }
  let LV = [];
  function setup(animate) {
    const r = cv.getBoundingClientRect(), dpr = Math.min(devicePixelRatio || 1, 2);
    cv.width = r.width * dpr; cv.height = r.height * dpr; ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    build(r.width, r.height);
    LV = Array.from({length: LEVELS}, (_, k) => k ? segments(k / LEVELS) : []);
    if (!animate || reduce) return draw(LEVELS);
    const t0 = performance.now(), dur = 1500;
    (function step(t) {
      const p = Math.min((t - t0) / dur, 1), e = 1 - Math.pow(1 - p, 3);
      draw(Math.ceil(e * LEVELS)); if (p < 1) requestAnimationFrame(step);
    })(t0);
  }
  setup(true);
  let rt; addEventListener("resize", () => { clearTimeout(rt); rt = setTimeout(() => setup(false), 150); });
  matchMedia("(prefers-color-scheme: dark)").addEventListener("change", () => draw(LEVELS));
  cv.parentElement.addEventListener("mousemove", e => {
    const r = cv.getBoundingClientRect();
    const i = Math.round((e.clientX - r.left) / CELL), j = Math.round((e.clientY - r.top) / CELL);
    if (!G || i < 0 || j < 0 || i >= gw || j >= gh) return;
    const m = Math.round(G[j * gw + i] * TOP_M / 10) * 10;
    elev.textContent = m.toLocaleString("en-US").replace(",", " ") + " m";
  });
})();

/* ---------- upload ---------- */
(() => {
  const $ = id => document.getElementById(id);
  const drop = $("drop"), go = $("go"), err = $("error"), prog = $("progress");
  let file = null, timers = [];
  function showError(msg) { err.textContent = msg; err.style.display = msg ? "block" : "none"; }
  function setFile(f) {
    if (!f) return;
    if (!f.type.startsWith("image/")) return showError("That file isn't an image. Choose a JPG, PNG or HEIC photo.");
    file = f; showError("");
    $("pimg").src = URL.createObjectURL(f); $("pname").textContent = f.name;
    $("empty").style.display = "none"; $("preview").style.display = "block"; go.disabled = false;
  }
  $("pick").onchange = e => setFile(e.target.files[0]);
  $("snap").onchange = e => setFile(e.target.files[0]);
  $("change").onclick = e => { e.stopPropagation(); $("pick").click(); };
  drop.addEventListener("click", e => { if (!file && e.target === drop) $("pick").click(); });
  drop.addEventListener("keydown", e => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); $("pick").click(); } });
  ["dragenter", "dragover"].forEach(t => drop.addEventListener(t, e => { e.preventDefault(); drop.classList.add("over"); }));
  ["dragleave", "drop"].forEach(t => drop.addEventListener(t, e => { e.preventDefault(); drop.classList.remove("over"); }));
  drop.addEventListener("drop", e => setFile(e.dataTransfer.files[0]));

  function stage(n) {
    [...prog.children].forEach((li, k) => { li.className = k < n ? "done" : k === n ? "on" : ""; });
  }
  go.onclick = async () => {
    if (!file) return;
    go.disabled = true; showError(""); prog.style.display = "block"; stage(0);
    timers = [setTimeout(() => stage(1), 1800), setTimeout(() => stage(2), 3200)];
    const q = new URLSearchParams({ invert: +$("invert").checked, flip: +$("flip").checked });
    try {
      const r = await fetch("/search?" + q, { method: "POST", body: file,
                                              headers: { "Content-Type": "application/octet-stream" } });
      const j = await r.json().catch(() => ({}));
      if (!r.ok) throw new Error(j.error || "The search stopped unexpectedly. Check the terminal for details.");
      timers.forEach(clearTimeout); stage(3);
      location.href = j.report;
    } catch (e) {
      timers.forEach(clearTimeout); prog.style.display = "none";
      showError(e.message === "Failed to fetch" ? "Can't reach the app. Is app.py still running in the terminal?" : e.message);
      go.disabled = false;
    }
  };
})();
</script>
</body></html>
"""


def render_page(count):
    return (_PAGE.replace("%%FONTS%%", FONTS).replace("%%CSS%%", BASE_CSS)
            .replace("%%MARK%%", MARK_SVG).replace("%%COUNT%%", f"{count:,}"))
