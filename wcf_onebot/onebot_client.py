import asyncio
import json
import aiohttp
from .logger import logger
from .models import OneBotMessage, MessageConverter
from .config import config

class OneBotClient:
    """OneBot WebSocket客户端"""
    def __init__(self, ws_url: str, access_token: str = None):
        self.ws_url = ws_url
        self.access_token = access_token
        self.ws = None
        self.connected = False
        self._reconnect_task = None
        self._heartbeat_task = None
        self.self_id = None  # 存储self_id
        self._session = None

    async def connect(self):
        """连接到OneBot服务器"""
        try:
            # 确保有self_id
            if not self.self_id:
                self.self_id = config.self_id
                if not self.self_id:
                    logger.error("缺少self_id，无法连接到OneBot服务器")
                    return False

            # 将微信ID转换为数字ID
            numeric_id = MessageConverter._convert_sender_id(self.self_id)
            logger.info(f"使用数字ID连接: {numeric_id} (原始ID: {self.self_id})")

            # 构建headers
            headers = {
                "X-Self-ID": str(numeric_id),
                "X-Client-Role": "Universal",
                "User-Agent": "WCF-OneBot/1.0",
            }
            
            # 如果有访问令牌，添加到headers
            if self.access_token:
                headers["Authorization"] = f"Bearer {self.access_token}"

            # 创建新的session
            if not self._session:
                self._session = aiohttp.ClientSession()

            # 连接到服务器
            self.ws = await self._session.ws_connect(
                self.ws_url,
                headers=headers
            )
            self.connected = True
            logger.info(f"成功连接到OneBot服务器: {self.ws_url}")
            
            # 启动心跳任务
            self._heartbeat_task = asyncio.create_task(self.start_heartbeat())
            
            return True
        except Exception as e:
            logger.error(f"连接OneBot服务器失败: {str(e)}")
            self.connected = False
            return False

    async def _reconnect_loop(self):
        """重连循环"""
        while not self.connected:
            logger.info("尝试重新连接到OneBot服务器...")
            if await self.connect():
                break
            await asyncio.sleep(5)  # 等待5秒后重试

    async def reconnect(self):
        """重新连接到服务器"""
        if not self._reconnect_task or self._reconnect_task.done():
            self._reconnect_task = asyncio.create_task(self._reconnect_loop())

    async def close(self):
        """关闭连接"""
        if self.ws:
            await self.ws.close()
        if self._session:
            await self._session.close()
        self.connected = False
        if self._heartbeat_task:
            self._heartbeat_task.cancel()

    async def send_message(self, message: OneBotMessage):
        """发送消息到OneBot服务器"""
        try:
            if not self.connected or not self.ws or self.ws.closed:
                await self.reconnect()
                if not self.connected:
                    logger.error("无法发送消息：未连接到OneBot服务器")
                    return False

            await self.ws.send_json(message.dict())
            logger.info(f"消息已发送到OneBot服务器: {message.message}")
            return True
        except Exception as e:
            logger.error(f"发送消息到OneBot服务器失败: {str(e)}")
            await self.reconnect()
            return False

    async def receive_message(self):
        """接收OneBot服务器的消息"""
        if not self.connected:
            logger.error("未连接到OneBot服务器")
            return None

        try:
            msg = await self.ws.receive_json()
            return msg
        except Exception as e:
            logger.error(f"接收消息失败: {str(e)}")
            return None

    async def start_heartbeat(self):
        """启动心跳任务"""
        while True:
            if self.connected:
                try:
                    await self.ws.send_json({
                        "op": 2,
                        "d": {
                            "heartbeat": True
                        }
                    })
                    logger.debug("发送心跳包")
                except Exception as e:
                    logger.error(f"发送心跳失败: {str(e)}")
                    self.connected = False
                    
            await asyncio.sleep(30)  # 每30秒发送一次心跳
