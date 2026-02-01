#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MQTT连接诊断脚本
"""

import paho.mqtt.client as mqtt
import ssl
import time
import yaml


def on_connect(client, userdata, flags, rc):
    """连接回调"""
    error_messages = {
        0: "✓ 连接成功",
        1: "✗ 协议版本不正确",
        2: "✗ 客户端标识符无效",
        3: "✗ 服务器不可用",
        4: "✗ 用户名或密码错误",
        5: "✗ 未授权"
    }
    print(f"\n连接结果 (rc={rc}): {error_messages.get(rc, f'未知错误码: {rc}')}")

    if rc == 0:
        print(f"✓ 成功连接到 {userdata['broker']}:{userdata['port']}")
        client.disconnect()


def diagnose_mqtt_connection():
    """诊断MQTT连接"""

    # 读取配置
    import os
    config_path = os.path.join(os.path.dirname(__file__), 'config.yaml')
    with open(config_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)

    mqtt_config = config['mqtt']

    print("=" * 60)
    print("MQTT 连接诊断")
    print("=" * 60)
    print(f"Broker: {mqtt_config['broker']}")
    print(f"Port: {mqtt_config['port']}")
    print(f"Username: {mqtt_config['username']}")
    print(f"Password: {'*' * len(mqtt_config['password'])}")
    print(f"TLS: {mqtt_config['use_tls']}")
    print(f"CA Certs: {mqtt_config['ca_certs']}")
    print("=" * 60)

    # 创建客户端
    client = mqtt.Client(
        client_id=mqtt_config['client_id'],
        clean_session=True,
        protocol=mqtt.MQTTv311,
        userdata={
            'broker': mqtt_config['broker'],
            'port': mqtt_config['port']
        }
    )

    client.on_connect = on_connect

    # 设置认证
    print(f"\n设置认证信息...")
    client.username_pw_set(mqtt_config['username'], mqtt_config['password'])

    # 配置TLS
    if mqtt_config['use_tls']:
        print(f"配置TLS...")
        try:
            # 如果是相对路径，转换为绝对路径
            ca_certs = mqtt_config['ca_certs']
            if not os.path.isabs(ca_certs):
                ca_certs = os.path.join(os.path.dirname(__file__), ca_certs)

            print(f"CA证书路径: {ca_certs}")
            if not os.path.exists(ca_certs):
                print(f"✗ CA证书文件不存在: {ca_certs}")
                return

            client.tls_set(
                ca_certs=ca_certs,
                cert_reqs=ssl.CERT_REQUIRED,
                tls_version=ssl.PROTOCOL_TLS
            )
            print("✓ TLS配置成功")
        except Exception as e:
            print(f"✗ TLS配置失败: {e}")
            return

    # 尝试连接
    print(f"\n正在连接到 {mqtt_config['broker']}:{mqtt_config['port']}...")
    try:
        client.connect(
            mqtt_config['broker'],
            mqtt_config['port'],
            keepalive=60
        )

        # 等待连接结果
        client.loop_start()
        time.sleep(3)
        client.loop_stop()

    except Exception as e:
        print(f"\n✗ 连接异常: {e}")
        print("\n可能的原因:")
        print("1. 网络连接问题")
        print("2. Broker地址或端口错误")
        print("3. 防火墙阻止连接")

    print("\n" + "=" * 60)
    print("诊断建议:")
    print("=" * 60)
    print("如果 rc=4 (用户名或密码错误)，请检查:")
    print("1. 登录 EMQX Cloud 控制台验证用户名密码")
    print("2. 检查用户是否有订阅/发布权限")
    print("3. 确认密码没有特殊字符转义问题")
    print("4. 尝试重置密码")
    print("\n如果 rc=5 (未授权)，请检查:")
    print("1. ACL权限配置")
    print("2. 主题订阅/发布权限")
    print("=" * 60)


if __name__ == '__main__':
    diagnose_mqtt_connection()
