import gettext as _gettext
import locale
import logging
import os

DOMAIN = "nautilus-file-menu"
_LOCALE_DIR = os.path.join(os.path.dirname(__file__), "po")
if not os.path.isdir(_LOCALE_DIR):
    _LOCALE_DIR = os.path.join(os.path.dirname(__file__), "locale")


_translator = None


_logger = logging.getLogger("nautilus-file-menu")


def _setup(lang_code="auto"):
    """Initialize gettext and return the translation function."""
    if lang_code and lang_code != "auto":
        languages = [lang_code]
        resolved = lang_code
    else:
        try:
            sys_locale = locale.getlocale()[0] or os.environ.get("LANG", "en")
            languages = [sys_locale]
            resolved = sys_locale
        except (AttributeError, ValueError):
            languages = ["en"]
            resolved = "en"

    t = _gettext.translation(DOMAIN, _LOCALE_DIR, languages=languages, fallback=True)
    if type(t) is _gettext.NullTranslations:
        _logger.warning("No translation found for language '%s', using fallback", resolved)
    else:
        _logger.debug("Translation loaded: language=%s, locale_dir=%s", resolved, _LOCALE_DIR)
    return t.gettext


def select_language(lang_code="auto"):
    """Re-initialize translation with a specific language."""
    global _translator
    _translator = _setup(lang_code)


def gettext(msgid: str) -> str:
    """Translate a message ID."""
    global _translator
    if _translator is None:
        _translator = _setup()
    return _translator(msgid)


# Initialize on import
_translator = _setup()
