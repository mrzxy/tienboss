# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run the service
python main.py

# Run tests
python -m pytest tests/

# Run a single test file
python tests/test_find_avatar.py

# Diagnose MQTT connectivity
python mqtt_diagnose.py

# Test basic MQTT publish/subscribe
python mqtt_test.py
```

## Configuration

Copy `config.example.yaml` to `config.yaml` and fill in credentials. Key sections:

- `user_accounts`: Discord user tokens used for **sending** messages (keyed by sender ID like `dp`, `neil`, etc.)
- `user_listeners`: maps account IDs to lists of `"server_id/channel_id"` strings to **listen** on
- `mqtt`: EMQX broker connection with TLS — `emqxsl-ca.crt` is the CA cert at project root
- `anthropic`: Claude API key and model settings for translation
- `tencent`: Tencent Cloud OCR credentials

## Architecture

The service bridges Discord channels to an MQTT broker using a **listen → process → publish** pipeline.

### Startup flow (`main.py` → `Application`)

1. `DiscordSenderManager` — logs in multiple Discord user accounts that will **send** messages downstream; stores `discord_msg_id → sent_msg_id` mappings in `listeners/messages.db` (SQLite)
2. `MQTTListener` — subscribes to the MQTT topic (`lis-msg-v2`); when a message arrives it calls `sender_manager.send_message(sender, server_id, channel_id, content, attachments)` via `asyncio.run_coroutine_threadsafe` (paho-mqtt runs in a background thread)
3. `BotListener` (optional) — official bot token listener, logs messages only
4. `UserListener` (optional) — selfbot listener using `discord.py-self`; the main business logic lives here

### UserListener channel routing (`listeners/user_listener.py`)

`process_message` dispatches to a per-channel handler by hard-coded channel ID:

| Handler | Channel IDs | Behaviour |
|---|---|---|
| `procCommentary` | 1286023151532114002, 1286022517869514874 | Filter "live voice" lines, forward to MQTT |
| `procShunge` | 1072731733402865714 | CN→EN translation via Claude, EN→CN, publish EN to MQTT + CN via Discord webhook; applies keyword blocklist |
| `procDiamondHandsAndComments` | 1335234038365163531, 1387251242341761136 | Forward to MQTT with sender `sam` |
| `procproFessorrChannel` | 1029055168425246761 + others | Attachment filtering (avatar match + OCR), optional EN→CN translation, publish to MQTT; some channels also post to `/x/post` topic |

### Attachment filtering (`proc_attachments`)

Before forwarding images from `procproFessorrChannel`, each attachment is checked:
1. OpenCV template matching against `static/thumb.png` (the sender's avatar) — skip if matched
2. Tencent Cloud OCR (`OcrClient.contains_prof`) — skip if the word "Prof" appears in the image text

### MQTT message format

Published JSON payload on topic `lis-msg-v2`:
```json
{
  "sender": "<account key from user_accounts>",
  "target_id": "<server_id>/<channel_id>",
  "content": "...",
  "attachments": ["url1", ...],
  "discord_msg_id": "...",   // optional, enables reply threading
  "ref_msg_id": "..."        // optional, reply to this msg in target channel
}
```

`MQTTListener` receives this payload and routes it to the correct `DiscordSenderManager` client.

### Message reply threading

`UserListener._init_db` / `DiscordSenderManager.save_message` share `listeners/messages.db`. When a source message references an earlier message, `_get_msg_id` looks up the original `discord_msg_id` to find the forwarded `msg_id` in the target channel, enabling proper Discord reply chains.

### Concurrency model

All Discord clients (`discord.py-self`) are async and run inside a single `asyncio` event loop via `asyncio.gather`. The paho-mqtt client runs in its own thread (`loop_start`) and bridges back to the async loop with `run_coroutine_threadsafe`.
