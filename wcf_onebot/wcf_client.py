import httpx
from typing import Optional, Dict, Any
from .config import config
from .logger import logger

class WCFClient:
    def __init__(self):
        self.client = httpx.AsyncClient(
            base_url=config.wcf_base_url,
            timeout=10.0  # 添加超时设置
        )
        logger.info(f"初始化 WCF 客户端，服务器地址: {config.wcf_base_url}")
    
    async def close(self):
        await self.client.aclose()
    
    async def is_login(self) -> bool:
        """检查是否已登录"""
        try:
            response = await self.client.get("/api/is_login")  # 修正 API 路径
            data = response.json()
            logger.debug(f"登录状态检查响应: {data}")
            return data.get("data", {}).get("is_login", False)  # 修正响应解析
        except Exception as e:
            logger.error(f"检查登录状态失败: {str(e)}")
            return False
    
    async def get_user_info(self) -> Optional[Dict[str, Any]]:
        """获取登录账号信息"""
        try:
            response = await self.client.get("/api/get_self_info")  # 修正 API 路径
            data = response.json()
            logger.debug(f"获取用户信息响应: {data}")
            return data.get("data", {})  # 修正响应解析
        except Exception as e:
            logger.error(f"获取用户信息失败: {str(e)}")
            return None
    
    async def get_self_wxid(self) -> Optional[str]:
        """获取机器人的微信ID"""
        try:
            user_info = await self.get_user_info()
            if user_info:
                wxid = user_info.get("wxid")
                logger.info(f"获取到机器人微信ID: {wxid}")
                return wxid
            return None
        except Exception as e:
            logger.error(f"获取微信ID失败: {str(e)}")
            return None

wcf_client = WCFClient()
