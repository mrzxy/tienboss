#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Bot Token监听器模块
"""

import logging
from datetime import datetime
import discord
from discord.ext import commands


class BotListener:
    """Bot Token监听器 - 用于监听自己的频道"""

    def __init__(self, token, channels):
        """
        初始化Bot监听器

        Args:
            token: Bot Token
            channels: 要监听的频道ID列表
        """
        self.token = token
        self.channels = set(str(ch) for ch in channels)

        # 创建Bot实例
        intents = discord.Intents.default()
        intents.message_content = True
        intents.guilds = True
        intents.members = True

        self.bot = commands.Bot(command_prefix='!', intents=intents)
        self.setup_events()
        self.logger = logging.getLogger('BotListener')

    def setup_events(self):
        """设置事件处理器"""

        @self.bot.event
        async def on_ready():
            self.logger.info(
                f'Bot已登录: {self.bot.user} (ID: {self.bot.user.id})'
            )
            self.logger.info(f'监听 {len(self.channels)} 个频道')

        @self.bot.event
        async def on_message(message):
            # 忽略自己的消息
            if message.author == self.bot.user:
                return

            # 只处理指定频道的消息
            if str(message.channel.id) not in self.channels:
                return

            await self.process_message(message)

    async def process_message(self, message):
        """处理消息

        Args:
            message: Discord消息对象
        """
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        # 基本信息
        info = {
            'source': 'BOT',
            'timestamp': timestamp,
            'channel': message.channel.name,
            'channel_id': message.channel.id,
            'author': str(message.author),
            'author_id': message.author.id,
            'content': message.content,
            'attachments': [att.url for att in message.attachments],
            'embeds': len(message.embeds)
        }

        # 日志输出
        log_msg = (
            f"[BOT] {info['channel']} | "
            f"{info['author']}: {info['content'][:50]}"
        )
        self.logger.info(log_msg)

        # 可以在这里添加更多处理逻辑
        # 例如：保存到数据库、发送webhook等
        # await self.on_message_received(info)

    async def on_message_received(self, message_info):
        """消息接收回调（供子类或外部使用）

        Args:
            message_info: 消息信息字典
        """
        pass

    async def start(self):
        """启动Bot"""
        try:
            await self.bot.start(self.token)
        except discord.LoginFailure:
            self.logger.error("Bot Token无效")
        except Exception as e:
            self.logger.error(f"Bot启动失败: {e}")

    async def stop(self):
        """停止Bot"""
        try:
            await self.bot.close()
            self.logger.info("Bot已停止")
        except Exception as e:
            self.logger.error(f"停止Bot失败: {e}")
