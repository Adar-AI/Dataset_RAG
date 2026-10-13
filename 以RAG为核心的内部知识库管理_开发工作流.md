# 以 RAG 为核心的内部知识库管理 · 开发工作流

> **项目定位**：个人开发 Demo —— 以 RAG 为核心的内部知识库管理与问答系统。 
> **目标**：在 PyCharm 里从空项目独立复现「导入流水线 + 检索流水线 + 两个 Web 服务」，并**按功能模块逐块留痕**，形成一份可回溯的个人开发记录。
> **用法**：每完成一步就执行该步的「验收」，不通过不要往下走；每个功能模块单独发起一轮对话（见第 0.4 节）。

---

## 0. 先读这一页（避免走弯路）

### 0.1 三个必须提前定死的事

**① 项目根目录与包名**
参考教案里出现过 `app`、`kb`、`knowledge_base_0115` 三种包名，那是同一项目不同阶段的写法。**从第一天就定死一种**，本路线图统一用：

```
Dataset_RAG/                 ← PyCharm 项目根（也是 uv 的根）
├── app/                     ← 唯一顶层包
│   ├── core/  conf/  lm/  clients/  utils/  tool/
│   ├── import_process/agent/{state.py, main_graph.py, nodes/}
│   └── query_process/agent/{state.py, main_graph.py, nodes/}
```

- 所有 import 一律写 `from app.xxx import yyy`，**永远不要写 `from Dataset_RAG.xxx`**。
- 在 PyCharm 里把 `Dataset_RAG` 目录标记为 **Sources Root**（右键 → Mark Directory as → Sources Root），否则 `app` 包找不到。

**② Java 式「先骨架后血肉」**
参考教案用的是 Top-Down：**先把 7 个节点写成只打日志的空函数（Stub）→ 串通主图 → 跑通流程 → 再逐个填逻辑**。请严格照做，这是这个项目最值钱的工程习惯，也是你最容易跳过而卡死的地方。

**③ 两个模型必须先在本地就位**（CPU 也能跑，只是慢）
- `BAAI/bge-m3` → 稠密 1024 维 + 稀疏向量
- `BAAI/bge-reranker-large` → 精排

用 `modelscope` 的 `snapshot_download` 下载到 `D:/ai_models/modelscope_cache/models`，然后把路径写进 `.env`。

### 0.2 你现有配置文件里的 5 个「坑」（开工前先修）

| # | 位置 | 问题 | 处理 |
| --- | --- | --- | --- |
| 1 | `.env:24` | `BGE_M3_PATH=D:/ai_models/modelscope_cachessss/...` 多了 `ssss`，且与 `MODELSCOPE_CACHE` 不一致 | 改成真实存在的路径，并在第 3 步后用一行 Python 验证能加载 |
| 2 | `.env:56` | `MINIO_ENDPOINT=127.0.0.1:9000` 没有协议前缀，同时又有 `MINIO_SECURE=False` | 代码里统一按 `endpoint + MINIO_SECURE` 拼 URL（参考教案就是这么做的）；先去 MinIO 控制台确认 9000 端口活着 |
| 3 | `.env:13,17` | `LLM_DEFAULT_MODEL=qwen3.8-max`、`VL_MODEL=qwen3.8-max` 疑似笔误（参考教案是 `qwen-flash` / `qwen3-vl-flash`） | 去百炼控制台「模型广场」抄准确 model id，写错会在第一次调用时报 `model not found` |
| 4 | `.env:18` | 真实 API Key 已明文存在 | 这份 Key 已经出现在聊天记录里，**建议去百炼控制台重新生成并替换**；`.env` 不要提交 Git |
| 5 | `.env:32` | 你自己加的 `ITEM_NAME_DIAG=1`，参考教案里没有 | 无妨，但注意别让代码依赖未定义变量 |

另外：`pyproject.toml` 里 `pymilvus[model]>=2.6.10` 与参考教案使用的 **Milvus 2.4.11 服务端**跨了大版本。pymilvus 2.5+ 对 2.4 服务端一般兼容，但如果出现 `hybrid_search` / `SPARSE_FLOAT_VECTOR` 相关报错，**第一反应就是降到 `pymilvus[model]==2.4.*`**。

### 0.3 需要你提前准备好的外部服务

| 服务 | 启动方式 | 验证 |
| --- | --- | --- |
| Milvus 2.4.11 单机版 | 官方 `milvus-standalone-docker-compose.yml` → `docker compose up -d` | `docker compose ps` 三个容器 Up |
| Attu 2.4.0（可视化，可选但强烈建议） | `docker run -d --name attu -p 8000:3000 -e MILVUS_URL=host.docker.internal:19530 zilliz/attu:v2.4.0` | 浏览器开 `http://localhost:8000` 能连上 |
| MinIO | `docker run -d --name minio -p 9000:9000 -p 9001:9001 -e MINIO_ROOT_USER=minioadmin -e MINIO_ROOT_PASSWORD=minioadmin quay.io/minio/minio server /data --console-address ":9001"` | `http://localhost:9001` 能登录 |
| MongoDB | `docker run -d --name mongo -p 27017:27017 mongo:latest` | `mongosh` 能连 |
| MinerU Token | https://mineru.net/apiManage/token（有效期 90 天） | 第 6 步验证 |
| 百炼 API Key | 阿里云百炼控制台 → API-KEY 管理 | 第 5 步验证 |
| 百炼 MCP 联网搜索 | 百炼「MCP 广场」搜索"联网搜索"→ 开通 → 绑定 API Key → 复制 SSE 地址 | 第 18 步验证 |

### 0.4 按功能模块留痕（本项目特有的工作方式）

这个 Demo 的目标不只是"跑通"，还要**把开发过程本身记录下来**。因此约定：

**每个功能模块 = 一轮独立对话**。一轮对话之内不跨模块，这样每轮都有清晰的输入（要做什么）、过程（为什么这么做）、结论（怎么验收），日后回看就是一份开发日志。

| 模块 | 对应步骤 | 对话里该问什么 | 该留下的产出 |
| --- | --- | --- | --- |
| **M1-1 环境与骨架** | 1–2 | uv 环境怎么配、目录为什么要分层 | 依赖清单、目录树 |
| **M1-2 日志与配置** | 3–5 | 为什么配置要集中成 dataclass、日志怎么按天切割 | `logger.py`、7 个 config |
| **M2-1 状态与主图骨架** | 6–7 | TypedDict 状态该放哪些字段、条件边怎么写 | `state.py`、`main_graph.py` + ASCII 流程图 |
| **M2-2 文档解析** | 8–9 | MinerU 四段式交互、图片为什么要转 MinIO | 节点②③ + 一份解析后的 MD |
| **M2-3 切片与向量化** | 10–12 | 为什么按标题切、稠密/稀疏向量分别解决什么 | 节点④⑤⑥ + 1024 维向量样例 |
| **M2-4 向量入库** | 13 | Schema 怎么设计、幂等为什么要先删后插 | 节点⑦ + Attu 截图 |
| **M3-1 检索状态与历史** | 14–15 | 多轮上下文怎么存、索引怎么建 | `state.py`、mongo 工具 |
| **M3-2 意图与商品名对齐** | 16 | 为什么要先对齐实体再检索、三分支怎么设计 | 节点① |
| **M3-3 多路召回** | 17–18 | 四路各自的盲区、HyDE 到底解决了什么 | 节点②③④ |
| **M3-4 融合与精排** | 19 | RRF 为什么只看排名、动态 TopK 的断崖怎么定 | 节点⑥⑦⑧ |
| **M4 Web 化** | 20–21 | 轮询 vs SSE 该用哪个、后台任务怎么不阻塞 | 两个 FastAPI 服务 |
| **M5 联调** | 22 | 端到端怎么验收、报错怎么定位 | 验收记录 |

**每轮对话建议的固定三段式**（复制到新对话开头即可）：

```
【模块】M2-2 文档解析（对应工作流步骤 8–9）
【现状】上一步已完成：<简述>；当前目录结构：<粘贴树>
【目标】完成 node_pdf_to_md 与 node_md_img，验收标准是 <粘贴路线图里的验收段落>
【约束】只用 app 包内已有工具；不要引入新依赖
```

**为什么值得这么做**：RAG 项目的坑几乎都在"参数与边界"上（阈值、批量大小、截断长度、超时）。把每一轮的决定和踩过的坑写下来，第二次做同类模块时你会直接省掉一半时间——这也是这份路线图里「易错」栏目的来源。

---

## 1. 步骤总览（18 步 / 5 个里程碑）

| 里程碑 | 步骤 | 产出 |
| --- | --- | --- |
| **M1 地基** | 1–5 | 环境、目录骨架、日志、配置层、LLM 客户端 |
| **M2 导入流水线** | 6–13 | 7 个节点 + 主图，能把 PDF 灌进 Milvus |
| **M3 检索流水线** | 14–19 | 7 个节点 + 主图，能问答 |
| **M4 Web 化** | 20–21 | 两个 FastAPI 服务（上传轮询 + SSE 对话） |
| **M5 联调** | 22 | 端到端 + 排查清单 |

---

## M1 · 地基（步骤 1–5）

### 步骤 1 · 项目与虚拟环境
**做什么**
1. PyCharm 新建项目 `Dataset_RAG`，解释器选 **uv**，Python **3.11**。
2. 确认 `pyproject.toml` 生成；把依赖装上（你现有的 `pyproject.toml` 已经够用）：

```bash
uv sync
# PyTorch 若要 GPU，单独从官方源装（国内镜像是 CPU 版）
# uv pip install --force-reinstall torch --index-url https://download.pytorch.org/whl/cu124
```

**验收**
```bash
uv run python -c "import langgraph, langchain_openai, pymilvus, minio, pymongo, fastapi; print('deps ok')"
uv run python -c "import torch; print(torch.__version__, torch.cuda.is_available())"
```

**易错**：PyCharm 终端默认可能没激活 uv 环境；用 `uv run python ...` 最稳。

---

### 步骤 2 · 目录骨架 + 工具链（先建空壳）
**做什么**：一次性建好全部目录与空文件，避免后面来回找路径。

```
app/
├── __init__.py
├── core/{__init__.py, logger.py, load_prompt.py}
├── conf/{__init__.py, lm_config.py, minio_config.py, milvus_config.py,
│         mongo_config.py, mineru_config.py, reranker_config.py, bailian_mcp_config.py}
├── lm/{__init__.py, lm_utils.py, embedding_utils.py}
├── clients/{__init__.py, minio_utils.py, milvus_utils.py, mongo_history_utils.py}
├── utils/{__init__.py, task_utils.py, format_utils.py, path_util.py,
│          sse_utils.py, rate_limit_utils.py, normalize_sparse_vector.py,
│          escape_milvus_string_utils.py}
├── tool/{__init__.py, download_bge_m3.py, download_reranker.py}
├── import_process/{__init__.py, agent/{__init__.py, state.py, main_graph.py,
│                  nodes/{__init__.py, node_entry.py, node_pdf_to_md.py,
│                         node_md_img.py, node_document_split.py,
│                         node_item_name_recognition.py,
│                         node_bge_embedding.py, node_import_milvus.py}}}
└── query_process/{__init__.py, agent/{__init__.py, state.py, main_graph.py,
                   nodes/{__init__.py, node_item_name_confirm.py,
                          node_search_embedding.py, node_search_embedding_hyde.py,
                          node_web_search_mcp.py, node_query_kg.py,
                          node_rrf.py, node_rerank.py, node_answer_output.py}}}

prompts/    doc/    output/    logs/    test/
main_import_web.py   main_query_web.py
```

**验收**：`uv run python -c "import app; print('app ok')"` 不报 `ModuleNotFoundError`。

**易错**：**每个包目录都要有 `__init__.py`**（哪怕是空的）。少一个，PyCharm 里能跑、命令行里就炸。

---

### 步骤 3 · 统一日志 `app/core/logger.py`
**做什么**：基于 `loguru` 封装，被全项目 `from app.core.logger import logger` 引用。
- 控制台 + 文件双输出，文件写 `logs/app_YYYYMMDD.log`
- 按天切割、保留 7 天、`encoding="utf-8"`、`enqueue=True`
- 开关与级别全部读 `.env`：`LOG_CONSOLE_ENABLE / LOG_CONSOLE_LEVEL / LOG_FILE_ENABLE / LOG_FILE_LEVEL / LOG_FILE_RETENTION`
- 参考教案还做了 `logger.patch(...)` 遍历调用栈，让日志显示**业务代码**的行号而不是 loguru 内部行号（可选，但很好用）

**验收**：任意脚本里 `logger.info("测试中文不乱码")`，控制台有彩色输出、`logs/` 下生成当日文件且中文正常。

---

### 步骤 4 · 配置层 `app/conf/*.py`
**做什么**：每个外部服务一个 `dataclass` + 一个模块级单例，值全部来自 `.env`。

| 文件 | 关键字段 |
| --- | --- |
| `lm_config.py` | `llm_model`、`vl_model`、`api_key`、`api_base`、`temperature` |
| `minio_config.py` | `endpoint`、`access_key`、`secret_key`、`bucket_name`、`minio_img_dir`、`minio_secure` |
| `milvus_config.py` | `milvus_url`、`chunks_collection`、`item_name_collection`、`entity_name_collection` |
| `mongo_config.py` | `mongo_url`、`db_name` |
| `mineru_config.py` | `base_url`、`api_token` |
| `reranker_config.py` | `bge_reranker_large`、`device`、`fp16` |
| `bailian_mcp_config.py` | `mcp_base_url`、`api_key` |

**统一写法**（后面 7 个文件照抄这个模式）：
```python
from dataclasses import dataclass
from dotenv import load_dotenv
import os

load_dotenv()

@dataclass
class MilvusConfig:
    milvus_url: str
    chunks_collection: str
    item_name_collection: str

milvus_config = MilvusConfig(
    milvus_url=os.getenv("MILVUS_URL"),
    chunks_collection=os.getenv("CHUNKS_COLLECTION"),
    item_name_collection=os.getenv("ITEM_NAME_COLLECTION"),
)
```

**验收**：写个 `test/01-config.py` 打印每个配置对象，确认没有 `None`（尤其检查 `BGE_M3_PATH` 指向的目录真实存在）。

**易错**：**每个配置文件里都要 `load_dotenv()`**，不要指望别的模块替你加载。

---

### 步骤 5 · LLM 客户端 `app/lm/lm_utils.py`
**做什么**
```python
from langchain_openai import ChatOpenAI
from app.conf.lm_config import lm_config

_client_cache = {}

def get_llm_client(model: str | None = None, json_mode: bool = False):
    target = model or lm_config.llm_model
    key = (target, json_mode)
    if key not in _client_cache:
        kw = {"model_kwargs": {"response_format": {"type": "json_object"}}} if json_mode else {}
        _client_cache[key] = ChatOpenAI(
            model=target, api_key=lm_config.api_key,
            base_url=lm_config.api_base, temperature=lm_config.temperature, **kw)
    return _client_cache[key]
```
- 走**百炼 OpenAI 兼容模式**：`https://dashscope.aliyuncs.com/compatible-mode/v1`
- 用 `(模型名, json_mode)` 元组做缓存，避免重复建客户端

**验收**：
```python
from app.lm.lm_utils import get_llm_client
print(get_llm_client().invoke("只回复：连接成功").content)
```
必须真的打印出文字。**这一步不过，后面全白搭。**

---

## M2 · 导入流水线（步骤 6–13）

### 步骤 6 · 定义导入状态 `app/import_process/agent/state.py`
**做什么**：`ImportGraphState(TypedDict)` + `graph_default_state` + `create_default_state(**overrides)`。
字段清单见 **图 1 右侧面板**：`task_id`、`is_pdf_read_enabled`、`is_md_read_enabled`、`is_normal_split_enabled`、`is_advanced_split_enabled`、`is_vllm_enabled`、`local_dir`、`local_file_path`、`file_title`、`pdf_path`、`md_path`、`md_content`、`chunks`、`item_name`、`split_path`、`embeddings_path`、`embeddings_content`。
`create_default_state` 用 `copy.deepcopy` 返回新实例，避免全局污染。

**验收**：`create_default_state(task_id="t1")` 能打印，改一个字段不影响再次调用。

---

### 步骤 7 · 先写 7 个 Stub 节点 + 串通主图（关键步骤，别跳）
**做什么**：7 个文件各写一个只打日志、原样返回 state 的函数。

```python
# app/import_process/agent/nodes/node_entry.py
import sys
from app.core.logger import logger
from app.import_process.agent.state import ImportGraphState

def node_entry(state: ImportGraphState) -> ImportGraphState:
    logger.info(f">>> [Stub] 执行节点: {sys._getframe().f_code.co_name}")
    return state
```
`node_entry` 这一版可以先带上真实的路由判断（`.pdf` → `is_pdf_read_enabled=True` + `pdf_path`；`.md` → `is_md_read_enabled=True` + `md_path`；其余只警告）。

再写 `main_graph.py`：
```python
workflow = StateGraph(ImportGraphState)
workflow.add_node("node_entry", node_entry)
# ... 其余 6 个
workflow.set_entry_point("node_entry")

def route_after_entry(state):
    if state.get("is_md_read_enabled"):   return "node_md_img"
    if state.get("is_pdf_read_enabled"):  return "node_pdf_to_md"
    return END

workflow.add_conditional_edges("node_entry", route_after_entry,
    {"node_md_img": "node_md_img", "node_pdf_to_md": "node_pdf_to_md", END: END})
workflow.add_edge("node_pdf_to_md", "node_md_img")
workflow.add_edge("node_md_img", "node_document_split")
workflow.add_edge("node_document_split", "node_item_name_recognition")
workflow.add_edge("node_item_name_recognition", "node_bge_embedding")
workflow.add_edge("node_bge_embedding", "node_import_milvus")
workflow.add_edge("node_import_milvus", END)
kb_import_app = workflow.compile()
```

**验收**（这一关过了再写业务逻辑）：
```python
from app.import_process.agent.main_graph import kb_import_app
from app.import_process.agent.state import create_default_state
for ev in kb_import_app.stream(create_default_state(local_file_path="x.pdf")):
    print(list(ev.keys()))
kb_import_app.get_graph().print_ascii()   # 需要 grandalf
```
应看到 7 个节点依次打印，PDF 与 MD 两条路径符合预期。

---

### 步骤 8 · 节点②：PDF → Markdown（MinerU 云端）
**做什么**：4 段式「申请上传链接 → PUT 直传 → 轮询 → 下载解压」。
- `POST {MINERU_BASE_URL}/file-urls/batch`（body 带 `model_version: "vlm"`）→ 拿 `signed_url` + `batch_id`
- `PUT signed_url` 上传 PDF —— **必须用 `requests.Session()` 并设 `trust_env = False`**
- `GET {MINERU_BASE_URL}/extract-results/batch/{batch_id}` 轮询：间隔 3s、上限 600s、`state` 为 `done/failed`
- `GET full_zip_url` → `zipfile.extractall()` → 按 `原名.md → full.md → 任意 .md` 三级优先级找目标 → 重命名统一
- 写回 `state["md_path"]`（绝对路径）与 `state["md_content"]`

**验收**：拿一份真 PDF 跑单文件 `__main__`，`output/` 下出现 `<文件名>/<文件名>.md` 且正文和图片都在。

**易错**
- 报 `403 SignatureDoesNotMatch` → 就是代理污染请求头，检查 `trust_env=False`
- 读 `pdf_path`/`local_dir` 前必须判空并 `raise`，不要静默返回
- **参考代码**：你 `E:\LangchainPythonWork\liu\node_pdf_to_md.py` 里已有完整实现（含 PyMuPDF 本地兜底），可直接对照

---

### 步骤 9 · 节点③：图片理解 + MinIO 转存
**做什么**（5 步流水）
1. 扫描 Markdown 里的本地图片引用
2. 调用 **VLM**（`qwen3-vl-flash` 等）生成中文摘要：图片转 Base64 → `HumanMessage` 多模态消息 → `invoke` → 取 `content` 作为 alt 文本
3. 上传 MinIO：桶不存在则创建，并设置**公网只读策略**；上传前先清理该文档旧目录（幂等）
4. 替换 Markdown：`![原描述](本地路径)` → `![VLM摘要](MinIO URL)`
5. 另存为 `_new.md` 或覆盖原文件

**验收**：MinIO 控制台能看到 `upload-images/<文档名>/...`；Markdown 里图片链接变成 `http://127.0.0.1:9000/...`，**浏览器直接打开这个 URL 能看到图片**（看不到就是桶策略没设对）。

**易错**
- 用**令牌桶限流**（参考教案默认每分钟 9 次、窗口 60s），否则批量图片必然 429
- VLM 摘要失败不能中断流程，退化为不填 alt
- **参考代码**：`E:\LangchainPythonWork\liu\node_md_img.py`

---

### 步骤 10 · 节点④：语义切片
**做什么**
- 两个阈值常量：`DEFAULT_MAX_CONTENT_LENGTH = 2000`、`MIN_CONTENT_LENGTH = 500`
- 正则 `^\s*#{1,6}\s+.+` 识别标题；用 `in_code_block` 跳过 ```` ``` ```` / `~~~` 围栏里的伪标题
- 无标题兜底 → 整篇作为一个 `{"title": "无标题"}` 章节
- 超长章节用 `RecursiveCharacterTextSplitter(chunk_overlap=0, separators=["\n\n","\n","。","！","？","；",".","!","?",";"," "])` 二次切分，`chunk_size = 2000 - len(标题前缀)`
- 同 `parent_title` 且长度 < 500 的相邻块合并
- 每个 chunk 字段：`title / content / parent_title / part / file_title`
- 写回 `state["chunks"]`，并把结果备份成 `output/<文档>/chunks.json`

**验收**：拿一份长文档跑，打印 chunk 总数与前 3 个 chunk 的 `title/content` 前 80 字，检查标题路径有没有丢、有没有超长块。

---

### 步骤 11 · 节点⑤：主体识别（Item Name）
**做什么**
- 取前 **5** 个切片、单切片截断 **800** 字、上下文总长上限 **2500** 字
- 拼 Prompt（模板外置到 `prompts/item_name_recognition.prompt`），`get_llm_client(json_mode=False).invoke(...)`
- 三级兜底：`file_title → file_name → chunks[0]["file_title"]`；LLM 失败一律回退 `file_title`
- 把识别结果写回 `state["item_name"]`，**并给每个 chunk 加 `item_name` 字段**
- 同时用 BGE-M3 给 `item_name` 生成稠密+稀疏向量，写入 Milvus 的 `kb_item_names` 集合（幂等：先按 `item_name` 删除再插入）

**验收**：打印 `state["item_name"]` 是否像"HAK 180 烫金机"这样的具体型号；Attu 里 `kb_item_names` 集合多了一条记录。

---

### 步骤 12 · 节点⑥：BGE-M3 混合向量化
**做什么**
- `app/lm/embedding_utils.py`：`get_bge_m3_ef()` 做**全局单例**，`generate_embeddings(texts)` 批量推理
- `BGEM3EmbeddingFunction(model_name=BGE_M3_PATH or "BAAI/bge-m3", device=BGE_DEVICE, use_fp16=BGE_FP16, normalize_embeddings=True)`
- 文本拼接：有 item_name 时 `f"商品：{item_name}，介绍：{content}"`（**核心词前置**，BERT 类模型对前 128 token 注意力最强）
- **`batch_size = 5`** 分批（防 OOM），每批独立 try/except，失败则保留原切片继续
- 每条 chunk 加 `dense_vector`（1024 维）与 `sparse_vector`（**必须把 `np.int64` / `np.float32` 转成 Python 原生类型**，否则 Milvus 序列化报错）

**验收**：CPU 上跑 5 个 chunk，打印 `len(chunk["dense_vector"])` 应为 **1024**；`type(list(chunk["sparse_vector"])[0])` 应为 `int`。

**易错**：CSR 结构要用 `indptr` 切片取 `indices`/`data` 再 `.tolist()`。

---

### 步骤 13 · 节点⑦：写入 Milvus
**做什么**
- 集合不存在才创建。Schema（9 字段）：`chunk_id`(INT64 主键 auto_id)、`content`/`title`/`parent_title`/`file_title`/`item_name`(VARCHAR 65535)、`part`(INT8)、`dense_vector`(FLOAT_VECTOR dim=1024)、`sparse_vector`(SPARSE_FLOAT_VECTOR)
- 索引：稠密 `HNSW + COSINE`，`{"M":16,"efConstruction":200}`；稀疏 `SPARSE_INVERTED_INDEX + IP`，`{"inverted_index_algo":"DAAT_MAXSCORE","quantization":"none"}`
- **幂等**：先按 `item_name` 删除旧数据（过滤表达式里的商品名要用 `escape_milvus_string` 转义）→ `flush`
- 插入前 `item.copy()` 并 `pop("chunk_id")`（避开 auto_id 冲突）；插入后用 `insert_result["ids"]` **回填 chunk_id**
- 插入后 `load_collection`，保证立即可查

**验收**：Attu 里 `kb_chunks` 有数据、两个向量字段都有值；**同一个文档再导入一次，记录数不翻倍**（幂等生效）。

**里程碑 M2 通过标准**：`kb_import_app.invoke(create_default_state(local_file_path="doc/某手册.pdf", local_dir="output"))` 端到端跑通，Milvus 里两个集合都有数据。

---

## M3 · 检索流水线（步骤 14–19）

### 步骤 14 · 检索状态 + 主图骨架
**做什么**
- `QueryGraphState` 字段见 **图 3 / 参考教案 07**：`session_id`、`original_query`、`rewritten_query`、`item_names`、`history`、`embedding_chunks`、`hyde_embedding_chunks`、`kg_chunks`、`web_search_docs`、`rrf_chunks`、`reranked_docs`、`prompt`、`answer`、`is_stream`
- **先用虚拟节点串图**：
  ```python
  builder.add_node("node_multi_search", lambda x: x)   # 分叉点
  builder.add_node("node_join", lambda x: {})          # 合并点
  ```
  四路搜索从 `node_multi_search` 并发出发，各自汇入 `node_join` → `node_rrf` → `node_rerank` → `node_answer_output` → `END`
- 条件边：`node_item_name_confirm` 之后，若 `state.get("answer")` 已存在（需反问或拒答）→ 直接跳 `node_answer_output`

**验收**：`query_app.get_graph().print_ascii()` 能看到四路并发结构；7 个 Stub 依次跑完。

---

### 步骤 15 · MongoDB 会话历史 `app/clients/mongo_history_utils.py`
**做什么**
- `HistoryMongoTool` 懒加载单例；集合 `chat_message`
- 复合索引：`create_index([("session_id", 1), ("ts", -1)])`（自带幂等）
- 接口：`save_chat_message(...)`（有 `message_id` 走 `update_one`，否则 `insert_one`）、`get_recent_messages(session_id, limit=10)`、`update_message_item_names(...)`、`clear_history(session_id)`

**验收**：写一条再读一条，中文正常；`db.chat_message.getIndexes()` 能看到复合索引。

---

### 步骤 16 · 节点①：意图识别与商品名对齐（全流程最难的一个）
**做什么**
1. 从 Mongo 取最近 **10** 条历史
2. 调 LLM（`json_mode=True`）+ 模板 `prompts/rewritten_query_and_itemnames.prompt`，返回 JSON `{item_names, rewritten_query}`
   - **必须剥离 ```` ```json ```` 代码块包裹**并做解析兜底
3. 逐个商品名生成 BGE-M3 向量 → `create_hybrid_search_requests` → `hybrid_search(collection_name=ITEM_NAME_COLLECTION, ranker_weights=(0.8, 0.2), norm_score=True, limit=5)`
4. 按分数三分支：
   - **确认**（高分）→ 回填 `state["item_names"]`，继续检索
   - **候选**（多个接近的候选）→ 生成**反问**写入 `state["answer"]`，走 `node_answer_output` 直接返回
   - **未知**（低于阈值）→ 生成**拒答**写入 `state["answer"]`
5. 把 `rewritten_query`、`item_names`、处理状态写回 Mongo

**注意**：参考教案里阈值自相矛盾（正文 0.95/0.8/0.6，代码 >0.85 / ≥0.6）。**以代码为准**，并把这个阈值提成模块级常量，方便你调。

**验收**：三种分支各构造一个 query 测一遍（精确型号 / 模糊型号 / 库里没有的型号），确认分别走"继续检索 / 反问 / 拒答"。

---

### 步骤 17 · 节点②③：两路向量召回
**做什么**
- `app/clients/milvus_utils.py` 先写好四个工具函数：`get_milvus_client()` 单例、`create_hybrid_search_requests(...)`、`hybrid_search(...)`、`fetch_chunks_by_chunk_ids(...)`
- **节点② `node_search_embedding`**：用 `rewritten_query` 生成向量，在 `CHUNKS_COLLECTION` 混合检索，过滤表达式 `item_name in ["...","..."]`，候选 `limit=10` → `limit=5`，`ranker_weights=(0.8, 0.2)`，`output_fields=["chunk_id","content","item_name"]`，写 `state["embedding_chunks"]`
- **节点③ `node_search_embedding_hyde`**：先让 LLM 生成"假设性答案"，把 `rewritten_query + " " + hyde_doc` 一起向量化再检索，写 `state["hyde_embedding_chunks"]`

**验收**：两个节点各自返回 5 条带 `item_name` 的切片；`item_names` 为空时直接返回空列表（不要报错）。

---

### 步骤 18 · 节点④⑤：MCP 联网 + 图谱（可选）
**做什么**
- 装 SDK：`uv add openai-agents`
- `from agents.mcp import MCPServerSse`，`url = MCP_DASHSCOPE_BASE_URL`，`headers={"Authorization": OPENAI_API_KEY}`
- `await connect()` → `await call_tool(tool_name="bailian_web_search", arguments={"query": ..., "count": 5})` → `await cleanup()`（**放 finally**）
- **同步节点调用异步 API 用 `asyncio.run(mcp_call(query))` 做桥接**
- 解析返回的 `pages`（`title/url/snippet`，空 snippet 剔除）→ 写 `state["web_search_docs"]`
- `node_query_kg` 本轮可以先只 return state（参考教案也标注"最后实现"，属于**扩展模块**，不阻塞 M2/M3 主线）

**验收**：单独跑 `node_web_search_mcp` 的 `__main__`，能打印出 5 条真实网页标题。

---

### 步骤 19 · 节点⑥⑦⑧：RRF → Rerank → 答案生成
**做什么**
- **RRF（节点⑥）**：`score += weight × 1/(k + rank)`，`k=60`，两路权重各 1.0，用 `chunk_id`（回退 `id`）去重，`max_results=10` → `state["rrf_chunks"]`
  - 写一个 `_as_entity_list` 兼容 pymilvus `Hit` / `dict` / `.get` 三种形态
- **Rerank（节点⑦）**：`FlagReranker(model_name_or_path=BGE_RERANKER_LARGE, device=..., use_fp16=...)` 单例；`compute_score([(query, doc), ...])`；合并 `rrf_chunks` + `web_search_docs` → 统一 `text/source` 字段 → **动态 TopK**：上限 10、下限 1，检测相邻分数断崖即截断 → `state["reranked_docs"]`
- **答案生成（节点⑧）**：
  1. `state["answer"]` 已有 → 直接输出
  2. 组装 Prompt：系统角色 + TopK 上下文（`MAX_CONTEXT_CHARS = 12000`）+ 历史对话 + 约束
  3. `llm.stream()` 流式 → 每个 delta 通过 `push_to_session(session_id, "delta", ...)` 推 SSE
  4. 从 `reranked_docs` 用正则 `!\[.*?\]\((.*?)\)` 提取图片 URL
  5. `save_chat_message` 写 Mongo，推 `final` 事件

**里程碑 M3 通过标准**：`query_app.invoke({"session_id":"s1","original_query":"HAK180 的电源故障怎么排查？","is_stream":False})` 能拿到有依据的答案。

---

## M4 · Web 化（步骤 20–21）

### 步骤 20 · 导入 Web 服务（8000 端口）
**做什么**
- `POST /upload`：多文件上传 → `uuid4()` 生成 `task_id` → 存到 `output/YYYYMMDD/<task_id>/` → `BackgroundTasks` 跑 `kb_import_app` → 立即返回 `task_ids`
- `GET /status/{task_id}`：从内存任务列表读节点进度（`add_running_task` / `add_done_task` 写入）
- `GET /import.html`：上传页 + 定时轮询进度
- 任务状态机：`pending → processing → completed / failed`

**验收**：浏览器上传一个 PDF，页面能看到 7 个节点逐个变"完成"；完成后 Attu 里能看到数据。

---

### 步骤 21 · 检索 Web 服务（8001 端口，SSE 流式）
**做什么**
- `app/utils/sse_utils.py`：会话级 `asyncio.Queue`（`{session_id: Queue}`）、`SSEEvent` 枚举、`sse_generator`
- `POST /query`（`QueryRequest` Pydantic 模型）→ 建队列 → `BackgroundTasks` 跑 `query_app` → 返回 `session_id`
- `GET /stream/{session_id}` → `StreamingResponse(media_type="text/event-stream")`，按 `data: xxx\n\n` 推送；`None` 作结束标记
- `GET /history/{session_id}`（limit 默认 50）、`DELETE /history/{session_id}`、`GET /chat.html`、`GET /health`
- 响应头带 `Cache-Control: no-cache`、`X-Accel-Buffering: no`
- `main_query_web.py` 用 uvicorn 启动，**Windows 下加 asyncio 事件循环兼容补丁**

**验收**：`chat.html` 里提问，答案**逐字出现**；刷新页面后历史仍在（Mongo 生效）。

---

## M5 · 联调（步骤 22）

### 端到端验收清单
1. 新 PDF → 导入服务 → `kb_chunks` / `kb_item_names` 均有数据
2. 同 PDF 再导入一次 → 记录数不翻倍（幂等 OK）
3. 提问命中库内知识 → 答案有依据、带图片
4. 提问库外知识 → 走 MCP 联网或明确拒答，不编造
5. 模糊型号提问 → 出现反问让用户选
6. 连续多轮对话 → 指代（"它的重量呢"）能被正确改写

### 高频报错速查

| 现象 | 首要怀疑 |
| --- | --- |
| `ModuleNotFoundError: app` | 没标记 Sources Root，或缺 `__init__.py` |
| 配置项是 `None` | 该模块没 `load_dotenv()`，或 `.env` 变量名拼错 |
| `model not found` | `.env` 里模型 id 写错（去百炼模型广场核对） |
| `403 SignatureDoesNotMatch`（MinerU） | 代理污染，`requests.Session().trust_env = False` |
| Milvus 报 schema/向量字段错 | `pymilvus` 版本与 2.4.11 服务端不匹配 → 降级 |
| sparse_vector 序列化报错 | `np.int64`/`np.float32` 没转原生类型 |
| `hybrid_search` 结果为空 | `expr` 里的商品名没转义，或 `item_name` 过滤把结果全滤掉了 |
| 图片 404 | MinIO 桶没设公网只读策略，或 `endpoint` 少了协议前缀 |
| SSE 不流式（一次性全出） | 中间有同步阻塞 / `time.sleep` / 缺 `X-Accel-Buffering` |
| LangGraph 报状态字段缺失 | 节点 `return` 的 key 不在 `TypedDict` 里 |

---

## 附一：建议的落地节奏

| 天 | 内容 | 理由 |
| --- | --- | --- |
| D1 | 步骤 1–5 | 地基不牢，后面每一步都会怀疑人生 |
| D2–D3 | 步骤 6–13 | 导入链路是主线，节点②③最耗时 |
| D4–D5 | 步骤 14–19 | 检索链路，节点①（商品名对齐）最烧脑 |
| D6 | 步骤 20–21 | Web 化，纯工程活 |
| D7 | 步骤 22 | 联调与排错 |

> 复现时**不要在节点内部一次写全**：每个节点都先按「输入→处理→输出」三段写清注释，再填代码，再单文件 `__main__` 测。这是参考教案本身的节奏，也是唯一能让你不被 5507 行代码淹死的办法。

---

## 附二：命名与来源说明

- **本项目名**：以 RAG 为核心的内部知识库管理（个人开发 Demo）
- **关系**：本项目在**架构与流程**上参考课程教案复现，但作为个人 Demo 独立命名、独立演进。凡本文档中提到"参考教案 / 参考项目"处，均指课程示例，不代表本项目沿用其名称。
- **对外表述建议**：项目描述、README、简历中统一使用「以 RAG 为核心的内部知识库管理」，可注明"参考主流 RAG 工程实践 / 开源课程示例实现"。
