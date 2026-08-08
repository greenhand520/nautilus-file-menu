import configparser
import glob
import os
import subprocess

from .file_utils import uri_to_path as _uri_to_path, find_binary, is_flatpak_installed
from .notify import logger

IDE_COMMANDS = {
    "Visual Studio Code": "code",
    "Visual Studio Code - Insiders": "code-insiders",
    "Code - OSS": "code-oss",
    "Zed": "zed",
}

FLATPAK_IDS = {
    "Visual Studio Code": "com.visualstudio.code",
    "Visual Studio Code - Insiders": "com.visualstudio.code.insiders",
    "Code - OSS": "com.visualstudio.code-oss",
    "Zed": "dev.zed.Zed",
}

JETBRAINS_COMMANDS = {
    "IntelliJ IDEA": "idea",
    "PyCharm": "pycharm",
    "WebStorm": "webstorm",
    "CLion": "clion",
    "GoLand": "goland",
    "Rider": "rider",
    "RubyMine": "rubymine",
    "PhpStorm": "phpstorm",
    "DataGrip": "datagrip",
    "RustRover": "rustrover",
}

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

NON_IDE_MIME_PREFIXES = [
    "video/", "audio/", "image/",
    "application/zip", "application/x-rar", "application/x-7z-compressed",
    "application/x-tar", "application/gzip", "application/x-bzip2",
    "application/x-xz", "application/pdf", "application/epub+zip",
]


def is_file_openable_in_ide(file):
    mime = file.get_mime_type()
    return not any(mime.startswith(p) for p in NON_IDE_MIME_PREFIXES)


def _find_jetbrains_binary(cmd):
    """Find a JetBrains IDE binary in Toolbox dirs."""
    found = find_binary(cmd)
    if found:
        return found
    for base_dir in JETBRAINS_TOOLBOX_DIRS:
        if not os.path.isdir(base_dir):
            continue
        pattern = os.path.join(base_dir, "*", "bin", cmd)
        for match in glob.glob(pattern):
            if os.access(match, os.X_OK):
                return match
    return None


def _is_jetbrains_name(name):
    """Check if a name matches any JetBrains IDE (exact or prefix match)."""
    if name in JETBRAINS_COMMANDS.keys():
        return True
    # Toolbox desktop files: "PyCharm 2024.1" → prefix match
    for jb_name in JETBRAINS_COMMANDS.keys():
        if name.startswith(jb_name + " "):
            return True
    return False


def _match_desktop_name(desktop_name, config_names):
    """Match a desktop file Name to a config key. Returns config key or None.

    Handles:
    - Exact match: "CLion" == "CLion"
    - JetBrains prefix: "CLion 2024.2" matches "CLion"
    - Other prefix: "Zed Editor" matches "Zed" (if "Zed" is in config)
    """
    if desktop_name in config_names:
        return desktop_name

    # Try prefix match: desktop_name starts with config_name + " "
    for config_name in config_names:
        if desktop_name.startswith(config_name + " "):
            return config_name

    return None


class IdeOps:
    def __init__(self, config):
        self.config = config
        # {display_name: ["/path/to/binary"] or ["flatpak", "run", "app-id"]}
        self.available_ides = {}
        self.available_jetbrains = {}
        self._detect()

    def _detect(self):
        ide_cfg = self.config.get("open_ide", {})
        other_ides = ide_cfg.get("other_ides", {})
        jb_ides = ide_cfg.get("jetbrains_ides", {})

        # Build cmd/flatpak maps from the new nested structure
        ide_cmds = {}
        flatpak_ids = {}
        for name, cfg in other_ides.items():
            if isinstance(cfg, dict):
                if cfg.get("enabled", True):
                    ide_cmds[name] = cfg.get("cmd", "")
                    fid = cfg.get("flatpak_id", "")
                    if fid:
                        flatpak_ids[name] = fid
            else:
                # Legacy format: plain string cmd
                ide_cmds[name] = cfg

        jb_cmds = {}
        for name, cfg in jb_ides.items():
            if name in ("collapse_menu",):
                continue
            if isinstance(cfg, dict):
                if cfg.get("enabled", True):
                    jb_cmds[name] = cfg.get("cmd", "")
            else:
                jb_cmds[name] = cfg

        all_names = set(ide_cmds.keys()) | set(jb_cmds.keys())

        # --- Phase 1: Binary lookup ---
        for name, cmd in ide_cmds.items():
            found = find_binary(cmd)
            if found:
                self._add_ide(name, [found])

        for name, cmd in jb_cmds.items():
            found = _find_jetbrains_binary(cmd)
            if found:
                self._add_ide(name, [found])

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

                    # Match desktop Name to a config key
                    matched_name = _match_desktop_name(name, all_names)
                    if not matched_name:
                        continue

                    # Already found via binary?
                    if matched_name in self.available_ides or matched_name in self.available_jetbrains:
                        continue

                    binary = exec_cmd.split()[0].strip('"')
                    if os.path.isfile(binary) and os.access(binary, os.X_OK):
                        self._add_ide(matched_name, [binary])
                except Exception as e:
                    logger.exception("Failed to detect IDEs, cause: %s", e)

        # --- Phase 3: Flatpak ---
        # note⚠️: not tested
        for name, app_id in flatpak_ids.items():
            if name in self.available_ides or name in self.available_jetbrains:
                continue
            if is_flatpak_installed(app_id):
                self._add_ide(name, ["flatpak", "run", app_id])

    def _add_ide(self, name, cmd_list):
        """Add an IDE to the appropriate dict (JetBrains or other)."""
        if _is_jetbrains_name(name):
            self.available_jetbrains[name] = cmd_list
            logger.info("IDE detected (JetBrains): %s → %s", name, cmd_list)
        else:
            self.available_ides[name] = cmd_list
            logger.info("IDE detected: %s → %s", name, cmd_list)

    def open_with_ide(self, menu, files, name):
        cmd_list = self.available_ides.get(name) or self.available_jetbrains.get(name)
        if not cmd_list:
            return
        paths = [_uri_to_path(f) for f in files]
        subprocess.Popen(
            cmd_list + paths,
            start_new_session=True, close_fds=True,
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )

    def get_other_ides(self):
        """Return list of (display_name, display_name) for non-JetBrains IDEs."""
        return [(name, name) for name in self.available_ides]

    def get_jetbrains_ides(self):
        """Return list of (display_name, display_name) for JetBrains IDEs."""
        return [(name, name) for name in self.available_jetbrains]
