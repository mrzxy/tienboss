#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Discord监听器 - 主入口
支持Bot Token、User Token监听，以及MQTT消息接收和发送
"""

import asyncio
import logging
import sys

from config import Config
from core import setup_logging, DiscordSenderManager
from listeners import BotListener, UserListener, MQTTListener
from services import MessageService


class Application:
    """应用主类"""

    def __init__(self, config_file='config.yaml'):
        """初始化应用

        Args:
            config_file: 配置文件路径
        """
        # 加载配置
        try:
            self.config = Config(config_file)
        except Exception as e:
            print(f"加载配置失败: {e}")
            sys.exit(1)

        # 设置日志
        log_config = self.config.get_log_config()
        setup_logging(log_config['level'], log_config['file'])
        self.logger = logging.getLogger('Application')

        # 初始化服务
        self.message_service = MessageService()
        self.sender_manager = None
        self.tasks = []

        self.logger.info("=" * 60)
        self.logger.info("Discord监听器启动")
        self.logger.info("=" * 60)

    async def initialize_sender_manager(self):
        """初始化Discord发送管理器"""
        user_accounts = self.config.get_user_accounts()

        if not user_accounts:
            self.logger.warning("未配置user_accounts，MQTT消息发送功能将不可用")
            return None

        self.logger.info(f"初始化Discord发送管理器，账号数: {len(user_accounts)}")
        sender_manager = DiscordSenderManager(user_accounts)
        await sender_manager.initialize()

        sender_tasks = await sender_manager.start_all()
        self.tasks.extend(sender_tasks)

        # 等待客户端就绪
        await asyncio.sleep(3)
        available_senders = sender_manager.get_available_senders()
        self.logger.info(f"可用发送账号: {available_senders}")

        return sender_manager

    def setup_mqtt_listener(self):
        """设置MQTT监听器"""
        mqtt_config = self.config.get_mqtt_config()

        if not mqtt_config.get('enabled', False):
            self.logger.info("MQTT未启用")
            return

        if not self.sender_manager:
            self.logger.error("MQTT启用但未配置发送账号，跳过MQTT监听器")
            return

        mqtt_listener = MQTTListener(mqtt_config, self.sender_manager)
        self.tasks.append(mqtt_listener.start())
        self.logger.info("MQTT监听器已创建")

    def setup_bot_listener(self):
        """设置Bot监听器"""
        bot_config = self.config.get_bot_config()
        bot_token = bot_config['token']
        bot_channels = bot_config['channels']

        if not bot_token or bot_token == 'YOUR_BOT_TOKEN_HERE':
            self.logger.info("Bot Token未配置，跳过Bot监听器")
            return

        if not bot_channels:
            self.logger.warning("Bot Token已配置但未指定监听频道")
            return

        bot_listener = BotListener(bot_token, bot_channels)
        self.tasks.append(bot_listener.start())
        self.logger.info(f"Bot监听器已创建，监听 {len(bot_channels)} 个频道")

    def setup_user_listener(self):
        """设置User监听器（支持多账号）"""
        user_listeners_config = self.config.get_user_listen_config()

        if not user_listeners_config:
            self.logger.info("未配置User监听")
            return

        user_accounts = self.config.get_user_accounts()
        if not user_accounts:
            self.logger.warning("User监听已配置但无可用账号")
            return

        # 获取MQTT配置用于发送消息
        mqtt_config = self.config.get_mqtt_config()
        mqtt_client = None

        # 如果MQTT已启用，创建一个用于发送的MQTT客户端
        if mqtt_config.get('enabled', False):
            try:
                import paho.mqtt.client as mqtt
                import ssl
                import os

                mqtt_client = mqtt.Client(client_id='user_listener_sender')

                # 设置认证
                username = mqtt_config.get('username', '')
                password = mqtt_config.get('password', '')
                if username and password:
                    mqtt_client.username_pw_set(username, password)

                # 配置TLS（如果启用）
                if mqtt_config.get('use_tls', False):
                    ca_certs = mqtt_config.get('ca_certs', None)

                    # 处理相对路径
                    if ca_certs and not os.path.isabs(ca_certs):
                        # 获取当前文件所在目录
                        current_dir = os.path.dirname(os.path.abspath(__file__))
                        ca_certs = os.path.join(current_dir, ca_certs)

                    self.logger.info(f"配置TLS证书: {ca_certs}")

                    mqtt_client.tls_set(
                        ca_certs=ca_certs,
                        certfile=mqtt_config.get('certfile', None),
                        keyfile=mqtt_config.get('keyfile', None),
                        cert_reqs=ssl.CERT_REQUIRED if not mqtt_config.get('tls_insecure', False) else ssl.CERT_NONE,
                        tls_version=ssl.PROTOCOL_TLS
                    )

                    if mqtt_config.get('tls_insecure', False):
                        mqtt_client.tls_insecure_set(True)

                # 连接到broker
                broker = mqtt_config.get('broker', 'localhost')
                port = mqtt_config.get('port', 1883)
                mqtt_client.connect(broker, port, keepalive=60)
                mqtt_client.loop_start()

                self.logger.info(f"为UserListener创建MQTT发送客户端: {broker}:{port} (TLS: {mqtt_config.get('use_tls', False)})")
            except Exception as e:
                self.logger.warning(f"创建MQTT客户端失败: {e}，UserListener将无法发送MQTT消息")
                mqtt_client = None

        listener_count = 0

        # 遍历每个账号的监听配置
        for account_id, targets in user_listeners_config.items():
            # 检查账号是否存在
            if account_id not in user_accounts:
                self.logger.warning(
                    f"监听配置中的账号 {account_id} 不存在，跳过"
                )
                continue

            account_info = user_accounts[account_id]
            token = account_info.get('token')

            # 验证token
            if not token or token.startswith('YOUR_USER_TOKEN'):
                self.logger.warning(
                    f"账号 {account_id} 的Token无效，跳过"
                )
                continue

            # 解析并转换监听目标格式
            channels = []
            for target in targets:
                if '/' in target:
                    # 格式: server_id/channel_id
                    server_id, channel_id = target.split('/', 1)
                    channels.append(channel_id)
                else:
                    # 纯channel_id格式
                    channels.append(target)

            if not channels:
                self.logger.warning(
                    f"账号 {account_id} 没有有效的监听目标，跳过"
                )
                continue

            # 创建监听器，传入MQTT客户端和配置
            account_name = account_info.get('name', account_id)
            anthropic_config = self.config.get_anthropic_config()
            user_listener = UserListener(token, channels, mqtt_client, mqtt_config, anthropic_config)
            self.tasks.append(user_listener.start())
            listener_count += 1

            self.logger.info(
                f"User监听器已创建: {account_name} ({account_id}), "
                f"监听 {len(channels)} 个频道"
            )

        if listener_count == 0:
            self.logger.info("未创建任何User监听器")
        else:
            self.logger.info(f"总共创建 {listener_count} 个User监听器")

    async def run(self):
        """运行应用"""
        try:
            # 1. 初始化发送管理器
            self.sender_manager = await self.initialize_sender_manager()

            # 2. 设置MQTT监听器
            self.setup_mqtt_listener()

            # 3. 设置Bot监听器（可选）
            self.setup_bot_listener()

            # 4. 设置User监听器（可选）
            self.setup_user_listener()

            # 检查是否有任务
            if not self.tasks:
                self.logger.error("没有可启动的服务，请检查配置")
                sys.exit(1)

            self.logger.info(f"启动 {len(self.tasks)} 个服务...")

            # 运行所有任务
            await asyncio.gather(*self.tasks)

        except KeyboardInterrupt:
            self.logger.info("收到中断信号，正在关闭...")
        except Exception as e:
            self.logger.error(f"运行时错误: {e}", exc_info=True)
        finally:
            await self.cleanup()

    async def cleanup(self):
        """清理资源"""
        self.logger.info("清理资源...")
        if self.sender_manager:
            await self.sender_manager.stop_all()


def main():
    """主函数"""
    try:
        app = Application()
        asyncio.run(app.run())
    except KeyboardInterrupt:
        print("\n程序已退出")
    except Exception as e:
        print(f"程序异常: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
