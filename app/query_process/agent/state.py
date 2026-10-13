from typing_extensions import TypedDict
from typing import List
import copy


class QueryGraphState(TypedDict):
    """
    QueryGraphState 定义了整个查询流程中流转的数据结构。
    """
    session_id: str  # 会话唯一标识
    original_query: str  # 用户原始问题

    # 检索过程中的中间数据
    embedding_chunks: list  # 普通向量检索回来的切片
    hyde_embedding_chunks: list  # HyDE 检索回来的切片
    kg_chunks: list  # 图谱检索回来的切片
    web_search_docs: list  # 网络搜索回来的文档

    # 排序过程中的数据
    rrf_chunks: list  # RRF 融合排序后的切片
    reranked_docs: list  # 重排序后的最终 Top-K 文档

    # 生成过程中的数据
    prompt: str  # 组装好的 Prompt
    answer: str  # 最终生成的答案

    # 辅助信息
    item_names: List[str]  # 提取出的商品名称
    rewritten_query: str  # 改写后的问题
    history: list  # 历史对话记录
    is_stream: bool  # 是否流式输出标记


# 查询流程的默认初始状态（与 ImportGraphState 的 graph_default_state 保持同一套写法）
query_graph_default_state: QueryGraphState = {
    "session_id": "",
    "original_query": "",
    "embedding_chunks": [],
    "hyde_embedding_chunks": [],
    "kg_chunks": [],
    "web_search_docs": [],
    "rrf_chunks": [],
    "reranked_docs": [],
    "prompt": "",
    "answer": "",
    "item_names": [],
    "rewritten_query": "",
    "history": [],
    "is_stream": False,
}


def create_query_default_state(**overrides) -> QueryGraphState:
    """
    创建查询流程的默认状态，支持按需覆盖字段。

    使用 copy.deepcopy 返回全新实例，避免多个会话之间互相污染（与导入流程的
    create_default_state 语义一致）。

    :param overrides: 要覆盖的字段（关键字参数）
    :return: 新的 QueryGraphState 实例

    Examples:
        state = create_query_default_state(session_id="s1", original_query="HAK180 如何保养？")
    """
    state = copy.deepcopy(query_graph_default_state)
    state.update(overrides)
    return state


def get_query_default_state() -> QueryGraphState:
    """返回一份全新的查询默认状态，避免全局字典被就地修改。"""
    return copy.deepcopy(query_graph_default_state)


if __name__ == "__main__":
    s1 = create_query_default_state(session_id="s1", original_query="HAK180 保养")
    s2 = create_query_default_state()
    s1["item_names"].append("BrotherHAK180烫金机")
    print("s1:", s1["session_id"], s1["item_names"])
    print("s2 未被污染:", s2["session_id"] == "" and s2["item_names"] == [])