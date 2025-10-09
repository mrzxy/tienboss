from shlex import join
from config import get_config
from chat import send_chat_request, send_msg_by_webhook, send_chat_request_by_chatting_room, send_msg_by_webhook_sync, extract_image_urls
from dc_history import insert_message_if_not_exists, update_last_message_id, generate_content_md5,search_message_by_content_md5
import datetime
from helper import get_logger,contains_chinese

# 加载配置
app_config = get_config()
debug = app_config.is_debug()
logger = get_logger(__name__, app_config.get_logging_config())

send_history = []

def extract_stock_symbols(content):
    """
    提取开头的股票代码和剩余内容
    
    Args:
        content: 输入的文本内容
        
    Returns:
        tuple: (股票代码列表, 剩余内容)
        
    Examples:
        "$TSL $SMCI $CJJJ Next stop July Ath $8.37 long" 
        -> (["$TSL", "$SMCI", "$CJJJ"], "Next stop July Ath $8.37 long")
        
        "$SMCI Strong Sept" 
        -> (["$SMCI"], "Strong Sept")
    """
    if not content or not content.strip():
        return [], ""
    
    content = content.strip()
    words = content.split()
    
    stock_symbols = []
    remaining_start_index = 0
    
    # 从开头开始提取所有以 $ 开头的单词
    for i, word in enumerate(words):
        if word.startswith('$'):
            stock_symbols.append(word)
            remaining_start_index = i + 1
        else:
            # 遇到第一个不是 $ 开头的单词就停止
            break
    
    # 获取剩余内容
    remaining_content = ' '.join(words[remaining_start_index:])
    
    return stock_symbols, remaining_content

def in_send_history(id):
    print(f"send_history: {send_history}")
    for item in send_history:
        if item == id:
            return True
    return False
    
def add_send_history(id):
    send_history.append(id)
    print(f"send_history: {send_history}")
    if len(send_history) > 100:
        send_history[:] = send_history[-50:]
        logger.info(f"历史记录已优化，当前保留 {len(send_history)} 条记录")

webhook_map = {
    'dk_149': 'https://discord.com/api/webhooks/1424774662511919258/qV4UZKnfM64JNOEG1JxS_Dz4VM2CBsndmM6GjYlePo003fSD2p9xgV948_95RMqONdxV',
    'ricktrader_will': 'https://discord.com/api/webhooks/1424776333031899278/deiNsOAS2V_Vl8ycwlnQgtyz8Mc1QQ_8s4KfFugJvF1LwoHN_I6yhuORORSbMefspTJH',
    'winnerjason_': 'https://discord.com/api/webhooks/1424776457611382884/ncMU1XmjbFPdrzVktPpG-mE7TR1OzbBZKXH_Xma1d0GFJ2VEKD97n8AOsYv6uHyz2J2C',
    'kira_169': 'https://discord.com/api/webhooks/1424776632509399063/NUkzt3ZpD8gogPC_2-TGDXOJcyAdqK0u9AeL-2tevBaemo9Eu3zc4IDJfw8qhrJWdx5Z',
    'qiyu_31338': 'https://discord.com/api/webhooks/1425314330366312499/VeE4mausk48b_eJzpX_m5SjyHmoSPz6FUx6sBpsggAhWMCcVlryiPYeoRKwyOhZb14sm'
}

def process_chatting_room_news(message):
    msg = {}

    if in_send_history(message.id):
        logger.info(f"{message.id} 是我们自己发的")
        return None

    symbos, content = extract_stock_symbols(message.content)

    if contains_chinese(content):
        logger.info(f"{message.content} 包含中文, 所以不发")
        return None

    images = extract_image_urls(message.content)

    logger.info(f"author: {message.author.name}")

    if message.author.name not in webhook_map:
        logger.info(f"不需要转发到webhook: {message.author.name}")
        return None

    send_content = None
    if len(content) > 0:
        send_content = send_chat_request_by_chatting_room(content)

    if send_content is None and len(images) < 1:
        logger.info(f"内容为空以及没有图片: {message.content}")
        return None

    send_content = " ".join(symbos) + " " + send_content
        
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




