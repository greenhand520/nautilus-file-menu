import os
import re
import shlex
import subprocess

from gi.repository import Gio

import translation
from .file_utils import uri_to_path as _uri_to_path, find_terminal
from .notify import logger, notify

_EXEC_FIELD_CODE_RE = re.compile(r'%[fFuUdDnNickvm]')

# MIME types that can be run directly as admin (not scripts)
_ADMIN_RUNNABLE_MIMES = frozenset({
    "application/x-executable",
    "application/x-sharedlib",
    "application/x-pie-executable",
    "text/x-shellscript",
    "text/x-python"
})


def _find_python():
    """Find a usable python3 interpreter path."""
    for name in ("python3", "python"):
        path = subprocess.run(
            ["which", name], capture_output=True, text=True
        ).stdout.strip()
        if path:
            return path
    return None


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
    def __init__(self, config, terminal_ops=None):
        self.config = config
        self.terminal_ops = terminal_ops

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

    def run_as_admin(self, menu, files):
        """Run script or executable with admin privileges in a terminal with sudo."""
        terminal_prefix = find_terminal(self.terminal_ops)
        if not terminal_prefix:
            logger.warning("No terminal emulator found for run-as-admin")
            notify(
                translation.gettext("notify_admin_done"),
                translation.gettext("notify_no_terminal"),
            )
            return

        for f in files:
            path = _uri_to_path(f)
            mime_type = f.get_mime_type() or ""
            inner_cmd = self._build_run_command(path, mime_type)
            if not inner_cmd:
                logger.warning("Cannot determine how to run as admin: %s (mime=%s)", path, mime_type)
                continue
            parent_dir = os.path.dirname(path)
            sudo_cmd = " ".join(shlex.quote(a) for a in inner_cmd)
            shell_body = (
                f"cd {shlex.quote(parent_dir)} && "
                f"sudo {sudo_cmd}; "
                f"echo; echo '--- Press Enter to close ---'; read"
            )
            # -e takes separate args: /bin/sh -c "..."
            cmd = terminal_prefix + ["/bin/sh", "-c", shell_body]
            logger.info("Running as admin: %s → %s", path, cmd)
            try:
                subprocess.Popen(
                    cmd, start_new_session=True, close_fds=True,
                    stdin=subprocess.DEVNULL,
                )
            except Exception as e:
                logger.exception("Failed to run as admin: %s, cause: %s", path, e)

    @staticmethod
    def is_runnable_as_admin(file_info):
        """Check if a file is a script or executable suitable for 'run as admin'."""
        if file_info.is_directory():
            return False
        mime = file_info.get_mime_type() or ""
        return (
            mime in _ADMIN_RUNNABLE_MIMES
            or mime.startswith("text/x-python")
            or mime.startswith("text/x-shellscript")
        )

    @staticmethod
    def _build_run_command(path, mime_type):
        """Build a command list to run the file (no sudo prefix).

        Returns a list of args, or [] if the MIME type is not runnable.
        """
        if mime_type.startswith("text/x-python"):
            python = _find_python()
            if python:
                return [python, path]
            logger.warning("No python interpreter found for: %s", path)
            return []
        if mime_type.startswith("text/x-shellscript"):
            return ["/bin/sh", path]
        # application/x-executable, application/x-sharedlib, etc.
        if mime_type in _ADMIN_RUNNABLE_MIMES:
            return [path]
        return []
