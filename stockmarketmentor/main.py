import requests
import time
import json
import logging
import re

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s -  %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
log = logging.getLogger(__name__)

debug = False

proxy_url = "http://D0BFA2CA:809AD5BFCDCB@tunpool-yu7bw.qg.net:11639"

def get_posts(ts):
  url = f"https://stockmarketmentor.com/forum/api/services/PostsDAO.php?site=smm&params=[%22posts%22,%22all%22,null,%22conversation%22,{ts}]"

  payload={}
  headers = {
    'User-Agent': 'Apifox/1.0.0 (https://apifox.com)',
    'Accept': '*/*',
    'Host': 'stockmarketmentor.com',
    'Connection': 'keep-alive',
    'Cookie': 'PHPSESSID=t2ohrs60r7ifte17cp9lis838g'
  }

  response = requests.request("GET", url, headers=headers, data=payload, proxies={"http": proxy_url, "https": proxy_url})
  if response.status_code == 200:
    return response.json()
  else:
    log.info(f"❌ 请求失败: {response.status_code} {response.text}")    
    return None

def on_connect(client, userdata, flags, rc):
  log.info("MQTT连接成功回调被调用")

# 全局变量
last_ts = int(time.time())  # 当前时间戳作为初始值
if debug:
  last_ts = 1752623143
# 白名单用户
whitelist_users = ['DavidK', 'woodman', 'champ', 'joelsg1']

# 主题映射配置
topic_map = {
    "joelsg1": {
        "topic": "lis-msg/rickmarch",
        "channel": "chatting-room"
    },
    "champ": {
        "topic": "lis-msg/dp",
        "channel": "chatting-room"
    },
    "DavidK": {
        "topic": "lis-msg/kiraturner",
        "channel": "chatting-room"
    },
    "woodman": {
        "topic": "lis-msg/jasonwood",
        "channel": "chatting-room"
    }
}

def process_posts(client, posts):
    """处理posts数据"""
    global last_ts
    
    if not posts or len(posts) == 0:
        log.info("没有新的posts数据")
        return
    
    # 更新last_ts为返回记录中最大的update_unix
    update_unixes = []
    for post in posts:
        try:
            update_unix = int(post.get('update_unix', 0))
            update_unixes.append(update_unix)
        except (ValueError, TypeError):
            continue
    
    if update_unixes:
        max_update_unix = max(update_unixes)
        if max_update_unix > last_ts:
            last_ts = max_update_unix
            log.info(f"更新last_ts为: {last_ts}")
    
    # 处理每个post
    processed_count = 0
    for post in posts:
        author = post.get('author', '')
        
        # 判断author是否在白名单中
        if not debug:
          if author not in whitelist_users:
              log.info(f"跳过非白名单用户: {author}")
              continue
        
        log.info(f"处理白名单用户 {author} 的消息")
        
        # 发送MQTT消息
        send_post_to_mqtt(client, post)
        processed_count += 1
    
    log.info(f"本次处理了 {processed_count} 条白名单用户消息")

def send_post_to_mqtt(client, post):
    """发送post到MQTT"""
    author = post.get('author', '').strip()
    if debug:
      mapping = {
        "topic": "lis-msg/qiyu",
        "channel": "rogertest"
      }
    else:
      mapping = topic_map.get(author)
        
    
    if not mapping:
        log.info(f"❌ 未找到用户 {author} 的主题映射配置")
        return
    
    content = post.get('message', '').strip()
    if content == "":
      log.info(f"❌ 用户 {author} 的消息为空")
      return
    # 替换特殊字符
    content = content.replace('~', '').replace('#', '')
    
    # 去除所有@用户名（如@abc @joelsg1等）
    content = re.sub(r'@\w+\s*', '', content).strip()

    # 构造消息数据
    message_data = {
        "channel": mapping["channel"],
        "content": content,
    }
    
    log.info(f"发送消息到主题 {mapping['topic']}:")
    log.info(f"  作者: {author}")
    log.info(f"  内容: {post.get('message', '')[:100]}...")  # 只显示前100个字符
    
    try:
        # 发送MQTT消息
        success = client.publish(mapping["topic"], json.dumps(message_data))
        if success:
            log.info(f"✅ 已发送 {author} 的消息到 {mapping['topic']}")
        else:
            log.info(f"❌ 发送 {author} 的消息失败")
    except Exception as e:
        log.info(f"❌ 发送MQTT消息时出错: {e}")

def listen(client):
    """Posts监听主循环"""
    global last_ts
    
    log.info(f"🚀 开始监听Posts... (last_ts: {last_ts})")
    
    while True:
        try:
            log.info(f"\n--- 请求Posts数据 (last_ts: {last_ts}) ---")
            
            # 请求get_posts API
            posts = get_posts(last_ts)
            
            if posts is None:
                log.info("❌ API请求失败")
            elif isinstance(posts, list):
                log.info(f"📨 获取到 {len(posts)} 条posts数据")
                
                # 处理posts数据
                if len(posts) > 0:
                    process_posts(client, posts)
                else:
                    log.info("没有新的posts数据")
            else:
                log.info(f"⚠️ API返回了意外的数据格式: {type(posts)}")
            
            # 休息5秒
            log.info("💤 等待10秒后继续监听...")
            time.sleep(5)
            
        except KeyboardInterrupt:
            log.info("\n⏹️ 用户中断监听")
            break
        except Exception as e:
            log.info(f"❌ 监听循环出错: {e}")
            log.info("等待5秒后重试...")
            time.sleep(5)


if __name__ == "__main__":

    from emqx import MQTTConfig, MQTTClient
    
    log.info("🚀 启动Posts监听服务...")
    log.info(f"白名单用户: {', '.join(whitelist_users)}")
    log.info(f"初始时间戳: {last_ts}")
    
    # 创建MQTT配置
    config = MQTTConfig(
        auto_reconnect=True,
        max_reconnect_attempts=5,
        reconnect_delay=3
    )
    
    # 创建MQTT客户端
    client = MQTTClient(config)
    client.set_connection_callback(on_connect)
    
    try:
        # 连接MQTT服务器
        log.info("🔗 连接MQTT服务器...")
        connect_result = client.connect()
        log.info(f"连接结果: {connect_result}")
        
        if connect_result:
            log.info("✅ MQTT连接成功，开始监听Posts...")
            # 开始监听
            listen(client)
        else:
            log.info("❌ MQTT连接失败")
            
    except KeyboardInterrupt:
        log.info("\n⏹️ 用户中断")
    except Exception as e:
        log.info(f"❌ 运行错误: {e}")
        import traceback
        traceback.print_exc()
    finally:
        log.info("🔌 断开MQTT连接...")
        client.disconnect()
        log.info("👋 程序退出")