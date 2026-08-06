import os
from gi import require_version
require_version('Gtk', '4.0')
from gi.repository import Gtk, Gdk, Gio, GLib
from translation import Translation
from .path_utils import uri_to_path as _uri_to_path
from .notify import logger


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


def _gio_move(src_path, dst_path):
    """Move a file using Gio.File.move."""
    src = Gio.File.new_for_path(src_path)
    dst = Gio.File.new_for_path(dst_path)
    src.move(dst, Gio.FileCopyFlags.NONE, None, None, None)


class FolderOps:
    def dissolve_folder(self, menu, files):
        """Move all contents of a folder to its parent, then delete the folder."""
        if len(files) != 1:
            return

        folder_path = _uri_to_path(files[0])
        if not os.path.isdir(folder_path):
            return

        parent_path = os.path.dirname(folder_path)

        for item_name in os.listdir(folder_path):
            src = os.path.join(folder_path, item_name)
            dst = _unique_dst(parent_path, item_name)
            _gio_move(src, dst)

        try:
            Gio.File.new_for_path(folder_path).delete(None)
        except GLib.Error as e:
            logger.error("dissolve_folder: failed to remove folder: %s", e.message)

    def move_into_folder(self, menu, files):
        """Create a new folder and move all selected files into it."""
        if len(files) < 2:
            return

        win = Gtk.Window(title=Translation.t("dialog_move_into_folder_title"))
        win.set_default_size(350, 120)
        win.set_modal(True)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        box.set_margin_top(20)
        box.set_margin_bottom(20)
        box.set_margin_start(20)
        box.set_margin_end(20)

        label = Gtk.Label(label=Translation.t("dialog_folder_name_label"))
        box.append(label)

        entry = Gtk.Entry()
        entry.set_text(Translation.t("dialog_default_folder_name"))
        box.append(entry)

        btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        btn_box.set_halign(Gtk.Align.END)

        cancel_btn = Gtk.Button(label=Translation.t("dialog_cancel"))
        cancel_btn.connect("clicked", lambda b: win.destroy())
        btn_box.append(cancel_btn)

        ok_btn = Gtk.Button(label=Translation.t("dialog_create"))
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

        # Create folder using Gio
        Gio.File.new_for_path(new_folder).make_directory_with_parents(None)

        for src in paths:
            dst = _unique_dst(new_folder, os.path.basename(src))
            _gio_move(src, dst)
