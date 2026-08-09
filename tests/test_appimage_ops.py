import tempfile
import unittest
from pathlib import Path
from unittest import mock

from modules.appimage_ops import AppImageOps, _unique_extract_dir


class AppImageOpsTests(unittest.TestCase):
    def test_unique_extract_dir_appends_suffix(self):
        with tempfile.TemporaryDirectory() as root:
            Path(root, "app_extracted").mkdir()
            result = _unique_extract_dir(root, "app_extracted")
            self.assertEqual(result, str(Path(root, "app_extracted_1")))

    def test_unique_extract_dir_free_name(self):
        with tempfile.TemporaryDirectory() as root:
            result = _unique_extract_dir(root, "app_extracted")
            self.assertEqual(result, str(Path(root, "app_extracted")))

    def test_extract_one_success_renames_to_unique_dir(self):
        with tempfile.TemporaryDirectory() as root:
            appimage = Path(root, "app.AppImage")
            appimage.write_text("ELF")
            appimage.chmod(0o755)  # already executable -> no permission dance
            squashfs = Path(root, "squashfs-root")

            proc = mock.Mock()
            proc.poll.return_value = 0
            proc.returncode = 0

            def _spawn(*args, **kwargs):
                squashfs.mkdir()  # pretend --appimage-extract produced it
                return proc

            with mock.patch("modules.appimage_ops.subprocess.Popen", side_effect=_spawn), \
                 mock.patch("modules.appimage_ops.os.rename") as rename:
                ok = AppImageOps()._extract_one(str(appimage))

            self.assertTrue(ok)
            rename.assert_called_once_with(str(squashfs), str(Path(root, "app_extracted")))

    def test_extract_one_does_not_clobber_existing_dir(self):
        # Regression: an existing "name_extracted" dir used to be silently removed.
        with tempfile.TemporaryDirectory() as root:
            appimage = Path(root, "app.AppImage")
            appimage.write_text("ELF")
            appimage.chmod(0o755)
            existing = Path(root, "app_extracted")
            existing.mkdir()
            keep_file = existing / "keep.txt"
            keep_file.write_text("keep")
            squashfs = Path(root, "squashfs-root")

            proc = mock.Mock()
            proc.poll.return_value = 0
            proc.returncode = 0

            def _spawn(*args, **kwargs):
                squashfs.mkdir()
                return proc

            with mock.patch("modules.appimage_ops.subprocess.Popen", side_effect=_spawn), \
                 mock.patch("modules.appimage_ops.os.rename") as rename:
                ok = AppImageOps()._extract_one(str(appimage))

            self.assertTrue(ok)
            self.assertTrue(keep_file.exists())
            rename.assert_called_once_with(str(squashfs), str(Path(root, "app_extracted_1")))

    def test_extract_one_restores_permissions_on_failure(self):
        # Regression: the execute bit added before extraction was never restored
        # when the process could not be started.
        with tempfile.TemporaryDirectory() as root:
            appimage = Path(root, "app.AppImage")
            appimage.write_text("ELF")
            appimage.chmod(0o644)  # not executable -> need_restore True

            with mock.patch(
                "modules.appimage_ops.subprocess.Popen",
                side_effect=FileNotFoundError,
            ), mock.patch("modules.appimage_ops.os.chmod") as chmod:
                ok = AppImageOps()._extract_one(str(appimage))

            self.assertFalse(ok)
            # One call to add the exec bit, one call to restore it.
            self.assertEqual(chmod.call_count, 2)

    def test_extract_one_times_out(self):
        with tempfile.TemporaryDirectory() as root:
            appimage = Path(root, "app.AppImage")
            appimage.write_text("ELF")
            appimage.chmod(0o755)

            proc = mock.Mock()
            proc.poll.return_value = None  # never finishes

            with mock.patch("modules.appimage_ops.subprocess.Popen", return_value=proc), \
                 mock.patch("modules.appimage_ops.EXTRACT_TIMEOUT", 0), \
                 mock.patch("modules.appimage_ops.time.sleep"), \
                 mock.patch("modules.appimage_ops._terminate") as terminate:
                ok = AppImageOps()._extract_one(str(appimage))

            self.assertFalse(ok)
            terminate.assert_called_once_with(proc)

    def test_extract_one_nonzero_exit_fails(self):
        with tempfile.TemporaryDirectory() as root:
            appimage = Path(root, "app.AppImage")
            appimage.write_text("ELF")
            appimage.chmod(0o755)

            proc = mock.Mock()
            proc.poll.return_value = 1
            proc.returncode = 1

            with mock.patch("modules.appimage_ops.subprocess.Popen", return_value=proc), \
                 mock.patch("modules.appimage_ops.os.rename") as rename:
                ok = AppImageOps()._extract_one(str(appimage))

            self.assertFalse(ok)
            rename.assert_not_called()


if __name__ == "__main__":
    unittest.main()
