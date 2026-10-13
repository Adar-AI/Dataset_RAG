import sys
import os
import json
import asyncio
from app.utils.task_utils import add_done_task, add_running_task
from app.conf.bailian_mcp_config import mcp_config
from agents.mcp import MCPServerStreamableHttp
from app.core.logger import logger

# ===================== MCP 联网搜索常量（便于随服务变更调整） =====================
# 当前百炼 EnhancedSearch MCP 提供的搜索工具名；换服务时改这里即可
MCP_SEARCH_TOOL = "search_pro"
# 连接与调用超时（秒）。联网搜索偶发较慢，留足余量；可用环境变量覆盖
MCP_TIMEOUT_SECONDS = float(os.getenv("MCP_TIMEOUT_SECONDS", "90"))
# 最多保留多少条联网结果（接口固定返回约 10 条，这里做一次截断，防止上下文过长）
MCP_MAX_DOCS = int(os.getenv("MCP_MAX_DOCS", "5"))

async def mcp_call(query):
    """
    异步调用百炼MCP搜索服务的核心函数。
    
    该函数负责初始化MCP客户端，建立SSE连接，调用远程工具，并返回原始结果。
    
    :param query: 搜索查询词（通常是经过改写后的精准Query）
    :return: MCP返回的原始结果对象 (包含 content, isError 等字段)
    """
    
    # ==================================================================================
    # 初始化百炼 MCP 客户端（Streamable HTTP）
    # ----------------------------------------------------------------------------------
    # 历史变更（重要）：百炼 MCP 已从 SSE 迁移到 Streamable HTTP。
    #   - 旧写法：MCPServerSse + url ".../mcps/WebSearch/sse" → 现在返回 404
    #   - 现写法：MCPServerStreamableHttp + url ".../mcps/EnhancedSearch/mcp"
    # 因此这里使用 MCPServerStreamableHttp；若换成其它 MCP 服务，只需改 .env 里的
    # MCP_DASHSCOPE_BASE_URL，无需改代码。
    #
    # 参数解释：
    #   name: 客户端名称，用于日志标识，方便调试。
    #   params: 连接配置字典
    #     - url: MCP 服务地址（Streamable HTTP 端点，以 /mcp 结尾）
    #     - headers: HTTP 请求头，必须包含 Authorization 字段传入 API Key 进行鉴权。
    #     - timeout: 连接建立和整体请求的超时时间。
    # ==================================================================================
    search_mcp = MCPServerStreamableHttp(
        name="search_mcp",
        params={
            "url": mcp_config.mcp_base_url,
            "headers": {"Authorization": mcp_config.api_key},
            "timeout": MCP_TIMEOUT_SECONDS
        }
    )

    try:
        logger.info(f"[MCP] 正在连接百炼联网搜索服务: {mcp_config.mcp_base_url}")
        # 建立与MCP服务的连接（异步方法，需await）
        await search_mcp.connect()

        logger.info(f"[MCP] 连接成功，正在调用工具 '{MCP_SEARCH_TOOL}' 查询: {query}")
        # 调用百炼MCP的搜索工具（核心步骤）
        # 注意工具名：EnhancedSearch 提供的工具是 "search_pro"（旧 WebSearch 服务里叫 bailian_web_search）。
        # 参数只有 query；工具 schema 为 additionalProperties=False，多传参数会被判为非法入参。
        result = await search_mcp.call_tool(
            tool_name=MCP_SEARCH_TOOL,
            arguments={"query": query}
        )
        logger.info("[MCP] 工具调用完成，已获取返回结果")
        return result
        
    except Exception as e:
        logger.error(f"[MCP] 调用过程中发生异常: {e}", exc_info=True)
        return None
        
    finally:
        # 无论调用成功/失败，最终都关闭MCP连接（释放资源，异步方法）
        await search_mcp.cleanup()


def node_web_search_mcp(state):
    """
    LangGraph同步节点函数：处理MCP搜索逻辑，作为整个搜索流程的入口。
    
    该节点会调用 mcp_call 异步函数获取搜索结果，并将其解析为结构化数据存储到 state 中。
    
    :param state: LangGraph的全局状态对象，包含 session_id, rewritten_query 等信息
    :return: 字典，包含结构化的搜索结果 web_search_docs，供后续节点使用
    """
    logger.info("---node_web_search_mcp 开始处理---")
    
    # 1. 标记任务开始
    add_running_task(state["session_id"], sys._getframe().f_code.co_name, state.get("is_stream"))

    # 2. 获取查询词
    query = state.get("rewritten_query", "")
    if not query:
        # 尝试回退到原始查询
        query = state.get("original_query", "")
        
    docs = []
    
    # 3. 执行搜索
    if query:
        try:
            # 同步-异步桥接：通过asyncio.run()执行异步的mcp_call函数
            logger.info(f"启动异步 MCP 调用，Query: {query}")
            
            # ======================================================================
            # MCP 返回结果格式解析说明
            # ----------------------------------------------------------------------
            # result 是一个 CallToolResult 对象 (定义在 agents.mcp.types 中)
            # result.content 是一个 TextContent 对象的列表，通常只有一项
            # result.content[0].text 是一个 JSON 字符串，包含实际的搜索结果
            #
            # 示例数据结构：
            # result.content[0].text = """
            # {
            #   "pages": [
            #     {
            #       "title": "HAK 180 烫金机使用手册",
            #       "url": "http://example.com/manual",
            #       "snippet": "在出厂默认状态下，若想设置局部转印..."
            #     },
            #     ...
            #   ]
            # }
            # """
            # ======================================================================
            result = asyncio.run(mcp_call(query))
            
            # 4. 解析结果
            if result and not result.isError and result.content:
                # 解析MCP原始结果：提取文本内容并转为JSON对象
                # result.content 通常是一个列表，第一项包含文本结果
                raw_text = result.content[0].text
                try:
                    data = json.loads(raw_text)
                    pages = data.get("pages") or []
                    
                    logger.info(f"MCP 返回原始页面数量: {len(pages)}")
                    
                    # 遍历结果，统一封装为结构化格式
                    for item in pages:
                        snippet = (item.get("snippet") or "").strip()
                        url = (item.get("url") or "").strip()
                        title = (item.get("title") or "").strip()
                        
                        # 过滤无核心摘要的结果
                        if not snippet:
                            continue
                            
                        docs.append({"title": title, "url": url, "snippet": snippet})

                    # 接口固定返回约 10 条，这里按 MCP_MAX_DOCS 截断，避免上下文过长
                    if len(docs) > MCP_MAX_DOCS:
                        logger.info(f"联网结果 {len(docs)} 条，按上限截断为 {MCP_MAX_DOCS} 条")
                        docs = docs[:MCP_MAX_DOCS]
                        
                except json.JSONDecodeError:
                    logger.error(f"MCP 返回结果解析 JSON 失败: {raw_text[:100]}...")
            else:
                if result and result.isError:
                    logger.error(f"MCP 返回错误: {result}")
                else:
                    logger.warning("MCP 返回结果为空或无效")

            logger.info(f"结构化搜索结果数量: {len(docs)}")
            
        except Exception as e:
            logger.error(f"MCP 搜索节点执行异常: {e}", exc_info=True)
    else:
        logger.warning("查询词为空，跳过 MCP 搜索")

    # 5. 标记任务结束
    add_done_task(state["session_id"], sys._getframe().f_code.co_name, state.get("is_stream"))
    
    logger.info("---node_web_search_mcp 处理结束---")
    
    # 若有有效搜索结果，返回结果供后续节点使用；无则返回空字典
    if docs:
        return {"web_search_docs": docs}
    return {}


if __name__ == '__main__':
    # 测试代码：单独运行该文件时，验证MCP搜索功能是否正常
    print("\n" + "="*50)
    print(">>> 启动 node_web_search_mcp 本地测试")
    print("="*50)
    
    test_state = {
        "session_id": "test_mcp_session",
        "rewritten_query": "HAK 180 在出厂默认状态下，若想在纸张上只把烫金膜转印到顶部 50 mm–170 mm 的局部区域，应在操作面板上如何设置",
        "is_stream": False
    }

    try:
        # 调用MCP搜索节点函数，执行测试
        result_state = node_web_search_mcp(test_state)

        print("\n" + "="*50)
        print(">>> 测试结果摘要:")
        search_results = result_state.get('web_search_docs', [])
        print(f"搜索结果数量: {len(search_results)}")
        if search_results:
            print("首条结果预览:")
            print(json.dumps(search_results[0], indent=2, ensure_ascii=False))
        else:
            print("未获取到搜索结果")
        print("="*50)
        
    except Exception as e:
        logger.exception(f"测试运行期间发生未捕获异常: {e}")
