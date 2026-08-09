import os
import shlex
from .file_utils import uri_to_path as _uri_to_path, COPY_CONTENT_MIME_TYPES
from .notify import notify, logger
import translation

MAX_FILE_CONTENT_COPY = 512 * 1024


class CopyOps:
    def __init__(self, config, clipboard, primary_clipboard):
        self.config = config
        self.clipboard = clipboard
        self.primary_clipboard = primary_clipboard

    def copy_paths(self, menu, files):
        self._copy_value(list(map(_uri_to_path, files)))

    def copy_uris(self, menu, files):
        self._copy_value(list(map(lambda f: f.get_activation_uri(), files)))

    def copy_names(self, menu, files):
        copy_cfg = self.config.get("copy", {})
        ignore_ext = copy_cfg.get("item", {}).get("copy_name", {}).get("ignore_extension", False)

        def _name(file):
            path = unquote(os.path.basename(file.get_activation_uri()))
            if ignore_ext:
                path = os.path.splitext(path)[0]
            return path

        self._copy_value(list(map(_name, files)))

    def copy_content(self, menu, file):
        # Nautilus 50 removed FileInfo.get_size(); use the local path.
        p = _uri_to_path(file)
        try:
            if os.path.getsize(p) > MAX_FILE_CONTENT_COPY:
                return
        except OSError as e:
            logger.error("copy_content: cannot stat %s: %s", p, e)
            return
        content = []
        file_type = file.get_mime_type()
        if file_type in COPY_CONTENT_MIME_TYPES or file_type.startswith("text/"):
            p = _uri_to_path(file)
            logger.debug("copy_content: reading %s", p)
            try:
                with open(p, 'r') as _file:
                    content.append(_file.read())
            except IOError as e:
                logger.error("copy_content: failed to read %s: %s", p, e)

        self._copy_value(content)
        notify(translation.gettext("notify_file_contents_copied") % {"file": file.get_name()})

    def _copy_value(self, value):
        if len(value) > 0:
            copy_cfg = self.config.get("copy", {})

            if copy_cfg.get("escape_value_items", False):
                value = list(map(lambda x: shlex.quote(x), value))

            new_value = self.config.get("separator", ", ").join(value)

            if copy_cfg.get("escape_value", False):
                new_value = shlex.quote(new_value)

            selections = copy_cfg.get("selections", {"clipboard": True, "primary": True})
            if selections.get("clipboard", True):
                self.clipboard.set(new_value)

            if selections.get("primary", False):
                self.primary_clipboard.set(new_value)
