from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Optional


@dataclass(frozen=True)
class PromptPair:
    system: str
    user: str


_BASE_DIR = Path(__file__).resolve().parent / "i18n"
_DEFAULT_LOCALE = "zh-CN"
_FALLBACK_LOCALE = "en"


def normalize_locale(locale: Optional[str]) -> str:
    raw = (locale or "").strip()
    if not raw:
        return _DEFAULT_LOCALE

    lowered = raw.replace("_", "-").lower()

    if lowered == "zh-cn" or lowered.startswith("zh"):
        return "zh-CN"
    if lowered == "en" or lowered.startswith("en-"):
        return "en"
    if lowered == "es" or lowered.startswith("es-"):
        return "es"
    if lowered == "fr" or lowered.startswith("fr-"):
        return "fr"
    if lowered == "ar" or lowered.startswith("ar-"):
        return "ar"
    if lowered == "ja" or lowered.startswith("ja-"):
        return "ja"

    return _FALLBACK_LOCALE


def _template_path(locale: str, name: str) -> Path:
    return _BASE_DIR / locale / name


@lru_cache(maxsize=None)
def _read_template(locale: str, name: str) -> str:
    path = _template_path(locale, name)
    if not path.exists():
        raise FileNotFoundError(f"Missing prompt template: {path}")
    return path.read_text(encoding="utf-8")


def load_template(locale: Optional[str], name: str, *, fallback_locale: str = _FALLBACK_LOCALE) -> str:
    loc = normalize_locale(locale)
    try:
        return _read_template(loc, name)
    except FileNotFoundError:
        return _read_template(fallback_locale, name)


def get_prompts(kind: str, locale: Optional[str]) -> PromptPair:
    system = load_template(locale, f"{kind}_system.txt")
    user = load_template(locale, f"{kind}_user.txt")
    return PromptPair(system=system, user=user)


def get_scriptwriter_prompts(locale: Optional[str]) -> PromptPair:
    return get_prompts("scriptwriter", locale)


def get_segmenter_prompts(locale: Optional[str]) -> PromptPair:
    return get_prompts("segmenter", locale)


def get_analyzer_prompts(locale: Optional[str]) -> PromptPair:
    return get_prompts("analyzer", locale)
