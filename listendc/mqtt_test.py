#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MQTT测试脚本 - 用于测试发送消息到Discord
"""

import json
import paho.mqtt.client as mqtt
import time


def send_test_message(broker='localhost', port=1883, topic='lis-msg-v2'):
    """发送测试消息"""

    # 测试消息（新格式：使用target_id）
    test_message = {
        "sender": "paul",
        "target_id": "1321313424717774949/1415604571597963404",
        "content": "这是一条来自MQTT的测试消息"
    }

    print(f"连接到MQTT Broker: {broker}:{port}")

    client = mqtt.Client(client_id="mqtt_test_sender")

    try:
        client.connect(broker, port, 60)
        print(f"发送消息到主题: {topic}")
        print(f"消息内容: {json.dumps(test_message, ensure_ascii=False)}")

        result = client.publish(
            topic,
            json.dumps(test_message, ensure_ascii=False),
            qos=1
        )

        if result.rc == mqtt.MQTT_ERR_SUCCESS:
            print("消息发送成功!")
        else:
            print(f"消息发送失败，返回码: {result.rc}")

        time.sleep(1)
        client.disconnect()

    except Exception as e:
        print(f"发送失败: {e}")


if __name__ == '__main__':
    # 使用示例
    send_test_message()

    # 也可以自定义参数
    # send_test_message(broker='192.168.1.100', port=1883)
