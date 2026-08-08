import os

from gi import require_version

require_version('Gtk', '4.0')
from gi.repository import Gtk, Gdk
import translation
from .file_utils import uri_to_path as _uri_to_path
from .notify import logger
from .file_utils import file_move, file_delete, gio_make_directories


def _unique_dst(parent, item_name):
    """Return a unique destination path in parent, appending _N if needed."""
    dst = os.path.join(parent, item_name)
    if not os.path.exists(dst):
        return dst
    base, ext = os.path.splitext(item_name)
    counter = 1
    while os.path.exists(dst):
        dst = os.path.join(parent, f"{base}_{counter}{ext}")
        counter += 1
    return dst


class FolderOps:
    def dissolve_folder(self, menu, files):
        """Move all contents of selected folders to their parents, then delete the folders."""
        folders = []
        for f in files:
            path = _uri_to_path(f)
            if os.path.isdir(path) and not os.path.islink(path):
                folders.append(path)

        if not folders:
            return

        logger.debug("dissolve_folder: %d folder(s)", len(folders))

        # Confirmation dialog
        if len(folders) == 1:
            msg = translation.gettext("dialog_dissolve_confirm").format(
                name=os.path.basename(folders[0]))
        else:
            msg = translation.gettext("dialog_dissolve_confirm_plural").format(
                count=len(folders))

        win = Gtk.Window(title=translation.gettext("dissolve_folder"))
        win.set_default_size(280, 120)
        win.set_modal(True)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        box.set_margin_top(20)
        box.set_margin_bottom(20)
        box.set_margin_start(20)
        box.set_margin_end(20)

        label = Gtk.Label(label=msg)
        label.set_wrap(True)
        box.append(label)

        btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        btn_box.set_halign(Gtk.Align.END)

        cancel_btn = Gtk.Button(label=translation.gettext("dialog_cancel"))
        cancel_btn.connect("clicked", lambda b: win.destroy())
        btn_box.append(cancel_btn)

        ok_btn = Gtk.Button(label=translation.gettext("dialog_dissolve"))
        ok_btn.add_css_class("destructive-action")
        ok_btn.connect("clicked", lambda b: self._do_dissolve(win, folders))
        btn_box.append(ok_btn)

        box.append(btn_box)
        win.set_child(box)

        # Enter → confirm, Escape → cancel
        def _on_key(ctrl, keyval, keycode, state):
            if keyval in (Gdk.KEY_Return, Gdk.KEY_KP_Enter):
                ok_btn.activate()
                return True
            if keyval == Gdk.KEY_Escape:
                win.destroy()
                return True
            return False

        controller = Gtk.EventControllerKey()
        controller.connect("key-pressed", _on_key)
        win.add_controller(controller)

        win.present()

    def _do_dissolve(self, win, folders):
        """Execute dissolve after confirmation."""
        win.destroy()

        for folder_path in folders:
            logger.debug("dissolving: %s", folder_path)
            parent_path = os.path.dirname(folder_path)

            move_failed = False
            for item_name in os.listdir(folder_path):
                src = os.path.join(folder_path, item_name)
                dst = _unique_dst(parent_path, item_name)
                if not file_move(src, dst):
                    move_failed = True
                    logger.error("dissolve_folder: failed to move %s -> %s", src, dst)

            if move_failed:
                logger.error("dissolve_folder: source directory was not removed: %s", folder_path)
                continue

            if not file_delete(folder_path):
                logger.error("dissolve_folder: failed to remove folder: %s", folder_path)

    def move_into_folder(self, menu, files):
        """Create a new folder and move all selected files into it."""
        if len(files) < 2:
            return

        logger.debug("move_into_folder: %d files", len(files))

        win = Gtk.Window(title=translation.gettext("dialog_move_into_folder_title"))
        win.set_default_size(280, 120)
        win.set_modal(True)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        box.set_margin_top(20)
        box.set_margin_bottom(20)
        box.set_margin_start(20)
        box.set_margin_end(20)

        label = Gtk.Label(label=translation.gettext("dialog_folder_name_label"))
        box.append(label)

        entry = Gtk.Entry()
        entry.set_text(translation.gettext("dialog_default_folder_name"))
        box.append(entry)

        btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        btn_box.set_halign(Gtk.Align.END)

        cancel_btn = Gtk.Button(label=translation.gettext("dialog_cancel"))
        cancel_btn.connect("clicked", lambda b: win.destroy())
        btn_box.append(cancel_btn)

        ok_btn = Gtk.Button(label=translation.gettext("dialog_create"))
        ok_btn.add_css_class("suggested-action")
        ok_btn.connect("clicked", lambda b: self._do_move_into_folder(win, entry.get_text(), files))
        btn_box.append(ok_btn)

        box.append(btn_box)
        win.set_child(box)

        # Enter on Entry → confirm
        entry.connect("activate", lambda e: self._do_move_into_folder(win, entry.get_text(), files))

        # Escape on Entry → cancel
        def _on_key(ctrl, keyval, keycode, state):
            if keyval == Gdk.KEY_Escape:
                win.destroy()
                return True
            return False

        controller = Gtk.EventControllerKey()
        controller.connect("key-pressed", _on_key)
        entry.add_controller(controller)

        win.present()

    def _do_move_into_folder(self, win, folder_name, files):
        folder_name = folder_name.strip()
        if not folder_name:
            return

        win.destroy()

        paths = [_uri_to_path(f) for f in files]
        parent_path = os.path.dirname(paths[0])
        new_folder = os.path.join(str(parent_path), folder_name)

        gio_make_directories(new_folder)

        for src in paths:
            dst = _unique_dst(new_folder, os.path.basename(src))
            file_move(src, dst)
