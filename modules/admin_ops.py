import os
import subprocess

from gi.repository import Gio

from .ide_ops import _get_exclude_mime
from .notify import logger, notify
import translation


def _is_openable_in_editor(file, config):
    """Check if a file can be opened in a text editor (same exclusion as IDE)."""
    mime = file.get_mime_type()
    exclude = _get_exclude_mime(config)
    return not any(mime.startswith(p) for p in exclude)


class AdminOps:
    def __init__(self, config):
        self.config = config

    def open_as_admin(self, menu, files):
        """Open folder(s) in Nautilus with admin privileges."""
        for f in files:
            uri = f.get_uri()
            admin_uri = uri.replace("file://", "admin://")
            try:
                subprocess.Popen(["nautilus", admin_uri])
            except Exception as e:
                logger.exception("Failed to open as admin: %s, cause: %s", admin_uri, e)

    def edit_as_admin(self, menu, files):
        """Open file(s) in the default text editor with admin privileges."""
        for f in files:
            uri = f.get_uri()
            admin_uri = uri.replace("file://", "admin://")
            content_type = Gio.content_type_guess(uri, None)

            # Find default text editor for this MIME type
            try:
                app_info = Gio.app_info_get_default_for_type(content_type[0], True)
                editor = app_info.get_executable() if app_info else None
            except Exception as e:
                logger.exception("Failed to get default app info for content %s, cause: %s", content_type[0], e)
                editor = None

            # Fallback to default text/plain editor
            if not editor:
                try:
                    app_info = Gio.app_info_get_default_for_type("text/plain", True)
                    editor = app_info.get_executable() if app_info else None
                except Exception as e:
                    logger.exception("Failed to get default app info for content text/plain, cause: %s", e)
                    editor = None

            if not editor:
                logger.warning("No text editor found for: %s", uri)
                notify(
                    translation.gettext("notify_admin_done"),
                    translation.gettext("notify_no_editor"),
                )
                continue

            logger.info("Editing as admin: %s → %s %s", uri, editor, admin_uri)
            try:
                subprocess.Popen([editor, admin_uri])
            except Exception as e:
                logger.exception("Failed to edit as admin: %s, cause: %s", admin_uri, e)
