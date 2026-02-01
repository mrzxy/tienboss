#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
工具函数模块
"""

import re
from datetime import datetime


def validate_discord_id(discord_id):
    """验证Discord ID格式

    Args:
        discord_id: Discord ID（字符串或整数）

    Returns:
        bool: 是否有效
    """
    try:
        id_str = str(discord_id)
        # Discord ID是18位数字
        if len(id_str) >= 17 and len(id_str) <= 19 and id_str.isdigit():
            return True
        return False
    except:
        return False


def format_message(content, max_length=2000):
    """格式化消息内容

    Args:
        content: 消息内容
        max_length: 最大长度（Discord限制2000字符）

    Returns:
        str: 格式化后的消息
    """
    if not content:
        return ""

    content = str(content)

    # 如果超过最大长度，截断
    if len(content) > max_length:
        return content[:max_length-3] + "..."

    return content


def parse_mentions(content):
    """解析消息中的@提及

    Args:
        content: 消息内容

    Returns:
        list: 提及的用户ID列表
    """
    # Discord提及格式: <@USER_ID> 或 <@!USER_ID>
    pattern = r'<@!?(\d+)>'
    matches = re.findall(pattern, content)
    return matches


def timestamp_to_datetime(timestamp):
    """将时间戳转换为datetime对象

    Args:
        timestamp: Unix时间戳（秒）

    Returns:
        datetime: datetime对象
    """
    return datetime.fromtimestamp(timestamp)


def get_current_timestamp():
    """获取当前时间戳

    Returns:
        str: 格式化的时间字符串
    """
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')
