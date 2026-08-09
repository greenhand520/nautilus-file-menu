import os
import subprocess
import time

from gi import require_version

require_version('Gtk', '4.0')
from gi.repository import GLib, Gtk

from .file_utils import uri_to_path as _uri_to_path
from .notify import logger, notify
import translation

# AppImage extraction timeout in seconds. Extraction runs synchronously on the
# main thread (a modal progress dialog keeps the UI responsive), so the bound is
# kept tight to avoid freezing Nautilus on a hung AppImage.
EXTRACT_TIMEOUT = 60


def is_appimage(path):
    """Check if a file is an AppImage (by extension only)."""
    return path.endswith(".AppImage") and os.path.isfile(path)


def _unique_extract_dir(parent, base_name):
    """Return a non-existing extract dir name, appending _1, _2, ... if needed."""
    candidate = os.path.join(parent, base_name)
    counter = 1
    while os.path.exists(candidate):
        candidate = os.path.join(parent, f"{base_name}_{counter}")
        counter += 1
    return candidate


def _terminate(proc):
    """Terminate a subprocess, escalating to kill if it ignores SIGTERM."""
    try:
        proc.terminate()
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()


class AppImageOps:
    def extract(self, menu, files):
        """Extract selected AppImage files to their parent directories.

        Extraction runs synchronously on the main thread so the completion
        notification is sent immediately — no GLib idle/focus dependency that
        could postpone it until Nautilus regains focus. A modal progress dialog
        keeps the UI responsive by pumping the event loop while waiting.
        """
        appimages = []
        for f in files:
            path = _uri_to_path(f)
            if is_appimage(path):
                appimages.append(path)

        if not appimages:
            return

        logger.debug("AppImage extract: %d file(s)", len(appimages))

        win, label, cancel_flag = self._build_dialog(len(appimages))

        passed = 0
        try:
            for i, path in enumerate(appimages, start=1):
                if cancel_flag["cancelled"]:
                    break
                label.set_text(translation.gettext("appimage_extracting").format(
                    name=os.path.basename(path), current=i, total=len(appimages)))
                # Render the dialog before the blocking call starts.
                self._pump_events()
                if self._extract_one(path, win, cancel_flag):
                    passed += 1
        finally:
            win.destroy()

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

    def _build_dialog(self, count):
        win = Gtk.Window(title=translation.gettext("appimage_extracting_title"))
        win.set_modal(True)
        win.set_default_size(360, -1)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        box.set_margin_top(20)
        box.set_margin_bottom(20)
        box.set_margin_start(20)
        box.set_margin_end(20)

        label = Gtk.Label(label="")
        label.set_wrap(True)
        label.set_xalign(0)
        box.append(label)

        progress = Gtk.ProgressBar()
        progress.set_show_text(False)
        progress.pulse()
        box.append(progress)

        # Cancel only makes sense when multiple AppImages are queued up.
        cancel_flag = {"cancelled": False}
        if count > 1:
            cancel_btn = Gtk.Button(label=translation.gettext("dialog_cancel"))
            cancel_btn.connect("clicked", lambda b: cancel_flag.__setitem__("cancelled", True))
            box.append(cancel_btn)

        win.set_child(box)
        win.present()
        return win, label, cancel_flag

    @staticmethod
    def _pump_events():
        """Process pending GTK events so the dialog stays responsive.

        GTK4 removed ``Gtk.events_pending()``/``Gtk.main_iteration()``;
        the equivalent is GLib's main-context API, which also works headless
        (tests) and matches the main loop Nautilus already runs.
        """
        ctx = GLib.MainContext.default()
        while ctx.pending():
            ctx.iteration(False)

    def _extract_one(self, path, win=None, cancel_flag=None):
        """Extract a single AppImage synchronously. Returns True on success.

        ``win``/``cancel_flag`` are optional: pass a window to keep it responsive
        during the wait, or leave them out (tests, headless) for a plain block.
        """
        parent = os.path.dirname(path)
        name = os.path.basename(path)
        # Never clobber an existing directory of the same name.
        extract_dir = _unique_extract_dir(parent, os.path.splitext(name)[0] + "_extracted")

        # Add execute permission if missing, restore afterwards in all cases.
        need_restore = not os.access(path, os.X_OK)
        if need_restore:
            logger.info("Adding execute permission: %s", name)
            os.chmod(path, os.stat(path).st_mode | 0o111)

        try:
            proc = subprocess.Popen(
                [path, "--appimage-extract"],
                cwd=parent,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
            deadline = time.monotonic() + EXTRACT_TIMEOUT
            while proc.poll() is None:
                if cancel_flag is not None and cancel_flag["cancelled"]:
                    _terminate(proc)
                    logger.info("AppImage extract cancelled: %s", name)
                    return False
                if time.monotonic() > deadline:
                    _terminate(proc)
                    logger.error("AppImage extract timeout: %s", name)
                    return False
                if win is not None:
                    self._pump_events()
                time.sleep(0.05)
            if proc.returncode != 0:
                logger.error("AppImage extract failed (exit %s): %s", proc.returncode, name)
                return False
        except Exception as e:
            logger.exception("AppImage extract failed: %s, cause: %s", name, e)
            return False
        finally:
            # Restore original permissions regardless of outcome.
            if need_restore:
                os.chmod(path, os.stat(path).st_mode & ~0o111)

        # AppImage extracts to squashfs-root/ in cwd by default.
        squashfs = os.path.join(parent, "squashfs-root")
        if os.path.isdir(squashfs):
            # extract_dir is guaranteed non-existing, so a plain rename is safe.
            os.rename(squashfs, extract_dir)
            logger.info("Extracted: %s", extract_dir)
            return True

        logger.warning("AppImage extract: no squashfs-root found for %s", name)
        return False
