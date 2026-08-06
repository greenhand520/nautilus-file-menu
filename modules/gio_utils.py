import errno
import os
import shutil
from collections import defaultdict
from pathlib import Path

from gi import require_version

require_version('Gtk', '4.0')
from gi.repository import Gio

from .notify import logger


def group_paths_by_parent(paths):
    """Group filesystem paths by parent directory, preserving input order."""
    groups = defaultdict(list)
    for path in paths:
        groups[str(Path(path).parent)].append(path)
    return dict(groups)


def _move_or_replace(src_path, dst_path):
    """Finalize one output without silently losing it on cross-device moves."""
    try:
        parent = os.path.dirname(dst_path)
        if parent:
            os.makedirs(parent, exist_ok=True)
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


def finalize_outputs(records, check_smaller=False):
    """Finalize explicitly mapped temporary outputs.

    ``records`` contains ``(temporary_path, output_path, original_path)``.
    Only files present in the records are considered, which prevents stale or
    concurrent temporary files from being moved into the user's directory.
    """
    results = []
    for temp_path, output_path, original_path in records:
        if not os.path.isfile(temp_path):
            continue

        if check_smaller and os.path.isfile(original_path):
            try:
                output_size = os.path.getsize(temp_path)
                original_size = os.path.getsize(original_path)
            except OSError as exc:
                logger.warning("failed to compare %s and %s: %s",
                               temp_path, original_path, exc)
                continue

            if output_size >= original_size:
                logger.info("output not smaller, skipped: %s", temp_path)
                try:
                    os.unlink(temp_path)
                except OSError:
                    logger.warning("failed to remove skipped output: %s", temp_path)
                continue

        if _move_or_replace(temp_path, output_path):
            results.append(output_path)

    return results


def gio_move(src_path, dst_path):
    """Move file/directory, preferring an atomic same-filesystem operation."""
    if _move_or_replace(src_path, dst_path):
        return

    try:
        src = Gio.File.new_for_path(src_path)
        dst = Gio.File.new_for_path(dst_path)
        src.move(dst, Gio.FileCopyFlags.OVERWRITE, None, None, None)
    except Exception as e:
        logger.exception("gio_move: failed to move %s to %s, cause: %s",
                         src_path, dst_path, e)


def move_from_temp(temp_dir, src_dir, suffix, check_smaller=False):
    """Compatibility wrapper for legacy callers.

    New batch code should use :func:`finalize_outputs` with explicit records.
    """
    records = []
    try:
        entries = os.listdir(temp_dir)
    except OSError as exc:
        logger.warning("move_from_temp: cannot list %s: %s", temp_dir, exc)
        return records

    for filename in entries:
        src = os.path.join(temp_dir, filename)
        if not os.path.isfile(src):
            continue

        name, ext = os.path.splitext(filename)
        dst = os.path.join(src_dir, f"{name}{suffix}{ext}")
        original_name = name[:-len(suffix)] if suffix and name.endswith(suffix) else name
        original = os.path.join(src_dir, f"{original_name}{ext}")
        records.append((src, dst, original))

    return finalize_outputs(records, check_smaller=check_smaller)


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
