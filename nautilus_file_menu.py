import json
import os
import traceback
from typing import Any

from gi import require_version

from modules.checksum_ops import ChecksumOps
from modules.copy_ops import CopyOps
from modules.file_utils import uri_to_path as _uri_to_path
from modules.folder_ops import FolderOps
from modules.ide_ops import IdeOps, is_file_openable_in_ide
from modules.notify import set_log_level
from translation import Translation

require_version('Gtk', '4.0')
from gi.repository import Nautilus, GObject, Gtk, Gdk, GLib


class NautilusFileMenu(GObject.Object, Nautilus.MenuProvider):
    def _window_added(self, application, window):
        copy_cfg = self.config.get("copy", {})
        for item_name, item_cfg in copy_cfg.get("item", {}).items():
            shortcut_str = item_cfg.get("shortcut", "")
            if shortcut_str:
                action = Gtk.CallbackAction.new(self._shortcuts_handler)
                shortcut = Gtk.Shortcut.new(
                    Gtk.ShortcutTrigger.parse_string(shortcut_str), action
                )
                shortcut.set_arguments(GLib.Variant.new_string(item_name))
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
            "ops_enabled": {
                "copy": True,
                "dissolve_folder": True,
                "move_into_folder": True,
                "open_ide": True,
                "open_terminal": True,
                "checksum": True,
            },
            "language": "auto",
            "log_level": "WARNING",
            "separator": ", ",
            "copy": {
                "item": {
                    "copy_path": {"enabled": True, "shortcut": "<Ctrl><Shift>C"},
                    "copy_uri": {"enabled": True, "shortcut": "<Ctrl><Shift>U"},
                    "copy_name": {"enabled": True, "shortcut": "<Ctrl><Shift>D", "ignore_extension": False},
                    "copy_content": {"enabled": True, "shortcut": "<Ctrl><Shift>G"},
                },
                "collapse_menu": True,
                "selections": {"clipboard": True, "primary": True},
                "escape_value_items": False,
                "escape_value": False,
            },
            "open_ide": {
                "other_ides": {},
                "jetbrains_ides": {"collapse_menu": True},
            },
            "open_terminal": {
                "terminals": {},
                "collapse_menu": True,
            },
            "checksum_algorithms": {
                "enabled": ["md5", "sha1", "sha256", "sha512"],
            },
        }

        with open(os.path.join(os.path.dirname(__file__), "config.json")) as json_file:
            try:
                user_cfg = json.load(json_file)
                self._deep_update(self.config, user_cfg)
                if self.config.get("language"):
                    Translation.select_language(self.config["language"])
                if self.config.get("log_level"):
                    set_log_level(self.config["log_level"])
            except Exception:
                traceback.print_exc()

        # Initialize operation modules
        self.copy_ops = CopyOps(self.config, self.clipboard, self.primary_clipboard)
        self.folder_ops = FolderOps()
        self.ide_ops = IdeOps(self.config)
        self.checksum_ops = ChecksumOps(self.config, self.clipboard, self.primary_clipboard)

        app = Gtk.Application.get_default()
        if app:
            app.connect("window-added", self._window_added)
            app.connect("window-removed", self._window_removed)

    @staticmethod
    def _deep_update(base: dict, override: dict):
        """Recursively merge override into base."""
        for key, value in override.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                NautilusFileMenu._deep_update(base[key], value)
            else:
                base[key] = value

    def _shortcuts_handler(self, window, key) -> bool:
        item_name = GLib.Variant.get_string(key)
        window_id = window.get_id()

        action_function = {
            "copy_path": self.copy_ops.copy_paths,
            "copy_uri": self.copy_ops.copy_uris,
            "copy_name": self.copy_ops.copy_names,
            "copy_content": self.copy_ops.copy_content,
        }.get(item_name)

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
        ops = self.config.get("ops_enabled", {})

        items.extend(self._create_copy_items(files, group, ops))
        items.extend(self._create_folder_items(files, group, ops))
        items.extend(self._create_ide_items(files, group, ops))
        items.extend(self._create_checksum_items(files, group, ops))

        return items

    # --- Copy operations ---

    def _create_copy_items(self, files: list[Nautilus.FileInfo], group,
                           ops: dict[str, bool]) -> list[Nautilus.MenuItem]:
        if not ops.get("copy", True):
            return []

        plural = len(files) > 1
        copy_cfg = self.config.get("copy", {})
        copy_items_cfg = copy_cfg.get("item", {})

        # Build list of (name, label, callback, data) for enabled items
        entries = []

        if copy_items_cfg.get("copy_path", {}).get("enabled", True):
            entries.append((
                "CopyPath",
                Translation.t("copy_paths" if plural else "copy_path"),
                self.copy_ops.copy_paths,
                files,
            ))

        if copy_items_cfg.get("copy_uri", {}).get("enabled", True):
            entries.append((
                "CopyUri",
                Translation.t("copy_uris" if plural else "copy_uri"),
                self.copy_ops.copy_uris,
                files,
            ))

        if copy_items_cfg.get("copy_name", {}).get("enabled", True):
            entries.append((
                "CopyName",
                Translation.t("copy_names" if plural else "copy_name"),
                self.copy_ops.copy_names,
                files,
            ))

        if copy_items_cfg.get("copy_content", {}).get("enabled", True):
            allow_copy_content = ["application/x-shellscript", "application/json"]
            if len(files) == 1 and (
                    files[0].get_mime_type() in allow_copy_content or files[0].get_mime_type().startswith("text/")):
                entries.append((
                    "CopyContent",
                    Translation.t("copy_content"),
                    self.copy_ops.copy_content,
                    files[0],
                ))

        if not entries:
            return []

        # Single item: no submenu needed
        if len(entries) == 1:
            name, label, callback, data = entries[0]
            item = Nautilus.MenuItem(
                name=f"NautilusFileMenu::{name}{group}",
                label=label,
            )
            item.connect("activate", callback, data)
            return [item]

        # collapse_menu=true: fold into submenu
        if copy_cfg.get("collapse_menu", True):
            submenu = Nautilus.Menu()
            for name, label, callback, data in entries:
                sub_item = Nautilus.MenuItem(
                    name=f"NautilusFileMenu::{name}{group}",
                    label=label,
                )
                sub_item.connect("activate", callback, data)
                submenu.append_item(sub_item)

            menu_item = Nautilus.MenuItem(
                name="NautilusFileMenu::CopyMore" + group,
                label=Translation.t("copy_more"),
            )
            menu_item.set_submenu(submenu)
            return [menu_item]

        # collapse_menu=false: list all items directly
        items = []
        for name, label, callback, data in entries:
            item = Nautilus.MenuItem(
                name=f"NautilusFileMenu::{name}{group}",
                label=label,
            )
            item.connect("activate", callback, data)
            items.append(item)
        return items

    # --- Folder operations ---

    def _create_folder_items(self, files: list[Nautilus.FileInfo], group,
                             ops: dict[str, bool]) -> list[Nautilus.MenuItem]:
        items = []

        if (
                ops.get("dissolve_folder", True)
                and len(files) == 1
                and os.path.isdir(_uri_to_path(files[0]))
        ):
            item = Nautilus.MenuItem(
                name="NautilusFileMenu::DissolveFolder" + group,
                label=Translation.t("dissolve_folder"),
            )
            item.connect("activate", self.folder_ops.dissolve_folder, files)
            items.append(item)

        if ops.get("move_into_folder", True) and len(files) >= 2:
            item = Nautilus.MenuItem(
                name="NautilusFileMenu::MoveIntoFolder" + group,
                label=Translation.t("move_into_folder"),
            )
            item.connect("activate", self.folder_ops.move_into_folder, files)
            items.append(item)

        return items

    # --- IDE operations (single file/folder only) ---

    def _create_ide_items(self, files: list[Nautilus.FileInfo], group,
                          ops: dict[str, bool]) -> list[Nautilus.MenuItem]:
        items = []

        if not ops.get("open_ide", True):
            return items
        if len(files) != 1:
            return items
        if not is_file_openable_in_ide(files[0]):
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
            if len(jb_ides) == 1:
                # Single JetBrains IDE: show directly, no submenu
                jb_label, jb_cmd = jb_ides[0]
                jb_item = Nautilus.MenuItem(
                    name="NautilusFileMenu::OpenIDE_JB_" + jb_cmd + group,
                    label=jb_label,
                )
                jb_item.connect(
                    "activate",
                    lambda m, f, c=jb_cmd: self.ide_ops.open_with_ide(m, f, c),
                    files,
                )
                submenu.append_item(jb_item)
            else:
                jb_cfg = self.config.get("open_ide", {}).get("jetbrains_ides", {})
                if jb_cfg.get("collapse_menu", True):
                    # Multiple + collapse: fold into "JetBrains" submenu
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
                else:
                    # Multiple + no collapse: list all directly
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
                        submenu.append_item(jb_item)

        menu_item = Nautilus.MenuItem(
            name="NautilusFileMenu::OpenIDE" + group,
            label=Translation.t("open_with_ide_submenu"),
        )
        menu_item.set_submenu(submenu)
        items.append(menu_item)

        return items

    # --- Checksum ---

    def _create_checksum_items(self, files: list[Nautilus.FileInfo], group,
                               ops: dict[str, bool]) -> list[Nautilus.MenuItem]:
        items = []

        if not ops.get("checksum", True):
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
