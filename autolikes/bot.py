
import discord
from discord.ext import commands, tasks
import asyncio
import random
import logging
from typing import List, Dict, Optional
import aiohttp
import json
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor
from config import get_config
from helper import get_logger
import urllib.parse

# 加载配置
app_config = get_config()
debug = app_config.is_debug()
logger = get_logger(__name__, app_config.get_logging_config())
listen_channel = app_config.get_listen_channels()

@dataclass
class BotConfig:
    token: str
    name: str
    delay_range: tuple = (1, 60)  # 延迟范围（秒）
    enabled: bool = True


class MasterBot:
    def __init__(self, master_token: str, worker_configs: List[BotConfig]):
        self.proxy_url = app_config.get_proxy_url()
        # 只使用必要的intents，避免需要特权访问
        intents = discord.Intents.default()
        intents.message_content = True  # 读取消息内容
        intents.messages = True  # 接收消息事件
        intents.guilds = True  # 访问服务器信息
        intents.reactions = True  # 处理反应事件
        
        self.master_bot = commands.Bot(
            command_prefix='!',
            intents=intents,
            help_command=None,
            proxy=self.proxy_url
        )
        self.master_token = master_token
        self.worker_configs = worker_configs
        self.workers  = []
        self.message_queue = asyncio.Queue()
        self.active_tasks: Dict[str, asyncio.Task] = {}
        self.session = None
        
        # 设置事件处理器
        self.setup_handlers()
    
    def setup_handlers(self):
        """设置消息处理器"""
        @self.master_bot.event
        async def on_ready():
            logger.info(f'主控Bot已上线: {self.master_bot.user}')
            await self.initialize_workers()
            self.process_queue.start()
        
        @self.master_bot.event
        async def on_message(message):
            # 查找匹配的监听频道配置
            matched_channel = None
            for ch in listen_channel:
                if str(message.channel.id) == str(ch.get('id')):
                    matched_channel = ch
                    break
            
     
            # 未找到匹配频道，直接返回
            if not matched_channel:
                await self.master_bot.process_commands(message)
                return

            # if message.channel.id != 1430131207575965838:
            #     print("跳过")
            #     await self.master_bot.process_commands(message)
            #     return
            
            category = matched_channel.get('category', 'green')
            
            # green分类 1/3概率跳过
            if category == 'green':
                if random.randint(1, 3) == 1:
                    logger.info(f'频道 {message.channel.name} (green) 掷骰子跳过')
                    await self.master_bot.process_commands(message)
                    return
            
            print(f'塞入队列处理，频道: {matched_channel.get("name")}, 分类: {category}')
            # 30秒后加入队列处理
            asyncio.create_task(self._delayed_queue_put({'message': message, 'category': category}, delay=30))
            
            await self.master_bot.process_commands(message)
    
    async def _delayed_queue_put(self, data: dict, delay: int):
        """延迟后将消息加入队列"""
        await asyncio.sleep(delay)
        await self.message_queue.put(data)
    
    async def initialize_workers(self):
        """初始化工作Bot集群"""
        logger.info("正在初始化工作Bot集群...")
        
        # 创建aiohttp会话
        self.session = aiohttp.ClientSession(trust_env=True)
        
        # 为每个工作Bot创建实例
        for config in self.worker_configs:
            if config.enabled:
                worker = WorkerBot(config, self.session, self.proxy_url)
                self.workers.append(worker)
                logger.info(f'已初始化工作Bot: {config.name}')
        
        logger.info(f'工作Bot集群初始化完成，共 {len(self.workers)} 个Bot')
    
    @tasks.loop(seconds=0.1)
    async def process_queue(self):
        """处理消息队列（非阻塞）"""
        if not self.message_queue.empty():
            try:
                data = await asyncio.wait_for(self.message_queue.get(), timeout=0.1)
                await self.dispatch_reaction_tasks(data)
            except asyncio.TimeoutError:
                pass
            except Exception as e:
                logger.error(f"处理消息队列时出错: {e}")
    
    async def dispatch_reaction_tasks(self, data: dict):
        """分发反应任务给所有工作Bot"""
        message = data['message']
        category = data.get('category', 'red')
        
        # 🥳🫡🤑🫶🏻👏🏻👻👊🏻👍🙏🏻👑🌹🔥🥑❤️💯💰📈📝🚀🐐✈️⬆️🫰😄
        emoji_list = ['🥳', '🫡', '🤑', '🫶🏻', '👏🏻', '👻', '👊🏻', '👍🏻', '🙏🏻', '👑', '🌹', '🔥', '🥑', '❤️', '💯', '💰', '📈', '📝', '🚀', '🐐', '✈️', '⬆️', '🫰', '😄']
        
        # 根据category设置不同参数
        if category == 'green':
            # green: 1-3个表情, 每个1-10个
            emoji_count = random.randint(1, 3)
            worker_range = (1, 10)
        else:
            # red (默认): 6-11个表情, 每个5-40个
            emoji_count = random.randint(6, 12)
            worker_range = (5, 40)
        
        selected_emojis = random.sample(emoji_list, min(emoji_count, len(emoji_list)))
        emoji_counts = {emoji: random.randint(*worker_range) for emoji in selected_emojis}
        
        # 为每个emoji选择对应数量的worker
        tasks = []
        for emoji, count in emoji_counts.items():
            # 随机选择count个worker来点这个emoji
            selected_workers = random.sample(self.workers, min(count, len(self.workers)))
            
            for worker in selected_workers:
                # 为每个worker创建异步任务
                task = asyncio.create_task(
                    worker.add_reaction_with_delay(message, emoji)
                )
                tasks.append(task)
                
                # 记录任务用于监控
                task_name = f"{worker.config.name}-{message.id}-{emoji}"
                self.active_tasks[task_name] = task
                
                # 任务完成时清理
                task.add_done_callback(lambda t, name=task_name: self.active_tasks.pop(name, None))
        
        # 不等待任务完成，立即返回
        logger.info(f"已为消息 {message.id} (category: {category}) 分发 {len(tasks)} 个反应任务，emoji分配: {emoji_counts}")
        
        # 可选：后台监控任务完成情况
        asyncio.create_task(self.monitor_tasks_completion(message.id, tasks))
    
    async def monitor_tasks_completion(self, message_id: int, tasks: List[asyncio.Task]):
        """监控任务完成情况（后台运行）"""
        try:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            success_count = sum(1 for r in results if r is True)
            error_count = len(results) - success_count
            
            logger.info(f"消息 {message_id} 的反应任务完成: {success_count} 成功, {error_count} 失败")
            
        except Exception as e:
            logger.error(f"监控任务时出错: {e}")
    
    async def get_active_tasks_count(self) -> Dict[str, int]:
        """获取当前活跃任务统计"""
        return {
            'total': len(self.active_tasks),
            'by_worker': {}
        }
    
    async def start(self):
        """启动主控Bot"""
        await self.master_bot.start(self.master_token)
    
    async def close(self):
        """清理资源"""
        if self.session:
            await self.session.close()
        
        # 取消所有活跃任务
        for task in self.active_tasks.values():
            task.cancel()
        
        await self.master_bot.close()

class BotClusterManager:
    def __init__(self, master_bot: MasterBot):
        self.master_bot = master_bot
        self.health_check_task = None
        self.metrics = {
            'messages_processed': 0,
            'reactions_added': 0,
            'errors': 0,
            'start_time': None
        }
    
    async def start(self):
        """启动集群管理器"""
        self.metrics['start_time'] = asyncio.get_event_loop().time()
        self.health_check_task = asyncio.create_task(self.health_check_loop())
        
        # 启动主控Bot
        await self.master_bot.start()
    
    async def health_check_loop(self):
        """健康检查循环"""
        while True:
            try:
                await self.perform_health_checks()
                await asyncio.sleep(60)  # 每分钟检查一次
            except Exception as e:
                logger.error(f"健康检查出错: {e}")
                await asyncio.sleep(30)
    
    async def perform_health_checks(self):
        """执行健康检查"""
        healthy_workers = 0
        
        for worker in self.master_bot.workers:
            if await worker.test_connection():
                healthy_workers += 1
            else:
                logger.warning(f'⚠️ 工作Bot {worker.config.name} 连接异常')
        
        logger.info(f'🏥 健康检查: {healthy_workers}/{len(self.master_bot.workers)} 个Bot正常')
        
        # 更新指标
        active_tasks = await self.master_bot.get_active_tasks_count()
        
        logger.info(f'📊 集群指标 - 活跃任务: {active_tasks["total"]}')
    
    async def get_cluster_status(self) -> Dict:
        """获取集群状态"""
        status = {
            'master_online': self.master_bot.master_bot.is_ready(),
            'worker_count': len(self.master_bot.workers),
            'queue_size': self.master_bot.message_queue.qsize(),
            'active_tasks': len(self.master_bot.active_tasks),
            'metrics': self.metrics,
            'uptime': asyncio.get_event_loop().time() - self.metrics['start_time'] if self.metrics['start_time'] else 0
        }
        
        # 检查每个worker的状态
        status['workers'] = []
        for worker in self.master_bot.workers:
            worker_status = {
                'name': worker.config.name,
                'enabled': worker.config.enabled,
                'online': await worker.test_connection()
            }
            status['workers'].append(worker_status)
        
        return status
    
    async def graceful_shutdown(self):
        """优雅关闭"""
        logger.info("正在关闭Bot集群...")
        
        if self.health_check_task:
            self.health_check_task.cancel()
        
        await self.master_bot.close()
        logger.info("Bot集群已关闭")

class WorkerBot:
    def __init__(self, config: BotConfig, session: aiohttp.ClientSession, proxy_url: Optional[str] = None):
        self.config = config
        self.session = session
        self.proxy_url = proxy_url
        self.headers = {
            'Authorization': f'{config.token}',
            'Content-Type': 'application/json',
            'User-Agent': 'DiscordBot (https://github.com) Python/3.8 aiohttp/3.7.4'
        }
    
    async def add_reaction_with_delay(self, message: discord.Message, emoji: str) -> bool:
        """添加反应（带随机延迟）"""
        try:
            # 生成随机延迟
            delay = random.uniform(*self.config.delay_range)
            # logger.info(f'{self.config.name} 将在 {delay:.2f} 秒后为消息 {message.id} 添加反应')
            
            # 非阻塞延迟
            await asyncio.sleep(delay)
            
            # 执行添加反应操作
            success = await self._add_reaction_api(
                message.guild.id,
                message.channel.id,
                message.id,
                emoji
            )
            
            if not success:
                logger.warning(f'❌ {self.config.name} 为消息 {message.id} 添加反应失败')
            
            return success
            
        except Exception as e:
            logger.error(f'❌ {self.config.name} 执行反应任务时出错: {e}')
            return False
            

    async def _add_reaction_api(self, guild_id: int, channel_id: int, message_id: int, emoji: str) -> bool:

        encoded_emoji = urllib.parse.quote(emoji, safe='')

        
        url = f"https://discord.com/api/v10/channels/{channel_id}/messages/{message_id}/reactions/{encoded_emoji}/@me"
        
        try:
            async with self.session.put(url, headers=self.headers, proxy=self.proxy_url) as response:
                if response.status == 204:
                    return True
                elif response.status == 429:
                    # 处理速率限制
                    retry_after = float(response.headers.get('Retry-After', 1)) + 30
                    logger.warning(f'⚠️ {self.config.name} 触发速率限制，等待 {retry_after} 秒')
                    await asyncio.sleep(retry_after)
                    return await self._add_reaction_api(guild_id, channel_id, message_id, emoji)
                else:
                    error_text = await response.text()
                    logger.error(f'API错误 {response.status}: {error_text}')
                    logger.error(f'token:{self.config.token[:8]}...{self.config.token[-4:]}')
                    return False
                    
        except aiohttp.ClientError as e:
            logger.error(f'网络错误: {e}')
            return False
    
    async def test_connection(self) -> bool:
        """测试用户连接状态"""
        url = "https://discord.com/api/v10/users/@me"
        
        # 使用用户token的headers
        user_headers = {
            'Authorization': self.config.token,
            'Content-Type': 'application/json',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
        
        try:
            async with self.session.get(url, headers=user_headers, proxy=self.proxy_url) as response:
                return response.status == 200
        except:
            return False


async def batch_test_tokens(tokens: List[str]) -> Dict[str, bool]:
    """
    批量测试tokens是否有效
    
    Args:
        tokens: token列表
        
    Returns:
        Dict[token, is_valid] 每个token的有效性
    """
    url = "https://discord.com/api/v10/users/@me"
    results = {}
    
    proxy_url = app_config.get_proxy_url()
    async with aiohttp.ClientSession(trust_env=True) as session:
        for i, token in enumerate(tokens):
            if i==0:
                continue
            headers = {
                'Authorization': token,
                'Content-Type': 'application/json',
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            }
            
            try:
                async with session.get(url, headers=headers, proxy=proxy_url) as response:
                    is_valid = response.status == 200
                    if is_valid:
                        data = await response.json()
                        username = data.get('username', 'unknown')
                        logger.info(f'✅ Token {i+1}: 有效 (用户: {username})')
                    else:
                        logger.warning(f'❌ Token {i+1}: 无效 (状态码: {response.status})')
                    results[token[:20] + '...'] = is_valid
            except Exception as e:
                logger.error(f'❌ Token {i+1}: 检测失败 ({e})')
                results[token[:20] + '...'] = False
            
            # 避免触发速率限制
            await asyncio.sleep(3)
    
    valid_count = sum(1 for v in results.values() if v)
    logger.info(f'📊 检测完成: {valid_count}/{len(tokens)} 个token有效')
    
    return results


async def test_all_tokens():
    """测试配置文件中所有tokens"""
    from config import config as app_config
    
    tokens = app_config.get_discord_token()
    if not tokens:
        logger.error("未找到tokens配置")
        return
    
    if isinstance(tokens, str):
        tokens = [tokens]
    
    logger.info(f"开始检测 {len(tokens)} 个tokens...")
    return await batch_test_tokens(tokens)


async def batch_add_reaction(channel_id: int, message_id: int, emoji: str = '👍'):
    """
    用所有tokens挨个给消息点赞
    
    Args:
        channel_id: 频道ID
        message_id: 消息ID
        emoji: 表情，默认👍
    """
    from config import config as app_config
    
    tokens = app_config.get_discord_token()
    if not tokens:
        logger.error("未找到tokens配置")
        return
    
    if isinstance(tokens, str):
        tokens = [tokens]
    
    encoded_emoji = urllib.parse.quote(emoji, safe='')
    url = f"https://discord.com/api/v10/channels/{channel_id}/messages/{message_id}/reactions/{encoded_emoji}/@me"
    
    success_count = 0
    fail_count = 0
    
    logger.info(f"开始用 {len(tokens)} 个账号给消息 {message_id} 点赞...")
    
    proxy_url = app_config.get_proxy_url()
    async with aiohttp.ClientSession(trust_env=True) as session:
        for i, token in enumerate(tokens):
            if i == 0:
                continue
            
            headers = {
                'Authorization': token,
                'Content-Type': 'application/json',
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            }
            
            try:
                async with session.put(url, headers=headers, proxy=proxy_url) as response:
                    if response.status == 204:
                        success_count += 1
                        logger.info(f'✅ Token {i+1}: 点赞成功')
                    elif response.status == 429:
                        retry_after = float(response.headers.get('Retry-After', 5))
                        logger.warning(f'⚠️ Token {i+1}: 速率限制，等待 {retry_after} 秒')
                        await asyncio.sleep(retry_after)
                        # 重试
                        async with session.put(url, headers=headers, proxy=proxy_url) as retry_resp:
                            if retry_resp.status == 204:
                                success_count += 1
                                logger.info(f'✅ Token {i+1}: 重试点赞成功')
                            else:
                                fail_count += 1
                                logger.warning(f'❌ Token {i+1}: 重试失败 ({retry_resp.status})')
                    else:
                        fail_count += 1
                        error_text = await response.text()
                        logger.warning(f'❌ Token {i+1}: 点赞失败 ({response.status}) {error_text[:100]}')
            except Exception as e:
                fail_count += 1
                logger.error(f'❌ Token {i+1}: 异常 ({e})')
            
            # 避免触发速率限制
            await asyncio.sleep(5)
    
    logger.info(f'📊 点赞完成: {success_count} 成功, {fail_count} 失败')


if __name__ == "__main__":
    # 给指定消息点赞
    # CHANNEL_ID = 1430131207575965838
    # MESSAGE_ID = 1448559543079534602
    # asyncio.run(batch_add_reaction(CHANNEL_ID, MESSAGE_ID, '👍'))
    pass
