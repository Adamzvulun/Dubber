# Dubber 🎙️ — any YouTube video → a dub in your language

Paste a YouTube link (speech in **any language**, even several in one video), pick one of **12 dub languages**
(Russian by default; English, Hebrew, Ukrainian, Spanish, French, German, Italian, Portuguese, Arabic, Chinese,
Japanese) and get back:
- **the same video with a voice-over** (original audio kept quietly underneath, and as a 2nd selectable track),
- **subtitles** in the dub language (`.srt`, also embedded in the MP4),
- **a transcript**, plus a bilingual original + translation transcript for studying.

Made for people who learn from videos in other languages. Runs on your own PC, free by default.

**Инструкция на русском:** [Как установить и пользоваться](#ru) · **מדריך בעברית:** [התקנה ושימוש](#he) ·
**Developers:** [How it works](#how-it-works)

---

<a id="ru"></a>
## 🇷🇺 «Дубляж видео» — как установить и пользоваться

Программа озвучивает видео с YouTube (или видеофайл с компьютера) на русском или одном из 12 языков. Она работает
на вашем компьютере с Windows и бесплатна. Нужен интернет.

### Установка (один раз, около 15–20 минут)

1. **Скачайте программу.** Нажмите на эту ссылку:
   **[⬇ Скачать «Дубляж видео»](https://github.com/Adamzvulun/Dubber/archive/refs/heads/main.zip)**.
   Скачается файл `Dubber-main.zip` (обычно он попадает в папку «Загрузки»).
2. **Распакуйте его.** Откройте папку «Загрузки», нажмите на файл `Dubber-main.zip` **правой** кнопкой мыши и
   выберите **«Извлечь все…»**. В окне можно выбрать папку, например «Документы», затем нажмите **«Извлечь»**.
   Появится папка `Dubber-main` — это и есть программа. Не удаляйте её.
3. **Запустите установку.** Откройте папку `Dubber-main` и дважды щёлкните файл **`Start Dubber`**.
4. **Если Windows предупреждает** (так бывает с файлами из интернета):
   - синее окно «Windows защитила ваш компьютер» → нажмите **«Подробнее»** → **«Выполнить в любом случае»**;
   - окно «Открыть файл — предупреждение системы безопасности» → **«Запустить»**;
   - вопрос «Разрешить этому приложению вносить изменения?» → **«Да»** (это устанавливаются Python и ffmpeg).
5. **Подождите.** Откроется чёрное окно, программа сама скачает и установит всё нужное. В первый раз это
   10–15 минут, строки в окне будут меняться. **Не закрывайте окно.**
6. **Готово.** Сайт программы откроется в браузере сам, а на рабочем столе появится значок **«Дубляж видео»**
   (синий квадрат с белой буквой D).

### Как пользоваться

1. Дважды щёлкните значок **«Дубляж видео»** на рабочем столе. Откроется чёрное окно (оно должно оставаться
   открытым, пока вы пользуетесь программой — его можно свернуть) и сайт в браузере.
2. На YouTube откройте видео, скопируйте его адрес из адресной строки браузера (**Ctrl+C**) и вставьте в большое поле
   на сайте (**Ctrl+V**).
   - Можно вставить **несколько ссылок** — каждую с новой строки (**Shift+Enter**). Они озвучатся по очереди.
   - Ссылка на **плейлист** озвучит все его видео.
   - Видео **с компьютера**: нажмите «выберите видеофайл на компьютере» или перетащите файл на поле.
3. Выберите **язык озвучки** и **голос** (мужской или женский) и нажмите **«Озвучить»**.
4. Подождите: видео на 10 минут обычно готово за 5–10 минут. Страницу можно закрыть — работа продолжится.
5. Нажмите **«Смотреть»**. Рядом с видео — текст перевода. Кнопки под видео сохраняют видео, субтитры и текст на
   компьютер.
6. Все готовые видео — в разделе **«Библиотека»** (вверху страницы).

### Как закрыть программу
Закройте чёрное окно «Дубляж видео» (крестик в углу). В следующий раз — снова значок на рабочем столе.

### Обновления
Программа обновляется **сама** при запуске. После обновления на странице появится «Что нового». Ничего скачивать не
нужно.

### Если что-то не так
| Что случилось | Что сделать |
|---|---|
| Нет значка на рабочем столе | Откройте папку `Dubber-main` и дважды щёлкните `Start Dubber`. |
| Сайт не открывается | Проверьте, что чёрное окно открыто. Откройте в браузере адрес `http://127.0.0.1:7860` |
| «Не удалось скачать видео» | Проверьте ссылку и интернет. Закройте чёрное окно и запустите программу снова. |
| Окно пишет «Дубляж уже запущен» | Где-то открыто ещё одно чёрное окно — закройте его и запустите снова. |

Подробная инструкция (перевод через Claude, глоссарий, место на диске и другое): [`docs/README.ru.md`](docs/README.ru.md).

---

<a id="he"></a>
<div dir="rtl" lang="he">

## 🇮🇱 «Дубляж видео» — מדריך התקנה ושימוש

התוכנה מדבבת סרטוני YouTube (או קובץ וידאו מהמחשב) לרוסית או לאחת מ-12 שפות, כולל עברית. היא פועלת על המחשב
שלכם עם Windows, והיא בחינם. צריך חיבור לאינטרנט.

### התקנה (פעם אחת, כ-15–20 דקות)

1. **הורידו את התוכנה.** לחצו על הקישור:
   **[⬇ הורדת התוכנה](https://github.com/Adamzvulun/Dubber/archive/refs/heads/main.zip)**.
   יירד קובץ בשם `Dubber-main.zip` (בדרך כלל לתיקייה "הורדות").
2. **חלצו את הקובץ.** פתחו את התיקייה "הורדות", לחצו על `Dubber-main.zip` עם הכפתור **הימני** של העכבר ובחרו
   **"חלץ הכל..."**. אפשר לבחור תיקייה, למשל "מסמכים", ואז ללחוץ **"חלץ"**.
   תיווצר תיקייה בשם `Dubber-main` — זו התוכנה. אל תמחקו אותה.
3. **הפעילו את ההתקנה.** פתחו את התיקייה `Dubber-main` ולחצו פעמיים על הקובץ **`Start Dubber`**.
4. **אם Windows מציג אזהרה** (זה קורה עם קבצים מהאינטרנט):
   - חלון כחול "Windows הגן על המחשב שלך" ← לחצו **"מידע נוסף"** ← **"הפעל בכל זאת"**;
   - חלון "פתיחת קובץ — אזהרת אבטחה" ← **"הפעל"**;
   - שאלה "האם לאפשר לאפליקציה זו לבצע שינויים?" ← **"כן"** (מותקנים Python ו-ffmpeg).
5. **המתינו.** ייפתח חלון שחור, והתוכנה תוריד ותתקין לבד את כל מה שצריך. בפעם הראשונה זה לוקח 10–15 דקות,
   והשורות בחלון יתחלפו. **אל תסגרו את החלון.**
6. **זהו.** אתר התוכנה ייפתח בדפדפן לבד, ועל שולחן העבודה יופיע סמל בשם **«Дубляж видео»** (ריבוע כחול עם האות
   D לבנה).

### איך משתמשים

1. לחצו פעמיים על הסמל **«Дубляж видео»** בשולחן העבודה. ייפתחו חלון שחור (הוא צריך להישאר פתוח כל זמן העבודה —
   אפשר למזער אותו) והאתר בדפדפן.
2. **האתר כתוב ברוסית ובאנגלית.** לחצו על **EN** בפינה העליונה כדי לעבור לאנגלית.
3. ב-YouTube פתחו סרטון, העתיקו את הכתובת שלו משורת הכתובת של הדפדפן (**Ctrl+C**) והדביקו בשדה הגדול באתר
   (**Ctrl+V**).
   - אפשר להדביק **כמה קישורים** — כל אחד בשורה חדשה (**Shift+Enter**). הם ידובבו אחד אחרי השני.
   - קישור ל**פלייליסט** ידבב את כל הסרטונים שבו.
   - סרטון **מהמחשב**: לחצו "choose a video file on this computer" או גררו את הקובץ אל השדה.
4. בחרו **שפת דיבוב** (Dub language — למשל Hebrew) ו**קול** (Male — גבר, Female — אישה), ולחצו **"Dub video"**.
5. המתינו: סרטון של 10 דקות מוכן בדרך כלל תוך 5–10 דקות. אפשר לסגור את הדף — העבודה תימשך.
6. לחצו **"Watch"** כדי לצפות. ליד הסרטון מופיע התרגום, והכפתורים מתחת לסרטון שומרים את הסרטון, הכתוביות
   והטקסט במחשב.
7. כל הסרטונים המוכנים נמצאים ב-**"Library"** (בראש הדף).

### איך סוגרים את התוכנה
סגרו את החלון השחור «Дубляж видео» (ה-X בפינה). בפעם הבאה — שוב הסמל בשולחן העבודה.

### עדכונים
התוכנה **מתעדכנת לבד** בכל הפעלה. אחרי עדכון יופיע בדף "What's new". אין צורך להוריד שום דבר.

### אם משהו לא עובד
| מה קרה | מה לעשות |
|---|---|
| אין סמל בשולחן העבודה | פתחו את התיקייה `Dubber-main` ולחצו פעמיים על `Start Dubber`. |
| האתר לא נפתח | ודאו שהחלון השחור פתוח. פתחו בדפדפן את הכתובת `http://127.0.0.1:7860` |
| "Couldn't download the video" | בדקו את הקישור ואת האינטרנט. סגרו את החלון השחור והפעילו את התוכנה שוב. |
| החלון כותב שהתוכנה כבר פועלת | חלון שחור נוסף פתוח איפשהו — סגרו אותו והפעילו שוב. |

</div>

---

<a id="how-it-works"></a>

![Dubber website](docs/images/site-home-light.png)

The website has a Russian/English interface switch; a running dub can be cancelled (and resumed later).
Full Russian user guide: [`docs/README.ru.md`](docs/README.ru.md). Design: [`docs/DESIGN.md`](docs/DESIGN.md).

## How it works
```
YouTube ─yt-dlp─► video ─faster-whisper (language per stretch of speech)─► text ─Google/Claude─► translation
        ─edge-tts─► voice in the dub language ─align─► timed track ─ffmpeg─► dubbed MP4 + SRT + TXT
        (optional: Demucs removes the original voice, keeping music and sounds under the dub)
```
Details and tool research: [`docs/RESEARCH.md`](docs/RESEARCH.md). Why each choice: [`docs/DECISIONS.md`](docs/DECISIONS.md).

## Install
Needs **Python 3.10+**, **ffmpeg** and an internet connection.

**Windows:** double-click **`Start Dubber.cmd`**. The first run installs Python and ffmpeg (winget) and the
components (10–15 min, log in `install.log`), puts a «Дубляж видео» shortcut with the program's icon on the desktop
and in the Start menu, and starts the program; later runs just start it (`scripts/windows/dubber.ps1`).

**macOS / Linux:**
```bash
./scripts/install.sh     # creates .venv, installs everything
./scripts/start.sh       # opens http://127.0.0.1:7860
```

Command line instead of the web page:
```bash
.venv/bin/python -m dubber.cli "https://www.youtube.com/watch?v=VIDEO_ID"            # → Russian
.venv/bin/python -m dubber.cli --lang he --voice female "https://youtu.be/VIDEO_ID"   # → Hebrew, female voice
```
Results go to `output/<video id>--<lang>-<hash>/` (one folder per dub) and appear in the website's library. The
website also takes several links at once, YouTube playlists, and video files from this computer.

## Updating
Automatic since 0.5.0: at start (and with the site's «Установить обновление» button) the program installs a newer
`main` from GitHub, keeping `work/`, `output/`, `.env` and `glossary.txt` (`dubber/update.py`, ADR-024); after an
update the page shows "What's new" once (`dubber/changelog.json`). By hand: extract the `main` ZIP over the folder and
double-click `Start Dubber.cmd`. The page footer shows the version.

## Settings (optional, in a `.env` file next to this README)
The website's **Settings** page (gear icon) manages translation: the Claude API key (checked, then saved to `.env`;
only its last 4 characters are ever shown), the model, Claude on/off, and a glossary (`glossary.txt`, one
"term = translation" per line, followed by Claude). Both files are git-ignored.

| Variable | Default | Meaning |
|---|---|---|
| `DUBBER_WHISPER_MODEL` | `small` | `tiny`/`base` faster; `large-v3-turbo` more accurate on French/Hebrew but ~1.5× slower and it skipped English lines in tests (RESEARCH "Session 3") |
| `DUBBER_VOICE` | `ru-RU-DmitryNeural` | or `ru-RU-SvetlanaNeural` |
| `DUBBER_TRANSLATOR` | `auto` | `auto` = Claude if a key is set, else free Google; `google` (free only), `claude`, `offline` (NLLB on this PC). Fallback chain: Claude → Google → offline |
| `ANTHROPIC_API_KEY` | – | enables Claude translation (paid, ~$0.09 per 10 min of speech on Opus 5.5) — normally entered on the website's **Settings** page, which saves it here |
| `DUBBER_CLAUDE_MODEL` | `claude-opus-5-5` | `claude-opus-5-5`, `claude-sonnet-5-5` or `claude-haiku-5-5` (also on the Settings page) |
| `DUBBER_COOKIES` | – | path to a `cookies.txt` exported from your browser, if YouTube says "confirm you're not a bot" |
| `DUBBER_LANG` | `ru` | default dub language (`ru en he uk es fr de it pt ar zh ja`) |
| `DUBBER_KEEP_BACKGROUND` | `1` | `0` = only the dubbed voice, without the original sound underneath (also a switch on the website) |
| `DUBBER_REMOVE_VOICE` | `0` | `1` = keep music and sounds under the dub but remove the speaker's voice (Demucs, ≈ +5 min per 10 min of video on 4 cores; also a switch on the website, CLI `--remove-voice`) |
| `DUBBER_MUSIC_VOLUME` | `0.7` | loudness of that voice-free background (lowered further while the dub speaks) |
| `DUBBER_MAX_SPEEDUP` | `1.6` | fastest the dub voice may speak (1.6 = 60% faster than natural) to keep the speaker's timing |
| `DUBBER_ORIGINAL_VOLUME` | `0.15` | loudness of the original under the dub |

## Development
```bash
.venv/bin/ruff check . && .venv/bin/pytest
```
Tests run offline (network services are stubbed). Project docs: [`docs/PLAN.md`](docs/PLAN.md) (roadmap),
[`docs/PROGRESS.md`](docs/PROGRESS.md) (log), [`kanban/`](kanban) (tasks), [`docs/SKILLS.md`](docs/SKILLS.md) (Claude skills),
[`CLAUDE.md`](CLAUDE.md) (rules for Claude Code sessions).

## Note
For personal, educational use. Respect YouTube's terms and creators' rights; don't redistribute dubbed copies.
