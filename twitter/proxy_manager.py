# 代理管理模块
# 自动从 webshare.io 获取和切换代理

import requests
import logging
from typing import List, Optional, Dict
from dataclasses import dataclass
import time
import random

logger = logging.getLogger(__name__)


@dataclass
class ProxyInfo:
    """代理信息"""
    host: str
    port: int
    username: str
    password: str
    protocol: str = "http"

    def to_url(self) -> str:
        """转换为代理 URL 格式"""
        return f"{self.protocol}://{self.username}:{self.password}@{self.host}:{self.port}"

    def __str__(self) -> str:
        return f"{self.host}:{self.port}"


class ProxyManager:
    """代理管理器 - 自动获取和切换 webshare.io 代理"""

    def __init__(self, api_key: str, auto_refresh: bool = True, refresh_interval: int = 86400):
        """
        初始化代理管理器

        Args:
            api_key: webshare.io API Key
            auto_refresh: 是否自动刷新代理列表
            refresh_interval: 刷新间隔（秒），默认 24 小时
        """
        self.api_key = api_key
        self.auto_refresh = auto_refresh
        self.refresh_interval = refresh_interval

        self.proxies: List[ProxyInfo] = []
        self.failed_proxies: Dict[str, int] = {}  # 记录失败次数
        self.current_index: int = 0
        self.last_refresh_time: float = 0

        # 初始化时加载代理列表
        self.refresh_proxies()

    def refresh_proxies(self) -> bool:
        """
        从 webshare.io API 获取代理列表

        Returns:
            bool: 成功返回 True
        """
        try:
            logger.info("正在从 webshare.io 获取代理列表...")

            url = "https://proxy.webshare.io/api/v2/proxy/list/"
            headers = {
                "Authorization": f"Token {self.api_key}"
            }
            params = {
                "mode": "direct",  # 直接模式
                "page": 1,
                "page_size": 100
            }

            response = requests.get(url, headers=headers, params=params, timeout=30)

            if response.status_code == 200:
                data = response.json()
                results = data.get("results", [])

                new_proxies = []
                for proxy_data in results:
                    proxy = ProxyInfo(
                        host=proxy_data.get("proxy_address"),
                        port=proxy_data.get("port"),
                        username=proxy_data.get("username"),
                        password=proxy_data.get("password"),
                        protocol="http"
                    )
                    new_proxies.append(proxy)

                if new_proxies:
                    self.proxies = new_proxies
                    self.current_index = 0
                    self.failed_proxies.clear()
                    self.last_refresh_time = time.time()

                    logger.info(f"✓ 成功获取 {len(self.proxies)} 个代理")
                    return True
                else:
                    logger.warning("✗ API 返回的代理列表为空")
                    return False
            else:
                logger.error(f"✗ 获取代理失败: {response.status_code} - {response.text}")
                return False

        except Exception as e:
            logger.error(f"✗ 获取代理时出错: {str(e)}")
            return False

    def get_proxy(self, username: str = None) -> Optional[str]:
        """
        获取一个可用代理（自动轮换）

        Args:
            username: 账号用户名（用于绑定特定代理，可选）

        Returns:
            str: 代理 URL，如 "http://user:pass@host:port"
        """
        # 检查是否需要刷新代理列表
        if self.auto_refresh and time.time() - self.last_refresh_time > self.refresh_interval:
            logger.info("代理列表已过期，正在刷新...")
            self.refresh_proxies()

        if not self.proxies:
            logger.error("✗ 没有可用的代理")
            return None

        # 如果指定了用户名，尝试为该用户返回固定代理
        if username:
            # 使用用户名的哈希值选择固定的代理
            index = hash(username) % len(self.proxies)
            proxy = self.proxies[index]

            # 检查该代理是否失败次数过多
            if self.failed_proxies.get(str(proxy), 0) >= 3:
                logger.warning(f"代理 {proxy} 失败次数过多，切换到下一个")
                return self._get_next_available_proxy()

            return proxy.to_url()

        # 否则轮换返回代理
        return self._get_next_available_proxy()

    def _get_next_available_proxy(self) -> Optional[str]:
        """获取下一个可用代理"""
        max_attempts = len(self.proxies)

        for _ in range(max_attempts):
            proxy = self.proxies[self.current_index]
            self.current_index = (self.current_index + 1) % len(self.proxies)

            # 跳过失败次数过多的代理
            if self.failed_proxies.get(str(proxy), 0) >= 3:
                continue

            return proxy.to_url()

        # 如果所有代理都失败了，清空失败记录并重试
        logger.warning("所有代理都失败了，重置失败计数")
        self.failed_proxies.clear()

        if self.proxies:
            return self.proxies[0].to_url()

        return None

    def mark_proxy_failed(self, proxy_url: str):
        """
        标记代理失败

        Args:
            proxy_url: 失败的代理 URL
        """
        # 从 URL 提取 host:port
        try:
            if "@" in proxy_url:
                host_port = proxy_url.split("@")[1]
            else:
                host_port = proxy_url.split("://")[1] if "://" in proxy_url else proxy_url

            self.failed_proxies[host_port] = self.failed_proxies.get(host_port, 0) + 1
            logger.warning(f"代理 {host_port} 失败次数: {self.failed_proxies[host_port]}")

        except Exception as e:
            logger.error(f"标记代理失败时出错: {str(e)}")

    def mark_proxy_success(self, proxy_url: str):
        """
        标记代理成功（清除失败记录）

        Args:
            proxy_url: 成功的代理 URL
        """
        try:
            if "@" in proxy_url:
                host_port = proxy_url.split("@")[1]
            else:
                host_port = proxy_url.split("://")[1] if "://" in proxy_url else proxy_url

            if host_port in self.failed_proxies:
                del self.failed_proxies[host_port]
                logger.info(f"代理 {host_port} 恢复正常")

        except Exception as e:
            logger.error(f"标记代理成功时出错: {str(e)}")

    def get_stats(self) -> dict:
        """获取代理统计信息"""
        return {
            "total_proxies": len(self.proxies),
            "failed_proxies": len(self.failed_proxies),
            "current_index": self.current_index,
            "last_refresh": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(self.last_refresh_time))
        }
