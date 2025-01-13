import httpx
from typing import Optional, Dict, Any
from .config import config
from .logger import logger, log_api_request, log_api_response

class WCFClient:
    def __init__(self):
        self.client = httpx.AsyncClient(
            base_url=config.wcf_base_url,
            timeout=10.0
        )
        logger.info(f"初始化 WCF 客户端，服务器地址: {config.wcf_base_url}")
    
    async def close(self):
        await self.client.aclose()
    
    async def _request(self, method: str, url: str, **kwargs) -> Dict[str, Any]:
        """发送请求并记录日志"""
        try:
            log_api_request(method, url, kwargs.get("json"))
            response = await self.client.request(method, url, **kwargs)
            data = response.json()
            log_api_response(url, data, response.status_code)
            return data
        except Exception as e:
            logger.error(f"请求失败 {method} {url}: {str(e)}")
            raise
    
    async def is_login(self) -> bool:
        """检查是否已登录"""
        try:
            data = await self._request("GET", "/islogin")
            return data.get("data", False)
        except Exception as e:
            logger.error(f"检查登录状态失败: {str(e)}")
            return False
    
    async def get_user_info(self) -> Optional[Dict[str, Any]]:
        """获取登录账号信息"""
        try:
            data = await self._request("GET", "/userinfo")
            return data.get("data", {})
        except Exception as e:
            logger.error(f"获取用户信息失败: {str(e)}")
            return None
    
    async def get_self_wxid(self) -> Optional[str]:
        """获取机器人的微信ID"""
        try:
            data = await self._request("GET", "/selfwxid")
            if data.get("status") == 0 and data.get("data"):
                return data.get("data")
            return None
        except Exception as e:
            logger.error(f"获取微信ID失败: {str(e)}")
            return None

wcf_client = WCFClient()
