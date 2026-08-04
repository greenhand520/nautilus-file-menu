import hashlib
import os
from urllib.parse import urlparse, unquote
from gi.repository import Gdk


ALGORITHMS = {
    "md5": hashlib.md5,
    "sha1": hashlib.sha1,
    "sha256": hashlib.sha256,
    "sha512": hashlib.sha512,
}


def _uri_to_path(file):
    p = urlparse(file.get_activation_uri())
    return os.path.abspath(os.path.join(p.netloc, unquote(p.path)))


class ChecksumOps:
    def __init__(self, config, clipboard, primary_clipboard):
        self.config = config
        self.clipboard = clipboard
        self.primary_clipboard = primary_clipboard
        self.algorithms = config.get("checksum_algorithms", ["md5", "sha1", "sha256", "sha512"])

    def compute_checksum(self, menu, files, algo_name):
        """Compute checksum of selected files and copy to clipboard."""
        hasher_cls = ALGORITHMS.get(algo_name)
        if not hasher_cls:
            return

        results = []
        for f in files:
            path = _uri_to_path(f)
            if not os.path.isfile(path):
                continue

            hasher = hasher_cls()
            try:
                with open(path, 'rb') as fh:
                    while True:
                        chunk = fh.read(8192)
                        if not chunk:
                            break
                        hasher.update(chunk)
                filename = os.path.basename(path)
                results.append(f"{hasher.hexdigest()}  {filename}")
            except Exception:
                pass

        if results:
            value = "\n".join(results)
            self.clipboard.set(value)
            selections = self.config.get("selections", {"clipboard": True, "primary": True})
            if selections.get("primary", False):
                self.primary_clipboard.set(value)

    def get_available_algorithms(self):
        """Return list of configured algorithm names."""
        return [a for a in self.algorithms if a in ALGORITHMS]
