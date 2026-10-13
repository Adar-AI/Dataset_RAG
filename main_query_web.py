"""
检索（问答）Web 服务启动入口（工作流步骤 21）
============================================
职责：把 app/query_process/api/query_server.py 里的 FastAPI 应用跑起来，
      对外提供「同步问答 + SSE 流式问答 + 历史记录」三类接口。
访问地址：
  - 对话页：   http://127.0.0.1:8001/chat.html
  - 健康检查： GET  http://127.0.0.1:8001/health
  - 发起提问： POST http://127.0.0.1:8001/query      （is_stream=False 走同步返回）
  - 流式通道： GET  http://127.0.0.1:8001/stream/{session_id}   （SSE，逐字输出）
  - 历史记录： GET/DELETE http://127.0.0.1:8001/history/{session_id}

用法：
    uv run python main_query_web.py
    # 等价写法（开发期热重载）：
    uv run uvicorn app.query_process.api.query_server:app --host 127.0.0.1 --port 8001 --reload

注意：SSE 不流式（一次性全出）时，优先检查响应头是否带 X-Accel-Buffering: no，
      以及链路中间是否有同步阻塞调用。
"""
import asyncio
import sys

import uvicorn

from app.query_process.api.query_server import app
from app.core.logger import logger

HOST = "127.0.0.1"
PORT = 8001


def _apply_windows_event_loop_patch() -> None:
    """
    Windows 下 asyncio 兼容补丁（与导入服务保持同一套写法）。

    SSE 场景尤其依赖事件循环对「长连接 + 生成器」的稳定调度，
    SelectorEventLoop 在 Windows 上表现更可预期。
    """
    if sys.platform.startswith("win"):
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        logger.info("[启动] 已应用 Windows Selector 事件循环兼容补丁")


if __name__ == "__main__":
    _apply_windows_event_loop_patch()
    logger.info(f"[启动] 检索服务已就绪：http://{HOST}:{PORT}/chat.html")
    uvicorn.run(app, host=HOST, port=PORT)
