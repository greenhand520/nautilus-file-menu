import configparser
import glob
import os
import subprocess

from .file_utils import uri_to_path as _uri_to_path, find_binary, is_flatpak_installed
from .notify import logger

JETBRAINS_TOOLBOX_DIRS = [
    os.path.expanduser("~/.local/share/JetBrains/Toolbox/apps"),
    os.path.expanduser("~/JetBrains"),
    "/opt/JetBrains",
]

DESKTOP_DIRS = [
    os.path.expanduser("~/.local/share/applications"),
    "/usr/share/applications",
]

SKIP_DESKTOP_NAMES = {"JetBrains Toolbox", "JetBrains"}

# Default exclusion list (used when config doesn't have exclude_mime)
_DEFAULT_EXCLUDE_MIME = [
    "video/", "audio/", "image/", "font/",
    "application/vnd.", "application/wps-office",
    "application/zip", "application/x-rar", "application/x-7z-compressed",
    "application/x-tar", "application/gzip", "application/x-bzip2",
    "application/x-xz", "application/pdf", "application/epub+zip",
    "application/x-rpm", "application/x-alpm-package",
    "application/x-executable", "application/x-sharedlib", "application/x-mach-binary",
    "application/x-iso9660-image", "application/octet-stream",
    "application/msword",
]

def _get_exclude_mime(config):
    """Get merged exclude_mime list (built-in + config)."""
    user_exclude = config.get("open_ide", {}).get("exclude_mime", [])
    return _DEFAULT_EXCLUDE_MIME + user_exclude


def is_openable_in_editor(file, config=None):
    """Check if a file can be opened in an IDE based on MIME type exclusion."""
    mime = file.get_mime_type()
    # logger.debug("File mime type: %s", mime)
    exclude = _get_exclude_mime(config) if config else _DEFAULT_EXCLUDE_MIME
    return not any(mime.startswith(p) for p in exclude)


def _find_jetbrains_binary(cmd_name):
    """Find a JetBrains IDE binary in Toolbox dirs."""
    found = find_binary(cmd_name)
    if found:
        return found
    for base_dir in JETBRAINS_TOOLBOX_DIRS:
        if not os.path.isdir(base_dir):
            continue
        pattern = os.path.join(base_dir, "*", "bin", cmd_name)
        for match in glob.glob(pattern):
            if os.access(match, os.X_OK):
                return match
    return None


def _match_desktop_name(desktop_name, config_names):
    """Match a desktop file Name to a config key. Returns config key or None."""
    if desktop_name in config_names:
        return desktop_name
    for config_name in config_names:
        if desktop_name.startswith(config_name + " "):
            return config_name
    return None


class IdeOps:
    def __init__(self, config):
        self.config = config
        self.available_ides = {}
        self.available_jetbrains = {}
        self._detect()

    def _detect(self):
        ide_cfg = self.config.get("open_ide", {})
        other_cfg = ide_cfg.get("other_ides", {})
        jb_cfg = ide_cfg.get("jetbrains_ides", {})

        # name -> {cfg, is_jetbrains}
        all_ide_cfgs = {}
        for name, cfg in other_cfg.items():
            if isinstance(cfg, dict) and cfg.get("enabled", True):
                all_ide_cfgs[name] = {"cfg": cfg, "is_jetbrains": False}
        for name, cfg in jb_cfg.items():
            if name in ("collapse_menu",):
                continue
            if isinstance(cfg, dict) and cfg.get("enabled", True):
                all_ide_cfgs[name] = {"cfg": cfg, "is_jetbrains": True}

        all_names = set(all_ide_cfgs.keys())

        # --- Phase 1: Binary lookup ---
        for name, info in all_ide_cfgs.items():
            cfg = info["cfg"]
            is_jb = info["is_jetbrains"]
            cmd = cfg.get("cmd", [])
            cmd_name = cmd[0] if isinstance(cmd, list) and cmd else ""
            if not cmd_name:
                continue

            if is_jb:
                found = _find_jetbrains_binary(cmd_name)
            else:
                found = find_binary(cmd_name)

            if found:
                self._add_ide(name, [found], is_jb)

        # --- Phase 2: Desktop file scan ---
        for desktop_dir in DESKTOP_DIRS:
            if not os.path.isdir(desktop_dir):
                continue
            for filename in os.listdir(desktop_dir):
                if not filename.endswith(".desktop"):
                    continue
                filepath = os.path.join(desktop_dir, filename)
                try:
                    parser = configparser.ConfigParser(interpolation=None)
                    parser.read(filepath)
                    if not parser.has_section("Desktop Entry"):
                        continue

                    name = parser.get("Desktop Entry", "Name", fallback="")
                    exec_cmd = parser.get("Desktop Entry", "Exec", fallback="")

                    if not name or not exec_cmd or name in SKIP_DESKTOP_NAMES:
                        continue

                    matched_name = _match_desktop_name(name, all_names)
                    if not matched_name:
                        continue

                    if matched_name in self.available_ides or matched_name in self.available_jetbrains:
                        continue

                    binary = exec_cmd.split()[0].strip('"')
                    if os.path.isfile(binary) and os.access(binary, os.X_OK):
                        is_jb = all_ide_cfgs[matched_name]["is_jetbrains"]
                        self._add_ide(matched_name, [binary], is_jb)
                except Exception as e:
                    logger.exception("Failed to detect IDEs cfg: %s", e)

        # --- Phase 3: Flatpak ---
        for name, info in all_ide_cfgs.items():
            if name in self.available_ides or name in self.available_jetbrains:
                continue
            cfg = info["cfg"]
            is_jb = info["is_jetbrains"]
            flatpak = cfg.get("flatpak", [])
            if not flatpak or not isinstance(flatpak, list):
                continue
            app_id = flatpak[0]
            if is_flatpak_installed(app_id):
                args = ["flatpak", "run"] + flatpak
                self._add_ide(name, args, is_jb)

    def _add_ide(self, name, cmd_list, is_jetbrains):
        """Add an IDE to the appropriate dict."""
        if is_jetbrains:
            self.available_jetbrains[name] = cmd_list
            logger.info("IDE detected (JetBrains): %s → %s", name, cmd_list)
        else:
            self.available_ides[name] = cmd_list
            logger.info("IDE detected: %s → %s", name, cmd_list)

    def open_with_ide(self, menu, files, name):
        cmd_list = self.available_ides.get(name) or self.available_jetbrains.get(name)
        paths = [_uri_to_path(f) for f in files]
        if cmd_list and paths:
            try:
                subprocess.Popen(
                    cmd_list + paths,
                    start_new_session=True, close_fds=True,
                    stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    )
            except Exception as e:
                logger.exception("Failed to open IDE: %s, cause: %s", name, e)
        else:
            logger.warning("Empty cmd list or paths")

    def get_other_ides(self):
        """Return list of (display_name, display_name) for non-JetBrains IDEs."""
        return [(name, name) for name in self.available_ides]

    def get_jetbrains_ides(self):
        """Return list of (display_name, display_name) for JetBrains IDEs."""
        return [(name, name) for name in self.available_jetbrains]
