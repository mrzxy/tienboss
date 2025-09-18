import requests
import time
import json
import logging
import re
import psutil
import os
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s -  %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
log = logging.getLogger(__name__)

debug = False

proxy_url = "http://D0BFA2CA:809AD5BFCDCB@tunpool-yu7bw.qg.net:11639"

# 创建一个持久的session对象，复用连接
session = requests.Session()

# 配置重试策略
retry_strategy = Retry(
    total=3,
    backoff_factor=1,
    status_forcelist=[429, 500, 502, 503, 504],
)
adapter = HTTPAdapter(max_retries=retry_strategy, pool_connections=1, pool_maxsize=1)
session.mount("http://", adapter)
session.mount("https://", adapter)

# 设置代理
session.proxies = {"http": proxy_url, "https": proxy_url}

# 内存统计相关变量
memory_stats_interval = 60  # 每60秒记录一次内存统计
last_memory_stats_time = 0

def log_memory_stats():
    """记录内存使用统计信息"""
    global last_memory_stats_time
    
    current_time = time.time()
    
    # 检查是否到了记录时间
    if current_time - last_memory_stats_time < memory_stats_interval:
        return
    
    try:
        process = psutil.Process(os.getpid())
        memory_info = process.memory_info()
        
        # 获取详细的内存信息
        rss_mb = memory_info.rss / 1024 / 1024  # 物理内存
        vms_mb = memory_info.vms / 1024 / 1024  # 虚拟内存
        
        # 获取系统内存信息
        system_memory = psutil.virtual_memory()
        system_available_mb = system_memory.available / 1024 / 1024
        system_usage_percent = system_memory.percent
        
        log.info(f"📊 内存统计 - 进程: RSS={rss_mb:.1f}MB, VMS={vms_mb:.1f}MB | 系统: 可用={system_available_mb:.0f}MB, 使用率={system_usage_percent:.1f}%")
        
        last_memory_stats_time = current_time
        
    except Exception as e:
        log.info(f"获取内存统计失败: {e}")

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

  try:
    # 使用session发送请求，设置超时时间
    response = session.get(url, headers=headers, timeout=(10, 30))  # 连接超时10秒，读取超时30秒
    if response.status_code == 200:
      return response.json()
    else:
      log.info(f"❌ 请求失败: {response.status_code}")    
      return None
  except requests.exceptions.Timeout:
    log.info("❌ 请求超时")
    return None
  except requests.exceptions.ConnectionError:
    log.info("❌ 连接错误")
    return None
  except Exception as e:
    log.info(f"❌ 请求异常: {e}")
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
    
    # 更新last_ts为返回记录中最大的update_unix - 优化内存使用
    max_update_unix = last_ts
    for post in posts:
        try:
            update_unix = int(post.get('update_unix', 0))
            if update_unix > max_update_unix:
                max_update_unix = update_unix
        except (ValueError, TypeError):
            continue
    
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
    
    # 显式删除局部变量引用，帮助内存释放
    del max_update_unix, processed_count

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
        message_json = json.dumps(message_data)
        success = client.publish(mapping["topic"], message_json)
        if success:
            log.info(f"✅ 已发送 {author} 的消息到 {mapping['topic']}")
        else:
            log.info(f"❌ 发送 {author} 的消息失败")
    except Exception as e:
        log.info(f"❌ 发送MQTT消息时出错: {e}")
    finally:
        # 清理局部变量
        del author, content, message_data
        if 'message_json' in locals():
            del message_json

def listen(client):
    """Posts监听主循环"""
    global last_ts
    
    log.info(f"🚀 开始监听Posts... (last_ts: {last_ts})")
    
    while True:
        posts = None  # 初始化变量
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
            
            # 记录内存使用统计
            log_memory_stats()
            
            # 休息5秒
            log.info("💤 等待5秒后继续监听...")
            time.sleep(5)
            
        except KeyboardInterrupt:
            log.info("\n⏹️ 用户中断监听")
            break
        except Exception as e:
            log.info(f"❌ 监听循环出错: {e}")
            log.info("等待5秒后重试...")
            time.sleep(5)
        finally:
            # 确保每次循环后清理posts变量
            if posts is not None:
                del posts


if __name__ == "__main__":

    from emqx import MQTTConfig, MQTTClient
    
    log.info("🚀 启动Posts监听服务...")
    log.info(f"白名单用户: {', '.join(whitelist_users)}")
    log.info(f"初始时间戳: {last_ts}")
    
    # 创建MQTT配置 - 针对低配置主机优化
    config = MQTTConfig(
        auto_reconnect=True,
        max_reconnect_attempts=3,  # 减少重连次数
        reconnect_delay=5,         # 增加重连间隔
        keepalive=120,             # 增加心跳间隔，减少网络开销
        exponential_backoff=False  # 禁用指数退避，避免长时间等待
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
        try:
            client.disconnect()
            session.close()  # 关闭HTTP session
        except Exception as e:
            log.info(f"清理资源时出错: {e}")
        log.info("👋 程序退出")