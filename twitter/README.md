# Twitter 自动发帖机器人

MQTT 监听自动发推

## 使用

### 1. 配置账号

编辑 `accounts.py`:

```python
TWITTER_ACCOUNTS = [
    TwitterAccount(
        username="your_username",
        password="your_password",
        enabled=True
    ),
]
```

### 2. 启动

```bash
python twitter_bot.py
```

### 3. 发送 MQTT 消息到 `/x/post`

```json
{
    "username": "your_username",
    "text": "推文内容"
}
```

## 消息格式

```json
{
    "username": "account1",
    "text": "推文内容",
    "media_ids": ["media_id"],
    "reply_to_tweet_id": "123456",
    "is_note_tweet": false,
    "proxy": "http://proxy:port"
}
```
