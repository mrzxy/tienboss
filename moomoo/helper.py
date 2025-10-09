import re

def contains_chinese(text):
    """
    判断文本内容是否包含中文字符
    
    Args:
        text (str): 需要检查的文本内容
        
    Returns:
        bool: 如果文本包含中文字符返回 True，否则返回 False
    """
    if not isinstance(text, str):
        return False
    
    # 使用正则表达式匹配中文字符
    # \u4e00-\u9fff 是中文字符的 Unicode 范围
    chinese_pattern = re.compile(r'[\u4e00-\u9fff]+')
    return bool(chinese_pattern.search(text))
