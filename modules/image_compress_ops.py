import os
import threading
from gi import require_version
require_version('Gtk', '4.0')
from gi.repository import Gtk, Gdk, GLib
from translation import Translation
from .path_utils import uri_to_path as _uri_to_path
from .pngquant_utils import has_pngquant, compress_batch as pngquant_batch
from .imagemagick_utils import (
    has_mogrify, compress_batch_by_quality as im_compress_batch,
)
from .notify import logger, notify

try:
    from PIL import Image
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

PNG_EXTS = {".png"}


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


def _output_path(src_path, suffix):
    base, ext = os.path.splitext(src_path)
    return f"{base}{suffix}{ext}"


def _unprocessed_paths(paths, outputs, suffix):
    successful = {os.path.abspath(path) for path in outputs}
    return [
        path for path in paths
        if os.path.abspath(_output_path(path, suffix)) not in successful
    ]


def _pil_compress_one(src_path, quality):
    """Compress a single image with PIL. Returns output path or None."""
    from .image_quality_compress import compress_image

    dst_path = _output_path(src_path, f"_q{int(quality)}")
    try:
        ok, _ = compress_image(src_path, dst_path, quality)
        return dst_path if ok else None
    except Exception:
        logger.exception("PIL compress failed: %s", src_path)
        return None


class ImageCompressOps:
    def compress_by_quality(self, menu, files):
        if not has_pngquant() and not has_mogrify() and not HAS_PIL:
            return

        win = Gtk.Window(title=Translation.t("dialog_quality_title"))
        win.set_default_size(350, 150)
        win.set_modal(True)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        box.set_margin_top(20)
        box.set_margin_bottom(20)
        box.set_margin_start(20)
        box.set_margin_end(20)

        label = Gtk.Label(label=Translation.t("dialog_quality_label"))
        box.append(label)

        adj = Gtk.Adjustment(value=80, lower=1, upper=100, step_increment=1, page_increment=10)
        spin = Gtk.SpinButton()
        spin.set_adjustment(adj)
        box.append(spin)

        btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        btn_box.set_halign(Gtk.Align.END)

        cancel_btn = Gtk.Button(label=Translation.t("dialog_cancel"))
        cancel_btn.connect("clicked", lambda b: win.destroy())
        btn_box.append(cancel_btn)

        ok_btn = Gtk.Button(label=Translation.t("dialog_compress"))
        ok_btn.add_css_class("suggested-action")
        ok_btn.connect("clicked", lambda b: self._do_quality_compress(win, spin.get_value_as_int(), files))
        btn_box.append(ok_btn)

        box.append(btn_box)
        win.set_child(box)
        _connect_spin_keys(spin, win, ok_btn)
        win.present()

    def _do_quality_compress(self, win, quality, files):
        win.destroy()
        paths = [_uri_to_path(f) for f in files]
        threading.Thread(
            target=self._run_quality_compress,
            args=(quality, paths),
            daemon=True,
        ).start()

    def _run_quality_compress(self, quality, paths):
        """Compress images in a worker thread with ordered per-file fallback.

        PNG: pngquant -> ImageMagick -> PIL
        Other: ImageMagick -> PIL
        """
        png_paths = [
            p for p in paths
            if os.path.splitext(p)[1].lower() in PNG_EXTS
        ]
        other_paths = [p for p in paths if p not in png_paths]

        logger.info("Quality compress: %d PNG, %d other, quality=%d",
                    len(png_paths), len(other_paths), quality)

        results = []
        suffix = f"_q{int(quality)}"

        for group in self._groups(png_paths):
            remaining = group
            if has_pngquant():
                outputs = pngquant_batch(group, quality, suffix=suffix)
                results.extend(outputs)
                remaining = _unprocessed_paths(group, outputs, suffix)

            if remaining and has_mogrify():
                outputs = im_compress_batch(
                    remaining, os.path.dirname(remaining[0]), quality
                )
                results.extend(outputs)
                remaining = _unprocessed_paths(remaining, outputs, suffix)

            if remaining and HAS_PIL:
                for path in remaining:
                    output = _pil_compress_one(path, quality)
                    if output:
                        results.append(output)

        for group in self._groups(other_paths):
            remaining = group
            if has_mogrify():
                outputs = im_compress_batch(
                    group, os.path.dirname(group[0]), quality
                )
                results.extend(outputs)
                remaining = _unprocessed_paths(group, outputs, suffix)

            if remaining and HAS_PIL:
                for path in remaining:
                    output = _pil_compress_one(path, quality)
                    if output:
                        results.append(output)

        if results:
            GLib.idle_add(
                notify, Translation.t("notify_compress_done"),
                Translation.t("notify_compress_count").format(
                    len(results), len(paths)
                ),
            )
        else:
            GLib.idle_add(
                notify, Translation.t("notify_compress_done"),
                Translation.t("notify_no_image_compressed"),
            )

    @staticmethod
    def _groups(paths):
        groups = {}
        for path in paths:
            parent = os.path.dirname(path)
            groups.setdefault(parent, []).append(path)
        return groups.values()
