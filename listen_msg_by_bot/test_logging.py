#!/usr/bin/env python3
"""
日志测试脚本
用于验证日志系统是否正常工作
"""

from config import get_config
import logging

def test_logging():
    """测试日志配置和输出"""
    
    # 加载配置
    app_config = get_config()
    
    # 验证配置
    if not app_config.validate_config():
        raise RuntimeError("配置文件验证失败，请检查配置文件")
    
    # 配置日志
    log_config = app_config.get_logging_config()
    
    # 清除已有的日志配置
    for handler in logging.root.handlers[:]:
        logging.root.removeHandler(handler)
    
    logging.basicConfig(
        level=getattr(logging, log_config['level']),
        format=log_config['format'],
        datefmt=log_config['date_format'],
        force=True
    )
    logger = logging.getLogger(__name__)
    
    # 测试不同级别的日志
    logger.debug("这是DEBUG级别日志 - 默认不显示")
    logger.info("这是INFO级别日志 - 应该显示")
    logger.warning("这是WARNING级别日志 - 应该显示")
    logger.error("这是ERROR级别日志 - 应该显示")
    
    # 测试配置读取
    logger.info(f"当前环境: {app_config.get_environment()}")
    logger.info(f"调试模式: {app_config.is_debug()}")
    logger.info(f"代理设置: {app_config.get_proxy_url()}")
    logger.info(f"Anthropic API Key存在: {bool(app_config.get_anthropic_api_key())}")
    
    print("\n✅ 日志测试完成！如果您看到了上面的时间戳格式的日志输出，说明日志系统工作正常。")

if __name__ == "__main__":
    test_logging()
