import errno
import os
import shutil
import subprocess
from collections import defaultdict
from pathlib import Path
from urllib.parse import urlparse, unquote

from gi import require_version

require_version('Gtk', '4.0')
from gi.repository import Gio

from .notify import logger

# Fallback terminal emulators (used when terminal_ops has none)
FALLBACK_TERMINALS = [
    "x-terminal-emulator", "ptyxis", "kgx", "gnome-terminal", "kitty", "alacritty",
]


def find_terminal(terminal_ops=None):
    """Return a terminal prefix list (e.g. ['ptyxis', '-e']) or None.

    The returned list is prepended to the command to launch.
    ``{path}`` is replaced with the home directory.
    """
    if terminal_ops:
        terminals = terminal_ops.get_terminals()
        if terminals:
            _name, cfg = terminals[0]
            home = os.path.expanduser("~")
            if cfg.get("_flatpak"):
                flatpak = cfg.get("flatpak", [])
                if flatpak:
                    args = ["flatpak", "run"] + [a.replace("{path}", home) for a in flatpak]
                    return args + ["-e"]
            cmd = cfg.get("cmd", [])
            if cmd:
                return [a.replace("{path}", home) for a in cmd] + ["-e"]

    for term in FALLBACK_TERMINALS:
        found = find_binary(term)
        if found:
            return [found, "-e"]

    return None


def uri_to_path(file):
    """Convert a Nautilus FileInfo URI to an absolute filesystem path."""
    # logger.debug("file url: %s", file.get_activation_uri())
    p = urlparse(file.get_activation_uri())
    if p.netloc in ("", "localhost"):
        # file:///path and admin:///path both map directly to a local absolute
        # path; host-less URIs never need a host prefix.
        return os.path.abspath(unquote(p.path))
    # Remote URIs with a host (e.g. sftp://host/path): prefix the host so the
    # result stays deterministic and never aliases a random local path.
    return os.path.abspath(os.path.join(p.netloc, unquote(p.path).lstrip("/")))


# MIME types allowed for "copy content" (in addition to text/*)
COPY_CONTENT_MIME_TYPES = ["application/x-shellscript", "application/json"]


def is_flatpak_installed(app_id):
    """Check if a Flatpak app is installed."""
    try:
        result = subprocess.run(
            ["flatpak", "info", app_id],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        return result.returncode == 0
    except FileNotFoundError:
        return False


# Standard binary search dirs
_EXTRA_SEARCH_DIRS = [
    os.path.expanduser("~/.local/bin"),
    "/usr/local/bin",
    "/usr/bin",
]


def find_binary(cmd: str) -> str | None:
    """Find a binary, checking shutil.which first, then extra search dirs."""
    found = shutil.which(cmd)
    if found:
        return found
    for d in _EXTRA_SEARCH_DIRS:
        path = os.path.join(d, cmd)
        if os.path.isfile(path) and os.access(path, os.X_OK):
            return path
    return None


def group_paths_by_parent(paths):
    """Group filesystem paths by parent directory, preserving input order."""
    groups = defaultdict(list)
    for path in paths:
        groups[str(Path(path).parent)].append(path)
    return dict(groups)


def _move_or_replace(src_path, dst_path):
    """Rename one path atomically when source and destination share a device.

    Callers are responsible for ensuring that the destination parent exists.
    Avoiding a per-file ``os.makedirs(..., exist_ok=True)`` matters on GVFS,
    FUSE, network, and removable filesystems because it performs redundant
    metadata operations for every item.
    """
    try:
        os.replace(src_path, dst_path)
        return True
    except OSError as exc:
        if exc.errno != errno.EXDEV:
            logger.warning("failed to finalize %s -> %s: %s", src_path, dst_path, exc)
            return False

    try:
        shutil.move(src_path, dst_path)
        return True
    except OSError as exc:
        logger.warning("cross-device move failed %s -> %s: %s", src_path, dst_path, exc)
        return False


def file_move(src_path, dst_path):
    """Move a file/directory and return whether the operation succeeded.

    Same-filesystem moves use ``os.replace`` and therefore only update
    directory metadata. Gio is retained as the cross-device/unsupported
    fallback.
    """
    if _move_or_replace(src_path, dst_path):
        return True

    try:
        src = Gio.File.new_for_path(src_path)
        dst = Gio.File.new_for_path(dst_path)
        src.move(dst, Gio.FileCopyFlags.OVERWRITE, None, None, None)
        return True
    except Exception as e:
        logger.exception("gio_move: failed to move %s to %s, cause: %s",
                         src_path, dst_path, e)
        return False


def file_delete(path):
    """Delete a file or empty directory and return whether it succeeded."""
    try:
        Gio.File.new_for_path(path).delete(None)
        return True
    except Exception as e:
        logger.exception("gio_delete: failed to delete %s, cause: %s", path, e)
        return False


def gio_make_directories(path):
    """Make directories and return whether they exist after the operation."""
    try:
        Gio.File.new_for_path(path).make_directory_with_parents(None)
        return True
    except Exception as e:
        # G_IO_ERROR_EXISTS is a successful end state for this helper.
        if os.path.isdir(path):
            return True
        logger.exception("gio_make_directories: failed to make directories %s, cause: %s", path, e)
        return False
