#!/usr/bin/env python3
"""
配置文件管理模块

提供配置文件的读取、验证和访问功能
"""

import json
import os
import logging
from typing import Any, Dict, Optional
from pathlib import Path

class Config:
    """配置管理类"""
    
    def __init__(self, config_file: str = "config.json"):
        """
        初始化配置管理器
        
        Args:
            config_file: 配置文件路径
        """
        self.config_file = config_file
        self.config_data = {}
        self._load_config()
    
    def _load_config(self):
        """加载配置文件"""
        try:
            # 获取当前脚本所在目录
            current_dir = Path(__file__).parent
            config_path = current_dir / self.config_file
            
            if not config_path.exists():
                raise FileNotFoundError(f"配置文件不存在: {config_path}")
            
            with open(config_path, 'r', encoding='utf-8') as f:
                self.config_data = json.load(f)
            
            logging.info(f"配置文件加载成功: {config_path}")
            
        except FileNotFoundError as e:
            logging.error(f"配置文件未找到: {e}")
            raise
        except json.JSONDecodeError as e:
            logging.error(f"配置文件JSON格式错误: {e}")
            raise
        except Exception as e:
            logging.error(f"加载配置文件时出错: {e}")
            raise
    
    def get(self, key_path: str, default: Any = None) -> Any:
        """
        获取配置值，支持点分隔的路径
        
        Args:
            key_path: 配置键路径，如 'discord.bot_tokens.test'
            default: 默认值
            
        Returns:
            配置值
        """
        try:
            keys = key_path.split('.')
            value = self.config_data
            
            for key in keys:
                value = value[key]
            
            return value
            
        except (KeyError, TypeError):
            return default
    
    def get_discord_token(self, environment: str = None) -> str:
        """获取Discord bot token"""
        env = environment or self.get('app.environment', 'test')
        return self.get(f'discord.bot_tokens.{env}', '')
    
    def get_webhook_url(self, webhook_type: str, environment: str = None) -> str:
        """获取webhook URL"""
        env = environment or self.get('app.environment', 'test')
        if webhook_type in ['test', 'production']:
            return self.get(f'discord.webhooks.{webhook_type}', '')
        else:
            return self.get(f'discord.webhooks.{webhook_type}', '')
    
    def get_mqtt_topic(self, environment: str = None) -> str:
        """获取MQTT topic"""
        env = environment or self.get('app.environment', 'test')
        return self.get(f'mqtt.topics.{env}', '')
    
    def get_anthropic_api_key(self) -> str:
        """获取Anthropic API key"""
        return self.get('anthropic.api_key', '')
    
    def is_debug(self) -> bool:
        """是否为调试模式"""
        return self.get('app.environment', 'test') == 'test'
    
    def get_environment(self) -> str:
        """获取当前环境"""
        return self.get('app.environment', 'test')
    
    def get_allowed_users(self) -> list:
        """获取允许的用户列表"""
        return self.get('users.allowed_users', [])
    
    def get_proxy_url(self) -> Optional[str]:
        """获取代理URL"""
        if self.get('discord.proxy.enabled', False):
            return self.get('discord.proxy.url')
        return None
    
    def get_mqtt_config(self) -> Dict[str, Any]:
        """获取MQTT配置"""
        return {
            'auto_reconnect': self.get('mqtt.auto_reconnect', True),
            'max_reconnect_attempts': self.get('mqtt.max_reconnect_attempts', 5),
            'reconnect_delay': self.get('mqtt.reconnect_delay', 3)
        }
    
    def get_logging_config(self) -> Dict[str, str]:
        """获取日志配置"""
        return {
            'level': self.get('logging.level', 'INFO'),
            'format': self.get('logging.format', '%(asctime)s - %(levelname)s - %(message)s'),
            'date_format': self.get('logging.date_format', '%Y-%m-%d %H:%M:%S')
        }
    
    def get_channel_name(self, channel_type: str) -> str:
        """获取频道名称"""
        return self.get(f'channels.{channel_type}', '')
    
    def reload(self):
        """重新加载配置文件"""
        logging.info("重新加载配置文件...")
        self._load_config()
    
    def validate_config(self) -> bool:
        """验证配置文件的完整性"""
        required_keys = [
            'discord.bot_tokens',
            'app.environment'
        ]
        
        missing_keys = []
        for key in required_keys:
            if self.get(key) is None:
                missing_keys.append(key)
        
        if missing_keys:
            logging.error(f"配置文件缺少必需的键: {missing_keys}")
            return False
        
        logging.info("配置文件验证通过")
        return True

# 全局配置实例
config = Config()

# 便捷函数
def get_config() -> Config:
    """获取配置实例"""
    return config

def reload_config():
    """重新加载配置"""
    config.reload()
