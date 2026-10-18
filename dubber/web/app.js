/* Dubber front-end: hash router, dubbing jobs, library, watch page with synced transcript.
   Interface texts live in i18n.js (t()); dub languages come from /api/languages. */
"use strict";

const $ = (sel, root = document) => root.querySelector(sel);
const STEP_KEYS = ["download", "transcribe", "translate", "tts", "align", "separate", "mux"]; // matches t("steps")
// Russian voices keep their Russian names in the Russian interface.
const RU_VOICE_NAMES = { "ru-RU-DmitryNeural": "Дмитрий", "ru-RU-SvetlanaNeural": "Светлана" };
const FALLBACK_LANGS = [{ code: "ru", name_ru: "Русский", name_en: "Russian", native: "Русский", rtl: false }];

const state = {
  jobs: new Map(), pollTimer: null, videos: [], seenDone: new Set(), languages: FALLBACK_LANGS, video: null,
  submitting: false, dubLang: "ru", firstRoute: true, settings: null, glossaryDirty: false,
};
const jobNodes = new Map(); // job id → { node, sig }: cards are patched in place so focus survives polling
const etaShown = new Map(); // job id → { text, at }: the time-left text changes at most every ETA_HOLD ms
const ETA_HOLD = 10000;

/* ---------- helpers ---------- */
async function api(path, options = {}) {
  let res;
  try {
    res = await fetch(path, { headers: { "Content-Type": "application/json" }, ...options });
  } catch (_) {
    throw new Error(t("server.down")); // the program window was closed, or the network is down
  }
  if (!res.ok) {
    let message = res.status === 404 ? t("server.notFound") : t("server.down");
    try {
      const { detail } = await res.json();
      // Our errors come as {ru, en}; FastAPI's own (404 "Not Found", 422 lists) are replaced by ours above.
      if (detail && typeof detail === "object" && !Array.isArray(detail)) message = detail[uiLang] || detail.ru || message;
    } catch (_) {}
    throw new Error(message);
  }
  return res.json();
}

function clock(seconds) {
  seconds = Math.max(0, Math.round(seconds || 0));
  const h = Math.floor(seconds / 3600), m = Math.floor((seconds % 3600) / 60), s = seconds % 60;
  const mm = h ? String(m).padStart(2, "0") : String(m);
  return (h ? `${h}:` : "") + `${mm}:${String(s).padStart(2, "0")}`;
}

function dateLabel(iso) {
  if (!iso) return "";
  return new Date(iso).toLocaleDateString(uiLang === "ru" ? "ru-RU" : "en-GB", { day: "numeric", month: "long", year: "numeric" })
    .replace(/ /g, "\u00a0"); // one unit: "г." never wraps onto its own line
}

function el(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === "class") node.className = v;
    else if (k === "text") node.textContent = v;
    else if (k.startsWith("on")) node.addEventListener(k.slice(2), v);
    else if (v !== false && v != null) node.setAttribute(k, v === true ? "" : v);
  }
  for (const c of children) if (c != null) node.append(c);
  return node;
}

function language(code) {
  return state.languages.find((l) => l.code === code) || null;
}

/** Name of a dub language in the interface language, e.g. "Иврит" / "Hebrew". */
function langName(code) {
  const lang = language(code);
  if (!lang) return (code || "").toUpperCase();
  return uiLang === "ru" ? lang.name_ru : lang.name_en;
}

/** "ru-RU-DmitryNeural" → "Дмитрий" (Russian UI) / "Dmitry"; "he-IL-HilaNeural" → "Hila". */
function voiceName(voice) {
  if (!voice) return "";
  if (uiLang === "ru" && RU_VOICE_NAMES[voice]) return RU_VOICE_NAMES[voice];
  const m = voice.match(/^[a-z]{2}-[A-Z]{2}-(.+?)(?:Multilingual)?Neural$/);
  return m ? m[1] : voice;
}

/** A web address worth sending: http(s), a host with a dot, no spaces (the server checks the same). */
function looksLikeUrl(text) {
  if (!/^https?:\/\//i.test(text) || /\s/.test(text)) return false;
  try { const host = new URL(text).hostname; return host === "localhost" || /^[a-z0-9-]+(\.[a-z0-9-]+)+$/i.test(host); }
  catch (_) { return false; }
}

/* ---------- router ---------- */
function route() {
  const hash = location.hash || "#/";
  const [, page, id] = hash.match(/^#\/?([^/]*)\/?(.*)$/) || [];
  document.querySelectorAll(".view").forEach((v) => (v.hidden = true));
  document.querySelectorAll("[data-nav]").forEach((a) => a.removeAttribute("aria-current"));
  stopPlayer();
  state.video = null;
  if (!state.firstRoute) $("#main").focus({ preventScroll: true }); // keyboard/screen-reader users land on the new page
  state.firstRoute = false;

  if (page === "settings") {
    $("#view-settings").hidden = false;
    $('[data-nav="settings"]').setAttribute("aria-current", "page");
    document.title = t("title.settings");
    loadSettings();
  } else if (page === "library") {
    $("#view-library").hidden = false;
    $('[data-nav="library"]').setAttribute("aria-current", "page");
    document.title = t("title.library");
    loadLibrary();
  } else if (page === "watch" && id) {
    $("#view-watch").hidden = false;
    $('[data-nav="library"]').setAttribute("aria-current", "page");
    showVideo(decodeURIComponent(id));
  } else {
    $("#view-home").hidden = false;
    $('[data-nav="home"]').setAttribute("aria-current", "page");
    document.title = t("title.home");
    loadLibrary();
  }
  window.scrollTo(0, 0);
}

/* ---------- library ---------- */
function card(video) {
  const node = $("#tpl-card").content.firstElementChild.cloneNode(true);
  node.href = `#/watch/${encodeURIComponent(video.id)}`;
  if (video.thumbnail) $("img", node).src = video.thumbnail;
  $(".card__duration", node).textContent = clock(video.duration);
  $(".card__title", node).textContent = video.title;
  $(".card__meta", node).textContent = [video.channel, dubLabel(video), dateLabel(video.created)]
    .filter(Boolean).join(" · ");
  return node;
}

/** What tells dubs of one video apart: language, voice, and the sound choices (e.g. "Русский · Дмитрий · без фона"). */
function dubLabel(dub) {
  return [langName(dub.target_lang), voiceName(dub.voice), dub.background === false ? t("card.noBackground") : null,
    dub.remove_voice ? t("card.noVoice") : null].filter(Boolean).join(" · ");
}

async function loadLibrary() {
  try { state.videos = await api("/api/videos"); } catch (_) { state.videos = []; }
  renderLibrary();
}

function renderLibrary() {
  const recent = $("#recent"), all = $("#library");
  recent.replaceChildren(...state.videos.slice(0, 6).map(card));
  if (!state.videos.length) recent.append(el("p", { class: "empty-note", text: t("recent.empty") }));
  $("#all-link").hidden = state.videos.length <= 6;

  all.replaceChildren(...state.videos.map(card));
  if (!state.videos.length) {
    all.append(el("div", { class: "empty-note" },
      el("p", { text: t("library.empty") }),
      el("p", {}, el("a", { class: "link", href: "#/", text: t("library.first") }))));
  }
  const n = state.videos.length;
  $("#library-count").textContent = n ? t("library.count", n) : "";
}

/* ---------- dubbing jobs ---------- */
function jobStatusText(job) {
  if (job.status === "done") return t("job.done");
  if (job.status === "error") return t("job.error");
  if (job.status === "cancelled") return t("job.cancelled");
  if (job.cancel_requested) return t("job.stopping");
  if (job.status === "queued") return t("job.queued");
  return `${job.stage ? t(`stage.${job.stage}`) : t("job.starting")}…`;
}

function jobSignature(job) {
  return [job.status, job.cancel_requested, job.stage, uiLang].join("|");
}

function jobCard(job) {
  // "separate" (removing the original voice) is a step only when the job asked for it.
  const keys = STEP_KEYS.filter((k) => k !== "separate" || job.remove_voice);
  const labels = t("steps").filter((_, i) => STEP_KEYS[i] !== "separate" || job.remove_voice);
  const activeIndex = keys.indexOf(job.stage);
  const running = job.status === "running" || job.status === "queued";
  const started = job.status === "running";
  const steps = el("ol", { class: "steps" }, ...labels.map((label, i) => {
    let cls = "";
    if (job.status === "done" || (running && activeIndex > i)) cls = "is-done";
    else if (running && activeIndex === i) cls = "is-active";
    return el("li", { class: cls, text: label });
  }));

  const elapsed = (Date.now() / 1000) - (job.started || job.created); // not counting the time in the queue
  const head = el("div", { class: "job__head" },
    el("span", { class: "job__status" },
      running ? el("span", { class: job.status === "queued" ? "lamp lamp--idle" : "lamp", "aria-hidden": "true" }) : null,
      document.createTextNode(jobStatusText(job))),
    started ? el("span", { class: "job__clock" },
      el("span", { class: "job__time", text: clock(elapsed) }),
      el("span", { class: "job__left", title: t("job.leftHint"), text: etaText(job) })) : null);

  const node = el("article", { class: `job job--${job.status}`, "data-job": job.id },
    head, el("p", { class: "job__url", text: `${t("job.into", langName(job.lang || "ru"))} · ${job.url}` }));

  const hide = () => el("button", { class: "btn", type: "button", "data-action": "hide", text: t("btn.hide"), onclick: () => dismissJob(job.id) });
  const cancel = () => el("button", { class: "btn", type: "button", "data-action": "cancel", disabled: job.cancel_requested,
    text: job.cancel_requested ? t("job.stopping") : t("btn.cancel"), onclick: (e) => cancelJob(job, e.currentTarget) });
  if (started) {
    node.append(
      el("div", { class: "bar", role: "progressbar", "aria-valuemin": "0", "aria-valuemax": "100",
        "aria-valuenow": String(Math.round(job.progress * 100)), "aria-label": t("job.progress") },
        el("div", { class: "bar__fill", style: `width:${(job.progress * 100).toFixed(1)}%` })),
      steps,
      el("p", { class: "job__note", text: t("job.note") }),
      el("div", { class: "job__actions" }, cancel()));
  } else if (job.status === "queued") { // compact: waits for the running job
    node.append(el("div", { class: "job__actions" }, cancel()));
  } else if (job.status === "done") {
    node.append(steps, el("div", { class: "job__actions" },
      el("a", { class: "btn btn--primary", "data-action": "watch", href: `#/watch/${encodeURIComponent(job.video_id)}`, text: t("btn.watch") }),
      hide()));
  } else if (job.status === "cancelled") {
    node.append(el("p", { class: "job__note", text: t("job.cancelledNote") }),
      el("div", { class: "job__actions" },
        el("button", { class: "btn", type: "button", "data-action": "retry", text: t("btn.restart"), onclick: () => retryJob(job) }), hide()));
  } else if (job.status === "error") {
    const message = uiLang === "en" ? (job.error_en || job.error) : job.error;
    node.append(el("p", { class: "job__error", text: message }), el("div", { class: "job__actions" },
      el("button", { class: "btn", type: "button", "data-action": "retry", text: t("btn.retry"), onclick: () => retryJob(job) }), hide()));
  }
  return node;
}

/** "45 мин", "1 ч 20 мин" / "45 min", "1 h 20 min". */
function duration(minutes) {
  const h = Math.floor(minutes / 60), m = minutes % 60;
  return h ? t("time.hm", h, m) : t("time.m", m);
}

/** Rough time left from the server's estimate (eta.py), steadied so it doesn't flicker between polls. */
function etaText(job) {
  let text;
  if (job.eta_seconds == null) text = t("job.estimating");
  else if (job.eta_seconds < 120) text = t("job.leftSoon");
  else text = t("job.left", duration(Math.ceil(job.eta_seconds / 60)));
  const shown = etaShown.get(job.id), now = Date.now();
  if (shown && shown.text !== text && shown.lang === uiLang && now - shown.at < ETA_HOLD) return shown.text;
  if (!shown || shown.text !== text || shown.lang !== uiLang) etaShown.set(job.id, { text, at: now, lang: uiLang });
  return text;
}

/** Progress and elapsed time change every second: patch them without rebuilding the card. */
function updateJobCard(node, job) {
  const left = $(".job__left", node);
  if (left) left.textContent = etaText(job);
  const fill = $(".bar__fill", node), bar = $(".bar", node), time = $(".job__time", node);
  if (fill) fill.style.width = `${(job.progress * 100).toFixed(1)}%`;
  if (bar) bar.setAttribute("aria-valuenow", String(Math.round(job.progress * 100)));
  if (time) time.textContent = clock((Date.now() / 1000) - (job.started || job.created));
}

function hiddenJobs() {
  try { return new Set(JSON.parse(localStorage.getItem("dubber.hiddenJobs") || "[]")); } catch (_) { return new Set(); }
}
function dismissJob(id) {
  const hidden = hiddenJobs(); hidden.add(id);
  try { localStorage.setItem("dubber.hiddenJobs", JSON.stringify([...hidden])); } catch (_) {}
  renderJobs();
}

const JOB_ORDER = { running: 0, queued: 1 };

/** Forget hidden-job ids the server no longer knows (keeps localStorage small). */
function pruneHiddenJobs() {
  const hidden = hiddenJobs(), kept = [...hidden].filter((id) => state.jobs.has(id));
  if (kept.length === hidden.size) return;
  try { localStorage.setItem("dubber.hiddenJobs", JSON.stringify(kept)); } catch (_) {}
}

function renderJobs() {
  const hidden = hiddenJobs(), container = $("#jobs");
  // The running job first, then the queue in the order it will run, then finished jobs (newest first).
  const visible = [...state.jobs.values()].filter((j) => !hidden.has(j.id)).sort((a, b) =>
    (JOB_ORDER[a.status] ?? 2) - (JOB_ORDER[b.status] ?? 2) || (a.status === "queued" ? a.created - b.created : b.created - a.created));

  const focused = container.contains(document.activeElement) ? document.activeElement : null;
  const focusJob = focused?.closest("[data-job]")?.dataset.job, focusAction = focused?.dataset.action;
  let announce = "";
  const nodes = visible.map((job) => {
    let entry = jobNodes.get(job.id);
    const sig = jobSignature(job);
    if (!entry || entry.sig !== sig) {
      if (entry) announce = jobStatusText(job); // a stage or status changed: tell screen readers once
      entry = { node: jobCard(job), sig };
      jobNodes.set(job.id, entry);
    } else {
      updateJobCard(entry.node, job);
    }
    return entry.node;
  });
  for (const id of [...jobNodes.keys()]) if (!state.jobs.has(id) || hidden.has(id)) jobNodes.delete(id);
  const same = nodes.length === container.children.length && nodes.every((n, i) => container.children[i] === n);
  if (!same) container.replaceChildren(...nodes);
  if (focusJob && !container.contains(document.activeElement)) {
    const card = container.querySelector(`[data-job="${focusJob}"]`);
    (card?.querySelector(`[data-action="${focusAction}"]`) || card?.querySelector("button, a"))?.focus();
  }
  if (announce) $("#jobs-status").textContent = announce;
}

async function pollJobs() {
  clearTimeout(state.pollTimer);
  let jobs = [];
  try { jobs = await api("/api/jobs"); } catch (_) {}
  state.jobs = new Map(jobs.map((j) => [j.id, j]));
  pruneHiddenJobs();
  renderJobs();
  for (const j of jobs) {
    if (j.status === "done" && !state.seenDone.has(j.id)) { state.seenDone.add(j.id); loadLibrary(); }
  }
  const active = jobs.some((j) => j.status === "running" || j.status === "queued");
  state.pollTimer = setTimeout(pollJobs, active ? 1000 : 5000);
}

function showFormError(message) {
  const error = $("#form-error"), url = $("#url");
  if (message) { error.hidden = false; error.textContent = message; url.setAttribute("aria-invalid", "true"); }
  else { error.hidden = true; error.textContent = ""; url.removeAttribute("aria-invalid"); }
}

async function startJob(url, voice, background, lang, removeVoice = false) {
  if (state.submitting) return; // no double submits while the request is on its way
  state.submitting = true;
  const submit = $("#submit");
  showFormError("");
  submit.disabled = true; submit.textContent = t("form.sending");
  try {
    await api("/api/jobs", { method: "POST", body: JSON.stringify({ url, voice, background, lang, remove_voice: removeVoice }) });
    $("#url").value = "";
    pollJobs();
  } catch (e) {
    showFormError(e.message);
  } finally {
    state.submitting = false;
    submit.disabled = false; submit.textContent = t("form.submit");
  }
}

async function cancelJob(job, button) {
  button.disabled = true;
  button.textContent = t("job.stopping");
  try { await api(`/api/jobs/${job.id}/cancel`, { method: "POST" }); } catch (_) {}
  pollJobs();
}

function retryJob(job) {
  dismissJob(job.id);
  startJob(job.url, job.voice, job.background, job.lang || "ru", job.remove_voice);
}

/* ---------- watch page ---------- */
let syncHandler = null;

function stopPlayer() {
  const player = $("#player");
  if (!player.paused) player.pause();
  if (syncHandler) { player.removeEventListener("timeupdate", syncHandler); syncHandler = null; }
}

async function showVideo(id) {
  let video;
  try { video = await api(`/api/videos/${encodeURIComponent(id)}`); } catch (_) {
    $("#view-watch").hidden = true; $("#view-missing").hidden = false; document.title = t("missing.title"); return;
  }
  state.video = video;
  const player = $("#player"), files = video.files || {}, src = (name) => `/files/${video.id}/${name}`;
  player.replaceChildren(
    el("source", { src: video.video, type: "video/mp4" }),
    files.dub_vtt ? el("track", { kind: "subtitles", srclang: video.target_lang, src: src(files.dub_vtt), "data-label": "dub" }) : null,
    files.src_vtt ? el("track", { kind: "subtitles", srclang: video.source_lang || "und", src: src(files.src_vtt), "data-label": "src" }) : null);
  player.poster = video.thumbnail;
  player.load();
  renderWatchDetails();
}

/** "claude-opus-5-5" → "Opus 5.5". */
function modelLabel(id) {
  const m = (id || "").match(/^claude-([a-z]+)-(\d+)-(\d+)$/);
  return m ? `${m[1][0].toUpperCase()}${m[1].slice(1)} ${m[2]}.${m[3]}` : id || "";
}

function usd(amount) {
  if (!amount) return "";
  return amount < 0.01 ? "< $0.01" : `$${amount.toFixed(2)}`;
}

/** Who translated this video (Claude with its cost, why Claude was skipped, or the offline backup). */
function translatorLabels(video) {
  const translator = video.translator || "", out = [];
  if (translator === "claude") out.push(t("watch.claude", modelLabel(video.translator_model), usd(video.translation_cost_usd)));
  const claudeNote = (video.translator_notes || []).find((n) => n.startsWith("claude:"));
  if (claudeNote && translator !== "claude") out.push(t("watch.claudeFailed", t(`reason.${claudeNote.split(":")[1]}`)));
  if (translator.includes("offline")) out.push(t("watch.offline"));
  return out;
}

/** Everything on the watch page that depends on the interface language (re-run when it changes). */
function renderWatchDetails() {
  const video = state.video;
  if (!video) return;
  document.title = `${video.title} — ${t("app.name")}`;
  for (const track of $("#player").querySelectorAll("track")) {
    track.label = track.dataset.label === "dub" ? t("watch.subs", langName(video.target_lang)) : t("watch.subsOriginal");
  }
  $("#watch-title").textContent = video.title;
  $("#watch-meta").replaceChildren(...[
    video.channel, clock(video.duration), langName(video.target_lang), t("watch.voice", voiceName(video.voice)),
    video.background === false ? t("watch.noBackground") : null,
    video.remove_voice ? t("watch.noVoice") : null,
    ...translatorLabels(video), dateLabel(video.created),
  ].filter(Boolean).map((text) => el("span", { text })));

  // Other dubs of this video (another language or voice): each is its own library entry.
  const siblings = video.siblings || [];
  $("#other-dubs").hidden = !siblings.length;
  $("#other-dubs-list").replaceChildren(...siblings.map((s) => el("a", {
    class: "btn", href: `#/watch/${encodeURIComponent(s.id)}`,
    text: dubLabel(s),
  })));

  const files = video.files || {};
  const file = (name) => `/files/${video.id}/${name}?download=1`;
  const link = (name, text, primary) => name
    ? el("a", { class: primary ? "btn btn--primary" : "btn", href: file(name), download: true, text }) : null;
  $("#downloads").replaceChildren(...[
    link("dubbed.mp4", t("btn.download"), true),
    link(files.dub_srt, t("btn.srt")),
    link(files.transcript, t("btn.text")),
    link(files.bilingual, t("btn.bilingual")),
  ].filter(Boolean));
  $("#delete-video").onclick = () => deleteVideo(video);

  renderTranscript(video);
}

function renderTranscript(video) {
  const segments = video.segments || [], list = $("#transcript"), player = $("#player");
  if (syncHandler) { player.removeEventListener("timeupdate", syncHandler); syncHandler = null; }
  const target = language(video.target_lang);
  // One tab stop for the whole list (roving tabindex); arrow keys move between lines, Enter/Space plays from a line.
  const move = (from, to) => {
    const next = lines[Math.max(0, Math.min(lines.length - 1, to))];
    if (!next || next === lines[from]) return;
    lines[from].tabIndex = -1; next.tabIndex = 0; next.focus();
  };
  const keys = { ArrowDown: (i) => i + 1, ArrowUp: (i) => i - 1, Home: () => 0, End: () => lines.length - 1 };
  const lines = segments.map((seg, i) => el("li", {
    class: target?.rtl ? "line line--rtl" : "line", tabindex: i === 0 ? "0" : "-1", "data-i": String(i),
    onclick: () => { player.currentTime = seg.start + 0.01; player.play().catch(() => {}); },
    onkeydown: (e) => {
      if (e.key === "Enter" || e.key === " ") { e.preventDefault(); e.currentTarget.click(); }
      else if (keys[e.key]) { e.preventDefault(); move(i, keys[e.key](i)); }
    },
  },
  el("span", { class: "line__time", text: clock(seg.start) }),
  el("span", {},
    el("span", { class: "line__ru", text: seg.ru, lang: video.target_lang, dir: target?.rtl ? "rtl" : null }),
    el("span", { class: "line__en", text: seg.text, lang: video.source_lang || null, dir: "auto" }))));
  list.replaceChildren(...lines);
  if (!segments.length) list.append(el("li", { class: "empty-note", text: t("watch.noText") }));

  let current = -1;
  syncHandler = () => {
    const time = player.currentTime;
    const i = segments.findIndex((s, k) => time >= s.start && time < (segments[k + 1]?.start ?? Infinity));
    if (i === current) return;
    lines[current]?.classList.remove("is-current");
    lines[current]?.removeAttribute("aria-current");
    current = i;
    const line = lines[i];
    if (!line) return;
    line.classList.add("is-current");
    line.setAttribute("aria-current", "true");
    // Scroll inside the panel only, never the page.
    const top = line.offsetTop - list.offsetTop - list.clientHeight / 3;
    list.scrollTo({ top, behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth" });
  };
  player.addEventListener("timeupdate", syncHandler);
}

async function deleteVideo(video) {
  if (!confirm(t("watch.delete", video.title, dubLabel(video)))) return;
  try { await api(`/api/videos/${encodeURIComponent(video.id)}`, { method: "DELETE" }); } catch (e) { alert(e.message); return; }
  location.hash = "#/library";
}

/* ---------- languages ---------- */
function fillLanguageSelect() {
  const select = $("#lang");
  select.replaceChildren(...state.languages.map((l) => {
    const name = uiLang === "ru" ? l.name_ru : l.name_en;
    return el("option", { value: l.code, text: name === l.native ? name : `${name} — ${l.native}` });
  }));
  select.value = language(state.dubLang) ? state.dubLang : "ru";
}

function updateBackgroundHint() {
  const background = $("#background").checked, removeVoice = $("#remove-voice");
  $("#background-hint").textContent = t(background ? "form.background.on" : "form.background.off");
  removeVoice.disabled = !background; // without a background there is no voice to remove
  $("#remove-voice-hint").textContent = t(!background ? "form.removeVoice.disabled"
    : removeVoice.checked ? "form.removeVoice.on" : "form.removeVoice.off");
}

/** Re-render everything after the interface language changes (without reloading the video). */
function applyUiLang() {
  applyStaticTexts();
  showFormError(""); // a validation message in the old language would linger otherwise
  showKeyError("");
  if (!state.submitting) $("#submit").textContent = t("form.submit");
  document.querySelectorAll("[data-ui-lang]").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.uiLang === uiLang)));
  fillLanguageSelect();
  updateBackgroundHint();
  renderJobs();
  renderLibrary();
  renderSettings();
  renderVersion();
  renderUpdate();
  if (state.video) renderWatchDetails();
  else if (!$("#view-settings").hidden) document.title = t("title.settings");
  else if (!$("#view-library").hidden) document.title = t("title.library");
  else if (!$("#view-home").hidden) document.title = t("title.home");
  else if (!$("#view-missing").hidden) document.title = t("missing.title");
}

/* ---------- settings ---------- */
async function loadSettings() {
  try { state.settings = await api("/api/settings"); } catch (_) { return; }
  renderSettings();
}

function announce(text) {
  $("#settings-status").textContent = "";
  setTimeout(() => { $("#settings-status").textContent = text; }, 50); // re-announce the same text too
}

function showKeyError(message) {
  const box = $("#key-error"), input = $("#claude-key");
  box.textContent = message;
  box.hidden = !message;
  if (message) input.setAttribute("aria-invalid", "true"); else input.removeAttribute("aria-invalid");
}

/** The settings page and the note under the dub form, from state.settings (re-run when the UI language changes). */
function renderSettings() {
  const s = state.settings;
  renderTranslatorNote();
  if (!s) return;
  const claude = s.claude, active = s.active;
  const badge = $("#claude-badge");
  badge.textContent = t(!claude.key_set ? "settings.badge.noKey" : active ? "settings.badge.on" : "settings.badge.off");
  badge.className = `badge${active ? " badge--on" : ""}`;
  $("#key-current").hidden = !claude.key_set;
  $("#key-current").textContent = claude.key_set ? t("settings.key.current", claude.key_hint) : "";
  $("#key-remove").hidden = !claude.key_set;

  const use = $("#use-claude");
  use.checked = active;
  use.disabled = !claude.key_set;
  $("#use-claude-hint").textContent = t(!claude.key_set ? "settings.use.noKey" : active ? "settings.use.on" : "settings.use.off");

  const select = $("#claude-model");
  select.replaceChildren(...claude.models.map((m) => el("option", {
    value: m.id, text: t("settings.model.option", m.label, t(`settings.model.${m.id}`)),
  })));
  select.value = claude.model;
  const model = claude.models.find((m) => m.id === claude.model);
  $("#model-price").textContent = model ? t("settings.model.price", usd(model.per_10_min_usd)) : "";
  if (!state.glossaryDirty) $("#glossary").value = s.glossary || "";
}

function renderVersion() {
  if (state.version) $("#app-version").textContent = t("footer.version", state.version);
}

/* ---------- new version (the program also updates itself at start, see dubber/update.py) ---------- */
async function checkUpdate() {
  try { state.update = await api("/api/update"); } catch (_) { return; }
  renderUpdate();
}

function renderUpdate() {
  const u = state.update, box = $("#update");
  if (state.installing) return; // keep the "updating" text
  box.hidden = !(u && (u.available || u.note));
  if (box.hidden) return;
  $("#update-text").textContent = u.note ? t(u.note) : t("update.available", u.latest);
  $("#update-btn").hidden = Boolean(u.note);
}

async function installUpdate() {
  const button = $("#update-btn");
  const done = (update) => {
    state.installing = false; button.disabled = false; button.removeAttribute("aria-busy");
    if (update) state.update = update;
    renderUpdate();
  };
  state.installing = true; button.disabled = true; button.setAttribute("aria-busy", "true");
  $("#update-text").textContent = t("update.working");
  let result;
  try { result = await api("/api/update", { method: "POST" }); } catch (e) {
    done(); $("#update-text").textContent = e.message; return;
  }
  if (!result.restarting) { done({ note: "update.restart" }); return; }
  for (let i = 0; i < 600; i++) { // the server restarts with the new version; dependencies can take minutes
    await new Promise((r) => setTimeout(r, 1000));
    try { if ((await api("/api/version")).version === result.installed) { location.reload(); return; } } catch (_) {}
  }
  done({ note: "update.restart" });
}

function renderTranslatorNote() {
  const s = state.settings, note = $("#translator-note");
  note.hidden = !s;
  if (!s) return;
  $("#translator-note-text").textContent = s.active
    ? t("form.translator.claude", modelLabel(s.claude.model)) : t("form.translator.free");
}

async function saveSettings(changes, savedNote) {
  try {
    state.settings = await api("/api/settings", { method: "PUT", body: JSON.stringify(changes) });
    renderSettings();
    announce(t("settings.saved"));
    if (savedNote) { savedNote.textContent = t("settings.saved"); savedNote.hidden = false; }
  } catch (err) {
    announce(err.message);
    loadSettings(); // show what is really saved
  }
}

function initSettings() {
  $("#key-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const input = $("#claude-key"), button = $("#key-save"), key = input.value.trim();
    if (!key) { showKeyError(t("settings.key.empty")); input.focus(); return; }
    showKeyError("");
    button.disabled = true;
    button.textContent = t("settings.key.checking");
    try {
      state.settings = await api("/api/settings/claude-key", { method: "POST", body: JSON.stringify({ key }) });
      input.value = "";
      renderSettings();
      announce(t("settings.key.saved"));
    } catch (err) {
      showKeyError(err.message);
      input.focus();
    } finally {
      button.disabled = false;
      button.textContent = t("settings.key.save");
    }
  });
  $("#claude-key").addEventListener("input", () => { if (!$("#key-error").hidden) showKeyError(""); });
  $("#key-remove").addEventListener("click", async () => {
    if (!confirm(t("settings.key.confirmRemove"))) return;
    try {
      state.settings = await api("/api/settings/claude-key", { method: "DELETE" });
      renderSettings();
      announce(t("settings.key.removed"));
      $("#claude-key").focus();
    } catch (err) { announce(err.message); }
  });
  $("#use-claude").addEventListener("change", (e) => saveSettings({ use_claude: e.target.checked }));
  $("#claude-model").addEventListener("change", (e) => saveSettings({ model: e.target.value }));
  $("#glossary").addEventListener("input", () => { state.glossaryDirty = true; $("#glossary-saved").hidden = true; });
  $("#glossary-save").addEventListener("click", async () => {
    await saveSettings({ glossary: $("#glossary").value }, $("#glossary-saved"));
    state.glossaryDirty = false;
  });
}

/* ---------- init ---------- */
async function init() {
  $("#dub-form").addEventListener("submit", (e) => {
    e.preventDefault();
    const url = $("#url").value.trim();
    if (!looksLikeUrl(url)) { showFormError(t("form.badUrl")); $("#url").focus(); return; }
    const voice = new FormData(e.target).get("voice") || "male";
    const background = $("#background").checked;
    startJob(url, voice, background, $("#lang").value || "ru", background && $("#remove-voice").checked);
  });

  try { state.dubLang = localStorage.getItem("dubber.dubLang") || "ru"; } catch (_) {}
  $("#lang").addEventListener("change", (e) => {
    state.dubLang = e.target.value;
    try { localStorage.setItem("dubber.dubLang", e.target.value); } catch (_) {}
  });
  $("#url").addEventListener("input", () => { if (!$("#form-error").hidden) showFormError(""); });
  // The skip link must not change the hash (that is the router's job): just move focus to the content.
  $(".skip").addEventListener("click", (e) => { e.preventDefault(); $("#main").focus(); });
  $("#background").addEventListener("change", updateBackgroundHint);
  $("#remove-voice").addEventListener("change", updateBackgroundHint);
  document.querySelectorAll("[data-ui-lang]").forEach((b) => b.addEventListener("click", () => {
    setUiLang(b.dataset.uiLang); applyUiLang();
  }));

  const showEn = $("#show-en");
  try { showEn.checked = localStorage.getItem("dubber.showEn") !== "0"; } catch (_) {}
  const applyEn = () => $(".transcript").classList.toggle("hide-en", !showEn.checked);
  showEn.addEventListener("change", () => { applyEn(); try { localStorage.setItem("dubber.showEn", showEn.checked ? "1" : "0"); } catch (_) {} });
  applyEn();

  initSettings();
  applyUiLang(); // interface language first, before waiting for the server (no flash of the other language)
  try { state.languages = await api("/api/languages"); fillLanguageSelect(); renderLibrary(); } catch (_) {}
  window.addEventListener("hashchange", route);
  route();
  if (!state.settings) loadSettings(); // the note under the dub form says which translator is used
  try { state.version = (await api("/api/version")).version; renderVersion(); } catch (_) {}
  $("#update-btn").addEventListener("click", installUpdate);
  checkUpdate();
  setInterval(checkUpdate, 60 * 60 * 1000); // the server asks GitHub at most once an hour
  pollJobs();
}

init();
