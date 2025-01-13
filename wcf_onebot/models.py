from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any, Literal
from datetime import datetime
import json
import re
from enum import IntEnum
import os
from pathlib import Path
from .config import config
import httpx
import hashlib
import asyncio
import aiofiles
import mimetypes
from datetime import datetime, timedelta

class WeChatMsgType(IntEnum):
    """微信消息类型"""
    TEXT = 1            # 文本消息
    IMAGE = 3          # 图片消息
    VOICE = 34         # 语音消息
    VIDEO = 43         # 视频消息
    FILE = 49          # 文件消息
    EMOJI = 47         # 表情消息
    LOCATION = 48      # 位置消息
    APP = 49           # APP消息/链接/小程序
    SYSTEM = 10000     # 系统消息

class WCFMessage(BaseModel):
    """WCF 消息模型"""
    type: int
    content: str
    xml: str
    sender: str
    roomid: Optional[str] = None
    is_group: bool = False
    at_users: List[str] = Field(default_factory=list)
    extra: Dict[str, Any] = Field(default_factory=dict)
    # 文件相关字段
    file_url: Optional[str] = None      # 文件的HTTP URL
    thumb_url: Optional[str] = None     # 缩略图的HTTP URL（仅图片消息）
    file_name: Optional[str] = None     # 文件名
    file_size: Optional[int] = None     # 文件大小（字节）

class OneBotMessage(BaseModel):
    """OneBot v11 消息模型"""
    post_type: str = "message"
    time: int = Field(default_factory=lambda: int(datetime.now().timestamp()))
    self_id: int = Field(default_factory=lambda: config.self_id)
    message_type: Literal["private", "group"]
    sub_type: str = "normal"
    message_id: int
    user_id: int
    message: str
    raw_message: str
    font: int = 0
    sender: Dict[str, Any]
    
    # 群消息特有字段
    group_id: Optional[int] = None

class FileManager:
    """文件管理器"""
    def __init__(self, storage_path: str = "storage"):
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)
        
        # 启动清理任务
        asyncio.create_task(self._clean_old_files())
        
    async def download_file(self, url: str, filename: str = None) -> Path:
        """下载文件并返回本地路径"""
        # 生成文件名
        if not filename:
            # 从URL中提取文件名，如果没有则使用URL的哈希值
            filename = url.split("/")[-1]
            if not filename or len(filename) < 5:
                filename = hashlib.md5(url.encode()).hexdigest()
                
            # 添加文件扩展名
            content_type = mimetypes.guess_type(url)[0]
            if content_type:
                ext = mimetypes.guess_extension(content_type)
                if ext:
                    filename = f"{filename}{ext}"
                    
        # 生成本地路径
        file_path = self.storage_path / filename
        
        # 如果文件已存在且未过期，直接返回
        if file_path.exists() and self._is_file_valid(file_path):
            return file_path
            
        # 下载文件
        async with httpx.AsyncClient() as client:
            response = await client.get(url)
            response.raise_for_status()
            
            async with aiofiles.open(file_path, "wb") as f:
                await f.write(response.content)
                
        return file_path
        
    def _is_file_valid(self, file_path: Path) -> bool:
        """检查文件是否有效（未过期）"""
        # 文件不存在
        if not file_path.exists():
            return False
            
        # 检查文件修改时间
        mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
        return datetime.now() - mtime <= timedelta(hours=24)
        
    async def _clean_old_files(self):
        """定期清理旧文件"""
        while True:
            try:
                now = datetime.now()
                for file_path in self.storage_path.glob("*"):
                    if not self._is_file_valid(file_path):
                        try:
                            file_path.unlink()
                        except Exception:
                            pass
            except Exception:
                pass
            finally:
                await asyncio.sleep(3600)  # 每小时检查一次

# 创建全局文件管理器实例
file_manager = FileManager(config.storage_path)

class MessageConverter:
    """消息转换器"""
    @staticmethod
    def _extract_at_users(xml: str) -> List[str]:
        """从XML中提取被@的用户列表"""
        try:
            match = re.search(r'<atuserlist>(.*?)</atuserlist>', xml)
            if match:
                return match.group(1).split(',')
        except Exception:
            pass
        return []

    @staticmethod
    def _extract_app_message_info(xml: str) -> Dict[str, str]:
        """从XML中提取APP消息信息"""
        try:
            title_match = re.search(r'<title>(.*?)</title>', xml)
            desc_match = re.search(r'<des>(.*?)</des>', xml)
            url_match = re.search(r'<url>(.*?)</url>', xml)
            
            return {
                "title": title_match.group(1) if title_match else "",
                "desc": desc_match.group(1) if desc_match else "",
                "url": url_match.group(1) if url_match else "",
            }
        except Exception:
            return {}

    @staticmethod
    async def _parse_message_content(msg: WCFMessage) -> str:
        """解析消息内容，处理特殊消息类型"""
        msg_type = WeChatMsgType(msg.type)
        
        if msg_type == WeChatMsgType.TEXT:
            # 文本消息
            content = msg.content
            # 处理@消息
            for at_user in msg.at_users:
                content = content.replace(f"@{at_user}", f"[CQ:at,qq={MessageConverter._convert_sender_id(at_user)}]")
            return content
            
        elif msg_type == WeChatMsgType.IMAGE:
            # 图片消息
            if msg.file_url:
                try:
                    # 下载图片
                    file_path = await file_manager.download_file(msg.file_url)
                    return f"[CQ:image,file=file:///{file_path}]"
                except Exception as e:
                    print(f"下载图片失败: {e}")
            return "[图片消息]"
            
        elif msg_type == WeChatMsgType.VOICE:
            # 语音消息
            if msg.file_url:
                try:
                    # 下载语音
                    file_path = await file_manager.download_file(msg.file_url)
                    return f"[CQ:record,file=file:///{file_path}]"
                except Exception as e:
                    print(f"下载语音失败: {e}")
            return "[语音消息]"
            
        elif msg_type == WeChatMsgType.VIDEO:
            # 视频消息
            if msg.file_url:
                try:
                    # 下载视频
                    file_path = await file_manager.download_file(msg.file_url)
                    return f"[CQ:video,file=file:///{file_path}]"
                except Exception as e:
                    print(f"下载视频失败: {e}")
            return "[视频消息]"
            
        elif msg_type == WeChatMsgType.FILE:
            # 文件消息
            if msg.file_url:
                try:
                    # 下载文件
                    file_path = await file_manager.download_file(msg.file_url, msg.file_name)
                    return f"[CQ:file,file=file:///{file_path},name={msg.file_name or 'file'}]"
                except Exception as e:
                    print(f"下载文件失败: {e}")
            return f"[文件消息: {msg.file_name}]"
            
        elif msg_type == WeChatMsgType.EMOJI:
            # 表情消息
            return f"[CQ:face,id={msg.content}]"
            
        elif msg_type == WeChatMsgType.LOCATION:
            # 位置消息
            try:
                loc_data = json.loads(msg.content)
                return f"[CQ:location,lat={loc_data.get('lat', 0)},lon={loc_data.get('lon', 0)},title={loc_data.get('title', '')}]"
            except:
                return "[位置消息]"
            
        elif msg_type == WeChatMsgType.APP:
            # APP消息/链接/小程序
            app_info = MessageConverter._extract_app_message_info(msg.xml)
            if app_info:
                return f"[CQ:share,url={app_info['url']},title={app_info['title']},content={app_info['desc']}]"
            return "[应用消息]"
            
        elif msg_type == WeChatMsgType.SYSTEM:
            # 系统消息
            return f"[系统消息] {msg.content}"
            
        else:
            # 未知消息类型
            return f"[未知消息类型] {msg.content}"

    @staticmethod
    def _generate_message_id() -> int:
        """生成消息ID"""
        return int(datetime.now().timestamp() * 1000) % (2**31)

    @staticmethod
    def _convert_sender_id(sender_id: str) -> int:
        """将微信ID转换为数字ID（为了兼容OneBot的整数ID要求）"""
        return abs(hash(sender_id)) % (2**31)

    @staticmethod
    async def wcf_to_onebot(msg: WCFMessage) -> OneBotMessage:
        """将WCF消息转换为OneBot消息"""
        # 提取被@的用户列表
        msg.at_users = MessageConverter._extract_at_users(msg.xml)
        
        # 处理消息内容
        message = await MessageConverter._parse_message_content(msg)
        
        # 转换发送者ID
        user_id = MessageConverter._convert_sender_id(msg.sender)
        
        # 构建基本消息结构
        onebot_msg = {
            "post_type": "message",
            "time": int(datetime.now().timestamp()),
            "self_id": config.self_id,
            "message_type": "group" if msg.is_group else "private",
            "sub_type": "normal",
            "message_id": MessageConverter._generate_message_id(),
            "user_id": user_id,
            "message": message,
            "raw_message": msg.content,
            "font": 0,
            "sender": {
                "user_id": user_id,
                "nickname": msg.sender,
                "card": msg.sender,
            }
        }

        # 如果是群消息，添加群相关信息
        if msg.is_group and msg.roomid:
            onebot_msg["group_id"] = MessageConverter._convert_sender_id(msg.roomid)
            onebot_msg["sender"]["card"] = msg.sender  # 群名片

        return OneBotMessage(**onebot_msg)
