import discord
from discord.ext import commands
import asyncio
import logging
from datetime import datetime
from chat import send_chat_request, send_msg_by_webhook, send_chat_request_by_Heisen, send_msg_by_mqtt
from config import get_config

# 加载配置
app_config = get_config()

# 验证配置
if not app_config.validate_config():
    raise RuntimeError("配置文件验证失败，请检查配置文件")

# 配置日志
log_config = app_config.get_logging_config()

# 清除已有的日志配置
for handler in logging.root.handlers[:]:
    logging.root.removeHandler(handler)

logging.basicConfig(
    level=getattr(logging, log_config['level']),
    format=log_config['format'],
    datefmt=log_config['date_format'],
    force=True  # 强制重新配置
)
logger = logging.getLogger(__name__)

# 测试日志输出
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
bot = commands.Bot(command_prefix='!', intents=intents, proxy=http_proxy)

from emqx import MQTTConfig, MQTTClient

# 从配置文件读取MQTT设置
mqtt_config_data = app_config.get_mqtt_config()
mqtt_config = MQTTConfig(
    auto_reconnect=mqtt_config_data['auto_reconnect'],
    max_reconnect_attempts=mqtt_config_data['max_reconnect_attempts'],
    reconnect_delay=mqtt_config_data['reconnect_delay']
)

client = MQTTClient(mqtt_config)

def on_connect(client, userdata, flags, rc):
    logger.info("mqtt连接成功回调被调用")

client.set_connection_callback(on_connect)
    



# 创建消息队列来确保有序处理
message_queue = asyncio.Queue()

# 消息处理任务
async def process_message_queue():
    logger.info("消息处理任务已启动")
    while True:
        try:
            # 从队列中获取消息
            message = await message_queue.get()

            if 'webhook_url' in message:
                await send_msg_by_webhook(message['content'], message['webhook_url'])
                continue
            elif 'wash_data' in message:
                  # 调用chat处理函数
                content = await asyncio.to_thread(send_chat_request_by_Heisen, message['content'])
                
                # 如果chat返回了结果，可以在这里处理
                if content:
                    content = content + "\n" + "\n".join(message['images'])
                    result = await send_msg_by_mqtt(client,message['topic'],message['channel'],content)
                    logger.info(f"MQTT消息发送结果: {result}")

            else:
            
                # 调用chat处理函数
                result = await asyncio.to_thread(send_chat_request, message['content'])
                
                # 如果chat返回了结果，可以在这里处理
                if result:
                   
                    await send_msg_by_webhook(result, "https://discord.com/api/webhooks/1386580439451435068/nQa_K4i0GGUo0ksQ_ftWuPkaz0Q4HDv6YBve1fjf0rNv9m-R5Q2ufwZURQN1I3cthLGB")
            # 标记任务完成
            message_queue.task_done()
            
        except Exception as e:
            logger.error(f"处理消息时出错: {e}")

@bot.event
async def setup_hook():
    """机器人启动时的初始化钩子"""
    # 启动消息处理任务
    bot.loop.create_task(process_message_queue())

@bot.event
async def on_ready():
    logger.info(f'Logged in as {bot.user}')
    logger.info(f'Bot is ready and listening for messages...')
    logger.info(f'Connected to {len(bot.guilds)} guilds')
    
    # 检查机器人的权限
    logger.info(f'Bot permissions: {bot.intents}')
    logger.info(f'Message content intent: {bot.intents.message_content}')
    logger.info(f'Messages intent: {bot.intents.messages}')
    
    # 列出所有连接的服务器
    if len(bot.guilds) > 0:
        for guild in bot.guilds:
            logger.info(f'Connected to guild: {guild.name} (ID: {guild.id})')
            # 检查机器人在该服务器中的权限
            bot_member = guild.get_member(bot.user.id)
            if bot_member:
                logger.info(f'Bot permissions in {guild.name}: {bot_member.guild_permissions}')
    else:
        logger.warning('⚠️  WARNING: Bot is not connected to any guilds!')
        logger.warning('请确保机器人已被邀请到服务器中，并且具有以下权限：')
        logger.warning('- Read Messages/View Channels')
        logger.warning('- Send Messages')
        logger.warning('- Read Message History')


@bot.event
async def on_message(message):
    # 忽略机器人自己的消息
    if message.author == bot.user:
        return
    
    # 确保处理命令（如果你有命令系统）
    await bot.process_commands(message)

    msg = {
        "content": message.content,
    }
    
    # 构建日志消息，包含文本和图片信息
    images = []
    
    if message.attachments:
        for i, attachment in enumerate(message.attachments):
            if attachment.content_type and attachment.content_type.startswith('image/'):
                logger.info(f"检测到图片附件 - ID: {attachment.id}, 文件名: {attachment.filename}, URL: {attachment.url}")
                images.append(attachment.url)
            # else:
            #     log_parts.append(f'附件{i+1}: {attachment.filename} ({attachment.url})')
    msg['images'] = images
    

    # if 'real-time-news' in message.channel.name:
    #     msg['channel'] = 'real-time-news'
    if 'alerts-windows' in message.channel.name and ( message.author.name == 'dk_149' or message.author.name == 'qiyu_31338'):
        logger.info(f'来自: {message.author.name}')
        # test
        msg['webhook_url'] = 'https://discord.com/api/webhooks/1410512538860519499/CR8XEA-Z2OsLgxCAA6dAj0aNlTWaAIKH5fiVXM6_sLMSyogH2o8LXQ2E1FgFMGwGmMW3'
        if debug:
            msg['webhook_url'] = 'https://discord.com/api/webhooks/1387993663837310996/Kuov6iYyG8nRaHzHjCaZcVbxlRvNQ82WwoXncU9i_e9sfQxuosgAgX919R22mDNMQQqO'
    # elif 'trade-alerts' in message.channel.name:
    #     msg['webhook_url'] = 'https://discord.com/api/webhooks/1382589146157289483/7Wds1Kt90n3qrsoMa_zAniHr1vd-Vr6wW3e6JzpHtvi7kBmj_9wFy8Jt3cV2CfZ-_Jc7'
    elif 'heisenberg' in message.channel.name:
        msg['topic'] = 'lis-msg/jasonwood'
        msg['channel'] = 'craig-comments'
        if debug:
            msg['topic'] = 'lis-msg/qiyu'
        msg['wash_data'] = True
    else:
        return

    # 将消息添加到队列中进行有序处理
    await message_queue.put(msg)
    
    logger.info(f'收到消息: {message.content}')
    logger.info(f'来自: {message.author}')
    logger.info(f'频道: {message.channel.name}')


if __name__ == '__main__':
    # 运行机器人
    try:
        # 连接MQTT
        if client.connect():
            logger.info("MQTT连接成功")

        # 从配置文件获取Discord bot token
        app_key = app_config.get_discord_token()
        if not app_key:
            raise ValueError("Discord bot token未配置或为空")
        
        logger.info(f"使用环境: {app_config.get_environment()}")
        logger.info(f"调试模式: {debug}")
        
        bot.run(app_key)

        
    except Exception as e:
        logger.error(f"机器人启动失败: {e}")
