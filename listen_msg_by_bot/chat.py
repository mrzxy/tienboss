import re
import requests
import aiohttp
from anthropic import Anthropic, HUMAN_PROMPT, AI_PROMPT
import json
import os
import logging
import tempfile
from typing import List, Dict, Optional
from config import get_config

# 加载配置
app_config = get_config()

# 确保日志配置正确
logger = logging.getLogger(__name__)

tip = """
你是一个专业的华尔街情绪分析大模型。你的任务是接收一条或多条实时消息（如新闻标题、社交媒体推文等），并从中提取出对**美股市场（特别是指数、行业ETF或美股个股）具有价格驱动意义的信息**，忽略无关信息（如A股、港股、日经、欧元区本地数据等）。

请严格遵守以下规则：

【内容处理逻辑】
1. 如果信息对美股价格无明确驱动效应，则直接忽略，不输出。
2. 如果信息模糊或影响尚不明朗，请判断为"不易判断"。
3. 严格忽略以下内容：
   - 仅涉及 A股、港股、人民币、欧元、日经、欧洲本地经济数据
   - 没有价格驱动价值的官话、废话、重复评论、搞笑内容

【输出格式要求（每条）】
翻译：（将英文内容翻译成简洁、准确、地道的中文）
结论：利多 / 利空 / 不易判断，受影响标的（可以是指数如 SPX、QQQ，也可以是行业如 XLE、军工，也可以是个股如 TSLA、META）
原因：（一句话简洁说明为什么该消息可能导致价格变动）

【举例说明】
输入示例1：
"Trump says U.S. has complete control of Iran's skies."
输出：
翻译：特朗普表示美国"完全控制伊朗的领空"。
结论：利空，SPX / 利多军工板块（LMT, RTX）
原因：发言加剧地缘政治紧张，避险情绪升温，美股承压，军工板块受益。

输入示例2：
"Eurozone CPI final YoY matches expectations at 1.9%"
输出：
（忽略，无需输出）

输入示例3：
"Meta announces WhatsApp to launch in-app ads and paid subscription options."
输出：
翻译：Meta宣布将在WhatsApp中推出应用内广告和付费订阅服务。
结论：利多，META
原因：打开商业化新增长空间，营收预期增强。

【其他】
- 所有输出必须为中文。
- 避免出现"可能"、"或许"这类模糊判断，尽量明确归类为"利多 / 利空 / 不易判断"三类。
- 只对"对美股价格有可能产生变动"的消息进行输出，其他全部自动丢弃。

现在开始，你将持续接收消息文本（英文原文），逐条按照上述标准进行分析并返回结果。
"""

def extract_image_urls(text: str) -> List[str]:
    """从文本中提取所有图片链接，支持http/https、Markdown、HTML<img>。

    规则：
    - 匹配以 .png/.jpg/.jpeg/.gif/.webp/.bmp/.svg 结尾的链接，允许带查询参数或fragment。
    - 抽取Markdown: ![alt](url)
    - 抽取HTML: <img src="url">（仅提取符合图片后缀的链接）
    - 返回去重且保持首次出现顺序的列表。
    """
    if not text:
        return []

    image_ext_pattern = r"(?:png|jpe?g|gif|webp|bmp|svg)"

    # 1) 直接URL匹配（包含查询/fragment）
    url_pattern = rf"https?://[^\s)>'\"]+\.(?:{image_ext_pattern})(?:[?#][^\s)>'\"]*)?"

    # 2) Markdown: ![alt](url)
    md_img_pattern = rf"!\[[^\]]*\]\((https?://[^\s)>'\"]+\.(?:{image_ext_pattern})(?:[?#][^\s)>'\"]*)?)\)"

    # 3) HTML: <img src="url">
    html_img_pattern = rf"<img[^>]*?\bsrc=[\"'](https?://[^\s\"'>]+\.(?:{image_ext_pattern})(?:[?#][^\s\"'>]*)?)[\"'][^>]*>"

    candidates: List[str] = []

    # 先找markdown与html中的URL，再找裸露URL，避免重复
    for pat in (md_img_pattern, html_img_pattern, url_pattern):
        for match in re.findall(pat, text, flags=re.IGNORECASE):
            url = match if isinstance(match, str) else match[0]
            candidates.append(url)

    # 去重且保持顺序
    seen = set()
    result: List[str] = []
    for url in candidates:
        if url not in seen:
            seen.add(url)
            result.append(url)

    return result

def send_chat_request(content):
    try:
        # 从配置文件获取API key
        api_key = app_config.get_anthropic_api_key()
        if not api_key:
            raise ValueError("Anthropic API key未配置")
        
        anthropic = Anthropic(api_key=api_key)

        message = content


        response = anthropic.messages.create(
            model="claude-opus-4-1-20250805",
            system=[{ "type": "text", "text": tip }],
            messages=[
              {"role": "user", "content": message}
            ],
            max_tokens=20000,
            stream=False
        )
        text = response.content[0].text
        # 使用正则表达式提取translation内容
      
        return text

    except Exception as e:
        logger.error(f"Anthropic请求失败: {e}")
        return None

def send_chat_request_by_Heisen(content):
    try:
        # 从配置文件获取API key
        api_key = app_config.get_anthropic_api_key()
        if not api_key:
            raise ValueError("Anthropic API key未配置")

        tip = "请你扮演一个专业的华尔街基金经理，把我给你的内容先整理一下，然后用地道中文表达出来。不要增加段落和格式，直接一段话表达。每个股票代码前面加上$符号。如果要翻译的内容里面有Heisenberg，那么直接忽略这个。如果有和股票不相关的内容，直接空白处理。"

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
                logger.error(f"Anthropic HTTP请求返回内容为空: {response.status_code}, {response.text}, 原内容: {content}")
                return None
            text = result["content"][0]["text"]
            logger.info(f"Anthropic HTTP请求成功，返回长度: {len(text)}")
            return text
        else:
            logger.error(f"Anthropic HTTP请求失败: {response.status_code}, {response.text}")
            return None

    except requests.exceptions.Timeout:
        logger.error("Anthropic请求超时")
        return None
    except requests.exceptions.RequestException as e:
        logger.error(f"Anthropic HTTP请求异常: {e}")
        return None
    except Exception as e:
        logger.error(f"Anthropic请求失败: {e}")
        return None

def send_chat_request_by_chatting_room(content):
    tip = "请你扮演一个专业的股票机构从业者，把给你的内容翻译成通俗易懂的中文，不用解释也不用做备注，直接翻译成一段话就行, 直接返回翻译结果。"
    return send_chat(tip, content)

def send_chat(tip, content):
    try:
        # 从配置文件获取API key
        api_key = app_config.get_anthropic_api_key()
        if not api_key:
            raise ValueError("Anthropic API key未配置")

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
                logger.error(f"Anthropic HTTP请求返回内容为空: {response.status_code}, {response.text}, 原内容: {content}")
                return None
            text = result["content"][0]["text"]
            logger.info(f"Anthropic HTTP请求成功，返回长度: {len(text)}")
            return text
        else:
            logger.error(f"Anthropic HTTP请求失败: {response.status_code}, {response.text}")
            return None

    except requests.exceptions.Timeout:
        logger.error("Anthropic请求超时")
        return None
    except requests.exceptions.RequestException as e:
        logger.error(f"Anthropic HTTP请求异常: {e}")
        return None
    except Exception as e:
        logger.error(f"Anthropic请求失败: {e}")
        return None

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
                logger.error(f"Anthropic HTTP请求返回内容为空: {response.status_code}, {response.text}, 原内容: {content}")
                return None
            text = result["content"][0]["text"]
            logger.info(f"Anthropic HTTP请求成功，返回长度: {len(text)}")
            return text
        else:
            logger.error(f"Anthropic HTTP请求失败: {response.status_code}, {response.text}")
            return None

    except requests.exceptions.Timeout:
        logger.error("Anthropic请求超时")
        return None
    except requests.exceptions.RequestException as e:
        logger.error(f"Anthropic HTTP请求异常: {e}")
        return None
    except Exception as e:
        logger.error(f"Anthropic请求失败: {e}")
        return None

async def send_msg_by_webhook(msg, webhook):
    # webhook = "https://discord.com/api/webhooks/1386580439451435068/nQa_K4i0GGUo0ksQ_ftWuPkaz0Q4HDv6YBve1fjf0rNv9m-R5Q2ufwZURQN1I3cthLGB"
    # webhook = "https://discord.com/api/webhooks/1386583844475375726/6A6cjiaYkbgXHxmQ38muWvKJ4qJqt02HPDsNa92S5BTh_flHN83HMf1IRTDPLXtPYDmZ"

    payload = {"content": msg}
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(webhook, json=payload) as response:
                if response.status == 204:
                    logger.info("消息发送成功！")
                    return True
                else:
                    logger.error(f"发送失败: {response.status}, {await response.text()}")
                    return False
    except Exception as e:
        logger.error(f"发送消息时出错: {e}")
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

    webhook += "?wait=true"
    
    try:
        response = requests.post(webhook, json=payload, timeout=30)
        
        if response.status_code >= 200 and response.status_code <= 204:
            logger.info("消息发送成功！")
            return response.json()
        else:
            logger.error(f"发送失败: {response.status_code}, {response.text}")
            return None
    except requests.exceptions.Timeout:
        logger.error("发送消息超时")
        return None
    except requests.exceptions.RequestException as e:
        logger.error(f"发送消息时网络错误: {e}")
        return None
    except Exception as e:
        logger.error(f"发送消息时出错: {e}")
        return None

async def send_msg_by_mqtt(client, topic, channel, msg, other=None):
    try:
        message_data = {
            "channel": channel,
            "content": msg
        }
        if other is not None:
            message_data.update(other)

        success = client.publish(topic, json.dumps(message_data))
        return success
    except Exception as e:
        logger.error(f"发送消息时出错: {e}")
        return False

def call_deepseek(content):
    """同步版本的 deepseek 调用"""
    try:
        # 从配置文件获取API key
        api_key = app_config.get_huoshan_api_key()
        if not api_key:
            raise ValueError("火山 API key未配置")

        # 构建HTTP请求
        url = "https://ark.cn-beijing.volces.com/api/v3/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": "Bearer " + api_key
        }

        payload = {
            "model": "deepseek-v3-2-251201",  # 使用标准模型名称
            "messages": [
                {"role": "user", "content": content}
            ]
        }

        # 发送HTTP请求
        response = requests.post(url, headers=headers, json=payload, timeout=60)

        if response.status_code == 200:
            result = response.json()
            if 'choices' not in result or len(result["choices"]) == 0:
                logger.error(f"火山 HTTP请求返回内容为空: {response.status_code}, {response.text}, 原内容: {content}")
                return None
            text = result['choices'][0]["message"]['content']
            logger.info(f"火山 HTTP请求成功，返回长度: {len(text)}")
            return text
        else:
            logger.error(f"火山 HTTP请求失败: {response.status_code}, {response.text}")
            return None

    except requests.exceptions.Timeout:
        logger.error("火山请求超时")
        return None
    except requests.exceptions.RequestException as e:
        logger.error(f"火山 HTTP请求异常: {e}")
        return None
    except Exception as e:
        logger.error(f"火山请求失败: {e}")
        return None
# 示例用法
if __name__ == "__main__":
    content = """翻译:TRUMP: THE BIGGEST DAMAGE TO IRAN NUCLEAR SITES TOOK PLACE FAR BELOW GROUND LEVEL.
    结果:"""

    print(content)

    # 直接调用同步函数
    result = call_deepseek(content)
    print(f"Chat结果: {result}")
