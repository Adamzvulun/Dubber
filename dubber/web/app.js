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

/* Phone mode: this page was opened from the mailbox (https://…workers.dev/p/<token>/, phone.py / ADR-033). The
   household token is in the address; requests go to the home PC through its tunnel, links wait in the mailbox
   while the PC is off. On the PC itself PHONE is null and nothing changes. */
const PHONE = (() => {
  const m = location.pathname.match(/^\/p\/([A-Za-z0-9_-]{32,64})\//);
  return m ? { token: m[1], pc: null, online: false, checked: false, box: null, seen: null, install: null,
               timer: null } : null;
})();

/* ---------- helpers ---------- */
/** An abort signal that fires after `ms` (AbortSignal.timeout is missing on older iPhones). */
function timeout(ms) {
  const controller = new AbortController();
  setTimeout(() => controller.abort(), ms);
  return controller.signal;
}

/** Where a request goes: on the phone, the mailbox (/api/box…) or the home PC through its tunnel. */
function target(path) {
  if (!PHONE || path.startsWith("/api/box")) return path;
  if (!PHONE.online) throw new Error(PHONE.checked ? t("phone.pcLost") : t("phone.checking"));
  return PHONE.pc + path;
}

/** A video, picture or download address: on the phone it points at the PC and carries the token. */
function media(path) {
  if (!PHONE || !path) return path;
  return `${PHONE.pc}${path}${path.includes("?") ? "&" : "?"}t=${PHONE.token}`;
}

async function api(path, options = {}) {
  let res;
  const headers = { ...(options.headers || { "Content-Type": "application/json" }) };
  if (PHONE) headers["X-Dubber-Token"] = PHONE.token;
  const url = target(path);
  try {
    res = await fetch(url, { ...options, headers });
  } catch (_) {
    // the program window was closed, or the network is down
    if (PHONE && url !== path) { phoneLost(); throw new Error(t("phone.pcLost")); }
    throw new Error(PHONE ? t("phone.noInternet") : t("server.down"));
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
  if (voice === "original") return t("voice.original");
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

  if (page === "settings" && PHONE) { // the settings stay on the PC
    location.replace("#/");
    return;
  } else if (page === "settings") {
    $("#view-settings").hidden = false;
    $('[data-nav="settings"]').setAttribute("aria-current", "page");
    document.title = t("title.settings");
    loadSettings();
    loadClone();
    loadLogins();
    loadStorage();
    loadPhone();
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
  if (PHONE) $("#phone-bar").hidden = !$("#view-watch").hidden; // not over the video
  window.scrollTo(0, 0);
}

/* ---------- library ---------- */
/** One card per video (its dubs newest first): opens the newest dub; the watch page switches between them. */
function card(dubs) {
  const video = dubs[0];
  const node = $("#tpl-card").content.firstElementChild.cloneNode(true);
  node.href = `#/watch/${encodeURIComponent(video.id)}`;
  if (video.thumbnail) $("img", node).src = media(video.thumbnail);
  $(".card__duration", node).textContent = clock(video.duration);
  $(".card__title", node).textContent = video.title;
  if (dubs.length === 1) {
    $(".card__meta", node).textContent = [video.channel, dubLabel(video), dateLabel(video.created)]
      .filter(Boolean).join(" · ");
  } else { // several dubs: one tag per language; its dubs (voice, sound) on hover and for screen readers
    $(".card__meta", node).textContent = [video.channel, t("card.dubs", dubs.length), dateLabel(video.created)]
      .filter(Boolean).join(" · ");
    const byLang = new Map();
    for (const dub of dubs) byLang.set(dub.target_lang, [...(byLang.get(dub.target_lang) || []), dubLabel(dub)]);
    $(".card__tags", node).replaceChildren(...[...byLang].map(([lang, labels]) => el("span", {
      class: "tag", title: labels.join("\n"), "aria-label": labels.join("; "), text: lang.toUpperCase(),
    })));
  }
  return node;
}

/** The library's dubs grouped per video, newest first (the API sends dubs newest first). */
function videoGroups() {
  const groups = new Map();
  for (const dub of state.videos) {
    const key = dub.video_id || dub.id;
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key).push(dub);
  }
  return [...groups.values()];
}

/** Lower case, "ё" = "е": what the search compares. */
function searchable(text) {
  return (text || "").toLocaleLowerCase().replace(/ё/g, "е");
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
  const recent = $("#recent"), all = $("#library"), groups = videoGroups();
  recent.replaceChildren(...groups.slice(0, 6).map(card));
  if (!groups.length) recent.append(el("p", { class: "empty-note", text: t("recent.empty") }));
  $("#all-link").hidden = groups.length <= 6;

  const query = searchable($("#library-search").value.trim());
  const shown = query ? groups.filter((dubs) => searchable(`${dubs[0].title} ${dubs[0].channel}`).includes(query)) : groups;
  $("#library-search-box").hidden = groups.length < 2 && !query; // nothing to search in one video
  all.replaceChildren(...shown.map(card));
  if (!groups.length && PHONE && !PHONE.online) { // not empty: the PC that has the videos is off (phone mode)
    recent.replaceChildren(el("p", { class: "empty-note", text: t("phone.libraryOff") }));
    all.append(el("p", { class: "empty-note", text: t("phone.libraryOff") }));
  } else if (!groups.length) {
    all.append(el("div", { class: "empty-note" },
      el("p", { text: t("library.empty") }),
      el("p", {}, el("a", { class: "link", href: "#/", text: t("library.first") }))));
  } else if (!shown.length) {
    all.append(el("p", { class: "empty-note", text: t("library.noMatch") }));
  }
  $("#library-count").textContent = !groups.length ? "" : query ? t("library.found", shown.length, groups.length)
    : t("library.count", groups.length);
}

/* ---------- dubbing jobs ---------- */
function jobStatusText(job) {
  if (job.status === "done") return t("job.done");
  if (job.status === "error") return t("job.error");
  if (job.status === "cancelled") return t("job.cancelled");
  if (job.cancel_requested) return t("job.stopping");
  if (job.status === "queued") return t("job.queued");
  if (job.stage === "separate" && !job.remove_voice) return `${t("stage.separateCopy")}…`; // copying, not removing
  return `${job.stage ? t(`stage.${job.stage}`) : t("job.starting")}…`;
}

function jobSignature(job) {
  return [job.status, job.cancel_requested, job.stage, uiLang].join("|");
}

function jobCard(job) {
  // "separate" (removing or copying the original voice) is a step only when the job needs it; for the original
  // voice it comes before the voice-over (the separated voice is what gets copied).
  const separate = job.separate || job.remove_voice;
  let order = STEP_KEYS.filter((k) => k !== "separate" || separate);
  if (job.clone) order = [...order.filter((k) => k !== "separate" && k !== "tts" && k !== "align" && k !== "mux"),
    "separate", "tts", "align", "mux"];
  const keys = order;
  const labels = keys.map((k) => k === "separate" && !job.remove_voice ? t("steps.voiceCopy") : t("steps")[STEP_KEYS.indexOf(k)]);
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
    head, el("p", { class: "job__url", text: `${t("job.into", langName(job.lang || "ru"))} · ${job.title || job.url}` }));

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
    // a job cancelled while it waited in the queue did no work: no "the work done is kept"
    node.append(job.started ? el("p", { class: "job__note", text: t("job.cancelledNote") }) : null,
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

/** The form's choices for a new dub. */
function formChoices() {
  const background = $("#background").checked;
  return { voice: new FormData($("#dub-form")).get("voice") || "male", background, lang: $("#lang").value || "ru",
    remove_voice: background && $("#remove-voice").checked };
}

/** Queue one job per source ({url} or {file}); they run one after another. */
async function startJobs(sources, choices = formChoices()) {
  for (const [i, source] of sources.entries()) {
    try {
      await api("/api/jobs", { method: "POST", body: JSON.stringify({ ...source, ...choices }) });
    } catch (e) {
      // Phone: the PC went off just now — the links not sent yet wait in the mailbox instead of getting lost.
      const left = sources.slice(i).map((s) => s.url).filter(Boolean);
      if (!PHONE || PHONE.online || !left.length) throw e;
      await queueLinks(left, choices);
      return;
    }
  }
  pollJobs();
  if (sources.length > 1) $("#jobs-status").textContent = t("form.queued", sources.length);
}

/** While a request is on its way: no double submits, the button says so. */
async function busy(work, label = t("form.sending")) {
  if (state.submitting) return;
  state.submitting = true;
  const submit = $("#submit");
  showFormError("");
  submit.disabled = true; submit.textContent = label;
  try { await work(); } catch (e) { showFormError(e.message); } finally {
    state.submitting = false;
    submit.disabled = false; submit.textContent = t("form.submit");
  }
}

/** "playlist" for a playlist page, "both" for a video inside a playlist, null otherwise (YouTube mixes too). */
function playlistKind(link) {
  let url;
  try { url = new URL(link); } catch (_) { return null; }
  const list = url.searchParams.get("list");
  if (!list || list.startsWith("RD") || !/(^|\.)youtube\.com$|(^|\.)youtu\.be$/.test(url.hostname)) return null;
  if (url.pathname === "/playlist") return "playlist";
  return "both";
}

/** Shows the playlist question in the form; resolves to "one", "all" or null (cancelled, also Esc).
 * withOne: the link is a video inside the playlist ("just this video" is offered). */
function askPlaylist(playlist, withOne) {
  const box = $("#playlist-choice");
  state.playlistAsk = { playlist, withOne };
  renderPlaylistAsk();
  box.hidden = false;
  $("#submit").textContent = t("form.submit");
  (withOne ? $("#playlist-one") : $("#playlist-all")).focus();
  return new Promise((resolve) => {
    const onKey = (e) => { if (e.key === "Escape") { e.preventDefault(); done(null)(); } };
    const done = (answer) => () => {
      box.hidden = true; state.playlistAsk = null;
      document.removeEventListener("keydown", onKey);
      $("#submit").textContent = t("form.sending");
      resolve(answer);
    };
    $("#playlist-one").onclick = done("one");
    $("#playlist-all").onclick = done("all");
    $("#playlist-cancel").onclick = done(null);
    document.addEventListener("keydown", onKey); // Esc cancels, wherever the focus is
  });
}

function renderPlaylistAsk() {
  const ask = state.playlistAsk;
  if (!ask) return;
  const n = ask.playlist.entries.length, title = ask.playlist.title || "";
  $("#playlist-text").textContent = ask.withOne ? t("playlist.ask", title, n) : t("playlist.askAll", title, n);
  $("#playlist-one").hidden = !ask.withOne;
  $("#playlist-all").textContent = t("playlist.all", n);
}

/** The links in the field (one per line, or separated by spaces) → queued jobs; playlists become their videos. */
async function submitLinks() {
  // Links inside other text (a messenger's "Look: https://…") are taken out of it; plain text stays an error.
  const field = $("#url"), found = field.value.match(/https?:\/\/\S+/gi);
  const links = found || field.value.split(/\s+/).filter(Boolean);
  if (!links.length) { showFormError(t("form.badUrl")); field.focus(); return; }
  const bad = links.find((link) => !looksLikeUrl(link));
  if (bad) { showFormError(links.length > 1 ? t("form.badUrlLine", bad) : t("form.badUrl")); field.focus(); return; }
  const choices = formChoices(), sources = [];
  if (PHONE && !PHONE.online) { await queueOnPhone(links, choices); return; }
  let cancelled = false;
  await busy(async () => {
    for (const link of links) {
      const kind = playlistKind(link);
      if (!kind) { sources.push({ url: link }); continue; }
      $("#submit").textContent = t("playlist.loading");
      const playlist = await api("/api/playlist", { method: "POST", body: JSON.stringify({ url: link }) });
      if (!playlist.entries.length) throw new Error(t("playlist.empty"));
      // a video inside a playlist: always ask; a playlist page: ask only when it is long
      const answer = kind === "both" ? await askPlaylist(playlist, true)
        : playlist.entries.length > 10 ? await askPlaylist(playlist, false) : "all";
      if (answer === null) { cancelled = true; return; }
      if (answer === "one") sources.push({ url: link });
      else sources.push(...playlist.entries.map((entry) => ({ url: entry.url })));
    }
    $("#submit").textContent = t("form.sending");
    const unique = [...new Map(sources.map((source) => [source.url, source])).values()]; // a link listed twice
    await startJobs(unique, choices);
    field.value = ""; autoGrow();
  });
  if (cancelled) field.focus();
}

/** The link field grows with its lines (up to its max height). */
function autoGrow() {
  const field = $("#url");
  field.style.height = "auto";
  field.style.height = `${field.scrollHeight + 2}px`;
  if (!field.value) field.scrollLeft = 0; // else an emptied field shows its placeholder scrolled sideways
}

/* ---------- upload a video file ---------- */
const VIDEO_TYPES = /\.(mp4|mkv|webm|mov|avi|m4v|wmv|flv|mpg|mpeg|ts|3gp)$/i;
let uploadRequest = null;

function uploadFile(file) {
  if (!file || uploadRequest) return;
  showFormError("");
  if (!VIDEO_TYPES.test(file.name)) { showFormError(t("upload.badType")); return; }
  if (PHONE && !PHONE.online) { showFormError(t("phone.fileOffline")); $("#file").value = ""; return; }
  const choices = formChoices(), box = $("#upload");
  $("#upload-name").textContent = file.name;
  const show = (fraction) => {
    $("#upload-pct").textContent = `${Math.round(fraction * 100)}%`;
    $("#upload-fill").style.width = `${(fraction * 100).toFixed(1)}%`;
    $("#upload-bar").setAttribute("aria-valuenow", String(Math.round(fraction * 100)));
  };
  show(0);
  box.hidden = false;
  const xhr = uploadRequest = new XMLHttpRequest(); // fetch() can't report upload progress
  const finish = (message) => {
    uploadRequest = null; box.hidden = true; $("#file").value = "";
    if (message) showFormError(message);
  };
  xhr.open("POST", target(`/api/upload?name=${encodeURIComponent(file.name)}`));
  if (PHONE) xhr.setRequestHeader("X-Dubber-Token", PHONE.token);
  xhr.upload.onprogress = (e) => { if (e.lengthComputable) show(e.loaded / e.total); };
  xhr.onerror = () => finish(t("server.down"));
  xhr.onabort = () => finish("");
  xhr.onload = async () => {
    let body = {};
    try { body = JSON.parse(xhr.responseText); } catch (_) {}
    if (PHONE && xhr.status === 413) { finish(t("phone.tooBig")); return; } // Cloudflare takes up to 100 MB
    if (xhr.status !== 200) {
      const detail = body.detail && typeof body.detail === "object" ? (body.detail[uiLang] || body.detail.ru) : "";
      finish(detail || t("server.down"));
      return;
    }
    finish("");
    try { await startJobs([{ file: body.file }], choices); } catch (e) { showFormError(e.message); }
  };
  xhr.send(file);
}

async function cancelJob(job, button) {
  button.disabled = true;
  button.textContent = t("job.stopping");
  try { await api(`/api/jobs/${job.id}/cancel`, { method: "POST" }); } catch (_) {}
  pollJobs();
}

function retryJob(job) {
  dismissJob(job.id);
  const source = job.file ? { file: job.file } : { url: job.url };
  startJobs([source], { voice: job.voice, background: job.background, lang: job.lang || "ru",
    remove_voice: job.remove_voice }).catch((e) => showFormError(e.message));
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
    $("#view-watch").hidden = true; $("#view-missing").hidden = false; document.title = t("missing.title");
    const off = PHONE && !PHONE.online; // the video isn't gone: the PC that has it is off
    $("#view-missing h1").textContent = t(off ? "phone.watchOffTitle" : "missing.title");
    $("#view-missing p").textContent = t(off ? "phone.libraryOff" : "missing.text");
    return;
  }
  state.video = video;
  const player = $("#player");
  // Subtitles come from renderCaptions (the switches under the player), not from <track> files.
  player.replaceChildren(el("source", { src: media(video.video), type: "video/mp4" }));
  player.poster = media(video.thumbnail);
  player.load();
  renderWatchDetails();
  renderCaptions();
}

/* ---------- on-screen subtitles ---------- */
// One text track that the browser draws over the video itself, so the subtitles also show in full screen and on
// phones. Rebuilt from the two switches: the dub language follows the dub voice (video.spoken, from timing.json),
// the original follows the speaker.
let liveTrack = null;

function captionsTrack() {
  if (!liveTrack) liveTrack = $("#player").addTextTrack("subtitles", "Dubber", "");
  return liveTrack;
}

// Each line in a "first strong" bidi isolate: a cue takes one direction from its first letter, so under a Hebrew
// line an English one would be laid out right to left (its full stop on the left) without it.
const cueEscape = (text) => `\u2068${text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")}\u2069`;

/** [start, end] list → the same, each shown at least 1.2 s and held over short gaps (< 0.8 s) so lines don't flicker. */
function smoothTimes(times) {
  return times.map((t, i) => {
    if (!t) return null;
    const next = times.slice(i + 1).find(Boolean);
    let end = Math.max(t[1], t[0] + 1.2);
    if (next && next[0] - end < 0.8) end = next[0];
    return [t[0], next ? Math.min(end, Math.max(next[0], t[0] + 0.1)) : end];
  });
}

function renderCaptions() {
  const video = state.video, player = $("#player");
  if (!video) return;
  const dub = $("#cc-dub").checked, src = $("#cc-src").checked;
  const track = captionsTrack();
  for (const cue of [...(track.cues || [])]) track.removeCue(cue);
  const segments = video.segments || [], spoken = video.spoken || [];
  // A line already said in the dub language is not repeated as the original
  const original = (seg) => seg.text && !(dub && seg.text.trim() === (seg.ru || "").trim());
  const lines = [
    ...(dub ? smoothTimes(segments.map((seg, i) => seg.ru ? spoken[i] || [seg.start, seg.end] : null))
      .map((time, i) => time && { time, text: cueEscape(segments[i].ru), dub: true }) : []),
    ...(src ? smoothTimes(segments.map((seg) => original(seg) ? [seg.start, seg.end] : null))
      .map((time, i) => time && { time, text: `<c.src>${cueEscape(segments[i].text)}</c>` }) : []),
  ].filter(Boolean);
  // The dub line and the original have their own times; the browser would stack two cues in either order, so each
  // stretch of time gets one cue: the dub line on top, the original under it.
  const edges = [...new Set(lines.flatMap((l) => l.time))].sort((a, b) => a - b);
  let last = null;
  for (let k = 0; k + 1 < edges.length; k++) {
    const mid = (edges[k] + edges[k + 1]) / 2;
    const now = lines.filter((l) => l.time[0] <= mid && mid < l.time[1]).sort((a, b) => Number(Boolean(b.dub)) - Number(Boolean(a.dub)));
    const text = now.map((l) => l.text).join("\n");
    if (!text) { last = null; continue; }
    if (last && last.text === text && last.endTime === edges[k]) { last.endTime = edges[k + 1]; continue; }
    last = new VTTCue(edges[k], edges[k + 1], text);
    track.addCue(last);
  }
  track.mode = dub || src ? "showing" : "hidden";
  player.dataset.captions = track.mode;
}

/** The two switches: their labels, remembered choice (dub language on by default), and the browser's own CC menu. */
function initCaptions() {
  const dub = $("#cc-dub"), src = $("#cc-src"), player = $("#player");
  try {
    dub.checked = localStorage.getItem("dubber.ccDub") !== "0";
    src.checked = localStorage.getItem("dubber.ccSrc") === "1";
  } catch (_) { dub.checked = true; }
  const save = () => {
    try {
      localStorage.setItem("dubber.ccDub", dub.checked ? "1" : "0");
      localStorage.setItem("dubber.ccSrc", src.checked ? "1" : "0");
    } catch (_) {}
  };
  for (const box of [dub, src]) box.addEventListener("change", () => { save(); renderCaptions(); });
  // Subtitles switched on or off in the player's own menu (CC button, full screen): the switches follow.
  player.textTracks.addEventListener("change", () => {
    if (!liveTrack || !state.video) return;
    const showing = liveTrack.mode === "showing";
    if (showing === (player.dataset.captions === "showing")) return;
    if (showing) { dub.checked = true; } else { dub.checked = false; src.checked = false; }
    save();
    renderCaptions();
  });
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
  $("#cc-dub-text").textContent = langName(video.target_lang);
  $("#watch-title").textContent = video.title;
  $("#watch-meta").replaceChildren(...[
    video.channel, clock(video.duration), langName(video.target_lang), t("watch.voice", voiceName(video.voice)),
    video.background === false ? t("watch.noBackground") : null,
    video.remove_voice ? t("watch.noVoice") : null,
    ...(video.voice_notes || []).map((note) => t(`watch.voiceNote.${note}`)),
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
  const file = (name) => media(`/files/${video.id}/${name}?download=1`);
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
  if (!confirm(t("watch.delete", video.title, dubLabel(video), (video.siblings || []).length > 0))) return;
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

/** The "Original" voice: offered once it is installed (Settings); its hint says what it does, and that Hebrew can't. */
function updateVoiceOption() {
  const ready = Boolean(state.clone?.ready), radio = $("#voice-original");
  radio.disabled = !ready;
  $("#voice-original-label").hidden = !ready;
  if (!ready && radio.checked) $("#voice-male").checked = true;
  const hint = $("#voice-hint");
  hint.hidden = !radio.checked;
  const unsupported = (state.clone?.unsupported || []).includes($("#lang").value);
  hint.textContent = radio.checked ? t(unsupported ? "form.original.he" : "form.original.hint") : "";
  updateBackgroundHint();
}

/** The original voice copies the speaker from the separated voice track, so its background is always voice-free. */
function originalVoiceChosen() {
  return $("#voice-original").checked && !(state.clone?.unsupported || []).includes($("#lang").value);
}

function updateBackgroundHint() {
  const background = $("#background").checked, removeVoice = $("#remove-voice"), original = originalVoiceChosen();
  // without the speaker's voice only the music and sounds stay under the dub
  $("#background-hint").textContent = t(!background ? "form.background.off"
    : original || removeVoice.checked ? "form.background.music" : "form.background.on");
  // The user's own choice is kept while «Оригинал» locks the switch, and comes back when another voice is picked.
  if (original && !state.originalLock) state.removeVoiceChoice = removeVoice.checked;
  if (!original && state.originalLock) removeVoice.checked = state.removeVoiceChoice;
  state.originalLock = original;
  if (original) removeVoice.checked = background;
  removeVoice.disabled = !background || original; // without a background there is no voice to remove
  $("#remove-voice-hint").textContent = t(!background ? "form.removeVoice.disabled"
    : original ? "form.removeVoice.original" : removeVoice.checked ? "form.removeVoice.on" : "form.removeVoice.off");
}

/** Re-render everything after the interface language changes (without reloading the video). */
function applyUiLang() {
  applyStaticTexts();
  showFormError(""); // a validation message in the old language would linger otherwise
  showKeyError("");
  if (!state.submitting || state.playlistAsk) $("#submit").textContent = t("form.submit");
  document.querySelectorAll("[data-ui-lang]").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.uiLang === uiLang)));
  fillLanguageSelect();
  updateBackgroundHint();
  updateVoiceOption();
  renderJobs();
  renderClone();
  renderLogins();
  renderLibrary();
  renderSettings();
  renderVersion();
  renderUpdate();
  renderNews();
  renderPlaylistAsk();
  renderStorage();
  renderPhonePanel();
  renderPhoneBar();
  if (state.video) renderWatchDetails();
  else if (!$("#view-settings").hidden) document.title = t("title.settings");
  else if (!$("#view-library").hidden) document.title = t("title.library");
  else if (!$("#view-home").hidden) document.title = t("title.home");
  else if (!$("#view-missing").hidden) document.title = t("missing.title");
}

/* ---------- settings ---------- */
/* ---------- disk space (Settings page) ---------- */
/** 1536 → "1,5 КБ" / "1.5 KB". */
function sizeLabel(bytes) {
  const units = ["B", "KB", "MB", "GB"];
  let value = bytes || 0, unit = 0;
  while (value >= 1024 && unit < units.length - 1) { value /= 1024; unit++; }
  const digits = unit === 0 || value >= 100 ? 0 : 1;
  return t("size", value.toLocaleString(uiLang === "ru" ? "ru-RU" : "en-GB", { maximumFractionDigits: digits }), units[unit]);
}

async function loadStorage() {
  try { state.storage = await api("/api/storage"); } catch (_) { state.storage = null; }
  renderStorage();
}

function renderStorage() {
  const s = state.storage;
  if (!s) return;
  const stat = (label, bytes) => el("div", {}, el("dt", { text: label }), el("dd", { text: sizeLabel(bytes) }));
  $("#storage-totals").replaceChildren(stat(t("storage.cache"), s.cache), stat(t("storage.library"), s.library),
    s.models ? stat(t("storage.models"), s.models) : ""); // models: downloaded on the first dub
  $("#storage-clear-all").hidden = !s.cache;
  $("#storage-list").replaceChildren(...s.videos.map((v) => el("li", {},
    el("span", { class: "storage-list__name", text: v.title || t("storage.uploads"), title: v.title || t("storage.uploads") }),
    el("span", { class: "storage-list__size", text: [sizeLabel(v.cache), v.dubs ? t("storage.inLibrary", v.dubs) : null]
      .filter(Boolean).join(" · ") }),
    el("button", { class: "btn btn--quiet", type: "button", text: t("storage.clear"), "aria-label": t("storage.clearAria", v.title),
      onclick: () => clearCache(`/api/storage/cache/${encodeURIComponent(v.video_id)}`) }))));
  if (!s.videos.length) $("#storage-list").append(el("li", { class: "muted", text: t("storage.empty") }));
}

async function clearCache(path, confirmText) {
  if (confirmText && !confirm(confirmText)) return;
  const note = $("#storage-note");
  try {
    const { freed } = await api(path, { method: "DELETE" });
    note.textContent = t("storage.freed", sizeLabel(freed));
    note.classList.remove("is-error");
  } catch (e) { note.textContent = e.message; note.classList.add("is-error"); }
  note.hidden = false;
  $("#storage-title").focus(); // the pressed button may disappear with its row
  loadStorage();
}

/* ---------- site logins (sites.py): the cookies file for login-only videos ---------- */
async function loadLogins() {
  try { state.logins = await api("/api/cookies"); } catch (_) { return; }
  renderLogins();
}

function renderLogins() {
  const l = state.logins;
  if (!l) return;
  const on = l.sites.filter((s) => s.logged_in).length;
  const badge = $("#logins-badge");
  badge.textContent = on ? t("logins.badge.on", on) : t("logins.badge.off");
  badge.className = `badge${on ? " badge--on" : ""}`;
  $("#logins-list").replaceChildren(...l.sites.map((s) => el("li", { class: `logins__site${s.logged_in ? " is-on" : ""}` },
    el("span", { class: "logins__name", text: s.name }),
    el("span", { class: "logins__state", text: !s.logged_in ? t("logins.no")
      : s.expires ? t("logins.until", dateLabel(new Date(s.expires * 1000).toISOString())) : t("logins.yes") }))));
  $("#logins-remove").hidden = !l.saved;
}

function loginNote(text, error) {
  const note = $("#logins-note");
  note.textContent = text;
  note.classList.toggle("is-error", Boolean(error));
}

async function addLoginFile(file) {
  if (!file) return;
  loginNote("");
  try {
    state.logins = await api("/api/cookies", { method: "POST", headers: { "Content-Type": "text/plain" }, body: file });
    renderLogins();
    loginNote(t("logins.added"));
  } catch (e) { loginNote(e.message, true); }
  $("#logins-file").value = ""; // the same file can be chosen again
}

async function removeLogins() {
  if (!confirm(t("logins.confirmRemove"))) return;
  try { state.logins = await api("/api/cookies", { method: "DELETE" }); } catch (e) { loginNote(e.message, true); return; }
  renderLogins();
  loginNote(t("logins.removed"));
  $("#logins-add").focus(); // the pressed button disappears
}

/* ---------- the original voice (clone.py): graphics card check and install ---------- */
const CLONE_STEPS = ["torch", "omnivoice", "model"];
let clonePoll = null;

async function loadClone() {
  try { state.clone = await api("/api/clone"); } catch (_) { return; }
  renderClone();
  updateVoiceOption();
  clearTimeout(clonePoll);
  // also while the card check runs (clone.cuda_status: PyTorch takes a few seconds to start)
  if (state.clone.install?.running || (state.clone.installed && state.clone.cuda == null)) {
    clonePoll = setTimeout(loadClone, 3000);
  }
}

function renderClone() {
  const c = state.clone;
  if (!c) return;
  const install = c.install || {}, working = Boolean(install.running);
  const badge = $("#clone-badge");
  badge.textContent = t(working ? "clone.badge.working" : c.ready ? "clone.badge.ready" : "clone.badge.no");
  badge.className = `badge${c.ready && !working ? " badge--on" : ""}`;
  const gpu = $("#clone-gpu");
  gpu.textContent = !c.gpu ? t("clone.gpu.none") : c.gpu_ok ? t("clone.gpu.ok", c.gpu.name, c.gpu.vram_gb)
    : t("clone.gpu.small", c.gpu.name, c.gpu.vram_gb, c.min_vram_gb);
  // Installed: does PyTorch really compute on the card? (without it the voice would crawl on the processor)
  const cudaBad = c.ready && !working && c.cuda && !c.cuda.available;
  if (c.ready && !working && c.gpu_ok) {
    gpu.textContent += " " + (c.cuda == null ? t("clone.cuda.checking")
      : c.cuda.available ? t("clone.cuda.ok", c.cuda.cuda || "") : t("clone.cuda.bad", c.cuda.error || ""));
  }
  gpu.classList.toggle("is-error", !c.gpu_ok || cudaBad);
  const button = $("#clone-install");
  button.hidden = !c.gpu_ok || (c.ready && !working && !cudaBad);
  button.disabled = working;
  button.textContent = t(install.error ? "clone.retry" : "clone.install");
  const step = (key) => t(`clone.step.${key}`);
  // The bar: bytes downloaded so far (clone.Installer.progress); the step line says what is being installed.
  const pct = working && typeof install.progress === "number" ? Math.round(install.progress * 100) : null;
  $("#clone-bar").hidden = !working;
  $("#clone-fill").style.width = `${pct ?? 0}%`;
  $("#clone-bar").setAttribute("aria-valuenow", String(pct ?? 0));
  $("#clone-progress").textContent = working
    ? t("clone.step", CLONE_STEPS.indexOf(install.step) + 1, CLONE_STEPS.length, step(install.step || "torch"), pct)
    : install.error ? t("clone.error", step(install.error)) : c.ready && install.done ? t("clone.ready") : "";
  $("#clone-progress").classList.toggle("is-error", Boolean(install.error) && !working);
}

async function installClone() {
  $("#clone-install").disabled = true;
  try { state.clone = await api("/api/clone/install", { method: "POST" }); } catch (e) {
    $("#clone-progress").textContent = e.message; $("#clone-install").disabled = false; return;
  }
  renderClone();
  clearTimeout(clonePoll);
  clonePoll = setTimeout(loadClone, 3000);
}

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

/* ---------- "What's new" once after an update (dubber/changelog.json) ---------- */
/** "0.10.1" > "0.9.3" */
function newerVersion(a, b) {
  const pa = String(a).split(".").map(Number), pb = String(b).split(".").map(Number);
  for (let i = 0; i < 3; i++) if ((pa[i] || 0) !== (pb[i] || 0)) return (pa[i] || 0) > (pb[i] || 0);
  return false;
}

async function checkNews() {
  let seen = null;
  try { seen = localStorage.getItem("dubber.seenVersion"); } catch (_) { return; }
  if (!seen) {
    // 0.5.x didn't remember the version: someone who already used the program has settings or videos
    let used = false;
    try { used = Object.keys(localStorage).some((key) => key.startsWith("dubber.")); } catch (_) {}
    if (!used) { try { used = (await api("/api/videos")).length > 0; } catch (_) {} }
    if (!used) { markNewsSeen(); return; } // first visit ever: nothing is "new"
    seen = "0.5.1";
  }
  if (!newerVersion(state.version, seen)) return;
  let log = [];
  try { log = await api("/api/changelog"); } catch (_) { return; }
  state.news = log.filter((entry) => newerVersion(entry.version, seen) && !newerVersion(entry.version, state.version));
  renderNews();
}

function markNewsSeen() {
  try { localStorage.setItem("dubber.seenVersion", state.version); } catch (_) {}
}

function renderNews() {
  const box = $("#news"), news = state.news || [];
  box.hidden = !news.length;
  if (!news.length) return;
  $("#news-title").textContent = t("news.title", news[0].version);
  $("#news-list").replaceChildren(...news.flatMap((entry, i) => [
    i ? el("h3", { text: t("news.version", entry.version) }) : null,
    el("ul", {}, ...(entry[uiLang] || entry.ru).map((line) => el("li", { text: line }))),
  ].filter(Boolean)));
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
  $("#clone-install").addEventListener("click", installClone);
  $("#logins-add").addEventListener("click", () => $("#logins-file").click());
  $("#logins-file").addEventListener("change", (e) => addLoginFile(e.target.files[0]));
  $("#logins-remove").addEventListener("click", removeLogins);
  $("#storage-clear-all").addEventListener("click", () =>
    clearCache("/api/storage/cache", t("storage.confirmAll", sizeLabel(state.storage?.cache))));
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
  $("#dub-form").addEventListener("submit", (e) => { e.preventDefault(); submitLinks(); });
  $("#url").addEventListener("keydown", (e) => { // Enter dubs, Shift+Enter starts a new line for another link
    if (e.key === "Enter" && !e.shiftKey && !e.isComposing) { e.preventDefault(); submitLinks(); }
  });
  $("#url").addEventListener("input", autoGrow);
  $("#pick-file").addEventListener("click", () => $("#file").click());
  $("#file").addEventListener("change", (e) => uploadFile(e.target.files[0]));
  $("#upload-cancel").addEventListener("click", () => uploadRequest?.abort());
  // A file dropped anywhere else on the page would open in the tab and leave the program.
  for (const type of ["dragover", "drop"]) {
    window.addEventListener(type, (e) => { if ([...(e.dataTransfer?.types || [])].includes("Files")) e.preventDefault(); });
  }
  const composer = $("#dub-form");
  const hasFile = (e) => [...(e.dataTransfer?.types || [])].includes("Files");
  composer.addEventListener("dragover", (e) => { if (hasFile(e)) { e.preventDefault(); composer.classList.add("is-dragover"); } });
  composer.addEventListener("dragleave", (e) => { if (!composer.contains(e.relatedTarget)) composer.classList.remove("is-dragover"); });
  composer.addEventListener("drop", (e) => {
    if (!hasFile(e)) return;
    e.preventDefault(); composer.classList.remove("is-dragover");
    uploadFile(e.dataTransfer.files[0]);
  });

  try { state.dubLang = localStorage.getItem("dubber.dubLang") || "ru"; } catch (_) {}
  $("#lang").addEventListener("change", (e) => {
    state.dubLang = e.target.value;
    updateVoiceOption();
    try { localStorage.setItem("dubber.dubLang", e.target.value); } catch (_) {}
  });
  $("#url").addEventListener("input", () => { if (!$("#form-error").hidden) showFormError(""); showFormNote(""); });
  // The skip link must not change the hash (that is the router's job): just move focus to the content.
  $(".skip").addEventListener("click", (e) => { e.preventDefault(); $("#main").focus(); });
  $("#library-search").addEventListener("input", renderLibrary);
  $("#background").addEventListener("change", updateBackgroundHint);
  document.querySelectorAll('input[name="voice"]').forEach((r) => r.addEventListener("change", updateVoiceOption));
  $("#remove-voice").addEventListener("change", updateBackgroundHint);
  document.querySelectorAll("[data-ui-lang]").forEach((b) => b.addEventListener("click", () => {
    setUiLang(b.dataset.uiLang); applyUiLang();
  }));

  const showEn = $("#show-en");
  try { showEn.checked = localStorage.getItem("dubber.showEn") !== "0"; } catch (_) {}
  const applyEn = () => $(".transcript").classList.toggle("hide-en", !showEn.checked);
  showEn.addEventListener("change", () => { applyEn(); try { localStorage.setItem("dubber.showEn", showEn.checked ? "1" : "0"); } catch (_) {} });
  applyEn();

  initCaptions();
  initSettings();
  if (PHONE) initPhone();
  applyUiLang(); // interface language first, before waiting for the server (no flash of the other language)
  if (PHONE) await phoneConnect(); // finds the home PC (or not) before the first requests
  await loadLanguages();
  window.addEventListener("hashchange", route);
  route();
  if (!state.settings) loadSettings(); // the note under the dub form says which translator is used
  if (!state.clone) loadClone(); // the "Original" voice is offered once it is installed
  try {
    state.version = (await api("/api/version")).version; renderVersion();
    if (!PHONE) checkNews(); // "What's new" is about the PC program; the phone would show its whole history at once
  } catch (_) {}
  $("#news-close").addEventListener("click", () => { state.news = []; renderNews(); markNewsSeen(); });
  $("#update-btn").addEventListener("click", installUpdate);
  if (!PHONE) { // the PC updates itself; the phone app is updated with the mailbox
    checkUpdate();
    setInterval(checkUpdate, 60 * 60 * 1000); // the server asks GitHub at most once an hour
  }
  pollJobs();
}

/** Dub languages from the PC; the phone keeps a copy for when the PC is off (links are queued with a language). */
async function loadLanguages() {
  try {
    state.languages = await api("/api/languages");
    try { localStorage.setItem("dubber.languages", JSON.stringify(state.languages)); } catch (_) {}
  } catch (_) {
    try { state.languages = JSON.parse(localStorage.getItem("dubber.languages")) || state.languages; } catch (_) {}
  }
  fillLanguageSelect();
  renderLibrary();
}

/* ---------- the phone (phone mode only) ---------- */
function initPhone() {
  document.documentElement.classList.add("is-phone");
  $("#phone-bar").hidden = false;
  $("#pick-file").dataset.i18n = "form.pickFilePhone";
  if ("serviceWorker" in navigator) navigator.serviceWorker.register("sw.js").catch(() => {}); // opens offline too
  // Samsung: Share → Дубляж hands the link over in the address (share_target in the manifest).
  const params = new URLSearchParams(location.search);
  const shared = ["url", "text", "title"].map((k) => params.get(k) || "").join(" ").match(/https?:\/\/\S+/);
  if (shared) { $("#url").value = shared[0]; autoGrow(); }
  if (location.search) history.replaceState(null, "", location.pathname + location.hash);
  // Paste: one tap instead of a long press in the field.
  if (navigator.clipboard?.readText) {
    $("#paste").hidden = false;
    $("#paste").addEventListener("click", async () => {
      let text = "";
      try { text = await navigator.clipboard.readText(); } catch (_) {}
      const link = (text || "").match(/https?:\/\/\S+/);
      if (!link) { // no focus on the field: the keyboard would cover the message
        showFormError(t("phone.pasteEmpty")); $("#form-error").scrollIntoView({ block: "center", behavior: "smooth" }); return;
      }
      showFormError("");
      const field = $("#url");
      field.value = field.value.trim() ? `${field.value.trim()}\n${link[0]}` : link[0];
      autoGrow();
    });
  }
  window.addEventListener("beforeinstallprompt", (e) => { e.preventDefault(); PHONE.install = e; renderPhoneBar(); });
  window.addEventListener("appinstalled", () => { PHONE.install = null; renderPhoneBar(); });
  $("#phone-install").addEventListener("click", async () => {
    if (!PHONE.install) return;
    PHONE.install.prompt();
    try { await PHONE.install.userChoice; } catch (_) {}
    PHONE.install = null; renderPhoneBar();
  });
  document.addEventListener("visibilitychange", () => { if (!document.hidden) phoneConnect(); });
}

/** Ask the mailbox where the PC is, then ask the PC itself. Repeats: often while the PC is off. */
async function phoneConnect() {
  clearTimeout(PHONE.timer);
  let box = null, online = false;
  try { box = await api("/api/box"); } catch (_) {}
  if (box?.pc) {
    try {
      const res = await fetch(`${box.pc.url}/api/version`, { headers: { "X-Dubber-Token": PHONE.token }, signal: timeout(6000) });
      online = res.ok;
    } catch (_) {}
  }
  const was = PHONE.online;
  Object.assign(PHONE, { box, pc: box?.pc?.url || null, seen: box?.pc?.seen || null, online, checked: true });
  renderPhoneBar();
  if (online && !was && state.version !== undefined) { // the PC came back while the app was open
    await loadLanguages(); loadLibrary(); loadSettings(); loadClone(); pollJobs();
  }
  PHONE.timer = setTimeout(phoneConnect, online ? 60000 : 20000);
}

/** A request to the PC failed: show it as off and look for it again soon. */
function phoneLost() {
  if (!PHONE.online) return;
  PHONE.online = false;
  renderPhoneBar();
  clearTimeout(PHONE.timer);
  PHONE.timer = setTimeout(phoneConnect, 5000);
}

function seenLabel(iso) {
  if (!iso) return "";
  const date = new Date(iso), today = new Date();
  const time = date.toLocaleTimeString(uiLang === "ru" ? "ru-RU" : "en-GB", { hour: "2-digit", minute: "2-digit" });
  return date.toDateString() === today.toDateString() ? time : `${dateLabel(iso)} ${time}`;
}

function renderPhoneBar() {
  if (!PHONE) return;
  const bar = $("#phone-bar");
  bar.classList.toggle("is-on", PHONE.online);
  bar.classList.toggle("is-off", PHONE.checked && !PHONE.online);
  $("#phone-state-text").textContent = !PHONE.checked ? t("phone.checking")
    : PHONE.online ? t("phone.pcOn") : PHONE.box === null ? t("phone.noInternet")
    : PHONE.pc ? t("phone.pcOff", seenLabel(PHONE.seen)) : t("phone.noPc");
  const standalone = matchMedia("(display-mode: standalone)").matches || navigator.standalone === true;
  const ios = /iPhone|iPad|iPod/.test(navigator.userAgent) || (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1);
  $("#phone-install").hidden = standalone || !PHONE.install;
  $("#phone-ios").hidden = standalone || !ios;
  // Android without Chrome's install offer (Samsung Internet, a dismissed offer): the browser menu does it
  $("#phone-android").hidden = standalone || ios || Boolean(PHONE.install);
  $("#phone-install-box").hidden = $("#phone-install").hidden && $("#phone-ios").hidden && $("#phone-android").hidden;
  renderPhoneQueue();
}

function renderPhoneQueue() {
  const links = PHONE.box?.links || [];
  $("#phone-queue-box").hidden = !links.length;
  $("#phone-queue").replaceChildren(...links.map((link) => {
    let label = link.url;
    // the query too: two YouTube links differ only in ?v=…
    try { const u = new URL(link.url); label = u.hostname.replace(/^www\./, "") + u.pathname + u.search; } catch (_) {}
    return el("li", { class: "phone-queue__item" },
      el("span", { class: "phone-queue__link", text: label, title: link.url }),
      el("span", { class: "phone-queue__lang muted", text: langName(link.lang) }),
      el("button", { class: "btn btn--quiet", type: "button", text: t("phone.remove"), onclick: async (e) => {
        e.currentTarget.disabled = true;
        try { await api(`/api/box/links/${link.id}`, { method: "DELETE" }); } catch (_) {}
        try { PHONE.box = await api("/api/box"); } catch (_) {}
        renderPhoneQueue();
        ($("#phone-queue button") || $("#url")).focus(); // the pressed button is gone
      } }));
  }));
}

/** PC off: the links wait in the mailbox with the form's choices; the PC dubs them when it starts. */
async function queueOnPhone(links, choices) {
  await busy(async () => {
    await queueLinks(links, choices);
    $("#url").value = ""; autoGrow();
  });
}

async function queueLinks(links, choices) {
  const unique = [...new Set(links)];
  for (const url of unique) {
    await api("/api/box/links", { method: "POST", body: JSON.stringify({ url, ...choices }) });
  }
  showFormNote(t("phone.queued", unique.length)); // visible next to the button, not only for screen readers
  try { PHONE.box = await api("/api/box"); } catch (_) {}
  renderPhoneQueue();
}

/** A short confirmation under the form (e.g. "sent, waits for the computer"); cleared by the next edit. */
function showFormNote(text) {
  const note = $("#form-note");
  note.textContent = text;
  note.hidden = !text;
}

/* ---------- the phone panel in Settings (on the PC) ---------- */
let phonePanelTimer = null;

async function loadPhone() {
  clearTimeout(phonePanelTimer);
  try { state.phone = await api("/api/phone"); } catch (_) { return; }
  renderPhonePanel();
  // still getting ready: look again soon, while the settings page is open
  if (["starting", "downloading", "waiting"].includes(state.phone.status) && !$("#view-settings").hidden) {
    phonePanelTimer = setTimeout(loadPhone, 3000);
  }
}

function renderPhonePanel() {
  const phone = state.phone;
  if (!phone) return;
  const ready = phone.status === "ready" || (phone.pair_url && phone.status !== "unconfigured");
  $("#phone-badge").textContent = phone.status === "ready" ? t("phone.badge.ready")
    : phone.status === "off" ? t("phone.badge.off") : "";
  $("#phone-badge").hidden = !$("#phone-badge").textContent;
  $("#phone-badge").classList.toggle("badge--on", phone.status === "ready");
  $("#pair").hidden = !ready;
  const qr = $("#pair-qr");
  qr.alt = t("phone.qrAlt");
  if (ready && !qr.getAttribute("src")) qr.src = "/api/phone/qr";
  $("#phone-note").textContent = t(`phone.status.${phone.status}`);
}

init();
