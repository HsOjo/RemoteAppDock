# RemoteAppDock

用 Python 实现的 Windows 任务栏替代方案，面向 RDP RemoteApp 环境部署。

## 范围

- 窗口管理（任务列表）
- 托盘管理（通知区域）
- 任务栏定位（AppBar）

不包含：开始菜单、主题系统、多语言、自动更新。

## 技术栈

- Python 3.13
- PySide6
- ctypes / pywin32
- PyInstaller
- uv

## 项目结构

```text
remoteappdock/
├── main.py
├── app.py
├── config.py
├── models/          # 数据模型
├── win32/           # Win32 API 封装
├── services/        # 业务服务
├── ui/              # PySide6 UI
└── utils/           # 工具函数
```

## 开发

```powershell
uv sync
uv run python -m remoteappdock.main
```

## 测试

```powershell
uv run pytest
```

## 打包

```powershell
uv run pyinstaller RemoteAppDock.spec --clean --noconfirm
```
