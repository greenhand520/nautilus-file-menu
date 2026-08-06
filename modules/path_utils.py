import os
import shutil
from urllib.parse import urlparse, unquote


def uri_to_path(file):
    """Convert a Nautilus FileInfo URI to an absolute filesystem path."""
    p = urlparse(file.get_activation_uri())
    return os.path.abspath(os.path.join(p.netloc, unquote(p.path)))


# Standard binary search dirs
_EXTRA_SEARCH_DIRS = [
    os.path.expanduser("~/.local/bin"),
    "/usr/local/bin",
    "/usr/bin",
]

def find_binary(cmd: str) -> str | None:
    """Find a binary, checking shutil.which first, then extra search dirs."""
    found = shutil.which(cmd)
    if found:
        return found
    for d in _EXTRA_SEARCH_DIRS:
        path = os.path.join(d, cmd)
        if os.path.isfile(path) and os.access(path, os.X_OK):
            return path
    return None
