from PIL import Image, ImageDraw, ImageFont
import paho.mqtt.client as mqtt
import time
import re
import requests
import json
import io
import platform
import os

def send_image_to_discord(image, webhook_url, message="", filename="options_image.png"):
    """
    发送图片到Discord webhook
    
    Args:
        image (PIL.Image): 要发送的图片对象
        webhook_url (str): Discord webhook URL
        message (str): 附加消息内容
        filename (str): 文件名
        
    Returns:
        bool: 发送是否成功
    """
    try:
        # 将PIL图片转换为高质量字节流
        img_buffer = io.BytesIO()
        image.save(img_buffer, format='PNG', quality=100, optimize=True, compress_level=1)
        img_buffer.seek(0)
        
        # 准备文件数据
        files = {
            'file': (filename, img_buffer, 'image/png')
        }
        
        # 准备消息数据
        data = { }
        
        # 发送到Discord
        response = requests.post(webhook_url, files=files, data=data, timeout=30)
        
        if response.status_code == 200 or response.status_code == 204:
            print(f"✅ 图片已成功发送到Discord")
            return True
        else:
            print(f"❌ 发送到Discord失败: {response.status_code} - {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ 发送图片到Discord时出错: {e}")
        return False
    finally:
        if img_buffer:
            img_buffer.close()

def parse_color(color_str):
    """
    解析各种颜色格式并转换为 PIL 支持的格式
    
    支持的格式：
    - 十六进制: "#FF0000", "#ff0000"
    - RGB: "rgb(255, 0, 0)", "RGB(255,0,0)"
    - 颜色名称: "red", "blue", "green"
    
    Args:
        color_str (str): 颜色字符串
        
    Returns:
        tuple or str: PIL 支持的颜色格式
    """
    if not color_str:
        return "#FFFFFF"
    
    color_str = color_str.strip()
    
    # 处理 RGB 格式: rgb(255, 0, 0)
    rgb_match = re.match(r'rgb\s*\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\)', color_str, re.IGNORECASE)
    if rgb_match:
        r, g, b = map(int, rgb_match.groups())
        return (r, g, b)
    
    # 处理十六进制格式（直接返回）
    if color_str.startswith('#'):
        return color_str
    
    # 处理颜色名称（直接返回，PIL 支持常见颜色名称）
    return color_str

def create_options_image(text_content, width=1200, height=70, bg_color="#000000", default_color="#FFFFFF", scale_factor=2):
    """
    创建高质量期权交易图片
    
    Args:
        text_content (list): 文本内容数组，支持两种格式：
            1. 字符串数组: ["11:09:08", "SPY", "PUT", "615.14"]
            2. 字典数组: [{"text": "11:09:08", "color": "#FFFFFF"}, {"text": "PUT", "color": "rgb(255,0,0)"}]
        width (int): 图片宽度，默认1200
        height (int): 图片高度，默认70
        bg_color (str): 背景色，支持多种格式，默认黑色
        default_color (str): 默认文字颜色，支持多种格式，默认白色
        scale_factor (int): 缩放因子，用于提高图片质量，默认2倍
        
    支持的颜色格式：
        - 十六进制: "#FF0000", "#ff0000"
        - RGB格式: "rgb(255, 0, 0)", "RGB(255,0,0)"
        - 颜色名称: "red", "blue", "green", "orange", "white" 等
    
    Returns:
        PIL.Image: 生成的高质量图片对象
    """
    # 计算高分辨率尺寸
    hq_width = width * scale_factor
    hq_height = height * scale_factor
    
    # 标准化输入数据格式
    segments = []
    
    for item in text_content:
        if isinstance(item, dict):
            # 字典格式：{"text": "内容", "color": "#颜色"}
            segments.append({
                "text": item.get("text", ""),
                "color": item.get("color", default_color)
            })
        else:
            # 字符串格式，使用默认颜色
            segments.append({
                "text": str(item),
                "color": default_color
            })
    
    # 创建高分辨率画布（解析背景色）
    parsed_bg_color = parse_color(bg_color)
    hq_image = Image.new("RGB", (hq_width, hq_height), parsed_bg_color)
    draw = ImageDraw.Draw(hq_image)
    
    # 加载高质量粗体字体（根据缩放因子调整大小）
    base_font_size = 28
    hq_font_size = base_font_size * scale_factor
    
    # 根据操作系统选择字体路径
    system = platform.system()
    font = None
    
    if system == "Windows":
        # Windows 字体路径
        windows_fonts = [
            "C:/Windows/Fonts/arialbd.ttf",      # Arial Bold
            "C:/Windows/Fonts/arial.ttf",       # Arial
            "C:/Windows/Fonts/calibrib.ttf",    # Calibri Bold
            "C:/Windows/Fonts/calibri.ttf",     # Calibri
            "C:/Windows/Fonts/verdanab.ttf",    # Verdana Bold
            "C:/Windows/Fonts/verdana.ttf",     # Verdana
            "C:/Windows/Fonts/times.ttf",       # Times New Roman
        ]
        
        for font_path in windows_fonts:
            try:
                if os.path.exists(font_path):
                    font = ImageFont.truetype(font_path, hq_font_size)
                    print(f"✅ 使用Windows字体: {font_path}")
                    break
            except Exception as e:
                print(f"尝试加载字体失败: {font_path} - {e}")
                continue
                
    elif system == "Darwin":  # macOS
        # macOS 字体路径
        macos_fonts = [
            "/System/Library/Fonts/Helvetica.ttc",
            "/System/Library/Fonts/Arial Bold.ttf", 
            "/System/Library/Fonts/ArialMT.ttc",
            "/System/Library/Fonts/Verdana Bold.ttf",
            "/System/Library/Fonts/Verdana.ttf",
            "/Library/Fonts/Arial.ttf",
        ]
        
        for font_path in macos_fonts:
            try:
                if os.path.exists(font_path):
                    font = ImageFont.truetype(font_path, hq_font_size)
                    print(f"✅ 使用macOS字体: {font_path}")
                    break
            except Exception as e:
                print(f"尝试加载字体失败: {font_path} - {e}")
                continue
                
    elif system == "Linux":
        # Linux 字体路径
        linux_fonts = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
            "/usr/share/fonts/TTF/arial.ttf",
            "/usr/share/fonts/TTF/arialbd.ttf",
        ]
        
        for font_path in linux_fonts:
            try:
                if os.path.exists(font_path):
                    font = ImageFont.truetype(font_path, hq_font_size)
                    print(f"✅ 使用Linux字体: {font_path}")
                    break
            except Exception as e:
                print(f"尝试加载字体失败: {font_path} - {e}")
                continue
    
    # 如果所有系统字体都加载失败，使用默认字体
    if font is None:
        try:
            # 尝试使用PIL的默认字体
            font = ImageFont.load_default()
            print(f"⚠️ 使用默认字体，字体大小可能不是最优")
        except:
            # 最后的备选方案
            font = ImageFont.load_default()
            print(f"❌ 字体加载失败，使用系统默认字体")
    
    # 计算每个文本段的宽度
    segment_widths = []
    for seg in segments:
        bbox = font.getbbox(seg["text"])
        segment_widths.append(bbox[2])
    
    # 计算总文本宽度
    total_text_width = sum(segment_widths)
    
    # 计算需要的间距，让文本均匀分布到整个图片宽度（高分辨率）
    margin = 10 * scale_factor  # 按比例调整边距
    available_width = hq_width - 2 * margin
    
    if len(segments) > 1:
        # 计算文本段之间的间距
        total_gap_space = available_width - total_text_width
        gap_between_segments = max(total_gap_space / (len(segments) - 1), 8 * scale_factor)  # 最小间距按比例调整
    else:
        gap_between_segments = 0
    
    # 重新计算实际需要的总宽度
    actual_total_width = total_text_width + (len(segments) - 1) * gap_between_segments
    
    # 如果超出可用宽度，按比例缩小间距
    if actual_total_width > available_width:
        gap_between_segments = max((available_width - total_text_width) / (len(segments) - 1), 2 * scale_factor)
    
    # 居中起始位置（高分辨率）
    start_x = (hq_width - (total_text_width + (len(segments) - 1) * gap_between_segments)) / 2
    
    # 垂直居中（根据高分辨率字体大小调整）
    y_pos = (hq_height - hq_font_size) // 2
    
    # 绘制文本，水平均匀分布
    current_x = start_x
    stroke_width = max(1, scale_factor // 2)  # 按比例调整描边宽度
    
    for i, seg in enumerate(segments):
        text = seg["text"]
        # 解析颜色格式
        parsed_color = parse_color(seg["color"])
        
        # 绘制文本，使用高质量渲染设置
        draw.text((current_x, y_pos), text, font=font, fill=parsed_color, 
                 stroke_width=stroke_width, stroke_fill=parsed_color)  # 高质量描边
        # 移动到下一个位置
        current_x += segment_widths[i]
        if i < len(segments) - 1:  # 不是最后一个元素
            current_x += gap_between_segments
    
    # 缩放回目标尺寸，使用高质量重采样
    if scale_factor > 1:
        final_image = hq_image.resize((width, height), Image.LANCZOS)
        return final_image
    else:
        return hq_image

def create_and_send_options_image(text_content, webhook_url, width=1200, height=70, bg_color="rgb(25, 32, 38)", message="", scale_factor=2):
    """
    创建高质量期权图片并发送到Discord的便捷函数
    
    Args:
        text_content (list): 文本内容数组
        webhook_url (str): Discord webhook URL
        width (int): 图片宽度
        height (int): 图片高度
        bg_color (str): 背景色
        message (str): 自定义消息，如果为空则自动生成
        scale_factor (int): 缩放因子，用于提高图片质量，默认2倍
        
    Returns:
        tuple: (image, success) - 高质量图片对象和发送是否成功
    """
    try:
        # 生成高质量图片
        image = create_options_image(
            text_content=text_content,
            width=width,
            height=height,
            bg_color=bg_color,
            scale_factor=scale_factor
        )
        
        # 准备消息
        if not message:
            if isinstance(text_content[0], dict):
                data_text = ' | '.join([item['text'] for item in text_content])
            else:
                data_text = ' | '.join(text_content)
            message = f"📊 **期权交易数据**\n\n**数据:** {data_text}\n**生成时间:** {time.strftime('%Y-%m-%d %H:%M:%S')}"
        
        # 发送到Discord
        success = send_image_to_discord(
            image=image,
            webhook_url=webhook_url,
            message=message,
            filename=f"options_{int(time.time())}.png"
        )
        
        return image, success
        
    except Exception as e:
        print(f"❌ 创建并发送图片时出错: {e}")
        return None, False

if __name__ == "__main__":
    # val = "{\"data\":[{\"text\":\"4:13:42\",\"color\":\"#FFFFFF\"},{\"text\":\"SPY\",\"color\":\"#FFFFFF\"},{\"text\":\"07/18/25\",\"color\":\"#FFFFFF\"},{\"text\":\"617\",\"color\":\"#FFFFFF\"},{\"text\":\"PUT\",\"color\":\"#FF0000\"},{\"text\":\"623.39\",\"color\":\"#FFFFFF\"},{\"text\":\"780@1.82_A\",\"color\":\"#FFFFFF\"},{\"text\":\"SWEEP\",\"color\":\"#FFFFFF\"},{\"text\":\"$142K\",\"color\":\"#FFFFFF\"},{\"text\":\"13\",\"color\":\"#FFFFFF\"}],\"timestamp\":1752489143766,\"source\":\"blackbox_options_monitor\"}"
    # f = json.loads(val)
    # print(f['data'])
    # exit()
    # Discord webhook URL
    DISCORD_WEBHOOK_URL = 'https://discord.com/api/webhooks/1386583844475375726/6A6cjiaYkbgXHxmQ38muWvKJ4qJqt02HPDsNa92S5BTh_flHN83HMf1IRTDPLXtPYDmZ'
    # pro
    DISCORD_WEBHOOK_URL = 'https://discord.com/api/webhooks/1388056531026841620/9xVZst5BI3tTNfhTBpGrrPm8EyeYgeAI2ZQuE8yrd-OHnbJmTgHLSAhI0yDoX3O35RnO'
    
    # 导入MQTT配置
    from emqx import MQTTConfig, MQTTClient
    
    config = MQTTConfig(
        auto_reconnect=True,
        max_reconnect_attempts=5,
        reconnect_delay=3
    )
    
    client = MQTTClient(config)
    
    # 设置回调函数
    def on_message(topic, payload, msg):
        print(f"收到消息: {topic} -> {payload}")
        # 性能测试（4C电脑上应<0.1秒）
        start_time = time.time()

        json_data = json.loads(payload)
        print(json_data)
        text_content_dict = json_data['data']
        
        # 使用字典数组格式（演示高质量RGB背景色）
        image = create_options_image(
            text_content=text_content_dict,
            width=1200,
            height=70,
            bg_color="rgb(25, 32, 38)",  # 深灰色背景
            scale_factor=5  # 使用3倍缩放获得超高质量
        )
        
        print(f"生成耗时: {(time.time()-start_time)*1000:.2f}毫秒")

        success = send_image_to_discord(
            image=image,
            webhook_url=DISCORD_WEBHOOK_URL,
            message='',
            filename=f"options_{int(time.time())}.png"
        )
        
        if success:
            print("✅ 图片已发送到Discord")
        else:
            print("❌ Discord发送失败")


    
    def on_connect(client, userdata, flags, rc):
        print("连接成功回调被调用")
    
    client.set_connection_callback(on_connect)
    
    try:
        # 连接
        if client.connect():
            print("连接成功")
            
            # 订阅主题
            client.subscribe("lis-msg/black_box", callback=on_message)
            
            print("客户端运行中，按Ctrl+C退出...")
            while True:
                time.sleep(1)
                
    except KeyboardInterrupt:
        print("用户中断")
    except Exception as e:
        print(f"运行错误: {e}")
    finally:
        client.disconnect()

def test_create_options_image():
    # 示例用法1：字典数组格式（展示各种颜色格式支持）
    text_content_dict = [
        {"text": "11:09:08", "color": "blue"},              # 颜色名称
        {"text": "SPY", "color": "magenta"},        # RGB格式
        {"text": "12/18/26", "color": "#FFFFFF"},           # 十六进制
        {"text": "610", "color": "rgb(255, 255, 255)"},    # RGB白色
        {"text": "PUT", "color": "#FF0000"},                # 十六进制红色
        {"text": "615.14", "color": "white"},              # 颜色名称
        {"text": "201@39.35_A", "color": "rgb(200, 200, 200)"}, # RGB灰色
        {"text": "BLOCK", "color": "orange"},              # 颜色名称橙色
        {"text": "$790.9K", "color": "rgb(255, 255, 0)"},  # RGB黄色
        {"text": "17", "color": "#FFFFFF"}                  # 十六进制白色
    ]
    
    # 示例用法2：字符串数组格式（使用默认颜色）
    text_content_simple = ["11:09:08", "SPY", "12/18/26", "610", "PUT", "615.14", "201@39.35_A", "BLOCK", "$790.9K", "17"]
    
    # 性能测试（4C电脑上应<0.1秒）
    start_time = time.time()
    
    # 使用字典数组格式（演示高质量RGB背景色）
    image = create_options_image(
        text_content=text_content_dict,
        width=1200,
        height=70,
        bg_color="rgb(25, 32, 38)",  # 深灰色背景
        scale_factor=5  # 使用3倍缩放获得超高质量
    )
    

    success = send_image_to_discord(
        image=image,
        webhook_url=DISCORD_WEBHOOK_URL,
        message='',
        filename=f"options_{int(time.time())}.png"
    )
    
    if success:
        print("✅ 图片已发送到Discord")
    else:
        print("❌ Discord发送失败")

    print(f"生成耗时: {(time.time()-start_time)*1000:.2f}毫秒")
    
    print("\n" + "="*50)
    print("测试便捷函数")
    print("="*50)
    
    # 测试便捷函数
    test_data = [
        {"text": "09:30:15", "color": "cyan"},
        {"text": "AAPL", "color": "lime"},
        {"text": "01/17/25", "color": "white"},
        {"text": "240", "color": "white"},
        {"text": "CALL", "color": "green"},
        {"text": "241.50", "color": "white"},
        {"text": "500@2.15", "color": "yellow"},
        {"text": "SWEEP", "color": "red"},
        {"text": "$1.07M", "color": "gold"}
    ]
    
    start_time_2 = time.time()
    image2, success2 = create_and_send_options_image(
        text_content=test_data,
        webhook_url=DISCORD_WEBHOOK_URL,
        message="🚀 **测试便捷函数** - AAPL期权扫单数据",
        scale_factor=3  # 使用3倍缩放获得更高质量
    )
    
    if success2:
        print("✅ 便捷函数测试成功")
    else:
        print("❌ 便捷函数测试失败")
        
    print(f"便捷函数耗时: {(time.time()-start_time_2)*1000:.2f}毫秒")