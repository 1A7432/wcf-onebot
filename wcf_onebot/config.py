from pydantic import BaseModel, Field
from typing import Optional
import os
from dotenv import load_dotenv
from pathlib import Path

# 加载环境变量
load_dotenv()

class Config(BaseModel):
    # WCF Client 配置
    wcf_host: str = os.getenv("WCF_HOST", "localhost")
    wcf_port: int = int(os.getenv("WCF_PORT", "8080"))
    
    @property
    def wcf_base_url(self) -> str:
        return f"http://{self.wcf_host}:{self.wcf_port}"
    
    # OneBot 服务配置
    onebot_host: str = os.getenv("ONEBOT_HOST", "localhost")
    onebot_port: int = int(os.getenv("ONEBOT_PORT", "8081"))
    onebot_access_token: Optional[str] = os.getenv("ONEBOT_ACCESS_TOKEN")

    # 服务器配置
    server_host: str = os.getenv("SERVER_HOST", "localhost")
    server_port: int = int(os.getenv("SERVER_PORT", "8082"))
    
    # 本服务配置
    host: str = os.getenv("HOST", "127.0.0.1")
    port: int = int(os.getenv("PORT", "8022"))
    
    # 文件存储配置
    storage_path: str = os.path.abspath(os.path.expanduser(os.getenv("STORAGE_PATH", "./storage")))
    
    # 缓存的机器人 self_id（原始微信ID）
    self_id: str = Field(default="")
    
    @property
    def wcf_api_url(self) -> str:
        return f"http://{self.wcf_host}:{self.wcf_port}"
        
    def __init__(self, **data):
        super().__init__(**data)
        # 确保存储目录存在
        os.makedirs(self.storage_path, exist_ok=True)

config = Config()
