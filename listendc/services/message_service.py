#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
消息处理服务模块
"""

import logging
from datetime import datetime


class MessageService:
    """消息处理服务 - 统一处理所有消息相关业务"""

    def __init__(self):
        self.logger = logging.getLogger('MessageService')
        self.message_handlers = []

    def register_handler(self, handler):
        """注册消息处理器

        Args:
            handler: 处理器函数，接收message_info参数
        """
        self.message_handlers.append(handler)
        self.logger.info(f"注册消息处理器: {handler.__name__}")

    async def process_message(self, message_info):
        """处理消息

        Args:
            message_info: 消息信息字典
        """
        # 调用所有注册的处理器
        for handler in self.message_handlers:
            try:
                await handler(message_info)
            except Exception as e:
                self.logger.error(
                    f"处理器 {handler.__name__} 执行失败: {e}",
                    exc_info=True
                )

    async def save_to_database(self, message_info):
        """保存消息到数据库（示例）

        Args:
            message_info: 消息信息字典
        """
        # TODO: 实现数据库保存逻辑
        self.logger.debug(f"保存消息到数据库: {message_info.get('content', '')[:50]}")

    async def send_webhook(self, message_info):
        """发送到Webhook（示例）

        Args:
            message_info: 消息信息字典
        """
        # TODO: 实现webhook发送逻辑
        self.logger.debug(f"发送Webhook: {message_info.get('content', '')[:50]}")

    async def filter_message(self, message_info):
        """消息过滤（示例）

        Args:
            message_info: 消息信息字典

        Returns:
            bool: 是否通过过滤
        """
        # TODO: 实现消息过滤逻辑（违禁词、垃圾信息等）
        content = message_info.get('content', '')

        # 示例：过滤空消息
        if not content.strip():
            return False

        return True
