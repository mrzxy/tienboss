#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MQTT监听器模块 - 支持断线自动重连
"""

import asyncio
import json
import logging
import os
import ssl
import time
from datetime import datetime

try:
    import paho.mqtt.client as mqtt
except ImportError:
    raise ImportError("请安装 paho-mqtt: pip install paho-mqtt")


class MQTTListener:
    """MQTT监听器 - 接收消息并通过Discord发送，支持断线自动重连"""

    def __init__(self, config, sender_manager):
        """
        初始化MQTT监听器

        Args:
            config: MQTT配置字典
            sender_manager: Discord发送管理器实例
        """
        self.config = config
        self.sender_manager = sender_manager
        self.logger = logging.getLogger('MQTTListener')

        # 基本配置
        self.broker = config.get('broker', 'localhost')
        self.port = config.get('port', 1883)
        self.username = config.get('username', '')
        self.password = config.get('password', '')
        self.topic = config.get('topic', 'lis-msg-v2')
        self.qos = config.get('qos', 1)

        # 生成唯一的client_id避免冲突
        import uuid
        client_id_prefix = config.get('client_id_prefix', config.get('client_id', 'discord_listener'))
        self.client_id = f"{client_id_prefix}_{uuid.uuid4().hex[:8]}"

        # SSL/TLS配置
        self.use_tls = config.get('use_tls', False)
        self.ca_certs = config.get('ca_certs', None)
        self.certfile = config.get('certfile', None)
        self.keyfile = config.get('keyfile', None)
        self.tls_insecure = config.get('tls_insecure', False)

        # 重连配置
        self.auto_reconnect = config.get('auto_reconnect', True)
        self.reconnect_min_delay = config.get('reconnect_min_delay', 1)
        self.reconnect_max_delay = config.get('reconnect_max_delay', 120)
        self.keepalive = config.get('keepalive', 60)

        # 状态管理
        self.mqtt_client = None
        self.loop = None
        self.connected = False
        self.running = False
        self.connection_time = None
        self.last_message_time = None
        self.reconnect_count = 0
        self.message_count = 0

    def on_connect(self, client, userdata, flags, rc):
        """MQTT连接回调

        Args:
            client: MQTT客户端
            userdata: 用户数据
            flags: 连接标志
            rc: 返回码
        """
        if rc == 0:
            self.connected = True
            self.connection_time = datetime.now()
            self.reconnect_count = 0

            connection_type = "重连成功" if flags.get('session present') else "首次连接"
            self.logger.info(
                f"MQTT {connection_type}: {self.broker}:{self.port}"
            )

            # 订阅主题
            result = client.subscribe(self.topic, qos=self.qos)
            if result[0] == mqtt.MQTT_ERR_SUCCESS:
                self.logger.info(f"✓ 订阅主题成功: {self.topic}")
            else:
                self.logger.error(f"✗ 订阅主题失败: {self.topic}")

        else:
            self.connected = False
            error_messages = {
                1: "协议版本不正确",
                2: "客户端标识符无效",
                3: "服务器不可用",
                4: "用户名或密码错误",
                5: "未授权"
            }
            error_msg = error_messages.get(rc, f"未知错误码: {rc}")
            self.logger.error(f"MQTT连接失败: {error_msg}")

    def on_disconnect(self, client, userdata, rc):
        """MQTT断开连接回调

        Args:
            client: MQTT客户端
            userdata: 用户数据
            rc: 返回码
        """
        self.connected = False

        if rc != 0:
            self.reconnect_count += 1
            self.logger.warning(
                f"MQTT意外断开连接 (返回码: {rc}), "
                f"将自动重连 (第{self.reconnect_count}次)"
            )
        else:
            self.logger.info("MQTT正常断开连接")

        # 显示连接时长
        if self.connection_time:
            uptime = datetime.now() - self.connection_time
            self.logger.info(f"本次连接时长: {uptime}")
            self.connection_time = None

    def on_message(self, client, userdata, msg):
        """MQTT消息回调

        Args:
            client: MQTT客户端
            userdata: 用户数据
            msg: 消息对象
        """
        try:
            self.last_message_time = datetime.now()
            self.message_count += 1

            payload = json.loads(msg.payload.decode('utf-8'))
            self.logger.info(
                f"[#{self.message_count}] 收到MQTT消息 (主题: {msg.topic}): {payload}"
            )

            sender = payload.get('sender')
            target_id = payload.get('target_id')
            content = payload.get('content', '')
            attachments = payload.get('attachments', [])

            # 验证必需字段
            if not sender:
                self.logger.error("消息缺少sender字段")
                return

            if not target_id:
                self.logger.error("消息缺少target_id字段")
                return

            # 解析target_id: server_id/channel_id
            try:
                if '/' in target_id:
                    server_id, channel_id = target_id.split('/', 1)
                else:
                    # 如果没有/，则认为是纯channel_id，server_id为None
                    server_id = None
                    channel_id = target_id
                    self.logger.warning(
                        f"target_id格式不标准，建议使用'server_id/channel_id'格式: {target_id}"
                    )
            except Exception as e:
                self.logger.error(f"解析target_id失败: {target_id}, 错误: {e}")
                return

            # 在事件循环中执行发送任务
            if self.loop:
                asyncio.run_coroutine_threadsafe(
                    self.sender_manager.send_message(
                        sender, server_id, channel_id, content, attachments
                    ),
                    self.loop
                )
            else:
                self.logger.error("事件循环未初始化，无法发送消息")

        except json.JSONDecodeError as e:
            self.logger.error(f"解析MQTT消息JSON失败: {e}")
            self.logger.debug(f"原始消息: {msg.payload}")
        except Exception as e:
            self.logger.error(f"处理MQTT消息失败: {e}", exc_info=True)

    def on_subscribe(self, client, userdata, mid, granted_qos):
        """订阅成功回调"""
        self.logger.debug(f"订阅确认 (mid: {mid}, QoS: {granted_qos})")

    def on_log(self, client, userdata, level, buf):
        """日志回调（用于调试）"""
        # 只在DEBUG级别输出paho-mqtt的日志
        if self.logger.isEnabledFor(logging.DEBUG):
            self.logger.debug(f"[MQTT] {buf}")

    def _configure_client(self):
        """配置MQTT客户端"""
        # 创建客户端
        self.mqtt_client = mqtt.Client(
            client_id=self.client_id,
            clean_session=True,
            protocol=mqtt.MQTTv311
        )

        # 设置回调
        self.mqtt_client.on_connect = self.on_connect
        self.mqtt_client.on_disconnect = self.on_disconnect
        self.mqtt_client.on_message = self.on_message
        self.mqtt_client.on_subscribe = self.on_subscribe
        self.mqtt_client.on_log = self.on_log

        # 设置认证
        if self.username and self.password:
            self.mqtt_client.username_pw_set(self.username, self.password)
            self.logger.debug(f"设置MQTT认证: {self.username}")

        # 配置SSL/TLS
        if self.use_tls:
            try:
                self.logger.info("启用TLS/SSL连接")

                # 处理CA证书路径：如果是相对路径，转换为绝对路径
                ca_certs = self.ca_certs
                if ca_certs and not os.path.isabs(ca_certs):
                    # 获取配置文件所在目录（假设证书文件在项目根目录）
                    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                    ca_certs = os.path.join(project_root, ca_certs)
                    self.logger.debug(f"CA证书相对路径转换: {self.ca_certs} -> {ca_certs}")

                if ca_certs and not os.path.exists(ca_certs):
                    raise FileNotFoundError(f"CA证书文件不存在: {ca_certs}")

                self.mqtt_client.tls_set(
                    ca_certs=ca_certs,
                    certfile=self.certfile,
                    keyfile=self.keyfile,
                    cert_reqs=ssl.CERT_REQUIRED if not self.tls_insecure else ssl.CERT_NONE,
                    tls_version=ssl.PROTOCOL_TLS
                )
                if self.tls_insecure:
                    self.mqtt_client.tls_insecure_set(True)
                    self.logger.warning("TLS证书验证已禁用（不安全）")
                else:
                    self.logger.info(f"TLS证书: {ca_certs}")
            except Exception as e:
                self.logger.error(f"配置TLS失败: {e}")
                raise

        # 配置自动重连
        if self.auto_reconnect:
            self.mqtt_client.reconnect_delay_set(
                min_delay=self.reconnect_min_delay,
                max_delay=self.reconnect_max_delay
            )
            self.logger.info(
                f"自动重连已启用 (延迟: {self.reconnect_min_delay}-{self.reconnect_max_delay}秒)"
            )

    async def start(self):
        """启动MQTT监听器"""
        self.loop = asyncio.get_event_loop()
        self.running = True

        try:
            # 配置客户端
            self._configure_client()

            # 首次连接
            connection_type = "TLS" if self.use_tls else "TCP"
            self.logger.info(
                f"连接到MQTT Broker ({connection_type}): "
                f"{self.broker}:{self.port}, ClientID: {self.client_id}"
            )

            self.mqtt_client.connect(
                self.broker,
                self.port,
                keepalive=self.keepalive
            )

            # 在后台线程中运行MQTT客户端（支持自动重连）
            self.mqtt_client.loop_start()

            # 状态监控循环
            await self._monitor_loop()

        except Exception as e:
            self.logger.error(f"MQTT启动失败: {e}", exc_info=True)
            raise
        finally:
            self.running = False

    async def _monitor_loop(self):
        """监控循环 - 定期输出状态信息"""
        last_status_time = time.time()
        status_interval = 600  # 每5分钟输出一次状态

        while self.running:
            await asyncio.sleep(5)

            # 定期输出状态
            current_time = time.time()
            if current_time - last_status_time >= status_interval:
                self._log_status()
                last_status_time = current_time

    def _log_status(self):
        """记录运行状态"""
        status = "已连接" if self.connected else "未连接"
        uptime = ""
        if self.connection_time:
            uptime = f", 运行时长: {datetime.now() - self.connection_time}"

        self.logger.info(
            f"MQTT状态: {status}{uptime}, "
            f"已接收消息: {self.message_count}, "
            f"重连次数: {self.reconnect_count}"
        )

    def stop(self):
        """停止MQTT监听器"""
        self.running = False

        if self.mqtt_client:
            try:
                self.mqtt_client.loop_stop()
                self.mqtt_client.disconnect()
                self.logger.info("MQTT监听器已停止")
            except Exception as e:
                self.logger.error(f"停止MQTT监听器失败: {e}")

        # 输出最终统计
        self.logger.info(
            f"MQTT监听器统计: "
            f"总消息数: {self.message_count}, "
            f"总重连次数: {self.reconnect_count}"
        )

    def is_connected(self):
        """检查是否已连接

        Returns:
            bool: 连接状态
        """
        return self.connected

    def get_stats(self):
        """获取统计信息

        Returns:
            dict: 统计信息字典
        """
        uptime = None
        if self.connection_time:
            uptime = (datetime.now() - self.connection_time).total_seconds()

        return {
            'connected': self.connected,
            'message_count': self.message_count,
            'reconnect_count': self.reconnect_count,
            'uptime_seconds': uptime,
            'last_message_time': self.last_message_time,
            'broker': self.broker,
            'port': self.port,
            'topic': self.topic
        }
