from fastapi import FastAPI, HTTPException, Header, WebSocket, Request
from fastapi.middleware.cors import CORSMiddleware
import httpx
import json
import asyncio
from typing import Optional
from datetime import datetime

from .config import config
from .models import WCFMessage, OneBotMessage, MessageConverter, file_manager
from .wcf_client import wcf_client
from .logger import logger, msg_logger

app = FastAPI(title="WCF-OneBot Bridge")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# OneBot HTTP 客户端
onebot_client = httpx.AsyncClient(
    base_url=f"http://{config.onebot_host}:{config.onebot_port}",
    headers={"Authorization": f"Bearer {config.onebot_access_token}"} if config.onebot_access_token else {}
)

async def init_self_id():
    """初始化并缓存 self_id"""
    try:
        # 检查登录状态
        logger.info("正在初始化 self_id...")
        if not await wcf_client.is_login():
            logger.error("WCF 客户端未登录")
            raise Exception("WCF client not logged in")
            
        # 获取微信ID
        wxid = await wcf_client.get_self_wxid()
        if not wxid:
            logger.error("获取微信ID失败")
            raise Exception("Failed to get wxid")
            
        # 存储原始微信ID
        config.self_id = wxid
        # 转换为数字ID用于日志显示
        numeric_id = MessageConverter._convert_sender_id(wxid)
        logger.info(f"初始化完成，self_id: {wxid} (数字ID: {numeric_id})")
    except Exception as e:
        logger.error(f"初始化 self_id 失败: {str(e)}")
        raise

@app.on_event("startup")
async def startup_event():
    """服务启动时初始化"""
    logger.info("服务正在启动...")
    try:
        await init_self_id()
        # 启动文件清理任务
        file_manager.start_cleanup()
        logger.info("服务启动成功")
    except Exception as e:
        logger.error(f"服务启动失败: {str(e)}")
        raise

@app.on_event("shutdown")
async def shutdown_event():
    """服务关闭时清理"""
    logger.info("服务正在关闭...")
    # 停止文件清理任务
    file_manager.stop_cleanup()
    await onebot_client.aclose()
    logger.info("服务已关闭")

@app.post("/message")
async def receive_message(message: WCFMessage):
    """接收来自 WCF 的消息并转发到 OneBot"""
    try:
        # 记录接收到的消息
        msg_logger.info("收到 WCF 消息:")
        message.log_details()
        
        # 转换为 OneBot 消息
        start_time = datetime.now()
        onebot_msg = await MessageConverter.wcf_to_onebot(message)
        conversion_time = (datetime.now() - start_time).total_seconds()
        msg_logger.info(f"消息转换耗时: {conversion_time:.3f}秒")
        
        # 转发到 OneBot
        msg_logger.info("正在转发到 OneBot...")
        response = await onebot_client.post(
            "/send_msg",
            json={
                "message_type": onebot_msg.message_type,
                "user_id": onebot_msg.user_id if onebot_msg.message_type == "private" else None,
                "group_id": onebot_msg.group_id if onebot_msg.message_type == "group" else None,
                "message": onebot_msg.message
            }
        )
        response.raise_for_status()
        
        msg_logger.info("消息转发成功")
        return {"status": "success", "message": "Message forwarded"}
        
    except Exception as e:
        error_msg = f"消息处理失败: {str(e)}"
        logger.error(error_msg)
        raise HTTPException(status_code=500, detail=error_msg)

async def handle_webhook(request: Request):
    """处理 WCF 的 Webhook 回调"""
    try:
        data = await request.json()
        logger.info(f"收到 WCF 回调消息: {data}")
        
        # 处理消息
        message = WCFMessage(**data)
        await receive_message(message)
        return {"status": "ok"}
    except Exception as e:
        logger.error(f"处理回调消息失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/webhook")
async def webhook(request: Request):
    return await handle_webhook(request)

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket 连接处理"""
    try:
        logger.info("新的 WebSocket 连接请求")
        await websocket.accept()
        logger.info("WebSocket 连接已建立")
        
        while True:
            try:
                # 接收消息
                data = await websocket.receive_text()
                msg_logger.info("收到 WebSocket 消息")
                
                # 解析消息
                try:
                    msg_data = json.loads(data)
                    message = WCFMessage(**msg_data)
                except json.JSONDecodeError:
                    logger.error("WebSocket 消息解析失败: JSON 格式错误")
                    continue
                except Exception as e:
                    logger.error(f"WebSocket 消息解析失败: {str(e)}")
                    continue
                
                # 处理消息
                try:
                    onebot_msg = await MessageConverter.wcf_to_onebot(message)
                    msg_logger.info("WebSocket 消息转换成功")
                    
                    # 转发到 OneBot
                    response = await onebot_client.post(
                        "/send_msg",
                        json={
                            "message_type": onebot_msg.message_type,
                            "user_id": onebot_msg.user_id if onebot_msg.message_type == "private" else None,
                            "group_id": onebot_msg.group_id if onebot_msg.message_type == "group" else None,
                            "message": onebot_msg.message
                        }
                    )
                    response.raise_for_status()
                    msg_logger.info("WebSocket 消息转发成功")
                    
                except Exception as e:
                    logger.error(f"WebSocket 消息处理失败: {str(e)}")
                    
            except Exception as e:
                logger.error(f"WebSocket 连接异常: {str(e)}")
                break
                
    except Exception as e:
        logger.error(f"WebSocket 连接失败: {str(e)}")
    finally:
        logger.info("WebSocket 连接已关闭")
