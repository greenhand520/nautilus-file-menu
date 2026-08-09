import unittest
from unittest import mock

from modules.admin_ops import _to_admin_uri, _strip_exec_codes, AdminOps


class AdminOpsTests(unittest.TestCase):
    def test_to_admin_uri_replaces_scheme_only(self):
        self.assertEqual(_to_admin_uri("file:///etc/fstab"), "admin:///etc/fstab")

    def test_to_admin_uri_leaves_non_file_uri_untouched(self):
        self.assertEqual(_to_admin_uri("ftp://host/etc/fstab"), "ftp://host/etc/fstab")

    def test_to_admin_uri_does_not_corrupt_embedded_scheme_text(self):
        self.assertEqual(_to_admin_uri("file:///etc/file://x"), "admin:///etc/file://x")

    def test_strip_exec_codes(self):
        self.assertEqual(_strip_exec_codes("/usr/bin/gedit %F"), "/usr/bin/gedit")
        self.assertEqual(_strip_exec_codes("gedit -n %f"), "gedit -n")
        self.assertEqual(_strip_exec_codes("%f %U cmd"), "cmd")

    def test_editor_command_preserves_exec_args(self):
        app_info = mock.Mock()
        app_info.get_commandline.return_value = "/usr/bin/gedit -n %F"
        args = AdminOps({})._editor_command(app_info)
        self.assertEqual(args, ["/usr/bin/gedit", "-n"])

    def test_editor_command_falls_back_to_executable(self):
        app_info = mock.Mock()
        app_info.get_commandline.return_value = ""
        app_info.get_executable.return_value = "gedit"
        args = AdminOps({})._editor_command(app_info)
        self.assertEqual(args, ["gedit"])

    def test_editor_command_returns_empty_when_nothing(self):
        app_info = mock.Mock()
        app_info.get_commandline.return_value = ""
        app_info.get_executable.return_value = ""
        self.assertEqual(AdminOps({})._editor_command(app_info), [])


if __name__ == "__main__":
    unittest.main()
