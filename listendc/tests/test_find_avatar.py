#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
find_avatar_in_chat 单元测试
"""

import sys
import os
import unittest
from unittest.mock import patch, MagicMock
import numpy as np

# 将项目根目录加入 sys.path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from utils.helpers import find_avatar_in_chat, download_image

# 测试图片路径
STATIC_DIR  = os.path.join(os.path.dirname(__file__), '..', 'static')
AVATAR_PATH = os.path.normpath(os.path.join(STATIC_DIR, 'thumb.png'))

if __name__ == '__main__':

    data = download_image("https://media.discordapp.net/attachments/1466080854274080818/1471709889406701611/e1.png?ex=698fec24&is=698e9aa4&hm=6880dff725f7f58073a9a9a53798b293939ede9b2a15588f41ce15d18979d78e&=&format=webp&quality=lossless")
    r = find_avatar_in_chat(AVATAR_PATH, data)
    print(r)