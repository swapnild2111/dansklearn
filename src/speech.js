// danskLearn shared speech module — unified Danish TTS across all modules.
//
// Before this module existed, each src/*.html carried its own
// pickDanishVoice / speak with a different voice preference list. This
// produced inconsistent pronunciation quality across modules. Now every
// module that needs Danish audio loads this file (via `<script src>` in
// standalone mode, inlined once at the top of the merged index.html), and
// calls window.DanskSpeech.speak() / .mountVoiceIndicator() / etc.
//
// Audio quality on the Web Speech API depends entirely on the OS-installed
// Danish voice. We:
//   1) detect what the user has and classify quality,
//   2) show a one-time onboarding banner if they have no good voice,
//   3) keep a small voice-indicator pill in each module's toolbar so they
//      can come back to the install instructions later,
//   4) (separately, via opts.audioUrl) allow callers to short-circuit TTS
//      with a pre-recorded MP3 if one is bundled.

(function () {
  if (window.DanskSpeech) return;  // idempotent — merged index.html inlines this once but standalone <script src> in each module may try again on view load

  // ── Voice selection ─────────────────────────────────────────────────
  // Order matters: first match wins. Highest-quality voices first.
  const PREFERRED_VOICES = [
    'Microsoft Helle Online (Natural) - Danish (Denmark)',
    'Google dansk',
    'Microsoft Helle',
    'Sara',
    'Magnus',
    'Naja',
    'Mads',
  ];

  const synth = window.speechSynthesis;
  let _voice = null;
  let _quality = 'none';
  let _voicesLoaded = false;
  const _listeners = new Set();  // re-run when voices load

  function classifyQuality(voice) {
    if (!voice) return 'none';
    const n = (voice.name || '');
    if (/Helle Online \(Natural\)/i.test(n) || /Google dansk/i.test(n)) return 'natural';
    if (/Microsoft Helle/i.test(n) || /^Sara$|^Magnus$|^Naja$|^Mads$/.test(n)) return 'good';
    return 'basic';
  }

  function pickInternal() {
    if (!synth || !synth.getVoices) return { voice: null, quality: 'none' };
    const voices = synth.getVoices();
    if (!voices.length) return { voice: null, quality: 'none' };
    // 1) named preference order
    for (const name of PREFERRED_VOICES) {
      const v = voices.find(v => v.name === name || v.name.includes(name));
      if (v) return { voice: v, quality: classifyQuality(v) };
    }
    // 2) fall back to any da-* voice
    const v = voices.find(v => /^da([-_]|$)/i.test(v.lang));
    return { voice: v || null, quality: v ? 'basic' : 'none' };
  }

  function refreshVoice() {
    const r = pickInternal();
    _voice = r.voice;
    _quality = r.quality;
    // Only mark voices "loaded" once we've actually seen the list populate.
    // Chrome returns [] on first call; if we'd flagged loaded=true immediately
    // we'd mount the onboarding banner under the false belief that quality
    // is 'none', then never remove it after voiceschanged upgrades the answer.
    if (synth && synth.getVoices && synth.getVoices().length > 0) {
      _voicesLoaded = true;
    }
    _listeners.forEach(fn => { try { fn(); } catch (_) {} });
  }

  if (synth) {
    refreshVoice();
    // Chrome / Edge: voices may not be ready on first call.
    if (synth.addEventListener) {
      synth.addEventListener('voiceschanged', refreshVoice);
    } else if ('onvoiceschanged' in synth) {
      synth.onvoiceschanged = refreshVoice;
    }
    // Fallback — if `voiceschanged` never fires (some Firefox/Linux builds),
    // treat the empty list as final after 1.5s so the onboarding banner can
    // show "no Danish voice installed".
    setTimeout(() => {
      if (!_voicesLoaded) {
        _voicesLoaded = true;
        _listeners.forEach(fn => { try { fn(); } catch (_) {} });
      }
    }, 1500);
  }

  // ── Public: pick / speak / cancel ──────────────────────────────────
  function pick() { return { voice: _voice, quality: _quality }; }

  function speak(text, opts) {
    opts = opts || {};
    // Pre-recorded audio override — if the caller has a bundled MP3, use it.
    if (opts.audioUrl) {
      try {
        const a = new Audio(opts.audioUrl);
        a.addEventListener('ended', () => { if (opts.onend) opts.onend(); });
        a.addEventListener('error', () => { if (opts.onerror) opts.onerror(new Error('audio load failed')); else speak(text, Object.assign({}, opts, { audioUrl: null })); });
        if (opts.onstart) a.addEventListener('play', opts.onstart);
        a.play().catch(() => { speak(text, Object.assign({}, opts, { audioUrl: null })); });
        return a;
      } catch (_) {
        // fall through to TTS
      }
    }
    if (!synth) {
      if (opts.onerror) opts.onerror(new Error('no synth'));
      return null;
    }
    try { synth.cancel(); } catch (_) {}
    const u = new SpeechSynthesisUtterance(text);
    if (_voice) u.voice = _voice;
    u.lang = 'da-DK';
    u.rate = (opts.rate != null) ? opts.rate : 0.9;
    if (opts.pitch != null) u.pitch = opts.pitch;
    if (opts.onstart) u.onstart = opts.onstart;
    if (opts.onend)   u.onend   = opts.onend;
    if (opts.onerror) u.onerror = opts.onerror;
    synth.speak(u);
    return u;
  }

  function cancel() {
    if (synth) { try { synth.cancel(); } catch (_) {} }
  }

  // ── OS detection ───────────────────────────────────────────────────
  function detectOS() {
    const ua = (navigator.userAgent || '').toLowerCase();
    const platform = (navigator.platform || '').toLowerCase();
    if (/iphone|ipad|ipod/.test(ua) || /(iphone|ipad|ipod)/.test(platform)) return 'ios';
    // iPadOS 13+ reports macIntel — disambiguate by touch points
    if (platform === 'macintel' && navigator.maxTouchPoints > 1) return 'ios';
    if (/android/.test(ua)) return 'android';
    if (/mac/.test(platform)) return 'mac';
    if (/win/.test(platform)) return 'win';
    if (/linux/.test(platform)) return 'linux';
    return 'unknown';
  }

  function installSteps(os) {
    switch (os) {
      case 'mac': return [
        'Open System Settings → Accessibility → Spoken Content.',
        'Click the info icon next to "System voice" and add a new voice.',
        'Find Danish (Sara or Magnus, or premium "Sara/Magnus enhanced").',
        'Wait for the download to finish, then reload this page.',
      ];
      case 'win': return [
        'Open Settings → Time & language → Language & region.',
        'Add Danish as a preferred language (you don\'t need to switch your display language).',
        'Click Danish → Language options → install Speech.',
        'Look for "Microsoft Helle Online (Natural)" — it sounds best.',
        'Reload this page.',
      ];
      case 'ios': return [
        'Open Settings → Accessibility → Spoken Content → Voices.',
        'Tap Danish, then download a Danish voice.',
        'Reload Safari and this page.',
      ];
      case 'android': return [
        'Install or update Google Speech Services from the Play Store.',
        'Open Settings → System → Languages → Text-to-speech output.',
        'Pick "Google Speech Services" as the engine, then download Danish.',
        'Reload Chrome and this page.',
      ];
      case 'linux': return [
        'Linux browsers usually have no built-in Danish voice.',
        'Install espeak-ng-data and configure your browser\'s speech-dispatcher to use it — quality is limited.',
        'For best results on Linux, try the Edge or Chrome browser with a Microsoft account; some Edge builds include the Helle Online voice.',
      ];
      default: return [
        'Your operating system needs a Danish text-to-speech voice installed for clear pronunciation.',
        'Check your system\'s Accessibility or Language settings for a Danish voice download.',
      ];
    }
  }

  // ── Styles for banner + indicator + modal ──────────────────────────
  function ensureStyle() {
    if (document.getElementById('dansk-speech-style')) return;
    const s = document.createElement('style');
    s.id = 'dansk-speech-style';
    s.textContent = `
      .ds-banner {
        position: relative;
        background: #1a2030;
        border-bottom: 1px solid #2a3347;
        color: #e8edf5;
        font-family: 'Inter', sans-serif;
        font-size: 13px;
        padding: 9px 16px 9px 12px;
        display: flex;
        align-items: center;
        gap: 10px;
        z-index: 95;
      }
      .ds-banner-icon { font-size: 16px; flex-shrink: 0; }
      .ds-banner-text { flex: 1; line-height: 1.4; }
      .ds-banner-text b { color: #ffd166; font-weight: 600; }
      .ds-banner-text a { color: #7dd3fc; text-decoration: underline; cursor: pointer; }
      .ds-banner-dismiss {
        background: transparent; border: 1px solid #3a4359;
        color: #8896ae; font-size: 12px; padding: 4px 10px;
        border-radius: 12px; cursor: pointer; flex-shrink: 0;
        font-family: 'Inter', sans-serif;
      }
      .ds-banner-dismiss:hover { border-color: #f87171; color: #f87171; }

      .ds-voice-pill {
        display: inline-flex; align-items: center; gap: 6px;
        background: transparent;
        border: 1px solid #2a3347;
        border-radius: 14px;
        padding: 3px 10px 3px 8px;
        font-family: 'JetBrains Mono', monospace;
        font-size: 11px;
        color: #8896ae;
        cursor: pointer;
        transition: border-color 0.15s, color 0.15s;
        white-space: nowrap;
        max-width: 180px;
        overflow: hidden;
        text-overflow: ellipsis;
      }
      .ds-voice-pill:hover { border-color: #4f8ef7; color: #e8edf5; }
      .ds-voice-pill .ds-dot {
        width: 7px; height: 7px; border-radius: 50%;
        background: #4a5568; flex-shrink: 0;
      }
      .ds-voice-pill.q-natural .ds-dot { background: #4ade80; }
      .ds-voice-pill.q-good    .ds-dot { background: #facc15; }
      .ds-voice-pill.q-basic   .ds-dot { background: #fb923c; }
      .ds-voice-pill.q-none    .ds-dot { background: #f87171; }

      /* Kids mode overrides */
      body.mode-kids .ds-voice-pill {
        background: #fff;
        border-color: #ffd9a8;
        color: #a4533a;
        font-family: 'Fredoka', sans-serif;
        font-weight: 500;
      }
      body.mode-kids .ds-voice-pill:hover { border-color: #ff7a59; color: #ff7a59; }

      .ds-modal-backdrop {
        position: fixed; inset: 0; background: rgba(0,0,0,0.6);
        backdrop-filter: blur(3px);
        display: none; align-items: center; justify-content: center;
        z-index: 9000; padding: 20px;
      }
      .ds-modal-backdrop.show { display: flex; }
      .ds-modal {
        background: #1c2333;
        border: 1px solid #2a3347;
        border-radius: 16px;
        max-width: 520px; width: 100%;
        box-shadow: 0 20px 60px rgba(0,0,0,0.5);
        color: #e8edf5;
        font-family: 'Inter', sans-serif;
      }
      .ds-modal-head {
        padding: 16px 20px; border-bottom: 1px solid #2a3347;
        display: flex; align-items: center; justify-content: space-between;
      }
      .ds-modal-title {
        font-family: 'DM Serif Display', serif;
        font-size: 18px;
      }
      .ds-modal-close {
        background: transparent; border: none; color: #8896ae;
        font-size: 22px; cursor: pointer; line-height: 1;
        padding: 2px 6px;
      }
      .ds-modal-body { padding: 16px 20px; font-size: 13.5px; line-height: 1.6; }
      .ds-modal-body p { margin: 0 0 10px; color: #8896ae; }
      .ds-modal-body ol { padding-left: 22px; margin: 8px 0 14px; }
      .ds-modal-body li { margin: 4px 0; }
      .ds-modal-body strong { color: #7dd3fc; }
      .ds-modal-foot { padding: 12px 20px 16px; display: flex; justify-content: flex-end; }
      .ds-modal-foot button {
        background: linear-gradient(135deg, #3b5fc0, #4f8ef7);
        color: #fff; border: none; border-radius: 10px;
        padding: 7px 16px; font-size: 13px; cursor: pointer;
      }
    `;
    document.head.appendChild(s);
  }

  // ── Onboarding banner (one-time, dismissable) ───────────────────────
  const BANNER_KEY = 'dansklearn:voice-banner-dismissed';

  function mountOnboardingBanner() {
    if (typeof document === 'undefined') return;
    if (localStorage.getItem(BANNER_KEY) === '1') return;
    // Defer until voices are known — quality may upgrade to 'good' after voiceschanged.
    if (!_voicesLoaded) {
      _listeners.add(mountOnboardingBanner);
      return;
    }
    if (_quality === 'natural' || _quality === 'good') return;
    ensureStyle();
    if (document.getElementById('ds-banner')) return;  // already mounted
    const bar = document.createElement('div');
    bar.id = 'ds-banner';
    bar.className = 'ds-banner';
    const headline = _quality === 'none'
      ? 'No Danish voice installed — audio will use your system default.'
      : 'Danish audio uses a basic voice on your device.';
    bar.innerHTML = `
      <span class="ds-banner-icon">🔊</span>
      <span class="ds-banner-text">
        <b>${headline}</b> For clearer pronunciation, <a class="ds-banner-learn">install a Danish voice</a>.
      </span>
      <button class="ds-banner-dismiss" type="button" aria-label="Dismiss">Got it</button>
    `;
    document.body.insertBefore(bar, document.body.firstChild);
    bar.querySelector('.ds-banner-learn').addEventListener('click', e => { e.preventDefault(); openModal(); });
    bar.querySelector('.ds-banner-dismiss').addEventListener('click', () => {
      try { localStorage.setItem(BANNER_KEY, '1'); } catch (_) {}
      bar.remove();
    });
  }

  // ── Voice-indicator pill ──────────────────────────────────────────
  function mountVoiceIndicator(host) {
    if (typeof document === 'undefined') return;
    if (!host) return;
    const el = (typeof host === 'string') ? document.querySelector(host) : host;
    if (!el) return;
    if (el.querySelector('.ds-voice-pill')) return;  // idempotent
    ensureStyle();
    const pill = document.createElement('button');
    pill.type = 'button';
    pill.className = 'ds-voice-pill q-' + (_quality || 'none');
    pill.title = 'Click to learn how to install a better Danish voice';
    pill.innerHTML = `<span class="ds-dot"></span><span class="ds-voice-label"></span>`;
    function refresh() {
      pill.className = 'ds-voice-pill q-' + (_quality || 'none');
      const label = pill.querySelector('.ds-voice-label');
      const name = _voice ? (_voice.name.length > 22 ? _voice.name.slice(0, 21) + '…' : _voice.name) : 'No Danish voice';
      label.textContent = name;
    }
    refresh();
    _listeners.add(refresh);
    pill.addEventListener('click', openModal);
    el.appendChild(pill);
  }

  // ── Modal (shared for banner-click and pill-click) ────────────────
  function openModal() {
    ensureStyle();
    let backdrop = document.getElementById('ds-modal-backdrop');
    if (!backdrop) {
      backdrop = document.createElement('div');
      backdrop.id = 'ds-modal-backdrop';
      backdrop.className = 'ds-modal-backdrop';
      backdrop.innerHTML = `
        <div class="ds-modal" role="dialog" aria-labelledby="ds-modal-title">
          <div class="ds-modal-head">
            <div class="ds-modal-title" id="ds-modal-title">Improve Danish pronunciation</div>
            <button class="ds-modal-close" type="button" aria-label="Close">×</button>
          </div>
          <div class="ds-modal-body" id="ds-modal-body"></div>
          <div class="ds-modal-foot"><button type="button" class="ds-modal-ok">Close</button></div>
        </div>
      `;
      document.body.appendChild(backdrop);
      backdrop.querySelector('.ds-modal-close').addEventListener('click', closeModal);
      backdrop.querySelector('.ds-modal-ok').addEventListener('click', closeModal);
      backdrop.addEventListener('click', e => { if (e.target === backdrop) closeModal(); });
    }
    // Fresh body content every time (voice may have changed)
    const os = detectOS();
    const osLabels = { mac: 'macOS', win: 'Windows', ios: 'iOS', android: 'Android', linux: 'Linux', unknown: 'your device' };
    const body = backdrop.querySelector('#ds-modal-body');
    body.innerHTML = `
      <p>Danish audio in danskLearn uses your device's text-to-speech engine. The currently selected voice is <strong>${_voice ? _voice.name : 'none'}</strong> (quality: <strong>${_quality}</strong>).</p>
      <p>To improve pronunciation on <strong>${osLabels[os]}</strong>:</p>
      <ol>${installSteps(os).map(s => `<li>${s}</li>`).join('')}</ol>
      <p style="font-size:12px;opacity:0.7;">Detected device: ${os}. Pick the steps for whichever OS you're on if this looks wrong.</p>
    `;
    backdrop.classList.add('show');
  }
  function closeModal() {
    const b = document.getElementById('ds-modal-backdrop');
    if (b) b.classList.remove('show');
  }

  // ── IPA lookup (uses window.DanskIPA.BANK if available) ────────────
  // Returns the IPA string for a Danish word/phrase, or '' if not found.
  // Strips the verb infinitive marker "at " so callers can pass words
  // either as "være" or "at være".
  function lookupIpa(text) {
    if (!text || !window.DanskIPA || !window.DanskIPA.BANK) return '';
    const bank = window.DanskIPA.BANK;
    const norm = String(text).toLowerCase().trim().replace(/^at\s+/i, '');
    return bank[norm] || '';
  }

  // ── Public surface ────────────────────────────────────────────────
  window.DanskSpeech = {
    PREFERRED_VOICES,
    pick,
    speak,
    cancel,
    detectOS,
    installSteps,
    mountOnboardingBanner,
    mountVoiceIndicator,
    openModal,    // exposed so other UIs can deep-link to the install help
    lookupIpa,    // optional IPA lookup; returns '' if no data
  };
})();
