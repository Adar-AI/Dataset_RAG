# Dataset_RAG

以 RAG 为核心的内部知识库管理与问答系统（个人开发 Demo）。

- **导入流水线**：MinerU 解析 PDF 手册 → 切块 → `bge-m3` 生成稠密 + 稀疏向量 → 写入 Milvus；原文件/图片放 MinIO，元数据放 MongoDB。
- **检索流水线**：多路召回（稠密 + 稀疏）→ `bge-reranker-large` 精排 → 由 LangGraph 编排的节点图生成带引用的回答。
- **两个服务**：`main_import_web.py`（导入）与 `main_query_web.py`（查询），FastAPI + Uvicorn。

## 技术栈

| 层 | 组件 |
| --- | --- |
| 编排 | LangChain、LangGraph |
| 向量库 | Milvus（稠密 + 稀疏混合检索） |
| 对象存储 | MinIO |
| 文档库 | MongoDB |
| 模型 | `BAAI/bge-m3`（稠密 1024 维 + 稀疏）、`BAAI/bge-reranker-large`（精排）、百炼 qwen 系（LLM / VL 多模态） |
| 文档解析 | MinerU（magic-pdf） |
| 服务 | FastAPI + Uvicorn、Loguru |

## 目录结构

```
Dataset_RAG/
├── app/
│   ├── core/  conf/  lm/  clients/  utils/  tool/
│   ├── import_process/agent/{state.py, main_graph.py, nodes/}
│   └── query_process/agent/{state.py, main_graph.py, nodes/}
├── main_import_web.py        # 导入服务入口
├── main_query_web.py         # 查询服务入口
├── prompts/                  # 提示词模板
├── test/                     # 手工验证脚本
├── doc/                      # 知识库源文档（PDF，未纳入版本库）
├── output/                   # 运行产物（未纳入版本库）
└── pyproject.toml / uv.lock
```

## 环境准备

需要 Python ≥ 3.11，依赖用 [uv](https://docs.astral.sh/uv/) 管理：

```bash
uv sync
```

### 1. 配置文件

仓库**不包含** `.env`（已被 `.gitignore` 排除）。请自行创建 `.env`，至少覆盖以下几类变量：

| 类别 | 变量 |
| --- | --- |
| 路径 | `MD_ROOT_DIR`、`MODELSCOPE_CACHE`、`HF_HOME`、`BGE_M3_PATH`、`BGE_RERANKER_LARGE` |
| 大模型 | `OPENAI_API_KEY`、`OPENAI_BASE_URL`、`LLM_DEFAULT_MODEL`、`VL_MODEL`、`LLM_DEFAULT_TEMPERATURE` |
| MCP 联网搜索 | `MCP_DASHSCOPE_BASE_URL`、`MCP_API_KEY` |
| 向量检索 | `MILVUS_URL`、`CHUNKS_COLLECTION`、`ITEM_NAME_COLLECTION`、`ENTITY_NAME_COLLECTION`、`EMBEDDING_DIM` |
| 文档库 | `MONGO_URL`、`MONGO_DB_NAME` |
| 对象存储 | `MINIO_ENDPOINT`、`MINIO_ACCESS_KEY`、`MINIO_SECRET_KEY`、`MINIO_BUCKET_NAME`、`MINIO_IMG_DIR`、`MINIO_SECURE` |
| 文档解析 | `MINERU_API_TOKEN`、`MINERU_BASE_URL` |
| 嵌入与精排设备 | `BGE_DEVICE`、`BGE_FP16`、`BGE_RERANKER_DEVICE`、`BGE_RERANKER_FP16` |
| 日志 | `LOG_CONSOLE_ENABLE`、`LOG_CONSOLE_LEVEL`、`LOG_FILE_ENABLE`、`LOG_FILE_LEVEL`、`LOG_FILE_RETENTION` |

### 2. 外部服务

| 服务 | 端口 | 用途 |
| --- | --- | --- |
| Milvus 单机版 | 19530 | 向量库（含稠密与稀疏向量） |
| MinIO | 9000 / 9001 | 原始文档与图片 |
| MongoDB | 27017 | 文档元数据 |

### 3. 本地模型

- `BAAI/bge-m3` → 稠密 1024 维 + 稀疏向量
- `BAAI/bge-reranker-large` → 精排

用 modelscope 下载到本地后，把路径写入 `.env` 的 `BGE_M3_PATH` 与 `BGE_RERANKER_LARGE`。

### 4. 知识库源文档

`doc/` 存放用于导入的 PDF 手册，因体积与版权原因**未纳入版本库**，需要自行放入。

## 运行

```bash
python main_import_web.py     # 导入服务
python main_query_web.py      # 查询服务
```

## 文档

| 文件 | 内容 |
| --- | --- |
| [以RAG为核心的内部知识库管理_开发工作流.md](以RAG为核心的内部知识库管理_开发工作流.md) | 完整开发路线图：环境搭建、模块划分、7 个节点、每步验收标准 |
| [开发验收记录.md](开发验收记录.md) | 各模块的验收记录 |
| [项目要总结内容.txt](项目要总结内容.txt) | 待总结的知识要点清单 |

## 测试

`test/` 下是**手工验证脚本**，不是自动化测试套件；需要上述外部服务与本地模型全部就绪后才能运行：

```bash
python test/04-test_graph_flow.py
python test/05-test-main-graph.py
```
