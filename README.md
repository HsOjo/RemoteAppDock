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
