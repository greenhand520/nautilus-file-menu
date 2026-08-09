import os
import unittest

from modules.file_utils import uri_to_path, group_paths_by_parent


class _FakeFile:
    def __init__(self, uri):
        self._uri = uri

    def get_activation_uri(self):
        return self._uri


class UriToPathTests(unittest.TestCase):
    def test_plain_file_uri(self):
        self.assertEqual(uri_to_path(_FakeFile("file:///home/user/a.txt")), "/home/user/a.txt")

    def test_localhost_file_uri(self):
        self.assertEqual(uri_to_path(_FakeFile("file://localhost/home/user/a.txt")), "/home/user/a.txt")

    def test_percent_encoded_path(self):
        self.assertEqual(
            uri_to_path(_FakeFile("file:///home/user/my%20file.txt")),
            "/home/user/my file.txt",
        )

    def test_non_file_uri_keeps_host_as_prefix(self):
        expected = os.path.abspath(os.path.join("host", "tmp", "a.txt"))
        self.assertEqual(uri_to_path(_FakeFile("sftp://host/tmp/a.txt")), expected)


class GroupPathsTests(unittest.TestCase):
    def test_groups_by_parent_preserving_order(self):
        result = group_paths_by_parent(["/a/1.txt", "/b/2.txt", "/a/3.txt"])
        self.assertEqual(result, {"/a": ["/a/1.txt", "/a/3.txt"], "/b": ["/b/2.txt"]})


if __name__ == "__main__":
    unittest.main()
