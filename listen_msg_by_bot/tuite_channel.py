from config import get_config
from chat import call_deepseek, send_msg_by_mqtt, send_chat_request_by_trump_news, send_msg_by_webhook_sync, extract_image_urls
import datetime
from helper import get_logger,contains_chinese
import json

# 加载配置
app_config = get_config()
debug = app_config.is_debug()
logger = get_logger(__name__, app_config.get_logging_config())


def process_tuite(client, message):
  tip = f"翻译成中文: {message.content}.\n结果:"
  result = call_deepseek(tip)
  if result == "":
    logger.info(f"调用llm失败,tip:{tip}, result:{result}")
    return
  success = client.publish("/x/post", json.dumps({
    "user_name": 'Moorewire',
    "text": result,
  }))
  logger.info( f"发送结果: {success}")
  return 

def process_tradecatalysts(client, message):
  # 关键词列表
  keywords = ['美', '特朗普', '哈塞特', '鲍威尔', '加密', '比特币', '以太坊', '跌', '涨']

  # 检查消息内容是否包含任一关键词
  if not any(keyword in message.content for keyword in keywords):
    logger.info(f"消息不包含关键词，跳过发送: {message.content[:50]}...")
    return

  logger.info(f"消息包含关键词，准备发送: {message.content[:50]}...")

  success = client.publish("/x/post", json.dumps({
    "user_name": 'Moorewire',
    "text": message.content,
  }))
  logger.info(f"发送结果: {success}")
  return 