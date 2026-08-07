import hashlib
import os

from gi.repository import GLib

from translation import Translation
from .file_utils import uri_to_path as _uri_to_path
from .notify import notify, logger

ALGORITHMS = {
    "md5": hashlib.md5,
    "sha1": hashlib.sha1,
    "sha256": hashlib.sha256,
    "sha512": hashlib.sha512,
}
# 64KB per idle tick
CHUNK_SIZE = 65536


class ChecksumOps:
    def __init__(self, config, clipboard, primary_clipboard):
        self.config = config
        self.clipboard = clipboard
        self.primary_clipboard = primary_clipboard
        self.algorithms = config.get("checksum_algorithms", ["md5", "sha1", "sha256", "sha512"])

    def compute_checksum(self, menu, files, algo_name):
        """计算所选文件的校验和并复制到剪贴板"""
        hasher_cls = ALGORITHMS.get(algo_name)
        if not hasher_cls:
            return

        paths = [_uri_to_path(f) for f in files]
        results = []
        GLib.idle_add(self._hash_step, algo_name, hasher_cls, paths, 0, results, None, None)

    def _hash_step(self, algo_name: str, hasher_cls, paths, file_index, results, fh, hasher):
        """每个空闲周期处理一个块。返回 True 继续，返回 False 完成"""
        # 文件不为空，则继续读取块
        if fh is not None:
            try:
                chunk = fh.read(CHUNK_SIZE)
                if chunk:
                    hasher.update(chunk)
                    return True  # more chunks to read
                else:
                    # File done — finalize
                    fh.close()
                    filename = os.path.basename(paths[file_index])
                    results.append(f"{hasher.hexdigest()}  {filename}")
                    file_index += 1
            except Exception as e:
                logger.exception(f"hash step error, cause: {e}")
                if fh:
                    fh.close()
                file_index += 1

        # Open next file (or finish)
        while file_index < len(paths):
            path = paths[file_index]
            if not os.path.isfile(path):
                file_index += 1
                continue
            try:
                fh = open(path, 'rb')
                hasher = hasher_cls()
                chunk = fh.read(CHUNK_SIZE)
                if chunk:
                    hasher.update(chunk)
                    # Schedule continuation for this file
                    GLib.idle_add(self._hash_step, algo_name, hasher_cls, paths, file_index, results, fh, hasher)
                    return False
                else:
                    # Empty file
                    fh.close()
                    filename = os.path.basename(path)
                    results.append(f"{hasher.hexdigest()}  {filename}")
                    file_index += 1
            except Exception as e:
                logger.exception(f"hash step error, cause: {e}")
                file_index += 1

        # All files done — copy to clipboard and notify
        if results:
            value = "\n".join(results)
            self.clipboard.set(value)
            selections = self.config.get("selections", {"clipboard": True, "primary": True})
            if selections.get("primary", False):
                self.primary_clipboard.set(value)

            if len(results) == 1:
                notify(Translation.t("notify_file_checksum_ok").format(algo_name.upper()))
            else:
                notify(Translation.t("notify_files_checksum_ok").format(len(results), algo_name.upper()))
        return False

    def get_available_algorithms(self):
        """Return list of configured algorithm names."""
        return [a for a in self.algorithms if a in ALGORITHMS]
