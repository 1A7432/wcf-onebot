import uvicorn
from wcf_onebot.config import config
from wcf_onebot.server import app

if __name__ == "__main__":
    uvicorn.run(
        "wcf_onebot.server:app",
        host=config.host,
        port=config.port,
        reload=True
    )
