#!/usr/bin/env python3
"""
Build script for danskLearn portal.

Reads danskord.html and danskskriv.html, assembles a single-file SPA at index.html.

How it works:
- Each app's <style> block is extracted and every selector is prefixed with
  the view's container id (#view-ord / #view-skriv) so the CSS only applies
  inside that view. Selectors targeting `body` or `header` (the app's own
  fixed header) are rewritten to fit inside the portal shell.
- Each app's body markup (everything inside <body> except <header> and <script>)
  is dropped into its view container.
- Each app's <script> body is wrapped in an IIFE and exposed as
  window.OrdApp.init() / window.SkrivApp.init() so the router can lazy-init
  each view the first time it is shown.
- A shared header, landing page, and tiny hash-based router sit on top.

Re-run this whenever danskord.html or danskskriv.html change.
"""
from __future__ import annotations
import re
import sys
from pathlib import Path

ROOT = Path(__file__).parent
ORD_PATH = ROOT / "danskord.html"
SKRIV_PATH = ROOT / "danskskriv.html"
OUT_PATH = ROOT / "index.html"


def read_source(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def extract_section(src: str, open_tag_re: str, close_tag: str) -> tuple[str, int, int]:
    """Return (inner_text, start_idx, end_idx_exclusive) for the FIRST tag
    matching open_tag_re. start_idx points at the inner content; end_idx points
    at the start of close_tag."""
    m = re.search(open_tag_re, src)
    if not m:
        raise RuntimeError(f"open tag {open_tag_re!r} not found")
    start = m.end()
    end = src.index(close_tag, start)
    return src[start:end], start, end


def extract_style(src: str) -> str:
    inner, _, _ = extract_section(src, r"<style[^>]*>", "</style>")
    return inner


def extract_body_markup(src: str) -> str:
    """Return everything between <body> and </body>, with the trailing
    <script>...</script> removed and the original <header> rewritten into an
    in-view toolbar (`<div class="app-toolbar">...</div>`).

    The portal owns the page-level header now, but each app's <header> carries
    real action controls (Ord's mode-toggle, stat pills, Shuffle/Known/Reset;
    Skriv's Done/Accuracy/Refresh). We keep that markup verbatim — only the
    enclosing tag name changes — so all original IDs/classes the script binds
    to still exist. The `.app-toolbar` CSS in PORTAL_STYLE then lays it out
    without `position: fixed`."""
    body, _, _ = extract_section(src, r"<body[^>]*>", "</body>")
    # Replace the opening <header ...> and closing </header>; everything in
    # between (logo, .header-right, etc.) is preserved.
    body = re.sub(r"<header(\s[^>]*)?>", '<div class="app-toolbar">', body, count=1)
    body = re.sub(r"</header>", "</div>", body, count=1)
    body = re.sub(r"<script[\s\S]*?</script>\s*$", "", body)
    return body.strip()


def extract_script(src: str) -> str:
    """Last <script>...</script> in the file is the app logic."""
    matches = list(re.finditer(r"<script[^>]*>([\s\S]*?)</script>", src))
    if not matches:
        raise RuntimeError("no <script> tag found")
    return matches[-1].group(1).strip()


# ─── CSS scoping ────────────────────────────────────────────────────────────
#
# The plan: split the style sheet into rules and prefix each selector with
# `<scope> ` so the rule only applies inside that view. Special cases:
#
#   * @-rules (@keyframes, @media, @font-face) are kept verbatim. @media wraps
#     ordinary rules whose selectors should still get prefixed; we recurse.
#   * `:root { ... }` declarations apply globally — both apps use the same
#     palette, so we keep one copy at the top of the merged stylesheet and
#     drop the per-view :root blocks.
#   * Selectors starting with `body` are rewritten to attach to the portal's
#     <body class="..."> via the scope id, e.g. `body.mode-kids .x` ->
#     `body.dansklearn-kids #view-ord .x`. The Ord app toggles
#     `document.body.classList` between {`mode-words`, `mode-verbs`,
#     `mode-kids`}; we keep that exact behaviour but rename `mode-kids` ->
#     `dansklearn-kids` only when it would otherwise leak across views.
#     Actually simpler: leave `body.mode-kids` alone in the JS and in CSS,
#     because mode-kids is Ord-specific. The risk is only if Skriv had a
#     `body.something` rule that collided — it doesn't.
#   * Selectors that match the app's own fixed `header` are dropped — the
#     portal owns the header.
#   * `:root` style is preserved once globally (taken from danskord since it
#     is the superset).

AT_RULE_RE = re.compile(r"@[a-zA-Z-]+")


def split_top_level(css: str) -> list[str]:
    """Split a CSS source into top-level chunks, where each chunk is either a
    @-rule (with its braces) or a `selector { ... }` rule. Preserves order."""
    chunks: list[str] = []
    i = 0
    n = len(css)
    while i < n:
        # skip whitespace
        while i < n and css[i].isspace():
            i += 1
        if i >= n:
            break
        # comment
        if css.startswith("/*", i):
            end = css.index("*/", i + 2) + 2
            chunks.append(css[i:end])
            i = end
            continue
        # find the matching opening brace at depth 0
        depth = 0
        start = i
        while i < n:
            c = css[i]
            if c == "{":
                depth = 1
                i += 1
                # consume balanced body
                while i < n and depth > 0:
                    if css.startswith("/*", i):
                        i = css.index("*/", i + 2) + 2
                        continue
                    if css[i] == "{":
                        depth += 1
                    elif css[i] == "}":
                        depth -= 1
                    i += 1
                chunks.append(css[start:i].strip())
                break
            i += 1
        else:
            # ran off the end without finding a brace
            tail = css[start:].strip()
            if tail:
                chunks.append(tail)
            break
    return chunks


def prefix_selector_list(selectors: str, scope: str) -> str:
    """Apply `scope` to each comma-separated selector in `selectors`."""
    out: list[str] = []
    for sel in selectors.split(","):
        sel = sel.strip()
        if not sel:
            continue
        out.append(prefix_one_selector(sel, scope))
    return ", ".join(out)


def prefix_one_selector(sel: str, scope: str) -> str:
    """Rewrite a single selector to be confined under `scope` (the view id).

    Special case: each app's `header` rule is retargeted at `.app-toolbar`,
    matching the rewritten body markup (see `extract_body_markup`)."""
    # Translate any leading `header` token to `.app-toolbar`.
    sel = re.sub(r"(^|[\s>+~,])header(?=$|[\s>+~,.:#\[])", r"\1.app-toolbar", sel)

    if sel.startswith("body"):
        # `body.x .y` -> `body.x scope .y`
        head_match = re.match(r"body(\.[A-Za-z0-9_\-]+)*(?:#[A-Za-z0-9_\-]+)?", sel)
        head = head_match.group(0)
        rest = sel[len(head):]
        rest = rest.lstrip()
        if rest:
            return f"{head} {scope} {rest}"
        return f"{head} {scope}"

    # plain selector — prepend scope
    return f"{scope} {sel}"


def scope_css(css: str, scope: str, *, drop_root: bool) -> str:
    """Return css rewritten so every rule is constrained to `scope`.

    Args:
        css: raw stylesheet text (the inner of a <style> tag).
        scope: e.g. "#view-ord".
        drop_root: when True, `:root { ... }` rules are removed (because the
            shared :root is emitted separately).
    """
    out: list[str] = []
    for chunk in split_top_level(css):
        if chunk.startswith("/*"):
            continue
        if chunk.startswith("@"):
            out.append(handle_at_rule(chunk, scope, drop_root=drop_root))
            continue
        # `selector-list { body }`
        brace = chunk.index("{")
        selectors = chunk[:brace].strip()
        body = chunk[brace:]  # includes braces
        if selectors == ":root":
            if drop_root:
                continue
            out.append(chunk)
            continue
        prefixed = prefix_selector_list(selectors, scope)
        out.append(prefixed + " " + body)
    return "\n".join(out)


def handle_at_rule(chunk: str, scope: str, *, drop_root: bool) -> str:
    head_match = re.match(r"@[a-zA-Z-]+", chunk)
    name = head_match.group(0) if head_match else "@?"
    if name in ("@keyframes", "@-webkit-keyframes", "@font-face", "@charset", "@import"):
        return chunk  # leave as-is
    if name == "@media":
        # Recurse into the body so its inner rules are scoped.
        prelude_end = chunk.index("{")
        prelude = chunk[:prelude_end].rstrip()
        inner = chunk[prelude_end + 1 : chunk.rfind("}")]
        scoped_inner = scope_css(inner, scope, drop_root=drop_root)
        return prelude + " {\n" + scoped_inner + "\n}"
    if name == "@supports":
        prelude_end = chunk.index("{")
        prelude = chunk[:prelude_end].rstrip()
        inner = chunk[prelude_end + 1 : chunk.rfind("}")]
        return prelude + " {\n" + scope_css(inner, scope, drop_root=drop_root) + "\n}"
    return chunk


# ─── Build the merged document ──────────────────────────────────────────────

PORTAL_HEAD = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>danskLearn — Learn Danish</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=DM+Serif+Display:ital@0;1&family=Fredoka:wght@500;600;700&family=Inter:wght@300;400;500;600&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
"""

# Shared CSS: palette + portal header + landing page + view container.
PORTAL_STYLE = r"""
<style id="portal-style">
:root {
  --bg: #0e1117;
  --surface: #161b26;
  --sidebar-bg: #12171f;
  --card-front: #1c2333;
  --card-back: #1a2744;
  --card: #1c2333;
  --card-alt: #1a2744;
  --border: #2a3347;
  --accent: #4f8ef7;
  --accent2: #7dd3fc;
  --text: #e8edf5;
  --text-muted: #8896ae;
  --text-dim: #4a5568;
  --success: #4ade80;
  --danger: #f87171;
  --radius: 12px;
  --card-radius: 16px;
  --sidebar-w: 220px;
  --header-h: 58px;
  --toolbar-h: 52px;
  --total-h: calc(var(--header-h) + var(--toolbar-h)); /* portal header + per-app toolbar */
}
* { box-sizing: border-box; margin: 0; padding: 0; }
body {
  background: var(--bg);
  color: var(--text);
  font-family: 'Inter', sans-serif;
  font-size: 15px;
  line-height: 1.6;
  min-height: 100vh;
}

/* ─── PORTAL HEADER ────────────────────────────────────────────── */
.portal-header {
  height: var(--header-h);
  border-bottom: 1px solid var(--border);
  padding: 0 24px;
  display: flex;
  align-items: center;
  gap: 18px;
  position: fixed;
  top: 0; left: 0; right: 0;
  background: rgba(14,17,23,0.95);
  backdrop-filter: blur(12px);
  z-index: 200;
}
.portal-logo {
  font-family: 'DM Serif Display', serif;
  font-size: 22px;
  letter-spacing: -0.5px;
  color: var(--text);
  cursor: pointer;
  user-select: none;
  flex-shrink: 0;
}
.portal-logo span { color: var(--accent); }
.portal-nav { display: flex; gap: 4px; flex: 1; }
.portal-nav a {
  font-family: 'Inter', sans-serif;
  font-size: 13px;
  color: var(--text-muted);
  text-decoration: none;
  padding: 6px 14px;
  border-radius: 18px;
  border: 1px solid transparent;
  transition: all 0.15s;
}
.portal-nav a:hover { color: var(--accent); border-color: var(--border); }
.portal-nav a.active { color: var(--accent); border-color: var(--accent); background: rgba(79,142,247,0.07); }

/* ─── KIDS-MODE OVERRIDES ON PORTAL CHROME ─────────────────────── */
body.mode-kids .portal-header { background: rgba(255,255,255,0.92); border-bottom: 2px solid #ffd9a8; }
body.mode-kids .portal-logo, body.mode-kids .portal-logo span { color: #ff7a59; }
body.mode-kids .portal-nav a { color: #6b5b8a; font-family: 'Fredoka', sans-serif; font-weight: 500; }
body.mode-kids .portal-nav a:hover { color: #ff7a59; border-color: #ffd9a8; }
body.mode-kids .portal-nav a.active { color: #ff7a59; border-color: #ff7a59; background: #fff0e0; }

/* ─── LANDING PAGE ─────────────────────────────────────────────── */
#view-home {
  margin-top: var(--header-h);
  padding: 48px 24px 80px;
  max-width: 980px;
  margin-left: auto;
  margin-right: auto;
}
.landing-hero { padding: 12px 4px 32px; }
.landing-hero h1 {
  font-family: 'DM Serif Display', serif;
  font-size: 38px;
  font-weight: 400;
  letter-spacing: -0.5px;
  margin-bottom: 8px;
}
.landing-hero h1 span { color: var(--accent); }
.landing-hero p { color: var(--text-muted); font-size: 15px; max-width: 600px; }

.module-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 18px;
  margin-top: 8px;
}
.module-card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--card-radius);
  padding: 22px 22px 20px;
  text-decoration: none;
  color: inherit;
  display: flex;
  flex-direction: column;
  gap: 10px;
  transition: border-color 0.18s, transform 0.18s, box-shadow 0.18s;
  cursor: pointer;
  position: relative;
  overflow: hidden;
}
.module-card:hover {
  border-color: var(--accent);
  transform: translateY(-2px);
  box-shadow: 0 8px 28px rgba(0,0,0,0.35);
}
.module-card.disabled {
  opacity: 0.5;
  cursor: not-allowed;
  pointer-events: none;
}
.module-card-head { display: flex; align-items: center; gap: 12px; }
.module-icon { font-size: 28px; line-height: 1; }
.module-title {
  font-family: 'DM Serif Display', serif;
  font-size: 22px;
  color: var(--text);
}
.module-title span { color: var(--accent); }
.module-desc {
  color: var(--text-muted);
  font-size: 13px;
  line-height: 1.55;
  flex: 1;
}
.module-stat {
  display: flex;
  align-items: baseline;
  gap: 8px;
  font-family: 'JetBrains Mono', monospace;
  font-size: 11px;
  color: var(--text-dim);
  border-top: 1px solid var(--border);
  padding-top: 12px;
  margin-top: 4px;
}
.module-stat b {
  font-family: 'JetBrains Mono', monospace;
  color: var(--accent2);
  font-weight: 500;
  font-size: 13px;
}
.module-stat .pct {
  margin-left: auto;
  color: var(--accent);
}
.module-progress {
  height: 3px;
  background: var(--border);
  border-radius: 3px;
  overflow: hidden;
  margin-top: 8px;
}
.module-progress > div {
  height: 100%;
  background: linear-gradient(90deg, var(--accent), var(--accent2));
  border-radius: 3px;
  transition: width 0.4s ease;
}
.module-card .coming-soon {
  position: absolute;
  top: 14px; right: 14px;
  font-family: 'JetBrains Mono', monospace;
  font-size: 9px;
  letter-spacing: 1.2px;
  text-transform: uppercase;
  color: var(--text-dim);
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 2px 8px;
}

.section-label {
  font-family: 'JetBrains Mono', monospace;
  font-size: 11px;
  letter-spacing: 1.4px;
  text-transform: uppercase;
  color: var(--text-dim);
  margin: 36px 0 14px;
}

/* ─── VIEW CONTAINERS ──────────────────────────────────────────── */
.view { display: none; }
.view.active { display: block; }

/* When inside Ord/Skriv views, push top-level content past the portal header.
   The original apps used `margin-top: var(--header-h)` on .shell and .main; since
   the portal header occupies that same space we keep their offsets intact. */
@media (max-width: 700px) {
  .portal-header { padding: 0 14px; gap: 10px; }
  .portal-nav a { padding: 5px 10px; font-size: 12px; }
  .landing-hero h1 { font-size: 30px; }
  #view-home { padding: 32px 14px 60px; }
}
</style>
"""

# Layout adjustments emitted AFTER the per-app scoped styles so they win on
# specificity/order. The merged document has two stacked bars (portal header
# above, per-app toolbar below); the original apps assumed only their own
# header existed at the top — these rules retarget their offsets at
# `--total-h` and stop hidden views from leaking fixed-position chrome.
LAYOUT_FIXES = r"""
<style id="layout-fixes">
/* The per-app `body { ... }` rules became `body #view-ord { ... }` and
   `body #view-skriv { ... }`. They include `display: flex` etc. which
   would override .view's display:none. Force the view on/off explicitly. */
.view { display: none !important; }
.view.active { display: block !important; }
/* Ord's body wanted a column flex layout — restore it only when active. */
#view-ord.active { display: flex !important; flex-direction: column; min-height: 100vh; }

/* App toolbars sit immediately below the portal header (which is var(--header-h) tall).
   Use the same compound specificity as the rewritten per-app `header` rule
   (`#view-ord .app-toolbar`, etc.) so we override its `top: 0` and z-index.

   Visual treatment: a slightly lighter surface, a hairline top highlight, and
   a soft shadow underneath so the toolbar reads as a distinct plane floating
   below the portal header rather than welding into it. */
#view-ord .app-toolbar,
#view-skriv .app-toolbar {
  position: fixed;
  top: var(--header-h);
  left: 0; right: 0;
  height: 52px;
  z-index: 150;
  background: linear-gradient(180deg, #1a2030 0%, #161b26 100%);
  border-bottom: 1px solid var(--border);
  box-shadow:
    inset 0 1px 0 rgba(255,255,255,0.04),  /* hairline highlight along seam */
    0 6px 16px rgba(0,0,0,0.35);            /* soft drop below */
  backdrop-filter: none;  /* override the original blur — we use solid surface */
}

/* Kids-mode parity: match the warmer palette so the toolbar still reads as a
   distinct surface against the cream/peach background. */
body.mode-kids #view-ord .app-toolbar {
  background: linear-gradient(180deg, #fff7ec 0%, #fff0e0 100%);
  border-bottom: 2px solid #ffd9a8;
  box-shadow:
    inset 0 1px 0 rgba(255,255,255,0.6),
    0 4px 12px rgba(255,154,122,0.18);
}


/* Original layout offsets used --header-h to clear the (now-portal) header,
   but a second fixed bar (the toolbar) sits below it. Bump them to --total-h. */
#view-ord .shell { margin-top: var(--total-h); }
#view-ord .sidebar { top: var(--total-h); }
#view-ord .topbar { top: var(--total-h); }
#view-ord .progress-bar-wrap { /* keeps natural flow under .topbar */ }
#view-skriv .main { margin-top: var(--total-h); }

/* Hide each app's toolbar when its view isn't active (toolbars are
   position:fixed so visibility doesn't follow display:none ancestors
   when display is set on the ancestor itself, but does when toolbars
   live inside a display:none subtree — which they do here. This rule is
   belt-and-suspenders.) */
.view:not(.active) .app-toolbar { display: none !important; }

/* Inside the toolbar the original CSS used the danskord `header` declarations
   for layout: `display:flex; align-items:center; justify-content:space-between; padding:0 24px;
   border-bottom:1px solid var(--border); background: rgba(14,17,23,0.95); backdrop-filter: blur(12px);`
   These transferred via the `header -> .app-toolbar` selector rewrite, so the
   toolbar already has the right look. Skriv's header had nearly identical
   declarations so it does too. */
</style>
"""

PORTAL_HEADER_AND_LANDING = r"""
<header class="portal-header">
  <div class="portal-logo" onclick="location.hash='#/'">dansk<span>learn</span></div>
  <nav class="portal-nav">
    <a href="#/" data-route="home">Home</a>
    <a href="#/ord" data-route="ord">Ord</a>
    <a href="#/skriv" data-route="skriv">Skriv</a>
  </nav>
</header>

<section id="view-home" class="view">
  <div class="landing-hero">
    <h1>dansk<span>learn</span></h1>
    <p>A growing portal for learning Danish — vocabulary, writing, and more on the way. Pick a module below to start, or jump back in where you left off.</p>
  </div>

  <div class="section-label">Modules</div>
  <div class="module-grid">
    <a class="module-card" href="#/ord">
      <div class="module-card-head">
        <div class="module-icon">📚</div>
        <div class="module-title">dansk<span>ord</span></div>
      </div>
      <div class="module-desc">Flashcards for the 1000 most essential Danish words, plus verb conjugations and a kids-friendly mode for ages 5–7.</div>
      <div class="module-stat">
        <span>Known</span><b id="snap-ord-known">—</b>
        <span class="pct" id="snap-ord-pct">0%</span>
      </div>
      <div class="module-progress"><div id="snap-ord-fill" style="width:0%"></div></div>
    </a>
    <a class="module-card" href="#/skriv">
      <div class="module-card-head">
        <div class="module-icon">✍️</div>
        <div class="module-title">dansk<span>skriv</span></div>
      </div>
      <div class="module-desc">Type along with fresh Danish news and culture paragraphs. Live colouring catches mistakes; tap any word for an instant English translation.</div>
      <div class="module-stat">
        <span>Done</span><b id="snap-skriv-done">—</b>
        <span class="pct" id="snap-skriv-pct">0%</span>
      </div>
      <div class="module-progress"><div id="snap-skriv-fill" style="width:0%"></div></div>
    </a>
    <div class="module-card disabled">
      <span class="coming-soon">Soon</span>
      <div class="module-card-head">
        <div class="module-icon">🗣️</div>
        <div class="module-title">dansk<span>tale</span></div>
      </div>
      <div class="module-desc">Speaking practice — pronounce phrases out loud and get instant feedback on your accent and rhythm.</div>
    </div>
    <div class="module-card disabled">
      <span class="coming-soon">Soon</span>
      <div class="module-card-head">
        <div class="module-icon">👂</div>
        <div class="module-title">dansk<span>hør</span></div>
      </div>
      <div class="module-desc">Listening drills — short Danish audio clips with comprehension questions, drawn from real radio and podcasts.</div>
    </div>
  </div>
</section>
"""

PORTAL_FOOTER_SCRIPT = r"""
<script>
// ─── Hash router ─────────────────────────────────────────────────
const Routes = {
  '': 'home', '/': 'home',
  '/ord': 'ord',
  '/skriv': 'skriv',
};
function currentRoute() {
  const h = location.hash.replace(/^#/, '') || '/';
  return Routes[h] || 'home';
}
function setActiveView(name) {
  document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));
  const target = document.getElementById('view-' + name);
  if (target) target.classList.add('active');
  document.querySelectorAll('.portal-nav a').forEach(a => {
    a.classList.toggle('active', a.dataset.route === name);
  });
  if (name === 'ord' && window.OrdApp) window.OrdApp.init();
  if (name === 'skriv' && window.SkrivApp) window.SkrivApp.init();
  if (name === 'home') refreshLandingSnapshot();
  // Kids-mode body class only makes sense inside Ord. Strip it when leaving.
  if (name !== 'ord') {
    document.body.classList.remove('mode-words', 'mode-verbs', 'mode-kids');
  }
}
window.addEventListener('hashchange', () => setActiveView(currentRoute()));

// ─── Landing-page progress snapshot ──────────────────────────────
function refreshLandingSnapshot() {
  // Ord — sum known counts across all three Ord modes (words / verbs / kids).
  const ordKeys = [
    { storage: 'dk-known',       totalApprox: 1000 },
    { storage: 'dk-known-verbs', totalApprox: 80   },
    { storage: 'dk-known-kids',  totalApprox: 200  },
  ];
  let ordKnown = 0, ordTotal = 0;
  for (const k of ordKeys) {
    try {
      const arr = JSON.parse(localStorage.getItem(k.storage) || '[]');
      ordKnown += Array.isArray(arr) ? arr.length : 0;
    } catch (_) { /* ignore */ }
    ordTotal += k.totalApprox;
  }
  const ordPct = ordTotal ? Math.round((ordKnown / ordTotal) * 100) : 0;
  setText('snap-ord-known', `${ordKnown} / ${ordTotal}`);
  setText('snap-ord-pct', ordPct + '%');
  setWidth('snap-ord-fill', ordPct + '%');

  // Skriv — count cards in current session whose typed text matches the target.
  let skrivDone = 0, skrivTotal = 0;
  try {
    const raw = localStorage.getItem('danskskriv:session:v1');
    if (raw) {
      const s = JSON.parse(raw);
      if (s && Array.isArray(s.paragraphs) && Array.isArray(s.typed)) {
        skrivTotal = s.paragraphs.length;
        for (let i = 0; i < skrivTotal; i++) {
          if ((s.typed[i] || '') === s.paragraphs[i]) skrivDone++;
        }
      }
    }
  } catch (_) { /* ignore */ }
  if (!skrivTotal) skrivTotal = 5;
  const skrivPct = skrivTotal ? Math.round((skrivDone / skrivTotal) * 100) : 0;
  setText('snap-skriv-done', `${skrivDone} / ${skrivTotal}`);
  setText('snap-skriv-pct', skrivPct + '%');
  setWidth('snap-skriv-fill', skrivPct + '%');
}
function setText(id, v)  { const el = document.getElementById(id); if (el) el.textContent = v; }
function setWidth(id, w) { const el = document.getElementById(id); if (el) el.style.width  = w; }

// ─── Boot ────────────────────────────────────────────────────────
setActiveView(currentRoute());
</script>
"""


## Functions called from inline `onclick="..."` markup in each app's body.
## These need to be addressable on `window` once the app script runs, because
## inline event attributes resolve identifiers against `window`, not against
## any IIFE closure they happen to live in. (Listing harvested with
## `grep -oE 'onclick="[^"]+"' danskord.html`.)
INLINE_ONCLICK_EXPORTS = {
    "ord": [
        "setMode",
        "shuffle",
        "toggleKnownFilter",
        "openResetModal",
        "closeResetModal",
        "confirmReset",
        "flipAll",
    ],
    "skriv": [],  # uses addEventListener exclusively
}


def wrap_app_script(name: str, script_body: str) -> str:
    """Wrap the original app script in an IIFE that exposes
    window.{Name}App.init() plus any names the original markup expects to
    find on `window` (inline-onclick handlers).

    Init is gated by a flag so the router can call it on every view-switch
    cheaply. Globals (`setMode`, `flipAll`, etc.) are written onto `window`
    inside `init` rather than at IIFE construction time, because in the
    original scripts they are top-level `function` declarations that hoist
    inside the IIFE — they don't exist on window unless we explicitly
    forward them.
    """
    namespace = name.capitalize() + "App"
    exports = INLINE_ONCLICK_EXPORTS.get(name, [])
    forward_lines = "\n      ".join(
        f"if (typeof {fn} === 'function') window.{fn} = {fn};"
        for fn in exports
    )
    forward_block = ("// Expose inline-onclick targets on window.\n      " + forward_lines) if forward_lines else ""
    return f"""
<script>
window.{namespace} = (function () {{
  let initialized = false;
  return {{
    init() {{
      if (initialized) return;
      initialized = true;
      // ─── BEGIN {name} app code ───
      {script_body}
      // ─── END {name} app code ───
      {forward_block}
    }}
  }};
}})();
</script>
""".lstrip()


def build() -> None:
    ord_src = read_source(ORD_PATH)
    skriv_src = read_source(SKRIV_PATH)

    # Extract pieces
    ord_style = extract_style(ord_src)
    ord_body = extract_body_markup(ord_src)
    ord_script = extract_script(ord_src)

    skriv_style = extract_style(skriv_src)
    skriv_body = extract_body_markup(skriv_src)
    skriv_script = extract_script(skriv_src)

    # Scope the per-app stylesheets
    ord_style_scoped = scope_css(ord_style, "#view-ord", drop_root=True)
    skriv_style_scoped = scope_css(skriv_style, "#view-skriv", drop_root=True)

    parts = [
        PORTAL_HEAD,
        PORTAL_STYLE,
        f'<style id="ord-style">\n{ord_style_scoped}\n</style>',
        f'<style id="skriv-style">\n{skriv_style_scoped}\n</style>',
        LAYOUT_FIXES,
        "</head>",
        "<body>",
        PORTAL_HEADER_AND_LANDING,
        f'<section id="view-ord" class="view">\n{ord_body}\n</section>',
        f'<section id="view-skriv" class="view">\n{skriv_body}\n</section>',
        wrap_app_script("ord", ord_script),
        wrap_app_script("skriv", skriv_script),
        PORTAL_FOOTER_SCRIPT,
        "</body>",
        "</html>",
    ]

    OUT_PATH.write_text("\n".join(parts), encoding="utf-8")
    print(f"Built {OUT_PATH} ({OUT_PATH.stat().st_size:,} bytes)")


if __name__ == "__main__":
    try:
        build()
    except Exception as exc:
        print(f"Build failed: {exc}", file=sys.stderr)
        sys.exit(1)
