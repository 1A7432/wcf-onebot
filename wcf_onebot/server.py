from fastapi import FastAPI, HTTPException, Header, WebSocket
from fastapi.middleware.cors import CORSMiddleware
import httpx
import json
import asyncio
from typing import Optional

from .config import config
from .models import WCFMessage, OneBotMessage, MessageConverter
from .wcf_client import wcf_client

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
        if not await wcf_client.is_login():
            raise Exception("WCF client not logged in")
            
        # 获取微信ID
        wxid = await wcf_client.get_self_wxid()
        if not wxid:
            raise Exception("Failed to get wxid")
            
        # 转换并缓存 self_id
        config.self_id = MessageConverter._convert_sender_id(wxid)
    except Exception as e:
        print(f"Failed to initialize self_id: {e}")

@app.on_event("startup")
async def startup_event():
    """服务启动时初始化"""
    await init_self_id()

@app.on_event("shutdown")
async def shutdown_event():
    """关闭时清理资源"""
    await onebot_client.aclose()
    await wcf_client.close()

@app.post("/message")
async def receive_message(message: WCFMessage):
    """接收来自 WCF 的消息并转发到 OneBot"""
    try:
        # 转换消息格式
        onebot_msg = await MessageConverter.wcf_to_onebot(message)
        
        # 发送到 OneBot 服务
        headers = {}
        if config.onebot_access_token:
            headers["Authorization"] = f"Bearer {config.onebot_access_token}"
            
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"http://{config.onebot_host}:{config.onebot_port}/",
                json=onebot_msg.dict(),
                headers=headers
            )
            response.raise_for_status()
            
        return {"status": "success"}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.websocket("/wcf/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket 连接处理"""
    await websocket.accept()
    try:
        while True:
            try:
                data = await websocket.receive_text()
                message = WCFMessage.parse_raw(data)
                onebot_msg = await MessageConverter.wcf_to_onebot(message)
                await websocket.send_text(onebot_msg.json())
            except Exception as e:
                print(f"Error processing message: {e}")
                # 发送错误消息给客户端
                await websocket.send_text(json.dumps({
                    "error": str(e)
                }))
    except Exception as e:
        print(f"WebSocket error: {e}")
    finally:
        try:
            await websocket.close()
        except:
            pass
