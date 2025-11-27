# Autolikes 安装指南

## 快速安装

### 1. 安装 Python 依赖包

```bash
cd /Users/zxy/Project/xianyu/blackbox/autolikes
pip install -r requirements.txt
```

### 2. 依赖包列表

- **discord.py**: Discord API 客户端库
- **anthropic**: Claude AI API 客户端
- **paho-mqtt**: MQTT 客户端库
- **requests**: HTTP 请求库
- **aiohttp**: 异步 HTTP 客户端
- **psutil**: 系统进程和资源监控
- **urllib3**: HTTP 客户端库

### 3. 配置文件

需要配置 `config.json` 文件（已通过符号链接从 listen_msg_by_bot 目录）

必须包含：
- Discord bot token
- MQTT 配置
- 代理设置（如需要）

### 4. 运行程序

```bash
python main.py
```

## 功能说明

### 自动 Like 功能

程序会自动对特定频道的消息添加 reaction：
- `tt3` 频道：自动添加 📊

可以在 `main.py` 中修改 `auto_like_channels` 列表来配置自动 like 的频道。

### 手动 Like 命令

在 Discord 中使用命令：

```
!like <消息ID> [表情]
```

示例：
```
!like 1234567890        # 使用默认 👍
!like 1234567890 ❤️     # 使用自定义表情
!like 1234567890 🚀     # 使用火箭表情
```

### 获取消息 ID

1. 在 Discord 设置中启用"开发者模式"
2. 右键点击消息
3. 选择"复制消息 ID"

## 依赖模块

本项目依赖 `listen_msg_by_bot` 目录中的以下模块（通过符号链接）：

- chat.py
- config.py
- dc_history.py
- t3_channel.py
- trump_news_channel.py
- chatting_room_channel.py
- helper.py
- emqx.py
- config.json

## 故障排除

### 导入错误

如果遇到模块导入错误，请确保：
1. 所有依赖包已安装：`pip install -r requirements.txt`
2. 符号链接正确创建
3. config.json 文件存在且配置正确

### 重新创建符号链接

如果符号链接损坏，可以重新创建：

```bash
cd /Users/zxy/Project/xianyu/blackbox/autolikes
ln -sf ../listen_msg_by_bot/chat.py .
ln -sf ../listen_msg_by_bot/config.py .
ln -sf ../listen_msg_by_bot/dc_history.py .
ln -sf ../listen_msg_by_bot/t3_channel.py .
ln -sf ../listen_msg_by_bot/trump_news_channel.py .
ln -sf ../listen_msg_by_bot/chatting_room_channel.py .
ln -sf ../listen_msg_by_bot/helper.py .
ln -sf ../listen_msg_by_bot/emqx.py .
ln -sf ../listen_msg_by_bot/config.json .
```

## 验证安装

运行以下命令验证所有依赖是否正确安装：

```bash
python -c "import discord; import discord.ext; from chat import send_chat_request; from config import get_config; from emqx import MQTTConfig; print('✅ 所有导入成功！')"
```

如果看到 "✅ 所有导入成功！"，说明安装完成！




