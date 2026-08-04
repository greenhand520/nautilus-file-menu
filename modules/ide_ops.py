import shutil
import subprocess
import os
import glob
import configparser
from urllib.parse import urlparse, unquote


def _uri_to_path(file):
    p = urlparse(file.get_activation_uri())
    return os.path.abspath(os.path.join(p.netloc, unquote(p.path)))


# Standard IDE commands (binary name in PATH or search dirs)
IDE_COMMANDS = {
    "vscode": "code",
    "code-insiders": "code-insiders",
    "code-oss": "code-oss",
    "zed": "zed",
}

# Flatpak app IDs for IDEs
FLATPAK_IDES = {
    "vscode": "com.visualstudio.code",
    "code-insiders": "com.visualstudio.code.insiders",
    "code-oss": "com.visualstudio.code-oss",
    "zed": "dev.zed.Zed",
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

# Standard binary search dirs
EXTRA_SEARCH_DIRS = [
    os.path.expanduser("~/.local/bin"),
    "/usr/local/bin",
    "/usr/bin",
]

# JetBrains Toolbox default install locations
JETBRAINS_TOOLBOX_DIRS = [
    os.path.expanduser("~/.local/share/JetBrains/Toolbox/apps"),
    os.path.expanduser("~/JetBrains"),
    "/opt/JetBrains",
]

DESKTOP_DIRS = [
    os.path.expanduser("~/.local/share/applications"),
    "/usr/share/applications",
]

# JetBrains entries that are NOT actual IDEs
JETBRAINS_SKIP_NAMES = {"JetBrains Toolbox", "JetBrains"}

# MIME types that should NOT show "Open with IDE"
NON_IDE_MIME_PREFIXES = [
    "video/",
    "audio/",
    "image/",
    "application/zip",
    "application/x-rar",
    "application/x-7z-compressed",
    "application/x-tar",
    "application/gzip",
    "application/x-bzip2",
    "application/x-xz",
    "application/pdf",
    "application/epub+zip",
]

# Labels for display
IDE_LABELS = {
    "vscode": "VSCode",
    "code-insiders": "VSCode Insiders",
    "code-oss": "Code - OSS",
    "zed": "Zed",
}


def _is_file_openable_in_ide(file):
    """Check if a file makes sense to open in an IDE."""
    mime = file.get_mime_type()
    if any(mime.startswith(prefix) for prefix in NON_IDE_MIME_PREFIXES):
        return False
    return True


def _find_binary(cmd):
    """Find a binary, checking shutil.which first, then extra search dirs."""
    found = shutil.which(cmd)
    if found:
        return found
    for d in EXTRA_SEARCH_DIRS:
        path = os.path.join(d, cmd)
        if os.path.isfile(path) and os.access(path, os.X_OK):
            return path
    return None


def _find_jetbrains_binary(cmd):
    """Find a JetBrains IDE binary in Toolbox install dirs."""
    # First try normal binary search
    found = _find_binary(cmd)
    if found:
        return found

    # Search JetBrains Toolbox dirs: .../clion/bin/clion
    for base_dir in JETBRAINS_TOOLBOX_DIRS:
        if not os.path.isdir(base_dir):
            continue
        # Search for <ide-name>/bin/<cmd> pattern
        pattern = os.path.join(base_dir, "*", "bin", cmd)
        for match in glob.glob(pattern):
            if os.access(match, os.X_OK):
                return match
    return None


def _is_flatpak_installed(app_id):
    """Check if a flatpak app is installed."""
    try:
        result = subprocess.run(
            ["flatpak", "info", app_id],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return result.returncode == 0
    except FileNotFoundError:
        return False


class IdeOps:
    def __init__(self, config):
        self.config = config
        self.available_ides = {}       # {name: ["cmd"] or ["flatpak", "run", "id"]}
        self.available_jetbrains = {}  # {name: ["/path/to/binary"]}
        self._detect_ides()

    def _detect_ides(self):
        """Detect which IDEs are installed on the system."""
        cmds = self.config.get("ide_commands", IDE_COMMANDS)
        flatpak_ids = self.config.get("flatpak_ids", FLATPAK_IDES)

        for name, cmd in cmds.items():
            if not cmd:
                continue
            # Try native binary — store full path
            found = _find_binary(cmd)
            if found:
                self.available_ides[name] = [found]
                continue
            # Try flatpak
            flatpak_id = flatpak_ids.get(name)
            if flatpak_id and _is_flatpak_installed(flatpak_id):
                self.available_ides[name] = ["flatpak", "run", flatpak_id]

        # Detect JetBrains IDEs
        jb_cmds = self.config.get("jetbrains_commands", JETBRAINS_COMMANDS)
        for name, cmd in jb_cmds.items():
            if not cmd:
                continue
            found = _find_jetbrains_binary(cmd)
            if found:
                self.available_jetbrains[name] = [found]

        # Fallback: scan .desktop files for JetBrains IDEs not yet found
        self._scan_desktop_files()

    def _scan_desktop_files(self):
        """Scan .desktop files to find JetBrains IDE entries not yet detected."""
        for desktop_dir in DESKTOP_DIRS:
            if not os.path.isdir(desktop_dir):
                continue
            for filename in os.listdir(desktop_dir):
                if "jetbrains" not in filename.lower() or not filename.endswith(".desktop"):
                    continue

                filepath = os.path.join(desktop_dir, filename)
                try:
                    parser = configparser.ConfigParser(interpolation=None)
                    parser.read(filepath)
                    if not parser.has_section("Desktop Entry"):
                        continue

                    name = parser.get("Desktop Entry", "Name", fallback=None)
                    exec_cmd = parser.get("Desktop Entry", "Exec", fallback=None)

                    if not name or not exec_cmd:
                        continue
                    if name in JETBRAINS_SKIP_NAMES:
                        continue
                    # Already found via binary search
                    if name in self.available_jetbrains:
                        continue

                    binary = exec_cmd.split()[0].strip('"')
                    if os.path.isfile(binary) and os.access(binary, os.X_OK):
                        self.available_jetbrains[name] = [binary]
                except Exception:
                    pass

    def open_with_ide(self, menu, files, name):
        """Open selected files/folder with the specified IDE."""
        cmd_list = self.available_ides.get(name) or self.available_jetbrains.get(name)
        if not cmd_list:
            return

        paths = [_uri_to_path(f) for f in files]
        full_cmd = cmd_list + paths

        # Use fork+exec in a new session to avoid Nautilus environment issues
        pid = os.fork()
        if pid == 0:
            # Child process: detach and exec
            os.setsid()
            try:
                os.execvp(full_cmd[0], full_cmd)
            except Exception:
                os._exit(1)
        # Parent continues immediately

    def get_other_ides(self):
        """Return list of (label, name) for non-JetBrains IDEs."""
        return [(IDE_LABELS.get(name, name), name) for name in self.available_ides]

    def get_jetbrains_ides(self):
        """Return list of (label, name) for JetBrains IDEs."""
        return [(name, name) for name in self.available_jetbrains]
