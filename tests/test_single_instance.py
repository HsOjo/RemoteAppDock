"""单实例管理相关测试。"""

import time
import uuid

import pytest

from remoteappdock.single_instance import SingleInstanceManager


def _unique_names():
    """生成互不冲突的互斥体/窗口类名，避免测试间相互干扰。"""
    suffix = uuid.uuid4().hex[:12]
    return (
        fr"Local\RemoteAppDock_Test_Mutex_{suffix}",
        f"RemoteAppDock_TestSingleInstance_{suffix}",
    )


class TestSingleInstanceManager:
    def test_first_instance_acquires_mutex(self):
        mutex_name, class_name = _unique_names()
        mgr = SingleInstanceManager(
            mutex_name=mutex_name,
            window_class_name=class_name,
        )
        assert mgr.try_acquire() is True
        assert mgr.is_first_instance() is True
        mgr.release()

    def test_second_instance_fails_to_acquire(self):
        mutex_name, class_name = _unique_names()
        first = SingleInstanceManager(
            mutex_name=mutex_name,
            window_class_name=class_name,
        )
        assert first.try_acquire() is True
        try:
            second = SingleInstanceManager(
                mutex_name=mutex_name,
                window_class_name=class_name,
            )
            assert second.try_acquire() is False
            assert second.is_first_instance() is False
            second.release()
        finally:
            first.release()

    def test_activation_message_received(self):
        mutex_name, class_name = _unique_names()
        activated = []

        def on_activate():
            activated.append(True)

        first = SingleInstanceManager(
            mutex_name=mutex_name,
            window_class_name=class_name,
            on_activate=on_activate,
        )
        assert first.try_acquire() is True
        first.start_listener()
        try:
            second = SingleInstanceManager(
                mutex_name=mutex_name,
                window_class_name=class_name,
            )
            assert second.try_acquire() is False
            assert second.activate_existing_instance() is True
            second.release()

            deadline = time.time() + 2.0
            while time.time() < deadline and not activated:
                first.process_activate_event()
                time.sleep(0.01)
            assert activated
        finally:
            first.release()

    def test_release_is_idempotent(self):
        mutex_name, class_name = _unique_names()
        mgr = SingleInstanceManager(
            mutex_name=mutex_name,
            window_class_name=class_name,
        )
        assert mgr.try_acquire() is True
        mgr.start_listener()
        mgr.release()
        mgr.release()  # 不应抛出异常
