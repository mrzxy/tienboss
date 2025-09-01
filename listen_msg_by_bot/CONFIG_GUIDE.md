# 配置文件使用指南

## 概述

本项目现在使用配置文件来管理所有的设置，包括Discord tokens、webhook URLs、MQTT配置等。这样做的好处是：

- ✅ 集中管理所有配置
- ✅ 环境分离（测试/生产）
- ✅ 敏感信息保护
- ✅ 易于维护和修改

## 文件结构

```
listen_msg_by_bot/
├── config.json          # 主配置文件
├── config.py            # 配置读取模块
├── main.py              # 主程序（已更新使用配置）
├── chat.py              # 聊天模块（已更新使用配置）
└── CONFIG_GUIDE.md      # 本文档
```

## 配置文件详解

### config.json 结构

```json
{
    "discord": {
        "bot_tokens": {
            "test": "测试环境的bot token",
            "production": "生产环境的bot token"
        },
        "webhooks": {
            "test": "测试环境webhook URL",
            "production": "生产环境webhook URL",
            "trade_alerts": "交易提醒webhook URL"
        },
        "proxy": {
            "enabled": false,
            "url": "http://127.0.0.1:53366"
        }
    },
    "anthropic": {
        "api_key": "您的Anthropic API密钥"
    },
    "mqtt": {
        "auto_reconnect": true,
        "max_reconnect_attempts": 5,
        "reconnect_delay": 3,
        "topics": {
            "test": "测试环境MQTT主题",
            "production": "生产环境MQTT主题"
        },
        "channels": {
            "heisenberg": "craig-comments",
            "real_time_news": "real-time-news"
        }
    },
    "channels": {
        "real_time_news": "real-time-news",
        "alerts_windows": "alerts-windows", 
        "heisenberg": "heisenberg",
        "trade_alerts": "trade-alerts"
    },
    "users": {
        "allowed_users": ["dk_149", "qiyu_31338"]
    },
    "app": {
        "debug": true,
        "environment": "test"
    },
    "logging": {
        "level": "INFO",
        "format": "%(asctime)s - %(levelname)s - %(message)s",
        "date_format": "%Y-%m-%d %H:%M:%S"
    }
}
```

## 配置项说明

### Discord配置
- `bot_tokens`: 不同环境的Discord bot tokens
- `webhooks`: 不同用途的webhook URLs
- `proxy`: 代理设置（可选）

### Anthropic配置
- `api_key`: Anthropic Claude API密钥

### MQTT配置
- `auto_reconnect`: 是否自动重连
- `max_reconnect_attempts`: 最大重连次数
- `reconnect_delay`: 重连延迟（秒）
- `topics`: 不同环境的MQTT主题
- `channels`: MQTT频道映射

### 应用配置
- `debug`: 是否为调试模式
- `environment`: 当前环境（test/production）

### 日志配置
- `level`: 日志级别
- `format`: 日志格式
- `date_format`: 时间格式

## 使用方法

### 1. 基本配置读取

```python
from config import get_config

# 获取配置实例
config = get_config()

# 读取配置值
discord_token = config.get_discord_token()
webhook_url = config.get_webhook_url('test')
api_key = config.get_anthropic_api_key()
```

### 2. 便捷方法

```python
# 检查是否为调试模式
if config.is_debug():
    print("运行在调试模式")

# 获取当前环境
env = config.get_environment()  # 'test' 或 'production'

# 获取允许的用户列表
users = config.get_allowed_users()

# 获取MQTT配置
mqtt_config = config.get_mqtt_config()
```

### 3. 点分隔路径访问

```python
# 使用点分隔路径访问嵌套配置
value = config.get('discord.webhooks.test')
level = config.get('logging.level', 'INFO')  # 带默认值
```

## 环境切换

通过修改 `app.environment` 来切换环境：

```json
{
    "app": {
        "environment": "production"  # 或 "test"
    }
}
```

这会自动切换：
- Discord bot token
- MQTT topic
- Webhook URLs（根据调试模式）

## 安全注意事项

1. **不要提交敏感信息到Git**
   - 将真实的tokens和API keys替换为占位符
   - 考虑使用 `.gitignore` 忽略配置文件

2. **环境变量覆盖**
   ```python
   # 可以通过环境变量覆盖配置
   import os
   api_key = os.getenv('ANTHROPIC_API_KEY') or config.get_anthropic_api_key()
   ```

3. **配置文件权限**
   ```bash
   # 限制配置文件访问权限
   chmod 600 config.json
   ```

## 配置验证

程序启动时会自动验证配置：

```python
if not app_config.validate_config():
    raise RuntimeError("配置文件验证失败，请检查配置文件")
```

必需的配置项：
- `discord.bot_tokens`
- `discord.webhooks` 
- `app.environment`

## 故障排除

### 常见错误

1. **配置文件不存在**
   ```
   FileNotFoundError: 配置文件不存在: /path/to/config.json
   ```
   解决：确保 `config.json` 文件存在于正确位置

2. **JSON格式错误**
   ```
   json.JSONDecodeError: 配置文件JSON格式错误
   ```
   解决：检查JSON语法，使用在线JSON验证器

3. **API key未配置**
   ```
   ValueError: Anthropic API key未配置
   ```
   解决：在 `config.json` 中设置正确的API key

4. **Discord token未配置**
   ```
   ValueError: Discord bot token未配置或为空
   ```
   解决：确保对应环境的bot token已配置

### 调试技巧

1. **启用调试日志**
   ```json
   {
       "logging": {
           "level": "DEBUG"
       }
   }
   ```

2. **配置重新加载**
   ```python
   from config import reload_config
   reload_config()  # 重新加载配置而不重启程序
   ```

3. **配置值检查**
   ```python
   config = get_config()
   print(f"当前环境: {config.get_environment()}")
   print(f"调试模式: {config.is_debug()}")
   print(f"Discord token存在: {bool(config.get_discord_token())}")
   ```

## 配置模板

创建新环境时，复制以下模板：

```json
{
    "discord": {
        "bot_tokens": {
            "test": "YOUR_TEST_BOT_TOKEN",
            "production": "YOUR_PRODUCTION_BOT_TOKEN"
        },
        "webhooks": {
            "test": "YOUR_TEST_WEBHOOK_URL",
            "production": "YOUR_PRODUCTION_WEBHOOK_URL"
        }
    },
    "anthropic": {
        "api_key": "YOUR_ANTHROPIC_API_KEY"
    },
    "app": {
        "debug": true,
        "environment": "test"
    }
}
```

将占位符替换为实际值即可使用。
