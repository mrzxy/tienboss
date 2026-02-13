#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
工具函数模块
"""
import cv2
import numpy as np

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


import urllib.request
def download_image(src: str):
    req = urllib.request.Request(src, headers={
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    })
    resp = urllib.request.urlopen(req, timeout=15)
    return np.frombuffer(resp.read(), dtype=np.uint8)


def find_avatar_in_chat(avatar_path: str, data, threshold: float = 0.85) -> dict:
    """在聊天截图中查找头像位置（支持本地路径或网络 URL）

    Args:
        avatar_path: 头像图片路径或 URL
        chat_path:   聊天截图路径或 URL
        threshold:   匹配置信度阈值，默认 0.85

    Returns:
        dict: {
            'found': bool,        是否找到（score > threshold）
            'score': float,       最佳匹配分数
            'x': int, 'y': int,   匹配位置左上角坐标
            'w': int, 'h': int,   匹配区域宽高
            'cx': int, 'cy': int  中心点坐标
        }
    """
    avatar = cv2.imread(avatar_path)
    chat = cv2.imdecode(data, cv2.IMREAD_COLOR)

    if avatar is None:
        raise ValueError(f"无法读取头像: {avatar_path}")
    if chat is None:
        raise ValueError(f"无法读取聊天截图")

    ah, aw = avatar.shape[:2]
    ch, cw = chat.shape[:2]

    best_score = 0.0
    best_loc = None
    best_size = (0, 0)

    for scale in np.arange(0.03, 1.1, 0.01):
        new_w, new_h = int(aw * scale), int(ah * scale)
        if new_w < 8 or new_h < 8 or new_w > cw or new_h > ch:
            continue

        resized = cv2.resize(avatar, (new_w, new_h))
        res = cv2.matchTemplate(chat, resized, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(res)

        if max_val > best_score:
            best_score = max_val
            best_loc = max_loc
            best_size = (new_w, new_h)

    if best_loc is None:
        return {'found': False, 'score': 0.0, 'x': 0, 'y': 0, 'w': 0, 'h': 0, 'cx': 0, 'cy': 0}

    x, y = best_loc
    w, h = best_size
    return {
        'found': best_score > threshold,
        'score': round(best_score, 4),
        'x': x, 'y': y,
        'w': w, 'h': h,
        'cx': x + w // 2,
        'cy': y + h // 2,
    }