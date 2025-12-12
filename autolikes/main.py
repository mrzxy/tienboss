import discord
from discord.ext import commands, tasks
import asyncio
import logging
import datetime
import json
from chat import send_chat_request, send_msg_by_webhook, send_msg_by_mqtt, extract_image_urls
from config import get_config
from helper import print_message_details,get_logger
from bot import MasterBot, BotClusterManager, BotConfig

# 加载配置
app_config = get_config()
# 验证配置
if not app_config.validate_config():
    raise RuntimeError("配置文件验证失败，请检查配置文件")

logger = get_logger(__name__, app_config.get_logging_config())
logger.info("日志系统初始化完成")

# 从配置文件读取设置
debug = app_config.is_debug()
if debug:
    logger.info('当前为: debug')
else:
    logger.info('当前为: production')

http_proxy = app_config.get_proxy_url()

# 初始化Discord intents
intents = discord.Intents.default()
intents.message_content = True  # 如果需要读取消息内容
intents.messages = True  # 确保能够接收消息事件

# 创建bot实例
logger.info(f"使用代理: {http_proxy}")

from emqx import MQTTConfig, MQTTClient

# 从配置文件读取MQTT设置
mqtt_config_data = app_config.get_mqtt_config()
mqtt_config = MQTTConfig(
    auto_reconnect=mqtt_config_data['auto_reconnect'],
    max_reconnect_attempts=mqtt_config_data['max_reconnect_attempts'],
    reconnect_delay=mqtt_config_data['reconnect_delay']
)

client = MQTTClient(mqtt_config)





async def main():
    # 从配置文件获取Discord bot token
    app_key_list = app_config.get_discord_token()
    if not app_key_list:
        raise ValueError("Discord bot token未配置或为空")

    MASTER_BOT_TOKEN = app_key_list[0]
    BOT_CONFIGS = []
    pos = 1
    for x in app_key_list[1:]:
        BOT_CONFIGS.append(BotConfig(token=x, name=f'bot_{pos}', delay_range=(1, 3600), enabled=True))
        pos += 1


    # 创建主控Bot
    master_bot = MasterBot(MASTER_BOT_TOKEN, BOT_CONFIGS)
    
    # 创建集群管理器
    cluster_manager = BotClusterManager(master_bot)
    
    # 设置信号处理
    def signal_handler(signum, frame):
        print(f"\n收到信号 {signum}，正在优雅关闭...")
        asyncio.create_task(cluster_manager.graceful_shutdown())
    
    import signal
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        # 启动集群
        await cluster_manager.start()
    except KeyboardInterrupt:
        await cluster_manager.graceful_shutdown()
    except Exception as e:
        logger.error(f"主程序出错: {e}")
        await cluster_manager.graceful_shutdown()

if __name__ == '__main__':
    # 运行机器人
    try:

        # 连接MQTT
        if client.connect():
            logger.info("MQTT连接成功")

        asyncio.run(main())

     

        
    except KeyboardInterrupt:
        logger.info("收到中断信号，正在关闭...")

    except Exception as e:
        logger.error(f"机器人启动失败: {e}")
    finally:
        pass
