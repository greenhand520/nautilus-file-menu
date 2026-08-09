import os
import sys
import logging
from gi.repository import Gio

# Log file lives next to the extension, so uninstall cleans it up
LOG_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG_FILE = os.path.join(LOG_DIR, "extension.log")

logger = logging.getLogger("nautilus-file-menu")
logger.setLevel(logging.WARNING)

# Append across restarts; guard so module re-imports don't stack handlers.
_file_handler = None
if not logger.handlers:
    try:
        _file_handler = logging.FileHandler(LOG_FILE, mode="a", encoding="utf-8")
        _file_handler.setLevel(logging.WARNING)
        _file_handler.setFormatter(logging.Formatter(
            "%(asctime)s [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
        ))
        logger.addHandler(_file_handler)
    except OSError as e:
        # e.g. system-wide install with a non-writable directory: keep the
        # logger usable instead of failing the extension's import.
        _file_handler = None
        print(f"nautilus-file-menu: cannot open log file {LOG_FILE}: {e}", file=sys.stderr)

# Valid levels: DEBUG, INFO, WARNING, ERROR, CRITICAL
_LEVEL_MAP = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL,
}


def set_log_level(level_name):
    """Set log level from a string like 'DEBUG', 'INFO', 'WARNING', 'ERROR'."""
    level = _LEVEL_MAP.get(level_name.upper())
    if level is not None:
        logger.setLevel(level)
        if _file_handler is not None:
            _file_handler.setLevel(level)
    else:
        logger.warning("Unknown log level: %s, keeping current level", level_name)


def notify(title, body=""):
    """Send a desktop notification via the Nautilus application."""
    try:
        app = Gio.Application.get_default()
        if app is None:
            logger.warning("notify: no default application, cannot send notification")
            return
        notification = Gio.Notification.new(title)
        if body:
            notification.set_body(body)
        notification.set_priority(Gio.NotificationPriority.NORMAL)
        app.send_notification(None, notification)
    except Exception as e_:
        logger.exception("Failed to send notification, cause %s", e_)
