import unittest

from modules.ide_ops import _DEFAULT_EXCLUDE_MIME, _get_exclude_mime, is_openable_in_editor


class _FakeFile:
    def __init__(self, mime):
        self._mime = mime

    def get_mime_type(self):
        return self._mime


class ExcludeMimeTests(unittest.TestCase):
    def test_octet_stream_and_msword_are_separate_entries(self):
        # Regression: a missing comma used to concatenate these two prefixes.
        self.assertIn("application/octet-stream", _DEFAULT_EXCLUDE_MIME)
        self.assertIn("application/msword", _DEFAULT_EXCLUDE_MIME)
        self.assertNotIn("application/octet-streamapplication/msword", _DEFAULT_EXCLUDE_MIME)

    def test_merges_user_exclude(self):
        merged = _get_exclude_mime({"open_ide": {"exclude_mime": ["custom/x-foo"]}})
        self.assertIn("custom/x-foo", merged)
        self.assertIn("video/", merged)

    def test_is_file_openable_in_ide_excludes_video(self):
        self.assertFalse(is_openable_in_editor(_FakeFile("video/mp4"), {"open_ide": {}}))

    def test_is_file_openable_in_ide_excludes_msword(self):
        self.assertFalse(is_openable_in_editor(_FakeFile("application/msword"), {"open_ide": {}}))

    def test_is_file_openable_in_ide_allows_text(self):
        self.assertTrue(is_openable_in_editor(_FakeFile("text/plain"), {"open_ide": {}}))


if __name__ == "__main__":
    unittest.main()
