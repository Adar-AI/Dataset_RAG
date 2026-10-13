from pathlib import Path

from app.core.logger import logger
from app.import_process.agent.main_graph import kb_import_app
from app.import_process.agent.state import create_default_state
from app.utils.path_util import PROJECT_ROOT


TEST_PDF_NAME = "hak180产品安全手册.pdf"


def build_initial_state():
    """构造不依赖当前工作目录的测试状态。"""
    pdf_path = (PROJECT_ROOT / "doc" / TEST_PDF_NAME).resolve()
    output_dir = (PROJECT_ROOT / "output").resolve()

    if not pdf_path.is_file():
        raise FileNotFoundError(f"测试 PDF 不存在：{pdf_path}")

    output_dir.mkdir(parents=True, exist_ok=True)
    return create_default_state(
        task_id="test_import_main_graph_001",
        local_file_path=str(pdf_path),
        local_dir=str(output_dir),
    )


def main():
    logger.info("===== 开始测试 =====")
    initial_state = build_initial_state()
    logger.info(f"测试 PDF：{initial_state['local_file_path']}")
    logger.info(f"输出目录：{initial_state['local_dir']}")

    # invoke 返回完整的最终状态；避免把体积很大的向量内容全部打印到控制台。
    final_state = kb_import_app.invoke(initial_state)
    chunks = final_state.get("chunks") or []
    vectorized_chunks = sum(1 for chunk in chunks if chunk.get("dense_vector"))

    logger.info(
        f"测试完成：item_name={final_state.get('item_name', '')}, "
        f"chunks={len(chunks)}, vectorized_chunks={vectorized_chunks}, "
        f"md_path={final_state.get('md_path', '')}"
    )

    logger.info("图结构:")
    kb_import_app.get_graph().print_ascii()
    logger.info("===== 测试结束 =====")
    return final_state


if __name__ == "__main__":
    main()


