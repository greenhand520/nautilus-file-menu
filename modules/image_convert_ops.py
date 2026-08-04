import os
from urllib.parse import urlparse, unquote
from gi.repository import Gtk, GLib

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

FORMAT_EXTENSIONS = {
    "PNG": ".png",
    "JPEG": ".jpg",
    "WEBP": ".webp",
    "BMP": ".bmp",
    "TIFF": ".tiff",
}


def is_image_file(file):
    mime = file.get_mime_type()
    return any(mime.startswith(prefix) for prefix in IMAGE_MIME_PREFIXES)


class ImageOps:
    def __init__(self, config):
        self.config = config
        self.formats = config.get("image_formats", ["PNG", "JPEG", "WEBP", "BMP", "TIFF"])

    def convert_image(self, menu, files, target_format):
        """Convert selected image files to the target format."""
        if not HAS_PIL:
            return

        for f in files:
            src_path = _uri_to_path(f)
            if not os.path.isfile(src_path):
                continue

            try:
                img = Image.open(src_path)

                if target_format == "JPEG" and img.mode in ("RGBA", "P"):
                    img = img.convert("RGB")

                base, _ = os.path.splitext(src_path)
                ext = FORMAT_EXTENSIONS.get(target_format, f".{target_format.lower()}")
                dst_path = base + ext

                if src_path == dst_path:
                    continue

                img.save(dst_path, target_format)
            except Exception:
                pass

    def get_format_items(self):
        if not HAS_PIL:
            return []
        return self.formats
