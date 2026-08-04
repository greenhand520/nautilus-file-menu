import os
from urllib.parse import urlparse, unquote
from gi.repository import Gtk, Gdk

try:
    from PIL import Image
    HAS_PIL = True
except ImportError:
    HAS_PIL = False


def _uri_to_path(file):
    p = urlparse(file.get_activation_uri())
    return os.path.abspath(os.path.join(p.netloc, unquote(p.path)))


IMAGE_MIME_PREFIXES = [
    "image/png",
    "image/jpeg",
    "image/webp",
    "image/bmp",
    "image/tiff",
    "image/x-ms-bmp",
]

FORMAT_MAP = {
    ".png": "PNG",
    ".jpg": "JPEG",
    ".jpeg": "JPEG",
    ".webp": "WEBP",
    ".bmp": "BMP",
    ".tiff": "TIFF",
}


def is_image_file(file):
    mime = file.get_mime_type()
    return any(mime.startswith(prefix) for prefix in IMAGE_MIME_PREFIXES)


def _connect_spin_keys(spin, win, ok_btn):
    """Connect Enter/Escape on a SpinButton's internal Text widget."""
    # GTK4 SpinButton contains a Text child that receives key events
    text_widget = spin.get_first_child()
    if text_widget is None:
        text_widget = spin

    controller = Gtk.EventControllerKey()
    controller.connect("key-pressed", lambda ctrl, keyval, keycode, state:
        ok_btn.activate() if keyval in (Gdk.KEY_Return, Gdk.KEY_KP_Enter)
        else win.destroy() if keyval == Gdk.KEY_Escape
        else False)
    text_widget.add_controller(controller)


class ImageCompressOps:
    def compress_by_quality(self, menu, files):
        if not HAS_PIL:
            return

        win = Gtk.Window(title="按质量压缩")
        win.set_default_size(350, 150)
        win.set_modal(True)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        box.set_margin_top(20)
        box.set_margin_bottom(20)
        box.set_margin_start(20)
        box.set_margin_end(20)

        label = Gtk.Label(label="质量百分比 (1-100)：")
        box.append(label)

        adj = Gtk.Adjustment(value=80, lower=1, upper=100, step_increment=1, page_increment=10)
        spin = Gtk.SpinButton()
        spin.set_adjustment(adj)
        box.append(spin)

        btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        btn_box.set_halign(Gtk.Align.END)

        cancel_btn = Gtk.Button(label="取消")
        cancel_btn.connect("clicked", lambda b: win.destroy())
        btn_box.append(cancel_btn)

        ok_btn = Gtk.Button(label="压缩")
        ok_btn.add_css_class("suggested-action")
        ok_btn.connect("clicked", lambda b: self._do_quality_compress(win, spin.get_value_as_int(), files))
        btn_box.append(ok_btn)

        box.append(btn_box)
        win.set_child(box)
        _connect_spin_keys(spin, win, ok_btn)
        win.present()

    def _do_quality_compress(self, win, quality, files):
        win.destroy()
        for f in files:
            src_path = _uri_to_path(f)
            if not os.path.isfile(src_path):
                continue
            try:
                img = Image.open(src_path)
                ext = os.path.splitext(src_path)[1].lower()
                fmt = FORMAT_MAP.get(ext)
                if fmt == "JPEG" and img.mode in ("RGBA", "P"):
                    img = img.convert("RGB")
                base, old_ext = os.path.splitext(src_path)
                dst_path = f"{base}_compressed{old_ext}"
                save_kwargs = {}
                if fmt in ("JPEG", "WEBP"):
                    save_kwargs["quality"] = quality
                elif fmt == "PNG":
                    save_kwargs["optimize"] = True
                img.save(dst_path, fmt, **save_kwargs)
            except Exception:
                pass

    def resize_by_dimensions(self, menu, files):
        if not HAS_PIL:
            return

        # Get original dimensions from first image
        default_w, default_h = 800, 600
        first_path = _uri_to_path(files[0])
        if os.path.isfile(first_path):
            try:
                with Image.open(first_path) as img:
                    default_w, default_h = img.size
            except Exception:
                pass

        win = Gtk.Window(title="按尺寸缩放")
        win.set_default_size(350, 200)
        win.set_modal(True)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        box.set_margin_top(20)
        box.set_margin_bottom(20)
        box.set_margin_start(20)
        box.set_margin_end(20)

        label_w = Gtk.Label(label=f"宽度 (像素) — 原始 {default_w}：")
        adj_w = Gtk.Adjustment(value=default_w, lower=1, upper=65535, step_increment=1, page_increment=100)
        spin_w = Gtk.SpinButton()
        spin_w.set_adjustment(adj_w)

        label_h = Gtk.Label(label=f"高度 (像素) — 原始 {default_h}：")
        adj_h = Gtk.Adjustment(value=default_h, lower=1, upper=65535, step_increment=1, page_increment=100)
        spin_h = Gtk.SpinButton()
        spin_h.set_adjustment(adj_h)

        box.append(label_w)
        box.append(spin_w)
        box.append(label_h)
        box.append(spin_h)

        btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        btn_box.set_halign(Gtk.Align.END)

        cancel_btn = Gtk.Button(label="取消")
        cancel_btn.connect("clicked", lambda b: win.destroy())
        btn_box.append(cancel_btn)

        ok_btn = Gtk.Button(label="缩放")
        ok_btn.add_css_class("suggested-action")
        ok_btn.connect("clicked", lambda b: self._do_resize_dimensions(
            win, spin_w.get_value_as_int(), spin_h.get_value_as_int(), files))
        btn_box.append(ok_btn)

        box.append(btn_box)
        win.set_child(box)
        # Connect keys on both spin buttons
        _connect_spin_keys(spin_w, win, ok_btn)
        _connect_spin_keys(spin_h, win, ok_btn)
        win.present()

    def _do_resize_dimensions(self, win, width, height, files):
        win.destroy()
        for f in files:
            src_path = _uri_to_path(f)
            if not os.path.isfile(src_path):
                continue
            try:
                img = Image.open(src_path)
                ext = os.path.splitext(src_path)[1].lower()
                fmt = FORMAT_MAP.get(ext)
                if fmt == "JPEG" and img.mode in ("RGBA", "P"):
                    img = img.convert("RGB")
                img_resized = img.resize((width, height), Image.LANCZOS)
                base, old_ext = os.path.splitext(src_path)
                dst_path = f"{base}_resized{old_ext}"
                img_resized.save(dst_path, fmt)
            except Exception:
                pass

    def resize_by_percent(self, menu, files):
        if not HAS_PIL:
            return

        win = Gtk.Window(title="按百分比缩放")
        win.set_default_size(350, 150)
        win.set_modal(True)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        box.set_margin_top(20)
        box.set_margin_bottom(20)
        box.set_margin_start(20)
        box.set_margin_end(20)

        label = Gtk.Label(label="缩放百分比 (1-100)：")
        adj = Gtk.Adjustment(value=50, lower=1, upper=100, step_increment=1, page_increment=10)
        spin = Gtk.SpinButton()
        spin.set_adjustment(adj)
        box.append(label)
        box.append(spin)

        btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        btn_box.set_halign(Gtk.Align.END)

        cancel_btn = Gtk.Button(label="取消")
        cancel_btn.connect("clicked", lambda b: win.destroy())
        btn_box.append(cancel_btn)

        ok_btn = Gtk.Button(label="缩放")
        ok_btn.add_css_class("suggested-action")
        ok_btn.connect("clicked", lambda b: self._do_resize_percent(win, spin.get_value(), files))
        btn_box.append(ok_btn)

        box.append(btn_box)
        win.set_child(box)
        _connect_spin_keys(spin, win, ok_btn)
        win.present()

    def _do_resize_percent(self, win, percent, files):
        win.destroy()
        scale = percent / 100.0
        for f in files:
            src_path = _uri_to_path(f)
            if not os.path.isfile(src_path):
                continue
            try:
                img = Image.open(src_path)
                ext = os.path.splitext(src_path)[1].lower()
                fmt = FORMAT_MAP.get(ext)
                if fmt == "JPEG" and img.mode in ("RGBA", "P"):
                    img = img.convert("RGB")
                new_w = max(1, int(img.width * scale))
                new_h = max(1, int(img.height * scale))
                img_resized = img.resize((new_w, new_h), Image.LANCZOS)
                base, old_ext = os.path.splitext(src_path)
                dst_path = f"{base}_resized{old_ext}"
                img_resized.save(dst_path, fmt)
            except Exception:
                pass
