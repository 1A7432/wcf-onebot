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
from .logger import logger, msg_logger, log_message_conversion, log_file_operation

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

    @classmethod
    def get_type_name(cls, type_id: int) -> str:
        """获取消息类型名称"""
        try:
            return cls(type_id).name
        except ValueError:
            return f"未知类型({type_id})"

class WCFMessage(BaseModel):
    """WCF 消息模型"""
    type: int
    content: str
    xml: str
    sender: str
    roomid: Optional[str] = None
    is_group: bool = False
    at_users: List[str] = Field(default_factory=list)
    # 文件相关字段
    thumb: Optional[str] = None         # 缩略图文件路径
    extra: Optional[str] = None         # 额外文件路径（如图片、视频等）
    file_url: Optional[str] = None      # 文件的HTTP URL
    thumb_url: Optional[str] = None     # 缩略图的HTTP URL（仅图片消息）
    file_name: Optional[str] = None     # 文件名
    file_size: Optional[int] = None     # 文件大小（字节）

    def log_details(self):
        """记录消息详情"""
        msg_type = WeChatMsgType.get_type_name(self.type)
        msg_logger.debug(f"收到{msg_type}消息:")
        msg_logger.debug(f"发送者: {self.sender}")
        msg_logger.debug(f"群ID: {self.roomid if self.is_group else '非群消息'}")
        msg_logger.debug(f"内容: {self.content}")
        if self.extra:
            msg_logger.debug(f"文件路径: {self.extra}")
        if self.thumb:
            msg_logger.debug(f"缩略图路径: {self.thumb}")
        if self.file_url:
            msg_logger.debug(f"文件URL: {self.file_url}")
            msg_logger.debug(f"文件名: {self.file_name}")
            msg_logger.debug(f"文件大小: {self.file_size} 字节")

class OneBotMessage(BaseModel):
    """OneBot v11 消息模型"""
    post_type: str = "message"
    time: int = Field(default_factory=lambda: int(datetime.now().timestamp()))
    self_id: int = Field(default_factory=lambda: MessageConverter._convert_sender_id(config.self_id))
    message_type: Literal["private", "group"]
    sub_type: str = "normal"
    message_id: int
    user_id: int
    message: str
    raw_message: str
    font: int = 0
    sender: Dict[str, Any] = Field(default_factory=dict)
    group_id: Optional[int] = None
    message_seq: Optional[int] = None
    anonymous: Optional[Dict[str, Any]] = None

    def log_details(self):
        """记录消息详情"""
        msg_logger.info(
            f"OneBot消息 - 类型: {self.message_type}, "
            f"发送者: {self.user_id}, "
            f"内容: {self.message}"
        )

class FileManager:
    """文件管理器"""
    def __init__(self, storage_path: str = "storage"):
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)
        logger.info(f"初始化文件管理器，存储路径: {storage_path}")
        
        # 不在初始化时启动清理任务
        self._cleanup_task = None
    
    def start_cleanup(self):
        """启动清理任务"""
        if self._cleanup_task is None:
            try:
                loop = asyncio.get_running_loop()
                self._cleanup_task = loop.create_task(self._clean_old_files())
            except RuntimeError:
                logger.warning("无法启动清理任务：没有运行中的事件循环")
    
    def stop_cleanup(self):
        """停止清理任务"""
        if self._cleanup_task is not None:
            self._cleanup_task.cancel()
            self._cleanup_task = None
    
    async def download_file(self, url: str, filename: str = None) -> Optional[Path]:
        """下载文件并返回本地路径"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url)
                response.raise_for_status()
                
                if not filename:
                    # 从URL或Content-Disposition中获取文件名
                    filename = self._get_filename_from_response(response, url)
                
                # 生成唯一文件名
                file_path = self.storage_path / self._generate_unique_filename(filename)
                
                # 保存文件
                async with aiofiles.open(file_path, 'wb') as f:
                    await f.write(response.content)
                
                log_file_operation("下载", str(file_path))
                return file_path
                
        except Exception as e:
            log_file_operation("下载", url, success=False)
            logger.error(f"文件下载失败: {str(e)}")
            return None
    
    def _get_filename_from_response(self, response: httpx.Response, url: str) -> str:
        """从响应或URL中获取文件名"""
        # 尝试从Content-Disposition获取
        if 'content-disposition' in response.headers:
            cd = response.headers['content-disposition']
            if 'filename=' in cd:
                return cd.split('filename=')[-1].strip('"')
        
        # 从URL中获取
        return url.split('/')[-1] or 'unknown_file'
    
    def _generate_unique_filename(self, original_name: str) -> str:
        """生成唯一的文件名"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        name, ext = os.path.splitext(original_name)
        return f"{name}_{timestamp}{ext}"
    
    def _is_file_valid(self, file_path: Path) -> bool:
        """检查文件是否有效（未过期）"""
        if not file_path.exists():
            return False
        
        # 获取文件修改时间
        mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
        # 文件超过24小时就视为过期
        return datetime.now() - mtime < timedelta(hours=24)
    
    async def _clean_old_files(self):
        """定期清理旧文件"""
        while True:
            try:
                cleaned_count = 0
                for file_path in self.storage_path.glob('*'):
                    if not self._is_file_valid(file_path):
                        file_path.unlink()
                        cleaned_count += 1
                
                if cleaned_count > 0:
                    logger.info(f"清理了 {cleaned_count} 个过期文件")
                    
                await asyncio.sleep(3600)  # 每小时检查一次
                
            except Exception as e:
                logger.error(f"清理文件时出错: {str(e)}")
                await asyncio.sleep(3600)  # 发生错误时也等待一小时

# 创建全局文件管理器实例
file_manager = FileManager(config.storage_path)

class MessageConverter:
    """消息转换器"""
    @staticmethod
    async def wcf_to_onebot(msg: WCFMessage) -> OneBotMessage:
        """将WCF消息转换为OneBot消息"""
        try:
            # 记录原始消息
            msg.log_details()
            
            # 解析消息内容
            parsed_content = await MessageConverter._parse_message_content(msg)
            
            # 创建 OneBot 消息
            onebot_msg = OneBotMessage(
                message_type="group" if msg.is_group else "private",
                message_id=MessageConverter._generate_message_id(),
                user_id=MessageConverter._convert_sender_id(msg.sender),
                message=parsed_content,
                raw_message=msg.content,
                group_id=MessageConverter._convert_sender_id(msg.roomid) if msg.is_group else None,
            )
            
            # 记录转换后的消息
            onebot_msg.log_details()
            
            # 记录转换结果
            log_message_conversion(
                msg.dict(),
                onebot_msg.dict(),
                success=True
            )
            
            return onebot_msg
            
        except Exception as e:
            logger.error(f"消息转换失败: {str(e)}")
            log_message_conversion(
                msg.dict(),
                {"error": str(e)},
                success=False
            )
            raise
    
    @staticmethod
    def _extract_at_users(xml: str) -> List[str]:
        """从XML中提取被@的用户列表"""
        try:
            pattern = r'<atuserlist>(.*?)</atuserlist>'
            match = re.search(pattern, xml)
            if match:
                users = match.group(1).split(',')
                return [user for user in users if user]
            return []
        except Exception as e:
            logger.error(f"提取@用户列表失败: {str(e)}")
            return []
    
    @staticmethod
    def _extract_app_message_info(xml: str) -> Dict[str, str]:
        """从XML中提取APP消息信息"""
        try:
            title_pattern = r'<title>(.*?)</title>'
            desc_pattern = r'<des>(.*?)</des>'
            url_pattern = r'<url>(.*?)</url>'
            
            title = re.search(title_pattern, xml)
            desc = re.search(desc_pattern, xml)
            url = re.search(url_pattern, xml)
            
            return {
                'title': title.group(1) if title else '',
                'description': desc.group(1) if desc else '',
                'url': url.group(1) if url else ''
            }
        except Exception as e:
            logger.error(f"提取APP消息信息失败: {str(e)}")
            return {}
    
    @staticmethod
    async def _parse_message_content(msg: WCFMessage) -> str:
        """解析消息内容，处理特殊消息类型"""
        try:
            msg_type = WeChatMsgType(msg.type)
            
            if msg_type == WeChatMsgType.TEXT:
                return msg.content
                
            elif msg_type == WeChatMsgType.IMAGE:
                if msg.file_url:
                    file_path = await file_manager.download_file(msg.file_url)
                    if file_path:
                        return f"[CQ:image,file=file:///{file_path}]"
                return "[图片下载失败]"
                
            elif msg_type == WeChatMsgType.VOICE:
                if msg.file_url:
                    file_path = await file_manager.download_file(msg.file_url)
                    if file_path:
                        return f"[CQ:record,file=file:///{file_path}]"
                return "[语音下载失败]"
                
            elif msg_type == WeChatMsgType.VIDEO:
                if msg.file_url:
                    file_path = await file_manager.download_file(msg.file_url)
                    if file_path:
                        return f"[CQ:video,file=file:///{file_path}]"
                return "[视频下载失败]"
                
            elif msg_type == WeChatMsgType.FILE:
                if msg.file_url:
                    file_path = await file_manager.download_file(msg.file_url, msg.file_name)
                    if file_path:
                        return f"[CQ:file,file=file:///{file_path},name={msg.file_name}]"
                return "[文件下载失败]"
                
            elif msg_type == WeChatMsgType.APP:
                app_info = MessageConverter._extract_app_message_info(msg.xml)
                return f"[应用消息]\n标题: {app_info.get('title', '')}\n描述: {app_info.get('description', '')}\n链接: {app_info.get('url', '')}"
                
            else:
                logger.warning(f"未处理的消息类型: {msg_type.name}")
                return f"[未支持的消息类型: {msg_type.name}]"
                
        except Exception as e:
            logger.error(f"解析消息内容失败: {str(e)}")
            return f"[消息解析失败: {str(e)}]"
    
    @staticmethod
    def _generate_message_id() -> int:
        """生成消息ID"""
        return int(datetime.now().timestamp() * 1000)
    
    @staticmethod
    def _convert_sender_id(sender_id: str) -> int:
        """将微信ID转换为数字ID（为了兼容OneBot的整数ID要求）"""
        if not sender_id:
            return 0
        # 使用哈希函数生成一个固定的数字ID
        # 使用更短的哈希以避免整数溢出
        return int(hashlib.md5(sender_id.encode()).hexdigest()[:8], 16)
