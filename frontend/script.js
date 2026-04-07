/**
 * JobShield — frontend
 * API base: same origin when served from Flask; fallback for file://
 */
function getApiBase() {
  if (typeof window === "undefined") return "";
  const { protocol, origin } = window.location;
  if (protocol === "file:" || !origin) return "http://127.0.0.1:5000";
  return "";
}

const API_BASE = getApiBase();

const RING_C = 2 * Math.PI * 52;

const analyzeBtn = document.getElementById("analyzeBtn");
const jobText = document.getElementById("jobText");
const scanUrlBtn = document.getElementById("scanUrlBtn");
const jobUrl = document.getElementById("jobUrl");
const quizForm = document.getElementById("quizForm");

const resultCard = document.getElementById("resultCard");
const resultBadge = document.getElementById("resultBadge");
const resultMode = document.getElementById("resultMode");
const resultLabel = document.getElementById("resultLabel");
const confidence = document.getElementById("confidence");
const confidenceRow = document.getElementById("confidenceRow");
const extraBlock = document.getElementById("extraBlock");
const riskRingFill = document.getElementById("riskRingFill");
const riskRingValue = document.getElementById("riskRingValue");
const riskBar = document.getElementById("riskBar");
const riskBarFill = document.getElementById("riskBarFill");
const riskBarCaption = document.getElementById("riskBarCaption");
const apiStatus = document.getElementById("apiStatus");

const errorMsgPaste = document.getElementById("errorMsgPaste");
const errorMsgLink = document.getElementById("errorMsgLink");
const errorMsgQuiz = document.getElementById("errorMsgQuiz");

function formatConfidence(value) {
  if (value === null || value === undefined) {
    return "—";
  }
  return `${(value * 100).toFixed(1)}%`;
}

function clearErrors() {
  errorMsgPaste.textContent = "";
  errorMsgLink.textContent = "";
  errorMsgQuiz.textContent = "";
}

function setButtonLoading(btn, loading) {
  if (!btn) return;
  btn.disabled = loading;
  btn.classList.toggle("btn-loading", loading);
  const label = btn.querySelector(".btn-label");
  const spin = btn.querySelector(".btn-spinner");
  if (spin) spin.hidden = !loading;
}

function parseNumericScore(text) {
  const m = String(text).match(/(\d+)/);
  if (!m) return null;
  const n = parseInt(m[1], 10);
  return Number.isFinite(n) ? Math.min(100, Math.max(0, n)) : null;
}

function riskCaption(score) {
  if (score === null || score === undefined) return "—";
  if (score < 30) return "Lower concern";
  if (score < 55) return "Review carefully";
  return "High concern";
}

function setRiskVisual(score) {
  const pct = score === null || score === undefined ? 0 : score;
  const offset = RING_C * (1 - pct / 100);
  riskRingFill.style.strokeDasharray = String(RING_C);
  riskRingFill.style.strokeDashoffset = String(offset);
  riskRingValue.textContent = score === null || score === undefined ? "—" : String(score);
  riskBarFill.style.width = `${pct}%`;
  riskBar.setAttribute("aria-valuenow", String(pct));
  riskBarCaption.textContent = riskCaption(score === null ? null : score);

  if (pct < 30) {
    riskRingFill.style.stroke = "var(--success)";
  } else if (pct < 55) {
    riskRingFill.style.stroke = "var(--warning)";
  } else {
    riskRingFill.style.stroke = "var(--danger)";
  }
}

function setBadgeForResult(labelText, numericScore, mode) {
  resultBadge.className = "result-badge";
  const upper = String(labelText).toUpperCase();

  if (upper.includes("UNKNOWN")) {
    resultBadge.classList.add("level-unknown");
    resultBadge.textContent = "Unknown";
    return;
  }

  if (mode === "quiz") {
    if (upper.includes("LOWER")) {
      resultBadge.classList.add("level-low");
      resultBadge.textContent = "Lower risk";
    } else if (upper.includes("SUSPICIOUS")) {
      resultBadge.classList.add("level-mid");
      resultBadge.textContent = "Suspicious";
    } else {
      resultBadge.classList.add("level-high");
      resultBadge.textContent = "High risk";
    }
    return;
  }

  if (upper === "FAKE" || upper.includes("FAKE")) {
    resultBadge.classList.add("level-high");
    resultBadge.textContent = "Likely risky";
  } else if (upper === "GENUINE" || upper.includes("GENUINE")) {
    resultBadge.classList.add("level-low");
    resultBadge.textContent = "Likely safer";
  } else if (numericScore !== null) {
    if (numericScore >= 55) {
      resultBadge.classList.add("level-high");
      resultBadge.textContent = "Elevated risk";
    } else if (numericScore >= 30) {
      resultBadge.classList.add("level-mid");
      resultBadge.textContent = "Review";
    } else {
      resultBadge.classList.add("level-low");
      resultBadge.textContent = "Lower risk";
    }
  } else {
    resultBadge.textContent = "Result";
  }
}

function scrollToResult() {
  resultCard.scrollIntoView({ behavior: "smooth", block: "nearest" });
}

function showResult(payload) {
  resultMode.textContent = payload.modeLabel || "";
  resultLabel.textContent = payload.label;

  const numeric = parseNumericScore(payload.riskScoreText);
  setRiskVisual(numeric);
  setBadgeForResult(payload.label, numeric, payload.modeKey);

  if (payload.showConfidence) {
    confidenceRow.style.display = "";
    confidence.textContent = formatConfidence(payload.confidence);
  } else {
    confidenceRow.style.display = "none";
    confidence.textContent = "—";
  }

  if (payload.extraHtml) {
    extraBlock.hidden = false;
    extraBlock.innerHTML = payload.extraHtml;
  } else {
    extraBlock.hidden = true;
    extraBlock.innerHTML = "";
  }

  resultCard.hidden = false;
  scrollToResult();
}

async function analyzePost() {
  const text = jobText.value.trim();
  clearErrors();
  resultCard.hidden = true;
  setButtonLoading(analyzeBtn, true);

  if (!text) {
    errorMsgPaste.textContent = "Please paste internship or job post text first.";
    setButtonLoading(analyzeBtn, false);
    return;
  }

  try {
    const response = await fetch(`${API_BASE}/predict`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text }),
    });

    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.error || "Request failed.");
    }

    showResult({
      modeLabel: "Paste text · ML classifier",
      modeKey: "ml",
      label: data.result,
      riskScoreText: `${data.risk_score}/100`,
      confidence: data.confidence,
      showConfidence: true,
      extraHtml: "",
    });
  } catch (error) {
    errorMsgPaste.textContent = error.message || "Could not analyze job post.";
  } finally {
    setButtonLoading(analyzeBtn, false);
  }
}

async function scanUrl() {
  const url = jobUrl.value.trim();
  clearErrors();
  resultCard.hidden = true;
  setButtonLoading(scanUrlBtn, true);

  if (!url) {
    errorMsgLink.textContent = "Paste a job URL first.";
    setButtonLoading(scanUrlBtn, false);
    return;
  }

  try {
    const response = await fetch(`${API_BASE}/scan-url`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url }),
    });

    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.error || "Request failed.");
    }

    const domainSignals = (data.domain && data.domain.signals) || [];
    const signalsHtml =
      domainSignals.length > 0
        ? `<p><strong>Domain signals</strong></p><ul>${domainSignals.map((s) => `<li>${escapeHtml(s)}</li>`).join("")}</ul>`
        : "";

    let label = data.result;
    if (data.result === "UNKNOWN") {
      label = "UNKNOWN (page not readable)";
    }

    const preview =
      data.text_preview && data.text_preview.length > 0
        ? `<p><strong>Text preview</strong><span class="preview">${escapeHtml(data.text_preview)}</span></p>`
        : "";

    const note = data.note ? `<p class="note">${escapeHtml(data.note)}</p>` : "";
    const fetchErr = data.fetch_error
      ? `<p class="warn"><strong>Fetch</strong> ${escapeHtml(data.fetch_error)}</p>`
      : "";

    showResult({
      modeLabel: "Smart link scan · ML + domain",
      modeKey: "url",
      label,
      riskScoreText: `${data.risk_score ?? "—"}/100`,
      confidence: data.confidence,
      showConfidence: data.confidence != null,
      extraHtml: `${fetchErr}${signalsHtml}${preview}${note}`,
    });
  } catch (error) {
    errorMsgLink.textContent = error.message || "Could not scan URL.";
  } finally {
    setButtonLoading(scanUrlBtn, false);
  }
}

function escapeHtml(s) {
  const div = document.createElement("div");
  div.textContent = s;
  return div.innerHTML;
}

function collectQuizAnswers() {
  const ids = [
    "upfront_fee",
    "telegram_whatsapp_only",
    "unrealistic_pay",
    "bank_details_early",
    "no_company_identity",
    "urgent_pressure",
  ];
  const answers = {};
  for (const id of ids) {
    const el = quizForm.querySelector(`input[name="${id}"]:checked`);
    if (!el) {
      return null;
    }
    answers[id] = el.value === "yes";
  }
  return answers;
}

async function submitQuiz(e) {
  e.preventDefault();
  clearErrors();
  resultCard.hidden = true;
  setButtonLoading(document.getElementById("quizSubmitBtn"), true);

  const answers = collectQuizAnswers();
  if (!answers) {
    errorMsgQuiz.textContent = "Please answer every question.";
    setButtonLoading(document.getElementById("quizSubmitBtn"), false);
    return;
  }

  try {
    const response = await fetch(`${API_BASE}/quiz`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ answers }),
    });

    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.error || "Request failed.");
    }

    const flags = (data.triggered_flags || []).join(", ") || "none";
    showResult({
      modeLabel: "60-second quiz · pattern score",
      modeKey: "quiz",
      label: data.label,
      riskScoreText: `${data.risk_score}/100`,
      showConfidence: false,
      extraHtml: `<p><strong>Flags triggered</strong> ${escapeHtml(flags)}</p><p class="note">Based on common scam patterns, not ML on post text.</p>`,
    });
  } catch (error) {
    errorMsgQuiz.textContent = error.message || "Could not submit quiz.";
  } finally {
    setButtonLoading(document.getElementById("quizSubmitBtn"), false);
  }
}

function initTabs() {
  const tabs = document.querySelectorAll(".tab");
  const panels = document.querySelectorAll(".tab-panel");

  tabs.forEach((tab) => {
    tab.addEventListener("click", () => {
      const name = tab.dataset.tab;
      tabs.forEach((t) => {
        const on = t === tab;
        t.classList.toggle("active", on);
        t.setAttribute("aria-selected", on ? "true" : "false");
      });
      panels.forEach((p) => {
        const show = p.dataset.panel === name;
        p.classList.toggle("hidden", !show);
        p.toggleAttribute("hidden", !show);
      });
    });
  });
}

async function checkHealth() {
  if (!apiStatus) return;
  try {
    const res = await fetch(`${API_BASE}/api/health`);
    const data = await res.json();
    if (data.status === "ready") {
      apiStatus.textContent = "API ready";
      apiStatus.className = "pill pill-ok";
    } else {
      apiStatus.textContent = "Model missing";
      apiStatus.className = "pill pill-warn";
      apiStatus.title = "Run py model.py then restart backend";
    }
  } catch {
    apiStatus.textContent = "Offline";
    apiStatus.className = "pill pill-warn";
    apiStatus.title = "Start backend: py backend/app.py";
  }
}

analyzeBtn.addEventListener("click", analyzePost);
scanUrlBtn.addEventListener("click", scanUrl);
quizForm.addEventListener("submit", submitQuiz);
initTabs();
checkHealth();
