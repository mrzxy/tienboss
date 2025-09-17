from config import get_config
from chat import send_chat_request, send_msg_by_webhook, send_chat_request_by_Heisen, send_msg_by_mqtt, extract_image_urls
from dc_history import insert_message_if_not_exists, update_last_message_id, generate_content_md5,search_message_by_content_md5
import datetime

# 加载配置
app_config = get_config()
debug = app_config.is_debug()

def process_t3(message):
    msg = {}
    if not debug:
        if 'TT3' not in message.author.name:
            return

    print("process_t3")

    msg['topic'] = 'lis-msg/craig'
    msg['channel'] = 'craig-diamond-hands'
    msg['mqtt'] = True
    msg['other'] = {}
    if debug:
        msg['topic'] = 'lis-msg/qiyu'

    images = extract_image_urls(message.content)
    send_content = ""
    if 'Quoted' in message.content:
        if len(message.embeds) >= 2:
            content_md5 = generate_content_md5(message.embeds[1].description)
            quoted_message = search_message_by_content_md5(content_md5)
            reply_msg_id = ""
            if quoted_message is not None:
                reply_msg_id= quoted_message.get('dc_msg_id')
            
            msg['other']['reply_msg_id'] = reply_msg_id
            send_content = message.embeds[0].description
    elif len(message.embeds) == 1:
        send_content =  message.embeds[0].description
    else:
        send_content = message.content

    if len(images) > 0:
        for image in images:
            send_content = send_content + f"[.]({image})"

    msg['content'] = send_content

    return msg
def update_tt3_db(message):
    """
    更新TT3数据库，插入消息并更新last_message_id
    使用 dc_history.py 中的统一数据库功能
    
    Args:
        message: Discord消息对象
    
    Returns:
        bool: 如果插入了新消息返回True，否则返回False
    """
    try:
        # 处理消息内容
        content = message.content
        
        # 生成MD5哈希
        content_md5 = generate_content_md5(content)
        
        # 创建消息数据（使用dc_history的统一格式）
        message_data = {
            "dc_msg_id": str(message.id),
            "content": content,
            "content_md5": content_md5,
            "created_at": message.created_at.isoformat()
        }
        
        # 使用dc_history的函数插入消息
        is_new_message = insert_message_if_not_exists(message_data)
        
        if is_new_message:
            # 使用dc_history的函数更新最后的消息ID
            update_last_message_id(message.channel.id, message.id)
            print(f"TT3数据库已更新：插入消息 {message.id}")
            return True
        else:
            print(f"TT3消息 {message.id} 已存在，跳过插入")
            return False
            
    except Exception as e:
        print(f"更新TT3数据库时出错: {e}")
        return False
