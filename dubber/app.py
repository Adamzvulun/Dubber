"""Russian-language web page: paste a YouTube link, get the dubbed video.

Run: `python -m dubber.app` → opens http://127.0.0.1:7860
"""

from __future__ import annotations

import os
from pathlib import Path

import gradio as gr

from . import pipeline
from .config import Settings, load_settings
from .download import is_url

VOICE_CHOICES = {"Мужской голос": "ru-RU-DmitryNeural", "Женский голос": "ru-RU-SvetlanaNeural"}

CSS = """
:root, .gradio-container { --dub-ink: #1B2433; --dub-blue: #2459D6; --dub-muted: #556070; }
.gradio-container { max-width: 860px !important; margin: 0 auto !important; font-size: 18px; }
#dub-title h1 { font-family: 'PT Serif', Georgia, serif; font-size: 2.3rem; font-weight: 700;
  color: var(--dub-ink); margin: 0.6em 0 0.2em; letter-spacing: -0.01em; }
#dub-title p { color: var(--dub-muted); font-size: 1.15rem; margin: 0 0 0.6em; max-width: 60ch; }
#dub-url textarea, #dub-url input { font-size: 1.15rem !important; padding: 14px !important; }
#dub-go { font-size: 1.25rem !important; min-height: 60px; }
#dub-status { font-size: 1.1rem; }
@media (prefers-reduced-motion: reduce) { * { transition: none !important; animation: none !important; } }
"""

HEAD = (
    '<link rel="preconnect" href="https://fonts.googleapis.com">'
    '<link href="https://fonts.googleapis.com/css2?family=PT+Serif:wght@700&display=swap" rel="stylesheet">'
)

HELP = """
**Как пользоваться**
1. Откройте видео на YouTube, скопируйте адрес из строки браузера.
2. Вставьте его в поле выше и нажмите **«Озвучить по-русски»**.
3. Дождитесь окончания. Обычно это занимает от половины до полной длины видео
   (видео на 10 минут — примерно 5–10 минут). Окно можно не трогать.
4. Смотрите прямо здесь или сохраните файлы кнопками ниже.

**Полезно знать**
- В готовом видео две звуковые дорожки: русская (по умолчанию) и оригинальная английская.
  Переключить можно в плеере на компьютере (например, VLC: «Аудио → Аудиодорожка»).
- Русские субтитры встроены в видео и лежат отдельным файлом `.srt`.
- Файл «EN + RU» — английский текст с переводом построчно: удобно для изучения терминов.
- Все готовые видео хранятся в папке `output` программы.
"""


def make_theme() -> gr.themes.Base:
    # PT Sans / PT Serif were designed by ParaType for Russian Cyrillic.
    fonts = [gr.themes.GoogleFont("PT Sans"), gr.themes.Font("Arial"), gr.themes.Font("sans-serif")]
    return gr.themes.Base(primary_hue="blue", neutral_hue="slate", font=fonts)


def friendly_error(exc: Exception) -> str:
    """Turn a technical error into a short Russian explanation with what to do."""
    text = f"{type(exc).__name__}: {exc}".lower()
    if "ffmpeg" in text and "not found" in text:
        return "Не найдена программа ffmpeg. Запустите установку ещё раз (install_windows.bat)."
    if "downloaderror" in text or "youtube" in text or "unsupported url" in text:
        return (
            "Не удалось скачать видео. Проверьте, что ссылка правильная и интернет работает. "
            "Если ошибка повторяется — запустите установку ещё раз, она обновит загрузчик."
        )
    if "английской речи" in text:
        return "В этом видео не найдено английской речи."
    if any(w in text for w in ("connect", "timeout", "network", "dns", "proxy", "ssl")):
        return "Нет связи с интернет-сервисом перевода или озвучки. Проверьте интернет и попробуйте снова."
    return f"Что-то пошло не так. Попробуйте ещё раз. Подробности для помощника: {exc}"


def previous_results(settings: Settings) -> list[tuple[str, str]]:
    if not settings.output_dir.exists():
        return []
    folders = sorted(
        (p for p in settings.output_dir.iterdir() if p.is_dir() and any(p.glob("*.mp4"))),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    return [(p.name, str(p)) for p in folders]


def _outputs_for_folder(folder: Path):
    video = next(folder.glob("*.mp4"), None)
    files = [folder / n for n in ("subtitles_ru.srt", "transcript_ru.txt", "transcript_en_ru.txt")]
    srt = files[0] if files[0].exists() else None
    return (
        gr.update(value=str(video) if video else None, subtitles=str(srt) if srt else None, visible=video is not None),
        gr.update(value=str(video) if video else None, visible=video is not None),
        *[gr.update(value=str(f) if f.exists() else None, visible=f.exists()) for f in files],
    )


def build_ui(settings: Settings | None = None, runner=pipeline.run) -> gr.Blocks:
    settings = settings or load_settings()

    def dub(url: str, voice_label: str, progress=gr.Progress()):  # noqa: B008 (Gradio injects progress this way)
        url = (url or "").strip()
        if not url:
            raise gr.Error("Вставьте ссылку на видео с YouTube.", title="Ошибка")
        if not is_url(url) and not Path(url).is_file():
            raise gr.Error("Это не похоже на ссылку. Она должна начинаться с https://", title="Ошибка")
        settings.voice = VOICE_CHOICES.get(voice_label, settings.voice)
        try:
            result = runner(url, settings, progress=lambda label, f: progress(f, desc=label))
        except gr.Error:
            raise
        except Exception as exc:  # shown to the user in Russian
            raise gr.Error(friendly_error(exc), duration=None, title="Ошибка") from exc
        status = f"✅ Готово: **{result.title}**"
        return (status, *_outputs_for_folder(result.folder), gr.update(choices=previous_results(settings)))

    def open_previous(folder: str | None):
        if not folder:
            return ("", *[gr.update()] * 5)
        return (f"Открыто: **{Path(folder).name}**", *_outputs_for_folder(Path(folder)))

    with gr.Blocks(title="Дубляж видео") as ui:
        gr.Markdown(
            "# Дубляж видео с YouTube\n"
            "Вставьте ссылку на английское видео — получите его с русской озвучкой, субтитрами и текстом.",
            elem_id="dub-title",
        )
        url = gr.Textbox(
            label="Ссылка на видео",
            placeholder="https://www.youtube.com/watch?v=…",
            elem_id="dub-url",
            autofocus=True,
        )
        voice = gr.Radio(list(VOICE_CHOICES), value="Мужской голос", label="Голос озвучки")
        go = gr.Button("Озвучить по-русски", variant="primary", size="lg", elem_id="dub-go")
        status = gr.Markdown(elem_id="dub-status")

        video = gr.Video(label="Видео на русском", interactive=False, height=420, visible=False)
        with gr.Row():
            dl_video = gr.DownloadButton("Скачать видео", visible=False, variant="primary")
            dl_srt = gr.DownloadButton("Субтитры (.srt)", visible=False)
            dl_txt = gr.DownloadButton("Текст на русском", visible=False)
            dl_bi = gr.DownloadButton("Текст EN + RU", visible=False)

        with gr.Accordion("Ранее озвученные видео", open=False):
            history = gr.Dropdown(choices=previous_results(settings), label="Выберите видео", value=None)

        with gr.Accordion("Как пользоваться", open=False):
            gr.Markdown(HELP)

        outputs = [status, video, dl_video, dl_srt, dl_txt, dl_bi]
        go.click(dub, inputs=[url, voice], outputs=[*outputs, history])
        url.submit(dub, inputs=[url, voice], outputs=[*outputs, history])
        history.change(open_previous, inputs=history, outputs=outputs)

    return ui


def main() -> None:
    settings = load_settings()
    ui = build_ui(settings)
    ui.queue(default_concurrency_limit=1).launch(
        server_name=os.environ.get("DUBBER_HOST", "127.0.0.1"),
        server_port=int(os.environ.get("DUBBER_PORT", "7860")),
        inbrowser=os.environ.get("DUBBER_NO_BROWSER") is None,
        allowed_paths=[str(settings.output_dir)],
        theme=make_theme(),
        css=CSS,
        head=HEAD,
        footer_links=[],
    )


if __name__ == "__main__":
    main()
