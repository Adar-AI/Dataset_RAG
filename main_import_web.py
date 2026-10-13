"""
导入 Web 服务启动入口（工作流步骤 20）
=====================================
职责：把 app/import_process/api/import_server.py 里的 FastAPI 应用跑起来。
访问地址：
  - 上传页： http://127.0.0.1:8000/import.html
  - 上传接口：POST http://127.0.0.1:8000/upload
  - 进度轮询：GET  http://127.0.0.1:8000/status/{task_id}
  - 接口文档： http://127.0.0.1:8000/docs

用法：
    uv run python main_import_web.py
    # 等价写法（开发期热重载）：
    uv run uvicorn app.import_process.api.import_server:app --host 127.0.0.1 --port 8000 --reload

为什么单独放一个入口文件，而不是直接 `python -m ...import_server`：
  1) 启动方式与工作流文档一致，PyCharm 里可以直接右键 Run；
  2) 统一在这里做 Windows 事件循环适配与端口配置，业务模块保持干净。
"""
import asyncio
import sys

import uvicorn

from app.import_process.api.import_server import app
from app.core.logger import logger

HOST = "127.0.0.1"
PORT = 8000


def _apply_windows_event_loop_patch() -> None:
    """
    Windows 下 asyncio 兼容补丁。

    背景：Windows 默认的 ProactorEventLoop 与部分同步阻塞式 SDK（以及 uvicorn 的
    信号处理）配合时容易出现 "Event loop is closed" / 子进程相关告警。
    这里统一改用 SelectorEventLoop，规避这类平台差异。
    """
    if sys.platform.startswith("win"):
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        logger.info("[启动] 已应用 Windows Selector 事件循环兼容补丁")


if __name__ == "__main__":
    _apply_windows_event_loop_patch()
    logger.info(f"[启动] 导入服务已就绪：http://{HOST}:{PORT}/import.html")
    uvicorn.run(app, host=HOST, port=PORT)
