import tempfile
import unittest
from pathlib import Path
from unittest import mock

from modules.folder_ops import FolderOps


class FolderOpsTests(unittest.TestCase):
    def test_dissolve_does_not_delete_source_when_a_move_fails(self):
        with tempfile.TemporaryDirectory() as root:
            folder = Path(root) / "folder"
            folder.mkdir()
            (folder / "a.txt").write_text("data")

            with mock.patch("modules.folder_ops._uri_to_path", return_value=str(folder)), \
                 mock.patch("modules.folder_ops.file_move", return_value=False), \
                 mock.patch("modules.folder_ops.file_delete") as delete:
                FolderOps().dissolve_folder(None, [object()])

            delete.assert_not_called()
            self.assertTrue(folder.exists())

    def test_dissolve_moves_all_items_then_deletes_source(self):
        with tempfile.TemporaryDirectory() as root:
            folder = Path(root) / "folder"
            folder.mkdir()
            (folder / "a.txt").write_text("data")
            (folder / "b.txt").write_text("data")

            with mock.patch("modules.folder_ops._uri_to_path", return_value=str(folder)), \
                 mock.patch("modules.folder_ops.file_move", return_value=True) as move, \
                 mock.patch("modules.folder_ops.file_delete", return_value=True) as delete:
                FolderOps().dissolve_folder(None, [object()])

            self.assertEqual(move.call_count, 2)
            delete.assert_called_once_with(str(folder))


if __name__ == "__main__":
    unittest.main()
