from config import get_config
from chat import send_chat_request, send_msg_by_webhook, send_chat_request_by_trump_news, send_msg_by_webhook_sync, extract_image_urls
from dc_history import insert_message_if_not_exists, update_last_message_id, generate_content_md5,search_message_by_content_md5
import datetime
from helper import get_logger,contains_chinese

# 加载配置
app_config = get_config()
debug = app_config.is_debug()
logger = get_logger(__name__, app_config.get_logging_config())

send_history = []

def in_send_history(id):
    for item in send_history:
        if item == id:
            return True
    return False
    
def add_send_history(id):
    send_history.append(id)
    if len(send_history) > 100:
        send_history[:] = send_history[-50:]

webhook_map = {
    'New York Post': 'https://discord.com/api/webhooks/1421682710945988641/M9HOYu-fvZ-RrwywoXYRJ5i_jiq4yEHhNL3JoFvHFpLd97JSDnOjolrEZPJyIcp4BZ9N',
    'First Squawk': 'https://discord.com/api/webhooks/1421683151016824882/DeGCCI7NHVd2qbPFqm6Grz2q9rZH8-5MFwi4DbdBTm4bCVXB48EyRW1WFUtmD8EAoJKr',
    'Reuters': 'https://discord.com/api/webhooks/1421683254271934505/Um3jzKrn0HNKCPGBefV-oBikFmG8onfL2VIrTmDbmSxULMik2vzbkrfA10uFylxWFkI9',
    '*Walter Bloomberg': 'https://discord.com/api/webhooks/1421683391723470951/B6FK1xUM4bl4nl43CgGEKLcQSQ6sRJAz_AunjGGahj9r6CXMhraMgk_XH27AShaoqdES',
    'Wall St Engine': 'https://discord.com/api/webhooks/1421683654198825052/G7N3n-qa0aYNtajGFE58EdK08_CcQeQ3i6SkthC8EkcLhVT4Ic--MW2zDjdOPkJo5OSf',
    'qiyuhook': 'https://discord.com/api/webhooks/1421750366483251232/9g_IvTelfhqj8uP-IAxIAEcQt94ivQCM3AeTqhXESiXDGpAbfbwNZW8l23FJXPvtVolo'
}

def process_trump_news(message):
    msg = {}

    if in_send_history(message.id):
        logger.info(f"{message.id} 是我们自己发的")
        return None

    if contains_chinese(message.content):
        logger.info(f"{message.content} 包含中文, 所以不发")
        return None

    images = extract_image_urls(message.content)

    logger.info(f"author: {message.author.name}")

    if message.author.name not in webhook_map:
        logger.info(f"不需要转发到webhook: {message.author.name}")
        return None


    send_content = None
    if len(message.content) > 0:
        send_content = send_chat_request_by_trump_news(message.content)

    if send_content is None and len(images) < 1:
        logger.info(f"内容为空以及没有图片: {message.content}")
        return None
        
    if len(images) > 0:
        send_content = "" if send_content is None else send_content
        for image in images:
            send_content = send_content + f"[.]({image})"
        
    webhook_url = webhook_map[message.author.name]

    result = send_msg_by_webhook_sync(send_content, webhook_url)
    if result is None:
        logger.error(f"发送消息失败: {send_content}")
        return

    add_send_history(int(result['id']))
    
    # 优化历史记录：当超过200条时，只保留最后100条
  

    # print(result)
    # print(result['id'])



