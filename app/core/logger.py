"""
项目日志工具类
基于loguru实现，支持.env配置控制台/文件双输出，自动生成logs/app_年月日.log
特性：
1. 配置驱动：通过.env开关输出、修改日志级别
2. 自动路径：文件日志默认输出到 项目根/logs/app_YYYYMMDD.log
3. 自动清理：按配置保留日志，自动删除过期文件
4. 中文友好：utf-8编码，彻底解决中文乱码
5. 异步安全：开启异步入队，支持多线程/异步场景，避免日志错乱
6. 开箱即用：项目所有模块直接导入logger即可使用
7. 位置终极精准：穿透loguru内部+工具类自身，完美显示业务模块实际调用位置
"""
import sys
import inspect
from pathlib import Path
import os
from dotenv import load_dotenv
from loguru import logger


# -------------------------- 第一步：加载.env配置文件 --------------------------
load_dotenv()

# -------------------------- 第二步：读取.env配置（带默认值，防止配置缺失） --------------------------
LOG_CONSOLE_ENABLE = os.getenv("LOG_CONSOLE_ENABLE", "True").lower() == "true"
LOG_CONSOLE_LEVEL = os.getenv("LOG_CONSOLE_LEVEL", "INFO").upper()
LOG_FILE_ENABLE = os.getenv("LOG_FILE_ENABLE", "True").lower() == "true"
LOG_FILE_LEVEL = os.getenv("LOG_FILE_LEVEL", "INFO").upper()
LOG_FILE_RETENTION = os.getenv("LOG_FILE_RETENTION", "7 days")
# 异步写入开关：默认 True，保持原有行为不变。
# 注意：enqueue=True 依赖 multiprocessing 队列（Windows 下即命名管道）。
# 在受限沙箱/无法创建命名管道的宿主环境中会抛 PermissionError，此时自动降级为同步写入，
# 保证日志永远可用（关掉排队只影响吞吐，不影响功能与格式）。
LOG_ENQUEUE = os.getenv("LOG_ENQUEUE", "True").lower() == "true"
# 运行期降级状态：一旦确认宿主无法创建命名管道，后续 sink 一律同步写入
_ENQUEUE_AVAILABLE = [True]

# -------------------------- 第三步：定义日志路径（自动推导项目根） --------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
LOG_DIR = PROJECT_ROOT / "logs"
LOG_FILE_NAME = "app_{time:YYYYMMDD}.log"
LOG_FILE_PATH = LOG_DIR / LOG_FILE_NAME

# -------------------------- 第四步：定义日志格式（彩色、结构化、易读） --------------------------
LOG_FORMAT = (
    "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
    "<level>{level: <8}</level> | "
    "<cyan>{name: <20}</cyan>:<cyan>{function: <15}</cyan>:<cyan>{line: <4}</cyan> - "
    "<level>{message}</level>"
)

# -------------------------- 第五步：初始化日志配置（核心方法） --------------------------
def add_sink_safely(**kwargs):
    """
    统一的安全加 sink 入口：优先按 LOG_ENQUEUE 异步写入，
    若宿主环境不允许创建命名管道（受限沙箱等），自动降级为同步写入。
    保证「日志功能永远可用」，只牺牲排队吞吐，不影响格式/级别/切割。
    """
    if LOG_ENQUEUE and _ENQUEUE_AVAILABLE[0]:
        handler_id = None
        try:
            handler_id = logger.add(enqueue=True, **kwargs)
            return handler_id
        except (PermissionError, OSError) as e:
            _ENQUEUE_AVAILABLE[0] = False
            # 只回收本次这个可能半注册的 sink，不影响已经加好的 sink
            if handler_id is not None:
                logger.remove(handler_id)
            try:
                print(f"[logger] enqueue=True 不可用（{type(e).__name__}），已自动降级为同步写入",
                      file=sys.stderr)
            except Exception:
                pass
    return logger.add(enqueue=False, **kwargs)


def init_logger():
    """
    初始化全局日志配置
    1. 移除loguru默认控制台输出（避免重复打印）
    2. 根据.env配置开启/关闭控制台输出
    3. 根据.env配置开启/关闭文件输出（自动创建logs文件夹）
    4. 配置日志格式、级别、分割、保留策略
    :return: 配置完成的loguru logger实例
    """
    # 1. 移除loguru默认的控制台输出
    logger.remove()

    # 2. 配置控制台输出（若.env开启）
    if LOG_CONSOLE_ENABLE:
        add_sink_safely(
            sink=sys.stdout,
            level=LOG_CONSOLE_LEVEL,
            format=LOG_FORMAT,
            colorize=True
        )

    # 3. 配置文件输出（若.env开启）
    if LOG_FILE_ENABLE:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        add_sink_safely(
            sink=LOG_FILE_PATH,
            level=LOG_FILE_LEVEL,
            format=LOG_FORMAT,
            rotation="00:00",
            retention=LOG_FILE_RETENTION,
            encoding="utf-8",
            backtrace=True,
            diagnose=True
        )

    return logger

# -------------------------- 第六步：初始化并终极修正全局logger --------------------------
base_logger = init_logger()

def fix_log_position(record):
    """遍历调用栈，跳过loguru内部帧+工具类自身帧，提取业务代码实际调用位置"""
    for frame in inspect.stack():
        # 终极过滤：排除loguru内部 + 排除工具类logger.py自身，直接定位业务模块
        if ("_logger.py" in frame.filename or frame.function == "_log") or "logger.py" in frame.filename:
            continue
        # 更新日志字段为业务代码实际位置
        record.update(
            name=frame.filename.split("/")[-1].split("\\")[-1],
            function=frame.function,
            line=frame.lineno
        )
        break

# 应用终极修复，导出全局可用的logger
logger = base_logger.patch(fix_log_position)

# -------------------------- 测试代码（验证修复效果） --------------------------
if __name__ == '__main__':
    logger.info("【测试】logger.py内部调用（仅测试，业务模块调用会显示正确文件名）")
    print(f"日志文件输出路径：{LOG_FILE_PATH}")