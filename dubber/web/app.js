/* Dubber front-end: hash router, dubbing jobs, library, watch page with synced transcript.
   Interface texts live in i18n.js (t()); dub languages come from /api/languages. */
"use strict";

const $ = (sel, root = document) => root.querySelector(sel);
const STEP_KEYS = ["download", "transcribe", "translate", "tts", "align", "mux"];
// Russian voices keep their Russian names in the Russian interface.
const RU_VOICE_NAMES = { "ru-RU-DmitryNeural": "Дмитрий", "ru-RU-SvetlanaNeural": "Светлана" };
const FALLBACK_LANGS = [{ code: "ru", name_ru: "Русский", name_en: "Russian", native: "Русский", rtl: false }];

const state = { jobs: new Map(), pollTimer: null, videos: [], seenDone: new Set(), languages: FALLBACK_LANGS, video: null };

/* ---------- helpers ---------- */
async function api(path, options = {}) {
  const res = await fetch(path, { headers: { "Content-Type": "application/json" }, ...options });
  if (!res.ok) {
    let message = t("server.down");
    try { const body = await res.json(); if (typeof body.detail === "string") message = body.detail; } catch (_) {}
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
  return new Date(iso).toLocaleDateString(uiLang === "ru" ? "ru-RU" : "en-GB", { day: "numeric", month: "long", year: "numeric" });
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

/* ---------- router ---------- */
function route() {
  const hash = location.hash || "#/";
  const [, page, id] = hash.match(/^#\/?([^/]*)\/?(.*)$/) || [];
  document.querySelectorAll(".view").forEach((v) => (v.hidden = true));
  document.querySelectorAll("[data-nav]").forEach((a) => a.removeAttribute("aria-current"));
  stopPlayer();
  state.video = null;

  if (page === "library") {
    $("#view-library").hidden = false;
    $('[data-nav="library"]').setAttribute("aria-current", "page");
    document.title = t("title.library");
    loadLibrary();
  } else if (page === "watch" && id) {
    $("#view-watch").hidden = false;
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
  $("img", node).src = video.thumbnail;
  $(".card__duration", node).textContent = clock(video.duration);
  $(".card__title", node).textContent = video.title;
  $(".card__meta", node).textContent = [video.channel, langName(video.target_lang), dateLabel(video.created)]
    .filter(Boolean).join(" · ");
  return node;
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

function jobCard(job) {
  const activeIndex = STEP_KEYS.indexOf(job.stage);
  const running = job.status === "running" || job.status === "queued";
  const steps = el("ol", { class: "steps" }, ...t("steps").map((label, i) => {
    let cls = "";
    if (job.status === "done" || (running && activeIndex > i)) cls = "is-done";
    else if (running && activeIndex === i) cls = "is-active";
    return el("li", { class: cls, text: label });
  }));

  const elapsed = (Date.now() / 1000) - job.created;
  const head = el("div", { class: "job__head" },
    el("span", { class: "job__status" },
      running ? el("span", { class: job.status === "queued" ? "lamp lamp--idle" : "lamp", "aria-hidden": "true" }) : null,
      document.createTextNode(jobStatusText(job))),
    running ? el("span", { class: "job__time", text: clock(elapsed) }) : null);

  const node = el("article", { class: `job job--${job.status}`, "data-job": job.id },
    head, el("p", { class: "job__url", text: `${t("job.into", langName(job.lang || "ru"))} · ${job.url}` }));

  const hide = () => el("button", { class: "btn", type: "button", text: t("btn.hide"), onclick: () => dismissJob(job.id) });
  if (running) {
    node.append(
      el("div", { class: "bar", role: "progressbar", "aria-valuemin": "0", "aria-valuemax": "100",
        "aria-valuenow": String(Math.round(job.progress * 100)), "aria-label": t("job.progress") },
        el("div", { class: "bar__fill", style: `width:${(job.progress * 100).toFixed(1)}%` })),
      steps,
      el("p", { class: "job__note", text: t("job.note") }),
      el("div", { class: "job__actions" },
        el("button", { class: "btn", type: "button", disabled: job.cancel_requested,
          text: job.cancel_requested ? t("job.stopping") : t("btn.cancel"), onclick: (e) => cancelJob(job, e.currentTarget) })));
  } else if (job.status === "done") {
    node.append(steps, el("div", { class: "job__actions" },
      el("a", { class: "btn btn--primary", href: `#/watch/${encodeURIComponent(job.video_id)}`, text: t("btn.watch") }),
      hide()));
  } else if (job.status === "cancelled") {
    node.append(el("p", { class: "job__note", text: t("job.cancelledNote") }),
      el("div", { class: "job__actions" },
        el("button", { class: "btn", type: "button", text: t("btn.restart"), onclick: () => retryJob(job) }), hide()));
  } else if (job.status === "error") {
    const message = uiLang === "en" ? (job.error_en || job.error) : job.error;
    node.append(el("p", { class: "job__error", text: message }), el("div", { class: "job__actions" },
      el("button", { class: "btn", type: "button", text: t("btn.retry"), onclick: () => retryJob(job) }), hide()));
  }
  return node;
}

function hiddenJobs() {
  try { return new Set(JSON.parse(localStorage.getItem("dubber.hiddenJobs") || "[]")); } catch (_) { return new Set(); }
}
function dismissJob(id) {
  const hidden = hiddenJobs(); hidden.add(id);
  try { localStorage.setItem("dubber.hiddenJobs", JSON.stringify([...hidden])); } catch (_) {}
  renderJobs();
}

function renderJobs() {
  const hidden = hiddenJobs();
  const visible = [...state.jobs.values()].filter((j) => !hidden.has(j.id)).sort((a, b) => b.created - a.created);
  $("#jobs").replaceChildren(...visible.map(jobCard));
}

async function pollJobs() {
  clearTimeout(state.pollTimer);
  let jobs = [];
  try { jobs = await api("/api/jobs"); } catch (_) {}
  state.jobs = new Map(jobs.map((j) => [j.id, j]));
  renderJobs();
  for (const j of jobs) {
    if (j.status === "done" && !state.seenDone.has(j.id)) { state.seenDone.add(j.id); loadLibrary(); }
  }
  const active = jobs.some((j) => j.status === "running" || j.status === "queued");
  $("#submit").disabled = false;
  state.pollTimer = setTimeout(pollJobs, active ? 1000 : 5000);
}

async function startJob(url, voice, background, lang) {
  const error = $("#form-error");
  error.hidden = true;
  $("#submit").disabled = true;
  try {
    await api("/api/jobs", { method: "POST", body: JSON.stringify({ url, voice, background, lang }) });
    $("#url").value = "";
    pollJobs();
  } catch (e) {
    error.textContent = e.message; error.hidden = false;
    $("#submit").disabled = false;
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
  startJob(job.url, job.voice, job.background, job.lang || "ru");
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
    $("#view-watch").hidden = true; $("#view-missing").hidden = false; return;
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
    video.background === false ? t("watch.noBackground") : null, dateLabel(video.created),
  ].filter(Boolean).map((text) => el("span", { text })));

  const files = video.files || {};
  const file = (name) => `/files/${video.id}/${name}?download=1`;
  const link = (name, text, primary) => name
    ? el("a", { class: primary ? "btn btn--primary" : "btn", href: file(name), download: true, text }) : null;
  $("#downloads").replaceChildren(...[
    link("dubbed.mp4", t("btn.download"), true),
    link(files.dub_srt, t("btn.srt")),
    link(files.transcript, t("btn.text")),
    link(files.bilingual, t("btn.bilingual")),
    el("span", { class: "spacer" }),
    el("button", { class: "btn btn--danger", type: "button", text: t("btn.delete"), onclick: () => deleteVideo(video) }),
  ].filter(Boolean));

  renderTranscript(video);
}

function renderTranscript(video) {
  const segments = video.segments || [], list = $("#transcript"), player = $("#player");
  if (syncHandler) { player.removeEventListener("timeupdate", syncHandler); syncHandler = null; }
  const target = language(video.target_lang);
  const lines = segments.map((seg, i) => el("li", {
    class: "line", tabindex: "0", "data-i": String(i),
    onclick: () => { player.currentTime = seg.start + 0.01; player.play(); },
    onkeydown: (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); e.currentTarget.click(); } },
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
    current = i;
    const line = lines[i];
    if (!line) return;
    line.classList.add("is-current");
    // Scroll inside the panel only, never the page.
    const top = line.offsetTop - list.offsetTop - list.clientHeight / 3;
    list.scrollTo({ top, behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth" });
  };
  player.addEventListener("timeupdate", syncHandler);
}

async function deleteVideo(video) {
  if (!confirm(t("watch.delete", video.title))) return;
  try { await api(`/api/videos/${encodeURIComponent(video.id)}`, { method: "DELETE" }); } catch (e) { alert(e.message); return; }
  location.hash = "#/library";
}

/* ---------- languages ---------- */
function fillLanguageSelect() {
  const select = $("#lang");
  let chosen = select.value;
  if (!chosen) { try { chosen = localStorage.getItem("dubber.dubLang") || "ru"; } catch (_) { chosen = "ru"; } }
  select.replaceChildren(...state.languages.map((l) => {
    const name = uiLang === "ru" ? l.name_ru : l.name_en;
    return el("option", { value: l.code, text: name === l.native ? name : `${name} — ${l.native}` });
  }));
  select.value = language(chosen) ? chosen : "ru";
}

function updateBackgroundHint() {
  $("#background-hint").textContent = t($("#background").checked ? "form.background.on" : "form.background.off");
}

/** Re-render everything after the interface language changes (without reloading the video). */
function applyUiLang() {
  applyStaticTexts();
  document.querySelectorAll("[data-ui-lang]").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.uiLang === uiLang)));
  fillLanguageSelect();
  updateBackgroundHint();
  renderJobs();
  renderLibrary();
  if (state.video) renderWatchDetails();
  else if ($("#view-library").hidden === false) document.title = t("title.library");
  else if ($("#view-home").hidden === false) document.title = t("title.home");
}

/* ---------- init ---------- */
async function init() {
  $("#dub-form").addEventListener("submit", (e) => {
    e.preventDefault();
    const url = $("#url").value.trim(), error = $("#form-error");
    if (!/^https?:\/\//i.test(url)) {
      error.textContent = t("form.badUrl");
      error.hidden = false; $("#url").focus(); return;
    }
    const voice = new FormData(e.target).get("voice") || "male";
    startJob(url, voice, $("#background").checked, $("#lang").value || "ru");
  });

  $("#lang").addEventListener("change", (e) => { try { localStorage.setItem("dubber.dubLang", e.target.value); } catch (_) {} });
  $("#background").addEventListener("change", updateBackgroundHint);
  document.querySelectorAll("[data-ui-lang]").forEach((b) => b.addEventListener("click", () => {
    setUiLang(b.dataset.uiLang); applyUiLang();
  }));

  const showEn = $("#show-en");
  try { showEn.checked = localStorage.getItem("dubber.showEn") !== "0"; } catch (_) {}
  const applyEn = () => $(".transcript").classList.toggle("hide-en", !showEn.checked);
  showEn.addEventListener("change", () => { applyEn(); try { localStorage.setItem("dubber.showEn", showEn.checked ? "1" : "0"); } catch (_) {} });
  applyEn();

  try { state.languages = await api("/api/languages"); } catch (_) {}
  applyUiLang();
  window.addEventListener("hashchange", route);
  route();
  pollJobs();
}

init();
