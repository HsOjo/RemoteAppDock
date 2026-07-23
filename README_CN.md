# RemoteAppDock

![RemoteAppDock 图标](assets/app-icon-256.png)

[English](README.md) | 简体中文

用 Python 实现的 Windows 任务栏替代方案，面向 RDP RemoteApp 环境部署。

## 范围

- 窗口管理（任务列表）
- 托盘管理（通知区域）
- 任务栏定位（AppBar）
- 多语言（i18n）

## 技术栈

- Python 3.13
- PySide6
- ctypes / pywin32
- PyInstaller
- uv

## 开发

```powershell
uv sync
uv run python -m remoteappdock.main
```

## 测试

```powershell
uv run --group dev pytest
```

## 打包

```powershell
uv run python -m PyInstaller RemoteAppDock.spec --clean --noconfirm
```

## 致谢

本项目的托盘协议、Explorer 任务栏控制等底层实现，参考并移植自
[ManagedShell](https://github.com/cairoshell/ManagedShell)（C# / .NET，
Apache License 2.0）。相关文件已在文件头标注衍生关系，归属详见 `NOTICE`，
Apache-2.0 许可全文见 `third_party/ManagedShell/LICENSE`。

## 许可

本项目整体依据 [GNU GPL v3](LICENSE) 或（由你选择）任何更新版本发布。
其中移植自 ManagedShell 的部分依据 Apache-2.0 授权并入本项目（Apache-2.0
与 GPLv3 兼容），需同时遵守其归属要求。
