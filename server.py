# 连接器入口：uvicorn 启动（uv run python ./server.py）。

import uvicorn

from app.config import load_settings
from app.main import create_app

settings = load_settings()
app = create_app(settings)

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=settings.port, log_level="info")
