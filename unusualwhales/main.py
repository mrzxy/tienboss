from weakref import proxy
import requests
import time
import json
import logging
import re
import psutil
import os
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# 配置日志 - 必须在导入 config 之前配置，因为 config 模块会在导入时使用 logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s -  %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
log = logging.getLogger(__name__)

from config import get_config

app_config = get_config()
# 验证配置
if not app_config.validate_config():
    raise RuntimeError("配置文件验证失败，请检查配置文件")


debug = app_config.is_debug()
send_history = []

proxy_url = None

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
  url = f"https://phx.unusualwhales.com/api/trump/tweets"

  payload={}
  headers = {
    'User-Agent': 'Apifox/1.0.0 (https://apifox.com)',
    'Accept': '*/*',
    'Connection': 'keep-alive',
  }

  try:
    proxy_url = None
    if debug:
        proxy_url = "127.0.0.1:7890"
    # 使用session发送请求，设置超时时间
    if proxy_url is not None:
        session.proxies = {"http": proxy_url, "https": proxy_url}

    response = session.get(url, headers=headers, timeout=(10, 30), )  # 连接超时10秒，读取超时30秒
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
    # max_update_unix = last_ts
    # for post in posts:
    #     try:
    #         update_unix = int(post.get('update_unix', 0))
    #         if update_unix > max_update_unix:
    #             max_update_unix = update_unix
    #     except (ValueError, TypeError):
    #         continue
    
    # if max_update_unix > last_ts:
    #     last_ts = max_update_unix
    #     log.info(f"更新last_ts为: {last_ts}")
    
    # 处理每个post
    processed_count = 0
    for post in posts:
        ts = post.get('timestamp', '')

        if in_send_history(int(ts)):
            continue

        # 使用示例
        if not is_ts_within_3min(ts):
            # log.info(f"该消息不在当前时间3分钟内: ts={ts}")
            continue
        
        content = post.get('post', '').strip()
        if content == "":
            log.info(f"❌ 消息为空")
            continue

        # 发送MQTT消息
        send_post_to_mqtt(client, content)
        add_send_history(int(ts))

        cn_content = send_chat_request_by_trump_news(content)
        if cn_content is not None:
            send_post_to_mqtt(client, cn_content)

        processed_count += 1
    
    log.info(f"本次发送了 {processed_count} 消息")
    
    # 显式删除局部变量引用，帮助内存释放
    # del max_update_unix, processed_count


def send_chat_request_by_trump_news(content):
    try:
        # 从配置文件获取API key
        api_key = app_config.get_anthropic_api_key()
        if not api_key:
            raise ValueError("Anthropic API key未配置")

        tip = "请将这些内容翻译成通俗易懂的中文，只需要返回翻译后的中文，不需要额外的注或解释"

        # 构建HTTP请求
        url = "https://api.anthropic.com/v1/messages"
        headers = {
            "Content-Type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01"
        }
        
        payload = {
            "model": "claude-opus-4-1-20250805",  # 使用标准模型名称
            "system": tip,
            "messages": [
                {"role": "user", "content": content}
            ],
            "max_tokens": 20000
        }

        # 发送HTTP请求
        response = requests.post(url, headers=headers, json=payload, timeout=60)
        
        if response.status_code == 200:
            result = response.json()
            if 'content' not in result or len(result["content"]) == 0:
                log.error(f"Anthropic HTTP请求返回内容为空: {response.status_code}, {response.text}, 原内容: {content}")
                return None
            text = result["content"][0]["text"]
            log.info(f"Anthropic HTTP请求成功，返回长度: {len(text)}")
            return text
        else:
            log.error(f"Anthropic HTTP请求失败: {response.status_code}, {response.text}")
            return None

    except requests.exceptions.Timeout:
        log.error("Anthropic请求超时")
        return None
    except requests.exceptions.RequestException as e:
        log.error(f"Anthropic HTTP请求异常: {e}")
        return None
    except Exception as e:
        log.error(f"Anthropic请求失败: {e}")
        return None
def in_send_history(id):
    for item in send_history:
        if item == id:
            return True
    return False
    
def add_send_history(id):
    send_history.append(id)
    if len(send_history) > 100:
        send_history[:] = send_history[-50:]
        log.info(f"历史记录已优化，当前保留 {len(send_history)} 条记录")

def send_post_to_mqtt(client, content):
    """发送post到MQTT"""
    webhook_url = "https://discord.com/api/webhooks/1386580439451435068/nQa_K4i0GGUo0ksQ_ftWuPkaz0Q4HDv6YBve1fjf0rNv9m-R5Q2ufwZURQN1I3cthLGB"
    if debug:
        webhook_url = "https://discord.com/api/webhooks/1421750366483251232/9g_IvTelfhqj8uP-IAxIAEcQt94ivQCM3AeTqhXESiXDGpAbfbwNZW8l23FJXPvtVolo?wait=true"
        
    if content == "":
      log.info(f"❌ 消息为空")
      return

    

    send_msg_by_webhook_sync(content, webhook_url)
    
         # 判断ts（13位毫秒时间戳）是否在当前时间3分钟内
def is_ts_within_3min(ts):
    """
    判断给定的13位毫秒时间戳是否在当前时间3分钟内

    Args:
        ts (str|int): 13位毫秒时间戳

    Returns:
        bool: True表示在3分钟内，False表示不在
    """
    try:
        ts_int = int(ts)
        ts_sec = ts_int // 1000
        now_sec = int(time.time())
        return abs(now_sec - ts_sec) <= 180
    except Exception as e:
        log.info(f"解析ts时出错: {e}")
        return False  

def send_msg_by_webhook_sync(msg, webhook):
    """
    同步版本的 webhook 消息发送函数
    
    Args:
        msg (str): 要发送的消息内容
        webhook (str): Discord webhook URL
        
    Returns:
        bool: 发送成功返回 True，失败返回 False
    """
    payload = {"content": msg}

    
    try:
        response = requests.post(webhook, json=payload, timeout=30)
        
        if response.status_code >= 200 and response.status_code <= 204:
            log.info("消息发送成功！")
            return response.json()
        else:
            log.error(f"发送失败: {response.status_code}, {response.text}")
            return None
    except requests.exceptions.Timeout:
        log.error("发送消息超时")
        return None
    except requests.exceptions.RequestException as e:
        log.error(f"发送消息时网络错误: {e}")
        return None
    except Exception as e:
        log.error(f"发送消息时出错: {e}")
        return None
        
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
            elif 'data' in posts and isinstance(posts['data'], list):
                log.info(f"📨 获取到 {len(posts['data'])} 条posts数据")
                
                # 处理posts数据
                if len(posts['data']) > 0:
                    process_posts(client, list(reversed(posts['data'])))
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

