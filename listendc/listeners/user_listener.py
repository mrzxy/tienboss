#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
User Token监听器模块
"""

import json
import logging
import re
import aiohttp
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

    def __init__(self, token, channels, mqtt_client=None, mqtt_config=None, anthropic_config=None):
        """
        初始化User监听器

        Args:
            token: User Token
            channels: 要监听的频道ID列表
            mqtt_client: MQTT客户端实例（可选）
            mqtt_config: MQTT配置字典（可选）
            anthropic_config: Anthropic API配置字典（可选）
        """
        self.token = token
        self.channels = set(str(ch) for ch in channels)
        self.client = discord.Client()
        self.mqtt_client = mqtt_client
        self.mqtt_config = mqtt_config or {}
        self.anthropic_config = anthropic_config or {}
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

        # 对特定频道进行特殊处理
        # 1286023151532114002 brando-commentary
        # 1286022517869514874 brandos-trade-alerts 
        if message.channel.id == 1286023151532114002 or message.channel.id == 1286022517869514874:
            await self.procCommentary(message)
            return
         
        elif message.channel.id == 1072731733402865714 or message.channel.id == 1467778640132575369:
            await self.procShunge(message)
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


    async def procContent(self, content):
        """处理消息内容，移除Discord角色提及等特殊标记

        Args:
            content: 原始消息内容

        Returns:
            str: 处理后的内容
        """
        if not content:
            return content

        # 移除角色提及标记 <@&任意字符>，支持多个
        content = re.sub(r'<@&[^>]+>', '', content)

        return content


    async def procShunge(self, message):
        """处理Shunge频道的特殊逻辑

        Args:
            message: Discord消息对象
        """
        content = await self.procContent(message.content)

        # 规范化换行符
        content = content.replace('\n', '\r\n')

        # 过滤空内容
        if not content or content.strip() == '':
            self.logger.debug('过滤 内容为空或者是图片')
            return


        # 翻译成英文
        trans = await self.fetch_anthropic_api(content)
        if not trans.get('success'):
            self.logger.error(f"翻译失败: {content}, err: {trans.get('msg', 'Unknown error')}")
            return

        en_content = trans.get('data', {}).get('en_content', '')

        # 如果en_content开头是"shunge"，替换成空
        if en_content and en_content.lower().startswith('shunge'):
            import re
            en_content = re.sub(r'^shunge', '', en_content, flags=re.IGNORECASE)

        # 检查违禁关键字
        ignore_keywords = [
            'translate',
            'wechat',
            'nafef.org@gmail.com',
            'article',
            'translating',
            'appreciate',
            'scam',
            'schemes',
            '杀猪盘',
            'fraudulent',
        ]

        should_ignore = any(keyword.lower() in en_content.lower() for keyword in ignore_keywords)
        if should_ignore:
            self.logger.info(f'内容包含敏感关键字，已忽略: {en_content}')
            return

        # 移除 "Brother Shun" 或 "Brother Shun."（忽略大小写）
        en_content = re.sub(r'Brother\s+Shun\.?', '', en_content, flags=re.IGNORECASE)
        en_content = en_content.strip()

        # 发布英文消息到MQTT
        payload_en = {
            "sender": "innercircle",
            "target_id": "1321046672712929280/1325294881517867018",
            "content": en_content
        }
        self._send_mqtt_message(payload_en)
        self.logger.info(f"已发送英文消息到 lis-msg/innercircle")

        # 翻译成中文
        cn_trans = await self.fetch_anthropic_api_innercircle_cn(en_content)
        if not cn_trans.get('success'):
            self.logger.error(f"中文翻译失败: {en_content}, err: {cn_trans.get('msg', 'Unknown error')}")
            return

        cn_content = cn_trans.get('data', {}).get('en_content', '')

        # 如果cn_content开头是"顺哥。"，替换成空
        if cn_content and cn_content.startswith('顺哥。'):
            cn_content = cn_content.replace('顺哥。', '', 1)

        # 调用webhook发送中文内容
        await self.call_webhook(
            url='https://discord.com/api/webhooks/1433668431512731690/bRZ4HRR3oeBdFzo0Y8kcgXV7rJfFbsdCSCyhdcz-sZtFksESiWE1dnPAaaYxO1B4EoyO',
            data={
                'content': cn_content,
                'embeds': []
            }
        )
        self.logger.info(f"已通过webhook发送中文消息")

    def contains_chinese(self, text):
        """检查文本是否包含中文字符

        Args:
            text: 要检查的文本

        Returns:
            bool: 是否包含中文
        """
        return bool(re.search(r'[\u4e00-\u9fff]', text))

    async def fetch_anthropic_api(self, content, tip=None):
        """调用Anthropic API进行翻译（中文到英文）

        Args:
            content: 要翻译的内容
            tip: 系统提示（可选）

        Returns:
            dict: 翻译结果 {'success': bool, 'data': {'en_content': str, 'cn_content': str}, 'msg': str}
        """
        if not self.contains_chinese(content):
            return {
                'success': True,
                'data': {'en_content': content, 'cn_content': content}
            }

        # 从配置读取API设置
        api_key = self.anthropic_config.get('api_key', '')
        api_url = self.anthropic_config.get('api_url', 'https://api.anthropic.com/v1/messages')
        model = self.anthropic_config.get('model', 'claude-opus-4-1-20250805')
        max_tokens = self.anthropic_config.get('max_tokens', 20000)
        temperature = self.anthropic_config.get('temperature', 1)

        # 验证 API 密钥
        if not api_key:
            return {
                'success': False,
                'msg': 'Anthropic API key not configured'
            }

        if not api_key.startswith('sk-ant-'):
            return {
                'success': False,
                'msg': 'Invalid API key format. API key should start with "sk-ant-"'
            }

        # 默认提示
        if tip is None:
            tip = "Translate the following Chinese text to English. Only provide the translation, no explanations."

        payload = {
            "model": model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "system": tip,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": content
                        }
                    ]
                }
            ]
        }

        try:
            self.logger.debug(f'Sending request to Anthropic API')

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    api_url,
                    headers={
                        'Content-Type': 'application/json',
                        'x-api-key': api_key,
                        'anthropic-version': '2023-06-01'
                    },
                    json=payload
                ) as response:
                    self.logger.debug(f'Response status: {response.status}')

                    if response.status != 200:
                        error_text = await response.text()
                        self.logger.error(f'API Error Response: {error_text}')
                        return {
                            'success': False,
                            'msg': f'HTTP error! status: {response.status}, response: {error_text}'
                        }

                    result = await response.json()
                    self.logger.debug(f'API Response received')

                    return_content = result['content'][0]['text']

                    return {
                        'success': True,
                        'data': {
                            'en_content': return_content,
                            'cn_content': content
                        },
                        'msg': 'ok'
                    }

        except Exception as e:
            self.logger.error(f'Anthropic API Error: {e}', exc_info=True)
            return {
                'success': False,
                'msg': str(e)
            }

    async def fetch_anthropic_api_innercircle_cn(self, content, tip=None):
        """调用Anthropic API进行翻译（英文到中文）

        Args:
            content: 要翻译的内容（英文）
            tip: 系统提示（可选）

        Returns:
            dict: 翻译结果 {'success': bool, 'data': {'en_content': str}, 'msg': str}
        """
        if not content or not content.strip():
            return {
                'success': False,
                'msg': 'Content is empty'
            }

        # 从配置读取API设置
        api_key = self.anthropic_config.get('api_key', '')
        api_url = self.anthropic_config.get('api_url', 'https://api.anthropic.com/v1/messages')
        model = self.anthropic_config.get('model', 'claude-opus-4-1-20250805')
        max_tokens = self.anthropic_config.get('max_tokens', 20000)
        temperature = self.anthropic_config.get('temperature', 1)

        # 验证 API 密钥
        if not api_key:
            return {
                'success': False,
                'msg': 'Anthropic API key not configured'
            }

        if not api_key.startswith('sk-ant-'):
            return {
                'success': False,
                'msg': 'Invalid API key format. API key should start with "sk-ant-"'
            }

        # 默认提示（英文到中文）
        if tip is None:
            tip = "Translate the following English text to Chinese. Only provide the translation, no explanations."

        payload = {
            "model": model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "system": tip,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": content
                        }
                    ]
                }
            ]
        }

        try:
            self.logger.debug(f'Sending request to Anthropic API for Chinese translation')

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    api_url,
                    headers={
                        'Content-Type': 'application/json',
                        'x-api-key': api_key,
                        'anthropic-version': '2023-06-01'
                    },
                    json=payload
                ) as response:
                    self.logger.debug(f'Response status: {response.status}')

                    if response.status != 200:
                        error_text = await response.text()
                        self.logger.error(f'API Error Response: {error_text}')
                        return {
                            'success': False,
                            'msg': f'HTTP error! status: {response.status}, response: {error_text}'
                        }

                    result = await response.json()
                    self.logger.debug(f'API Response received')

                    return_content = result['content'][0]['text']

                    return {
                        'success': True,
                        'data': {
                            'en_content': return_content  # 注意：这里返回的是中文内容，但key保持为en_content以兼容原代码
                        },
                        'msg': 'ok'
                    }

        except Exception as e:
            self.logger.error(f'Anthropic API Error: {e}', exc_info=True)
            return {
                'success': False,
                'msg': str(e)
            }

    async def call_webhook(self, url, data):
        """调用Discord Webhook

        Args:
            url: Webhook URL
            data: 要发送的数据

        Returns:
            bool: 是否成功
        """
        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=data) as resp:
                    if resp.status in [200, 204]:
                        self.logger.debug(f"Webhook调用成功: {resp.status}")
                        return True
                    else:
                        self.logger.error(f"Webhook调用失败: {resp.status}")
                        return False
        except Exception as e:
            self.logger.error(f"调用webhook异常: {e}", exc_info=True)
            return False


    async def procCommentary(self, message):
        """处理Commentary频道的特殊逻辑

        Args:
            message: Discord消息对象
        """
        # 规则1: 过滤bot发送的消息
        # if message.author.bot:
        #     self.logger.info(f"过滤bot消息: {message.author}")
        #     return

        content = await self.procContent(message.content)

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
