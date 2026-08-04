import os
import shutil
from urllib.parse import urlparse, unquote
from gi.repository import Gtk, Gdk
from translation import Translation


def _uri_to_path(file):
    p = urlparse(file.get_activation_uri())
    return os.path.abspath(os.path.join(p.netloc, unquote(p.path)))


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
            dst = os.path.join(parent_path, item_name)

            if os.path.exists(dst):
                base, ext = os.path.splitext(item_name)
                counter = 1
                while os.path.exists(dst):
                    dst = os.path.join(parent_path, f"{base}_{counter}{ext}")
                    counter += 1

            shutil.move(src, dst)

        try:
            os.rmdir(folder_path)
        except OSError:
            pass

    def move_into_folder(self, menu, files):
        """Create a new folder and move all selected files into it."""
        if len(files) < 2:
            return

        parent_path = os.path.dirname(_uri_to_path(files[0]))

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
        controller = Gtk.EventControllerKey()
        controller.connect("key-pressed", lambda ctrl, keyval, keycode, state:
            win.destroy() if keyval == Gdk.KEY_Escape else False)
        entry.add_controller(controller)

        win.present()

    def _do_move_into_folder(self, win, folder_name, files):
        folder_name = folder_name.strip()
        if not folder_name:
            return

        win.destroy()

        parent_path = os.path.dirname(_uri_to_path(files[0]))
        new_folder = os.path.join(parent_path, folder_name)
        os.makedirs(new_folder, exist_ok=True)

        for f in files:
            src = _uri_to_path(f)
            dst = os.path.join(new_folder, os.path.basename(src))

            if os.path.exists(dst):
                base, ext = os.path.splitext(os.path.basename(src))
                counter = 1
                while os.path.exists(dst):
                    dst = os.path.join(new_folder, f"{base}_{counter}{ext}")
                    counter += 1

            shutil.move(src, dst)
