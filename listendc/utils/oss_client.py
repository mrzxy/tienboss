#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
阿里云 OSS 客户端封装（用于上传图片并返回公网 URL）
"""
import os
import uuid
import logging
from datetime import datetime

try:
    import yaml
except ImportError:
    yaml = None

try:
    import oss2
    _SDK_AVAILABLE = True
except ImportError:
    _SDK_AVAILABLE = False


class OssClient:
    """阿里云 OSS 客户端"""

    def __init__(self, access_key_id: str, access_key_secret: str,
                 endpoint: str, bucket: str,
                 public_base_url: str = None, prefix: str = "discord/"):
        """
        Args:
            access_key_id:     OSS AccessKey ID
            access_key_secret: OSS AccessKey Secret
            endpoint:          地域节点，如 oss-ap-southeast-1.aliyuncs.com
            bucket:            Bucket 名称，如 tine
            public_base_url:   对象访问的基础 URL（如绑定了 CNAME 自定义域名）。
                               不填则用 https://{bucket}.{endpoint}
            prefix:            对象 key 前缀
        """
        if not _SDK_AVAILABLE:
            raise ImportError("请安装阿里云 OSS SDK: pip install oss2")

        self.logger = logging.getLogger('OssClient')

        # endpoint 规范化为带 scheme 的形式
        ep = endpoint if endpoint.startswith(('http://', 'https://')) else f'https://{endpoint}'
        self.endpoint = ep
        self.bucket_name = bucket
        self.prefix = prefix.strip('/') + '/' if prefix else ''

        auth = oss2.Auth(access_key_id, access_key_secret)
        self.bucket = oss2.Bucket(auth, ep, bucket)

        if public_base_url:
            self.public_base_url = public_base_url.rstrip('/')
        else:
            host = ep.split('://', 1)[1]
            self.public_base_url = f'https://{bucket}.{host}'

    def upload_bytes(self, data: bytes, ext: str = 'png',
                     content_type: str = 'image/png') -> str:
        """上传二进制数据，返回公网访问 URL

        Args:
            data:         文件二进制内容
            ext:          文件扩展名（不含点）
            content_type: MIME 类型

        Returns:
            str: 对象的公网访问 URL
        """
        key = (
            f"{self.prefix}{datetime.now().strftime('%Y%m%d')}/"
            f"{uuid.uuid4().hex}.{ext}"
        )
        result = self.bucket.put_object(
            key, data, headers={'Content-Type': content_type}
        )
        if result.status != 200:
            raise RuntimeError(f"OSS 上传失败, status={result.status}")
        return f"{self.public_base_url}/{key}"

    @classmethod
    def from_config(cls, config_file: str = None) -> "OssClient":
        """从 config.yaml 的 oss 段创建实例

        Args:
            config_file: 配置文件路径，默认为 listendc/config.yaml

        Returns:
            OssClient 实例
        """
        if yaml is None:
            raise ImportError("请安装 pyyaml: pip install pyyaml")

        if config_file is None:
            config_file = os.path.join(os.path.dirname(__file__), '..', 'config.yaml')
            config_file = os.path.normpath(config_file)

        with open(config_file, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)

        oss = config.get('oss', {}) or {}
        return cls(
            access_key_id=oss.get('access_key_id'),
            access_key_secret=oss.get('access_key_secret'),
            endpoint=oss.get('endpoint', 'oss-ap-southeast-1.aliyuncs.com'),
            bucket=oss.get('bucket', 'tine'),
            public_base_url=oss.get('public_base_url'),
            prefix=oss.get('prefix', 'discord/'),
        )
