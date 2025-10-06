#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
简单的内存监控测试脚本
"""

import psutil
import os
import time

def get_memory_info():
    """获取内存信息"""
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
        
        print(f"📊 内存统计 - 进程: RSS={rss_mb:.1f}MB, VMS={vms_mb:.1f}MB | 系统: 可用={system_available_mb:.0f}MB, 使用率={system_usage_percent:.1f}%")
        
        return {
            'process_rss_mb': rss_mb,
            'process_vms_mb': vms_mb,
            'system_available_mb': system_available_mb,
            'system_usage_percent': system_usage_percent
        }
        
    except Exception as e:
        print(f"获取内存统计失败: {e}")
        return None

if __name__ == "__main__":
    print("内存监控测试")
    print("=" * 50)
    
    # 测试基本内存获取
    memory_info = get_memory_info()
    if memory_info:
        print("✅ 内存监控功能正常")
    else:
        print("❌ 内存监控功能异常")
    
    print("\n模拟内存使用增长:")
    data_list = []
    for i in range(5):
        # 分配一些内存
        data_list.extend([f"test_data_{j}" for j in range(10000)])
        
        print(f"第{i+1}次分配后:")
        get_memory_info()
        time.sleep(1)
    
    print("\n清理内存后:")
    del data_list
    get_memory_info()
    
    print("\n测试完成")
