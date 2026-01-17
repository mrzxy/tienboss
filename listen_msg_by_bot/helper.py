
import logging
import re
from re import L
from config import get_config

def print_message_details(message):
    return None
    """完整打印 Discord Message 对象的所有成员"""
    print("=" * 80)
    print("DISCORD MESSAGE 完整信息:")
    print("=" * 80)
    
    # 基本信息
    print(f"📨 消息ID: {message.id}")
    print(f"📝 内容: {repr(message.content)}")
   
    
    # 附件信息
    if message.attachments:
        print(f"\n📎 附件信息 ({len(message.attachments)} 个):")
        for i, attachment in enumerate(message.attachments):
            print(f"   [{i+1}] 文件名: {attachment.filename}")
            print(f"       URL: {attachment.url}")
            print(f"       大小: {attachment.size} bytes")
            print(f"       内容类型: {attachment.content_type}")
    
    # 嵌入内容
    if message.embeds:
        print(f"\n🎨 嵌入内容 ({len(message.embeds)} 个):")
        for i, embed in enumerate(message.embeds):
            print(f"   [{i+1}] 标题: {embed.title}")
            print(f"       描述: {repr(embed.description)}")
            print(f"       URL: {embed.url}")
            print(f"       类型: {embed.type}")
            print(f"       颜色: {embed.color}")
            print(f"       时间戳: {embed.timestamp}")
            
            if embed.author:
                print(f"       作者: {embed.author.name} ({embed.author.url})")
            
            if embed.footer:
                print(f"       页脚: {embed.footer.text}")
            
            if embed.thumbnail:
                print(f"       缩略图: {embed.thumbnail.url}")
            
            if embed.image:
                print(f"       图片: {embed.image.url}")
            
            if embed.fields:
                print(f"       字段 ({len(embed.fields)} 个):")
                for j, field in enumerate(embed.fields):
                    print(f"         [{j+1}] {field.name}: {field.value} (内联: {field.inline})")
    
    # 反应信息
    if message.reactions:
        print(f"\n😀 反应信息 ({len(message.reactions)} 个):")
        for reaction in message.reactions:
            print(f"   {reaction.emoji}: {reaction.count} 次")
    
    # 引用/回复信息
    if message.reference:
        print(f"\n💬 回复信息:")
        print(f"   消息ID: {message.reference.message_id}")
        print(f"   频道ID: {message.reference.channel_id}")
        print(f"   服务器ID: {message.reference.guild_id}")
    
    # 提及信息
    if message.mentions:
        print(f"\n@ 提及用户 ({len(message.mentions)} 个):")
        for user in message.mentions:
            print(f"   {user.name}#{user.discriminator} (ID: {user.id})")
    
    if message.role_mentions:
        print(f"\n@ 提及角色 ({len(message.role_mentions)} 个):")
        for role in message.role_mentions:
            print(f"   {role.name} (ID: {role.id})")
    
    if message.channel_mentions:
        print(f"\n@ 提及频道 ({len(message.channel_mentions)} 个):")
        for channel in message.channel_mentions:
            print(f"   #{channel.name} (ID: {channel.id})")
    
    # 其他属性
    print(f"\n🔧 其他属性:")
    print(f"   TTS: {message.tts}")
    print(f"   系统消息: {message.system_content}")
    print(f"   Nonce: {message.nonce}")
    print(f"   Webhook ID: {getattr(message, 'webhook_id', None)}")
    print(f"   应用ID: {getattr(message, 'application_id', None)}")
    
    # 活动和应用信息
    if hasattr(message, 'activity') and message.activity:
        print(f"   活动: {message.activity}")
    
    if hasattr(message, 'application') and message.application:
        print(f"   应用: {message.application}")
    
    # 标志位
    if hasattr(message, 'flags'):
        print(f"   标志: {message.flags}")
    
    # 消息组件（按钮等）
    if hasattr(message, 'components') and message.components:
        print(f"\n🔘 消息组件 ({len(message.components)} 个):")
        for i, component in enumerate(message.components):
            print(f"   [{i+1}] 类型: {type(component).__name__}")
    
    # Stickers（贴纸）
    if hasattr(message, 'stickers') and message.stickers:
        print(f"\n🏷️  贴纸 ({len(message.stickers)} 个):")
        for sticker in message.stickers:
            print(f"   {sticker.name} (ID: {sticker.id})")
    
    print("=" * 80)
    print()

def get_app_config():
    # 加载配置
    app_config = get_config()
    # 验证配置
    if not app_config.validate_config():
        raise RuntimeError("配置文件验证失败，请检查配置文件")
    return app_config


def get_logger(name, log_config=None):
    if log_config is None:
        # 加载配置
        app_config = get_app_config()
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
    logger = logging.getLogger(name)
    return logger


def contains_chinese(text):
    """
    判断文本内容是否包含中文字符
    
    Args:
        text (str): 需要检查的文本内容
        
    Returns:
        bool: 如果文本包含中文字符返回 True，否则返回 False
    """
    if not isinstance(text, str):
        return False
    
    # 使用正则表达式匹配中文字符
    # \u4e00-\u9fff 是中文字符的 Unicode 范围
    chinese_pattern = re.compile(r'[\u4e00-\u9fff]+')
    return bool(chinese_pattern.search(text))

def isIllicitWord(content):
    keywords = ['习近平','李强']
    return any(keyword in content for keyword in keywords)
