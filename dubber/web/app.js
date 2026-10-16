/* Dubber front-end: hash router, dubbing jobs, library, watch page with synced transcript. */
"use strict";

const $ = (sel, root = document) => root.querySelector(sel);
const STEPS = [
  ["download", "Скачивание"],
  ["transcribe", "Распознавание речи"],
  ["translate", "Перевод"],
  ["tts", "Озвучка"],
  ["align", "Синхронизация"],
  ["mux", "Сборка видео"],
];
const VOICE_NAMES = { "ru-RU-DmitryNeural": "Голос: Дмитрий", "ru-RU-SvetlanaNeural": "Голос: Светлана" };

const state = { jobs: new Map(), pollTimer: null, videos: [], seenDone: new Set() };

/* ---------- helpers ---------- */
async function api(path, options = {}) {
  const res = await fetch(path, { headers: { "Content-Type": "application/json" }, ...options });
  if (!res.ok) {
    let message = "Сервер не ответил. Проверьте, что окно программы открыто.";
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
  const d = new Date(iso);
  return d.toLocaleDateString("ru-RU", { day: "numeric", month: "long", year: "numeric" });
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

/* ---------- router ---------- */
function route() {
  const hash = location.hash || "#/";
  const [, page, id] = hash.match(/^#\/?([^/]*)\/?(.*)$/) || [];
  document.querySelectorAll(".view").forEach((v) => (v.hidden = true));
  document.querySelectorAll("[data-nav]").forEach((a) => a.removeAttribute("aria-current"));
  stopPlayer();

  if (page === "library") {
    $("#view-library").hidden = false;
    $('[data-nav="library"]').setAttribute("aria-current", "page");
    document.title = "Библиотека — Дубляж";
    loadLibrary();
  } else if (page === "watch" && id) {
    $("#view-watch").hidden = false;
    showVideo(decodeURIComponent(id));
  } else {
    $("#view-home").hidden = false;
    $('[data-nav="home"]').setAttribute("aria-current", "page");
    document.title = "Дубляж — английские видео на русском";
    loadLibrary();
  }
  window.scrollTo(0, 0);
}

/* ---------- library ---------- */
function card(video) {
  const node = $("#tpl-card").content.firstElementChild.cloneNode(true);
  node.href = `#/watch/${encodeURIComponent(video.id)}`;
  const img = $("img", node);
  img.src = video.thumbnail;
  $(".card__duration", node).textContent = clock(video.duration);
  $(".card__title", node).textContent = video.title;
  $(".card__meta", node).textContent = [video.channel, dateLabel(video.created)].filter(Boolean).join(", ");
  return node;
}

async function loadLibrary() {
  try { state.videos = await api("/api/videos"); } catch (_) { state.videos = []; }
  const recent = $("#recent"), all = $("#library");
  recent.replaceChildren(...state.videos.slice(0, 6).map(card));
  if (!state.videos.length) recent.append(el("p", { class: "empty-note", text: "Здесь появятся видео, которые вы озвучите." }));
  $("#all-link").hidden = state.videos.length <= 6;

  all.replaceChildren(...state.videos.map(card));
  if (!state.videos.length) {
    all.append(el("div", { class: "empty-note" },
      el("p", { text: "В библиотеке пока пусто." }),
      el("p", {}, el("a", { class: "link", href: "#/", text: "Озвучить первое видео" }))));
  }
  const n = state.videos.length;
  $("#library-count").textContent = n ? `${n} ${plural(n, "видео", "видео", "видео")}` : "";
}

function plural(n, one, few, many) {
  const m10 = n % 10, m100 = n % 100;
  if (m10 === 1 && m100 !== 11) return one;
  if (m10 >= 2 && m10 <= 4 && (m100 < 12 || m100 > 14)) return few;
  return many;
}

/* ---------- dubbing jobs ---------- */
function jobCard(job) {
  const activeIndex = STEPS.findIndex(([key]) => key === job.stage);
  const running = job.status === "running" || job.status === "queued";
  const steps = el("ol", { class: "steps" }, ...STEPS.map(([key, label], i) => {
    let cls = "";
    if (job.status === "done" || (running && activeIndex > i)) cls = "is-done";
    else if (running && activeIndex === i) cls = "is-active";
    return el("li", { class: cls, text: label });
  }));

  const elapsed = (Date.now() / 1000) - job.created;
  const head = el("div", { class: "job__head" },
    el("span", { class: "job__status" },
      running ? el("span", { class: job.status === "queued" ? "lamp lamp--idle" : "lamp", "aria-hidden": "true" }) : null,
      document.createTextNode(
        job.status === "done" ? "Готово" :
        job.status === "error" ? "Не получилось" :
        job.status === "cancelled" ? "Отменено" :
        job.cancel_requested ? "Останавливаю…" :
        job.status === "queued" ? "В очереди" : `${job.label}…`)),
    running ? el("span", { class: "job__time", text: clock(elapsed) }) : null);

  const node = el("article", { class: `job job--${job.status}`, "data-job": job.id },
    head, el("p", { class: "job__url", text: job.url }));

  if (running) {
    node.append(
      el("div", { class: "bar", role: "progressbar", "aria-valuemin": "0", "aria-valuemax": "100",
        "aria-valuenow": String(Math.round(job.progress * 100)), "aria-label": "Готовность" },
        el("div", { class: "bar__fill", style: `width:${(job.progress * 100).toFixed(1)}%` })),
      steps,
      el("p", { class: "job__note", text: "Обычно дубляж занимает примерно столько же времени, сколько длится видео. Эту страницу можно закрыть — работа продолжится." }),
      el("div", { class: "job__actions" },
        el("button", { class: "btn", type: "button", disabled: job.cancel_requested,
          text: job.cancel_requested ? "Останавливаю…" : "Отменить", onclick: (e) => cancelJob(job, e.currentTarget) })));
  } else if (job.status === "done") {
    node.append(steps, el("div", { class: "job__actions" },
      el("a", { class: "btn btn--primary", href: `#/watch/${encodeURIComponent(job.video_id)}`, text: "Смотреть" }),
      el("button", { class: "btn", type: "button", text: "Скрыть", onclick: () => dismissJob(job.id) })));
  } else if (job.status === "cancelled") {
    node.append(el("p", { class: "job__note", text: "Дубляж остановлен. Если начать заново, уже сделанная часть работы не пропадёт." }),
      el("div", { class: "job__actions" },
        el("button", { class: "btn", type: "button", text: "Начать заново", onclick: () => retryJob(job) }),
        el("button", { class: "btn", type: "button", text: "Скрыть", onclick: () => dismissJob(job.id) })));
  } else if (job.status === "error") {
    node.append(el("p", { class: "job__error", text: job.error }), el("div", { class: "job__actions" },
      el("button", { class: "btn", type: "button", text: "Попробовать снова", onclick: () => retryJob(job) }),
      el("button", { class: "btn", type: "button", text: "Скрыть", onclick: () => dismissJob(job.id) })));
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

async function startJob(url, voice, background) {
  const error = $("#form-error");
  error.hidden = true;
  $("#submit").disabled = true;
  try {
    await api("/api/jobs", { method: "POST", body: JSON.stringify({ url, voice, background }) });
    $("#url").value = "";
    pollJobs();
  } catch (e) {
    error.textContent = e.message; error.hidden = false;
    $("#submit").disabled = false;
  }
}

async function cancelJob(job, button) {
  button.disabled = true;
  button.textContent = "Останавливаю…";
  try { await api(`/api/jobs/${job.id}/cancel`, { method: "POST" }); } catch (_) {}
  pollJobs();
}

function retryJob(job) {
  dismissJob(job.id);
  startJob(job.url, job.voice, job.background);
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
  document.title = `${video.title} — Дубляж`;
  const player = $("#player");
  player.replaceChildren(
    el("source", { src: video.video, type: "video/mp4" }),
    el("track", { kind: "subtitles", srclang: "ru", label: "Русские субтитры", src: `/files/${video.id}/subtitles_ru.vtt` }),
    el("track", { kind: "subtitles", srclang: "en", label: "English subtitles", src: `/files/${video.id}/subtitles_en.vtt` }));
  player.poster = video.thumbnail;
  player.load();

  $("#watch-title").textContent = video.title;
  $("#watch-meta").replaceChildren(...[
    video.channel, clock(video.duration), VOICE_NAMES[video.voice],
    video.background === false ? "Без оригинального звука" : null, dateLabel(video.created),
  ].filter(Boolean).map((t) => el("span", { text: t })));

  const file = (name) => `/files/${video.id}/${name}?download=1`;
  $("#downloads").replaceChildren(
    el("a", { class: "btn btn--primary", href: file("dubbed.mp4"), download: true, text: "Скачать видео" }),
    el("a", { class: "btn", href: file("subtitles_ru.srt"), download: true, text: "Субтитры .srt" }),
    el("a", { class: "btn", href: file("transcript_ru.txt"), download: true, text: "Текст" }),
    el("a", { class: "btn", href: file("transcript_en_ru.txt"), download: true, text: "Текст EN + RU" }),
    el("span", { class: "spacer" }),
    el("button", { class: "btn btn--danger", type: "button", text: "Удалить", onclick: () => deleteVideo(video) }));

  renderTranscript(video.segments || []);
}

function renderTranscript(segments) {
  const list = $("#transcript"), player = $("#player");
  const lines = segments.map((seg, i) => el("li", {
    class: "line", tabindex: "0", "data-i": String(i),
    onclick: () => { player.currentTime = seg.start + 0.01; player.play(); },
    onkeydown: (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); e.currentTarget.click(); } },
  },
  el("span", { class: "line__time", text: clock(seg.start) }),
  el("span", {}, el("span", { class: "line__ru", text: seg.ru }), el("span", { class: "line__en", text: seg.text, lang: "en" }))));
  list.replaceChildren(...lines);
  if (!segments.length) list.append(el("li", { class: "empty-note", text: "Текст недоступен." }));

  let current = -1;
  syncHandler = () => {
    const t = player.currentTime;
    let i = segments.findIndex((s, k) => t >= s.start && t < (segments[k + 1]?.start ?? Infinity));
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
  if (!confirm(`Удалить «${video.title}» из библиотеки? Файлы будут стёрты с компьютера.`)) return;
  try { await api(`/api/videos/${encodeURIComponent(video.id)}`, { method: "DELETE" }); } catch (e) { alert(e.message); return; }
  location.hash = "#/library";
}

/* ---------- init ---------- */
function init() {
  $("#dub-form").addEventListener("submit", (e) => {
    e.preventDefault();
    const url = $("#url").value.trim(), error = $("#form-error");
    if (!/^https?:\/\//i.test(url)) {
      error.textContent = "Вставьте ссылку на видео — она начинается с https://";
      error.hidden = false; $("#url").focus(); return;
    }
    const voice = new FormData(e.target).get("voice") || "male";
    startJob(url, voice, $("#background").checked);
  });

  const hint = $("#background-hint");
  $("#background").addEventListener("change", (e) => {
    hint.textContent = e.target.checked
      ? "Английская речь и музыка тихо звучат под русским голосом"
      : "Будет слышен только русский голос, без музыки и оригинала";
  });

  const showEn = $("#show-en");
  try { showEn.checked = localStorage.getItem("dubber.showEn") !== "0"; } catch (_) {}
  const applyEn = () => $(".transcript").classList.toggle("hide-en", !showEn.checked);
  showEn.addEventListener("change", () => { applyEn(); try { localStorage.setItem("dubber.showEn", showEn.checked ? "1" : "0"); } catch (_) {} });
  applyEn();

  window.addEventListener("hashchange", route);
  route();
  pollJobs();
}

init();
