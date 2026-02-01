#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
User Token监听器模块
"""

import json
import logging
from datetime import datetime

try:
    import discord
except ImportError:
    raise ImportError("请安装 discord.py-self: pip install discord.py-self")

try:
    import paho.mqtt.client as mqtt
except ImportError:
    mqtt = None


class UserListener:
    """User Token监听器 - 用于监听其他频道"""

    def __init__(self, token, channels, mqtt_client=None, mqtt_config=None):
        """
        初始化User监听器

        Args:
            token: User Token
            channels: 要监听的频道ID列表
            mqtt_client: MQTT客户端实例（可选）
            mqtt_config: MQTT配置字典（可选）
        """
        self.token = token
        self.channels = set(str(ch) for ch in channels)
        self.client = discord.Client()
        self.mqtt_client = mqtt_client
        self.mqtt_config = mqtt_config or {}
        self.setup_events()
        self.logger = logging.getLogger('UserListener')

    def setup_events(self):
        """设置事件处理器"""

        @self.client.event
        async def on_ready():
            self.logger.info(
                f'User已登录: {self.client.user} (ID: {self.client.user.id})'
            )
            self.logger.info(f'监听 {len(self.channels)} 个频道')

        @self.client.event
        async def on_message(message):
            # 忽略自己的消息
            # if message.author == self.client.user:
            #     return

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
            'source': 'USER',
            'timestamp': timestamp,
            'channel': (
                message.channel.name
                if hasattr(message.channel, 'name')
                else 'DM'
            ),
            'channel_id': message.channel.id,
            'author': str(message.author),
            'author_id': message.author.id,
            'content': message.content,
            'attachments': [att.url for att in message.attachments],
            'embeds': len(message.embeds)
        }

        # 日志输出
        log_msg = (
            f"[USER] {info['channel']} | "
            f"{info['author']}: {info['content'][:50]}"
        )
        self.logger.info(log_msg)

        await self.procTest(message) 
        return 


        # 对特定频道进行特殊处理
        if message.channel.id == 1286023151532114002 or message.channel.id == 1286022517869514874:
            await self.procCommentary(message)
            return

        # 可以在这里添加更多处理逻辑
        # await self.on_message_received(info)
    async def procTest(self, message):
        payload = {
            "sender": "paul",
            "target_id": "1321313424717774949/1466080854274080818",
            "content": message.content,
            "attachments": [att.url for att in message.attachments]
        }

        # 发送到MQTT
        self._send_mqtt_message(payload) 

    async def procCommentary(self, message):
        """处理Commentary频道的特殊逻辑

        Args:
            message: Discord消息对象
        """
        # 规则1: 过滤bot发送的消息
        if message.author.bot:
            self.logger.debug(f"过滤bot消息: {message.author}")
            return

        # 获取消息内容
        content = message.content

        # 规则2: 过滤包含"live voice"的行（不区分大小写）
        if content:
            lines = content.split('\n')
            filtered_lines = []
            for line in lines:
                if 'live voice' not in line.lower():
                    filtered_lines.append(line)
            content = '\n'.join(filtered_lines).strip()

        # 如果过滤后内容为空，则不发送
        if not content:
            self.logger.debug("过滤后内容为空，跳过发送")
            return
        
        target_id = "1321046672712929280/1321344063626149908"
        if message.channel.id == 1286022517869514874:
            target_id = "1321046672712929280/1321343858830741544"

        payload = {
            "sender": "neil",
            "target_id": target_id,
            "content": content,
            "attachments": [att.url for att in message.attachments]

        }

        # 发送到MQTT
        self._send_mqtt_message(payload)

    def _send_mqtt_message(self, payload):
        """发送MQTT消息

        Args:
            content: 消息内容
        """
        if not self.mqtt_client:
            self.logger.warning("MQTT客户端未配置，无法发送消息")
            return

        try:
            topic = self.mqtt_config.get('topic', 'lis-msg-v2')
            qos = self.mqtt_config.get('qos', 1)

            result = self.mqtt_client.publish(
                topic,
                json.dumps(payload),
                qos=qos
            )

            if result.rc == mqtt.MQTT_ERR_SUCCESS:
                self.logger.info(f"MQTT消息已发送: {payload}")
            else:
                self.logger.error(f"MQTT消息发送失败: rc={result.rc}")

        except Exception as e:
            self.logger.error(f"发送MQTT消息异常: {e}", exc_info=True)

    async def on_message_received(self, message_info):
        """消息接收回调（供子类或外部使用）

        Args:
            message_info: 消息信息字典
        """
        pass

    async def start(self):
        """启动User客户端"""
        try:
            await self.client.start(self.token)
        except Exception as e:
            self.logger.error(f"User客户端启动失败: {e}")

    async def stop(self):
        """停止User客户端"""
        try:
            await self.client.close()
            self.logger.info("User客户端已停止")
        except Exception as e:
            self.logger.error(f"停止User客户端失败: {e}")
