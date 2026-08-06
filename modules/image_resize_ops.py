import os
import threading
from gi import require_version
require_version('Gtk', '4.0')
from gi.repository import Gtk, Gdk, GLib
from translation import Translation
from .path_utils import uri_to_path as _uri_to_path
from .imagemagick_utils import (
    has_imagemagick, has_mogrify, resize_batch_by_dimensions, resize_batch_by_percent,
    get_image_size, RESIZE_FORMAT_MAP,
)
from .notify import logger, notify

try:
    from PIL import Image
    HAS_PIL = True
except ImportError:
    HAS_PIL = False


def _connect_spin_keys(spin, win, ok_btn):
    """Connect Enter/Escape on a SpinButton's internal Text widget."""
    text_widget = spin.get_first_child()
    if text_widget is None:
        text_widget = spin

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
    text_widget.add_controller(controller)


def _save_resized_pil(src_path, width, height):
    """Resize using PIL (fallback)."""
    with Image.open(src_path) as img:
        ext = os.path.splitext(src_path)[1].lower()
        fmt = RESIZE_FORMAT_MAP.get(ext)
        if fmt == "JPEG" and img.mode in ("RGBA", "P"):
            img = img.convert("RGB")
        img_resized = img.resize((width, height), Image.Resampling.LANCZOS)
        base, old_ext = os.path.splitext(src_path)
        dst_path = f"{base}_{width}x{height}{old_ext}"
        img_resized.save(dst_path, fmt)


class ImageResizeOps:
    def resize_by_dimensions(self, menu, files):
        if not has_mogrify() and not HAS_PIL:
            return

        # Get original dimensions from first image
        default_w, default_h = 800, 600
        first_path = _uri_to_path(files[0])
        if os.path.isfile(first_path):
            if has_imagemagick():
                w, h = get_image_size(first_path)
                if w > 0 and h > 0:
                    default_w, default_h = w, h
            elif HAS_PIL:
                try:
                    with Image.open(first_path) as img:
                        default_w, default_h = img.size
                except Exception:
                    pass

        win = Gtk.Window(title=Translation.t("dialog_dimensions_title"))
        win.set_default_size(350, 200)
        win.set_modal(True)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        box.set_margin_top(20)
        box.set_margin_bottom(20)
        box.set_margin_start(20)
        box.set_margin_end(20)

        label_w = Gtk.Label(label=Translation.t("dialog_width_label").format(w=default_w))
        adj_w = Gtk.Adjustment(value=default_w, lower=1, upper=65535, step_increment=1, page_increment=100)
        spin_w = Gtk.SpinButton()
        spin_w.set_adjustment(adj_w)

        label_h = Gtk.Label(label=Translation.t("dialog_height_label").format(h=default_h))
        adj_h = Gtk.Adjustment(value=default_h, lower=1, upper=65535, step_increment=1, page_increment=100)
        spin_h = Gtk.SpinButton()
        spin_h.set_adjustment(adj_h)

        box.append(label_w)
        box.append(spin_w)
        box.append(label_h)
        box.append(spin_h)

        btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        btn_box.set_halign(Gtk.Align.END)

        cancel_btn = Gtk.Button(label=Translation.t("dialog_cancel"))
        cancel_btn.connect("clicked", lambda b: win.destroy())
        btn_box.append(cancel_btn)

        ok_btn = Gtk.Button(label=Translation.t("dialog_resize"))
        ok_btn.add_css_class("suggested-action")
        ok_btn.connect("clicked", lambda b: self._do_resize_dimensions(
            win, spin_w.get_value_as_int(), spin_h.get_value_as_int(), files))
        btn_box.append(ok_btn)

        box.append(btn_box)
        win.set_child(box)
        _connect_spin_keys(spin_w, win, ok_btn)
        _connect_spin_keys(spin_h, win, ok_btn)
        win.present()

    def _do_resize_dimensions(self, win, width, height, files):
        win.destroy()
        paths = [_uri_to_path(f) for f in files]
        threading.Thread(
            target=self._run_resize_dimensions,
            args=(width, height, paths),
            daemon=True,
        ).start()

    def _run_resize_dimensions(self, width, height, paths):
        if has_mogrify():
            count = 0
            total = 0
            for group in self._groups(paths):
                out_dir = os.path.dirname(group[0])
                passed, group_total = resize_batch_by_dimensions(
                    group, out_dir, width, height
                )
                count += passed
                total += group_total
            GLib.idle_add(notify, Translation.t("notify_resize_done"),
                          Translation.t("notify_resize_count").format(count, total))
        else:
            count = 0
            for src_path in paths:
                if not os.path.isfile(src_path):
                    continue
                try:
                    _save_resized_pil(src_path, width, height)
                    count += 1
                except Exception:
                    logger.exception("Failed to resize: %s", src_path)
            GLib.idle_add(notify, Translation.t("notify_resize_done"),
                          Translation.t("notify_resize_count").format(count, len(paths)))

    def resize_by_percent(self, menu, files):
        if not has_mogrify() and not HAS_PIL:
            return

        win = Gtk.Window(title=Translation.t("dialog_percent_title"))
        win.set_default_size(350, 150)
        win.set_modal(True)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        box.set_margin_top(20)
        box.set_margin_bottom(20)
        box.set_margin_start(20)
        box.set_margin_end(20)

        label = Gtk.Label(label=Translation.t("dialog_percent_label"))
        adj = Gtk.Adjustment(value=50, lower=1, upper=100, step_increment=1, page_increment=10)
        spin = Gtk.SpinButton()
        spin.set_adjustment(adj)
        box.append(label)
        box.append(spin)

        btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        btn_box.set_halign(Gtk.Align.END)

        cancel_btn = Gtk.Button(label=Translation.t("dialog_cancel"))
        cancel_btn.connect("clicked", lambda b: win.destroy())
        btn_box.append(cancel_btn)

        ok_btn = Gtk.Button(label=Translation.t("dialog_resize"))
        ok_btn.add_css_class("suggested-action")
        ok_btn.connect("clicked", lambda b: self._do_resize_percent(win, spin.get_value(), files))
        btn_box.append(ok_btn)

        box.append(btn_box)
        win.set_child(box)
        _connect_spin_keys(spin, win, ok_btn)
        win.present()

    def _do_resize_percent(self, win, percent, files):
        win.destroy()
        paths = [_uri_to_path(f) for f in files]
        threading.Thread(
            target=self._run_resize_percent,
            args=(percent, paths),
            daemon=True,
        ).start()

    def _run_resize_percent(self, percent, paths):
        if has_mogrify():
            count = 0
            total = 0
            for group in self._groups(paths):
                out_dir = os.path.dirname(group[0])
                passed, group_total = resize_batch_by_percent(
                    group, out_dir, percent
                )
                count += passed
                total += group_total
            GLib.idle_add(notify, Translation.t("notify_resize_done"),
                          Translation.t("notify_resize_count").format(count, total))
        else:
            count = 0
            pct_label = int(percent) if percent == int(percent) else percent
            for src_path in paths:
                if not os.path.isfile(src_path):
                    continue
                try:
                    base, ext = os.path.splitext(src_path)
                    dst_path = f"{base}_p{pct_label}{ext}"
                    scale = percent / 100.0
                    with Image.open(src_path) as img:
                        fmt = RESIZE_FORMAT_MAP.get(ext.lower())
                        if fmt == "JPEG" and img.mode in ("RGBA", "P"):
                            img = img.convert("RGB")
                        new_w = max(1, int(img.width * scale))
                        new_h = max(1, int(img.height * scale))
                        img_resized = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
                        img_resized.save(dst_path, fmt)
                    count += 1
                except Exception:
                    logger.exception("Failed to resize: %s", src_path)
            GLib.idle_add(notify, Translation.t("notify_resize_done"),
                          Translation.t("notify_resize_count").format(count, len(paths)))

    @staticmethod
    def _groups(paths):
        groups = {}
        for path in paths:
            parent = os.path.dirname(path)
            groups.setdefault(parent, []).append(path)
        return groups.values()
