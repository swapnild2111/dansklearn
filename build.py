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
import json
import re
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).parent
SRC = ROOT / "src"
ORD_PATH       = SRC / "danskord.html"
SKRIV_PATH     = SRC / "danskskriv.html"
OVERSET_PATH   = SRC / "danskoverset.html"
TALE_PATH      = SRC / "dansktale.html"
HOR_PATH       = SRC / "danskhor.html"
PHRASES_PATH   = SRC / "phrases.js"
SITE_CONFIG_PATH = ROOT / "site.config.json"
OUT_PATH       = ROOT / "index.html"
NOT_FOUND_PATH = ROOT / "404.html"
ROBOTS_PATH    = ROOT / "robots.txt"
SITEMAP_PATH   = ROOT / "sitemap.xml"

SITE_ORIGIN = "https://swapnild2111.github.io"
SITE_BASE = "/dansklearn"
SITE_NAME = "danskLearn"

ROUTES = [
    {
        "id": "home",
        "path": "/",
        "title": "danskLearn — Learn Danish",
        "description": "Free Danish learning portal with flashcards, typing practice, translation, speaking, and listening exercises — five modules in one app.",
    },
    {
        "id": "ord",
        "path": "/ord",
        "title": "danskord — Danish Vocabulary | danskLearn",
        "description": "Learn 1000 essential Danish words and verb conjugations with flashcards. Includes a kids mode for young learners.",
    },
    {
        "id": "skriv",
        "path": "/skriv",
        "title": "danskskriv — Type Along in Danish | danskLearn",
        "description": "Type along with fresh Danish news paragraphs. Live feedback highlights mistakes as you write.",
    },
    {
        "id": "overset",
        "path": "/overset",
        "title": "danskoversæt — Translate to Danish | danskLearn",
        "description": "Read English paragraphs and type the Danish translation. Hints reveal the original Danish when you need help.",
    },
    {
        "id": "tale",
        "path": "/tale",
        "title": "dansktale — Speak Along | danskLearn",
        "description": "Listen to Danish phrases and practice speaking out loud. Spaced repetition schedules what to review next.",
    },
    {
        "id": "hor",
        "path": "/hor",
        "title": "danskhør — Listen and Pick | danskLearn",
        "description": "Listening comprehension quiz: hear a Danish phrase and pick the correct English meaning from four choices.",
    },
]


def load_site_config() -> dict:
    default = {"gaMeasurementId": "", "gscVerification": ""}
    if not SITE_CONFIG_PATH.exists():
        return default
    try:
        data = json.loads(SITE_CONFIG_PATH.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return default
        return {**default, **data}
    except (json.JSONDecodeError, OSError):
        return default


def site_url(path: str = "/") -> str:
    base = SITE_ORIGIN + SITE_BASE
    if path in ("", "/"):
        return base + "/"
    return base + path


def home_route() -> dict:
    return ROUTES[0]


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

def build_portal_head(config: dict) -> str:
    home = home_route()
    ga_id = (config.get("gaMeasurementId") or "").strip()
    gsc = (config.get("gscVerification") or "").strip()
    canonical = site_url("/")
    og_image = site_url("/og-image.svg")

    ga_block = ""
    if ga_id:
        ga_block = f"""
<script async src="https://www.googletagmanager.com/gtag/js?id={ga_id}"></script>
<script>
  window.dataLayer = window.dataLayer || [];
  function gtag(){{dataLayer.push(arguments);}}
  gtag('js', new Date());
  gtag('config', '{ga_id}', {{ send_page_view: false }});
</script>"""

    gsc_block = (
        f'\n<meta name="google-site-verification" content="{gsc}">' if gsc else ""
    )

    json_ld = json.dumps(
        {
            "@context": "https://schema.org",
            "@graph": [
                {
                    "@type": "WebSite",
                    "@id": canonical + "#website",
                    "url": canonical,
                    "name": SITE_NAME,
                    "description": home["description"],
                    "inLanguage": "en",
                },
                {
                    "@type": "WebApplication",
                    "@id": canonical + "#app",
                    "name": SITE_NAME,
                    "url": canonical,
                    "description": home["description"],
                    "applicationCategory": "EducationalApplication",
                    "operatingSystem": "Any",
                    "browserRequirements": "Requires JavaScript",
                    "isAccessibleForFree": True,
                    "offers": {
                        "@type": "Offer",
                        "price": "0",
                        "priceCurrency": "USD",
                    },
                },
            ],
        },
        ensure_ascii=False,
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{home["title"]}</title>
<meta name="description" content="{home["description"]}">
<meta name="robots" content="index, follow, max-image-preview:large">
<meta name="author" content="{SITE_NAME}">
<link rel="canonical" href="{canonical}">
<link rel="icon" href="./favicon.svg" type="image/svg+xml">
<link rel="icon" href="./favicon.svg" sizes="any">
<link rel="apple-touch-icon" href="./favicon.svg">
<meta name="theme-color" content="#0e1117">
<meta property="og:type" content="website">
<meta property="og:site_name" content="{SITE_NAME}">
<meta property="og:title" content="{home["title"]}">
<meta property="og:description" content="{home["description"]}">
<meta property="og:url" content="{canonical}">
<meta property="og:image" content="{og_image}">
<meta property="og:locale" content="en_US">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{home["title"]}">
<meta name="twitter:description" content="{home["description"]}">
<meta name="twitter:image" content="{og_image}">
{gsc_block}
<script type="application/ld+json">{json_ld}</script>
{ga_block}
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=DM+Serif+Display:ital@0;1&family=Fredoka:wght@500;600;700&family=Inter:wght@300;400;500;600&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
"""


def write_robots_txt() -> None:
    ROBOTS_PATH.write_text(
        "User-agent: *\nAllow: /\n\nSitemap: " + site_url("/sitemap.xml") + "\n",
        encoding="utf-8",
    )


def write_sitemap_xml() -> None:
    today = date.today().isoformat()
    urls = "\n".join(
        "  <url>\n"
        f"    <loc>{site_url(route['path'])}</loc>\n"
        f"    <lastmod>{today}</lastmod>\n"
        f"    <changefreq>{'weekly' if route['id'] == 'home' else 'monthly'}</changefreq>\n"
        f"    <priority>{'1.0' if route['id'] == 'home' else '0.8'}</priority>\n"
        "  </url>"
        for route in ROUTES
    )
    SITEMAP_PATH.write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f"{urls}\n"
        "</urlset>\n",
        encoding="utf-8",
    )


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

/* Kids Ord confetti — particles append to document.body, outside #view-ord. */
.confetti-piece {
  position: fixed;
  width: 10px;
  height: 14px;
  pointer-events: none;
  z-index: 10050;
  will-change: transform, opacity;
}
.confetti-piece.confetti-star {
  width: auto;
  height: auto;
  line-height: 1;
  background: transparent !important;
}
@keyframes confettiFall {
  0% { transform: translate3d(0, 0, 0) rotate(0deg); opacity: 1; }
  100% { transform: translate3d(var(--cx, 40px), var(--cy, 300px), 0) rotate(720deg); opacity: 0; }
}

/* ─── PORTAL HEADER ────────────────────────────────────────────── */
.portal-bar {
  height: var(--header-h);
  border-bottom: 1px solid var(--border);
  padding: 0 24px;
  padding-top: env(safe-area-inset-top, 0px);
  display: flex;
  align-items: center;
  gap: 18px;
  position: fixed;
  top: 0; left: 0; right: 0;
  background: rgba(14, 17, 23, 0.98);
  z-index: 200;
}
/* Legacy alias — some rules may reference portal-chrome during transition. */
.portal-chrome { display: contents; }

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
.portal-nav { display: flex; gap: 4px; flex: 1; align-items: center; }
.portal-nav--drawer { display: none; }
.portal-nav-links { display: flex; gap: 4px; flex: 1; align-items: center; }
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

/* Mobile nav drawer — hamburger + left panel (shown ≤700px via LAYOUT_FIXES). */
.portal-menu-btn {
  display: none;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  gap: 5px;
  width: 40px;
  height: 40px;
  padding: 0;
  border: 1px solid var(--border);
  border-radius: 10px;
  background: var(--surface);
  color: var(--text);
  cursor: pointer;
  flex-shrink: 0;
  transition: border-color 0.15s, background 0.15s;
  touch-action: manipulation;
  -webkit-tap-highlight-color: transparent;
  position: relative;
  z-index: 1;
}
.portal-menu-btn:hover { border-color: var(--accent); }
.portal-menu-bar {
  display: block;
  width: 18px;
  height: 2px;
  background: currentColor;
  border-radius: 2px;
  transition: transform 0.2s, opacity 0.2s;
}
body.portal-nav-open .portal-menu-bar:nth-child(1) { transform: translateY(7px) rotate(45deg); }
body.portal-nav-open .portal-menu-bar:nth-child(2) { opacity: 0; }
body.portal-nav-open .portal-menu-bar:nth-child(3) { transform: translateY(-7px) rotate(-45deg); }
.portal-nav-drawer-head {
  display: none;
  align-items: center;
  justify-content: space-between;
  padding: 16px 18px 12px;
  border-bottom: 1px solid var(--border);
  flex-shrink: 0;
}
.portal-nav-drawer-label {
  font-family: 'Inter', sans-serif;
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 1.1px;
  text-transform: uppercase;
  color: var(--text-dim);
}
.portal-nav-close {
  width: 36px;
  height: 36px;
  border: 1px solid var(--border);
  border-radius: 10px;
  background: transparent;
  color: var(--text-muted);
  font-size: 22px;
  line-height: 1;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0;
  transition: border-color 0.15s, color 0.15s;
}
.portal-nav-close:hover { border-color: var(--accent); color: var(--accent); }
.portal-nav-drawer-brand {
  font-family: 'DM Serif Display', serif;
  font-size: 20px;
  letter-spacing: -0.3px;
  color: var(--text);
  line-height: 1.2;
}
.portal-nav-drawer-brand span { color: var(--accent); }
.portal-drawer-icon {
  width: 40px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 24px;
  line-height: 1;
  flex-shrink: 0;
}
.portal-drawer-text {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 2px;
  text-align: left;
}
.portal-drawer-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--text);
  line-height: 1.25;
  text-align: left;
}
.portal-drawer-title em {
  font-style: normal;
  color: var(--accent2);
  font-weight: 500;
}
.portal-drawer-desc {
  font-size: 12px;
  color: var(--text-muted);
  line-height: 1.35;
  text-align: left;
}
.portal-drawer-chevron {
  flex-shrink: 0;
  margin-left: auto;
  color: var(--text-dim);
  font-size: 20px;
  line-height: 1;
  opacity: 0.7;
  transition: transform 0.15s, color 0.15s, opacity 0.15s;
}
.portal-nav-backdrop {
  display: none;
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.55);
  z-index: 280;
  opacity: 0;
  transition: opacity 0.25s;
  pointer-events: none;
}
body.portal-nav-open .portal-nav-backdrop {
  opacity: 1;
  pointer-events: auto;
}
body.portal-nav-open { overflow: hidden; }
body.portal-nav-open .portal-bar { z-index: 300; }

.portal-audience-toggle {
  flex-shrink: 0;
  display: inline-flex;
  align-items: center;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 22px;
  padding: 3px;
  gap: 2px;
}
.portal-audience-toggle button {
  font-family: 'Inter', sans-serif;
  font-size: 12px;
  font-weight: 600;
  padding: 6px 14px;
  border: none;
  border-radius: 18px;
  background: transparent;
  color: var(--text-muted);
  cursor: pointer;
  white-space: nowrap;
  transition: background 0.15s, color 0.15s, box-shadow 0.15s;
}
.portal-audience-toggle button:hover:not(.active) { color: var(--text); }
.portal-audience-toggle button.active {
  background: var(--accent);
  color: #fff;
  box-shadow: 0 2px 8px rgba(79, 142, 247, 0.35);
}
body.portal-kids .portal-audience-toggle {
  background: #fff;
  border: 2px solid #ffd9a8;
  box-shadow: 0 2px 0 #ffd9a8;
}
body.portal-kids .portal-audience-toggle button {
  font-family: 'Fredoka', sans-serif;
  font-weight: 600;
  color: #6b5b8a;
}
body.portal-kids .portal-audience-toggle button.active {
  background: linear-gradient(135deg, #ff9a7a, #ff7a59);
  color: #fff;
  box-shadow: 0 2px 0 #d85a3a;
}

/* ─── KIDS-MODE OVERRIDES ON PORTAL CHROME ─────────────────────── */
body.portal-kids .portal-bar,
body.mode-kids .portal-bar { background: rgba(255,255,255,0.92); border-bottom: 2px solid #ffd9a8; }
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
body.portal-kids .portal-menu-btn,
body.mode-kids .portal-menu-btn {
  background: #fff;
  border: 2px solid #ffd9a8;
  color: #2d2a4a;
}
body.portal-kids .portal-nav-drawer-head,
body.mode-kids .portal-nav-drawer-head { border-bottom-color: #ffd9a8; }
body.portal-kids .portal-nav-drawer-brand,
body.mode-kids .portal-nav-drawer-brand {
  font-family: 'Fredoka', sans-serif;
  font-weight: 700;
  color: #2d2a4a;
}
body.portal-kids .portal-nav-drawer-brand span,
body.mode-kids .portal-nav-drawer-brand span { color: #ff7a59; }
body.portal-kids .portal-nav-close,
body.mode-kids .portal-nav-close { border-color: #ffd9a8; color: #6b5b8a; }
body.portal-kids .portal-nav-close:hover,
body.mode-kids .portal-nav-close:hover { border-color: #ff7a59; color: #ff7a59; }

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
.portal-footer a { color: var(--accent2); text-decoration: none; border-bottom: 1px dotted var(--text-dim); transition: color 0.15s, border-color 0.15s; }
.portal-footer a:hover { color: var(--accent); border-bottom-color: var(--accent); }
.portal-footer .footer-gh-icon { width: 12px; height: 12px; vertical-align: -2px; margin-right: 3px; }

/* ─── VIEW CONTAINERS ──────────────────────────────────────────── */
.view { display: none; }
.view.active { display: block; }

/* When inside Ord/Skriv views, push top-level content past the portal header.
   The original apps used `margin-top: var(--header-h)` on .shell and .main; since
   the portal header occupies that same space we keep their offsets intact. */
@media (max-width: 700px) {
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
body.portal-kids #view-tale .badge-cat {
  color: #ff7a59;
  background: #fff0e0;
  border-color: #ffd9a8;
  font-family: 'Fredoka', sans-serif;
}
body.portal-kids #view-tale .badge-progress { color: #b8a0c0; font-family: 'Fredoka', sans-serif; }
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
  color: #2d2a4a;
  box-shadow: 0 3px 0 #ffd9a8;
}
body.portal-kids #view-tale .rating-btn .interval { font-family: 'Fredoka', sans-serif; color: #b8a0c0; }
body.portal-kids #view-tale .rating-btn.hard:hover { border-color: #ff9999; color: #c44; }
body.portal-kids #view-tale .rating-btn.good:hover { border-color: #ff7a59; color: #ff7a59; }
body.portal-kids #view-tale .rating-btn.easy:hover { border-color: #a8d995; color: #3d7a35; }
body.portal-kids #view-tale .session-done { border-color: #a8d995; box-shadow: 0 4px 0 #a8d995; }
body.portal-kids #view-tale .session-done h2 { font-family: 'Fredoka', sans-serif; color: #2d2a4a; }
body.portal-kids #view-tale .session-done p { color: #6b5b8a; font-family: 'Fredoka', sans-serif; }
body.portal-kids #view-tale .session-done .btn {
  font-family: 'Fredoka', sans-serif;
  background: #fff;
  border: 3px solid #ffd9a8;
  border-radius: 18px;
  color: #6b5b8a;
  box-shadow: 0 3px 0 #ffd9a8;
}
body.portal-kids #view-tale .session-done .btn:hover { border-color: #ff7a59; color: #ff7a59; }
body.portal-kids #view-tale .deck-toolbar h2 { font-family: 'Fredoka', sans-serif; color: #2d2a4a; }
body.portal-kids #view-tale .deck-toolbar .deck-count { color: #b8a0c0; font-family: 'Fredoka', sans-serif; }
body.portal-kids #view-tale .deck-refresh {
  background: #fff; border: 3px solid #ffd9a8; border-radius: 18px;
  font-family: 'Fredoka', sans-serif; font-weight: 600; color: #6b5b8a;
  box-shadow: 0 3px 0 #ffd9a8;
}
body.portal-kids #view-tale .deck-refresh:hover { border-color: #ff7a59; color: #ff7a59; }
body.portal-kids #view-tale .deck-list {
  background: #fff; border: 3px solid #ffd9a8; border-radius: 22px;
  box-shadow: 0 3px 0 #ffd9a8;
}
body.portal-kids #view-tale .deck-num { color: #b8a0c0; font-family: 'Fredoka', sans-serif; }
body.portal-kids #view-tale .deck-da { font-family: 'Fredoka', sans-serif; color: #2d2a4a; }
body.portal-kids #view-tale .deck-en { font-family: 'Fredoka', sans-serif; color: #6b5b8a; }
body.portal-kids #view-tale .deck-cat { color: #ff7a59; font-family: 'Fredoka', sans-serif; opacity: 1; }
body.portal-kids #view-tale .deck-item.done { opacity: 0.55; }
body.portal-kids #view-tale .deck-item.done .deck-da,
body.portal-kids #view-tale .deck-item.done .deck-en { color: #6b5b8a; }
body.portal-kids #view-tale .deck-item.active { background: rgba(255, 122, 89, 0.1); box-shadow: inset 3px 0 0 #ff7a59; }
body.portal-kids #view-tale .deck-item.active .deck-da { color: #2d2a4a; }

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
  color: #2d2a4a;
  box-shadow: 0 3px 0 #ffd9a8;
  min-height: 60px;
}
body.portal-kids #view-hor .answer-btn:hover:not(:disabled) { border-color: #ff7a59; color: #ff7a59; }
body.portal-kids #view-hor .answer-btn.faded { color: #6b5b8a; opacity: 0.55; }
body.portal-kids #view-hor .answer-btn.correct { border-color: #a8d995; background: #e8f8e0; color: #3d7a35; box-shadow: 0 3px 0 #a8d995; }
body.portal-kids #view-hor .answer-btn.wrong { border-color: #ff9999; background: #ffe5e5; color: #c44; box-shadow: 0 3px 0 #ff9999; }
body.portal-kids #view-hor .badge-score { color: #b8a0c0; font-family: 'Fredoka', sans-serif; }
body.portal-kids #view-hor .next-btn {
  font-family: 'Fredoka', sans-serif;
  background: #fff;
  border: 3px solid #ffd9a8;
  border-radius: 18px;
  color: #6b5b8a;
  box-shadow: 0 3px 0 #ffd9a8;
}
body.portal-kids #view-hor .next-btn:hover { border-color: #ff7a59; color: #ff7a59; }
body.portal-kids #view-hor .feedback.correct { color: #3d7a35; font-family: 'Fredoka', sans-serif; font-weight: 600; }
body.portal-kids #view-hor .feedback.wrong { color: #c44; font-family: 'Fredoka', sans-serif; font-weight: 600; }
body.portal-kids #view-hor .stat-card .label { color: #b8a0c0; font-family: 'Fredoka', sans-serif; }
body.portal-kids #view-hor .stat-card .value { color: #ff7a59; font-family: 'Fredoka', sans-serif; font-weight: 700; }
body.portal-kids #view-hor .session-stat,
body.portal-kids #view-hor .stat-card {
  background: #fff;
  border: 3px solid #ffd9a8;
  border-radius: 22px;
  box-shadow: 0 3px 0 #ffd9a8;
}
body.portal-kids #view-hor .session-stat .label { color: #b8a0c0; font-family: 'Fredoka', sans-serif; }
body.portal-kids #view-hor .session-stat .value { color: #ff7a59; font-family: 'Fredoka', sans-serif; font-weight: 700; }
body.portal-kids #view-hor .deck-toolbar h2 { font-family: 'Fredoka', sans-serif; color: #2d2a4a; }
body.portal-kids #view-hor .deck-toolbar .deck-count { color: #b8a0c0; font-family: 'Fredoka', sans-serif; }
body.portal-kids #view-hor .deck-refresh {
  background: #fff; border: 3px solid #ffd9a8; border-radius: 18px;
  font-family: 'Fredoka', sans-serif; font-weight: 600; color: #6b5b8a;
  box-shadow: 0 3px 0 #ffd9a8;
}
body.portal-kids #view-hor .deck-refresh:hover { border-color: #ff7a59; color: #ff7a59; }
body.portal-kids #view-hor .deck-list {
  background: #fff; border: 3px solid #ffd9a8; border-radius: 22px;
  box-shadow: 0 3px 0 #ffd9a8;
}
body.portal-kids #view-hor .deck-num { color: #b8a0c0; font-family: 'Fredoka', sans-serif; }
body.portal-kids #view-hor .deck-da { font-family: 'Fredoka', sans-serif; color: #2d2a4a; }
body.portal-kids #view-hor .deck-en { font-family: 'Fredoka', sans-serif; color: #6b5b8a; }
body.portal-kids #view-hor .deck-cat { color: #ff7a59; font-family: 'Fredoka', sans-serif; opacity: 1; }
body.portal-kids #view-hor .deck-item.active { background: rgba(255, 122, 89, 0.1); box-shadow: inset 3px 0 0 #ff7a59; }
body.portal-kids #view-hor .deck-item.correct { box-shadow: inset 3px 0 0 #a8d995; }
body.portal-kids #view-hor .deck-item.wrong { box-shadow: inset 3px 0 0 #ff9999; }
body.portal-kids #view-hor .deck-mark { color: #ff7a59; font-family: 'Fredoka', sans-serif; font-weight: 700; }
body.portal-kids #view-hor .session-done { border-color: #a8d995; box-shadow: 0 4px 0 #a8d995; }
body.portal-kids #view-hor .session-done h2 { font-family: 'Fredoka', sans-serif; color: #2d2a4a; }
body.portal-kids #view-hor .session-done p { color: #6b5b8a; font-family: 'Fredoka', sans-serif; }
body.portal-kids #view-hor .session-done .btn {
  font-family: 'Fredoka', sans-serif; background: #fff; border: 3px solid #ffd9a8;
  border-radius: 18px; color: #6b5b8a; box-shadow: 0 3px 0 #ffd9a8;
}
body.portal-kids #view-hor .session-done .btn:hover { border-color: #ff7a59; color: #ff7a59; }
body.portal-kids #view-hor .skip-btn {
  font-family: 'Fredoka', sans-serif; background: #fff; border: 3px solid #ffd9a8;
  border-radius: 18px; color: #6b5b8a; box-shadow: 0 3px 0 #ffd9a8;
}
body.portal-kids #view-hor .skip-btn:hover { border-color: #ff7a59; color: #ff7a59; }
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
#view-skriv .main { margin-top: var(--total-h); }
#view-overset .main { margin-top: var(--total-h); }
#view-tale .main { margin-top: var(--total-h); }
#view-tale .player-section { top: calc(var(--total-h) + 16px); }
#view-tale .tale-layout { min-height: calc(100vh - var(--total-h) - 210px); }
#view-hor .main { margin-top: var(--total-h); }
#view-hor .player-section { top: calc(var(--total-h) + 16px); }
#view-hor .hor-layout { min-height: calc(100vh - var(--total-h) - 210px); }

/* Hide each app's toolbar when its view isn't active (toolbars are
   position:fixed so visibility doesn't follow display:none ancestors
   when display is set on the ancestor itself, but does when toolbars
   live inside a display:none subtree — which they do here. This rule is
   belt-and-suspenders.) */
.view:not(.active) .app-toolbar { display: none !important; }

/* Portal owns global kids mode — hide Ord's duplicate Kids tab. */
#view-ord #mode-kids-btn { display: none !important; }
/* Words/Verbs clash with portal kids styling — header toggle controls mode. */
body.portal-kids #view-ord .mode-toggle { display: none !important; }

/* Ord toolbar stacks a filters row (category + search) on mobile. */
#view-ord .app-toolbar {
  flex-direction: column;
  align-items: stretch;
  height: auto;
  padding: 0;
  justify-content: flex-start;
}
#view-ord .app-toolbar .toolbar-main {
  display: flex;
  align-items: center;
  justify-content: space-between;
  min-height: var(--toolbar-h);
  width: 100%;
  padding: 0 24px;
  flex-wrap: wrap;
  gap: 8px;
}
#view-ord .app-toolbar .topbar {
  display: none;
  width: 100%;
  position: static;
  z-index: auto;
  border-top: 1px solid var(--border);
  border-bottom: none;
}

/* Inside the toolbar the original CSS used the danskord `header` declarations
   for layout: `display:flex; align-items:center; justify-content:space-between; padding:0 24px;
   border-bottom:1px solid var(--border); background: rgba(14,17,23,0.95); backdrop-filter: blur(12px);`
   These transferred via the `header -> .app-toolbar` selector rewrite, so the
   toolbar already has the right look. Skriv's header had nearly identical
   declarations so it does too. */

/* ─── Mobile ───────────────────────────────────────────────────────
   Portal header → single row with hamburger + left drawer nav.
   App toolbars compact; Ord stacks filters as a second fixed row. */
@media (max-width: 700px) {
  :root {
    --header-h: calc(52px + env(safe-area-inset-top, 0px));
    --toolbar-h: 48px;
  }

  /* ── Portal header + drawer nav ── */
  .portal-menu-btn { display: inline-flex; flex-shrink: 0; }
  .portal-bar {
    height: var(--header-h);
    flex-wrap: nowrap;
    align-items: center;
    padding: 0 12px;
    padding-top: env(safe-area-inset-top, 0px);
    gap: 10px;
  }
  .portal-logo {
    font-size: 17px;
    letter-spacing: -0.3px;
    flex: 1;
    min-width: 0;
  }
  .portal-audience-toggle {
    margin-left: 0;
    flex-shrink: 0;
    padding: 2px;
  }
  .portal-audience-toggle button {
    padding: 5px 11px;
    font-size: 11px;
  }
  .portal-nav--desktop { display: none !important; }
  .portal-nav--drawer { display: flex !important; }
  .portal-nav-backdrop { display: block; }
  .portal-nav--drawer {
    position: fixed;
    top: 0;
    left: 0;
    bottom: 0;
    width: min(320px, 88vw);
    flex: none;
    flex-direction: column;
    align-items: stretch;
    gap: 0;
    margin: 0;
    padding: 0;
    padding-top: env(safe-area-inset-top, 0px);
    overflow-y: auto;
    -webkit-overflow-scrolling: touch;
    background: linear-gradient(180deg, #1c2333 0%, #141a26 100%);
    box-shadow: 12px 0 40px rgba(0, 0, 0, 0.5);
    z-index: 310;
    transform: translateX(-105%);
    transition: transform 0.28s cubic-bezier(0.4, 0, 0.2, 1), visibility 0.28s;
    visibility: hidden;
    pointer-events: none;
  }
  body.portal-kids .portal-nav--drawer,
  body.mode-kids .portal-nav--drawer {
    background: linear-gradient(180deg, #fff8ef 0%, #fff0e4 100%);
  }
  body.portal-nav-open .portal-nav--drawer {
    transform: translateX(0);
    visibility: visible;
    pointer-events: auto;
  }
  .portal-nav--drawer .portal-nav-drawer-head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 18px 16px 10px;
    border-bottom: none;
    align-self: stretch;
  }
  .portal-nav--drawer .portal-nav-links {
    display: flex;
    flex-direction: column;
    align-items: stretch;
    align-self: stretch;
    width: 100%;
    gap: 6px;
    padding: 6px 12px calc(24px + env(safe-area-inset-bottom, 0px));
    box-sizing: border-box;
  }
  .portal-nav--drawer .portal-nav-links a {
    display: flex;
    align-items: center;
    justify-content: flex-start;
    text-align: left;
    width: 100%;
    max-width: 100%;
    box-sizing: border-box;
    gap: 14px;
    padding: 12px 14px;
    font-size: inherit;
    font-weight: inherit;
    border: 1px solid transparent;
    background: transparent;
    border-radius: 12px;
    min-height: 0;
    transition: background 0.15s, border-color 0.15s, opacity 0.15s;
    -webkit-tap-highlight-color: transparent;
  }
  .portal-nav--drawer .portal-nav-links a:hover {
    background: transparent;
    border-color: transparent;
    color: inherit;
    opacity: 0.88;
  }
  .portal-nav--drawer .portal-nav-links a.active {
    background: rgba(79, 142, 247, 0.1);
    border: 1px solid rgba(79, 142, 247, 0.32);
    box-shadow: none;
    color: inherit;
    opacity: 1;
  }
  /* Highlight container only — title/desc/chevron keep default drawer text styles. */
  .portal-nav--drawer .portal-nav-links a.active .portal-drawer-title,
  .portal-nav--drawer .portal-nav-links a.active .portal-drawer-title em,
  .portal-nav--drawer .portal-nav-links a.active .portal-drawer-desc,
  .portal-nav--drawer .portal-nav-links a.active .portal-drawer-chevron {
    color: inherit;
  }
  .portal-nav--drawer .portal-nav-links a.active .portal-drawer-title { color: var(--text); }
  .portal-nav--drawer .portal-nav-links a.active .portal-drawer-title em { color: var(--accent2); }
  .portal-nav--drawer .portal-nav-links a.active .portal-drawer-desc { color: var(--text-muted); }
  .portal-nav--drawer .portal-nav-links a.active .portal-drawer-chevron { color: var(--text-dim); opacity: 0.7; }
  body.portal-kids .portal-nav--drawer .portal-nav-links a.active,
  body.mode-kids .portal-nav--drawer .portal-nav-links a.active {
    color: inherit;
    background: #fff0e0;
    border: 1px solid #ffd9a8;
  }
  body.portal-kids .portal-nav--drawer .portal-nav-links a.active .portal-drawer-title,
  body.mode-kids .portal-nav--drawer .portal-nav-links a.active .portal-drawer-title { color: #2d2a4a; }
  body.portal-kids .portal-nav--drawer .portal-nav-links a.active .portal-drawer-title em,
  body.mode-kids .portal-nav--drawer .portal-nav-links a.active .portal-drawer-title em { color: #ff7a59; }
  body.portal-kids .portal-nav--drawer .portal-nav-links a.active .portal-drawer-desc,
  body.mode-kids .portal-nav--drawer .portal-nav-links a.active .portal-drawer-desc { color: #6b5b8a; }
  body.portal-kids .portal-nav--drawer .portal-nav-links a .portal-drawer-title,
  body.mode-kids .portal-nav--drawer .portal-nav-links a .portal-drawer-title {
    font-family: 'Fredoka', sans-serif;
    font-weight: 700;
    color: #2d2a4a;
  }
  body.portal-kids .portal-nav--drawer .portal-nav-links a .portal-drawer-title em,
  body.mode-kids .portal-nav--drawer .portal-nav-links a .portal-drawer-title em { color: #ff7a59; }
  body.portal-kids .portal-nav--drawer .portal-nav-links a .portal-drawer-desc,
  body.mode-kids .portal-nav--drawer .portal-nav-links a .portal-drawer-desc {
    font-family: 'Fredoka', sans-serif;
    color: #6b5b8a;
  }

  /* ── Shared app toolbars ── */
  #view-ord .app-toolbar,
  #view-skriv .app-toolbar,
  #view-overset .app-toolbar,
  #view-tale .app-toolbar,
  #view-hor .app-toolbar {
    padding-left: 12px;
    padding-right: 12px;
    box-shadow:
      inset 0 1px 0 rgba(255,255,255,0.04),
      0 4px 12px rgba(0,0,0,0.28);
  }
  #view-skriv .app-toolbar .logo,
  #view-overset .app-toolbar .logo,
  #view-tale .app-toolbar .logo,
  #view-hor .app-toolbar .logo,
  #view-ord .app-toolbar .toolbar-main .logo {
    font-size: 18px;
  }

  /* ── Ord toolbar ── */
  #view-ord .app-toolbar .toolbar-main {
    min-height: 48px;
    padding: 4px 0;
    flex-wrap: nowrap;
    gap: 6px;
  }
  #view-ord .app-toolbar .toolbar-main .header-right {
    gap: 4px;
    flex-wrap: nowrap;
    min-width: 0;
  }
  #view-ord .app-toolbar .toolbar-main .stat-pill { display: none; }
  #view-ord .app-toolbar .toolbar-main .mode-toggle {
    margin-right: 0;
    padding: 2px;
  }
  #view-ord .app-toolbar .toolbar-main .mode-toggle button {
    padding: 4px 10px;
    font-size: 11px;
  }
  #view-ord .app-toolbar .toolbar-main .btn:not(.btn-shuffle):not(.btn-reset):not(.btn-refresh):not(#known-filter-btn),
  #view-ord .app-toolbar .toolbar-main .btn-shuffle,
  #view-ord .app-toolbar .toolbar-main #known-filter-btn,
  #view-ord .app-toolbar .toolbar-main .btn-reset {
    font-size: 0;
    padding: 6px 9px;
    min-width: 34px;
    min-height: 34px;
  }
  #view-ord .app-toolbar .toolbar-main .btn::first-letter,
  #view-ord .app-toolbar .toolbar-main .btn-shuffle::first-letter,
  #view-ord .app-toolbar .toolbar-main #known-filter-btn::first-letter,
  #view-ord .app-toolbar .toolbar-main .btn-reset::first-letter {
    font-size: 15px;
  }
  #view-ord .app-toolbar .topbar {
    display: flex;
    padding: 6px 0 8px;
    gap: 8px;
    border-top: 1px solid rgba(42, 51, 71, 0.45);
    background: rgba(0, 0, 0, 0.12);
  }
  body.portal-kids #view-ord .app-toolbar .topbar,
  body.mode-kids #view-ord .app-toolbar .topbar {
    border-top-color: rgba(255, 217, 168, 0.65);
    background: rgba(255, 255, 255, 0.35);
  }
  #view-ord .main > .topbar { display: none !important; }
  #view-ord .shell, #view-ord .sidebar {
    --total-h: calc(var(--header-h) + 48px + 44px);
  }
}
@media (max-width: 500px) {
  .portal-logo { font-size: 16px; }
  .portal-audience-toggle button { padding: 4px 9px; font-size: 10px; }
  .portal-menu-btn { width: 38px; height: 38px; }
}
</style>
"""

PORTAL_HEADER_AND_LANDING = r"""
<div class="portal-bar">
  <button type="button" class="portal-menu-btn" id="portal-menu-btn" aria-label="Open navigation menu" aria-expanded="false" aria-controls="portal-nav">
    <span class="portal-menu-bar"></span>
    <span class="portal-menu-bar"></span>
    <span class="portal-menu-bar"></span>
  </button>
  <a href="./" class="portal-logo">dansk<span>learn</span></a>
  <nav class="portal-nav portal-nav--desktop" id="portal-nav-desktop" aria-label="Main navigation">
    <div class="portal-nav-links">
      <a href="./"        data-route="home">Home</a>
      <a href="./ord"     data-route="ord">Ord</a>
      <a href="./skriv"   data-route="skriv">Skriv</a>
      <a href="./overset" data-route="overset">Oversæt</a>
      <a href="./tale"    data-route="tale">Tale</a>
      <a href="./hor"     data-route="hor">Hør</a>
    </div>
  </nav>
  <div class="portal-audience-toggle" role="group" aria-label="Learning mode">
    <button type="button" id="portal-mode-adult" class="active" aria-pressed="true">Adult</button>
    <button type="button" id="portal-mode-kids" aria-pressed="false">Kids</button>
  </div>
</div>
<nav class="portal-nav portal-nav--drawer" id="portal-nav" aria-label="Main navigation" aria-hidden="true">
  <div class="portal-nav-drawer-head">
    <div class="portal-nav-drawer-brand">dansk<span>learn</span></div>
    <button type="button" class="portal-nav-close" id="portal-nav-close" aria-label="Close menu">×</button>
  </div>
  <div class="portal-nav-links">
    <a href="./" data-route="home">
      <span class="portal-drawer-icon" aria-hidden="true">🏠</span>
      <span class="portal-drawer-text">
        <span class="portal-drawer-title">Home</span>
        <span class="portal-drawer-desc">Portal overview & modules</span>
      </span>
      <span class="portal-drawer-chevron" aria-hidden="true">›</span>
    </a>
    <a href="./ord" data-route="ord">
      <span class="portal-drawer-icon" aria-hidden="true">📚</span>
      <span class="portal-drawer-text">
        <span class="portal-drawer-title">dansk<em>ord</em></span>
        <span class="portal-drawer-desc">Vocabulary flashcards & verbs</span>
      </span>
      <span class="portal-drawer-chevron" aria-hidden="true">›</span>
    </a>
    <a href="./skriv" data-route="skriv">
      <span class="portal-drawer-icon" aria-hidden="true">✍️</span>
      <span class="portal-drawer-text">
        <span class="portal-drawer-title">dansk<em>skriv</em></span>
        <span class="portal-drawer-desc">Type along with Danish text</span>
      </span>
      <span class="portal-drawer-chevron" aria-hidden="true">›</span>
    </a>
    <a href="./overset" data-route="overset">
      <span class="portal-drawer-icon" aria-hidden="true">🌐</span>
      <span class="portal-drawer-text">
        <span class="portal-drawer-title">dansk<em>oversæt</em></span>
        <span class="portal-drawer-desc">Translate English → Danish</span>
      </span>
      <span class="portal-drawer-chevron" aria-hidden="true">›</span>
    </a>
    <a href="./tale" data-route="tale">
      <span class="portal-drawer-icon" aria-hidden="true">🗣️</span>
      <span class="portal-drawer-text">
        <span class="portal-drawer-title">dansk<em>tale</em></span>
        <span class="portal-drawer-desc">Listen &amp; repeat phrases</span>
      </span>
      <span class="portal-drawer-chevron" aria-hidden="true">›</span>
    </a>
    <a href="./hor" data-route="hor">
      <span class="portal-drawer-icon" aria-hidden="true">👂</span>
      <span class="portal-drawer-text">
        <span class="portal-drawer-title">dansk<em>hør</em></span>
        <span class="portal-drawer-desc">Listening comprehension quiz</span>
      </span>
      <span class="portal-drawer-chevron" aria-hidden="true">›</span>
    </a>
  </div>
</nav>
<div class="portal-nav-backdrop" id="portal-nav-backdrop" aria-hidden="true"></div>

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
    <p>Built by <a href="https://github.com/swapnild2111" target="_blank" rel="noopener">Swapnil Deshpande</a> — open source on
      <a href="https://github.com/swapnild2111/dansklearn" target="_blank" rel="noopener">
        <svg class="footer-gh-icon" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M12 .5a11.5 11.5 0 0 0-3.63 22.41c.58.1.79-.25.79-.56v-2c-3.2.7-3.87-1.36-3.87-1.36-.53-1.35-1.3-1.7-1.3-1.7-1.06-.73.08-.71.08-.71 1.18.08 1.8 1.21 1.8 1.21 1.04 1.78 2.73 1.27 3.4.97.1-.75.4-1.27.74-1.56-2.55-.29-5.24-1.28-5.24-5.7 0-1.26.45-2.29 1.2-3.1-.12-.3-.52-1.48.12-3.08 0 0 .97-.31 3.18 1.18a11 11 0 0 1 5.8 0c2.2-1.49 3.17-1.18 3.17-1.18.65 1.6.24 2.78.12 3.08.75.81 1.2 1.84 1.2 3.1 0 4.44-2.7 5.4-5.26 5.69.41.36.78 1.06.78 2.13v3.16c0 .31.21.67.8.56A11.5 11.5 0 0 0 12 .5z"/></svg>GitHub
      </a></p>
    <p class="footer-sub">MIT licensed. © <span id="portal-year">2026</span> · Free to use, study, and share.</p>
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
const SITE_ORIGIN = '__SITE_ORIGIN__';
const SITE_BASE = '__SITE_BASE__';
const GA_MEASUREMENT_ID = '__GA_MEASUREMENT_ID__';
const RouteMeta = __ROUTE_META_JSON__;
function setMetaTag(name, content, attr) {
  attr = attr || 'name';
  if (!content) return;
  let el = document.querySelector('meta[' + attr + '="' + name + '"]');
  if (!el) {
    el = document.createElement('meta');
    el.setAttribute(attr, name);
    document.head.appendChild(el);
  }
  el.setAttribute('content', content);
}
function trackPageView(meta) {
  if (typeof gtag !== 'function' || !GA_MEASUREMENT_ID) return;
  gtag('event', 'page_view', {
    page_title: meta.title,
    page_location: SITE_ORIGIN + SITE_BASE + (meta.path === '/' ? '/' : meta.path),
    page_path: meta.path,
  });
}
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
  const url = SITE_ORIGIN + SITE_BASE + (meta.path === '/' ? '/' : meta.path);
  document.title = meta.title;
  let link = document.querySelector('link[rel="canonical"]');
  if (!link) {
    link = document.createElement('link');
    link.rel = 'canonical';
    document.head.appendChild(link);
  }
  link.href = url;
  setMetaTag('description', meta.description);
  setMetaTag('og:title', meta.title, 'property');
  setMetaTag('og:description', meta.description, 'property');
  setMetaTag('og:url', url, 'property');
  setMetaTag('twitter:title', meta.title);
  setMetaTag('twitter:description', meta.description);
  trackPageView(meta);
}
function openPortalNav() {
  document.body.classList.add('portal-nav-open');
  const btn = document.getElementById('portal-menu-btn');
  const nav = document.getElementById('portal-nav');
  const backdrop = document.getElementById('portal-nav-backdrop');
  if (btn) btn.setAttribute('aria-expanded', 'true');
  if (nav) nav.setAttribute('aria-hidden', 'false');
  if (backdrop) backdrop.setAttribute('aria-hidden', 'false');
}
function closePortalNav() {
  if (!document.body.classList.contains('portal-nav-open')) return;
  document.body.classList.remove('portal-nav-open');
  const btn = document.getElementById('portal-menu-btn');
  const nav = document.getElementById('portal-nav');
  const backdrop = document.getElementById('portal-nav-backdrop');
  if (btn) btn.setAttribute('aria-expanded', 'false');
  if (window.matchMedia('(max-width: 700px)').matches && nav) nav.setAttribute('aria-hidden', 'true');
  if (backdrop) backdrop.setAttribute('aria-hidden', 'true');
}
function setActiveView(name) {
  closePortalNav();
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

document.getElementById('portal-menu-btn')?.addEventListener('click', e => {
  e.stopPropagation();
  if (document.body.classList.contains('portal-nav-open')) closePortalNav();
  else openPortalNav();
});
document.getElementById('portal-nav-close')?.addEventListener('click', closePortalNav);
document.getElementById('portal-nav-backdrop')?.addEventListener('click', closePortalNav);
document.addEventListener('keydown', e => {
  if (e.key === 'Escape') closePortalNav();
});
document.querySelectorAll('.portal-nav-links a').forEach(a => {
  a.addEventListener('click', closePortalNav);
});
if (window.matchMedia('(max-width: 700px)').matches) {
  document.getElementById('portal-nav')?.setAttribute('aria-hidden', 'true');
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
  updateAudienceToggle(on);
}
function updateAudienceToggle(kidsOn) {
  const adult = document.getElementById('portal-mode-adult');
  const kids = document.getElementById('portal-mode-kids');
  if (adult) {
    adult.classList.toggle('active', !kidsOn);
    adult.setAttribute('aria-pressed', kidsOn ? 'false' : 'true');
  }
  if (kids) {
    kids.classList.toggle('active', kidsOn);
    kids.setAttribute('aria-pressed', kidsOn ? 'true' : 'false');
  }
}
function applyPortalKids(on) {
  localStorage.setItem(PORTAL_KIDS_KEY, on ? '1' : '0');
  syncPortalKidsChrome();
  syncOrdKidsMode();
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
const portalModeAdult = document.getElementById('portal-mode-adult');
const portalModeKids = document.getElementById('portal-mode-kids');
if (portalModeAdult) portalModeAdult.addEventListener('click', () => applyPortalKids(false));
if (portalModeKids) portalModeKids.addEventListener('click', () => applyPortalKids(true));
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
        "setSortMode",
        "selectCat",
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

    site_config = load_site_config()
    ga_id = (site_config.get("gaMeasurementId") or "").strip()
    route_meta_json = json.dumps(
        {
            route["id"]: {
                "title": route["title"],
                "path": route["path"],
                "description": route["description"],
            }
            for route in ROUTES
        },
        ensure_ascii=False,
    )
    footer_script = (
        PORTAL_FOOTER_SCRIPT.replace("__SITE_ORIGIN__", SITE_ORIGIN)
        .replace("__SITE_BASE__", SITE_BASE)
        .replace("__GA_MEASUREMENT_ID__", ga_id)
        .replace("__ROUTE_META_JSON__", route_meta_json)
    )

    parts = [
        build_portal_head(site_config),
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
        footer_script,
        "</body>",
        "</html>",
    ]

    html = "\n".join(parts)
    OUT_PATH.write_text(html, encoding="utf-8")
    NOT_FOUND_PATH.write_text(html, encoding="utf-8")
    write_robots_txt()
    write_sitemap_xml()
    print(f"Built {OUT_PATH} ({OUT_PATH.stat().st_size:,} bytes)")
    print(f"Built {NOT_FOUND_PATH} ({NOT_FOUND_PATH.stat().st_size:,} bytes)")
    print(f"Built {ROBOTS_PATH}")
    print(f"Built {SITEMAP_PATH}")
    if not ga_id:
        print("Note: GA4 disabled — set gaMeasurementId in site.config.json")
    if not (site_config.get("gscVerification") or "").strip():
        print("Note: Search Console tag missing — set gscVerification in site.config.json")


if __name__ == "__main__":
    try:
        build()
    except Exception as exc:
        print(f"Build failed: {exc}", file=sys.stderr)
        sys.exit(1)
