import tempfile
import unittest
from pathlib import Path
from unittest import mock

from modules.folder_ops import FolderOps, _unique_dst, _is_valid_folder_name


class _FakeWin:
    """Minimal stand-in for the Gtk window; only destroy() is used by the ops."""

    def __init__(self):
        self.destroyed = False

    def destroy(self):
        self.destroyed = True


class _FakeFile:
    def __init__(self, path):
        self._uri = Path(path).as_uri()

    def get_activation_uri(self):
        return self._uri


class FolderOpsTests(unittest.TestCase):
    def test_dissolve_does_not_delete_source_when_a_move_fails(self):
        with tempfile.TemporaryDirectory() as root:
            folder = Path(root) / "folder"
            folder.mkdir()
            (folder / "a.txt").write_text("data")

            with mock.patch("modules.folder_ops.file_move", return_value=False), \
                 mock.patch("modules.folder_ops.file_delete") as delete:
                FolderOps()._do_dissolve(_FakeWin(), [str(folder)])

            delete.assert_not_called()
            self.assertTrue(folder.exists())

    def test_dissolve_moves_all_items_then_deletes_source(self):
        with tempfile.TemporaryDirectory() as root:
            folder = Path(root) / "folder"
            folder.mkdir()
            (folder / "a.txt").write_text("data")
            (folder / "b.txt").write_text("data")

            with mock.patch("modules.folder_ops.file_move", return_value=True) as move, \
                 mock.patch("modules.folder_ops.file_delete", return_value=True) as delete:
                FolderOps()._do_dissolve(_FakeWin(), [str(folder)])

            self.assertEqual(move.call_count, 2)
            delete.assert_called_once_with(str(folder))

    def test_dissolve_keeps_source_when_folder_unreadable(self):
        with tempfile.TemporaryDirectory() as root:
            folder = Path(root) / "folder"
            folder.mkdir()

            with mock.patch("os.listdir", side_effect=PermissionError(13, "denied")), \
                 mock.patch("modules.folder_ops.file_delete") as delete:
                FolderOps()._do_dissolve(_FakeWin(), [str(folder)])

            delete.assert_not_called()

    def test_dissolve_real_files_integration(self):
        with tempfile.TemporaryDirectory() as root:
            folder = Path(root) / "folder"
            folder.mkdir()
            (folder / "a.txt").write_text("data")
            (folder / "b.txt").write_text("data")

            FolderOps()._do_dissolve(_FakeWin(), [str(folder)])

            self.assertFalse(folder.exists())
            self.assertTrue((Path(root) / "a.txt").exists())
            self.assertTrue((Path(root) / "b.txt").exists())

    def test_unique_dst_appends_counter_on_collision(self):
        with tempfile.TemporaryDirectory() as root:
            (Path(root) / "x.txt").write_text("1")
            self.assertEqual(_unique_dst(root, "x.txt"), str(Path(root) / "x_1.txt"))

    def test_unique_dst_returns_original_when_free(self):
        with tempfile.TemporaryDirectory() as root:
            self.assertEqual(_unique_dst(root, "x.txt"), str(Path(root) / "x.txt"))

    def test_is_valid_folder_name(self):
        self.assertTrue(_is_valid_folder_name("New Folder"))
        self.assertTrue(_is_valid_folder_name("data"))
        self.assertFalse(_is_valid_folder_name(""))
        self.assertFalse(_is_valid_folder_name("."))
        self.assertFalse(_is_valid_folder_name(".."))
        self.assertFalse(_is_valid_folder_name("../escape"))
        self.assertFalse(_is_valid_folder_name("a/b"))

    def test_move_into_folder_rejects_unsafe_name(self):
        with tempfile.TemporaryDirectory() as root:
            (Path(root) / "a.txt").write_text("data")
            (Path(root) / "b.txt").write_text("data")
            files = [_FakeFile(str(Path(root) / "a.txt")), _FakeFile(str(Path(root) / "b.txt"))]

            win = _FakeWin()
            FolderOps()._do_move_into_folder(win, "..", files)

            # Dialog stays open and no folder is created.
            self.assertFalse(win.destroyed)
            self.assertEqual(sorted(p.name for p in Path(root).iterdir()), ["a.txt", "b.txt"])

    def test_move_into_folder_moves_files(self):
        with tempfile.TemporaryDirectory() as root:
            (Path(root) / "a.txt").write_text("data")
            (Path(root) / "b.txt").write_text("data")
            files = [_FakeFile(str(Path(root) / "a.txt")), _FakeFile(str(Path(root) / "b.txt"))]

            FolderOps()._do_move_into_folder(_FakeWin(), "New Folder", files)

            new_folder = Path(root) / "New Folder"
            self.assertTrue(new_folder.is_dir())
            self.assertTrue((new_folder / "a.txt").exists())
            self.assertTrue((new_folder / "b.txt").exists())


if __name__ == "__main__":
    unittest.main()
