/* MediExplain AI — frontend application logic with full features.
 * Features: Visual Result Charts, Search Tests, PDF Summary Export,
 * Report Comparison, User History, Listen to Full Report. */

(() => {
  const CONFIG = window.MEDIEXPLAIN_CONFIG || { languages: { en: "English" }, demoMode: true };
  let currentLang = "en";
  let selectedFile = null;
  let lastResults = null;
  let fullSpeechUtterance = null;
  let isFullSpeechPlaying = false;

  // ---------------------------------------------------------------- router
  const views = document.querySelectorAll(".view");
  const navButtons = document.querySelectorAll("#nav-links button");

  function goto(viewName) {
    views.forEach(v => v.classList.toggle("active", v.id === `view-${viewName}`));
    navButtons.forEach(b => b.classList.toggle("active", b.dataset.view === viewName));
    window.scrollTo({ top: 0, behavior: "smooth" });

    if (viewName === "history") {
      loadHistory();
    }
  }

  document.querySelectorAll("[data-goto]").forEach(el => {
    el.addEventListener("click", () => goto(el.dataset.goto));
  });
  navButtons.forEach(b => b.addEventListener("click", () => goto(b.dataset.view)));

  // ------------------------------------------------------------ language
  function setLanguage(lang) {
    currentLang = lang;
    document.querySelectorAll("#lang-pill button").forEach(b => b.classList.toggle("active", b.dataset.lang === lang));
    document.querySelectorAll("#upload-lang-row .chip[data-lang]").forEach(b => b.classList.toggle("active", b.dataset.lang === lang));
  }
  document.querySelectorAll("#lang-pill button").forEach(b => b.addEventListener("click", () => setLanguage(b.dataset.lang)));
  document.querySelectorAll("#upload-lang-row .chip[data-lang]").forEach(b => b.addEventListener("click", () => setLanguage(b.dataset.lang)));

  // ------------------------------------------------------- hero animation
  const HERO_FRAMES = [
    { jargon: "Hemoglobin  9.5 g/dL   Ref 12–15", status: "low", text: "Your hemoglobin is a little below the range printed on your report. Worth discussing with your doctor." },
    { jargon: "हिमोग्लोबिन  9.5 g/dL   संदर्भ 12–15", status: "low", text: "तुमचा हिमोग्लोबिन अहवालावरील श्रेणीपेक्षा थोडा कमी आहे. डॉक्टरांशी चर्चा करा." },
    { jargon: "हीमोग्लोबिन  9.5 g/dL   संदर्भ 12–15", status: "low", text: "आपका हीमोग्लोबिन रिपोर्ट पर छपी सीमा से थोड़ा कम है। डॉक्टर से चर्चा करें।" },
  ];
  let heroIndex = 0;
  function cycleHero() {
    const el = HERO_FRAMES[heroIndex];
    const jargonEl = document.getElementById("hero-jargon");
    const plainEl = document.getElementById("hero-plain-text");
    const chipEl = document.querySelector("#hero-plain .status-chip");
    if (!jargonEl) return;
    jargonEl.style.opacity = 0;
    plainEl.style.opacity = 0;
    setTimeout(() => {
      jargonEl.textContent = el.jargon;
      plainEl.textContent = el.text;
      chipEl.className = `status-chip ${el.status}`;
      jargonEl.style.opacity = 1;
      plainEl.style.opacity = 1;
    }, 260);
    heroIndex = (heroIndex + 1) % HERO_FRAMES.length;
  }
  document.querySelectorAll(".transform-line, .transform-plain").forEach(el => {
    el.style.transition = "opacity 260ms ease";
  });
  setInterval(cycleHero, 3600);

  // --------------------------------------------------------------- upload
  const dropzone = document.getElementById("dropzone");
  const fileInput = document.getElementById("file-input");
  const chipHolder = document.getElementById("file-chip-holder");
  const analyzeBtn = document.getElementById("analyze-btn");
  const errorHolder = document.getElementById("upload-error-holder");

  function formatSize(bytes) {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  }

  function setFile(file) {
    selectedFile = file;
    errorHolder.innerHTML = "";
    if (!file) {
      chipHolder.innerHTML = "";
      analyzeBtn.disabled = true;
      return;
    }
    const ext = file.name.split(".").pop().toLowerCase();
    if (!["pdf", "jpg", "jpeg", "png"].includes(ext)) {
      errorHolder.innerHTML = `<div class="error-box">Unsupported file type ".${ext}". Please upload a PDF, JPG, JPEG, or PNG.</div>`;
      selectedFile = null;
      analyzeBtn.disabled = true;
      return;
    }
    chipHolder.innerHTML = `
      <div class="file-chip">
        <div class="meta">
          <div class="name">${file.name}</div>
          <div class="size">${formatSize(file.size)}</div>
        </div>
        <button id="remove-file">Remove</button>
      </div>`;
    document.getElementById("remove-file").addEventListener("click", () => { setFile(null); fileInput.value = ""; });
    analyzeBtn.disabled = false;
  }

  if (dropzone) {
    dropzone.addEventListener("click", () => fileInput.click());
    dropzone.addEventListener("keydown", e => { if (e.key === "Enter" || e.key === " ") fileInput.click(); });
    fileInput.addEventListener("change", () => setFile(fileInput.files[0] || null));

    ["dragover", "dragenter"].forEach(evt =>
      dropzone.addEventListener(evt, e => { e.preventDefault(); dropzone.classList.add("drag-over"); })
    );
    ["dragleave", "drop"].forEach(evt =>
      dropzone.addEventListener(evt, e => { e.preventDefault(); dropzone.classList.remove("drag-over"); })
    );
    dropzone.addEventListener("drop", e => {
      const file = e.dataTransfer.files[0];
      if (file) setFile(file);
    });
  }

  // ------------------------------------------------------------ processing
  const PIPELINE_STEPS = [
    ["Uploading", "Sending your file securely"],
    ["OCR", "Reading the text on the report"],
    ["Extracting", "Finding test names, values and ranges"],
    ["Comparing", "Checking each value against its reference range"],
    ["Explaining", "Writing a plain-language explanation"],
    ["Translating", "Converting to your selected language"],
    ["Preparing voice", "Getting the Listen buttons ready"],
  ];

  function renderStepper(activeIndex, done) {
    const list = document.getElementById("stepper-list");
    if (!list) return;
    list.innerHTML = PIPELINE_STEPS.map(([title, desc], i) => {
      let cls = "";
      if (done) cls = "done";
      else if (i < activeIndex) cls = "done";
      else if (i === activeIndex) cls = "active";
      const dotContent = cls === "done" ? "✓" : (i + 1);
      return `<div class="stepper-item ${cls}">
        <div class="stepper-dot">${dotContent}</div>
        <div class="stepper-label"><strong>${title}</strong><span>${desc}</span></div>
      </div>`;
    }).join("");
  }

  let stepperTimer = null;
  function startStepperAnimation() {
    let i = 0;
    renderStepper(0, false);
    // Advance every 300 ms — fast enough that all 7 steps finish in
    // ~2 s, well before any real API response arrives.
    stepperTimer = setInterval(() => {
      i = Math.min(i + 1, PIPELINE_STEPS.length - 1);
      renderStepper(i, false);
    }, 300);
  }
  function stopStepperAnimation() {
    clearInterval(stepperTimer);
    stepperTimer = null;
    renderStepper(PIPELINE_STEPS.length, true); // mark all steps done
  }

  // ---------------------------------------------------------------- analyze
  if (analyzeBtn) {
    analyzeBtn.addEventListener("click", async () => {
      if (!selectedFile) return;
      goto("processing");
      startStepperAnimation();

      const formData = new FormData();
      formData.append("file", selectedFile);
      formData.append("language", currentLang);

      let data;
      try {
        const res = await fetch("/api/analyze", { method: "POST", body: formData });
        data = await res.json();
      } catch (err) {
        stopStepperAnimation();
        setTimeout(() => {
          goto("upload");
          errorHolder.innerHTML = `<div class="error-box">Could not reach the server. Is the Flask app running? (${err.message})</div>`;
        }, 200);
        return;
      }

      // Always stop the stepper and navigate — never leave the user stuck.
      stopStepperAnimation();

      if (!data.success) {
        setTimeout(() => {
          goto("upload");
          errorHolder.innerHTML = `<div class="error-box">${data.error || "Something went wrong analyzing this report."}</div>`;
        }, 200);
        return;
      }

      lastResults = data;
      // Short pause so the user sees all steps marked "done", then switch.
      // renderResults is wrapped in try/catch — any JS error in rendering
      // still shows the results view so the user is never left on the
      // processing screen.
      setTimeout(() => {
        try {
          renderResults(data);
        } catch (renderErr) {
          console.error("[MediExplain] renderResults error:", renderErr);
        }
        goto("results");
      }, 350);
    });
  }

  // ================================================================
  //  SPEECH ENGINE — voice selection, Pause/Resume/Stop
  // ================================================================

  const LANG_MAP = { en: "en-IN", mr: "mr-IN", hi: "hi-IN" };

  // Cache of loaded voices — populated eagerly and on onvoiceschanged.
  // Voice loading is NEVER awaited; it's opportunistic. If voices aren't
  // loaded when speakTest() is called, _pickVoice falls back gracefully.
  let _voices = [];
  function _loadVoices() {
    const v = window.speechSynthesis.getVoices();
    if (v.length) _voices = v; // only update if browser returned voices
  }
  if ("speechSynthesis" in window) {
    _loadVoices(); // might return [] on first call in some browsers
    window.speechSynthesis.onvoiceschanged = _loadVoices;
    // Safety timeout: if onvoiceschanged never fires (some browsers),
    // retry once after 1 second. The results page is already open by then.
    setTimeout(_loadVoices, 1000);
  }

  /**
   * Choose the best available voice for a BCP-47 lang tag.
   * Priority: exact lang match → language prefix match → null (browser default).
   */
  function _pickVoice(bcp47) {
    if (!_voices.length) _loadVoices();
    const exact = _voices.find(v => v.lang === bcp47);
    if (exact) return exact;
    const prefix = bcp47.split("-")[0];
    return _voices.find(v => v.lang.startsWith(prefix)) || null;
  }

  // ---- Per-test speech state -------------------------------------------
  // We track one active test utterance at a time.
  let _activeSpeechBtn   = null;   // the btn wrapper element
  let _activeSpeechState = "idle"; // idle | playing | paused

  function _resetTestBtn(wrapper) {
    if (!wrapper) return;
    wrapper.innerHTML = `<button class="listen-btn listen-play">🔊 Listen</button>`;
    const pb = wrapper.querySelector(".listen-play");
    if (pb && pb._clickHandler) pb.addEventListener("click", pb._clickHandler);
  }

  function _stopActiveTest() {
    if ("speechSynthesis" in window) window.speechSynthesis.cancel();
    // Also stop HTML5 Audio if playing server-generated MP3
    if (_activeSpeechBtn && _activeSpeechBtn._audioEl) {
      try {
        _activeSpeechBtn._audioEl.pause();
        _activeSpeechBtn._audioEl.currentTime = 0;
      } catch(e) {}
      _activeSpeechBtn._audioEl = null;
    }
    if (_activeSpeechBtn) _resetTestBtn(_activeSpeechBtn);
    _activeSpeechBtn   = null;
    _activeSpeechState = "idle";
  }

  /**
   * Attach Pause/Resume/Stop controls to a button wrapper after speech starts.
   */
  function _setTestBtnPlaying(wrapper) {
    wrapper.innerHTML = `
      <button class="listen-btn listen-pause">⏸ Pause</button>
      <button class="listen-btn listen-stop">⏹ Stop</button>
    `;
    wrapper.querySelector(".listen-pause").addEventListener("click", () => {
      if (_activeSpeechState === "playing") {
        if (wrapper._audioEl) {
          wrapper._audioEl.pause();
        } else {
          window.speechSynthesis.pause();
        }
        _activeSpeechState = "paused";
        _setTestBtnPaused(wrapper);
      }
    });
    wrapper.querySelector(".listen-stop").addEventListener("click", _stopActiveTest);
  }

  function _setTestBtnPaused(wrapper) {
    wrapper.innerHTML = `
      <button class="listen-btn listen-resume">▶ Resume</button>
      <button class="listen-btn listen-stop">⏹ Stop</button>
    `;
    wrapper.querySelector(".listen-resume").addEventListener("click", () => {
      if (_activeSpeechState === "paused") {
        if (wrapper._audioEl) {
          wrapper._audioEl.play();
        } else {
          window.speechSynthesis.resume();
        }
        _activeSpeechState = "playing";
        _setTestBtnPlaying(wrapper);
      }
    });
    wrapper.querySelector(".listen-stop").addEventListener("click", _stopActiveTest);
  }

  /**
   * Speak text for an individual test.
   * Tries server audio file first (gTTS MP3), then browser speechSynthesis.
   * @param {string} text  - translated explanation text
   * @param {string} lang  - en / hi / mr
   * @param {Element} wrapper - the .listen-btn-wrapper element
   * @param {string|null} audioFile - server-generated audio filename, if any
   */
  function speakTest(text, lang, wrapper, audioFile) {
    // Stop any currently playing speech first
    _stopActiveTest();

    _activeSpeechBtn   = wrapper;
    _activeSpeechState = "playing";
    _setTestBtnPlaying(wrapper);

    // ── 1. Try server-generated audio file (gTTS MP3) ──────────────
    if (audioFile) {
      const audio = new Audio(`/outputs/${audioFile}`);
      // Store reference so stop/pause can control it
      wrapper._audioEl = audio;

      audio.onended = () => {
        if (_activeSpeechBtn === wrapper) {
          _activeSpeechState = "idle";
          _resetTestBtn(wrapper);
          _activeSpeechBtn = null;
        }
      };
      audio.onerror = () => {
        // Server file failed to play — fall back to browser TTS
        console.warn("[MediExplain] Server audio failed, falling back to browser TTS");
        wrapper._audioEl = null;
        _speakWithBrowser(text, lang, wrapper);
      };

      audio.play().catch(() => {
        wrapper._audioEl = null;
        _speakWithBrowser(text, lang, wrapper);
      });
      return;
    }

    // ── 2. Fall back to browser speechSynthesis ────────────────────
    _speakWithBrowser(text, lang, wrapper);
  }

  /**
   * Internal: speak using browser speechSynthesis API.
   */
  function _speakWithBrowser(text, lang, wrapper) {
    if (!("speechSynthesis" in window)) {
      alert("Voice playback isn't supported in this browser.");
      _activeSpeechState = "idle";
      _resetTestBtn(wrapper);
      _activeSpeechBtn = null;
      return;
    }

    const bcp47  = LANG_MAP[lang] || "en-IN";
    const utter  = new SpeechSynthesisUtterance(text);
    utter.lang   = bcp47;
    utter.rate   = 0.92;
    const voice  = _pickVoice(bcp47);
    if (voice) utter.voice = voice;

    utter.onend = utter.onerror = () => {
      if (_activeSpeechBtn === wrapper) {
        _activeSpeechState = "idle";
        _resetTestBtn(wrapper);
        _activeSpeechBtn = null;
      }
    };
    window.speechSynthesis.speak(utter);
  }

  // ---- Full-report speech state ----------------------------------------
  let _fullSpeechState = "idle"; // idle | playing | paused

  function _updateFullSpeechUI() {
    const playBtn  = document.getElementById("full-speech-play");
    const pauseBtn = document.getElementById("full-speech-pause");
    const stopBtn  = document.getElementById("full-speech-stop");
    const statusEl = document.getElementById("full-speech-status");
    if (!playBtn) return;

    if (_fullSpeechState === "idle") {
      playBtn.style.display  = "";
      pauseBtn.style.display = "none";
      stopBtn.style.display  = "none";
      playBtn.innerHTML = "🔊 Listen to Full Report";
      if (statusEl) statusEl.textContent = "Click to play entire audio summary";
    } else if (_fullSpeechState === "playing") {
      playBtn.style.display  = "none";
      pauseBtn.style.display = "";
      stopBtn.style.display  = "";
      pauseBtn.innerHTML = "⏸ Pause";
      if (statusEl) statusEl.textContent = "Playing full report…";
    } else if (_fullSpeechState === "paused") {
      playBtn.style.display  = "none";
      pauseBtn.style.display = "";
      stopBtn.style.display  = "";
      pauseBtn.innerHTML = "▶ Resume";
      if (statusEl) statusEl.textContent = "Paused — click Resume to continue";
    }
  }

  function stopFullSpeech() {
    if ("speechSynthesis" in window) window.speechSynthesis.cancel();
    _fullSpeechState = "idle";
    _updateFullSpeechUI();
  }

  function _bindFullSpeechButtons(data) {
    const playBtn  = document.getElementById("full-speech-play");
    const pauseBtn = document.getElementById("full-speech-pause");
    const stopBtn  = document.getElementById("full-speech-stop");
    if (!playBtn) return;

    playBtn.addEventListener("click", () => {
      if (!("speechSynthesis" in window)) {
        alert("Voice playback isn't supported in this browser.");
        return;
      }
      // Stop any per-test speech
      _stopActiveTest();
      window.speechSynthesis.cancel();

      const bcp47 = LANG_MAP[data.language] || "en-IN";
      const fullScript = [
        `MediExplain AI. Total tests: ${data.tests.length}.`,
        ...data.tests.map(t =>
          `${t.display_test_name || t.test_name}. ${t.explanation}. ${t.display_status || t.status}.`
        )
      ].join(" ... ");

      const utter  = new SpeechSynthesisUtterance(fullScript);
      utter.lang   = bcp47;
      utter.rate   = 0.90;
      const voice  = _pickVoice(bcp47);
      if (voice) utter.voice = voice;

      _fullSpeechState = "playing";
      _updateFullSpeechUI();

      utter.onend = utter.onerror = () => {
        _fullSpeechState = "idle";
        _updateFullSpeechUI();
      };
      window.speechSynthesis.speak(utter);
    });

    pauseBtn.addEventListener("click", () => {
      if (_fullSpeechState === "playing") {
        window.speechSynthesis.pause();
        _fullSpeechState = "paused";
        _updateFullSpeechUI();
      } else if (_fullSpeechState === "paused") {
        window.speechSynthesis.resume();
        _fullSpeechState = "playing";
        _updateFullSpeechUI();
      }
    });

    stopBtn.addEventListener("click", stopFullSpeech);
  }

  // ------------------------------------------------ Feature 1: Visual Result Charts
  function statusClass(status) {
    return { "Low": "low", "Normal": "normal", "High": "high" }[status] || "uncertain";
  }

  function renderVisualChart(test) {
    const val = parseFloat(test.value);
    const low = parseFloat(test.reference_low);
    const high = parseFloat(test.reference_high);
    const st = statusClass(test.status);

    let posPercent = 50;
    const hasNumericBounds = !isNaN(val) && !isNaN(low) && !isNaN(high) && low < high;

    if (hasNumericBounds) {
      if (val < low) {
        posPercent = Math.max(5, Math.min(30, (val / low) * 30));
      } else if (val >= low && val <= high) {
        posPercent = 33 + Math.min(34, ((val - low) / (high - low)) * 34);
      } else {
        const overflow = (val - high) / (high || 1);
        posPercent = 67 + Math.min(28, Math.max(5, overflow * 25));
      }
    } else {
      if (st === "low") posPercent = 16.5;
      else if (st === "normal") posPercent = 50;
      else if (st === "high") posPercent = 83.5;
      else posPercent = 50;
    }

    const lowLabel = test.reference_low ? `< ${test.reference_low}` : "Low";
    const rangeLabel = test.reference_low && test.reference_high ? `${test.reference_low} – ${test.reference_high} ${test.unit || ''}` : "Normal Range";
    const highLabel = test.reference_high ? `> ${test.reference_high}` : "High";

    return `
      <div class="visual-chart-cell">
        <div class="chart-container">
          <div class="chart-track">
            <div class="chart-zone low ${st === 'low' ? 'active-zone' : ''}"></div>
            <div class="chart-zone normal ${st === 'normal' ? 'active-zone' : ''}"></div>
            <div class="chart-zone high ${st === 'high' ? 'active-zone' : ''}"></div>
            <div class="chart-marker-wrap" style="left: ${posPercent.toFixed(1)}%;">
              <div class="chart-pin ${st}" title="Value: ${test.value} (${test.status})"></div>
            </div>
          </div>
          <div class="chart-labels">
            <span>${lowLabel}</span>
            <span>${rangeLabel}</span>
            <span>${highLabel}</span>
          </div>
        </div>
      </div>
    `;
  }

  // ------------------------------------------------ Results View & Filtering
  function renderResults(data) {
    const holder = document.getElementById("results-holder");
    const now = new Date().toLocaleString();
    const langName = CONFIG.languages[data.language] || data.language;

    let activeFilter = "all";
    let searchQuery = "";

    function filterAndRenderRows() {
      const tbody = document.getElementById("results-tbody");
      if (!tbody) return;

      const filtered = data.tests.filter(t => {
        const q = searchQuery.toLowerCase();
        const matchesSearch = !q ||
          (t.display_test_name || t.test_name).toLowerCase().includes(q) ||
          t.test_name.toLowerCase().includes(q) ||
          (t.display_status || t.status).toLowerCase().includes(q) ||
          t.status.toLowerCase().includes(q) ||
          t.value.toString().toLowerCase().includes(q) ||
          t.explanation.toLowerCase().includes(q);
        const matchesFilter = activeFilter === "all" || statusClass(t.status) === activeFilter;
        return matchesSearch && matchesFilter;
      });

      if (filtered.length === 0) {
        tbody.innerHTML = `<tr><td colspan="6" style="text-align:center; padding: 24px; color:var(--stone);">No matching tests found for "${searchQuery}".</td></tr>`;
        return;
      }

      tbody.innerHTML = filtered.map((t, idx) => `
        <tr class="test-row-item" data-name="${t.test_name}">
          <td><strong>${t.display_test_name || t.test_name}</strong></td>
          <td><strong>${t.value}</strong></td>
          <td>${t.unit || "—"}</td>
          <td>${renderVisualChart(t)}</td>
          <td><span class="status-chip ${statusClass(t.status)}"><span class="dot"></span> ${t.display_status || t.status}</span></td>
          <td style="vertical-align: middle; text-align: right;">
            <div class="listen-btn-wrapper" data-idx="${data.tests.indexOf(t)}">
              <button class="listen-btn listen-play">🔊 Listen</button>
            </div>
          </td>
        </tr>
        <tr class="explanation-row">
          <td colspan="6">
            <div class="explanation-box">
              <p>${t.explanation}</p>
            </div>
          </td>
        </tr>
      `).join("");

      // Attach speakTest to each listen button wrapper
      tbody.querySelectorAll(".listen-btn-wrapper").forEach(wrapper => {
        const idx  = Number(wrapper.dataset.idx);
        const t    = data.tests[idx];
        const btn  = wrapper.querySelector(".listen-play");
        if (btn) {
          btn._clickHandler = () => speakTest(t.explanation, data.language, wrapper, t.audio_file || null);
          btn.addEventListener("click", btn._clickHandler);
        }
      });
    }

    holder.innerHTML = `
      <div class="summary-bar">
        <div>
          <strong>Report analyzed</strong>
          <div class="meta">${now} · Explained in ${langName}${data.demo_mode ? " · Demo mode" : ""}</div>
        </div>
        <div class="disclaimer">${data.safety_notice}</div>
      </div>

      ${data.ocr_warnings && data.ocr_warnings.length ? `<div class="error-box">${data.ocr_warnings.join(" ")}</div>` : ""}

      <!-- Full Report Speech Controls -->
      <div class="full-speech-bar">
        <button class="btn-speech" id="full-speech-play">🔊 Listen to Full Report</button>
        <button class="btn-speech btn-speech-pause" id="full-speech-pause" style="display:none">⏸ Pause</button>
        <button class="btn-speech btn-speech-stop"  id="full-speech-stop"  style="display:none">⏹ Stop</button>
        <span class="speech-status" id="full-speech-status">Click to play entire audio summary</span>
      </div>

      <!-- Feature 2: Search Tests & Filter Toolbar -->
      <div class="results-toolbar">
        <div class="search-box">
          <span class="search-icon">🔍</span>
          <input type="text" id="test-search-input" placeholder="Search for a test (e.g., Hemoglobin, Glucose, WBC)...">
        </div>
        <div class="filter-pills" id="filter-pills-container">
          <button class="filter-pill active" data-filter="all">All (${data.tests.length})</button>
          <button class="filter-pill" data-filter="low">Low (${data.tests.filter(t => statusClass(t.status)==='low').length})</button>
          <button class="filter-pill" data-filter="normal">Normal (${data.tests.filter(t => statusClass(t.status)==='normal').length})</button>
          <button class="filter-pill" data-filter="high">High (${data.tests.filter(t => statusClass(t.status)==='high').length})</button>
        </div>
      </div>

      <!-- Feature 1: Visual Result Table -->
      <table class="results-table">
        <thead>
          <tr>
            <th>Test Name</th>
            <th>Result</th>
            <th>Unit</th>
            <th>Visual Range Gauge</th>
            <th>Status</th>
            <th style="text-align: right;">Voice</th>
          </tr>
        </thead>
        <tbody id="results-tbody"></tbody>
      </table>

      <!-- Action Buttons -->
      <div class="results-actions">
        <button class="btn btn-primary" id="save-report-btn">💾 Save Report to History</button>
        <button class="btn btn-ghost" id="download-pdf-btn">📑 Download PDF Summary</button>
        <button class="btn btn-ghost" id="compare-report-btn">📈 Compare Report</button>
        <button class="btn btn-ghost" id="analyze-another">Upload another</button>
      </div>
      <div id="save-status-holder" style="margin-top: 10px;"></div>
    `;

    filterAndRenderRows();
    _bindFullSpeechButtons(data);

    // Event listeners for Toolbar
    const searchInput = document.getElementById("test-search-input");
    if (searchInput) {
      searchInput.addEventListener("input", (e) => {
        searchQuery = e.target.value.trim();
        filterAndRenderRows();
      });
    }

    document.querySelectorAll("#filter-pills-container .filter-pill").forEach(pill => {
      pill.addEventListener("click", () => {
        document.querySelectorAll("#filter-pills-container .filter-pill").forEach(p => p.classList.remove("active"));
        pill.classList.add("active");
        activeFilter = pill.dataset.filter;
        filterAndRenderRows();
      });
    });

    // Full report speech buttons are wired by _bindFullSpeechButtons(data) above.
    // (The old "full-speech-btn" id no longer exists — buttons are now
    //  full-speech-play / full-speech-pause / full-speech-stop)

    // Save to History
    document.getElementById("save-report-btn").addEventListener("click", async () => {
      const btn = document.getElementById("save-report-btn");
      btn.disabled = true;
      btn.textContent = "Saving…";
      try {
        const res = await fetch("/api/reports", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ language: data.language, summary: data })
        });
        const resp = await res.json();
        if (resp.success) {
          btn.textContent = "✓ Saved to History";
          btn.style.background = "var(--teal)";
          btn.style.color = "#fff";
        } else {
          btn.disabled = false;
          btn.textContent = "Save Report to History";
          alert("Could not save report.");
        }
      } catch (err) {
        btn.disabled = false;
        btn.textContent = "Save Report to History";
        alert("Error saving report: " + err.message);
      }
    });

    // Feature 3: Download PDF
    document.getElementById("download-pdf-btn").addEventListener("click", () => downloadPDFSummary(data));

    // Feature 4: Compare Report
    document.getElementById("compare-report-btn").addEventListener("click", async () => {
      try {
        const res = await fetch("/api/reports");
        const resp = await res.json();
        if (resp.success && resp.reports.length > 0) {
          showComparisonSelectionModal(data, resp.reports);
        } else {
          alert("No previous saved reports found in history to compare with. Please save at least one past report first!");
        }
      } catch (e) {
        alert("Could not fetch user history for comparison.");
      }
    });

    document.getElementById("analyze-another").addEventListener("click", () => {
      stopFullSpeech();
      setFile(null); if (fileInput) fileInput.value = "";
      goto("upload");
    });
  }

  // ------------------------------------------------ Feature 3: Download PDF Summary
  function downloadPDFSummary(data) {
    const langName = CONFIG.languages[data.language] || data.language;
    const now = new Date().toLocaleString();

    // Create a styled temporary HTML container for PDF rendering
    const container = document.createElement("div");
    container.style.position = "absolute";
    container.style.left = "-9999px";
    container.style.top = "0";
    container.style.width = "780px";
    container.style.padding = "30px";
    container.style.background = "#ffffff";
    container.style.color = "#16233F";
    container.style.fontFamily = "'Noto Sans Devanagari', 'Inter', -apple-system, sans-serif";

    container.innerHTML = `
      <div style="border-bottom: 2px solid #E2992F; padding-bottom: 12px; margin-bottom: 16px;">
        <h1 style="font-family: 'Fraunces', Georgia, serif; font-size: 22px; color: #16233F; margin: 0 0 6px 0;">MediExplain AI — Lab Report Summary</h1>
        <div style="font-size: 13px; color: #6E6858;">
          Generated: ${now} | Language: ${langName}
        </div>
        <div style="margin-top: 10px; padding: 10px 12px; background: #FBEAE6; border-left: 3px solid #BC4A3C; color: #BC4A3C; font-size: 12px; border-radius: 4px; line-height: 1.4;">
          <strong>Safety Notice:</strong> ${data.safety_notice}
        </div>
      </div>

      <table style="width: 100%; border-collapse: collapse; font-size: 13px; margin-top: 14px;">
        <thead>
          <tr style="background: #E2992F; color: #ffffff;">
            <th style="padding: 10px; text-align: left; width: 20%; font-weight: bold;">Test Name</th>
            <th style="padding: 10px; text-align: left; width: 14%; font-weight: bold;">Result</th>
            <th style="padding: 10px; text-align: left; width: 16%; font-weight: bold;">Ref Range</th>
            <th style="padding: 10px; text-align: left; width: 12%; font-weight: bold;">Status</th>
            <th style="padding: 10px; text-align: left; font-weight: bold;">Plain Language Explanation</th>
          </tr>
        </thead>
        <tbody>
          ${data.tests.map(t => {
            let stBg = '#E3F2EA', stCol = '#2B7A5B';
            if (t.status === 'Low') { stBg = '#E8EFF9'; stCol = '#2F5FA0'; }
            else if (t.status === 'High') { stBg = '#FBEAE6'; stCol = '#BC4A3C'; }
            else if (t.status === 'Unable to determine') { stBg = '#FBEEDA'; stCol = '#B87415'; }

            return `
              <tr style="border-bottom: 1px solid #E4DECF;">
                <td style="padding: 10px; font-weight: bold; vertical-align: top; color: #16233F;">${t.test_name}</td>
                <td style="padding: 10px; vertical-align: top;">${t.value} ${t.unit || ''}</td>
                <td style="padding: 10px; vertical-align: top; color: #6E6858;">${t.reference_text}</td>
                <td style="padding: 10px; vertical-align: top;">
                  <span style="display:inline-block; padding: 3px 8px; border-radius: 12px; background: ${stBg}; color: ${stCol}; font-weight: bold; font-size: 11px;">
                    ${t.status}
                  </span>
                </td>
                <td style="padding: 10px; vertical-align: top; line-height: 1.45; color: #3E4A63;">${t.explanation}</td>
              </tr>
            `;
          }).join('')}
        </tbody>
      </table>

      <div style="margin-top: 24px; padding-top: 12px; border-top: 1px solid #E4DECF; font-size: 11px; color: #6E6858; text-align: center;">
        MediExplain AI — Multilingual Medical Report Simplifier. Educational reference only.
      </div>
    `;

    document.body.appendChild(container);

    if (window.html2pdf) {
      const opt = {
        margin:       8,
        filename:     `MediExplain-Summary-${data.language}-${new Date().toISOString().slice(0,10)}.pdf`,
        image:        { type: 'jpeg', quality: 0.98 },
        html2canvas:  { scale: 2, useCORS: true, logging: false },
        jsPDF:        { unit: 'mm', format: 'a4', orientation: 'portrait' }
      };

      window.html2pdf().set(opt).from(container).save().then(() => {
        if (container.parentNode) container.parentNode.removeChild(container);
      }).catch(err => {
        console.error("html2pdf failed, printing:", err);
        if (container.parentNode) container.parentNode.removeChild(container);
        window.print();
      });
    } else {
      if (container.parentNode) container.parentNode.removeChild(container);
      window.print();
    }
  }

  // ------------------------------------------------ Feature 5: User History
  async function loadHistory() {
    const holder = document.getElementById("history-holder");
    if (!holder) return;

    holder.innerHTML = `<div style="text-align:center; padding: 40px;"><span class="spin"></span> Loading saved reports…</div>`;

    try {
      const res = await fetch("/api/reports");
      const data = await res.json();

      if (!data.success || !data.reports || data.reports.length === 0) {
        holder.innerHTML = `
          <div class="panel" style="text-align:center; padding: 48px 24px;">
            <div style="font-size: 2.4rem; margin-bottom: 12px;">📁</div>
            <h3>No saved reports yet</h3>
            <p style="color:var(--ink-soft); max-width:40ch; margin:8px auto 20px;">
              When you analyze a lab report, click "Save Report to History" to store it securely for future reference and trend comparison.
            </p>
            <button class="btn btn-primary" data-goto="upload">Analyze your first report</button>
          </div>
        `;
        holder.querySelectorAll("[data-goto]").forEach(el => el.addEventListener("click", () => goto(el.dataset.goto)));
        return;
      }

      const cardsHtml = data.reports.map(rep => {
        const dateStr = new Date(rep.created_at).toLocaleString();
        const tests = rep.summary && rep.summary.tests ? rep.summary.tests : [];
        const lowCnt = tests.filter(t => statusClass(t.status) === 'low').length;
        const normCnt = tests.filter(t => statusClass(t.status) === 'normal').length;
        const highCnt = tests.filter(t => statusClass(t.status) === 'high').length;
        const langName = CONFIG.languages[rep.language] || rep.language;

        return `
          <div class="history-card" data-id="${rep.id}">
            <div>
              <div class="date">${dateStr}</div>
              <div class="meta-row">
                <span class="status-chip normal">${tests.length} Tests</span>
                <span class="status-chip low">${lowCnt} Low</span>
                <span class="status-chip normal">${normCnt} Normal</span>
                <span class="status-chip high">${highCnt} High</span>
              </div>
              <div style="margin-top: 10px; font-size: 0.85rem; color: var(--stone);">
                Language: ${langName}
              </div>
            </div>
            <div class="actions">
              <button class="btn btn-primary view-report-btn" data-id="${rep.id}">👁️ View</button>
              <button class="btn btn-ghost compare-hist-btn" data-id="${rep.id}">📈 Compare</button>
              <button class="btn btn-ghost delete-hist-btn" data-id="${rep.id}" style="color:var(--coral);">🗑️ Delete</button>
            </div>
          </div>
        `;
      }).join("");

      holder.innerHTML = `<div class="history-grid">${cardsHtml}</div>`;

      // Event handlers
      holder.querySelectorAll(".view-report-btn").forEach(btn => {
        btn.addEventListener("click", async () => {
          const repId = btn.dataset.id;
          const rRes = await fetch(`/api/reports/${repId}`);
          const rData = await rRes.json();
          if (rData.success && rData.report && rData.report.summary) {
            lastResults = rData.report.summary;
            renderResults(rData.report.summary);
            goto("results");
          }
        });
      });

      holder.querySelectorAll(".compare-hist-btn").forEach(btn => {
        btn.addEventListener("click", async () => {
          const repId = btn.dataset.id;
          const selectedRep = data.reports.find(r => r.id == repId);
          if (selectedRep && selectedRep.summary) {
            if (lastResults) {
              renderComparison(lastResults, selectedRep.summary);
              goto("comparison");
            } else {
              // compare against another history item
              const otherRep = data.reports.find(r => r.id != repId);
              if (otherRep && otherRep.summary) {
                renderComparison(selectedRep.summary, otherRep.summary);
                goto("comparison");
              } else {
                alert("Please analyze or select another report to compare with.");
              }
            }
          }
        });
      });

      holder.querySelectorAll(".delete-hist-btn").forEach(btn => {
        btn.addEventListener("click", async () => {
          if (!confirm("Are you sure you want to delete this saved report?")) return;
          const repId = btn.dataset.id;
          await fetch(`/api/reports/${repId}`, { method: "DELETE" });
          loadHistory();
        });
      });

    } catch (err) {
      holder.innerHTML = `<div class="error-box">Could not load history: ${err.message}</div>`;
    }
  }

  // ------------------------------------------------ Feature 4: Report Comparison
  function showComparisonSelectionModal(currentData, reports) {
    const modalHtml = `
      <div style="position:fixed; top:0; left:0; right:0; bottom:0; background:rgba(0,0,0,0.5); z-index:100; display:flex; align-items:center; justify-content:center;">
        <div class="panel" style="max-width:500px; width:90%;">
          <h3>📈 Compare with an Older Report</h3>
          <p style="color:var(--ink-soft); font-size:0.9rem; margin-bottom:16px;">Select a saved past report from your history to compare side-by-side:</p>
          <div style="max-height:260px; overflow-y:auto; border:1px solid var(--line); border-radius:6px; margin-bottom:20px;">
            ${reports.map(r => `
              <div class="select-rep-item" data-id="${r.id}" style="padding:12px; border-bottom:1px solid var(--line); cursor:pointer; font-size:0.9rem;">
                <strong>${new Date(r.created_at).toLocaleString()}</strong>
                <div style="color:var(--stone); font-size:0.8rem;">Language: ${r.language} · ${r.summary && r.summary.tests ? r.summary.tests.length : 0} tests</div>
              </div>
            `).join("")}
          </div>
          <div style="display:flex; justify-content:flex-end; gap:10px;">
            <button class="btn btn-ghost" id="close-modal-btn">Cancel</button>
          </div>
        </div>
      </div>
    `;

    const div = document.createElement("div");
    div.innerHTML = modalHtml;
    document.body.appendChild(div);

    div.querySelectorAll(".select-rep-item").forEach(item => {
      item.addEventListener("click", async () => {
        const repId = item.dataset.id;
        const rRes = await fetch(`/api/reports/${repId}`);
        const rData = await rRes.json();
        document.body.removeChild(div);
        if (rData.success && rData.report && rData.report.summary) {
          renderComparison(currentData, rData.report.summary);
          goto("comparison");
        }
      });
    });

    document.getElementById("close-modal-btn").addEventListener("click", () => {
      document.body.removeChild(div);
    });
  }

  function renderComparison(curr, old) {
    const holder = document.getElementById("comparison-holder");
    if (!holder) return;

    const currDate = new Date().toLocaleDateString();
    const oldDate = old.created_at ? new Date(old.created_at).toLocaleDateString() : "Previous Report";

    const allNames = Array.from(new Set([
      ...curr.tests.map(t => t.test_name),
      ...old.tests.map(t => t.test_name)
    ]));

    const rowsHtml = allNames.map(name => {
      const cTest = curr.tests.find(t => t.test_name === name);
      const oTest = old.tests.find(t => t.test_name === name);

      const cVal = cTest ? `${cTest.value} ${cTest.unit || ''}` : "—";
      const oVal = oTest ? `${oTest.value} ${oTest.unit || ''}` : "—";

      const cSt = cTest ? cTest.status : "—";
      const oSt = oTest ? oTest.status : "—";

      let trendBadge = `<span class="trend-chip stable">No Change</span>`;
      let diffStr = "";

      if (cTest && oTest) {
        const cNum = parseFloat(cTest.value);
        const oNum = parseFloat(oTest.value);

        if (!isNaN(cNum) && !isNaN(oNum)) {
          const diff = (cNum - oNum).toFixed(1);
          const sign = diff > 0 ? "+" : "";
          diffStr = `${sign}${diff} ${cTest.unit || ''}`;

          if (oSt === "Low" && cSt === "Normal") {
            trendBadge = `<span class="trend-chip improved">Improved 🟢</span>`;
          } else if (oSt === "High" && cSt === "Normal") {
            trendBadge = `<span class="trend-chip improved">Improved 🟢</span>`;
          } else if (cSt === "Low" || cSt === "High") {
            trendBadge = `<span class="trend-chip degraded">Attention 🔴</span>`;
          } else {
            trendBadge = `<span class="trend-chip stable">${diffStr}</span>`;
          }
        }
      } else if (cTest && !oTest) {
        trendBadge = `<span class="trend-chip stable">New Test 🆕</span>`;
      }

      return `
        <tr>
          <td><strong>${name}</strong></td>
          <td>${oVal} ${oSt !== '—' ? `<span class="status-chip ${statusClass(oSt)}" style="font-size:0.75rem;">${oSt}</span>` : ''}</td>
          <td>${cVal} ${cSt !== '—' ? `<span class="status-chip ${statusClass(cSt)}" style="font-size:0.75rem;">${cSt}</span>` : ''}</td>
          <td>${trendBadge}</td>
        </tr>
      `;
    }).join("");

    holder.innerHTML = `
      <div class="comparison-container">
        <div class="comparison-header">
          <div>
            <h2 style="font-family:var(--font-display); font-size:1.5rem;">📈 Report Comparison</h2>
            <p style="color:var(--ink-soft); font-size:0.9rem;">Comparing Current Analysis (${currDate}) vs. Previous Report (${oldDate})</p>
          </div>
          <div>
            <button class="btn btn-ghost" id="back-to-results-btn">← Back to Results</button>
          </div>
        </div>

        <table class="results-table">
          <thead>
            <tr>
              <th>Test Name</th>
              <th>Older Report (${oldDate})</th>
              <th>Current Report (${currDate})</th>
              <th>Change / Trend</th>
            </tr>
          </thead>
          <tbody>
            ${rowsHtml}
          </tbody>
        </table>
      </div>
    `;

    document.getElementById("back-to-results-btn").addEventListener("click", () => goto("results"));
  }

})();
