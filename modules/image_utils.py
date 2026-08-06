IMAGE_MIME_PREFIXES = [
    "image/png",
    "image/jpeg",
    "image/webp",
    "image/bmp",
    "image/tiff",
    "image/x-ms-bmp",
]


def is_image_file(file):
    """Check if a Nautilus FileInfo is an image by MIME type."""
    mime = file.get_mime_type()
    return any(mime.startswith(prefix) for prefix in IMAGE_MIME_PREFIXES)
