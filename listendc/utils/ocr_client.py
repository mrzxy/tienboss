#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
腾讯云 OCR 客户端封装
"""
import os
import re
import json
import base64
import logging

try:
    import yaml
except ImportError:
    yaml = None

try:
    from tencentcloud.common import credential
    from tencentcloud.common.profile.client_profile import ClientProfile
    from tencentcloud.common.profile.http_profile import HttpProfile
    from tencentcloud.common.exception.tencent_cloud_sdk_exception import TencentCloudSDKException
    from tencentcloud.ocr.v20181119 import ocr_client, models
    _SDK_AVAILABLE = True
except ImportError:
    _SDK_AVAILABLE = False


class OcrClient:
    """腾讯云 OCR 客户端"""

    def __init__(self, secret_id: str = None, secret_key: str = None, region: str = "ap-singapore"):
        """
        Args:
            secret_id:  腾讯云 SecretId，默认读取环境变量 TENCENTCLOUD_SECRET_ID
            secret_key: 腾讯云 SecretKey，默认读取环境变量 TENCENTCLOUD_SECRET_KEY
            region:     地域，默认 ap-singapore
        """
        if not _SDK_AVAILABLE:
            raise ImportError("请安装腾讯云 SDK: pip install tencentcloud-sdk-python-ocr")

        self.logger = logging.getLogger('OcrClient')
        secret_id  = secret_id  or os.getenv("TENCENTCLOUD_SECRET_ID")
        secret_key = secret_key or os.getenv("TENCENTCLOUD_SECRET_KEY")

        cred = credential.Credential(secret_id, secret_key)

        http_profile = HttpProfile()
        http_profile.endpoint = "ocr.intl.tencentcloudapi.com"

        client_profile = ClientProfile()
        client_profile.httpProfile = http_profile

        self.client = ocr_client.OcrClient(cred, region, client_profile)

    def contains_prof(self, data) -> bool:
        lines = self.recognize(data=data)
        return any(re.search(r'(?<!\S)Prof(?!\S)', line) for line in lines)

    def recognize(self, data: bytes = None, url: str = None) -> list[str]:
        """通用文字识别（基础版）

        Args:
            data: 图片原始字节（bytes 或 numpy uint8 array），与 url 二选一
            url:  图片网络地址，与 data 二选一

        Returns:
            list[str]: 识别出的文字行列表，识别失败返回空列表
        """
        try:
            req = models.GeneralBasicOCRRequest()
            params = {}

            if data is not None:
                # numpy array 转 bytes
                raw = bytes(data) if not isinstance(data, (bytes, bytearray)) else data
                params["ImageBase64"] = base64.b64encode(raw).decode()
            elif url:
                params["ImageUrl"] = url
            else:
                raise ValueError("data 和 url 不能同时为空")

            req.from_json_string(json.dumps(params))
            resp = self.client.GeneralBasicOCR(req)

            lines = [item.DetectedText for item in resp.TextDetections]
            self.logger.debug(f"OCR 识别到 {len(lines)} 行文字")
            return lines

        except TencentCloudSDKException as e:
            self.logger.error(f"OCR 请求失败: {e}")
            return []

    @classmethod
    def from_config(cls, config_file: str = None) -> "OcrClient":
        """从 config.yaml 创建实例

        Args:
            config_file: 配置文件路径，默认为 listendc/config.yaml

        Returns:
            OcrClient 实例
        """
        if yaml is None:
            raise ImportError("请安装 pyyaml: pip install pyyaml")

        if config_file is None:
            config_file = os.path.join(os.path.dirname(__file__), '..', 'config.yaml')
            config_file = os.path.normpath(config_file)

        with open(config_file, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)

        tencent = config.get('tencent', {})
        return cls(
            secret_id=tencent.get('secret_id'),
            secret_key=tencent.get('secret_key'),
            region=tencent.get('ocr_region', 'ap-singapore'),
        )





if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)

    ocr = OcrClient.from_config()
    
    from helpers import download_image
    img_path = input("请输入本地图片路径或图片URL: ").strip()
    if os.path.isfile(img_path):
        with open(img_path, 'rb') as f:
            data = f.read()
    else:
        data = download_image(img_path)
    containProf = ocr.contains_prof(data)
    print(containProf)

