import os
import unittest
from unittest import mock

from modules.launch_ops import LaunchOps, _clean_exec
from modules.file_utils import find_terminal


class LaunchOpsTests(unittest.TestCase):
    def test_clean_exec_strips_field_codes(self):
        self.assertEqual(_clean_exec("gedit %F"), "gedit")
        self.assertEqual(_clean_exec("gedit -n %f"), "gedit -n")
        self.assertEqual(_clean_exec("%f %U cmd"), "cmd")

    def test_find_terminal_preserves_full_command(self):
        # Regression: only cmd[0] + "-e" used to be returned, dropping flags.
        terminal_ops = mock.Mock()
        terminal_ops.get_terminals.return_value = [
            ("Ptyxis", {"cmd": ["ptyxis", "--new-window", "-d", "{path}"]})
        ]
        prefix = find_terminal(terminal_ops)
        self.assertEqual(prefix, ["ptyxis", "--new-window", "-d", mock.ANY, "-e"])
        self.assertEqual(prefix[3], os.path.expanduser("~"))

    def test_find_terminal_flatpak_uses_flatpak_run(self):
        terminal_ops = mock.Mock()
        terminal_ops.get_terminals.return_value = [
            ("Ptyxis", {"_flatpak": True, "flatpak": ["app.devsuite.Ptyxis", "--new-window", "-d", "{path}"]})
        ]
        prefix = find_terminal(terminal_ops)
        self.assertEqual(prefix[:2], ["flatpak", "run"])
        self.assertEqual(prefix[-1], "-e")

    def test_find_terminal_falls_back_to_common_binary(self):
        with mock.patch("modules.file_utils.find_binary") as find_binary:
            find_binary.return_value = "/usr/bin/kitty"
            prefix = find_terminal(None)
        self.assertEqual(prefix, ["/usr/bin/kitty", "-e"])

    def test_find_terminal_none_when_unavailable(self):
        with mock.patch("modules.file_utils.find_binary", return_value=None):
            self.assertIsNone(find_terminal(None))


if __name__ == "__main__":
    unittest.main()
