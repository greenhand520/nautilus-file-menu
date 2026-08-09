import tempfile
import unittest
from pathlib import Path
from unittest import mock

from modules.copy_ops import CopyOps, MAX_FILE_CONTENT_COPY


class _FakeFile:
    def __init__(self, path):
        self._uri = Path(path).as_uri()

    def get_activation_uri(self):
        return self._uri


class _FakeFileWithMime(_FakeFile):
    def __init__(self, path, mime, name=None):
        super().__init__(path)
        self._mime = mime
        self._name = name or Path(path).name

    def get_mime_type(self):
        return self._mime

    def get_name(self):
        return self._name


class CopyOpsTests(unittest.TestCase):
    def _make(self, config_overrides=None):
        config = {
            "separator": ", ",
            "copy": {
                "selections": {"clipboard": True, "primary": False},
                "escape_value_items": False,
                "escape_value": False,
                "item": {"copy_name": {"ignore_extension": False}},
            },
        }
        if config_overrides:
            for key, value in config_overrides.items():
                if key == "copy":
                    config["copy"].update(value)
                else:
                    config[key] = value
        clipboard = mock.Mock()
        primary = mock.Mock()
        ops = CopyOps(config, clipboard, primary)
        return ops, clipboard, primary

    def test_selections_primary_respected_when_false(self):
        # Regression: the user's selections config used to be ignored.
        ops, clipboard, primary = self._make()
        ops.copy_paths(None, [_FakeFile("/tmp/a.txt")])
        clipboard.set.assert_called_once()
        primary.set.assert_not_called()

    def test_selections_primary_copies_when_enabled(self):
        ops, clipboard, primary = self._make({"copy": {"selections": {"clipboard": True, "primary": True}}})
        ops.copy_paths(None, [_FakeFile("/tmp/a.txt")])
        primary.set.assert_called_once()

    def test_joins_paths_with_separator(self):
        ops, clipboard, _ = self._make({"separator": "\n"})
        ops.copy_paths(None, [_FakeFile("/tmp/a.txt"), _FakeFile("/tmp/b.txt")])
        self.assertEqual(clipboard.set.call_args.args[0], "/tmp/a.txt\n/tmp/b.txt")

    def test_escape_value_items_quotes_each_item(self):
        ops, clipboard, _ = self._make({"copy": {"escape_value_items": True}})
        ops.copy_paths(None, [_FakeFile("/tmp/my file.txt")])
        value = clipboard.set.call_args.args[0]
        self.assertIn("/tmp/my", value)
        self.assertIn("'", value)

    def test_copy_uris(self):
        ops, clipboard, _ = self._make()
        ops.copy_uris(None, [_FakeFile("/tmp/a.txt")])
        self.assertEqual(clipboard.set.call_args.args[0], "file:///tmp/a.txt")

    def test_copy_content_reads_text_file(self):
        # Regression: Nautilus 50 removed FileInfo.get_size(); copy_content
        # must fall back to the local path instead of crashing.
        with tempfile.TemporaryDirectory() as root:
            p = Path(root, "a.txt")
            p.write_text("hello")
            fake = _FakeFileWithMime(str(p), "text/plain")
            ops, clipboard, _ = self._make()
            ops.copy_content(None, fake)
            self.assertEqual(clipboard.set.call_args.args[0], "hello")

    def test_copy_content_skips_oversized_file(self):
        with tempfile.TemporaryDirectory() as root:
            p = Path(root, "big.txt")
            p.write_bytes(b"x" * (MAX_FILE_CONTENT_COPY + 1))
            fake = _FakeFileWithMime(str(p), "text/plain")
            ops, clipboard, _ = self._make()
            ops.copy_content(None, fake)
            clipboard.set.assert_not_called()


if __name__ == "__main__":
    unittest.main()
