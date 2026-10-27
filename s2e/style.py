"""Shared look for the upload page and the results report: a topographic survey sheet."""

FONTS = ('<link rel="preconnect" href="https://fonts.googleapis.com">'
         '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
         '<link href="https://fonts.googleapis.com/css2?family=Newsreader:ital,opsz,wght@1,6..72,400;1,6..72,500'
         '&family=Schibsted+Grotesk:wght@400;500;600;700;800&display=swap" rel="stylesheet">')

BASE_CSS = r"""
:root {
  --paper: #EDF0EA;        /* map paper, cool */
  --sheet: #F8F9F5;        /* inset panels */
  --ink: #1E2B2F;          /* rock ink */
  --ink-2: #4E5B5C;
  --ink-3: #7A8582;
  --rule: #C9CFC4;
  --contour: #9C6B47;      /* contour brown */
  --contour-soft: #C4A58C;
  --glacier: #2E6E9A;      /* water / action */
  --glacier-deep: #23577B;
  --forest: #5E7D5A;       /* match */
  --error: #A8432F;
  --sans: "Schibsted Grotesk", "Helvetica Neue", Arial, sans-serif;
  --place: "Newsreader", Georgia, serif;
  --radius-s: 6px;
  --radius-m: 10px;
}
@media (prefers-color-scheme: dark) {
  :root {
    --paper: #18211F; --sheet: #1F2A28; --ink: #E4E9E2; --ink-2: #B3BDB5; --ink-3: #85918A;
    --rule: #34403D; --contour: #B48A68; --contour-soft: #5E5246;
    --glacier: #6FA8CF; --glacier-deep: #8BBBDC; --forest: #8FB28A; --error: #E08A76;
  }
}
* { box-sizing: border-box; }
html { -webkit-text-size-adjust: 100%; }
body {
  margin: 0; background: var(--paper); color: var(--ink);
  font: 400 17px/1.55 var(--sans); font-feature-settings: "tnum" 0;
  -webkit-font-smoothing: antialiased;
}
a { color: var(--glacier); text-underline-offset: 3px; text-decoration-thickness: 1px; }
a:hover { color: var(--glacier-deep); }
:focus-visible { outline: 2px solid var(--glacier); outline-offset: 3px; border-radius: 3px; }
.place { font-family: var(--place); font-style: italic; font-weight: 400; }
.num { font-variant-numeric: tabular-nums; }

/* wordmark: two words joined by a contour-like stroke */
.mark { display: inline-flex; align-items: center; gap: 10px; font-weight: 800; font-size: 19px;
        letter-spacing: -0.01em; color: var(--ink); text-decoration: none; }
.mark svg { width: 34px; height: 22px; }

/* map neatline: the double frame printed around every map sheet */
.neatline { position: relative; border: 1px solid var(--ink); padding: 3px; }
.neatline::before { content: ""; position: absolute; inset: 3px; border: 0.5px solid var(--ink-3); pointer-events: none; }

.btn { font: 600 16px/1 var(--sans); border-radius: var(--radius-s); padding: 14px 20px;
       border: 1px solid var(--rule); background: var(--sheet); color: var(--ink); cursor: pointer;
       transition: background .15s, border-color .15s, color .15s; text-decoration: none; display: inline-flex;
       align-items: center; justify-content: center; gap: 8px; }
.btn:hover { border-color: var(--ink-3); color: var(--ink); }
.btn-primary { background: var(--glacier); border-color: var(--glacier); color: #fff; }
.btn-primary:hover { background: var(--glacier-deep); border-color: var(--glacier-deep); color: #fff; }
@media (prefers-color-scheme: dark) { .btn-primary, .btn-primary:hover { color: #0E1A22; } }
.btn:disabled { opacity: .4; cursor: default; }

@media (prefers-reduced-motion: reduce) { * { transition: none !important; animation: none !important; } }
"""

MARK_SVG = ('<svg viewBox="0 0 34 22" aria-hidden="true" fill="none" stroke="currentColor" stroke-linecap="round">'
            '<path d="M2 19c5-1 7-9 15-11s11 6 15 5" stroke-width="2.2"/>'
            '<path d="M8 19c3-1 5-6 9-7s7 3 10 3" stroke-width="1.2" opacity=".55"/>'
            '<path d="M13 19c2 0 3-3 5-3s3 2 5 2" stroke-width="1" opacity=".35"/></svg>')
