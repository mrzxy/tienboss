import discord
from discord.ext import commands, tasks
import asyncio
import logging
import datetime
import json
from chat import send_chat_request, send_msg_by_webhook, send_chat_request_by_Heisen, send_msg_by_mqtt, extract_image_urls
from config import get_config
from dc_history import sync_history
from t3_channel import process_t3, update_tt3_db
from trump_news_channel import process_trump_news
from chatting_room_channel import process_chatting_room_news
from helper import print_message_details,get_logger
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

# 定时同步历史消息任务
@tasks.loop(seconds=600)  # 每10秒执行一次，你可以根据需要调整时间间隔
async def scheduled_sync_history():
    """定时同步历史消息"""
    try:
        logger.info("开始定时同步历史消息...")
        await sync_history(bot)
        logger.info("定时同步历史消息完成")
    except Exception as e:
        logger.error(f"定时同步历史消息失败: {e}")

@scheduled_sync_history.before_loop
async def before_scheduled_sync():
    """等待bot准备就绪"""
    await bot.wait_until_ready()
    logger.info("定时同步任务已准备就绪")
    



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
                if 'webhook_url2' in message:
                    await send_msg_by_webhook(message['content'], message['webhook_url2'])
                continue

            elif 'mqtt' in message:
                other = None
                if 'other' in message:
                    other = message['other']
                result = await send_msg_by_mqtt(client,message['topic'],message['channel'],message['content'], other)
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

    # 同步slash commands到Discord
    try:
        logger.info("正在同步slash commands...")
        synced = await bot.tree.sync()
        logger.info(f"成功同步 {len(synced)} 个slash commands")
    except Exception as e:
        logger.error(f"同步slash commands失败: {e}")

    # 启动定时同步任务
    if not scheduled_sync_history.is_running():
        scheduled_sync_history.start()
        logger.info("定时同步历史消息任务已启动（每10秒执行一次）")

    # 立即执行一次同步
    await sync_history(bot)



def parse_time_range(time_str):
    """
    解析时间范围字符串，返回对应的时间差
    支持: 8小时, 24小时, 72小时, 一周前
    """
    time_mappings = {
        '8小时': datetime.timedelta(hours=8),
        '24小时': datetime.timedelta(hours=24),
        '72小时': datetime.timedelta(hours=72),
        '一周': datetime.timedelta(weeks=1)
    }

    return time_mappings.get(time_str)


async def search_messages_in_channels(bot, keyword, time_delta):
    """
    搜索指定频道中包含关键字的消息
    """
    results = []
    current_time = datetime.datetime.now(datetime.timezone.utc)
    start_time = current_time - time_delta

    # 指定要搜索的频道ID列表
    target_channel_ids = [
        1321048952405229600,
        1394484823015424081,
        1325294881517867018,
        1383128286196137995,
        1386580405557395576,
        1420046304624509060
    ]

    logger.info(f"搜索参数 - 关键字: {keyword}, 开始时间: {start_time}, 当前时间: {current_time}")
    # logger.info(f"目标频道ID: {target_channel_ids}")

    # 遍历所有服务器
    total_channels = 0
    scanned_channels = 0
    total_messages = 0

    for guild in bot.guilds:
        logger.info(f"正在搜索服务器: {guild.name}")
        # 遍历服务器中的所有文本频道
        for channel in guild.text_channels:
            # 只处理指定ID的频道
            if channel.id not in target_channel_ids:
                continue
            total_channels += 1
            try:
                # 检查是否有读取消息历史的权限
                # permissions = channel.permissions_for(guild.me)
                # if not permissions.read_message_history:
                #     logger.warning(f"跳过频道（无权限）: {guild.name} - {channel.name}")
                #     continue

                scanned_channels += 1
                channel_msg_count = 0

                # 获取频道消息历史
                async for message in channel.history(limit=None, after=start_time):
                    channel_msg_count += 1
                    total_messages += 1

                    # 检查消息内容是否包含关键字（不区分大小写）
                    if keyword.lower() in message.content.lower():
                        logger.info(f"找到匹配消息 - 频道: {channel.name}, 作者: {message.author}, 时间: {message.created_at}")
                        results.append({
                            'channel': channel.name,
                            'guild': guild.name,
                            'author': str(message.author),
                            'content': message.content,
                            'timestamp': message.created_at,
                            'jump_url': message.jump_url
                        })

                logger.info(f"频道 {channel.name}: 扫描了 {channel_msg_count} 条消息")

            except discord.Forbidden:
                logger.warning(f"没有权限访问频道: {guild.name} - {channel.name}")
            except Exception as e:
                logger.error(f"搜索频道 {guild.name} - {channel.name} 时出错: {e}")

    logger.info(f"搜索完成 - 总频道: {total_channels}, 已扫描: {scanned_channels}, 总消息数: {total_messages}, 匹配结果: {len(results)}")

    return results


def format_search_results(results, keyword, time_str):
    """
    格式化搜索结果为易读的消息
    """
    if not results:
        return f"未找到包含关键字「{keyword}」的消息（时间范围: {time_str}）"

    # 按时间倒序排序（最新的在前面）
    results.sort(key=lambda x: x['timestamp'], reverse=True)

    # 构建结果消息
    response = f"找到 {len(results)} 条包含关键字「{keyword}」的消息（时间范围: {time_str}）:\n\n"

    for i, result in enumerate(results[:50], 1):  # 限制显示前50条
        timestamp = result['timestamp'].strftime('%Y-%m-%d %H:%M:%S')
        response += f"**{i}.** [{result['guild']} - #{result['channel']}]({result['jump_url']})\n"
        response += f"   作者: {result['author']} | 时间: {timestamp}\n"
        response += f"   内容: {result['content'][:100]}{'...' if len(result['content']) > 100 else ''}\n\n"

    if len(results) > 50:
        response += f"\n*注: 仅显示前50条结果，共找到 {len(results)} 条消息*"

    return response


@bot.tree.command(name="查询", description="搜索频道内包含关键字的消息")
async def search_command(
    interaction: discord.Interaction,
    时间: str,
    关键字: str
):
    """
    查询指令的slash command实现
    """
    try:
        # 解析时间范围
        time_delta = parse_time_range(时间)
        if not time_delta:
            await interaction.response.send_message(
                f"❌ 不支持的时间范围: {时间}\n请使用以下选项之一:\n- 8小时\n- 24小时\n- 72小时\n- 一周",
                ephemeral=False
            )
            return

        # 发送初始响应（避免超时）- 只有执行命令的用户可见
        await interaction.response.send_message(
            f"🔍 正在搜索关键字「{关键字}」（时间范围: {时间}）...",
            ephemeral=False
        )

        # 执行搜索
        results = await search_messages_in_channels(bot, 关键字, time_delta)

        # 格式化结果
        response = format_search_results(results, 关键字, 时间)

        # Discord消息有2000字符限制，需要分割长消息
        if len(response) <= 2000:
            await interaction.followup.send(response, ephemeral=False)
        else:
            # 将消息分割成多个部分
            chunks = []
            current_chunk = ""

            for line in response.split('\n'):
                if len(current_chunk) + len(line) + 1 > 2000:
                    chunks.append(current_chunk)
                    current_chunk = line + '\n'
                else:
                    current_chunk += line + '\n'

            if current_chunk:
                chunks.append(current_chunk)

            # 发送所有分割的消息 - 只有执行命令的用户可见
            for chunk in chunks:
                await interaction.followup.send(chunk, ephemeral=False)

        logger.info(f"查询指令执行完成 - 关键字: {关键字}, 时间: {时间}, 结果数: {len(results)}")

    except Exception as e:
        logger.error(f"处理查询指令时出错: {e}")
        try:
            await interaction.followup.send(f"❌ 查询出错: {str(e)}")
        except:
            await interaction.response.send_message(f"❌ 查询出错: {str(e)}", ephemeral=False)


@bot.event
async def on_message(message):
    # 忽略机器人自己的消息
    if message.author == bot.user:
        return

    print_message_details(message)
    # 确保处理命令（如果你有命令系统）
    await bot.process_commands(message)

    # 完整打印 Discord Message 对象的所有成员


    msg = {
        "content": message.content,
    }
    
    # 构建日志消息，包含文本和图片信息
    images = []
    
    # if message.attachments:
    #     for i, attachment in enumerate(message.attachments):
    #         if attachment.content_type and attachment.content_type.startswith('image/'):
    #             logger.info(f"检测到图片附件 - ID: {attachment.id}, 文件名: {attachment.filename}, URL: {attachment.url}")
    #             images.append(attachment.url)
            # else:
            #     log_parts.append(f'附件{i+1}: {attachment.filename} ({attachment.url})')
    # msg['images'] = images
    

    # if 'real-time-news' in message.channel.name:
    #     msg['channel'] = 'real-time-news'
    if 'alerts-window' in message.channel.name and ( message.author.name == 'dk_149' or message.author.name == 'qiyu_31338'):
        logger.info(f'来自: {message.author.name}')
        # test
        msg['webhook_url'] = 'https://discord.com/api/webhooks/1410512538860519499/CR8XEA-Z2OsLgxCAA6dAj0aNlTWaAIKH5fiVXM6_sLMSyogH2o8LXQ2E1FgFMGwGmMW3'
        msg['webhook_url2'] = 'https://discord.com/api/webhooks/1417517906161434776/zB62fu_aVed1mcaS_YflbzOi4-QIQu4HScA2reS9iTEq8t0NghOuzOCzK5DbMNLxHo_D'
        if debug:
            msg['webhook_url'] = 'https://discord.com/api/webhooks/1387993663837310996/Kuov6iYyG8nRaHzHjCaZcVbxlRvNQ82WwoXncU9i_e9sfQxuosgAgX919R22mDNMQQqO'
            msg['webhook_url2'] = 'https://discord.com/api/webhooks/1387993663837310996/Kuov6iYyG8nRaHzHjCaZcVbxlRvNQ82WwoXncU9i_e9sfQxuosgAgX919R22mDNMQQqO'
    # elif 'trade-alerts' in message.channel.name:
    #     msg['webhook_url'] = 'https://discord.com/api/webhooks/1382589146157289483/7Wds1Kt90n3qrsoMa_zAniHr1vd-Vr6wW3e6JzpHtvi7kBmj_9wFy8Jt3cV2CfZ-_Jc7'
    elif 'heisen' in message.channel.name:
        msg['topic'] = 'lis-msg/jasonwood'
        msg['channel'] = 'craig-comments'
        msg['mqtt'] = True
        if debug:
            msg['topic'] = 'lis-msg/qiyu'


        # content = message.content
        content = await asyncio.to_thread(send_chat_request_by_Heisen, message.content)
        
        # 如果chat返回了结果，可以在这里处理
        if content:
            images = extract_image_urls(message.content)
            if len(images) > 0:
                logger.info(f"提取到的图片: {len(images)}")
                for image in images:
                    content = content + f"[.]({image})"


        msg['content'] = content
    elif 'chatting-room' in message.channel.name:
        msg = process_chatting_room_news(message)
        return
    elif 'trump-news' in message.channel.name:
        msg = process_trump_news(message)
        return
    elif 'tt3' in message.channel.name:
        msg = process_t3(message)
        # 同时保存TT3消息到数据库
        update_tt3_db(message)
    elif 'diamond-only-stock' in message.channel.name:
        update_tt3_db(message)
        return
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

        
    except KeyboardInterrupt:
        logger.info("收到中断信号，正在关闭...")
        # 停止定时任务
        if scheduled_sync_history.is_running():
            scheduled_sync_history.cancel()
            logger.info("定时同步任务已停止")
    except Exception as e:
        logger.error(f"机器人启动失败: {e}")
    finally:
        # 确保定时任务被停止
        if scheduled_sync_history.is_running():
            scheduled_sync_history.cancel()
