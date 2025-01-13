import httpx
from typing import Optional, Dict, Any
from .config import config

class WCFClient:
    def __init__(self):
        self.client = httpx.AsyncClient(base_url=config.wcf_base_url)
    
    async def close(self):
        await self.client.aclose()
    
    async def is_login(self) -> bool:
        """检查是否已登录"""
        try:
            response = await self.client.get("/islogin")
            return response.json().get("success", False)
        except Exception:
            return False
    
    async def get_user_info(self) -> Optional[Dict[str, Any]]:
        """获取登录账号信息"""
        try:
            response = await self.client.get("/userinfo")
            return response.json()
        except Exception:
            return None
    
    async def get_self_wxid(self) -> Optional[str]:
        """获取机器人的微信ID"""
        try:
            user_info = await self.get_user_info()
            if user_info:
                return user_info.get("wxid")
            return None
        except Exception:
            return None

wcf_client = WCFClient()
