import os
import subprocess

from .file_utils import uri_to_path as _uri_to_path, find_binary
from .notify import logger


class TerminalOps:
    def __init__(self, config):
        self.config = config
        self.available_terminals = []
        self._detect()

    def _detect(self):
        try:
            terminals_cfg = self.config.get("open_terminal", {}).get("terminals", {})
            for name, cfg in terminals_cfg.items():
                if not isinstance(cfg, dict) or not cfg.get("enabled", True):
                    continue

                cmd = cfg.get("cmd", "")
                if not cmd:
                    continue

                flatpak_id = cfg.get("flatpak_id", "")

                # Extract binary name for detection (first element if array)
                cmd_name = cmd[0] if isinstance(cmd, list) else cmd

                # Phase 1: native binary
                found = find_binary(cmd_name)
                if found:
                    self.available_terminals.append((name, cfg))
                    logger.info("Terminal detected: %s → %s", name, found)
                    continue

                # Phase 2: flatpak
                if flatpak_id and self._is_flatpak_installed(flatpak_id):
                    cfg_copy = dict(cfg)
                    cfg_copy["_flatpak"] = True
                    self.available_terminals.append((name, cfg_copy))
                    logger.info("Terminal detected (flatpak): %s → %s", name, flatpak_id)
        except Exception as e:
            logger.exception("Failed to detect open terminal cfg, cause: %s", e)

    @staticmethod
    def _is_flatpak_installed(app_id):
        try:
            result = subprocess.run(
                ["flatpak", "info", app_id],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
            return result.returncode == 0
        except FileNotFoundError:
            return False

    def open_terminal(self, menu, files, cfg):
        """Open terminal in the given directory."""
        if files:
            f = files[0]
            loc = f.get_location()
            target = loc.get_path() if loc else None
            if not target:
                target = _uri_to_path(f)
            if target is None:
                target = os.path.expanduser("~")
            if not os.path.isdir(target):
                target = os.path.dirname(target)
        else:
            target = os.path.expanduser("~")

        # Build command with path substitution
        if cfg.get("_flatpak"):
            flatpak_id = cfg.get("flatpak_id", "")
            flatpak_args = cfg.get("flatpak_args", [])
            args = ["flatpak", "run", flatpak_id]
            for a in flatpak_args:
                args.append(a.replace("{path}", target))
        else:
            cmd = cfg.get("cmd", [])
            if isinstance(cmd, list):
                args = [a.replace("{path}", target) for a in cmd]
            else:
                args = [cmd]

        try:
            subprocess.Popen(
                args, cwd=target,
                start_new_session=True, close_fds=True,
                stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
        except Exception as e:
            logger.exception("Failed to open terminal: %s, cause: %s", args, e)

    def get_terminals(self):
        """Return list of (display_name, cfg) for available terminals."""
        return self.available_terminals
