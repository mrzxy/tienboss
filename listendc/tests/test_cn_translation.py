#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试 fetch_anthropic_api 的中文翻译 prompt（procproFessorrChannel 使用的那段）
"""

import sys
import os
import asyncio
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from config.config import Config


def build_listener():
    """构造一个带真实 API 配置的 UserListener（不启动 discord）"""
    from unittest.mock import MagicMock, patch

    # OcrClient.from_config 在模块顶层调用，需要在 import 前 mock 掉
    with patch("utils.ocr_client.OcrClient.from_config", return_value=MagicMock()):
        # 确保重新执行模块顶层（首次 import 时 patch 已生效）
        import importlib
        import listeners.user_listener as _mod
        importlib.reload(_mod)
        UserListener = _mod.UserListener

    cfg = Config(os.path.join(os.path.dirname(__file__), '..', 'config.yaml'))
    anthropic_config = cfg.get_anthropic_config()

    listener = object.__new__(UserListener)
    listener.anthropic_config = anthropic_config
    listener.logger = __import__('logging').getLogger('test_cn_translation')
    return listener


PROMPT = """
保持原文的格式，然后用通俗易懂的中文替代原文内容，尽量把内容说的像个正常的中国人，语气不要太严肃，像个机器人，但同时也要像一个专业的基金经理。
以及必须遵守以下要求:
    1.不要出现任何有关带"翻译"俩字的提示，也不要给任何提示。
    2.以及原文中包含"<@&{id}>"的内容时保持原样，不需要翻译。样例:<@&1288011122103943201>
"""

# ---- 测试用例 ----

CASES = [
  
    {
        "name": "含 <@&id> mention 保持原样",
        "input": (
            "<@&1288011122103943201> Attention everyone: $AAPL earnings beat expectations. "
            "EPS came in at $1.53 vs $1.43 expected."
        ),
        "checks": [
            lambda r: r.get("success") is True,
            lambda r: "<@&1288011122103943201>" in r.get("data", {}).get("en_content", ""),
            lambda r: "翻译" not in r.get("data", {}).get("en_content", ""),
        ],
        "check_names": ["success=True", "<@&id> 保持原样", "不含'翻译'字样"],
    }
]


async def run_case(listener, case):
    print(f"\n{'='*60}")
    print(f"[测试] {case['name']}")
    print(f"[输入]\n{case['input']}")

    result = await listener.fetch_anthropic_api(case["input"], PROMPT, "claude-sonnet-4-6")

    output = result.get("data", {}).get("en_content", "")
    print(f"[输出]\n{output}")

    all_pass = True
    for check, name in zip(case["checks"], case["check_names"]):
        ok = check(result)
        status = "PASS" if ok else "FAIL"
        print(f"  [{status}] {name}")
        if not ok:
            all_pass = False

    return all_pass


async def main():
    listener = build_listener()
    results = []
    for case in CASES:
        ok = await run_case(listener, case)
        results.append((case["name"], ok))

    print(f"\n{'='*60}")
    print("汇总:")
    for name, ok in results:
        print(f"  {'PASS' if ok else 'FAIL'}  {name}")

    failed = [n for n, ok in results if not ok]
    if failed:
        print(f"\n{len(failed)} 个用例失败")
        sys.exit(1)
    else:
        print(f"\n全部 {len(results)} 个用例通过")


import re
if __name__ == "__main__":
    # asyncio.run(main())


    a = "<@&1440354561712721941> Attention everyone: $AAPL earnings beat expectations. EPS came in at $1.53 vs $1.43 expected."
    b = procContent(a)
    print(b)

