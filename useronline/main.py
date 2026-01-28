import discord
import asyncio
import logging
import sys
from typing import Dict, Optional, List
from config import get_config
from proxy_manager import ProxyManager

# 加载配置
app_config = get_config()

# 配置日志
logging.basicConfig(
    level=getattr(logging, app_config.get('logging.level', 'INFO')),
    format=app_config.get('logging.format', '%(asctime)s - %(levelname)s - %(message)s'),
    datefmt=app_config.get('logging.date_format', '%Y-%m-%d %H:%M:%S'),
    handlers=[
        logging.FileHandler('useronline.log'),
        logging.StreamHandler(sys.stdout)
    ],
    force=True
)
logger = logging.getLogger(__name__)

# 设置根日志记录器
root_logger = logging.getLogger()
root_logger.setLevel(getattr(logging, app_config.get('logging.level', 'INFO')))


class UserOnlineClient(discord.Client):
    """单个用户在线客户端"""

    def __init__(self, token: str, index: int, use_proxy: bool = False, proxy_url: Optional[str] = None, *args, **kwargs):
        """
        初始化用户在线客户端

        Args:
            token: Discord 用户 token
            index: 账号索引
            use_proxy: 是否使用代理
            proxy_url: 代理 URL
        """
        self.token = token
        self.index = index
        self.use_proxy = use_proxy
        self.proxy_url = proxy_url
        self.is_connected = False
        self.reconnect_attempts = 0
        self.max_reconnect_attempts = app_config.get('reconnect.max_attempts', 5)
        self.retry_delay = app_config.get('reconnect.retry_delay', 5)
        self.backoff_multiplier = app_config.get('reconnect.backoff_multiplier', 1.5)

        # 设置 intents（尝试不同的方式）
        if 'intents' not in kwargs:
            try:
                intents = discord.Intents.default()
                intents.guilds = True
                intents.members = True
                kwargs['intents'] = intents
            except AttributeError:
                # 如果 Intents 不可用，使用旧版本的方式
                logger.warning(f"[账号 {index}] discord.Intents 不可用，使用默认配置")
                pass

        # 设置代理
        if use_proxy and proxy_url:
            kwargs['proxy'] = proxy_url
            logger.info(f"[账号 {index}] 使用代理: {proxy_url.split('@')[1] if '@' in proxy_url else proxy_url}")
        else:
            logger.info(f"[账号 {index}] 不使用代理")

        try:
            super().__init__(*args, **kwargs)
        except TypeError as e:
            # 如果 intents 参数不被接受，尝试不带 intents 初始化
            if 'intents' in str(e):
                logger.warning(f"[账号 {index}] 移除 intents 参数后重试")
                kwargs.pop('intents', None)
                super().__init__(*args, **kwargs)
            else:
                raise

    async def on_ready(self):
        """客户端就绪回调"""
        self.is_connected = True
        self.reconnect_attempts = 0
        logger.info(f"[账号 {self.index}] ✓ 已登录: {self.user.name} (ID: {self.user.id})")

        # 打印服务器信息
        logger.info(f"[账号 {self.index}] 可访问 {len(self.guilds)} 个服务器")

    async def on_disconnect(self):
        """客户端断开连接回调"""
        self.is_connected = False
        logger.warning(f"[账号 {self.index}] 连接已断开: {self.user.name if self.user else 'Unknown'}")

    async def on_error(self, event):
        """错误处理"""
        logger.error(f"[账号 {self.index}] 发生错误: {event}")
        import traceback
        traceback.print_exc()


class UserOnlineManager:
    """多账号在线管理器"""

    def __init__(self, tokens: List[str], proxy_manager: Optional[ProxyManager] = None):
        """
        初始化多账号在线管理器

        Args:
            tokens: Discord 用户 token 列表
            proxy_manager: 代理管理器（可选）
        """
        self.tokens = tokens
        self.proxy_manager = proxy_manager
        self.clients: Dict[int, UserOnlineClient] = {}
        self.tasks: Dict[int, asyncio.Task] = {}

        # 计算使用代理的账号数量（一半）
        self.proxy_count = int(len(tokens) * app_config.get('proxy.use_proxy_ratio', 0.5))

        logger.info("=" * 60)
        logger.info(f"初始化账号在线管理器: 总账号数 {len(tokens)}, 使用代理 {self.proxy_count} 个")
        logger.info("=" * 60)

    async def start_client(self, index: int, token: str, use_proxy: bool = False):
        """
        启动单个客户端并自动重连

        Args:
            index: 账号索引
            token: Discord token
            use_proxy: 是否使用代理
        """
        retry_count = 0
        max_retries = app_config.get('reconnect.max_attempts', 5)
        retry_delay = app_config.get('reconnect.retry_delay', 5)
        backoff_multiplier = app_config.get('reconnect.backoff_multiplier', 1.5)

        while True:
            try:
                # 获取代理 URL
                proxy_url = None
                if use_proxy and self.proxy_manager:
                    proxy_url = self.proxy_manager.get_proxy(username=f"user_{index}")
                    if not proxy_url:
                        logger.warning(f"[账号 {index}] 无法获取代理，将不使用代理")

                # 创建客户端
                client = UserOnlineClient(
                    token=token,
                    index=index,
                    use_proxy=use_proxy,
                    proxy_url=proxy_url
                )

                self.clients[index] = client

                # 启动客户端
                logger.info(f"[账号 {index}] 正在启动...")
                await client.start(token)

            except discord.LoginFailure as e:
                logger.error(f"[账号 {index}] ✗ 登录失败: Token 无效")
                break  # Token 无效，不再重试

            except Exception as e:
                retry_count += 1
                logger.error(f"[账号 {index}] ✗ 连接失败 (尝试 {retry_count}/{max_retries}): {e}")

                # 如果使用了代理且失败，标记代理失败
                if use_proxy and proxy_url and self.proxy_manager:
                    self.proxy_manager.mark_proxy_failed(proxy_url)

                if retry_count >= max_retries:
                    logger.error(f"[账号 {index}] 达到最大重试次数，停止重连")
                    break

                # 等待后重试（指数退避）
                wait_time = retry_delay * (backoff_multiplier ** (retry_count - 1))
                logger.info(f"[账号 {index}] 将在 {wait_time:.1f} 秒后重试...")
                await asyncio.sleep(wait_time)

            finally:
                # 清理客户端
                if index in self.clients:
                    try:
                        await self.clients[index].close()
                    except:
                        pass
                    del self.clients[index]

    async def start_all(self):
        """启动所有账号"""
        logger.info(f"开始启动 {len(self.tokens)} 个账号...")

        for i, token in enumerate(self.tokens):
            # 前一半使用代理
            use_proxy = i < self.proxy_count

            # 创建任务
            task = asyncio.create_task(
                self.start_client(i, token, use_proxy),
                name=f"client_{i}"
            )
            self.tasks[i] = task

            # 避免同时启动太多连接
            if i < len(self.tokens) - 1:
                await asyncio.sleep(2)

        logger.info("=" * 60)
        logger.info(f"所有账号已启动")
        logger.info("=" * 60)

        # 等待所有任务完成
        await asyncio.gather(*self.tasks.values(), return_exceptions=True)

    async def stop_all(self):
        """停止所有账号"""
        logger.info("正在停止所有账号...")

        # 关闭所有客户端
        for index, client in list(self.clients.items()):
            try:
                await client.close()
                logger.info(f"[账号 {index}] 已停止")
            except Exception as e:
                logger.error(f"[账号 {index}] 停止失败: {e}")

        # 取消所有任务
        for index, task in list(self.tasks.items()):
            if not task.done():
                task.cancel()

        logger.info("所有账号已停止")

    def get_status(self) -> dict:
        """获取所有账号状态"""
        online_count = sum(1 for client in self.clients.values() if client.is_connected)
        return {
            "total": len(self.tokens),
            "online": online_count,
            "offline": len(self.tokens) - online_count,
            "using_proxy": self.proxy_count
        }


async def main():
    """主函数"""
    # 获取 token 列表
    app_key_list = app_config.get_tokens()
    if not app_key_list:
        raise ValueError("Discord token 未配置或为空")

    logger.info(f"加载了 {len(app_key_list)} 个 Discord token")

    # 初始化代理管理器
    proxy_manager = None
    if app_config.get('proxy.enabled', False):
        webshare_api_key = app_config.get('proxy.webshare_api_key', '')
        if webshare_api_key and webshare_api_key != 'YOUR_WEBSHARE_API_KEY':
            logger.info("初始化代理管理器...")
            proxy_manager = ProxyManager(
                api_key=webshare_api_key,
                auto_refresh=True,
                refresh_interval=86400
            )
            logger.info(f"代理管理器初始化完成，可用代理: {len(proxy_manager.proxies)} 个")
        else:
            logger.warning("代理已启用但未配置 API Key，将不使用代理")

    # 创建在线管理器
    manager = UserOnlineManager(app_key_list, proxy_manager)

    try:
        # 启动所有账号
        await manager.start_all()
    except KeyboardInterrupt:
        logger.info("收到中断信号，正在关闭...")
    finally:
        await manager.stop_all()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("程序已退出")
    except Exception as e:
        logger.error(f"程序启动失败: {e}")
        import traceback
        traceback.print_exc()