#!/usr/bin/env python3
"""
Build script for danskLearn portal.

Reads five standalone .html source files and assembles a single-file SPA at
index.html. Each source file is also runnable on its own in a browser.

How it works:
- Each source's <style> is extracted and every selector is prefixed with the
  view's container id (#view-X) so the CSS only applies inside that view.
  Selectors targeting `body` or `header` (the source's own fixed header) are
  rewritten to fit inside the portal shell.
- Each source's body markup (everything inside <body> except <script>) is
  dropped into its view container, with the original <header>...</header>
  rewritten to <div class="app-toolbar">...</div>.
- Each source's last <script> body is wrapped in an IIFE and exposed as
  window.{Name}App.init() so the router can lazy-init each view the first
  time it is shown.
- phrases.js is inlined ONCE before the per-app scripts so the shared phrase
  bank (window.DanskPhrases.BANK) is available to dansktale and danskhor
  without duplication.
- A shared header, landing page, and tiny history-based router sit on top.

Re-run this whenever any of the source .html files or phrases.js change.
"""
from __future__ import annotations
import re
import sys
from pathlib import Path

ROOT = Path(__file__).parent
SRC = ROOT / "src"
ORD_PATH       = SRC / "danskord.html"
SKRIV_PATH     = SRC / "danskskriv.html"
OVERSET_PATH   = SRC / "danskoverset.html"
TALE_PATH      = SRC / "dansktale.html"
HOR_PATH       = SRC / "danskhor.html"
PHRASES_PATH   = SRC / "phrases.js"
OUT_PATH       = ROOT / "index.html"
NOT_FOUND_PATH = ROOT / "404.html"


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
    """Return everything between <body> and </body>, with all <script> tags
    removed (both `<script src="...">` and inline) and the original <header>
    rewritten into an in-view toolbar (`<div class="app-toolbar">...</div>`).

    The portal owns the page-level header now, but each app's <header> carries
    real action controls (Ord's mode-toggle, stat pills, Shuffle/Known/Reset;
    Skriv's Done/Accuracy/Refresh; etc.). We keep that markup verbatim — only
    the enclosing tag name changes — so all original IDs/classes the script
    binds to still exist. The `.app-toolbar` CSS in LAYOUT_FIXES then lays it
    out without `position: fixed`.

    All <script> tags (including <script src="phrases.js">) are stripped here.
    The last inline script per source file is reattached separately by
    `extract_script` and wrapped in an IIFE; phrases.js is inlined once
    globally."""
    body, _, _ = extract_section(src, r"<body[^>]*>", "</body>")
    # Strip HTML comments FIRST so that comment content like `<script>`
    # references don't trip up the script-stripping regex below. (HTML
    # parsers respect `<!-- -->` boundaries; regex doesn't, so we have
    # to remove comments before applying tag-shaped patterns.)
    body = re.sub(r"<!--[\s\S]*?-->", "", body)
    # Replace the opening <header ...> and closing </header>; everything in
    # between (logo, .header-right, etc.) is preserved.
    body = re.sub(r"<header(\s[^>]*)?>", '<div class="app-toolbar">', body, count=1)
    body = re.sub(r"</header>", "</div>", body, count=1)
    # Strip ALL <script> tags from the body — both `<script src="...">` and
    # inline `<script>...</script>`. The dansktale/danskhor sources have a
    # `<script src="phrases.js">` tag that would otherwise leak through.
    body = re.sub(r"<script\b[^>]*>[\s\S]*?</script>", "", body)
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
<meta name="description" content="Learn Danish with flashcards, typing practice, translation, speaking, and listening exercises — five modules in one free portal.">
<link rel="canonical" href="https://swapnild2111.github.io/dansklearn/">
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
  text-decoration: none;
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

#portal-kids-toggle {
  flex-shrink: 0;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-family: 'Fredoka', sans-serif;
  font-weight: 700;
  font-size: 13px;
  padding: 7px 16px;
  border-radius: 22px;
  border: 2px solid #ffb84d;
  background: linear-gradient(135deg, #fff8d4 0%, #ffd966 45%, #ff9a7a 100%);
  color: #8a3a12;
  cursor: pointer;
  white-space: nowrap;
  box-shadow:
    0 2px 0 #e8a030,
    0 4px 14px rgba(255, 154, 122, 0.45);
  animation: kidsToggleGlow 2.4s ease-in-out infinite;
  transition: transform 0.12s, box-shadow 0.15s, filter 0.15s;
}
#portal-kids-toggle .kids-star {
  color: #ff5a20;
  font-size: 16px;
  line-height: 1;
  text-shadow: 0 0 1px #fff, 0 1px 3px rgba(138, 58, 18, 0.45);
}
#portal-kids-toggle:hover {
  transform: translateY(-2px) scale(1.04);
  filter: brightness(1.05);
  box-shadow:
    0 3px 0 #e8a030,
    0 8px 22px rgba(255, 122, 89, 0.55);
}
#portal-kids-toggle:active {
  transform: translateY(1px) scale(0.98);
  box-shadow: 0 1px 0 #e8a030, 0 3px 10px rgba(255, 154, 122, 0.35);
}
@keyframes kidsToggleGlow {
  0%, 100% { box-shadow: 0 2px 0 #e8a030, 0 4px 14px rgba(255, 154, 122, 0.4); }
  50%      { box-shadow: 0 2px 0 #e8a030, 0 4px 20px rgba(255, 122, 89, 0.65), 0 0 0 4px rgba(255, 184, 77, 0.25); }
}
body.portal-kids #portal-kids-toggle {
  border-color: #ff7a59;
  background: linear-gradient(135deg, #ff9a7a, #ff7a59);
  color: #fff;
  animation: kidsToggleOn 2s ease-in-out infinite;
  box-shadow: 0 3px 0 #d85a3a, 0 6px 20px rgba(255, 122, 89, 0.5);
}
body.portal-kids #portal-kids-toggle:hover {
  color: #fff;
  filter: brightness(1.08);
  box-shadow: 0 4px 0 #d85a3a, 0 10px 26px rgba(255, 122, 89, 0.6);
}
body.portal-kids #portal-kids-toggle:active {
  box-shadow: 0 1px 0 #d85a3a, 0 4px 12px rgba(255, 122, 89, 0.4);
}
@keyframes kidsToggleOn {
  0%, 100% { box-shadow: 0 3px 0 #d85a3a, 0 6px 18px rgba(255, 122, 89, 0.45); }
  50%      { box-shadow: 0 3px 0 #d85a3a, 0 6px 24px rgba(255, 122, 89, 0.7), 0 0 0 5px rgba(255, 122, 89, 0.2); }
}
@media (prefers-reduced-motion: reduce) {
  #portal-kids-toggle,
  body.portal-kids #portal-kids-toggle { animation: none; }
}

/* ─── KIDS-MODE OVERRIDES ON PORTAL CHROME ─────────────────────── */
body.portal-kids .portal-header,
body.mode-kids .portal-header { background: rgba(255,255,255,0.92); border-bottom: 2px solid #ffd9a8; }
body.portal-kids .portal-logo,
body.mode-kids .portal-logo {
  font-family: 'Fredoka', sans-serif;
  font-weight: 700;
  color: #2d2a4a;
  letter-spacing: 0;
}
body.portal-kids .portal-logo span,
body.mode-kids .portal-logo span { color: #ff7a59; }
body.portal-kids .portal-nav a,
body.mode-kids .portal-nav a { color: #6b5b8a; font-family: 'Fredoka', sans-serif; font-weight: 500; }
body.portal-kids .portal-nav a:hover,
body.mode-kids .portal-nav a:hover { color: #ff7a59; border-color: #ffd9a8; }
body.portal-kids .portal-nav a.active,
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

/* ─── PORTAL FOOTER (home view only) ─────────────────────────── */
.portal-footer {
  margin-top: 60px;
  padding: 24px 0 8px;
  border-top: 1px solid var(--border);
  text-align: center;
  color: var(--text-dim);
  font-size: 12px;
  line-height: 1.6;
}
.portal-footer p { margin: 2px 0; }
.portal-footer .footer-sub { color: var(--text-dim); opacity: 0.75; font-size: 11px; }

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

# Portal-wide kids theme — same playful palette as Ord's kids mode, applied to
# every module when the home-page toggle is on.
PORTAL_KIDS_STYLE = r"""
<style id="portal-kids-style">
body.portal-kids {
  background: linear-gradient(180deg, #fff8e7 0%, #ffe9f0 100%);
  color: #2d2a4a;
}

/* ── Home ─────────────────────────────────────────────────────── */
body.portal-kids #view-home { background: transparent; }
body.portal-kids .landing-hero h1 { font-family: 'Fredoka', sans-serif; font-weight: 700; color: #2d2a4a; }
body.portal-kids .landing-hero h1 span { color: #ff7a59; }
body.portal-kids .landing-hero p { color: #6b5b8a; font-family: 'Fredoka', sans-serif; font-weight: 500; }
body.portal-kids .section-label { color: #b8a0c0; font-family: 'Fredoka', sans-serif; font-weight: 600; letter-spacing: 1px; }
body.portal-kids .module-card {
  background: #fff;
  border: 3px solid #ffd9a8;
  border-radius: 22px;
  box-shadow: 0 4px 0 #ffd9a8, 0 8px 20px rgba(255,154,122,0.12);
}
body.portal-kids .module-card:hover {
  border-color: #ff7a59;
  transform: translateY(-3px);
  box-shadow: 0 6px 0 #ffd9a8, 0 12px 28px rgba(255,154,122,0.22);
}
body.portal-kids .module-title { font-family: 'Fredoka', sans-serif; font-weight: 700; color: #2d2a4a; }
body.portal-kids .module-title span { color: #ff7a59; }
body.portal-kids .module-desc { color: #6b5b8a; font-family: 'Fredoka', sans-serif; font-size: 14px; }
body.portal-kids .module-stat { border-top-color: #ffe9d4; color: #b8a0c0; font-family: 'Fredoka', sans-serif; }
body.portal-kids .module-stat b { color: #ff7a59; font-family: 'Fredoka', sans-serif; font-weight: 700; }
body.portal-kids .module-stat .pct { color: #ff7a59; }
body.portal-kids .module-progress { background: #ffe9d4; height: 8px; border-radius: 8px; }
body.portal-kids .module-progress > div { background: linear-gradient(90deg, #ff9a7a, #ff7a59); border-radius: 8px; }
body.portal-kids .portal-footer { border-top-color: #ffd9a8; color: #b8a0c0; font-family: 'Fredoka', sans-serif; }

body.portal-kids #view-ord { background: transparent; color: #2d2a4a; }

/* ── Shared module chrome (Skriv, Oversæt, Tale, Hør) ─────────── */
body.portal-kids #view-skriv,
body.portal-kids #view-overset,
body.portal-kids #view-tale,
body.portal-kids #view-hor {
  background: transparent;
  color: #2d2a4a;
}
body.portal-kids #view-skriv .app-toolbar,
body.portal-kids #view-overset .app-toolbar,
body.portal-kids #view-tale .app-toolbar,
body.portal-kids #view-hor .app-toolbar,
body.portal-kids #view-ord .app-toolbar {
  background: rgba(255,255,255,0.92) !important;
  border-bottom: 2px solid #ffd9a8 !important;
  box-shadow: none !important;
}
body.portal-kids #view-skriv .app-toolbar .logo,
body.portal-kids #view-overset .app-toolbar .logo,
body.portal-kids #view-tale .app-toolbar .logo,
body.portal-kids #view-hor .app-toolbar .logo,
body.portal-kids #view-ord .app-toolbar .logo,
body.mode-kids #view-ord .app-toolbar .logo {
  font-family: 'Fredoka', sans-serif;
  font-weight: 700;
  color: #2d2a4a;
  letter-spacing: 0;
}
body.portal-kids #view-skriv .app-toolbar .logo span,
body.portal-kids #view-overset .app-toolbar .logo span,
body.portal-kids #view-tale .app-toolbar .logo span,
body.portal-kids #view-hor .app-toolbar .logo span,
body.portal-kids #view-ord .app-toolbar .logo span,
body.mode-kids #view-ord .app-toolbar .logo span { color: #ff7a59; }
body.portal-kids #view-skriv .app-toolbar .stat-pill,
body.portal-kids #view-overset .app-toolbar .stat-pill,
body.portal-kids #view-tale .app-toolbar .stat-pill,
body.portal-kids #view-hor .app-toolbar .stat-pill {
  background: #fff;
  border-color: #ffd9a8;
  color: #6b5b8a;
  font-family: 'Fredoka', sans-serif;
  font-weight: 500;
}
body.portal-kids #view-skriv .app-toolbar .stat-pill b,
body.portal-kids #view-overset .app-toolbar .stat-pill b,
body.portal-kids #view-tale .app-toolbar .stat-pill b,
body.portal-kids #view-hor .app-toolbar .stat-pill b { color: #ff7a59; }
body.portal-kids #view-skriv .app-toolbar .btn,
body.portal-kids #view-overset .app-toolbar .btn,
body.portal-kids #view-tale .app-toolbar .btn,
body.portal-kids #view-hor .app-toolbar .btn {
  background: #fff;
  border-color: #ffd9a8;
  color: #6b5b8a;
  font-family: 'Fredoka', sans-serif;
  font-weight: 500;
}
body.portal-kids #view-skriv .app-toolbar .btn:hover,
body.portal-kids #view-overset .app-toolbar .btn:hover,
body.portal-kids #view-tale .app-toolbar .btn:hover,
body.portal-kids #view-hor .app-toolbar .btn:hover { border-color: #ff7a59; color: #ff7a59; }
body.portal-kids #view-skriv .app-toolbar .btn-refresh,
body.portal-kids #view-overset .app-toolbar .btn-refresh {
  background: linear-gradient(135deg, #ff9a7a, #ff7a59);
  border: none;
  color: #fff;
}

/* ── Skriv & Oversæt ──────────────────────────────────────────── */
body.portal-kids #view-skriv .intro h1,
body.portal-kids #view-overset .intro h1 { font-family: 'Fredoka', sans-serif; font-weight: 700; color: #2d2a4a; }
body.portal-kids #view-skriv .intro p,
body.portal-kids #view-overset .intro p { color: #6b5b8a; font-family: 'Fredoka', sans-serif; }
body.portal-kids #view-skriv .overall-wrap,
body.portal-kids #view-overset .overall-wrap {
  background: #fff;
  border: 3px solid #ffd9a8;
  border-radius: 22px;
  box-shadow: 0 4px 0 #ffd9a8;
}
body.portal-kids #view-skriv .overall-info,
body.portal-kids #view-overset .overall-info { color: #6b5b8a; font-family: 'Fredoka', sans-serif; font-weight: 500; }
body.portal-kids #view-skriv .overall-info b,
body.portal-kids #view-overset .overall-info b { color: #ff7a59; font-weight: 700; }
body.portal-kids #view-skriv .overall-track,
body.portal-kids #view-overset .overall-track { background: #ffe9d4; height: 8px; border-radius: 8px; }
body.portal-kids #view-skriv .overall-fill,
body.portal-kids #view-overset .overall-fill { background: linear-gradient(90deg, #ff9a7a, #ff7a59); border-radius: 8px; }
body.portal-kids #view-skriv .card,
body.portal-kids #view-overset .card {
  background: #fff;
  border: 3px solid #ffd9a8;
  border-radius: 22px;
  box-shadow: 0 4px 0 #ffd9a8;
}
body.portal-kids #view-skriv .card.complete,
body.portal-kids #view-overset .card.complete { border-color: #a8d995; box-shadow: 0 4px 0 #a8d995; }
body.portal-kids #view-skriv .card-num,
body.portal-kids #view-overset .card-num { color: #b8a0c0; font-family: 'Fredoka', sans-serif; }
body.portal-kids #view-skriv .card-category,
body.portal-kids #view-overset .card-category {
  color: #ff7a59;
  background: #fff0e0;
  border-color: #ffd9a8;
  font-family: 'Fredoka', sans-serif;
}
body.portal-kids #view-skriv .paragraph {
  background: #fff8e7;
  border: 2px solid #ffd9a8;
  border-radius: 16px;
  padding: 12px 14px;
  color: #2d2a4a;
  font-family: 'Fredoka', sans-serif;
}
body.portal-kids #view-skriv .paragraph .ch.cur,
body.portal-kids #view-overset .target-da .ch.cur {
  background: rgba(255, 122, 89, 0.22);
  box-shadow: inset 0 -2px 0 #ff7a59;
}
body.portal-kids #view-overset .prompt-en {
  background: #fff8e7;
  border: 2px solid #ffd9a8;
  border-radius: 16px;
  color: #2d2a4a;
  font-family: 'Fredoka', sans-serif;
}
body.portal-kids #view-overset .prompt-en .label { color: #b8a0c0; font-family: 'Fredoka', sans-serif; }
body.portal-kids #view-overset .target-da {
  background: #fff0e0;
  border: 2px solid #ffb84d;
  border-radius: 16px;
  color: #2d2a4a;
  font-family: 'Fredoka', sans-serif;
}
body.portal-kids #view-skriv .card-status,
body.portal-kids #view-overset .card-status { color: #6b5b8a; font-family: 'Fredoka', sans-serif; }
body.portal-kids #view-skriv .card-source,
body.portal-kids #view-overset .card-source { color: #b8a0c0; font-family: 'Fredoka', sans-serif; }
body.portal-kids #view-skriv textarea,
body.portal-kids #view-overset textarea {
  background: #fff;
  border: 3px solid #ffd9a8;
  border-radius: 16px;
  color: #2d2a4a;
  font-family: 'Fredoka', sans-serif;
  font-size: 16px;
}
body.portal-kids #view-skriv textarea::placeholder,
body.portal-kids #view-overset textarea::placeholder { color: #b8a0c0; }
body.portal-kids #view-skriv textarea:focus,
body.portal-kids #view-overset textarea:focus { border-color: #ff7a59; }
body.portal-kids #view-skriv .icon-btn,
body.portal-kids #view-overset .icon-btn {
  background: #fff;
  border: 2px solid #ffd9a8;
  border-radius: 12px;
  color: #6b5b8a;
}
body.portal-kids #view-skriv .icon-btn:hover,
body.portal-kids #view-overset .icon-btn:hover { border-color: #ff7a59; color: #ff7a59; }
body.portal-kids #view-skriv .icon-btn.hint.active,
body.portal-kids #view-overset .icon-btn.hint.active {
  background: #fff0e0;
  border-color: #ff7a59;
  color: #ff7a59;
}
body.portal-kids #view-skriv .progress-mini,
body.portal-kids #view-overset .progress-mini {
  color: #ff7a59;
  background: #fff0e0;
  border: 2px solid #ffd9a8;
  border-radius: 10px;
  font-family: 'Fredoka', sans-serif;
}
body.portal-kids #view-skriv .card.complete .progress-mini,
body.portal-kids #view-overset .card.complete .progress-mini {
  color: #3d7a35;
  background: #e8f8e0;
  border-color: #a8d995;
}
body.portal-kids #view-skriv .card.error .progress-mini,
body.portal-kids #view-overset .card.error .progress-mini {
  color: #c44;
  background: #ffe5e5;
  border-color: #ff9999;
}
body.portal-kids #view-skriv .skeleton-card,
body.portal-kids #view-overset .skeleton-card {
  background: #fff;
  border: 3px solid #ffd9a8;
  border-radius: 22px;
}
body.portal-kids #view-skriv .skeleton-line,
body.portal-kids #view-overset .skeleton-line {
  background: linear-gradient(90deg, #ffe9d4 25%, #fff5e9 50%, #ffe9d4 75%);
}
body.portal-kids #view-skriv .toast,
body.portal-kids #view-overset .toast {
  background: #fff;
  border: 2px solid #ffd9a8;
  color: #6b5b8a;
  font-family: 'Fredoka', sans-serif;
}
body.portal-kids #view-skriv .modal-text,
body.portal-kids #view-overset .modal-text { color: #6b5b8a; font-family: 'Fredoka', sans-serif; }
body.portal-kids #view-skriv .modal-close,
body.portal-kids #view-overset .modal-close { color: #6b5b8a; }
body.portal-kids #view-skriv .modal,
body.portal-kids #view-overset .modal {
  background: #fff;
  border: 3px solid #ffd9a8;
  border-radius: 22px;
}
body.portal-kids #view-skriv .modal-head,
body.portal-kids #view-overset .modal-head { border-bottom-color: #ffd9a8; }
body.portal-kids #view-skriv .modal-title,
body.portal-kids #view-overset .modal-title { font-family: 'Fredoka', sans-serif; color: #2d2a4a; font-weight: 700; }
body.portal-kids #view-skriv .modal-btn,
body.portal-kids #view-overset .modal-btn {
  font-family: 'Fredoka', sans-serif;
  background: #fff;
  border-color: #ffd9a8;
  color: #6b5b8a;
}
body.portal-kids #view-skriv .modal-btn.primary,
body.portal-kids #view-overset .modal-btn.primary {
  background: linear-gradient(135deg, #ff9a7a, #ff7a59);
  border: none;
  color: #fff;
}

/* ── Tale ─────────────────────────────────────────────────────── */
body.portal-kids #view-tale .intro h1 { font-family: 'Fredoka', sans-serif; font-weight: 700; color: #2d2a4a; }
body.portal-kids #view-tale .intro p { color: #6b5b8a; font-family: 'Fredoka', sans-serif; }
body.portal-kids #view-tale .session-stat,
body.portal-kids #view-tale .stat-card {
  background: #fff;
  border: 3px solid #ffd9a8;
  border-radius: 22px;
  box-shadow: 0 3px 0 #ffd9a8;
}
body.portal-kids #view-tale .session-stat .label,
body.portal-kids #view-tale .stat-card .label { color: #b8a0c0; font-family: 'Fredoka', sans-serif; }
body.portal-kids #view-tale .session-stat .value,
body.portal-kids #view-tale .stat-card .value { color: #ff7a59; font-family: 'Fredoka', sans-serif; font-weight: 700; }
body.portal-kids #view-tale .review-card,
body.portal-kids #view-tale .session-done {
  background: #fff;
  border: 3px solid #ffd9a8;
  border-radius: 28px;
  box-shadow: 0 6px 0 #ffd9a8, 0 12px 28px rgba(255,154,122,0.15);
}
body.portal-kids #view-tale .review-card .phrase-da { font-family: 'Fredoka', sans-serif; font-weight: 700; color: #2d2a4a; font-size: 28px; }
body.portal-kids #view-tale .review-card .phrase-en { color: #6b5b8a; font-family: 'Fredoka', sans-serif; }
body.portal-kids #view-tale .play-btn {
  background: linear-gradient(135deg, #ff9a7a, #ff7a59);
  box-shadow: 0 6px 0 #e56a4a, 0 10px 24px rgba(255,122,89,0.35);
}
body.portal-kids #view-tale .rating-btn {
  background: #fff;
  border: 3px solid #ffd9a8;
  border-radius: 18px;
  font-family: 'Fredoka', sans-serif;
  font-weight: 600;
  box-shadow: 0 3px 0 #ffd9a8;
}
body.portal-kids #view-tale .rating-btn .interval { font-family: 'Fredoka', sans-serif; color: #b8a0c0; }
body.portal-kids #view-tale .session-done { border-color: #a8d995; box-shadow: 0 4px 0 #a8d995; }
body.portal-kids #view-tale .session-done h2 { font-family: 'Fredoka', sans-serif; color: #2d2a4a; }

/* ── Hør ──────────────────────────────────────────────────────── */
body.portal-kids #view-hor .intro h1 { font-family: 'Fredoka', sans-serif; font-weight: 700; color: #2d2a4a; }
body.portal-kids #view-hor .intro p { color: #6b5b8a; font-family: 'Fredoka', sans-serif; }
body.portal-kids #view-hor .listen-card {
  background: #fff;
  border: 3px solid #ffd9a8;
  border-radius: 28px;
  box-shadow: 0 6px 0 #ffd9a8, 0 12px 28px rgba(255,154,122,0.15);
}
body.portal-kids #view-hor .listen-prompt { font-family: 'Fredoka', sans-serif; color: #6b5b8a; }
body.portal-kids #view-hor .play-btn {
  background: linear-gradient(135deg, #ff9a7a, #ff7a59);
  box-shadow: 0 6px 0 #e56a4a, 0 10px 24px rgba(255,122,89,0.35);
}
body.portal-kids #view-hor .badge-cat {
  color: #ff7a59;
  background: #fff0e0;
  border-color: #ffd9a8;
  font-family: 'Fredoka', sans-serif;
}
body.portal-kids #view-hor .answer-btn {
  background: #fff;
  border: 3px solid #ffd9a8;
  border-radius: 18px;
  font-family: 'Fredoka', sans-serif;
  font-weight: 500;
  box-shadow: 0 3px 0 #ffd9a8;
  min-height: 60px;
}
body.portal-kids #view-hor .answer-btn:hover:not(:disabled) { border-color: #ff7a59; color: #ff7a59; }
body.portal-kids #view-hor .answer-btn.correct { border-color: #a8d995; background: #e8f8e0; color: #3d7a35; box-shadow: 0 3px 0 #a8d995; }
body.portal-kids #view-hor .answer-btn.wrong { border-color: #ff9999; background: #ffe5e5; color: #c44; box-shadow: 0 3px 0 #ff9999; }
body.portal-kids #view-hor .next-btn {
  font-family: 'Fredoka', sans-serif;
  background: #fff;
  border: 3px solid #ffd9a8;
  border-radius: 18px;
  box-shadow: 0 3px 0 #ffd9a8;
}
body.portal-kids #view-hor .stat-card {
  background: #fff;
  border: 3px solid #ffd9a8;
  border-radius: 22px;
  box-shadow: 0 3px 0 #ffd9a8;
}
body.portal-kids #view-hor .stat-card .value { color: #ff7a59; font-family: 'Fredoka', sans-serif; font-weight: 700; }
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
#view-skriv .app-toolbar,
#view-overset .app-toolbar,
#view-tale .app-toolbar,
#view-hor .app-toolbar {
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
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 24px;
}
/* The hand-authored toolbars in the new modules need toolbar internals
   styled too (Ord/Skriv inherit these from their original CSS). */
#view-overset .app-toolbar .logo,
#view-tale    .app-toolbar .logo,
#view-hor     .app-toolbar .logo {
  font-family: 'DM Serif Display', serif; font-size: 22px; letter-spacing: -0.5px; color: var(--text);
}
#view-overset .app-toolbar .logo span,
#view-tale    .app-toolbar .logo span,
#view-hor     .app-toolbar .logo span { color: var(--accent); }
#view-overset .app-toolbar .header-right,
#view-tale    .app-toolbar .header-right,
#view-hor     .app-toolbar .header-right { display: flex; align-items: center; gap: 10px; }
#view-overset .app-toolbar .stat-pill,
#view-tale    .app-toolbar .stat-pill,
#view-hor     .app-toolbar .stat-pill {
  font-family: 'JetBrains Mono', monospace; font-size: 11px; color: var(--text-muted);
  background: var(--surface); border: 1px solid var(--border); border-radius: 20px; padding: 3px 10px;
}
#view-overset .app-toolbar .stat-pill b,
#view-tale    .app-toolbar .stat-pill b,
#view-hor     .app-toolbar .stat-pill b { color: var(--accent2); font-weight: 500; }
#view-overset .app-toolbar .btn,
#view-tale    .app-toolbar .btn,
#view-hor     .app-toolbar .btn {
  background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius);
  color: var(--text-muted); padding: 6px 14px; font-family: 'Inter', sans-serif; font-size: 12px;
  cursor: pointer; transition: all 0.15s; white-space: nowrap; display: inline-flex; align-items: center; gap: 6px;
}
#view-overset .app-toolbar .btn:hover,
#view-tale    .app-toolbar .btn:hover,
#view-hor     .app-toolbar .btn:hover { border-color: var(--accent); color: var(--accent); }
#view-overset .app-toolbar .btn-refresh {
  background: linear-gradient(135deg, #3b5fc0, #4f8ef7); border: none; color: white;
}
#view-overset .app-toolbar .btn-refresh:hover { opacity: 0.88; color: white; }

/* Kids-mode parity: match the warmer palette so the toolbar still reads as a
   distinct surface against the cream/peach background. */
body.portal-kids #view-ord .app-toolbar,
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
#view-overset .main { margin-top: var(--total-h); }
#view-tale .main { margin-top: var(--total-h); }
#view-hor .main { margin-top: var(--total-h); }

/* Hide each app's toolbar when its view isn't active (toolbars are
   position:fixed so visibility doesn't follow display:none ancestors
   when display is set on the ancestor itself, but does when toolbars
   live inside a display:none subtree — which they do here. This rule is
   belt-and-suspenders.) */
.view:not(.active) .app-toolbar { display: none !important; }

/* Portal owns global kids mode — hide Ord's duplicate Kids tab. */
#view-ord #mode-kids-btn { display: none !important; }

/* Inside the toolbar the original CSS used the danskord `header` declarations
   for layout: `display:flex; align-items:center; justify-content:space-between; padding:0 24px;
   border-bottom:1px solid var(--border); background: rgba(14,17,23,0.95); backdrop-filter: blur(12px);`
   These transferred via the `header -> .app-toolbar` selector rewrite, so the
   toolbar already has the right look. Skriv's header had nearly identical
   declarations so it does too. */

/* ─── Mobile ───────────────────────────────────────────────────────
   At <700px the portal nav scrolls horizontally (better than a hamburger
   for a learning portal where module discovery matters). The Ord toolbar
   wraps to two rows; non-essential controls collapse to icon-only. */
@media (max-width: 700px) {
  /* Portal header: smaller padding, condensed gap. */
  .portal-header { padding: 0 14px; gap: 10px; }

  /* Make the portal nav a horizontally-scrolling strip. */
  .portal-nav {
    overflow-x: auto;
    overflow-y: hidden;
    flex-wrap: nowrap;
    -webkit-overflow-scrolling: touch;
    scrollbar-width: none;
    mask-image: linear-gradient(to right, black 92%, transparent);
    -webkit-mask-image: linear-gradient(to right, black 92%, transparent);
  }
  .portal-nav::-webkit-scrollbar { display: none; }
  .portal-nav a {
    flex-shrink: 0;
    scroll-snap-align: start;
    padding: 5px 10px;
    font-size: 12px;
  }

  /* Home link → 🏠 icon. The text is replaced via ::before/font-size:0 trick
     so screen readers can still expose the original "Home" text. */
  .portal-nav a[data-route="home"] {
    font-size: 0;
  }
  .portal-nav a[data-route="home"]::before {
    content: "🏠";
    font-size: 16px;
  }

  /* Ord toolbar: wrap to two rows, collapse btns to icon-only first letter. */
  #view-ord .app-toolbar {
    flex-wrap: wrap;
    height: auto;
    padding: 6px 12px;
    gap: 8px;
  }
  /* Collapse the three action btns (Shuffle/Known/Reset) to first-letter
     glyph only; their text already starts with the appropriate symbol. */
  #view-ord .app-toolbar .btn:not(.btn-shuffle):not(.btn-reset):not(.btn-refresh):not(#known-filter-btn),
  #view-ord .app-toolbar .btn-shuffle,
  #view-ord .app-toolbar #known-filter-btn,
  #view-ord .app-toolbar .btn-reset {
    font-size: 0;
    padding: 6px 10px;
    min-width: 36px;
  }
  #view-ord .app-toolbar .btn::first-letter,
  #view-ord .app-toolbar .btn-shuffle::first-letter,
  #view-ord .app-toolbar #known-filter-btn::first-letter,
  #view-ord .app-toolbar .btn-reset::first-letter {
    font-size: 14px;
  }
  /* The Ord toolbar now wraps; bump --total-h so .shell, .sidebar, .topbar
     clear the taller toolbar correctly. */
  #view-ord .shell, #view-ord .sidebar, #view-ord .topbar {
    --total-h: calc(var(--header-h) + 96px);
  }
  /* Sidebar already hidden by source CSS at <700px; keep that. */

  /* Skriv toolbar already handled by source CSS at <700px. */

  /* Logo collapses to "d" + accent glyph at very narrow widths to reclaim space. */
}
@media (max-width: 500px) {
  .portal-logo { font-size: 18px; }
  .portal-nav a { padding: 4px 8px; font-size: 11px; }
  #portal-kids-toggle { padding: 5px 10px; font-size: 11px; }
}
</style>
"""

PORTAL_HEADER_AND_LANDING = r"""
<header class="portal-header">
  <a href="./" class="portal-logo">dansk<span>learn</span></a>
  <nav class="portal-nav">
    <a href="./"        data-route="home">Home</a>
    <a href="./ord"     data-route="ord">Ord</a>
    <a href="./skriv"   data-route="skriv">Skriv</a>
    <a href="./overset" data-route="overset">Oversæt</a>
    <a href="./tale"    data-route="tale">Tale</a>
    <a href="./hor"     data-route="hor">Hør</a>
  </nav>
  <button id="portal-kids-toggle" type="button" aria-pressed="false" title="Friendly colours &amp; big buttons for ages 5–7"><span class="kids-star" aria-hidden="true">★</span> Kids</button>
</header>

<section id="view-home" class="view">
  <div class="landing-hero">
    <h1>dansk<span>learn</span></h1>
    <p>A growing portal for learning Danish — vocabulary, writing, listening, speaking, and translation. Pick a module below to start, or jump back in where you left off.</p>
  </div>

  <div class="section-label">Modules</div>
  <div class="module-grid">
    <a class="module-card" href="./ord">
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
    <a class="module-card" href="./skriv">
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
    <a class="module-card" href="./overset">
      <div class="module-card-head">
        <div class="module-icon">🌐</div>
        <div class="module-title">dansk<span>oversæt</span></div>
      </div>
      <div class="module-desc">Same fresh paragraphs, reversed: read English, type the Danish translation. Hint icon reveals the original Danish.</div>
      <div class="module-stat">
        <span>Done</span><b id="snap-overset-done">—</b>
        <span class="pct" id="snap-overset-pct">0%</span>
      </div>
      <div class="module-progress"><div id="snap-overset-fill" style="width:0%"></div></div>
    </a>
    <a class="module-card" href="./tale">
      <div class="module-card-head">
        <div class="module-icon">🗣️</div>
        <div class="module-title">dansk<span>tale</span></div>
      </div>
      <div class="module-desc">Listen and repeat — phrases for everyday Danish. Self-rate Hard/Good/Easy and the deck schedules itself like Anki.</div>
      <div class="module-stat">
        <span>Today</span><b id="snap-tale-reviewed">—</b>
        <span class="pct" id="snap-tale-streak">🔥 0</span>
      </div>
      <div class="module-progress"><div id="snap-tale-fill" style="width:0%"></div></div>
    </a>
    <a class="module-card" href="./hor">
      <div class="module-card-head">
        <div class="module-icon">👂</div>
        <div class="module-title">dansk<span>hør</span></div>
      </div>
      <div class="module-desc">Listen to a Danish phrase and pick the English meaning from four choices. Distractors come from the same topic.</div>
      <div class="module-stat">
        <span>Played</span><b id="snap-hor-played">—</b>
        <span class="pct" id="snap-hor-acc">—</span>
      </div>
      <div class="module-progress"><div id="snap-hor-fill" style="width:0%"></div></div>
    </a>
  </div>

  <footer class="portal-footer">
    <p>© <span id="portal-year">2026</span> Swapnil Deshpande. All rights reserved.</p>
    <p class="footer-sub">danskLearn — built for learning Danish. Content for educational use only.</p>
  </footer>
</section>
"""

PORTAL_FOOTER_SCRIPT = r"""
<script>
// ─── Router: clean paths on http(s), hash fallback for file:// ────
const Routes = {
  '': 'home', '/': 'home',
  '/ord': 'ord',
  '/skriv': 'skriv',
  '/overset': 'overset',
  '/tale': 'tale',
  '/hor': 'hor',
};
const useHashRouting = location.protocol === 'file:';
const SITE_ORIGIN = 'https://swapnild2111.github.io';
const SITE_BASE = '/dansklearn';
const RouteMeta = {
  home:    { title: 'danskLearn — Learn Danish', path: '/' },
  ord:     { title: 'danskord — Danish Vocabulary | danskLearn', path: '/ord' },
  skriv:   { title: 'danskskriv — Type Along in Danish | danskLearn', path: '/skriv' },
  overset: { title: 'danskoversæt — Translate to Danish | danskLearn', path: '/overset' },
  tale:    { title: 'dansktale — Speak Along | danskLearn', path: '/tale' },
  hor:     { title: 'danskhør — Listen and Pick | danskLearn', path: '/hor' },
};
function hrefToRoute(href) {
  if (!href) return null;
  if (href.startsWith('#')) {
    const p = href.replace(/^#/, '') || '/';
    return Routes[p] !== undefined ? p : null;
  }
  let p = href;
  if (p.startsWith('./')) p = p.slice(1);
  if (!p.startsWith('/')) p = '/' + p;
  return Routes[p] !== undefined ? p : null;
}
function routeFromLink(a) {
  if (a.dataset.route) {
    return a.dataset.route === 'home' ? '/' : '/' + a.dataset.route;
  }
  return hrefToRoute(a.getAttribute('href'));
}
function basePath() {
  const raw = location.pathname.replace(/\/index\.html$/i, '');
  const normalized = raw.endsWith('/') && raw.length > 1 ? raw.slice(0, -1) : raw;
  for (const routePath of Object.keys(Routes)) {
    if (!routePath || routePath === '/') continue;
    if (normalized.endsWith(routePath)) {
      const base = normalized.slice(0, -routePath.length);
      return base.replace(/\/$/, '') || '';
    }
  }
  if (location.hostname.endsWith('github.io')) {
    const parts = normalized.split('/').filter(Boolean);
    if (parts.length === 1) return '/' + parts[0];
  }
  return '';
}
function routePath() {
  const base = basePath();
  let p = location.pathname.replace(/\/index\.html$/i, '');
  if (base && p.startsWith(base)) p = p.slice(base.length) || '/';
  p = p.replace(/\/$/, '') || '/';
  return p;
}
function currentRoute() {
  if (useHashRouting) {
    const h = location.hash.replace(/^#/, '') || '/';
    return Routes[h] || 'home';
  }
  return Routes[routePath()] || 'home';
}
function buildUrl(path) {
  const base = basePath();
  if (path === '/' || path === '') return base ? base + '/' : '/';
  return (base || '') + path;
}
function navigate(path, replace) {
  if (useHashRouting) {
    const hash = path === '/' ? '#/' : '#' + path;
    if (replace) {
      const url = location.pathname + location.search + hash;
      history.replaceState(null, '', url);
      setActiveView(currentRoute());
    } else {
      location.hash = hash;
    }
    return;
  }
  const url = buildUrl(path);
  if (replace) history.replaceState(null, '', url);
  else history.pushState(null, '', url);
  setActiveView(currentRoute());
}
function updateSeo(name) {
  const meta = RouteMeta[name] || RouteMeta.home;
  document.title = meta.title;
  let link = document.querySelector('link[rel="canonical"]');
  if (!link) {
    link = document.createElement('link');
    link.rel = 'canonical';
    document.head.appendChild(link);
  }
  link.href = SITE_ORIGIN + SITE_BASE + (meta.path === '/' ? '/' : meta.path);
}
function setActiveView(name) {
  document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));
  const target = document.getElementById('view-' + name);
  if (target) target.classList.add('active');
  document.querySelectorAll('.portal-nav a').forEach(a => {
    a.classList.toggle('active', a.dataset.route === name);
  });
  updateSeo(name);
  // Re-apply portal-kids chrome on every route change (SPA nav skips full reload).
  syncPortalKidsChrome();
  if (name === 'ord'     && window.OrdApp)     window.OrdApp.init();
  if (name === 'skriv'   && window.SkrivApp)   window.SkrivApp.init();
  if (name === 'overset' && window.OversetApp) window.OversetApp.init();
  if (name === 'tale'    && window.TaleApp)    window.TaleApp.init();
  if (name === 'hor'     && window.HorApp)     window.HorApp.init();
  if (name === 'home') refreshLandingSnapshot();
  // Ord content-mode classes — keep mode-kids while portal kids is on.
  if (name !== 'ord') {
    document.body.classList.remove('mode-words', 'mode-verbs');
    if (!isPortalKids()) document.body.classList.remove('mode-kids');
  } else {
    syncOrdKidsMode();
  }
}
document.addEventListener('click', e => {
  const a = e.target.closest('a[href]');
  if (!a || a.target === '_blank' || a.hasAttribute('download')) return;
  const href = a.getAttribute('href');
  if (!href || href.startsWith('http') || href.startsWith('mailto:')) return;
  const path = routeFromLink(a);
  if (path !== null && Routes[path] !== undefined) {
    e.preventDefault();
    navigate(path);
  }
});
if (useHashRouting) {
  window.addEventListener('hashchange', () => setActiveView(currentRoute()));
} else {
  window.addEventListener('popstate', () => setActiveView(currentRoute()));
  // Upgrade old #/… bookmarks to clean URLs when served over http(s).
  if (/^#\//.test(location.hash)) {
    const legacy = location.hash.replace(/^#/, '');
    history.replaceState(null, '', buildUrl(legacy));
  }
}

// ─── Portal-wide kids mode (home toggle) ─────────────────────────
const PORTAL_KIDS_KEY = 'dansklearn:portal-kids:v1';
function isPortalKids() {
  return localStorage.getItem(PORTAL_KIDS_KEY) === '1';
}
function syncOrdKidsMode() {
  if (typeof window.setMode !== 'function') return;
  if (isPortalKids()) window.setMode('kids');
  else if (document.body.classList.contains('mode-kids')) window.setMode('words');
}
function syncPortalKidsChrome() {
  const on = isPortalKids();
  document.body.classList.toggle('portal-kids', on);
  updateKidsToggleLabel(on);
}
function updateKidsToggleLabel(on) {
  const btn = document.getElementById('portal-kids-toggle');
  if (!btn) return;
  btn.setAttribute('aria-pressed', on ? 'true' : 'false');
  if (on) btn.textContent = 'Turn off';
  else btn.innerHTML = '<span class="kids-star" aria-hidden="true">★</span> Kids';
}
function applyPortalKids(on) {
  localStorage.setItem(PORTAL_KIDS_KEY, on ? '1' : '0');
  syncPortalKidsChrome();
  syncOrdKidsMode();
}
function togglePortalKids() {
  applyPortalKids(!isPortalKids());
}

// ─── Landing-page progress snapshot ──────────────────────────────
function refreshLandingSnapshot() {
  // ── Ord — Words mode only (matches the card's "1000 words" copy). ────
  let ordKnown = 0;
  try {
    const arr = JSON.parse(localStorage.getItem('dk-known') || '[]');
    ordKnown = Array.isArray(arr) ? arr.length : 0;
  } catch (_) { /* ignore */ }
  const ordTotal = 1000;
  const ordPct = ordTotal ? Math.round((ordKnown / ordTotal) * 100) : 0;
  setText('snap-ord-known', `${ordKnown} / ${ordTotal}`);
  setText('snap-ord-pct', ordPct + '%');
  setWidth('snap-ord-fill', ordPct + '%');

  // ── Skriv — count cards in current session whose typed text matches the target.
  const skriv = countTypingProgress('danskskriv:session:v1', 5);
  setText('snap-skriv-done', `${skriv.done} / ${skriv.total}`);
  setText('snap-skriv-pct', skriv.pct + '%');
  setWidth('snap-skriv-fill', skriv.pct + '%');

  // ── Overset — same shape as Skriv. ────────────────────────────────
  const overset = countTypingProgress('danskoverset:session:v1', 5);
  setText('snap-overset-done', `${overset.done} / ${overset.total}`);
  setText('snap-overset-pct', overset.pct + '%');
  setWidth('snap-overset-fill', overset.pct + '%');

  // ── Tale — reviewed today + streak from meta. ─────────────────────
  let taleReviewed = 0, taleStreak = 0;
  try {
    const raw = localStorage.getItem('dansktale:meta:v1');
    if (raw) {
      const m = JSON.parse(raw);
      const today = todayStrLocal();
      if (m && m.lastDate === today) taleReviewed = m.reviewedToday || 0;
      taleStreak = m && m.streak || 0;
    }
  } catch (_) { /* ignore */ }
  setText('snap-tale-reviewed', taleReviewed);
  setText('snap-tale-streak', '🔥 ' + taleStreak);
  // Fill bar uses today-reviewed against an aspirational 10/day target.
  const taleTarget = 10;
  const talePct = Math.min(100, Math.round((taleReviewed / taleTarget) * 100));
  setWidth('snap-tale-fill', talePct + '%');

  // ── Hør — accuracy + played from progress. ────────────────────────
  let horSeen = 0, horCorrect = 0;
  try {
    const raw = localStorage.getItem('danskor:progress:v1');
    if (raw) {
      const p = JSON.parse(raw);
      horSeen = (p && p.seen) || 0;
      horCorrect = (p && p.correct) || 0;
    }
  } catch (_) { /* ignore */ }
  const horPct = horSeen ? Math.round((horCorrect / horSeen) * 100) : 0;
  setText('snap-hor-played', horSeen);
  setText('snap-hor-acc', horSeen ? horPct + '%' : '—');
  setWidth('snap-hor-fill', horPct + '%');
}
function countTypingProgress(storageKey, fallbackTotal) {
  let done = 0, total = 0;
  try {
    const raw = localStorage.getItem(storageKey);
    if (raw) {
      const s = JSON.parse(raw);
      if (s && Array.isArray(s.paragraphs) && Array.isArray(s.typed)) {
        total = s.paragraphs.length;
        for (let i = 0; i < total; i++) {
          if ((s.typed[i] || '') === s.paragraphs[i]) done++;
        }
      }
    }
  } catch (_) { /* ignore */ }
  if (!total) total = fallbackTotal;
  const pct = total ? Math.round((done / total) * 100) : 0;
  return { done, total, pct };
}
function todayStrLocal() {
  const d = new Date();
  return d.getFullYear() + '-' + String(d.getMonth()+1).padStart(2,'0') + '-' + String(d.getDate()).padStart(2,'0');
}
function setText(id, v)  { const el = document.getElementById(id); if (el) el.textContent = v; }
function setWidth(id, w) { const el = document.getElementById(id); if (el) el.style.width  = w; }

// ─── Footer year ─────────────────────────────────────────────────
(function setFooterYear() {
  const el = document.getElementById('portal-year');
  if (el) el.textContent = new Date().getFullYear();
})();

// ─── Boot ────────────────────────────────────────────────────────
syncPortalKidsChrome();
const portalKidsBtn = document.getElementById('portal-kids-toggle');
if (portalKidsBtn) portalKidsBtn.addEventListener('click', togglePortalKids);
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


## Source files that go through the same extract → scope → wrap pipeline.
## Each is a standalone runnable .html. Order is preserved in the merged
## index.html (each shows up as `#view-{name}`).
APP_SOURCES = [
    ("ord",     ORD_PATH),
    ("skriv",   SKRIV_PATH),
    ("overset", OVERSET_PATH),
    ("tale",    TALE_PATH),
    ("hor",     HOR_PATH),
]


def build() -> None:
    # Extract and scope each source.
    apps = []
    for name, path in APP_SOURCES:
        src = read_source(path)
        style = extract_style(src)
        body = extract_body_markup(src)
        script = extract_script(src)
        scoped = scope_css(style, f"#view-{name}", drop_root=True)
        apps.append({"name": name, "scoped": scoped, "body": body, "script": script})

    phrases_js = read_source(PHRASES_PATH)

    style_blocks = [
        f'<style id="{a["name"]}-style">\n{a["scoped"]}\n</style>'
        for a in apps
    ]
    view_sections = [
        f'<section id="view-{a["name"]}" class="view">\n{a["body"]}\n</section>'
        for a in apps
    ]
    # Wrap each app's script in its IIFE. Inline-onclick exports apply only
    # to the source apps that need them (see INLINE_ONCLICK_EXPORTS).
    app_scripts = [wrap_app_script(a["name"], a["script"]) for a in apps]

    parts = [
        PORTAL_HEAD,
        PORTAL_STYLE,
        *style_blocks,
        LAYOUT_FIXES,
        PORTAL_KIDS_STYLE,
        "</head>",
        "<body>",
        PORTAL_HEADER_AND_LANDING,
        *view_sections,
        # Shared phrase bank — inlined ONCE before per-app scripts so
        # window.DanskPhrases.BANK is available to dansktale & danskhor
        # without duplication. (Standalone HTML files load it via
        # <script src="phrases.js">; we strip that in extract_body_markup
        # and inline the bank's contents here instead.)
        f'<script id="phrases-bank">\n{phrases_js}\n</script>',
        *app_scripts,
        PORTAL_FOOTER_SCRIPT,
        "</body>",
        "</html>",
    ]

    html = "\n".join(parts)
    OUT_PATH.write_text(html, encoding="utf-8")
    NOT_FOUND_PATH.write_text(html, encoding="utf-8")
    print(f"Built {OUT_PATH} ({OUT_PATH.stat().st_size:,} bytes)")
    print(f"Built {NOT_FOUND_PATH} ({NOT_FOUND_PATH.stat().st_size:,} bytes)")


if __name__ == "__main__":
    try:
        build()
    except Exception as exc:
        print(f"Build failed: {exc}", file=sys.stderr)
        sys.exit(1)
