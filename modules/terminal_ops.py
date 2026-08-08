import os
import subprocess

from .file_utils import uri_to_path as _uri_to_path, find_binary, is_flatpak_installed
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

                cmd = cfg.get("cmd", [])
                if not cmd or not isinstance(cmd, list):
                    continue

                cmd_name = cmd[0]

                # Phase 1: native binary
                found = find_binary(cmd_name)
                if found:
                    self.available_terminals.append((name, cfg))
                    logger.info("Terminal detected: %s → %s", name, found)
                    continue

                # Phase 2: flatpak
                flatpak = cfg.get("flatpak", [])
                if flatpak and isinstance(flatpak, list) and flatpak[0]:
                    if is_flatpak_installed(flatpak[0]):
                        cfg_copy = dict(cfg)
                        cfg_copy["_flatpak"] = True
                        self.available_terminals.append((name, cfg_copy))
                        logger.info("Terminal detected (flatpak): %s → %s", name, flatpak[0])
        except Exception as e:
            logger.exception("Failed to detect terminal cfg: %s", e)

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

        logger.debug("Opening terminal in: %s", target)

        # Build command with path substitution
        if cfg.get("_flatpak"):
            flatpak = cfg.get("flatpak", [])
            args = ["flatpak", "run"] + [a.replace("{path}", target) for a in flatpak]
        else:
            cmd = cfg.get("cmd", [])
            args = [a.replace("{path}", target) for a in cmd]

        logger.debug("Terminal command: %s", args)

        try:
            subprocess.Popen(
                args, cwd=target,
                start_new_session=True, close_fds=True,
                stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
        except Exception as e:
            logger.exception("Failed to open terminal: %s", e)

    def get_terminals(self):
        """Return list of (display_name, cfg) for available terminals."""
        return self.available_terminals
