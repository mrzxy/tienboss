
import discord
import asyncio
import datetime
import json
import hashlib
from tinydb import TinyDB, Query
from config import get_config

MAX_MESSAGES = 10000
OUTPUT_FILE = "channel_history.json"
DB_FILE = "channel_history.db"

# 初始化数据库
db = TinyDB(DB_FILE)
messages_table = db.table('messages')
metadata_table = db.table('metadata')
Message = Query()

def get_last_message_id(channel_id):
    """获取指定频道的最后一条消息ID"""
    result = metadata_table.search(Message.channel_id == str(channel_id))
    if result:
        return result[0].get('last_message_id')
    return None

def update_last_message_id(channel_id, message_id):
    """更新指定频道的最后一条消息ID"""
    metadata_table.upsert({
        'channel_id': str(channel_id),
        'last_message_id': str(message_id),
        'updated_at': datetime.datetime.utcnow().isoformat()
    }, Message.channel_id == str(channel_id))

def insert_message_if_not_exists(message_data):
    """插入消息，如果不存在的话"""
    existing = messages_table.search(Message.dc_msg_id == message_data['dc_msg_id'])
    if not existing:
        messages_table.insert(message_data)
        return True
    return False

def get_message_by_md5(content_md5):
    """根据内容的MD5哈希查找消息"""
    result = messages_table.search(Message.content_md5 == content_md5)
    return result[0] if result else None

def generate_content_md5(content):
    """生成内容的MD5哈希"""
    return hashlib.md5(content.encode('utf-8')).hexdigest()

async def sync_history(bot):
    app_config = get_config()
    channel_id =  app_config.get_sync_channel_id()
    # 查找目标频道
    target_channel = bot.get_channel(channel_id)
    
    if not target_channel:
        print(f"错误：找不到ID为 {channel_id} 的频道")
        return
    
    print(f"找到目标频道: #{target_channel.name} (ID: {target_channel.id})")

    # 开始获取历史消息
    await fetch_channel_history(target_channel)

async def fetch_channel_history(channel):
    """获取频道历史消息并保存到数据库"""
    print(f"开始获取频道 #{channel.name} 的历史消息...")
    
    # 获取上次同步的最后一条消息ID
    last_message_id = get_last_message_id(channel.id)
    after_message = discord.Object(id=int(last_message_id)) if last_message_id else None
    
    print(f"上次同步的最后消息ID: {last_message_id}")
    
    new_messages = []
    last_message = None
    message_count = 0
    new_message_count = 0
    latest_message_id = last_message_id
    
    try:
        # 分批获取消息（每次100条）
        while message_count < MAX_MESSAGES:
            messages = []
            async for message in channel.history(limit=100, before=last_message, after=after_message):
                messages.append(message)
            
            if not messages:
                break  # 没有更多消息了
                
            message_count += len(messages)
            last_message = messages[-1]
            
            # 处理每条消息
            for message in messages:
                message_data = await process_message(message, channel)
                
                # 插入消息到数据库（如果不存在）
                if insert_message_if_not_exists(message_data):
                    new_messages.append(message_data)
                    new_message_count += 1
                
                # 更新最新的消息ID
                if not latest_message_id or int(message.id) > int(latest_message_id):
                    latest_message_id = str(message.id)
            
            print(f"已处理 {message_count} 条消息，新增 {new_message_count} 条...")
            
            # 每1000条消息暂停一下，避免速率限制
            if message_count % 1000 == 0:
                await asyncio.sleep(5)
    
    except discord.Forbidden:
        print("错误：没有权限读取消息历史")
        return
    except discord.HTTPException as e:
        print(f"API错误: {e}")
        return
    
    # 更新最后同步的消息ID
    if latest_message_id and latest_message_id != last_message_id:
        update_last_message_id(channel.id, latest_message_id)
        print(f"更新最后同步消息ID: {latest_message_id}")
    
    print(f"同步完成！总共处理 {message_count} 条消息，新增 {new_message_count} 条消息")
    


async def process_message(message, channel):
    """处理单条消息，转换为简化的数据库格式"""
    content = message.content
    content_md5 = generate_content_md5(content)
    
    # 返回简化的消息数据
    return {
        "dc_msg_id": str(message.id),
        "content": content,
        "content_md5": content_md5,
        "created_at": message.created_at.isoformat()
    }


def search_message_by_content_md5(content_md5):
    """根据内容MD5搜索消息 - 便捷函数"""
    return get_message_by_md5(content_md5)
