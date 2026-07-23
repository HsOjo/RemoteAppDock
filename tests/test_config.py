"""配置持久化与国际化相关测试。"""

import json
import os
import tempfile

import pytest
from PySide6.QtCore import QCoreApplication
from PySide6.QtWidgets import QApplication

from remoteappdock.config import AppConfig, WindowGeometry
from remoteappdock.i18n import install_translator, normalize_language


class TestAppConfig:
    def test_default_values(self):
        cfg = AppConfig()
        assert cfg.edge == "bottom"
        assert cfg.geometry.width == 128
        assert cfg.geometry.height == 480

    def test_save_and_load_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "config.json")
            cfg = AppConfig(
                edge="left",
                auto_hide=True,
                geometry=WindowGeometry(x=10, y=20, width=200, height=500),
            )
            cfg.save(path)

            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            assert data["edge"] == "left"
            assert data["geometry"]["x"] == 10

            loaded = AppConfig.load(path)
            assert loaded.edge == "left"
            assert loaded.auto_hide is True
            assert loaded.geometry.x == 10
            assert loaded.geometry.width == 200

    def test_load_missing_file_returns_default(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "not_exists.json")
            loaded = AppConfig.load(path)
            assert loaded.edge == "bottom"


class TestI18N:
    @pytest.fixture
    def qt_app(self):
        app = QApplication.instance() or QApplication([])
        yield app

    def test_normalize_language_auto_uses_system(self):
        lang = normalize_language("auto")
        assert lang in {"zh_CN", "en_US"}

    def test_install_translator_zh_cn(self, qt_app):
        translator = install_translator(qt_app, "zh_CN")
        assert translator is not None
        text = QCoreApplication.translate("TaskbarWindow", "Run")
        assert text == "运行程序"

    def test_install_translator_en_us_returns_none(self, qt_app):
        translator = install_translator(qt_app, "en_US")
        assert translator is None
