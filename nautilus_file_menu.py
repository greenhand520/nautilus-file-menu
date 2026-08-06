import os
import json
import traceback
from typing import Any
from urllib.parse import urlparse, unquote
from translation import Translation
from modules.copy_ops import CopyOps
from modules.folder_ops import FolderOps
from modules.path_utils import uri_to_path as _uri_to_path
from modules.ide_ops import IdeOps, _is_file_openable_in_ide
from modules.image_convert_ops import ImageConvertOps
from modules.image_compress_ops import ImageCompressOps
from modules.image_utils import is_image_file
from modules.image_resize_ops import ImageResizeOps
from modules.checksum_ops import ChecksumOps
from modules.notify import set_log_level
from gi import require_version
import gi

require_version('Gtk', '4.0')
from gi.repository import Nautilus, GObject, Gtk, Gdk, GLib


class NautilusFileMenu(GObject.Object, Nautilus.MenuProvider):
    def _window_added(self, application, window):
        shortcuts: dict[str, str] = self.config.get("shortcuts", {})
        for key, shortcut_str in shortcuts.items():
            if shortcut_str:
                action = Gtk.CallbackAction.new(self._shortcuts_handler)
                shortcut = Gtk.Shortcut.new(
                    Gtk.ShortcutTrigger.parse_string(shortcut_str), action
                )
                shortcut.set_arguments(GLib.Variant.new_string(key))
                window.add_shortcut(shortcut)

    def _window_removed(self, application, window):
        window_id = window.get_id()
        if window_id in self.selected_files:
            del self.selected_files[window_id]

    def __init__(self):
        self.display = Gdk.Display.get_default()
        self.clipboard = self.display.get_clipboard()
        self.primary_clipboard = self.display.get_primary_clipboard()

        self.selected_files: dict[int, Any] = {}
        self.config: dict[str, Any] = {
            "items": {
                "copy_path": True,
                "copy_uri": True,
                "copy_name": True,
                "copy_content": True,
                "dissolve_folder": True,
                "move_into_folder": True,
                "open_ide": True,
                "image_convert": True,
                "image_compress": True,
                "checksum": True,
            },
            "selections": {
                "clipboard": True,
                "primary": True,
            },
            "shortcuts": {
                "copy_path": "<Ctrl><Shift>C",
                "copy_uri": "<Ctrl><Shift>U",
                "copy_name": "<Ctrl><Shift>D",
                "copy_content": "<Ctrl><Shift>G",
            },
            "language": "auto",
            "separator": ", ",
            "escape_value_items": False,
            "escape_value": False,
            "name_ignore_extension": False,
            "ide_commands": {
                "vscode": "code",
                "code-insiders": "code-insiders",
                "code-oss": "code-oss",
                "zed": "zed",
            },
            "flatpak_ids": {
                "vscode": "com.visualstudio.code",
                "code-insiders": "com.visualstudio.code.insiders",
                "code-oss": "com.visualstudio.code-oss",
                "zed": "dev.zed.Zed",
            },
            "jetbrains_commands": {
                "IntelliJ IDEA": "idea",
                "PyCharm": "pycharm",
                "WebStorm": "webstorm",
                "CLion": "clion",
                "GoLand": "goland",
                "Rider": "rider",
                "RubyMine": "rubymine",
                "PhpStorm": "phpstorm",
                "DataGrip": "datagrip",
            },
            "image_formats": ["PNG", "JPEG", "WEBP", "BMP", "TIFF"],
            "checksum_algorithms": ["md5", "sha1", "sha256", "sha512"],
            "log_level": "WARNING",
        }

        with open(os.path.join(os.path.dirname(__file__), "config.json")) as json_file:
            try:
                self.config.update(json.load(json_file))
                if self.config.get("language"):
                    Translation.select_language(self.config["language"])
                if self.config.get("log_level"):
                    set_log_level(self.config["log_level"])
            except Exception:
                traceback.print_exc()
                pass

        # Initialize operation modules
        self.copy_ops = CopyOps(self.config, self.clipboard, self.primary_clipboard)
        self.folder_ops = FolderOps()
        self.ide_ops = IdeOps(self.config)
        self.image_ops = ImageConvertOps(self.config)
        self.image_compress_ops = ImageCompressOps()
        self.image_resize_ops = ImageResizeOps()
        self.checksum_ops = ChecksumOps(self.config, self.clipboard, self.primary_clipboard)

        app = Gtk.Application.get_default()
        if app:
            app.connect("window-added", self._window_added)
            app.connect("window-removed", self._window_removed)

    def _shortcuts_handler(self, window, key) -> bool:
        action = GLib.Variant.get_string(key)
        window_id = window.get_id()

        action_function = {
            "copy_path": self.copy_ops.copy_paths,
            "copy_uri": self.copy_ops.copy_uris,
            "copy_name": self.copy_ops.copy_names,
            "copy_content": self.copy_ops.copy_content,
        }.get(action)

        if window_id in self.selected_files and action_function:
            action_function(None, self.selected_files[window_id])
            return True
        return False

    def get_file_items(self, *args):
        app = Gtk.Application.get_default()
        if not app:
            return []

        window = app.get_active_window()
        files = args[-1]

        self.selected_files[window.get_id()] = files

        return self._create_menu_items(files, "File")

    def get_background_items(self, *args):
        file = args[-1]
        return self._create_menu_items([file], "Background")

    def _create_menu_items(self, files: list[Nautilus.FileInfo], group) -> list[Nautilus.MenuItem]:
        items = []
        config_items: dict[str, bool] = self.config.get("items", {})

        items.extend(self._create_copy_items(files, group, config_items))
        items.extend(self._create_folder_items(files, group, config_items))
        items.extend(self._create_ide_items(files, group, config_items))
        items.extend(self._create_image_convert_items(files, group, config_items))
        items.extend(self._create_image_compress_items(files, group, config_items))
        items.extend(self._create_checksum_items(files, group, config_items))

        return items

    # --- Copy operations ---

    def _create_copy_items(self, files: list[Nautilus.FileInfo], group, config_items: dict[str, bool]) -> list[Nautilus.MenuItem]:
        items = []
        plural = len(files) > 1

        if config_items.get("copy_path", True):
            item = Nautilus.MenuItem(
                name="NautilusFileMenu::CopyPath" + group,
                label=Translation.t("copy_paths" if plural else "copy_path"),
            )
            item.connect("activate", self.copy_ops.copy_paths, files)
            items.append(item)

        if config_items.get("copy_uri", True):
            item = Nautilus.MenuItem(
                name="NautilusFileMenu::CopyUri" + group,
                label=Translation.t("copy_uris" if plural else "copy_uri"),
            )
            item.connect("activate", self.copy_ops.copy_uris, files)
            items.append(item)

        if config_items.get("copy_name", True):
            item = Nautilus.MenuItem(
                name="NautilusFileMenu::CopyName" + group,
                label=Translation.t("copy_names" if plural else "copy_name"),
            )
            item.connect("activate", self.copy_ops.copy_names, files)
            items.append(item)

        if config_items.get("copy_content", True):
            allow_copy_content = ["application/x-shellscript", "application/json"]
            if len(files) == 1 and (
                    files[0].get_mime_type() in allow_copy_content or files[0].get_mime_type().startswith("text/")):
                item = Nautilus.MenuItem(
                    name="NautilusFileMenu::CopyContent" + group,
                    label=Translation.t("copy_content"),
                )
                item.connect("activate", self.copy_ops.copy_content, files[0])
                items.append(item)

        return items

    # --- Folder operations ---

    def _create_folder_items(self, files: list[Nautilus.FileInfo], group, config_items: dict[str, bool]):
        items = []

        if (
                config_items.get("dissolve_folder", True)
                and len(files) == 1
                and os.path.isdir(_uri_to_path(files[0]))
        ):
            item = Nautilus.MenuItem(
                name="NautilusFileMenu::DissolveFolder" + group,
                label=Translation.t("dissolve_folder"),
            )
            item.connect("activate", self.folder_ops.dissolve_folder, files)
            items.append(item)

        if config_items.get("move_into_folder", True) and len(files) >= 2:
            item = Nautilus.MenuItem(
                name="NautilusFileMenu::MoveIntoFolder" + group,
                label=Translation.t("move_into_folder"),
            )
            item.connect("activate", self.folder_ops.move_into_folder, files)
            items.append(item)

        return items

    # --- IDE operations (single file/folder only) ---

    def _create_ide_items(self, files: list[Nautilus.FileInfo], group, config_items: dict[str, bool]):
        items = []

        if not config_items.get("open_ide", True):
            return items
        if len(files) != 1:
            return items
        if not _is_file_openable_in_ide(files[0]):
            return items

        other_ides = self.ide_ops.get_other_ides()
        jb_ides = self.ide_ops.get_jetbrains_ides()
        if not other_ides and not jb_ides:
            return items

        submenu = Nautilus.Menu()

        for ide_label, ide_cmd in other_ides:
            sub_item = Nautilus.MenuItem(
                name="NautilusFileMenu::OpenIDE_" + ide_cmd + group,
                label=ide_label,
            )
            sub_item.connect(
                "activate",
                lambda m, f, c=ide_cmd: self.ide_ops.open_with_ide(m, f, c),
                files,
            )
            submenu.append_item(sub_item)

        if jb_ides:
            jb_submenu = Nautilus.Menu()
            for jb_label, jb_cmd in jb_ides:
                jb_item = Nautilus.MenuItem(
                    name="NautilusFileMenu::OpenIDE_JB_" + jb_cmd + group,
                    label=jb_label,
                )
                jb_item.connect(
                    "activate",
                    lambda m, f, c=jb_cmd: self.ide_ops.open_with_ide(m, f, c),
                    files,
                )
                jb_submenu.append_item(jb_item)

            jb_menu_item = Nautilus.MenuItem(
                name="NautilusFileMenu::OpenIDE_JetBrains" + group,
                label=Translation.t("open_with_jetbrains"),
            )
            jb_menu_item.set_submenu(jb_submenu)
            submenu.append_item(jb_menu_item)

        menu_item = Nautilus.MenuItem(
            name="NautilusFileMenu::OpenIDE" + group,
            label=Translation.t("open_with_ide_submenu"),
        )
        menu_item.set_submenu(submenu)
        items.append(menu_item)

        return items

    # --- Image conversion ---

    def _create_image_convert_items(self, files: list[Nautilus.FileInfo], group, config_items: dict[str, bool]):
        items = []

        if not config_items.get("image_convert", True):
            return items

        image_files = [f for f in files if is_image_file(f)]
        if not image_files:
            return items

        formats = self.image_ops.get_format_items()
        if not formats:
            return items

        submenu = Nautilus.Menu()
        for fmt in formats:
            sub_item = Nautilus.MenuItem(
                name="NautilusFileMenu::ConvertImage_" + fmt + group,
                label=fmt,
            )
            sub_item.connect(
                "activate",
                lambda m, f, fmt_=fmt: self.image_ops.convert_image(m, f, fmt_),
                image_files,
            )
            submenu.append_item(sub_item)

        menu_item = Nautilus.MenuItem(
            name="NautilusFileMenu::ConvertImage" + group,
            label=Translation.t("image_convert_submenu"),
        )
        menu_item.set_submenu(submenu)
        items.append(menu_item)

        return items

    # --- Image compression ---

    def _create_image_compress_items(self, files: list[Nautilus.FileInfo], group, config_items: dict[str, bool]):
        items = []

        if not config_items.get("image_compress", True):
            return items

        compress_files = [f for f in files if is_image_file(f)]
        if not compress_files:
            return items

        submenu = Nautilus.Menu()

        quality_item = Nautilus.MenuItem(
            name="NautilusFileMenu::CompressQuality" + group,
            label=Translation.t("compress_by_quality"),
        )
        quality_item.connect(
            "activate",
            lambda m, f: self.image_compress_ops.compress_by_quality(m, f),
            compress_files,
        )
        submenu.append_item(quality_item)

        size_item = Nautilus.MenuItem(
            name="NautilusFileMenu::CompressDimensions" + group,
            label=Translation.t("resize_by_dimensions"),
        )
        size_item.connect(
            "activate",
            lambda m, f: self.image_resize_ops.resize_by_dimensions(m, f),
            compress_files,
        )
        submenu.append_item(size_item)

        percent_item = Nautilus.MenuItem(
            name="NautilusFileMenu::CompressPercent" + group,
            label=Translation.t("resize_by_percent"),
        )
        percent_item.connect(
            "activate",
            lambda m, f: self.image_resize_ops.resize_by_percent(m, f),
            compress_files,
        )
        submenu.append_item(percent_item)

        menu_item = Nautilus.MenuItem(
            name="NautilusFileMenu::ImageCompress" + group,
            label=Translation.t("image_compress_submenu"),
        )
        menu_item.set_submenu(submenu)
        items.append(menu_item)

        return items

    # --- Checksum ---

    def _create_checksum_items(self, files, group, config_items: dict[str, bool]):
        items = []

        if not config_items.get("checksum", True):
            return items

        checksum_files = [f for f in files if not os.path.isdir(_uri_to_path(f))]
        if not checksum_files:
            return items

        algos = self.checksum_ops.get_available_algorithms()
        if not algos:
            return items

        if len(algos) == 1:
            algo = algos[0]
            item = Nautilus.MenuItem(
                name="NautilusFileMenu::Checksum_" + algo + group,
                label=Translation.t("checksum").format(algo=algo.upper()),
            )
            item.connect(
                "activate",
                lambda m, f, a=algo: self.checksum_ops.compute_checksum(m, f, a),
                checksum_files,
            )
            items.append(item)
        else:
            submenu = Nautilus.Menu()
            for algo in algos:
                sub_item = Nautilus.MenuItem(
                    name="NautilusFileMenu::Checksum_" + algo + group,
                    label=algo.upper(),
                )
                sub_item.connect(
                    "activate",
                    lambda m, f, a=algo: self.checksum_ops.compute_checksum(m, f, a),
                    checksum_files,
                )
                submenu.append_item(sub_item)

            menu_item = Nautilus.MenuItem(
                name="NautilusFileMenu::Checksum" + group,
                label=Translation.t("checksum_submenu"),
            )
            menu_item.set_submenu(submenu)
            items.append(menu_item)

        return items
