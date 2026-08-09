import re
import shlex
import subprocess

from gi.repository import Gio

import translation
from .notify import logger, notify

_EXEC_FIELD_CODE_RE = re.compile(r'%[fFuUdDnNickvm]')


def _to_admin_uri(uri):
    """Convert a file:// URI to the equivalent admin:// URI (scheme only)."""
    if not uri.startswith("file://"):
        return uri
    # count=1: only the leading scheme, never an embedded "file://" in the path.
    return uri.replace("file://", "admin://", 1)


def _strip_exec_codes(cmdline):
    """Strip desktop-entry field codes (%f, %F, %u, %U, ...) from a command line."""
    return _EXEC_FIELD_CODE_RE.sub('', cmdline).strip()


class AdminOps:
    def __init__(self, config):
        self.config = config

    def open_as_admin(self, menu, files):
        """Open folder(s) in Nautilus with admin privileges."""
        for f in files:
            admin_uri = _to_admin_uri(f.get_uri())
            try:
                subprocess.Popen(["nautilus", admin_uri])
            except Exception as e:
                logger.exception("Failed to open as admin: %s, cause: %s", admin_uri, e)

    def edit_as_admin(self, menu, files):
        """Open file(s) in the default text editor with admin privileges."""
        for f in files:
            uri = f.get_uri()
            admin_uri = _to_admin_uri(uri)
            content_type = Gio.content_type_guess(uri, None)
            mime_type = content_type[0] if content_type else "text/plain"

            app_info = self._get_default_editor(mime_type)
            if app_info is None:
                logger.warning("No text editor found for: %s", uri)
                notify(
                    translation.gettext("notify_admin_done"),
                    translation.gettext("notify_no_editor"),
                )
                continue

            editor_args = self._editor_command(app_info)
            if not editor_args:
                notify(
                    translation.gettext("notify_admin_done"),
                    translation.gettext("notify_no_editor"),
                )
                continue

            logger.info("Editing as admin: %s → %s %s", uri, editor_args, admin_uri)
            try:
                subprocess.Popen(editor_args + [admin_uri])
            except Exception as e:
                logger.exception("Failed to edit as admin: %s, cause: %s", admin_uri, e)

    def _get_default_editor(self, mime_type):
        """Find the default editor AppInfo for a MIME type, falling back to text/plain."""
        try:
            app_info = Gio.app_info_get_default_for_type(mime_type, True)
        except Exception as e:
            logger.exception("Failed to get default app info for %s, cause: %s", mime_type, e)
            app_info = None
        if app_info:
            return app_info

        try:
            return Gio.app_info_get_default_for_type("text/plain", True)
        except Exception as e:
            logger.exception("Failed to get default app info for text/plain, cause: %s", e)
            return None

    def _editor_command(self, app_info):
        """Build a command list for the editor, preserving Exec arguments."""
        cmdline = None
        try:
            cmdline = app_info.get_commandline()
        except Exception:
            pass
        if not cmdline:
            try:
                cmdline = app_info.get_executable()
            except Exception:
                cmdline = None
        if not cmdline:
            return []

        cmdline = _strip_exec_codes(cmdline)
        try:
            args = shlex.split(cmdline)
        except ValueError:
            args = cmdline.split()
        return args or [cmdline]
