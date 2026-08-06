import os

from gi import require_version

require_version('Gtk', '4.0')
from gi.repository import Gio

from .notify import logger


def gio_move(src_path, dst_path):
    """Move file/directory. Uses os.rename first (fast, same-filesystem),
    falls back to Gio, then shutil for cross-filesystem."""
    try:
        os.rename(src_path, dst_path)
    except OSError:
        try:
            src = Gio.File.new_for_path(src_path)
            dst = Gio.File.new_for_path(dst_path)
            src.move(dst, Gio.FileCopyFlags.OVERWRITE, None, None, None)
        except Exception as e:
            logger.exception("gio_move: failed to move %s to %s, cause: %s",
                             src_path, dst_path, e)


def gio_delete(path):
    """Delete a file or empty directory using Gio.File."""
    try:
        Gio.File.new_for_path(path).delete(None)
    except Exception as e:
        logger.exception("gio_delete: failed to delete %s, cause: %s", path, e)


def gio_make_directories(path):
    """Make directories using Gio.File.make_directories."""
    try:
        Gio.File.new_for_path(path).make_directory_with_parents(None)
    except Exception as e:
        logger.exception("gio_make_directories: failed to make directories %s, cause: %s", path, e)
