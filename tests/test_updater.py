"""Tests for remoteappdock.updater."""

import time
import unittest
from unittest.mock import Mock, patch

from remoteappdock import updater
from remoteappdock.version import APP_VERSION


class TestVersionComparison(unittest.TestCase):
    """版本号比较测试。"""

    def test_latest_newer(self):
        self.assertTrue(updater.compare_version("0.1.0", "0.2.0"))

    def test_current_newer(self):
        self.assertFalse(updater.compare_version("0.2.0", "0.1.0"))

    def test_equal(self):
        self.assertFalse(updater.compare_version("0.1.0", "0.1.0"))

    def test_prefix_v_ignored(self):
        self.assertTrue(updater.compare_version("0.1.0", "v0.2.0"))

    def test_prerelease_ignored(self):
        self.assertFalse(updater.compare_version("0.1.0", "0.2.0-beta"))

    def test_different_part_count(self):
        self.assertTrue(updater.compare_version("0.1.0", "0.1.0.1"))
        self.assertFalse(updater.compare_version("0.1.0.1", "0.1.0"))


class TestSystemProxy(unittest.TestCase):
    """系统代理读取测试。"""

    def test_returns_none_when_no_proxy(self):
        with patch("remoteappdock.updater.urllib.request.getproxies", return_value={}):
            self.assertIsNone(updater._get_system_proxy())

    def test_merges_same_http_https_proxy(self):
        with patch(
            "remoteappdock.updater.urllib.request.getproxies",
            return_value={"http": "http://127.0.0.1:7890", "https": "http://127.0.0.1:7890"},
        ):
            self.assertEqual(updater._get_system_proxy(), "http://127.0.0.1:7890")

    def test_keeps_different_proxies(self):
        with patch(
            "remoteappdock.updater.urllib.request.getproxies",
            return_value={"http": "http://127.0.0.1:7890", "https": "http://127.0.0.1:7891"},
        ):
            self.assertEqual(
                updater._get_system_proxy(),
                {"http://": "http://127.0.0.1:7890", "https://": "http://127.0.0.1:7891"},
            )

    def test_passes_proxy_to_httpx_client(self):
        html = """
        <html>
        <body>
            <a href="/HsOjo/RemoteAppDock/releases/tag/0.3.0">0.3.0</a>
            <section><relative-time datetime="2026-07-23T12:00:00Z"></relative-time></section>
        </body>
        </html>
        """
        with patch("remoteappdock.updater._get_system_proxy", return_value="http://127.0.0.1:7890"):
            client = Mock()
            client.get = lambda url, **kwargs: Mock(text=html, raise_for_status=Mock())
            client.__enter__ = Mock(return_value=client)
            client.__exit__ = Mock(return_value=False)

            with patch("remoteappdock.updater.httpx.Client", return_value=client) as mock_client:
                updater.get_latest_release()

        self.assertTrue(mock_client.called)
        for call in mock_client.call_args_list:
            _, kwargs = call
            self.assertEqual(kwargs["proxy"], "http://127.0.0.1:7890")

    def test_passes_mounts_to_httpx_client_for_split_proxy(self):
        html = """
        <html>
        <body>
            <a href="/HsOjo/RemoteAppDock/releases/tag/0.3.0">0.3.0</a>
            <section><relative-time datetime="2026-07-23T12:00:00Z"></relative-time></section>
        </body>
        </html>
        """
        proxy_config = {"http://": "http://127.0.0.1:7890", "https://": "http://127.0.0.1:7891"}
        with patch("remoteappdock.updater._get_system_proxy", return_value=proxy_config):
            client = Mock()
            client.get = lambda url, **kwargs: Mock(text=html, raise_for_status=Mock())
            client.__enter__ = Mock(return_value=client)
            client.__exit__ = Mock(return_value=False)

            with patch("remoteappdock.updater.httpx.Client", return_value=client) as mock_client:
                updater.get_latest_release()

        self.assertTrue(mock_client.called)
        for call in mock_client.call_args_list:
            _, kwargs = call
            self.assertIn("mounts", kwargs)
            self.assertEqual(set(kwargs["mounts"].keys()), {"http://", "https://"})


class TestGetLatestRelease(unittest.TestCase):
    """GitHub Releases 页面解析测试。"""

    def _make_client(self, html: str, assets_html: str = ""):
        client = Mock()
        responses = {
            f"https://github.com/{updater.GITHUB_OWNER}/{updater.GITHUB_REPO}/releases": html,
            f"https://github.com/{updater.GITHUB_OWNER}/{updater.GITHUB_REPO}/releases/expanded_assets/v0.2.0": assets_html,
        }

        def get(url, **kwargs):
            resp = Mock()
            resp.text = responses.get(url, "")
            resp.raise_for_status = Mock()
            return resp

        client.get = get
        client.__enter__ = Mock(return_value=client)
        client.__exit__ = Mock(return_value=False)
        return client

    def test_parses_release(self):
        html = """
        <html>
        <body>
            <section>
                <a href="/HsOjo/RemoteAppDock/releases/tag/v0.2.0">RemoteAppDock 0.2.0</a>
                <relative-time datetime="2026-07-23T12:00:00Z">Jul 23, 2026</relative-time>
                <div class="markdown-body">Release notes</div>
            </section>
        </body>
        </html>
        """
        assets_html = """
        <html>
        <body>
            <a href="/HsOjo/RemoteAppDock/releases/download/v0.2.0/RemoteAppDock.zip">RemoteAppDock.zip</a>
        </body>
        </html>
        """
        client = self._make_client(html, assets_html)

        with patch("remoteappdock.updater.httpx.Client", return_value=client):
            release = updater.get_latest_release()

        self.assertEqual(release.tag_name, "v0.2.0")
        self.assertEqual(release.name, "RemoteAppDock 0.2.0")
        self.assertEqual(release.published_at, "2026-07-23 12:00:00")
        self.assertEqual(release.body, "Release notes")
        self.assertEqual(release.download_url, "https://github.com/HsOjo/RemoteAppDock/releases/download/v0.2.0/RemoteAppDock.zip")
        self.assertEqual(len(release.assets), 1)
        self.assertEqual(release.assets[0]["name"], "RemoteAppDock.zip")

    def test_no_release_found(self):
        client = self._make_client("<html><body></body></html>")
        with patch("remoteappdock.updater.httpx.Client", return_value=client):
            with self.assertRaises(ValueError):
                updater.get_latest_release()


class TestCheckUpdate(unittest.TestCase):
    """检查更新整体流程测试。"""

    def setUp(self):
        updater.invalidate_update_cache()

    def tearDown(self):
        updater.invalidate_update_cache()

    def test_detects_new_version(self):
        html = """
        <html>
        <body>
            <a href="/HsOjo/RemoteAppDock/releases/tag/0.3.0">0.3.0</a>
            <section><relative-time datetime="2026-07-23T12:00:00Z"></relative-time></section>
        </body>
        </html>
        """
        client = Mock()
        resp = Mock()
        resp.text = html
        resp.raise_for_status = Mock()
        client.get = lambda url, **kwargs: resp
        client.__enter__ = Mock(return_value=client)
        client.__exit__ = Mock(return_value=False)

        with patch("remoteappdock.updater.httpx.Client", return_value=client):
            release, have_new = updater.check_update()

        self.assertTrue(have_new)
        self.assertEqual(release.tag_name, "0.3.0")

    def test_cache_is_used(self):
        html = """
        <html>
        <body>
            <a href="/HsOjo/RemoteAppDock/releases/tag/99.0.0">99.0.0</a>
            <section><relative-time datetime="2026-07-23T12:00:00Z"></relative-time></section>
        </body>
        </html>
        """
        client = Mock()
        resp = Mock()
        resp.text = html
        resp.raise_for_status = Mock()
        client.get = lambda url, **kwargs: resp
        client.__enter__ = Mock(return_value=client)
        client.__exit__ = Mock(return_value=False)

        with patch("remoteappdock.updater.httpx.Client", return_value=client):
            release1, have_new1 = updater.check_update()
            # 强制修改返回内容以验证缓存生效；如果未缓存会返回新的 tag
            resp.text = html.replace("99.0.0", "100.0.0")
            release2, have_new2 = updater.check_update()

        self.assertEqual(release1.tag_name, "99.0.0")
        self.assertEqual(release2.tag_name, "99.0.0")
        self.assertEqual(have_new1, have_new2)

    def test_force_bypasses_cache(self):
        html = """
        <html>
        <body>
            <a href="/HsOjo/RemoteAppDock/releases/tag/0.3.0">0.3.0</a>
            <section><relative-time datetime="2026-07-23T12:00:00Z"></relative-time></section>
        </body>
        </html>
        """
        client = Mock()
        resp = Mock()
        resp.text = html
        resp.raise_for_status = Mock()
        client.get = lambda url, **kwargs: resp
        client.__enter__ = Mock(return_value=client)
        client.__exit__ = Mock(return_value=False)

        with patch("remoteappdock.updater.httpx.Client", return_value=client):
            updater.check_update()
            # 直接修改缓存时间使其过期
            updater._update_cache = (updater._update_cache[0], updater._update_cache[1], time.time() - 600)
            release, have_new = updater.check_update(force=True)

        self.assertEqual(release.tag_name, "0.3.0")
        self.assertTrue(have_new)


if __name__ == "__main__":
    unittest.main()
