#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
配置管理模块 - 支持YAML和JSON格式
"""

import json
import logging
from pathlib import Path

try:
    import yaml
except ImportError:
    raise ImportError("请安装 pyyaml: pip install pyyaml")


class Config:
    """配置管理类 - 支持YAML和JSON格式"""

    def __init__(self, config_file='config.yaml'):
        self.config_file = Path(config_file)
        self.config = self.load_config()
        self.logger = logging.getLogger('Config')

    def load_config(self):
        """加载配置文件（自动识别YAML或JSON格式）"""
        if not self.config_file.exists():
            raise FileNotFoundError(f"配置文件不存在: {self.config_file}")

        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                # 根据文件扩展名判断格式
                if self.config_file.suffix.lower() in ['.yaml', '.yml']:
                    return yaml.safe_load(f)
                elif self.config_file.suffix.lower() == '.json':
                    return json.load(f)
                else:
                    # 尝试YAML，失败则尝试JSON
                    content = f.read()
                    try:
                        return yaml.safe_load(content)
                    except yaml.YAMLError:
                        return json.loads(content)

        except yaml.YAMLError as e:
            raise ValueError(f"配置文件YAML格式错误: {e}")
        except json.JSONDecodeError as e:
            raise ValueError(f"配置文件JSON格式错误: {e}")
        except Exception as e:
            raise ValueError(f"加载配置文件失败: {e}")

    def reload(self):
        """重新加载配置"""
        self.logger.info("重新加载配置文件")
        self.config = self.load_config()

    def get(self, key, default=None):
        """获取配置项"""
        return self.config.get(key, default)

    def get_nested(self, *keys, default=None):
        """获取嵌套配置项
        例如: config.get_nested('mqtt', 'broker')
        """
        value = self.config
        for key in keys:
            if isinstance(value, dict):
                value = value.get(key)
            else:
                return default
            if value is None:
                return default
        return value

    def get_mqtt_config(self):
        """获取MQTT配置"""
        return self.get('mqtt', {})

    def get_user_accounts(self):
        """获取用户账号配置"""
        return self.get('user_accounts', {})

    def get_bot_config(self):
        """获取Bot配置"""
        return {
            'token': self.get('bot_token'),
            'channels': self.get('bot_channels', [])
        }

    def get_user_listen_config(self):
        """获取User监听配置

        Returns:
            dict: {account_id: [target_list]}
            例如: {'paul': ['server_id/channel_id', ...]}
        """
        return self.get('user_listeners', {})

    def get_log_config(self):
        """获取日志配置"""
        return {
            'level': self.get('log_level', 'INFO'),
            'file': self.get('log_file', 'discord_listener.log')
        }

    def get_anthropic_config(self):
        """获取Anthropic API配置"""
        return self.get('anthropic', {})
