import logging
import os
from datetime import datetime
from pathlib import Path

def setup_logger(name: str, log_dir: str = "logs") -> logging.Logger:
    """设置日志记录器"""
    # 创建日志目录
    log_dir = Path(log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)
    
    # 创建日志文件名，包含日期
    today = datetime.now().strftime("%Y%m%d")
    log_file = log_dir / f"{name}_{today}.log"
    
    # 创建日志记录器
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)
    
    # 文件处理器
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)
    
    # 控制台处理器
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    
    # 日志格式
    formatter = logging.Formatter(
        '%(asctime)s [%(levelname)s] %(name)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)
    
    # 添加处理器
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger

# 创建主日志记录器
logger = setup_logger("wcf_onebot")

# 创建消息转换日志记录器
msg_logger = setup_logger("message_convert", "logs/messages")

def log_message_conversion(wcf_msg: dict, onebot_msg: dict, success: bool = True):
    """记录消息转换过程"""
    status = "成功" if success else "失败"
    msg_logger.info(f"消息转换{status}:")
    msg_logger.info(f"WCF消息: {wcf_msg}")
    msg_logger.info(f"OneBot消息: {onebot_msg}")
    msg_logger.info("-" * 50)

def log_file_operation(operation: str, file_path: str, success: bool = True):
    """记录文件操作"""
    status = "成功" if success else "失败"
    logger.info(f"文件{operation}{status}: {file_path}")

def log_api_call(api_name: str, params: dict = None, response: dict = None, success: bool = True):
    """记录API调用"""
    status = "成功" if success else "失败"
    logger.debug(f"API调用 {api_name} {status}")
    if params:
        logger.debug(f"参数: {params}")
    if response:
        logger.debug(f"响应: {response}")
