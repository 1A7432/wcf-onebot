from aiohttp import web, WSMsgType
import asyncio
import json
from .wcf_client import WCFClient
from .config import config
from .logger import logger, log_webhook, log_message_conversion
from .models import MessageConverter, WCFMessage
from .onebot_client import OneBotClient

# 创建 WCF 客户端实例
wcf_client = WCFClient()
# 创建 OneBot 客户端实例
onebot_client = OneBotClient(config.onebot_ws_url, config.onebot_access_token)

# 创建应用
app = web.Application()

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
        logger.info(f"初始化完成，self_id: {numeric_id} (原始ID: {wxid})")
    except Exception as e:
        logger.error(f"初始化 self_id 失败: {str(e)}")
        raise

async def handle_webhook(request: web.Request) -> web.Response:
    """处理 WCF 的 Webhook 回调"""
    try:
        data = await request.json()
        log_webhook(data)
        
        # 解析为 WCFMessage
        wcf_msg = WCFMessage(**data)
        wcf_msg.log_details()
        
        # 转换消息
        onebot_msg = await MessageConverter.wcf_to_onebot(wcf_msg)
        if onebot_msg:
            log_message_conversion(data, onebot_msg.dict())
            # 发送到 OneBot 服务器
            await onebot_client.send_message(onebot_msg)
            return web.Response(text="OK")
        
        return web.Response(text="Ignored")
    except Exception as e:
        logger.error(f"处理 Webhook 失败: {str(e)}")
        return web.Response(text=str(e), status=500)

async def handle_websocket(request):
    """处理 WebSocket 连接"""
    ws = web.WebSocketResponse()
    await ws.prepare(request)
    
    logger.info("新的 WebSocket 连接已建立")
    
    try:
        async for msg in ws:
            if msg.type == WSMsgType.TEXT:
                try:
                    # 解析消息
                    data = json.loads(msg.data)
                    wcf_msg = WCFMessage(**data)
                    wcf_msg.log_details()
                    
                    # 转换消息
                    onebot_msg = await MessageConverter.wcf_to_onebot(wcf_msg)
                    if onebot_msg:
                        log_message_conversion(data, onebot_msg.dict())
                        # 发送到 OneBot 服务器
                        if await onebot_client.send_message(onebot_msg):
                            await ws.send_str(json.dumps({"status": "ok"}))
                        else:
                            await ws.send_str(json.dumps({"status": "failed", "error": "Failed to send to OneBot server"}))
                        
                except json.JSONDecodeError:
                    logger.error("WebSocket 消息解析失败: JSON 格式错误")
                    await ws.send_str(json.dumps({"error": "Invalid JSON"}))
                except Exception as e:
                    logger.error(f"WebSocket 消息处理失败: {str(e)}")
                    await ws.send_str(json.dumps({"error": str(e)}))
            
            elif msg.type == WSMsgType.ERROR:
                logger.error(f"WebSocket 连接错误: {ws.exception()}")
    
    finally:
        logger.info("WebSocket 连接已关闭")
    
    return ws

# 注册路由
app.router.add_post("/", handle_webhook)  # 根路径处理 Webhook
app.router.add_get("/ws", handle_websocket)  # WebSocket 路径

async def start_server():
    """启动服务器"""
    try:
        logger.info("服务正在启动...")
        
        # 初始化 self_id
        await init_self_id()
        
        # 设置self_id
        onebot_client.self_id = config.self_id
        
        # 连接到 OneBot 服务器
        if not await onebot_client.connect():
            logger.error("无法连接到 OneBot 服务器，服务将继续运行但消息转发可能失败")
        
        # 启动服务器
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, config.host, config.port)
        await site.start()
        
        logger.info(f"服务器已启动: http://{config.host}:{config.port}")
        
        # 保持服务器运行
        while True:
            await asyncio.sleep(3600)
            
    except Exception as e:
        logger.error(f"服务器启动失败: {str(e)}")
        raise
    finally:
        await wcf_client.close()

def run():
    """运行服务器"""
    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(start_server())
    except KeyboardInterrupt:
        logger.info("服务正在关闭...")
    finally:
        loop.close()

if __name__ == "__main__":
    run()
