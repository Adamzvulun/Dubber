/* Interface texts in Russian and English. The chosen language is remembered per browser (localStorage). */
"use strict";

const I18N = {
  ru: {
    "app.name": "Дубляж",
    "skip": "Перейти к содержимому",
    "nav.label": "Разделы",
    "nav.home": "Новое видео",
    "nav.library": "Библиотека",
    "home.aria": "Дубляж — на главную",
    "ui.lang": "Язык интерфейса",
    "hero.title": "Любое видео — на вашем языке",
    "hero.lead": "Вставьте ссылку на YouTube. Дубляж распознаёт речь на любом языке, переведёт её, озвучит и сохранит видео с субтитрами и текстом.",
    "form.url": "Ссылка на видео",
    "form.submit": "Озвучить",
    "form.lang": "Язык озвучки",
    "form.voice": "Голос",
    "form.male": "Мужской",
    "form.female": "Женский",
    "form.background": "Оригинальный звук фоном",
    "form.background.on": "Оригинальная речь и музыка тихо звучат под озвучкой",
    "form.background.off": "Будет слышна только озвучка, без музыки и оригинала",
    "form.badUrl": "Вставьте ссылку на видео — она начинается с https://",
    "server.down": "Сервер не ответил. Проверьте, что окно программы открыто.",
    "title.home": "Дубляж — любое видео на вашем языке",
    "title.library": "Библиотека — Дубляж",
    "recent.title": "Недавние видео",
    "recent.all": "Вся библиотека",
    "recent.empty": "Здесь появятся видео, которые вы озвучите.",
    "library.title": "Библиотека",
    "library.empty": "В библиотеке пока пусто.",
    "library.first": "Озвучить первое видео",
    "library.count": (n) => `${n}\u00a0видео`,
    "steps": ["Скачивание", "Распознавание речи", "Перевод", "Озвучка", "Синхронизация", "Сборка видео"],
    "stage.download": "Скачиваю видео",
    "stage.transcribe": "Распознаю речь",
    "stage.translate": "Перевожу",
    "stage.tts": "Озвучиваю",
    "stage.align": "Подгоняю озвучку по времени",
    "stage.mux": "Собираю итоговое видео",
    "job.queued": "В очереди",
    "job.starting": "Начинаю",
    "job.done": "Готово",
    "job.error": "Не получилось",
    "job.cancelled": "Отменено",
    "job.stopping": "Останавливаю…",
    "job.note": "Обычно дубляж занимает примерно столько же времени, сколько длится видео. Эту страницу можно закрыть — работа продолжится.",
    "job.cancelledNote": "Дубляж остановлен. Если начать заново, уже сделанная часть работы не пропадёт.",
    "job.progress": "Готовность",
    "job.into": (lang) => `Озвучка: ${lang}`,
    "btn.cancel": "Отменить",
    "btn.watch": "Смотреть",
    "btn.hide": "Скрыть",
    "btn.retry": "Попробовать снова",
    "btn.restart": "Начать заново",
    "btn.download": "Видео (.mp4)",
    "btn.srt": "Субтитры (.srt)",
    "btn.text": "Текст перевода (.txt)",
    "btn.bilingual": "Текст с оригиналом (.txt)",
    "btn.delete": "Удалить",
    "btn.openLibrary": "Открыть библиотеку",
    "watch.back": "Назад в библиотеку",
    "watch.text": "Текст",
    "watch.showOriginal": "Показывать оригинал",
    "watch.download": "Скачать",
    "watch.noText": "Текст недоступен.",
    "watch.voice": (name) => `Голос: ${name}`,
    "watch.noBackground": "Без оригинального звука",
    "watch.offline": "Перевод: резервный офлайн-переводчик (Google был недоступен)",
    "watch.subs": (lang) => `Субтитры: ${lang}`,
    "watch.subsOriginal": "Субтитры: оригинал",
    "watch.delete": (title) => `Удалить «${title}» из библиотеки? Файлы будут стёрты с компьютера.`,
    "missing.title": "Видео не найдено",
    "missing.text": "Возможно, оно было удалено.",
    "form.sending": "Отправляю…",
    "server.notFound": "Не найдено. Обновите страницу.",
  },
  en: {
    "app.name": "Dubber",
    "skip": "Skip to content",
    "nav.label": "Sections",
    "nav.home": "New video",
    "nav.library": "Library",
    "home.aria": "Dubber — home",
    "ui.lang": "Interface language",
    "hero.title": "Any video, in your language",
    "hero.lead": "Paste a YouTube link. Dubber recognises speech in any language, translates it, voices it and saves the video with subtitles and a transcript.",
    "form.url": "Video link",
    "form.submit": "Dub video",
    "form.lang": "Dub language",
    "form.voice": "Voice",
    "form.male": "Male",
    "form.female": "Female",
    "form.background": "Keep original audio in background",
    "form.background.on": "The original speech and music play quietly under the dub",
    "form.background.off": "Only the dubbed voice, without music or the original",
    "form.badUrl": "Paste a video link — it starts with https://",
    "server.down": "The server didn't answer. Check that the program window is open.",
    "title.home": "Dubber — any video in your language",
    "title.library": "Library — Dubber",
    "recent.title": "Recent videos",
    "recent.all": "See all",
    "recent.empty": "Videos you dub will appear here.",
    "library.title": "Library",
    "library.empty": "The library is empty so far.",
    "library.first": "Dub your first video",
    "library.count": (n) => `${n} ${n === 1 ? "video" : "videos"}`,
    "steps": ["Download", "Speech recognition", "Translation", "Voice-over", "Timing", "Final video"],
    "stage.download": "Downloading the video",
    "stage.transcribe": "Recognising speech",
    "stage.translate": "Translating",
    "stage.tts": "Generating the voice-over",
    "stage.align": "Fitting the voice to the timing",
    "stage.mux": "Building the final video",
    "job.queued": "Queued",
    "job.starting": "Starting",
    "job.done": "Done",
    "job.error": "Dubbing failed",
    "job.cancelled": "Cancelled",
    "job.stopping": "Stopping…",
    "job.note": "Dubbing usually takes about as long as the video itself. You can close this page — the work continues.",
    "job.cancelledNote": "Dubbing stopped. If you start again, the work already done is kept.",
    "job.progress": "Progress",
    "job.into": (lang) => `Dub: ${lang}`,
    "btn.cancel": "Cancel",
    "btn.watch": "Watch",
    "btn.hide": "Hide",
    "btn.retry": "Try again",
    "btn.restart": "Start again",
    "btn.download": "Video (.mp4)",
    "btn.srt": "Subtitles (.srt)",
    "btn.text": "Translated transcript (.txt)",
    "btn.bilingual": "Transcript with original (.txt)",
    "btn.delete": "Delete",
    "btn.openLibrary": "Open the library",
    "watch.back": "Back to library",
    "watch.text": "Transcript",
    "watch.showOriginal": "Show original",
    "watch.download": "Download",
    "watch.noText": "No transcript available.",
    "watch.voice": (name) => `Voice: ${name}`,
    "watch.noBackground": "Without the original sound",
    "watch.offline": "Translated by the offline backup (Google was unavailable)",
    "watch.subs": (lang) => `Subtitles: ${lang}`,
    "watch.subsOriginal": "Subtitles: original",
    "watch.delete": (title) => `Delete “${title}” from the library? Its files will be erased from this computer.`,
    "missing.title": "Video not found",
    "missing.text": "It may have been deleted.",
    "form.sending": "Sending…",
    "server.notFound": "Not found. Please reload the page.",
  },
};

const UI_LANGS = ["ru", "en"];

function initialUiLang() {
  try {
    const saved = localStorage.getItem("dubber.uiLang");
    if (UI_LANGS.includes(saved)) return saved;
  } catch (_) {}
  const preferred = navigator.languages?.length ? navigator.languages : [navigator.language || "ru"];
  return preferred.some((l) => l.toLowerCase().startsWith("ru")) ? "ru" : "en";
}

let uiLang = initialUiLang();

/** Text for `key` in the current interface language; function entries take arguments. */
function t(key, ...args) {
  const value = I18N[uiLang][key] ?? I18N.ru[key] ?? key;
  return typeof value === "function" ? value(...args) : value;
}

/** Fill every element marked with data-i18n (text), data-i18n-placeholder or data-i18n-aria (aria-label). */
function applyStaticTexts(root = document) {
  document.documentElement.lang = uiLang;
  root.querySelectorAll("[data-i18n]").forEach((n) => { n.textContent = t(n.dataset.i18n); });
  root.querySelectorAll("[data-i18n-placeholder]").forEach((n) => { n.placeholder = t(n.dataset.i18nPlaceholder); });
  root.querySelectorAll("[data-i18n-aria]").forEach((n) => n.setAttribute("aria-label", t(n.dataset.i18nAria)));
}

function setUiLang(lang) {
  if (!UI_LANGS.includes(lang)) return;
  uiLang = lang;
  try { localStorage.setItem("dubber.uiLang", lang); } catch (_) {}
}
