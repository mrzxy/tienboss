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
  
    def get_anthropic_api_key(self) -> str:
        """获取Anthropic API key"""
        return self.get('anthropic.api_key', '')
    
    def is_debug(self) -> bool:
        """是否为调试模式"""
        return self.get('app.environment', 'test') == 'test'
    

    def reload(self):
        """重新加载配置文件"""
        logging.info("重新加载配置文件...")
        self._load_config()
    
    def validate_config(self) -> bool:
        """验证配置文件的完整性"""
        required_keys = [
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
