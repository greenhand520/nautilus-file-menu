import threading
from pathlib import Path

from gi.repository import GLib

from translation import Translation
from .imagemagick_utils import has_mogrify, convert_format as im_convert, FORMAT_EXTENSIONS
from .notify import logger, notify
from .path_utils import uri_to_path as _uri_to_path

try:
    from PIL import Image

    HAS_PIL = True
except ImportError:
    HAS_PIL = False


def _pil_convert_one(src_path, target_format):
    """Convert a single image using PIL. Returns True on success."""
    upper_format = target_format.upper()
    if upper_format == "JPG":
        target_format = "JPEG"
        ext = FORMAT_EXTENSIONS.get(target_format)
    else:
        ext = FORMAT_EXTENSIONS.get(upper_format)
    if not ext:
        return False

    with Image.open(src_path) as img:
        if target_format == "JPEG" and img.mode in ("RGBA", "P", "LA"):
            img = img.convert("RGB")

        base = str(Path(src_path).with_suffix(""))
        dst_path = base + ext

        if src_path == dst_path:
            return False

        save_kwargs = {}
        if target_format == "JPEG":
            save_kwargs["quality"] = 95
            save_kwargs["progressive"] = True
        elif target_format == "WEBP":
            save_kwargs["quality"] = 95

        img.save(dst_path, target_format, **save_kwargs)
        logger.info("PIL convert: %s -> %s", Path(src_path).name, Path(dst_path).name)
        return True


class ImageConvertOps:
    def __init__(self, config):
        self.config = config
        self.formats = config.get("image_formats", ["PNG", "JPG", "WEBP", "BMP", "TIFF"])

    def convert_image(self, menu, files, target_format):
        """Convert selected image files to the target format."""
        if not has_mogrify() and not HAS_PIL:
            return

        paths = [_uri_to_path(f) for f in files]

        if has_mogrify():
            # ImageMagick: subprocess, safe in thread
            threading.Thread(
                target=self._run_im_convert,
                args=(target_format, paths),
                daemon=True,
            ).start()
        elif HAS_PIL:
            # PIL: must use GLib.idle_add (Image.open blocks in GLib threads)
            GLib.idle_add(self._run_pil_step, target_format, paths, 0, 0)

    def _run_im_convert(self, target_format, paths):
        convert_count = 0
        for group in self._groups(paths):
            out_dir = str(Path(group[0]).parent)
            passed, _ = im_convert(group, out_dir, target_format)
            convert_count += passed

        if convert_count > 0:
            GLib.idle_add(
                notify, Translation.t("notify_image_converted"),
                Translation.t("notify_image_converted_count").format(
                    convert_count, len(paths)
                ),
            )
        else:
            GLib.idle_add(
                notify, Translation.t("notify_image_converted"),
                Translation.t("notify_no_image_converted"),
            )

    @staticmethod
    def _groups(paths):
        groups = {}
        for path in paths:
            parent = str(Path(path).parent)
            groups.setdefault(parent, []).append(path)
        return groups.values()

    def _run_pil_step(self, target_format, paths, index, success_count):
        """Process one file per idle tick. Returns True to continue, False when done."""
        if index >= len(paths):
            # All done
            if success_count > 0:
                GLib.idle_add(notify, Translation.t("notify_image_converted"),
                              Translation.t("notify_image_converted_count").format(success_count, len(paths)))
            else:
                GLib.idle_add(notify, Translation.t("notify_image_converted"),
                              Translation.t("notify_no_image_converted"))
            return False

        src_path = paths[index]
        try:
            if _pil_convert_one(src_path, target_format):
                success_count += 1
        except Exception as e:
            logger.exception("PIL convert failed, cause: %s, path: %s", e, src_path)

        GLib.idle_add(self._run_pil_step, target_format, paths, index + 1, success_count)
        return False

    def get_format_items(self):
        if not has_mogrify() and not HAS_PIL:
            return []
        return self.formats
