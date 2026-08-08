# Nautilus File Menu

A feature-rich right-click context menu extension for Nautilus (GNOME Files).

**Note⚠️: Only tested on Gnome 50**

## Features

### Copy Operations
- **Copy Path** — Copy the absolute file/folder path to clipboard
- **Copy URI** — Copy the file URI (`file:///...`)
- **Copy Name** — Copy the file name (optionally strip extension)
- **Copy Content** — Copy the content of text files

### Folder Operations
- **Dissolve Folder** — Move all files from a folder to its parent, then delete the empty folder
  - Confirmation dialog before operation
  - Supports dissolving multiple folders at once
  - Symbolic link folders are automatically skipped
- **Move into Folder** — Create a new folder and move all selected files into it

### Open with IDE
- Auto-detects installed IDEs (binary → desktop file → flatpak)
- Supports VSCode, Code-OSS, Zed, and all JetBrains IDEs
- Single IDE shows directly, multiple IDEs in submenu
- Also available when right-clicking folder background

### Open in Terminal
- Auto-detects installed terminals (native binary → flatpak)
- Supports Ptyxis, Ghostty, Kitty, Alacritty, WezTerm
- Per-terminal command configuration with `{path}` placeholder
- Single terminal shows directly, multiple terminals in submenu
- Only appears when right-clicking a directory or folder background

### Checksum
- Supported algorithms: MD5, SHA1, SHA256, SHA512 (configurable)
- Results automatically copied to clipboard

## Installation

### Dependencies

```bash
# Arch Linux
sudo pacman -S python-nautilus python-gobject

# Ubuntu / Debian
sudo apt install python3-nautilus python3-gi

# Fedora
sudo dnf install nautilus-python python3-gobject
```

### Install

```bash
git clone <repo-url>
cd nautilus-file-menu
make install
nautilus -q  # Restart Nautilus
```

### Uninstall

```bash
make uninstall
nautilus -q
```

## Configuration

Edit `config.json` (installed at `~/.local/share/nautilus-python/extensions/nautilus-file-menu/config.json`):

### Global Settings

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `language` | string | `"auto"` | UI language. `"auto"` detects from system locale, or set to `"en"`, `"zh_CN"`, etc. |
| `log_level` | string | `"WARNING"` | Log level: `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`. Logs are written to `extension.log` in the extension directory. |
| `separator` | string | `"\n"` | Separator for joining multiple values when copying paths/names/URIs. |

### ops_enabled — Feature Toggles

Toggle which features appear in the context menu:

```json
"ops_enabled": {
  "copy": true,
  "dissolve_folder": true,
  "move_into_folder": true,
  "open_ide": true,
  "open_terminal": true,
  "checksum": true
}
```

### copy — Copy Operations

```json
"copy": {
  "item": {
    "copy_path":  { "enabled": true, "shortcut": "<Ctrl><Shift>C" },
    "copy_uri":   { "enabled": true, "shortcut": "<Ctrl><Shift>U" },
    "copy_name":  { "enabled": true, "shortcut": "<Ctrl><Shift>D", "ignore_extension": false },
    "copy_content": { "enabled": true, "shortcut": "<Ctrl><Shift>G" }
  },
  "collapse_menu": true,
  "selections": { "clipboard": true, "primary": true },
  "escape_value_items": false,
  "escape_value": false
}
```

| Key | Description |
|-----|-------------|
| `item.*.enabled` | Show/hide individual copy items |
| `item.*.shortcut` | Keyboard shortcut (GTK accelerator format) |
| `item.copy_name.ignore_extension` | Strip file extension when copying name |
| `collapse_menu` | `true`: fold into "Copy More" submenu; `false`: list all directly |
| `selections.clipboard` | Copy to system clipboard |
| `selections.primary` | Copy to primary clipboard (middle-click paste) |
| `escape_value_items` | Shell-escape each individual value |
| `escape_value` | Shell-escape the final joined value |

### open_ide — IDE Configuration

```json
"open_ide": {
  "other_ides": {
    "Visual Studio Code": {
      "enabled": true,
      "cmd": "code",
      "flatpak_id": "com.visualstudio.code"
    }
  },
  "jetbrains_ides": {
    "collapse_menu": false,
    "PyCharm": { "enabled": true, "cmd": "pycharm" }
  }
}
```

| Key | Description |
|-----|-------------|
| `other_ides.<name>.enabled` | Enable/disable this IDE |
| `other_ides.<name>.cmd` | Binary name (searched in PATH, `~/.local/bin`, `/usr/local/bin`) |
| `other_ides.<name>.flatpak_id` | Flatpak app ID as fallback when native binary is not found |
| `jetbrains_ides.collapse_menu` | `true`: fold JetBrains into submenu; `false`: list directly in IDE menu |
| `jetbrains_ides.<name>.enabled` | Enable/disable this JetBrains IDE |
| `jetbrains_ides.<name>.cmd` | Binary name (also searches JetBrains Toolbox directories) |

### open_terminal — Terminal Configuration

```json
"open_terminal": {
  "terminals": {
    "Ptyxis": {
      "enabled": true,
      "cmd": ["ptyxis", "--new-window", "-d", "{path}"],
      "flatpak_id": "app.devsuite.Ptyxis",
      "flatpak_args": ["--new-window", "-d", "{path}"]
    },
    "WezTerm": {
      "enabled": true,
      "cmd": ["wezterm", "start", "--cwd", "{path}"],
      "flatpak_id": ""
    }
  },
  "collapse_menu": true
}
```

| Key | Description |
|-----|-------------|
| `terminals.<name>.enabled` | Enable/disable this terminal |
| `terminals.<name>.cmd` | Command array. `{path}` is replaced with the target directory at runtime |
| `terminals.<name>.flatpak_id` | Flatpak app ID as fallback (leave empty to skip flatpak detection) |
| `terminals.<name>.flatpak_args` | Arguments for flatpak launch (optional, only used when launched via flatpak) |
| `collapse_menu` | `true`: fold into "Open in Terminal" submenu; `false`: list all directly |

### checksum_algorithms — Checksum Configuration

```json
"checksum_algorithms": {
  "enabled": ["md5", "sha1", "sha256", "sha512"]
}
```

| Key | Description |
|-----|-------------|
| `enabled` | List of hash algorithms to show in the checksum submenu. Supported: `md5`, `sha1`, `sha256`, `sha512` |

## Translation

Uses GNU gettext. Translation files are in `po/`:

```bash
make xgettext    # Extract translatable strings from source
make msgmerge    # Update .po files from .pot template
make msgfmt      # Compile .po to .mo binary
make i18n        # Full pipeline: extract → merge → compile
```

## Supported Languages

- English (`en`)
- Chinese Simplified (`zh_CN`)

## References

- [nautilus-copy-path](https://github.com/chr314/nautilus-copy-path)
- [nautilus-open-in-ptyxis](github.com/GustavoWidman/nautilus-open-in-ptyxis)
- [wezterm](https://github.com/wez/wezterm)
- [python-nautilus](https://github.com/GNOME/python-nautilus)

## Customization

Edit `config.json` to customize the extension's behavior. The file is located at:

```
~/.local/share/nautilus-python/extensions/nautilus-file-menu/config.json
```

After editing, restart Nautilus to apply changes:

```bash
nautilus -q
```

See the [Configuration](#configuration) section above for all available options.

## License

MIT
