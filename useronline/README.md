# Discord 用户在线管理器

维护多个 Discord 账号在线，支持代理和自动重连功能。

## 功能特性

- **多账号管理**: 同时维护多个 Discord 账号在线
- **代理支持**: 可配置一半账号使用代理（通过 webshare.io）
- **自动重连**: 账号掉线时自动重连，支持指数退避策略
- **灵活配置**: 通过 JSON 配置文件管理所有设置

## 配置说明

### config.json

```json
{
    "tokens": {
        "test": ["TOKEN1", "TOKEN2", "TOKEN3"],
        "production": []
    },
    "app": {
        "environment": "test"
    },
    "proxy": {
        "webshare_api_key": "YOUR_WEBSHARE_API_KEY",
        "enabled": true,
        "use_proxy_ratio": 0.5
    },
    "reconnect": {
        "max_attempts": 5,
        "retry_delay": 5,
        "backoff_multiplier": 1.5
    },
    "logging": {
        "level": "INFO",
        "format": "%(asctime)s - %(levelname)s - %(message)s",
        "date_format": "%Y-%m-%d %H:%M:%S"
    }
}
```

### 配置项说明

#### tokens
- `test`: 测试环境的 Discord token 列表
- `production`: 生产环境的 Discord token 列表

#### app
- `environment`: 当前环境 (`test` 或 `production`)

#### proxy
- `webshare_api_key`: Webshare.io 的 API Key
- `enabled`: 是否启用代理功能
- `use_proxy_ratio`: 使用代理的账号比例（0.5 表示一半账号使用代理）

#### reconnect
- `max_attempts`: 最大重连次数
- `retry_delay`: 初始重试延迟（秒）
- `backoff_multiplier`: 退避乘数（每次重试延迟增加的倍数）

#### logging
- `level`: 日志级别 (`DEBUG`, `INFO`, `WARNING`, `ERROR`)
- `format`: 日志格式
- `date_format`: 日期格式

## 使用方法

### 1. 安装依赖

```bash
pip install discord.py requests
```

### 2. 配置 token 和代理

编辑 `config.json`，添加你的 Discord token 和 Webshare API Key：

```json
{
    "tokens": {
        "test": [
            "YOUR_DISCORD_TOKEN_1",
            "YOUR_DISCORD_TOKEN_2",
            "YOUR_DISCORD_TOKEN_3"
        ]
    },
    "proxy": {
        "webshare_api_key": "YOUR_WEBSHARE_API_KEY",
        "enabled": true,
        "use_proxy_ratio": 0.5
    }
}
```

### 3. 运行程序

```bash
python main.py
```

## 工作原理

### 代理分配策略
- 根据 `use_proxy_ratio` 配置，前 N% 的账号使用代理
- 例如：3 个账号，`use_proxy_ratio: 0.5`，则前 1 个账号使用代理

### 自动重连机制
1. 账号连接失败时自动重试
2. 采用指数退避策略，每次重试延迟增加
3. 达到最大重试次数后停止该账号的重连
4. Token 无效的账号不会重试

### 代理管理
- 使用 [webshare.io](https://www.webshare.io/) 提供的代理服务
- 自动从 API 获取代理列表
- 为每个账号分配固定的代理（基于用户名哈希）
- 代理失败时自动切换

## 日志说明

程序会输出详细的运行日志：

```
2024-01-28 10:00:00 - INFO - ============================================================
2024-01-28 10:00:00 - INFO - 初始化账号在线管理器: 总账号数 3, 使用代理 1 个
2024-01-28 10:00:00 - INFO - ============================================================
2024-01-28 10:00:01 - INFO - [账号 0] 使用代理: proxy.webshare.io:5000
2024-01-28 10:00:02 - INFO - [账号 0] 正在启动...
2024-01-28 10:00:05 - INFO - [账号 0] ✓ 已登录: Username1 (ID: 123456789)
2024-01-28 10:00:05 - INFO - [账号 1] 不使用代理
2024-01-28 10:00:06 - INFO - [账号 1] 正在启动...
```

## 注意事项

⚠️ **重要提醒**

1. **Token 安全**: 请妥善保管你的 Discord token，不要泄露给任何人
2. **使用风险**: 使用自动化工具可能违反 Discord 服务条款
3. **代理配置**: 如果不需要代理，将 `proxy.enabled` 设置为 `false`
4. **账号限制**: 不建议同时运行过多账号，可能被 Discord 检测

## 故障排除

### Token 无效
- 确认 token 格式正确
- 检查 token 是否已过期
- 确认 token 类型（用户 token vs Bot token）

### 代理连接失败
- 检查 Webshare API Key 是否正确
- 确认代理服务是否正常
- 查看日志中的代理失败信息

### 频繁掉线
- 增加 `reconnect.max_attempts`
- 调整 `reconnect.retry_delay` 和 `backoff_multiplier`
- 检查网络连接稳定性

## 许可证

本项目仅供学习和研究使用。
