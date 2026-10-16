"""The languages Dubber can dub into, and helpers for any detected source language.

One table drives everything language-specific: Edge voices, the Google Translate code, ffmpeg's ISO 639-2 stream tag,
and names shown in the website (Russian and English UI). Voices verified against Edge's live voice list (2026-10-16).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

DEFAULT = "ru"


@dataclass(frozen=True)
class Language:
    code: str  # ISO 639-1, also used in file names (subtitles_he.vtt)
    name_ru: str
    name_en: str
    native: str  # the language's own name, shown next to the UI-language name
    male: str  # Edge voice
    female: str  # Edge voice
    google: str  # deep-translator / Google Translate code
    iso3: str  # ffmpeg stream tag (ISO 639-2/B)
    rtl: bool = False

    def voice(self, gender: str) -> str:
        return self.female if gender == "female" else self.male

    def public(self) -> dict:
        return asdict(self)


LANGUAGES: dict[str, Language] = {
    lang.code: lang
    for lang in [
        Language("ru", "Русский", "Russian", "Русский", "ru-RU-DmitryNeural", "ru-RU-SvetlanaNeural", "ru", "rus"),
        Language("en", "Английский", "English", "English", "en-US-AndrewNeural", "en-US-AvaNeural", "en", "eng"),
        Language("he", "Иврит", "Hebrew", "עברית", "he-IL-AvriNeural", "he-IL-HilaNeural", "iw", "heb", rtl=True),
        Language("uk", "Украинский", "Ukrainian", "Українська", "uk-UA-OstapNeural", "uk-UA-PolinaNeural", "uk", "ukr"),
        Language("es", "Испанский", "Spanish", "Español", "es-ES-AlvaroNeural", "es-ES-ElviraNeural", "es", "spa"),
        Language("fr", "Французский", "French", "Français", "fr-FR-HenriNeural", "fr-FR-DeniseNeural", "fr", "fre"),
        Language("de", "Немецкий", "German", "Deutsch", "de-DE-ConradNeural", "de-DE-KatjaNeural", "de", "ger"),
        Language("it", "Итальянский", "Italian", "Italiano", "it-IT-DiegoNeural", "it-IT-ElsaNeural", "it", "ita"),
        Language("pt", "Португальский", "Portuguese", "Português", "pt-BR-AntonioNeural", "pt-BR-FranciscaNeural",
                 "pt", "por"),
        Language("ar", "Арабский", "Arabic", "العربية", "ar-SA-HamedNeural", "ar-SA-ZariyahNeural", "ar", "ara",
                 rtl=True),
        Language("zh", "Китайский", "Chinese", "中文", "zh-CN-YunxiNeural", "zh-CN-XiaoxiaoNeural", "zh-CN", "chi"),
        Language("ja", "Японский", "Japanese", "日本語", "ja-JP-KeitaNeural", "ja-JP-NanamiNeural", "ja", "jpn"),
    ]
}

# Whisper language codes (any spoken language) → ISO 639-2 tag for the original audio track.
_ISO3 = {code: lang.iso3 for code, lang in LANGUAGES.items()} | {
    "pl": "pol", "nl": "dut", "tr": "tur", "ko": "kor", "hi": "hin", "sv": "swe", "cs": "cze", "el": "gre",
    "fi": "fin", "da": "dan", "no": "nor", "hu": "hun", "ro": "rum", "bg": "bul", "be": "bel", "kk": "kaz",
    "fa": "per", "id": "ind", "vi": "vie", "th": "tha", "yi": "yid",
}


def get(code: str | None) -> Language:
    """The target language for a code; unknown or empty → Russian (the default)."""
    return LANGUAGES.get((code or DEFAULT).lower(), LANGUAGES[DEFAULT])


def iso3(code: str | None) -> str:
    """ffmpeg language tag for any Whisper language code ("und" when unknown)."""
    return _ISO3.get((code or "").lower(), "und")


def voice_for(code: str, voice: str) -> str:
    """`voice` if it speaks this language, else the language's male voice.

    `voice` may be an Edge voice name (CLI setting) or "male"/"female" (website choice).
    """
    lang = get(code)
    if voice in ("male", "female"):
        return lang.voice(voice)
    return voice if voice in (lang.male, lang.female) else lang.male
