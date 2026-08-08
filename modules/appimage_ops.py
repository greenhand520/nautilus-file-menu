import os
import subprocess

from .file_utils import uri_to_path as _uri_to_path
from .notify import logger, notify
import translation


def is_appimage(path):
    """Check if a file is an AppImage (by extension only)."""
    return path.endswith(".AppImage") and os.path.isfile(path)


class AppImageOps:
    def extract(self, menu, files):
        """Extract selected AppImage files to their parent directories."""
        appimages = []
        for f in files:
            path = _uri_to_path(f)
            if is_appimage(path):
                appimages.append(path)

        if not appimages:
            return

        logger.debug("AppImage extract: %d file(s)", len(appimages))

        passed = 0
        for path in appimages:
            parent = os.path.dirname(path)
            name = os.path.basename(path)
            extract_dir = os.path.join(parent, os.path.splitext(name)[0] + "_extracted")

            # Add execute permission if missing, restore after extraction
            need_restore = not os.access(path, os.X_OK)
            if need_restore:
                logger.info("Adding execute permission: %s", name)
                os.chmod(path, os.stat(path).st_mode | 0o111)

            logger.info("Extracting AppImage: %s → %s", path, extract_dir)

            try:
                result = subprocess.run(
                    [path, "--appimage-extract"],
                    cwd=parent,
                    capture_output=True, text=True, timeout=300,
                )
                # AppImage extracts to squashfs-root/ in cwd by default
                squashfs = os.path.join(parent, "squashfs-root")
                # Restore original permissions
                if need_restore:
                    os.chmod(path, os.stat(path).st_mode & ~0o111)

                if os.path.isdir(squashfs):
                    if os.path.exists(extract_dir):
                        import shutil
                        shutil.rmtree(extract_dir)
                    os.rename(squashfs, extract_dir)
                    passed += 1
                    logger.info("Extracted: %s", extract_dir)
                else:
                    logger.warning("AppImage extract: no squashfs-root found for %s", name)
            except subprocess.TimeoutExpired:
                logger.error("AppImage extract timeout: %s", name)
            except Exception as e:
                logger.exception("AppImage extract failed: %s, cause: %s", name, e)

        if passed > 0:
            notify(
                translation.gettext("notify_appimage_extract_done"),
                translation.gettext("notify_appimage_extract_count") % {"count": passed},
            )
        else:
            notify(
                translation.gettext("notify_appimage_extract_done"),
                translation.gettext("notify_appimage_extract_failed"),
            )
