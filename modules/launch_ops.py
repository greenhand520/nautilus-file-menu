import configparser
import os
import re
import shlex
import subprocess

import translation
from .file_utils import uri_to_path as _uri_to_path, find_binary, find_terminal
from .notify import logger, notify


def _is_desktop_file(path):
    return path.endswith(".desktop") and os.path.isfile(path)


def _clean_exec(exec_str):
    """Strip desktop entry codes (%f, %F, %u, %U, etc.) from Exec string."""
    return re.sub(r'%[fFuUdDnNickvm]', '', exec_str).strip()


class LaunchOps:
    def __init__(self, terminal_ops=None):
        self.terminal_ops = terminal_ops

    def launch_desktop_file(self, menu, files):
        """Launch programs from selected .desktop files."""
        desktop_files = []
        for f in files:
            path = _uri_to_path(f)
            if _is_desktop_file(path):
                desktop_files.append(path)

        if not desktop_files:
            return

        logger.debug("launch_desktop_file: %d file(s)", len(desktop_files))

        passed = 0
        for path in desktop_files:
            try:
                parser = configparser.ConfigParser(interpolation=None)
                parser.read(path)

                if not parser.has_section("Desktop Entry"):
                    logger.warning("Not a valid desktop file: %s", path)
                    continue

                name = parser.get("Desktop Entry", "Name", fallback=os.path.basename(path))

                # TryExec: check if program is available
                try_exec = parser.get("Desktop Entry", "TryExec", fallback="")
                if try_exec:
                    if not find_binary(try_exec):
                        logger.info("TryExec not found, skipping: %s (%s)", name, try_exec)
                        continue

                # Exec: the command to run
                exec_str = parser.get("Desktop Entry", "Exec", fallback="")
                if not exec_str:
                    logger.warning("No Exec field in: %s", path)
                    continue

                exec_str = _clean_exec(exec_str)
                try:
                    args = shlex.split(exec_str)
                except ValueError:
                    args = exec_str.split()

                if not args:
                    continue

                # Terminal=true: wrap with terminal emulator
                terminal = parser.get("Desktop Entry", "Terminal", fallback="false").lower() == "true"
                if terminal:
                    term = find_terminal(self.terminal_ops)
                    if term:
                        args = term + args
                    else:
                        logger.warning("Terminal=true but no terminal found for: %s", name)
                        notify(
                            translation.gettext("notify_launch_done"),
                            translation.gettext("notify_no_terminal"),
                        )
                        continue

                logger.info("Launching: %s → %s", name, args)
                subprocess.Popen(
                    args,
                    start_new_session=True, close_fds=True,
                    stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                )
                passed += 1
            except Exception as e:
                logger.exception("Failed to launch: %s, cause: %s", path, e)

        if passed > 0:
            notify(
                translation.gettext("notify_launch_done"),
                translation.gettext("notify_launch_count") % {"count": passed},
            )
