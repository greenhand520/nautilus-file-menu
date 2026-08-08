import os
import shlex
from urllib.parse import urlparse, unquote
from .notify import notify
from translation import Translation


class CopyOps:
    def __init__(self, config, clipboard, primary_clipboard):
        self.config = config
        self.clipboard = clipboard
        self.primary_clipboard = primary_clipboard

    def copy_paths(self, menu, files):
        def _uri_to_path(file):
            p = urlparse(file.get_activation_uri())
            return os.path.abspath(os.path.join(p.netloc, unquote(p.path)))

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
        allow_copy_content = ["application/x-shellscript", "application/json", ]
        content = []
        file_type = file.get_mime_type()
        if file_type in allow_copy_content or file_type.startswith("text/"):
            p = urlparse(file.get_activation_uri())
            p = os.path.abspath(os.path.join(p.netloc, unquote(p.path)))
            with open(p, 'r') as _file:
                content.append(_file.read())

        self._copy_value(content)
        notify(Translation.t("notify_file_contents_copied").format(file.get_name()))

    def _copy_value(self, value):
        if len(value) > 0:
            copy_cfg = self.config.get("copy", {})

            if copy_cfg.get("escape_value_items", False):
                value = list(map(lambda x: shlex.quote(x), value))

            new_value = self.config.get("separator", ", ").join(value)

            if copy_cfg.get("escape_value", False):
                new_value = shlex.quote(new_value)

            selections = self.config.get("selections", {"clipboard": True, "primary": True})
            if selections.get("clipboard", True):
                self.clipboard.set(new_value)

            if selections.get("primary", False):
                self.primary_clipboard.set(new_value)
