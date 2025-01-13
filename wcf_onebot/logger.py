import logging
import os
import json
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

# 创建API调用日志记录器
api_logger = setup_logger("api_calls", "logs/api")

def format_json(data: dict) -> str:
    """格式化JSON数据为易读的字符串"""
    try:
        return json.dumps(data, ensure_ascii=False, indent=2)
    except:
        return str(data)

def log_message_conversion(wcf_msg: dict, onebot_msg: dict, success: bool = True):
    """记录消息转换过程"""
    status = "成功" if success else "失败"
    msg_logger.info(f"消息转换{status}:")
    msg_logger.info(f"WCF消息: {format_json(wcf_msg)}")
    msg_logger.info(f"OneBot消息: {format_json(onebot_msg)}")
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

def log_api_request(method: str, url: str, data: dict = None):
    """记录API请求"""
    api_logger.info(f"API请求 >>> {method} {url}")
    if data:
        api_logger.info(f"请求数据: {format_json(data)}")

def log_api_response(url: str, response: dict, status_code: int = 200):
    """记录API响应"""
    api_logger.info(f"API响应 <<< {url} [状态码: {status_code}]")
    api_logger.info(f"响应数据: {format_json(response)}")

def log_webhook(data: dict):
    """记录Webhook回调消息"""
    api_logger.info("收到Webhook回调:")
    api_logger.info(f"回调数据: {format_json(data)}")
