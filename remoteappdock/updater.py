"""检查 GitHub Releases 更新。

实现参考 Rosser 后端 app/core/updater.py，适配为桌面应用可直接调用的同步接口。
为不阻塞 UI，实际请求应放在 QThread 中执行。
"""

from __future__ import annotations

import logging
import re
import time
import urllib.request
from dataclasses import dataclass
from typing import Optional

import httpx
from bs4 import BeautifulSoup

from remoteappdock.version import APP_VERSION, GITHUB_OWNER, GITHUB_REPO


logger = logging.getLogger(__name__)


@dataclass
class Release:
    """GitHub Release 信息。"""

    name: str
    tag_name: str
    published_at: str
    html_url: str
    body: str
    download_url: Optional[str]
    assets: list[dict[str, str]]


# 内存缓存：避免频繁访问 GitHub 页面触发速率限制
_update_cache: tuple[Release, bool, float] | None = None
CACHE_TTL = 300  # seconds


DEFAULT_TIMEOUT = 5.0
USER_AGENT = f"RemoteAppDock/{APP_VERSION} (+https://github.com/{GITHUB_OWNER}/{GITHUB_REPO})"


def _norm_version(v: str) -> list[int]:
    """将版本字符串归一化为整数列表，忽略前缀 v/V 与预发布标记。"""
    v = (v or "").lstrip("vV").split("-")[0]
    parts = []
    for x in v.split("."):
        try:
            parts.append(int(x))
        except ValueError:
            parts.append(0)
    return parts


def _get_system_proxy() -> str | dict[str, str] | None:
    """读取系统代理设置，兼容环境变量与 Windows 注册表。

    httpx 默认只读取 HTTP_PROXY/HTTPS_PROXY 等环境变量，不会主动读取操作
    系统代理配置；这里使用 urllib.request.getproxies() 统一获取，保证打包后
    的桌面应用仍能复用用户已配置的系统代理。

    返回 httpx 0.28+ 可直接使用的代理配置：
    - None：未配置代理；
    - str：单一代理 URL（http 与 https 指向同一代理时合并为字符串）；
    - dict：按协议区分的代理 URL（仅在 http/https 指向不同代理时）。
    """
    proxies = urllib.request.getproxies()
    if not proxies:
        return None

    http = proxies.get("http")
    https = proxies.get("https")
    if http and http == https:
        return http

    result: dict[str, str] = {}
    if http:
        result["http://"] = http
    if https:
        result["https://"] = https
    return result or None


def compare_version(current: str, latest: str) -> bool:
    """Return True if `latest` is strictly newer than `current`.

    预发布版本（含 '-'）不被视为正式新版本。
    """
    if "-" in latest:
        return False
    a, b = _norm_version(current), _norm_version(latest)
    n = max(len(a), len(b))
    a += [0] * (n - len(a))
    b += [0] * (n - len(b))
    return b > a


def _fetch_page(client: httpx.Client, url: str, timeout: float = DEFAULT_TIMEOUT) -> str:
    """发起 GET 请求并返回 HTML 文本。"""
    resp = client.get(url, timeout=timeout, follow_redirects=True)
    resp.raise_for_status()
    return resp.text


def _create_client() -> httpx.Client:
    """创建使用系统代理的 httpx 客户端。"""
    proxy = _get_system_proxy()
    if proxy is None:
        return httpx.Client(headers={"User-Agent": USER_AGENT})
    if isinstance(proxy, str):
        return httpx.Client(headers={"User-Agent": USER_AGENT}, proxy=proxy)
    mounts = {scheme: httpx.HTTPTransport(proxy=url) for scheme, url in proxy.items()}
    return httpx.Client(headers={"User-Agent": USER_AGENT}, mounts=mounts)


def get_latest_release(timeout: float = DEFAULT_TIMEOUT) -> Release:
    """从 GitHub Releases 公开页面解析最新 Release。

    GitHub 未认证 REST API 的速率限制很低，因此采用 HTML 页面抓取。
    """
    releases_url = f"https://github.com/{GITHUB_OWNER}/{GITHUB_REPO}/releases"
    with _create_client() as client:
        html = _fetch_page(client, releases_url, timeout)
    soup = BeautifulSoup(html, "html.parser")

    tag_link = soup.find(
        "a",
        href=re.compile(rf"^/{GITHUB_OWNER}/{GITHUB_REPO}/releases/tag/"),
    )
    if not tag_link:
        raise ValueError("在 GitHub Releases 页面未找到 Release 标签")

    href = tag_link.get("href", "")
    tag_name = href.split("/")[-1]
    html_url = f"https://github.com{href}"
    name = tag_link.text.strip()

    published_at = ""
    body = ""
    section = tag_link.find_parent("section")
    if section:
        time_tag = section.find("relative-time")
        if time_tag:
            published_at = (time_tag.get("datetime") or "").replace("T", " ").replace("Z", "")
        body_tag = section.find("div", class_="markdown-body")
        if body_tag:
            body = body_tag.get_text("\n").strip()

    download_url = None
    assets: list[dict[str, str]] = []
    assets_url = f"https://github.com/{GITHUB_OWNER}/{GITHUB_REPO}/releases/expanded_assets/{tag_name}"
    try:
        with _create_client() as client:
            assets_html = _fetch_page(client, assets_url, timeout)
        assets_soup = BeautifulSoup(assets_html, "html.parser")
        asset_links = assets_soup.find_all(
            "a",
            href=re.compile(rf"^/{GITHUB_OWNER}/{GITHUB_REPO}/releases/download/"),
        )
        for asset_link in asset_links:
            href = asset_link.get("href", "")
            if href:
                assets.append({
                    "name": asset_link.text.strip(),
                    "url": f"https://github.com{href}",
                })
        if assets:
            download_url = assets[0]["url"]
    except Exception:
        # 资源列表是可选的；解析失败时仍返回 Release 基本信息。
        logger.debug("解析 Release 资源列表失败", exc_info=True)

    return Release(
        name=name,
        tag_name=tag_name,
        published_at=published_at,
        html_url=html_url,
        body=body,
        download_url=download_url,
        assets=assets,
    )


def check_update(timeout: float = DEFAULT_TIMEOUT, force: bool = False) -> tuple[Optional[Release], bool]:
    """获取最新 Release 并判断是否存在新版本。

    结果会缓存 CACHE_TTL 秒以减少对 GitHub 的请求；force=True 可跳过缓存。
    """
    global _update_cache

    now = time.time()
    if not force and _update_cache is not None and (now - _update_cache[2]) < CACHE_TTL:
        return _update_cache[0], _update_cache[1]

    release = get_latest_release(timeout=timeout)
    have_new = compare_version(APP_VERSION, release.tag_name)
    _update_cache = (release, have_new, now)
    return release, have_new


def invalidate_update_cache() -> None:
    """清除缓存，主要用于测试。"""
    global _update_cache
    _update_cache = None
