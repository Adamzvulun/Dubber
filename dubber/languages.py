"""The languages Dubber can dub into, and helpers for any detected source language.

One table drives everything language-specific: Edge voices, the Google Translate code, ffmpeg's ISO 639-2 stream tag,
and names shown in the website (Russian and English UI). Voices verified against Edge's live voice list (2026-10-16).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

DEFAULT = "ru"
# Unicode ranges (for a regex character class) that a translation into that script must contain.
CYRILLIC, HEBREW, ARABIC = "\u0400-\u04ff", "\u0590-\u05ff", "\u0600-\u06ff"
CJK, KANA = "\u4e00-\u9fff", "\u3040-\u30ff"


@dataclass(frozen=True)
class Language:
    code: str  # ISO 639-1, also used in file names (subtitles_he.vtt)
    name_ru: str
    name_en: str
    native: str  # the language's own name, shown next to the UI-language name
    male: str  # Edge voice
    female: str  # Edge voice
    google: str  # Google Translate code
    iso3: str  # ffmpeg stream tag (ISO 639-2/B)
    nllb: str  # NLLB-200 code (offline translator)
    script: str = ""  # Unicode range a correct translation must contain ("" = Latin, not checked)
    rtl: bool = False

    def voice(self, gender: str) -> str:
        return self.female if gender == "female" else self.male

    def public(self) -> dict:
        return asdict(self)


LANGUAGES: dict[str, Language] = {
    lang.code: lang
    for lang in [
        Language("ru", "Русский", "Russian", "Русский", "ru-RU-DmitryNeural", "ru-RU-SvetlanaNeural", "ru", "rus",
                 "rus_Cyrl", CYRILLIC),
        Language("en", "Английский", "English", "English", "en-US-AndrewNeural", "en-US-AvaNeural", "en", "eng",
                 "eng_Latn"),
        Language("he", "Иврит", "Hebrew", "עברית", "he-IL-AvriNeural", "he-IL-HilaNeural", "iw", "heb", "heb_Hebr",
                 HEBREW, rtl=True),
        Language("uk", "Украинский", "Ukrainian", "Українська", "uk-UA-OstapNeural", "uk-UA-PolinaNeural", "uk", "ukr",
                 "ukr_Cyrl", CYRILLIC),
        Language("es", "Испанский", "Spanish", "Español", "es-ES-AlvaroNeural", "es-ES-ElviraNeural", "es", "spa",
                 "spa_Latn"),
        Language("fr", "Французский", "French", "Français", "fr-FR-HenriNeural", "fr-FR-DeniseNeural", "fr", "fre",
                 "fra_Latn"),
        Language("de", "Немецкий", "German", "Deutsch", "de-DE-ConradNeural", "de-DE-KatjaNeural", "de", "ger",
                 "deu_Latn"),
        Language("it", "Итальянский", "Italian", "Italiano", "it-IT-DiegoNeural", "it-IT-ElsaNeural", "it", "ita",
                 "ita_Latn"),
        Language("pt", "Португальский", "Portuguese", "Português", "pt-BR-AntonioNeural", "pt-BR-FranciscaNeural",
                 "pt", "por", "por_Latn"),
        Language("ar", "Арабский", "Arabic", "العربية", "ar-SA-HamedNeural", "ar-SA-ZariyahNeural", "ar", "ara",
                 "arb_Arab", ARABIC, rtl=True),
        Language("zh", "Китайский", "Chinese", "中文", "zh-CN-YunxiNeural", "zh-CN-XiaoxiaoNeural", "zh-CN", "chi",
                 "zho_Hans", CJK),
        Language("ja", "Японский", "Japanese", "日本語", "ja-JP-KeitaNeural", "ja-JP-NanamiNeural", "ja", "jpn",
                 "jpn_Jpan", CJK + KANA),
    ]
}

# Characters per second the dub voice says at its natural speed (estimates from Edge voices, spaces included). Used to
# ask a translator for lines that fit their time slot (`translate.ClaudeBackend`); 14 when unknown.
_CPS = {"ru": 14.0, "uk": 14.0, "en": 14.0, "es": 15.0, "fr": 15.0, "it": 15.0, "pt": 15.0, "de": 14.0,
        "he": 12.0, "ar": 12.0, "zh": 5.0, "ja": 7.0}


def chars_per_second(code: str | None) -> float:
    return _CPS.get((code or "").lower(), 14.0)


# Whisper language code (any spoken language) → NLLB-200 code, for the offline translator's source side.
_NLLB = {code: lang.nllb for code, lang in LANGUAGES.items()} | {
    "pl": "pol_Latn", "nl": "nld_Latn", "tr": "tur_Latn", "ko": "kor_Hang", "hi": "hin_Deva", "sv": "swe_Latn",
    "cs": "ces_Latn", "el": "ell_Grek", "fi": "fin_Latn", "da": "dan_Latn", "no": "nob_Latn", "nn": "nno_Latn",
    "hu": "hun_Latn", "ro": "ron_Latn", "bg": "bul_Cyrl", "be": "bel_Cyrl", "kk": "kaz_Cyrl", "fa": "pes_Arab",
    "id": "ind_Latn", "ms": "zsm_Latn", "vi": "vie_Latn", "th": "tha_Thai", "yi": "ydd_Hebr", "sr": "srp_Cyrl",
    "hr": "hrv_Latn", "sk": "slk_Latn", "sl": "slv_Latn", "lt": "lit_Latn", "lv": "lvs_Latn", "et": "est_Latn",
    "ka": "kat_Geor", "hy": "hye_Armn", "az": "azj_Latn", "uz": "uzn_Latn", "ur": "urd_Arab", "bn": "ben_Beng",
    "ta": "tam_Taml", "ca": "cat_Latn", "gl": "glg_Latn", "eu": "eus_Latn", "sw": "swh_Latn", "tl": "tgl_Latn",
}
# Whisper code → Google code where they differ.
_GOOGLE = {code: lang.google for code, lang in LANGUAGES.items()} | {"jw": "jw", "yi": "yi"}


def nllb_code(code: str | None) -> str:
    """NLLB code for a Whisper language code; unknown → English (the most common source)."""
    return _NLLB.get((code or "").lower(), "eng_Latn")


def google_code(code: str | None) -> str:
    """Google Translate source code for a Whisper language code ("auto" when unknown)."""
    code = (code or "").lower()
    return _GOOGLE.get(code, code or "auto")


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
