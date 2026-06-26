<div align="center">

# 🇩🇰 danskLearn

**A free, open-source portal for learning Danish — built for actual learners, not for ad revenue.**

[![Live](https://img.shields.io/badge/Live-swapnild2111.github.io%2Fdansklearn-4f8ef7?style=flat-square)](https://swapnild2111.github.io/dansklearn/)
[![License: MIT](https://img.shields.io/badge/License-MIT-4ade80?style=flat-square)](LICENSE)
[![No build](https://img.shields.io/badge/Build-Python%20only-7dd3fc?style=flat-square)](#for-developers)
[![No tracking](https://img.shields.io/badge/Tracking-none*-f87171?style=flat-square)](#privacy)

[**👉 Open the app**](https://swapnild2111.github.io/dansklearn/)

</div>

---

## What's inside

Five focused modules that cover the four ways you actually use a language — reading, writing, listening, and speaking — plus translation between Danish and English. Pick one, learn for ten minutes, come back tomorrow. Your progress is saved locally in your browser.

| Module | Practice | What you do |
|---|---|---|
| 📚 **Ord** | Vocabulary | Flip flashcards through the **1000 most essential Danish words**, with verb conjugations and a colourful **Kids mode** for ages 5–7 |
| ✍️ **Skriv** | Writing | Type along with **fresh news paragraphs from DR.dk**. Live colouring catches mistakes character by character; tap any word for an instant translation |
| 🌐 **Oversæt** | Translation | The reverse: **read English, type the Danish**. A hint icon reveals the original whenever you're stuck |
| 🗣️ **Tale** | Speaking | **Listen and repeat** with Anki-style spaced repetition. Rate each phrase Hard / Good / Easy and the deck schedules the next review for you |
| 👂 **Hør** | Listening | A Danish phrase plays — **pick the right English meaning** from four choices. Distractors come from the same topic to keep things fair |

---

## Why this exists

Most language apps push you toward a paid tier, an account, a daily streak that nags you. **danskLearn doesn't.**

- 🆓 **Completely free** — no ads, no subscriptions, no premium tier
- 🔐 **No account, no email, no signup** — progress is yours, saved in your browser
- 🚫 **No tracking on you** — anonymous, aggregate page-view stats only (see [Privacy](#privacy))
- 📚 **Real content** — vocabulary is the 1000 most useful Danish words; reading practice pulls live from Danmarks Radio
- 📱 **Works on your phone** — responsive layouts; no app store
- 🌐 **Works offline-ish** — typing practice falls back to bundled paragraphs when you're without internet
- 💾 **Your data stays with you** — everything in `localStorage`; nothing leaves your device except API calls for fresh content

It started as two small standalone HTML files I built for myself while learning Danish. It grew into a portal because friends asked for the link.

---

## Standout features

### 🎯 1000 hand-picked words, sorted by usefulness

Not a random word dump. The Ord deck is the **1000 most essential Danish words** — pronouns, common verbs (in their own first-priority bucket), numbers, body, food, daily-life vocabulary, building up to abstract concepts. Search across Danish and English. Filter by initial letter group (A–D, E–H, …). Sort by what you haven't seen, what you've already learned, or shuffle for review.

### 👶 Kids mode for ages 5–7

A separate vocabulary deck of ~200 words paired with friendly emoji, big colourful tap-to-pop cards, a streak counter, and confetti when kids learn a new word. Bright pastel palette, audio-first, no flipping mechanic — just see, hear, tap.

### 📰 Fresh content every day

`Skriv` and `Oversæt` pull live paragraphs from **DR.dk** (Danmarks Radio) — news, politics, culture, sport, tech. Today's headlines, today's vocabulary. Click Refresh whenever you want a fresh set.

### 🎓 Real spaced repetition

`Tale` uses an Anki-lite algorithm. Phrases you find hard come back tomorrow. Phrases you've nailed don't reappear for a week. The deck schedules itself — you just rate each phrase honestly.

### 🔊 Audio + IPA for every word

Danish pronunciation matters. Every flashcard, every paragraph, every phrase has a play button. Audio uses your operating system's built-in Danish voice — danskLearn detects what you have and shows a small **voice indicator** in the toolbar (green = high-quality, amber = OK, red = no Danish voice installed). Click the indicator to see step-by-step instructions for installing a better Danish voice on your specific OS.

Most cards also display the **IPA transcription** (`[ˈhunˀ]`, `[ˈkad]`, …) so you have a visual reference for tricky sounds — the glottal stop, the soft `d`, the unstressed schwa — even if your device's voice is rough.

### 📊 Live progress dashboard

The landing page shows at-a-glance how you're doing in each module — words known, paragraphs completed, phrases reviewed today, listening accuracy, current streak. No nagging, just a quiet "here's where you left off."

---

## Improving Danish audio quality

Audio in danskLearn uses your **device's text-to-speech engine** (the Web Speech API). Quality varies wildly: macOS has Sara/Magnus built in, Windows has Microsoft Helle (and the much better "Helle Online (Natural)" on Windows 11), Android has Google's Danish TTS, iOS has a downloadable Danish voice. Linux usually has nothing.

The portal's toolbar shows a **small voice-quality pill** ("Voice: Sara" with a green/amber/red dot). Click it for OS-specific installation instructions:

- **macOS**: Settings → Accessibility → Spoken Content → System voice → add a Danish voice
- **Windows 10/11**: Settings → Time & language → Language → add Danish → Language options → install Speech (look for "Helle Online (Natural)")
- **iOS**: Settings → Accessibility → Spoken Content → Voices → Danish → download
- **Android**: Install/update Google Speech Services from the Play Store, then Settings → Languages → Text-to-speech → Google Speech Services → download Danish
- **Linux**: Built-in support is limited; Edge or Chrome with a Microsoft account sometimes exposes the Helle Online voice

After installing a Danish voice you may need to reload the page once. The portal also displays the **IPA transcription** under most words (e.g. `[ˈhunˀ]` for "hund") so you have a visual pronunciation reference regardless of audio quality.

---

## Quick start

### Use it (just open the link)

👉 **<https://swapnild2111.github.io/dansklearn/>**

That's it. Bookmark the page, open it whenever, leave it whenever. Your browser remembers where you left off.

### Run it locally

Want to tinker, fork, or run it offline?

```bash
git clone https://github.com/swapnild2111/dansklearn.git
cd dansklearn
python3 -m http.server 8765
# open http://localhost:8765/
```

No npm. No bundler. No build step required to **run** the site — the committed `index.html` works as-is. (To rebuild after editing source files, see [For developers](#for-developers) below.)

---

## Privacy

danskLearn collects **no personal data** about you. Specifically:

- **No account** — there's nothing to sign up for.
- **No cookies** — the site doesn't set any.
- **Your progress** lives entirely in your browser's `localStorage`. Clear your browser data and it's gone — no copy lives on a server somewhere.
- **API calls to DR.dk and MyMemory** (for fresh paragraphs and translation) are made directly from your browser. They see your IP like any other website you visit; the danskLearn portal does not.
- **Anonymous page views** *may* be reported to Google Analytics 4 if the maintainer has configured an analytics ID. This counts visits, not visitors — no advertising IDs, no behavioural profiles.

If you'd rather not have *any* tracking at all, use a content blocker (uBlock Origin, NextDNS, etc.); the site works exactly the same.

---

## Share it

If you find this useful, share the link — that's the only growth channel:

- The live URL is shareable on any platform: <https://swapnild2111.github.io/dansklearn/>
- Both Facebook and WhatsApp generate a nice preview card when you paste the link (Danish flag + tagline).
- A friend learning Danish? Just send them the URL — no signup, no friction, no "download the app" pitch.

---

## Contribute

Pull requests are very welcome. Some ideas:

- **More words** — expand the 1000-word list, fix translations, suggest better example sentences (see `src/danskord.html`).
- **More phrases** — extend the 80-phrase bank used by Tale and Hør (see `src/phrases.js`).
- **More categories** — the kids-mode taxonomy could double in size.
- **More modules** — listening to actual DR podcasts? Conjugation drills? A flashcard import/export?
- **Bug reports & UX feedback** — open an issue with a screenshot if something looks off in your browser.

The project is intentionally **dependency-free**: no npm, no framework, no build server. The only tool is `python3`. Keep that the case in PRs.

---

## For developers

> Skip this section if you're just here to learn Danish.

### Repository layout

```
dansklearn/
├── README.md              # this file
├── LICENSE                # MIT
├── build.py               # assembles index.html from src/
├── site.config.json       # optional: GA4 + Search Console tokens
├── index.html             # build output — what users open
├── 404.html               # SPA shell fallback for clean URLs
├── robots.txt             # build output
├── sitemap.xml            # build output
├── favicon.svg            # Dannebrog flag
├── og-image.svg           # social preview (1200×630)
└── src/
    ├── danskord.html      # standalone — 1000-word flashcards
    ├── danskskriv.html    # standalone — Danish typing
    ├── danskoverset.html  # standalone — English→Danish typing
    ├── dansktale.html     # standalone — speaking practice (SR)
    ├── danskhor.html      # standalone — listening quiz
    ├── phrases.js         # 80-phrase bank shared by tale + hor
    ├── speech.js          # shared TTS (window.DanskSpeech) + voice indicator
    └── ipa.js             # shared IPA dataset (window.DanskIPA, 816 entries)
```

Every file under `src/` is **standalone-runnable** — open `src/danskord.html` directly in a browser and you get just that module. The merged `index.html` at the repo root is what `build.py` produces.

### How `build.py` works

The build solves three merge challenges:

1. **CSS isolation.** Each source file's `<style>` block gets every selector prefixed with its view's container id (`#view-ord`, `#view-skriv`, …) so rules can't collide. `body { ... }` styles scope to the view container. `header { ... }` rules retarget to `.app-toolbar` (an in-flow sub-toolbar inside the merged document).

2. **Script isolation.** Each source's last `<script>` is wrapped in `window.{Name}App = (function(){ let initialized=false; return { init(){ … } }; })()`. The router calls `init()` the first time the view is shown; subsequent visits are no-ops. Sources that use inline `onclick=` (just `danskord.html`) get those handler functions explicitly forwarded to `window`.

3. **Shared phrase bank.** `phrases.js` defines `window.DanskPhrases.BANK`. Standalone files load it via `<script src="phrases.js">`. The build strips that tag from each body and inlines the bank's contents once at the top of the merged scripts.

4. **Shared TTS + IPA.** `speech.js` and `ipa.js` follow the same standalone-vs-inlined pattern. `speech.js` exposes `window.DanskSpeech` (`speak()`, `pick()` returning `{voice, quality}`, `lookupIpa()`, `mountVoiceIndicator()`, `mountOnboardingBanner()`). `ipa.js` exposes `window.DanskIPA.BANK` — a flat map from lowercase Danish word to IPA string. Each source HTML file loads them via `<script src>` for standalone use; the merged build inlines them once globally.

HTML comments are stripped during the merge so comment text containing `<script>` fragments can't trip the script-stripping regex.

### Edit and rebuild

```bash
# Edit any src/*.html file in your editor
python3 build.py            # writes index.html + 404.html + robots.txt + sitemap.xml
python3 -m http.server 8765
# open http://localhost:8765/
```

If you're only tweaking CSS/markup in one module, just open the source file directly — no rebuild needed until you want the merged portal updated.

### Storage keys

Each module persists independently. None overlap.

| Key                                  | Module    | Stores |
|---|---|---|
| `dk-mode`                            | Ord       | Current mode: `words` / `verbs` / `kids` |
| `dk-known`                           | Ord       | Set of known word indices (Words mode) |
| `dk-known-verbs`                     | Ord       | Set of known verb indices |
| `dk-known-kids`                      | Ord       | Set of known kids-mode word indices |
| `dk-kids-streak`                     | Ord       | `{count, lastDate}` for kids streak |
| `dk-sort`                            | Ord       | Persisted sort mode |
| `danskskriv:session:v1`              | Skriv     | Current 5-paragraph session + typed text |
| `danskoverset:session:v1`            | Overset   | Same shape as Skriv |
| `danskoverset:translation-cache:v1`  | Overset   | Persisted da→en translations (dodges MyMemory's daily quota) |
| `dansktale:progress:v1`              | Tale      | Per-phrase SR state: `{seen, ease, interval, due}` |
| `dansktale:meta:v1`                  | Tale      | `{lastDate, streak, reviewedToday}` |
| `danskor:progress:v1`                | Hør       | `{seen, correct}` (lifetime) |
| `danskor:seen-counts:v1`             | Hør       | Per-phrase seen counts (used for unseen-weighting) |

To wipe progress for one module, clear that module's keys in DevTools → Application → Local Storage.

### External dependencies (runtime only)

- **Google Fonts** — DM Serif Display, Inter, JetBrains Mono, Fredoka (Kids mode).
- **DR.dk RSS feeds** via `api.rss2json.com` (free tier, no auth) — Skriv and Oversæt.
- **MyMemory translation API** (free tier) — Skriv (on-demand) and Oversæt (page load + cached).
- **Web Speech API** (`speechSynthesis`) — pronunciation. Quality depends on the OS's installed Danish voice.
- **Web Audio API** — Hør's correct/wrong sound effects.

Offline fallback paragraphs are bundled in Skriv and Oversæt so the typing modules still work without an internet connection.

### Credits

- **IPA transcriptions** in `src/ipa.js` (816 entries covering ~51% of the vocabulary) were extracted from the publicly-shared *"Danish Dictionary from Beginner to Fluent"* AnkiWeb deck (deck ID `805471301`). IPA strings are factual linguistic data and not subject to copyright; we use only the IPA values, not the audio that deck also contained.
- **DR.dk** — danskskriv and danskoversæt fetch fresh paragraphs from Danmarks Radio's public RSS feeds for typing practice.
- **MyMemory** — translation API used to render English prompts in Oversæt and word-on-tap translations in Skriv.

### SEO, analytics & Search Console

Optional. Configure in `site.config.json`, then rebuild:

| Key | Purpose |
|---|---|
| `gaMeasurementId` | GA4 measurement ID (`G-XXXXXXXXXX`) for traffic analytics |
| `gscVerification` | HTML-tag verification token from Google Search Console |

The build automatically generates per-route meta tags (title, description, canonical URL), Open Graph & Twitter Card tags, JSON-LD structured data, `robots.txt`, and `sitemap.xml`. The `og-image.svg` is bundled.

To wire up Google Analytics 4:

1. Create a GA4 property at [analytics.google.com](https://analytics.google.com/) with a Web data stream for `https://swapnild2111.github.io/dansklearn/`.
2. Paste the Measurement ID into `site.config.json` → `gaMeasurementId`.
3. Run `python3 build.py`, commit, push.

To wire up Search Console:

1. Open [Search Console](https://search.google.com/search-console), add a URL-prefix property.
2. Choose HTML-tag verification and paste the `content="…"` value into `site.config.json` → `gscVerification`.
3. Rebuild, push, click **Verify**, submit the sitemap.

---

## License

**MIT** — see [LICENSE](LICENSE). Free to use, study, modify, and redistribute, including commercially, as long as the copyright notice stays in place.

Built by [Swapnil Deshpande](https://github.com/swapnild2111). Contributions welcome.
