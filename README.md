# RemoteAppDock

English | [简体中文](README_CN.md)

A Windows taskbar replacement implemented in Python, designed for RDP RemoteApp environments.

## Scope

- Window management (task list)
- Tray management (notification area)
- Taskbar positioning (AppBar)

Not included: Start menu, theming system, localization, auto-update.

## Tech Stack

- Python 3.13
- PySide6
- ctypes / pywin32
- PyInstaller
- uv

## Project Structure

```text
remoteappdock/
├── main.py
├── app.py
├── config.py
├── models/          # Data models
├── win32/           # Win32 API wrappers
├── services/        # Business services
├── ui/              # PySide6 UI
└── utils/           # Utilities
```

## Development

```powershell
uv sync
uv run python -m remoteappdock.main
```

## Testing

```powershell
uv run pytest
```

## Packaging

```powershell
uv run pyinstaller RemoteAppDock.spec --clean --noconfirm
```

## Acknowledgements

The low-level implementation of the tray protocol and Explorer taskbar control
is derived from and ported after
[ManagedShell](https://github.com/cairoshell/ManagedShell) (C# / .NET, Apache
License 2.0). The affected files carry derivation notices in their headers; see
`NOTICE` for attribution and `third_party/ManagedShell/LICENSE` for the full
Apache-2.0 license text.

## License

RemoteAppDock as a whole is licensed under the [GNU GPL v3](LICENSE) or (at your
option) any later version. The portions ported from ManagedShell are
incorporated under the Apache-2.0 license (which is compatible with GPLv3) and
remain subject to its attribution requirements.
