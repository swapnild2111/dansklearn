# danskLearn

A growing portal for learning Danish — vocabulary, writing, listening,
speaking, and translation. Five modules in one single-page app, no
framework, no build step beyond a small Python script.

Live: https://swapnild2111.github.io/dansklearn/

---

## SEO, analytics & Search Console

The portal ships with built-in SEO and optional Google integrations. Configure
them in `site.config.json`, then rebuild:

```bash
python3 build.py
```

| Key | Purpose |
|---|---|
| `gaMeasurementId` | GA4 measurement ID (`G-XXXXXXXXXX`) for traffic analytics |
| `gscVerification` | HTML-tag verification token from Google Search Console |

### What the build generates

- **Per-route meta** — title, description, canonical URL (updated on SPA navigation)
- **Open Graph & Twitter Card** tags for link previews
- **JSON-LD** structured data (`WebSite` + `WebApplication`)
- **`robots.txt`** — allows crawlers and points to the sitemap
- **`sitemap.xml`** — all six public routes (`/`, `/ord`, `/skriv`, …)
- **`og-image.svg`** — social preview image (1200×630)

### Google Analytics 4

1. In [Google Analytics](https://analytics.google.com/), create a **GA4 property**.
2. Add a **Web** data stream for `https://swapnild2111.github.io/dansklearn/`.
3. Copy the **Measurement ID** (`G-…`) into `site.config.json` → `gaMeasurementId`.
4. Run `python3 build.py`, commit, and push. Page views are tracked on each route change.

### Google Search Console

1. Open [Google Search Console](https://search.google.com/search-console).
2. Add a **URL-prefix** property: `https://swapnild2111.github.io/dansklearn/`
3. Choose **HTML tag** verification and copy the `content="…"` value.
4. Paste it into `site.config.json` → `gscVerification`.
5. Rebuild, push, then click **Verify** in Search Console.
6. Submit the sitemap: `https://swapnild2111.github.io/dansklearn/sitemap.xml`

---

## Modules

| Module | Route | What it does |
|---|---|---|
| **danskord**     | `/ord`     | Flashcards for the 1000 most essential Danish words, plus verb conjugations and a kids-friendly mode for ages 5–7 |
| **danskskriv**   | `/skriv`   | Type along with fresh DR.dk paragraphs. Live colouring catches mistakes; tap any word for an English translation |
| **danskoversæt** | `/overset` | Same fresh paragraphs, reversed: read English, type the Danish translation. Hint icon reveals the original |
| **dansktale**    | `/tale`    | Listen-and-repeat with Anki-lite spaced repetition. Self-rate Hard / Good / Easy and the deck schedules itself |
| **danskhør**     | `/hor`     | Listen to a Danish phrase, pick the English meaning from four choices. Distractors come from the same topic |

The home page (`/`) lists all five modules with a live progress snapshot
read from `localStorage`.

---

## Repository layout

```
dansklearn/
├── README.md              # this file
├── build.py               # assembles index.html from the source files in src/
├── site.config.json       # GA4 + Search Console tokens
├── index.html             # build output — what users actually open
├── 404.html               # same SPA shell — GitHub Pages fallback for clean URLs
├── robots.txt             # build output — crawler rules + sitemap link
├── sitemap.xml            # build output — all public routes
├── favicon.svg
├── og-image.svg           # social preview image
└── src/
    ├── danskord.html      # standalone flashcards app (1000 words)
    ├── danskskriv.html    # standalone Danish-typing app
    ├── danskoverset.html  # standalone English→Danish typing app
    ├── dansktale.html     # standalone speaking-practice app
    ├── danskhor.html      # standalone listening-quiz app
    └── phrases.js         # shared 80-phrase bank for tale + hor
```

Every file in `src/` is **standalone-runnable** — open any of them directly
in a browser and you get the same module without the portal chrome. This
mirrors the behaviour the project started with (`danskord.html` and
`danskskriv.html` have always been independent apps).

`build.py` reads the five source files plus `phrases.js`, scopes their CSS
to the merged document, wraps each script in an init-on-first-activation
IIFE, and emits a single `index.html` at the repo root.

---

## Getting started

### Run the merged portal

```bash
python3 build.py            # writes index.html + 404.html
python3 -m http.server 8765 # serve at http://localhost:8765/
```

Open `http://localhost:8765/` — module routes like `/ord` and `/overset` work when served from the repo root.

### Run a single module standalone

Just open the source HTML directly in a browser — no server needed for
modules that don't fetch anything (Tale, Hør). For `danskskriv` and
`danskoversæt` (which fetch RSS) you'll want a local server because some
browsers refuse `fetch()` on `file://` URLs:

```bash
python3 -m http.server 8765
# then open http://localhost:8765/src/dansktale.html
```

### Edit a module

1. Edit the relevant `src/*.html` file.
2. Run `python3 build.py` to regenerate `index.html`.
3. Reload your browser.

If you're only editing CSS or markup inside one module, you can just open
the source file directly to see your changes — no rebuild needed until you
want the merged portal updated.

---

## How `build.py` works

The merge has three challenges, all solved at build time:

1. **CSS isolation.** Each source file's `<style>` block defines rules that
   would collide if dropped into the merged document as-is. `build.py`
   parses each stylesheet and prefixes every selector with the view's
   container id (`#view-ord`, `#view-skriv`, etc.). The source's `body { ... }`
   styles are scoped to the view container; rules targeting the source's own
   fixed `<header>` are retargeted at `.app-toolbar` (the merged document's
   in-view sub-toolbar).

2. **Script isolation.** Each source's last `<script>` block is wrapped in
   an IIFE: `window.{Name}App = (function(){ let initialized=false; return { init(){ ... } }; })()`.
   The router (in `PORTAL_FOOTER_SCRIPT`) calls `init()` the first time the
   user navigates to that view; subsequent navigations are no-ops. Sources
   that use inline `onclick=` attributes (just `danskord.html`) get their
   handler functions explicitly forwarded to `window` after init.

3. **Shared phrase bank.** `phrases.js` defines `window.DanskPhrases.BANK`.
   Standalone files load it with a `<script src="phrases.js">` tag. When
   merged, `build.py` strips that tag from each body and inlines the bank's
   contents once via a top-level `<script id="phrases-bank">` block.

Source HTML comments are stripped during the merge so comment text
containing fragments like `<script>` doesn't trip up the script-stripping
regex.

---

## Storage keys (localStorage)

Modules persist independently. None overlap.

| Key                                  | Module    | Stores |
|---|---|---|
| `dk-mode`                            | Ord       | Current mode: `words` / `verbs` / `kids` |
| `dk-known`                           | Ord       | Set of known word indices (Words mode) |
| `dk-known-verbs`                     | Ord       | Set of known verb indices |
| `dk-known-kids`                      | Ord       | Set of known kids-mode word indices |
| `dk-kids-streak`                     | Ord       | `{count, lastDate}` for kids streak |
| `danskskriv:session:v1`              | Skriv     | Current 5-paragraph session + typed text |
| `danskoverset:session:v1`            | Overset   | Same shape as Skriv |
| `danskoverset:translation-cache:v1`  | Overset   | Persisted da→en translations to dodge mymemory's daily quota |
| `dansktale:progress:v1`              | Tale      | Per-phrase SR state: `{seen, ease, interval, due}` |
| `dansktale:meta:v1`                  | Tale      | `{lastDate, streak, reviewedToday}` |
| `danskor:progress:v1`                | Hør       | `{seen, correct}` (lifetime) |
| `danskor:seen-counts:v1`             | Hør       | Per-phrase seen counts (used for unseen-weighting) |

To wipe progress for a single module, clear that module's keys in
DevTools → Application → Local Storage.

---

## External dependencies

All loaded at runtime — nothing to install:

- **Google Fonts** — DM Serif Display, Inter, JetBrains Mono, Fredoka (kids mode).
- **DR.dk RSS feeds** via `api.rss2json.com` (free tier, no auth) — for Skriv and Overset.
- **mymemory.translated.net** translation API (free tier) — for Skriv (on-demand) and Overset (page load + cached).
- **Web Speech API** (`speechSynthesis`) — for Skriv, Tale, Hør pronunciation. Quality depends on the OS's installed Danish voice.
- **Web Audio API** — for Hør's correct/wrong sound effects.

Offline fallback paragraphs are bundled inside Skriv and Overset so the
typing modules still work without internet.

---

## License

© Swapnil Deshpande. All rights reserved.

Content is provided for personal educational use only.
