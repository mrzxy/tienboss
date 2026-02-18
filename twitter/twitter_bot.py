"""
Twitter 自动发帖机器人
通过 MQTT 监听发帖指令，支持多账号管理
"""

import json
import logging
import time
import sys
import os
import tempfile
import threading
import requests
from typing import Dict, Optional, List
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

from twitter_api import TwitterAPI
from accounts import get_account_by_username, get_all_enabled_accounts, TwitterAccount
from emqx import MQTTClient, MQTTConfig
from config import API_KEY, WEBSHARE_API_KEY, PROXY_AUTO_REFRESH, PROXY_REFRESH_INTERVAL
from proxy_manager import ProxyManager

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('twitter_bot.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


class TwitterBot:
    """Twitter 多账号管理机器人"""

    def __init__(self, api_key: str, webshare_api_key: str = None):
        """
        初始化 Twitter 机器人

        Args:
            api_key: TwitterAPI.io 的 API 密钥
            webshare_api_key: Webshare.io 的 API 密钥（可选）
        """
        self.api_key = api_key
        self.mqtt_client: Optional[MQTTClient] = None

        # 代理管理器
        self.proxy_manager: Optional[ProxyManager] = None
        if webshare_api_key:
            logger.info("初始化代理管理器...")
            self.proxy_manager = ProxyManager(
                api_key=webshare_api_key,
                auto_refresh=PROXY_AUTO_REFRESH,
                refresh_interval=PROXY_REFRESH_INTERVAL
            )
            logger.info(f"✓ 代理管理器初始化完成，共 {len(self.proxy_manager.proxies)} 个代理")

        # 账号管理：username -> TwitterAPI 实例
        self.twitter_clients: Dict[str, TwitterAPI] = {}

        # 统计信息
        self.stats = {
            'total_tweets': 0,
            'success_tweets': 0,
            'failed_tweets': 0,
            'start_time': datetime.now()
        }

        # 监听线程管理：username -> Thread
        self._monitor_threads: Dict[str, threading.Thread] = {}
        self._monitor_stop_events: Dict[str, threading.Event] = {}

    def initialize_accounts(self):
        """初始化所有启用的 Twitter 账号"""
        logger.info("=" * 60)
        logger.info("开始初始化 Twitter 账号")
        logger.info("=" * 60)

        accounts = get_all_enabled_accounts()

        if not accounts:
            logger.error("未找到任何启用的账号，请检查 accounts.py 配置")
            return False

        logger.info(f"找到 {len(accounts)} 个启用的账号")

        success_count = 0
        for account in accounts:
            if self._login_account(account):
                success_count += 1

        logger.info("=" * 60)
        logger.info(f"账号初始化完成: 成功 {success_count}/{len(accounts)}")
        logger.info("=" * 60)

        return success_count > 0

    def start_monitors(self):
        """为所有配置了 monitor_targets 的已登录账号启动监听线程"""
        accounts = get_all_enabled_accounts()
        for account in accounts:
            if account.monitor_targets and account.username in self.twitter_clients:
                self._start_monitor(account)

    def _start_monitor(self, account: TwitterAccount):
        """为单个账号启动监听线程"""
        username = account.username
        if username in self._monitor_threads and self._monitor_threads[username].is_alive():
            logger.info(f"账号 @{username} 的监听线程已在运行")
            return

        stop_event = threading.Event()
        self._monitor_stop_events[username] = stop_event

        thread = threading.Thread(
            target=self._monitor_loop,
            args=(account, stop_event),
            name=f"monitor-{username}",
            daemon=True
        )
        self._monitor_threads[username] = thread
        thread.start()
        logger.info(f"✓ 已启动账号 @{username} 的监听线程，监听目标: {account.monitor_targets}")

    def _monitor_loop(self, account: TwitterAccount, stop_event: threading.Event,
                      check_interval: int = 10):
        """
        监听循环，定期检查目标账号的新推文

        Args:
            account: 本账号配置（提供 api_key/proxy）
            stop_event: 停止信号
            check_interval: 检查间隔（秒），默认 300
        """
        url = "https://api.twitterapi.io/twitter/tweet/advanced_search"
        headers = {"X-API-Key": self.api_key}

        # 每个目标账号独立维护 last_checked_time
        last_checked: Dict[str, datetime] = {
            target: datetime.now(timezone.utc).replace(tzinfo=None)
            for target in account.monitor_targets
        }

        # 美东时间区（ET，夏令时 UTC-4，冬令时 UTC-5，用 pytz 或固定偏移均可）
        try:
            import zoneinfo
            ET = zoneinfo.ZoneInfo("America/New_York")
        except ImportError:
            from datetime import timezone as _tz
            ET = _tz(timedelta(hours=-5))  # 退化为 UTC-5（EST）

        def _is_weekend_quiet() -> bool:
            """判断当前是否处于美东时间 周五 19:00 ~ 周一 07:00 静默窗口"""
            now_et = datetime.now(ET)
            wd = now_et.weekday()  # 0=Mon … 4=Fri 5=Sat 6=Sun
            h = now_et.hour
            # 周六 / 周日 全天
            if wd in (5, 6):
                return True
            # 周五 19:00 之后
            if wd == 4 and h >= 19:
                return True
            # 周一 07:00 之前
            if wd == 0 and h < 7:
                return True
            return False

        logger.info(f"[monitor@{account.username}] 开始监听: {account.monitor_targets}")

        _in_quiet = False  # 追踪静默状态，避免重复日志

        while not stop_event.is_set():
            # 静默窗口：周五 19:00 ~ 周一 07:00（美东时间），跳过本轮请求
            if _is_weekend_quiet():
                if not _in_quiet:
                    logger.info(f"[monitor@{account.username}] 进入周末静默窗口，暂停监听")
                    _in_quiet = True
                stop_event.wait(check_interval)
                continue
            if _in_quiet:
                logger.info(f"[monitor@{account.username}] 退出周末静默窗口，恢复监听")
                _in_quiet = False

            for target in account.monitor_targets:
                if stop_event.is_set():
                    break
                try:
                    until_time = datetime.now(timezone.utc).replace(tzinfo=None)
                    since_time = last_checked[target]

                    since_str = since_time.strftime("%Y-%m-%d_%H:%M:%S_UTC")
                    until_str = until_time.strftime("%Y-%m-%d_%H:%M:%S_UTC")

                    query = f"from:{target} since:{since_str} until:{until_str} -filter:replies -filter:quote"
                    params = {"query": query, "queryType": "Latest"}

                    all_tweets = []
                    next_cursor = None

                    while True:
                        if next_cursor:
                            params["cursor"] = next_cursor

                        proxy_url = account.proxy
                        if not proxy_url and self.proxy_manager:
                            proxy_url = self.proxy_manager.get_proxy(username=account.username)

                        proxies = {"http": proxy_url, "https": proxy_url} if proxy_url else None
                        response = requests.get(url, headers=headers, params=params,
                                                proxies=proxies, timeout=30)

                        if response.status_code == 200:
                            data = response.json()
                            tweets = data.get("tweets", [])
                            if tweets:
                                all_tweets.extend(tweets)
                            if data.get("has_next_page") and data.get("next_cursor"):
                                next_cursor = data["next_cursor"]
                                continue
                        else:
                            logger.warning(f"[monitor@{account.username}] 请求失败 {response.status_code}: {response.text}")
                        break

                    if all_tweets:
                        logger.info(f"[monitor@{account.username}] @{target} 有 {len(all_tweets)} 条新推文")
                        for tweet in all_tweets:
                            logger.info(f"  [{tweet.get('createdAt')}] {tweet.get('text', '')}")
                            self._on_new_tweet(account, target, tweet)

                    last_checked[target] = until_time

                except Exception as e:
                    logger.error(f"[monitor@{account.username}] 监听 @{target} 异常: {e}")

            stop_event.wait(check_interval)

        logger.info(f"[monitor@{account.username}] 监听线程已停止")

    def _on_new_tweet(self, account: TwitterAccount, target_username: str, tweet: dict):
        """
        收到新推文时的回调，子类可重写此方法实现自定义处理

        Args:
            account: 监听所属账号
            target_username: 被监听的目标账号
            tweet: 推文数据
        """
        content = tweet.get('text', '')
        payload = {
            "sender": "sam",
            "content": content,
            "target_id": "1345761025684934748/1441624375194423368",
        }
        if '🚩' in content:
            payload["target_id"] =  "1345761025684934748/1441624282252710109"

        self.mqtt_client.publish('lis-msg-v2', json.dumps(payload))

        pass

    def stop_monitors(self):
        """停止所有监听线程"""
        for username, stop_event in self._monitor_stop_events.items():
            stop_event.set()
        for username, thread in self._monitor_threads.items():
            thread.join(timeout=5)
        logger.info("✓ 所有监听线程已停止")

    def _login_account(self, account: TwitterAccount, retry_count: int = 3) -> bool:
        """
        登录单个 Twitter 账号（支持代理自动切换）

        Args:
            account: Twitter 账号配置
            retry_count: 重试次数

        Returns:
            bool: 登录成功返回 True
        """
        for attempt in range(retry_count):
            try:
                logger.info(f"正在登录账号: @{account.username} (尝试 {attempt + 1}/{retry_count})")

                # 创建 TwitterAPI 实例（每个账号使用独立的 cookies 文件，避免多账号冲突）
                current_dir = os.path.dirname(os.path.abspath(__file__))
                cookies_file = os.path.join(current_dir, f".twitter_cookies_{account.username}.json")
                twitter = TwitterAPI(api_key=self.api_key, cookies_file=cookies_file)

                # 决定使用哪个代理
                proxy = account.proxy  # 优先使用账号配置的代理

                # 如果账号没有配置代理，或者上次登录失败，使用代理管理器
                if not proxy and self.proxy_manager:
                    proxy = self.proxy_manager.get_proxy(username=account.username)
                    logger.info(f"使用代理管理器分配的代理: {proxy}")
                elif attempt > 0 and self.proxy_manager:
                    # 如果不是第一次尝试，切换到新代理
                    if proxy:
                        self.proxy_manager.mark_proxy_failed(proxy)
                    proxy = self.proxy_manager.get_proxy(username=account.username)
                    logger.info(f"切换到新代理: {proxy}")

                # 检查 proxy 是否为 None（TwitterAPI 要求必须提供 proxy）
                if not proxy:
                    logger.error(f"✗ 无法获取可用代理，跳过账号 @{account.username}")
                    return False

                # 尝试登录
                success = twitter.authenticate(
                    user_name=account.username,
                    email=account.email,
                    password=account.password,
                    proxy=proxy,
                    totp_secret=account.totp_secret
                )

                if success:
                    self.twitter_clients[account.username] = twitter
                    logger.info(f"✓ 账号 @{account.username} 登录成功")

                    # 标记代理成功
                    if proxy and self.proxy_manager:
                        self.proxy_manager.mark_proxy_success(proxy)

                    return True
                else:
                    logger.error(f"✗ 账号 @{account.username} 登录失败")

                    # 标记代理失败
                    if proxy and self.proxy_manager:
                        self.proxy_manager.mark_proxy_failed(proxy)

                    # 如果还有重试次数，等待一下再重试
                    if attempt < retry_count - 1:
                        time.sleep(2)

            except Exception as e:
                logger.error(f"✗ 账号 @{account.username} 登录异常: {str(e)}")
                if attempt < retry_count - 1:
                    time.sleep(2)

        return False

    def setup_mqtt(self):
        """设置 MQTT 连接"""
        logger.info("=" * 60)
        logger.info("初始化 MQTT 客户端")
        logger.info("=" * 60)

        try:
            # 创建 MQTT 配置
            mqtt_config = MQTTConfig(
                client_id=f"twitter_bot_{int(time.time())}"
            )

            # 创建 MQTT 客户端
            self.mqtt_client = MQTTClient(mqtt_config)

            # 设置连接回调
            self.mqtt_client.set_connection_callback(self._on_mqtt_connected)

            # 连接到 MQTT 服务器
            if self.mqtt_client.connect():
                logger.info("✓ MQTT 连接成功")
                return True
            else:
                logger.error("✗ MQTT 连接失败")
                return False

        except Exception as e:
            logger.error(f"✗ MQTT 初始化异常: {str(e)}")
            return False

    def _on_mqtt_connected(self, client, userdata, flags, rc):
        """MQTT 连接成功回调"""
        logger.info("MQTT 连接成功回调触发，开始订阅主题")

        # 订阅发帖主题
        self.mqtt_client.subscribe("/x/post", callback=self._handle_post_message)
        logger.info("✓ 已订阅主题: /x/post")

    def _process_and_upload_files(self, files: list, twitter_client, proxy: Optional[str] = None) -> list:
        """
        处理文件列表（本地文件或 URL），上传并返回 media_ids

        Args:
            files: 文件路径或 URL 列表
            twitter_client: TwitterAPI 客户端实例
            proxy: 可选的代理服务器

        Returns:
            list: 上传成功的 media_id 列表
        """
        if not files:
            return []

        logger.info(f"检测到 {len(files)} 个文件需要上传")
        uploaded_media_ids = []
        temp_dir = None
        downloaded_files = []

        try:
            # 创建临时目录用于存放下载的文件
            temp_dir = tempfile.mkdtemp(prefix='twitter_media_')

            for file_or_url in files:
                file_path = None

                # 判断是 URL 还是本地文件路径
                if file_or_url.startswith('http://') or file_or_url.startswith('https://'):
                    # 是 URL，需要先下载
                    logger.info(f"检测到 URL: {file_or_url}")
                    file_path = self._download_file_from_url(file_or_url, temp_dir)

                    if file_path:
                        downloaded_files.append(file_path)
                    else:
                        logger.error(f"✗ 无法下载文件: {file_or_url}")
                        continue
                else:
                    # 是本地文件路径
                    if os.path.exists(file_or_url):
                        file_path = file_or_url
                        logger.info(f"使用本地文件: {file_path}")
                    else:
                        logger.error(f"✗ 本地文件不存在: {file_or_url}")
                        continue

                # 上传文件
                if file_path:
                    logger.info(f"上传文件: {os.path.basename(file_path)}")
                    media_id = twitter_client.upload_media(
                        file_path=file_path,
                        proxy=proxy
                    )

                    if media_id:
                        uploaded_media_ids.append(media_id)
                        logger.info(f"✓ 文件上传成功: {os.path.basename(file_path)} -> {media_id}")
                    else:
                        logger.error(f"✗ 文件上传失败: {file_path}")

            # 输出统计信息
            if uploaded_media_ids:
                logger.info(f"✓ 共上传 {len(uploaded_media_ids)} 个文件，media_ids: {uploaded_media_ids}")
            else:
                logger.warning("所有文件上传失败")

        finally:
            # 清理临时文件（上传完成后立即清理，无需等待发布推文）
            if temp_dir and os.path.exists(temp_dir):
                try:
                    cleaned_count = 0
                    for file_path in downloaded_files:
                        if os.path.exists(file_path):
                            os.remove(file_path)
                            cleaned_count += 1

                    # 删除临时目录
                    os.rmdir(temp_dir)

                    if cleaned_count > 0:
                        logger.info(f"✓ 已清理 {cleaned_count} 个临时文件和目录")
                except Exception as e:
                    logger.warning(f"⚠ 清理临时文件失败: {str(e)}")

        return uploaded_media_ids

    def _download_file_from_url(self, url: str, temp_dir: str) -> Optional[str]:
        """
        从 URL 下载文件到临时目录

        Args:
            url: 文件的 URL 地址
            temp_dir: 临时目录路径

        Returns:
            str: 下载成功返回本地文件路径，失败返回 None
        """
        try:
            logger.info(f"正在下载文件: {url}")

            # 发送 GET 请求下载文件
            response = requests.get(url, timeout=30, stream=True)

            if response.status_code != 200:
                logger.error(f"✗ 下载失败: HTTP {response.status_code}")
                return None

            # 从 URL 或 Content-Disposition 获取文件名
            parsed_url = urlparse(url)
            filename = os.path.basename(parsed_url.path)

            # 如果没有文件名，使用时间戳
            if not filename or '.' not in filename:
                content_type = response.headers.get('Content-Type', '')
                ext = '.jpg'  # 默认扩展名
                if 'png' in content_type:
                    ext = '.png'
                elif 'gif' in content_type:
                    ext = '.gif'
                elif 'webp' in content_type:
                    ext = '.webp'
                elif 'video' in content_type:
                    ext = '.mp4'
                filename = f"download_{int(time.time())}{ext}"

            # 保存文件
            file_path = os.path.join(temp_dir, filename)

            with open(file_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)

            file_size = os.path.getsize(file_path)
            logger.info(f"✓ 文件下载成功: {filename} ({file_size} bytes)")
            return file_path

        except requests.exceptions.Timeout:
            logger.error(f"✗ 下载超时: {url}")
            return None
        except requests.exceptions.RequestException as e:
            logger.error(f"✗ 下载失败: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"✗ 下载过程出错: {str(e)}")
            return None

    def _handle_post_message(self, topic: str, payload: str, msg):
        """
        处理 MQTT 发帖消息

        消息格式：
        {
            "username": "account1",
            "text": "推文内容",
            "files": [
                "/path/to/image1.jpg",              // 本地文件路径
                "https://example.com/image2.png"    // 或 URL 地址（会自动下载）
            ],  // 可选，图片文件路径或 URL 列表
            "media_ids": ["media_id1", "media_id2"],  // 可选，已有的 media_id
            "reply_to_tweet_id": "123456",            // 可选
            "attachment_url": "https://...",          // 可选
            "community_id": "123456",                 // 可选
            "is_note_tweet": false,                   // 可选
            "proxy": "http://proxy:port"              // 可选
        }
        """
        try:
            logger.info(f"收到发帖消息: {payload}")

            # 解析 JSON
            data = json.loads(payload)

            # 验证必需字段
            if 'user_name' not in data:
                logger.error("消息缺少 user_name 字段")
                return

            if 'text' not in data:
                logger.error("消息缺少 text 字段")
                return

            username = data['user_name']
            username = "professorr_pvt"
            text = data['text']
            media_ids = data.get('media_ids', [])
            files = data.get('files', [])
            reply_to_tweet_id = data.get('reply_to_tweet_id')
            attachment_url = data.get('attachment_url')
            community_id = data.get('community_id')
            is_note_tweet = data.get('is_note_tweet', False)

            # 从消息中获取 proxy，如果没有则从代理管理器获取
            proxy = data.get('proxy')
            if not proxy and self.proxy_manager:
                proxy = self.proxy_manager.get_proxy(username=username)
                logger.info(f"使用代理管理器分配的代理: {proxy}")

            # 查找对应的 Twitter 客户端
            twitter_client = self.twitter_clients.get(username)

            if not twitter_client:
                logger.error(f"未找到账号 @{username} 的登录实例")
                self.stats['failed_tweets'] += 1
                return

            # 如果有文件需要上传，先上传获取 media_ids
            if files:
                uploaded_media_ids = self._process_and_upload_files(
                    files=files,
                    twitter_client=twitter_client,
                    proxy=proxy
                )

                # 合并上传的 media_ids 和已有的 media_ids
                if uploaded_media_ids:
                    media_ids = media_ids + uploaded_media_ids if media_ids else uploaded_media_ids

            # 发布推文
            logger.info(f"使用账号 @{username} 发布推文...")
            self.stats['total_tweets'] += 1

            result = twitter_client.post_tweet(
                text=text,
                media_ids=media_ids if media_ids else None,
                reply_to_tweet_id=reply_to_tweet_id,
                attachment_url=attachment_url,
                community_id=community_id,
                is_note_tweet=is_note_tweet,
                proxy=proxy
            )

            if result:
                self.stats['success_tweets'] += 1
                logger.info(f"✓ 推文发布成功 - 账号: @{username}")
                logger.info(f"  推文 ID: {result.get('id', 'N/A')}")
                logger.info(f"  内容: {text[:50]}...")
            else:
                self.stats['failed_tweets'] += 1
                logger.error(f"✗ 推文发布失败 - 账号: @{username}")

        except json.JSONDecodeError as e:
            logger.error(f"JSON 解析失败: {str(e)}")
            self.stats['failed_tweets'] += 1
        except Exception as e:
            logger.error(f"处理消息异常: {str(e)}")
            self.stats['failed_tweets'] += 1

    def print_stats(self):
        """打印统计信息"""
        runtime = datetime.now() - self.stats['start_time']

        logger.info("=" * 60)
        logger.info("运行统计")
        logger.info("=" * 60)
        logger.info(f"运行时间: {runtime}")
        logger.info(f"已登录账号数: {len(self.twitter_clients)}")
        logger.info(f"总推文数: {self.stats['total_tweets']}")
        logger.info(f"成功: {self.stats['success_tweets']}")
        logger.info(f"失败: {self.stats['failed_tweets']}")
        logger.info("=" * 60)

    def run(self):
        """运行机器人"""
        logger.info("\n" + "=" * 60)
        logger.info("🐦 Twitter 自动发帖机器人启动".center(60))
        logger.info("=" * 60 + "\n")

        try:
            # 1. 初始化 Twitter 账号
            if not self.initialize_accounts():
                logger.error("没有成功登录的账号，程序退出")
                return

            # 2. 启动监听线程
            self.start_monitors()

            # 3. 设置 MQTT 连接
            if not self.setup_mqtt():
                logger.error("MQTT 连接失败，程序退出")
                return

            logger.info("\n" + "=" * 60)
            logger.info("✓ 机器人启动成功，等待 MQTT 消息...".center(60))
            logger.info("=" * 60)
            logger.info("发送 JSON 消息到 /x/post 主题来发推文")
            logger.info('格式: {"username": "账号", "text": "内容"}')
            logger.info("按 Ctrl+C 停止程序")
            logger.info("=" * 60 + "\n")

            # 3. 保持运行，每隔一段时间打印统计
            try:
                counter = 0
                while True:
                    time.sleep(60)  # 每 60 秒
                    counter += 1

                    # 每 10 分钟打印一次统计
                    if counter % 1440 == 0:
                        self.print_stats()

            except KeyboardInterrupt:
                logger.info("\n收到停止信号，正在关闭...")

        finally:
            # 清理资源
            self.stop_monitors()
            if self.mqtt_client:
                self.mqtt_client.disconnect()

            self.print_stats()
            logger.info("✓ 机器人已停止")


def main():
    """主函数"""
    # 创建机器人实例
    bot = TwitterBot(api_key=API_KEY, webshare_api_key=WEBSHARE_API_KEY)

    # 运行机器人
    bot.run()


if __name__ == "__main__":
    main()
