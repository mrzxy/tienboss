#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Discord消息发送管理模块
"""

import asyncio
import logging
import sqlite3
import os
import aiohttp
import io
from datetime import datetime

try:
    import discord
except ImportError:
    raise ImportError("请安装 discord.py-self: pip install discord.py-self")


class DiscordSenderManager:
    """Discord消息发送管理器 - 管理多个user账号"""

    def __init__(self, user_accounts):
        """
        初始化发送管理器

        Args:
            user_accounts: 用户账号配置字典 {sender_id: {token, name}}
        """
        self.user_accounts = user_accounts
        self.clients = {}
        self.ready_clients = {}
        self.logger = logging.getLogger('SenderManager')
        self._init_db()

    def _init_db(self):
        """初始化 SQLite 数据库，创建消息映射表"""
        db_dir = os.path.dirname(os.path.abspath(__file__))
        self.db_path = os.path.join(db_dir, '..', 'listeners', 'messages.db')
        self.db_path = os.path.normpath(self.db_path)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS discord_messages (
                    discord_msg_id TEXT PRIMARY KEY,
                    msg_id         TEXT NOT NULL,
                    channel_id     TEXT NOT NULL,
                    created_at     TEXT NOT NULL
                )
            ''')
            conn.commit()

    def save_message(self, discord_msg_id: str, msg_id: str, channel_id: str):
        """保存 discord_msg_id -> 目标 msg_id 映射"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                'INSERT OR REPLACE INTO discord_messages (discord_msg_id, msg_id, channel_id, created_at) VALUES (?, ?, ?, ?)',
                (str(discord_msg_id), str(msg_id), str(channel_id), datetime.now().isoformat())
            )
            conn.commit()

    async def initialize(self):
        """初始化所有客户端"""
        for sender_id, account in self.user_accounts.items():
            token = account.get('token')
            name = account.get('name', sender_id)

            if not token or token.startswith('YOUR_USER_TOKEN'):
                self.logger.warning(f"账号 {sender_id} ({name}) 的Token未配置，跳过")
                continue

            try:
                client = discord.Client()

                # 使用闭包捕获变量
                @client.event
                async def on_ready(sender_id=sender_id, name=name, client=client):
                    self.ready_clients[sender_id] = client
                    self.logger.info(
                        f'发送账号已就绪: {sender_id} ({name}) - {client.user}'
                    )

                self.clients[sender_id] = {
                    'client': client,
                    'token': token,
                    'name': name,
                    'task': None
                }

                self.logger.info(f"准备启动账号: {sender_id} ({name})")

            except Exception as e:
                self.logger.error(f"创建客户端失败 {sender_id}: {e}")

    async def start_all(self):
        """启动所有客户端

        Returns:
            list: 任务列表
        """
        tasks = []
        for sender_id, info in self.clients.items():
            task = asyncio.create_task(self._start_client(sender_id, info))
            info['task'] = task
            tasks.append(task)
        return tasks

    async def _start_client(self, sender_id, info):
        """启动单个客户端

        Args:
            sender_id: 发送者ID
            info: 客户端信息字典
        """
        try:
            await info['client'].start(info['token'])
        except Exception as e:
            self.logger.error(f"账号 {sender_id} 启动失败: {e}")

    async def send_message(self, sender_id, server_id, channel_id, content, attachments=None,
                           discord_msg_id: str = None, ref_msg_id: str = None):
        """发送消息（支持跨服务器）

        Args:
            sender_id: 发送者ID
            server_id: 服务器ID（可选，用于验证）
            channel_id: 频道ID
            content: 消息内容
            attachments: 附件URL列表（可选）
            discord_msg_id: 原始 Discord 消息 ID（用于建立映射，可选）
            ref_msg_id: 要回复的目标频道消息 ID（可选）

        Returns:
            bool: 是否成功
        """
        if sender_id not in self.ready_clients:
            self.logger.error(f"发送失败: 账号 {sender_id} 未就绪或未配置")
            return False

        client = self.ready_clients[sender_id]

        try:
            # 获取频道对象
            channel = await client.fetch_channel(int(channel_id))

            # 验证服务器ID（如果提供）
            if server_id:
                if hasattr(channel, 'guild') and channel.guild:
                    actual_server_id = str(channel.guild.id)
                    if actual_server_id != server_id:
                        self.logger.warning(
                            f"服务器ID不匹配: 期望 {server_id}, 实际 {actual_server_id}"
                        )
                else:
                    self.logger.warning(f"频道 {channel_id} 不属于任何服务器（可能是DM）")

            # 处理附件
            files = []
            if attachments:
                try:
                    async with aiohttp.ClientSession() as session:
                        for url in attachments:
                            async with session.get(url) as resp:
                                if resp.status == 200:
                                    data = await resp.read()
                                    filename = url.split('/')[-1].split('?')[0]
                                    files.append(discord.File(io.BytesIO(data), filename=filename))
                                    self.logger.debug(f"下载附件成功: {filename}")
                                else:
                                    self.logger.warning(f"下载附件失败 ({resp.status}): {url}")
                except Exception as e:
                    self.logger.error(f"处理附件时出错: {e}")

            # 构造 reply 对象（如果有 ref_msg_id）
            reference = None
            if ref_msg_id:
                try:
                    reference = discord.MessageReference(
                        message_id=int(ref_msg_id),
                        channel_id=int(channel_id),
                        fail_if_not_exists=False
                    )
                    self.logger.info(f"设置回复消息: ref_msg_id={ref_msg_id}")
                except Exception as e:
                    self.logger.warning(f"构造 reply reference 失败: {e}")

            # 发送消息
            if files:
                sent_msg = await channel.send(content=content, files=files, reference=reference)
            else:
                sent_msg = await channel.send(content, reference=reference)

            # 构建日志信息
            if server_id:
                log_target = f"服务器 {server_id}/频道 {channel_id}"
            else:
                log_target = f"频道 {channel_id}"

            attachment_info = f" (含{len(files)}个附件)" if files else ""
            self.logger.info(
                f"[{sender_id}] 发送成功 -> {log_target}: {content[:50]}{attachment_info}, msg_id={sent_msg.id}"
            )

            # 保存原始消息 id -> 目标消息 id 的映射
            if discord_msg_id:
                self.save_message(discord_msg_id, str(sent_msg.id), channel_id)
                self.logger.info(f"已保存消息映射: {discord_msg_id} -> {sent_msg.id}")

            return True

        except discord.NotFound:
            self.logger.error(f"频道不存在: {channel_id}")
            return False
        except discord.Forbidden:
            self.logger.error(f"没有权限发送到频道: {channel_id}")
            return False
        except ValueError as e:
            self.logger.error(f"ID格式错误: {e}")
            return False
        except Exception as e:
            self.logger.error(f"发送消息失败: {e}")
            return False

    def get_available_senders(self):
        """获取可用的发送账号列表

        Returns:
            list: 可用的sender_id列表
        """
        return list(self.ready_clients.keys())

    def get_client(self, sender_id):
        """获取指定的客户端

        Args:
            sender_id: 发送者ID

        Returns:
            discord.Client or None
        """
        return self.ready_clients.get(sender_id)

    async def stop_all(self):
        """停止所有客户端"""
        self.logger.info("停止所有Discord客户端...")
        for sender_id, client in self.ready_clients.items():
            try:
                await client.close()
                self.logger.info(f"账号 {sender_id} 已关闭")
            except Exception as e:
                self.logger.error(f"关闭账号 {sender_id} 失败: {e}")
