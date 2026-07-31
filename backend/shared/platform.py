"""
AgentMatrix 平台路径管理
处理 PyInstaller 打包环境中的 sys._MEIPASS 和 %APPDATA%/AgentMatrix/ 路径
"""
import os
import sys
import logging

logger = logging.getLogger(__name__)

PLATFORM_NAME = "AgentMatrix"
PLATFORM_DESCRIPTION = "多智能体动态协同与国产算力优化平台"

PLATFORM_IDENTITY = f"""
你是 {PLATFORM_NAME} 平台的 AI 助手——一个{PLATFORM_DESCRIPTION}。
核心原理：简单任务由本地轻量模型(qwen2.5)处理，复杂任务动态调用云端大模型(DeepSeek)增强。
你的回答永远不代表任何其他公司或平台的AI助手，你只属于 {PLATFORM_NAME} 平台。
当用户问"你是谁"或类似问题时，你应该直接回答"我是 {PLATFORM_NAME} 平台的 AI 助手"，而不是说"用户来自 {PLATFORM_NAME} 平台"。
"""


# ── 环境检测 ──

def is_packaged() -> bool:
    """检测是否在 PyInstaller 打包环境中运行"""
    return getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS')


def _get_appdata_dir() -> str:
    """获取 %APPDATA%/AgentMatrix/ 路径（可写数据目录）"""
    appdata = os.environ.get('APPDATA', os.path.expanduser('~'))
    path = os.path.join(appdata, 'AgentMatrix')
    os.makedirs(path, exist_ok=True)
    return path


def _get_meipass_dir() -> str:
    """获取 sys._MEIPASS 路径（只读资源目录）"""
    return sys._MEIPASS


def _get_dev_root() -> str:
    """开发环境下获取 backend 根目录"""
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# ── 路径 API ──

def get_resource_dir() -> str:
    """
    获取只读资源根目录。
    打包环境: sys._MEIPASS
    开发环境: backend/
    """
    if is_packaged():
        return _get_meipass_dir()
    return _get_dev_root()


def get_data_dir() -> str:
    """
    获取可写数据根目录。
    打包环境: %APPDATA%/AgentMatrix/
    开发环境: backend/
    """
    if is_packaged():
        return _get_appdata_dir()
    return _get_dev_root()


def get_prompts_dir() -> str:
    """获取 prompts 目录路径"""
    return os.path.join(get_resource_dir(), 'prompts')


def get_configs_dir() -> str:
    """获取 configs 目录路径"""
    return os.path.join(get_resource_dir(), 'configs')


def get_logs_dir() -> str:
    """获取日志目录路径（可写）"""
    path = os.path.join(get_data_dir(), 'logs')
    os.makedirs(path, exist_ok=True)
    return path


def get_config_file_path() -> str:
    """
    获取运行时配置文件路径（可写）。
    打包环境: %APPDATA%/AgentMatrix/config/app_config.json
    开发环境: backend/config/app_config.json
    """
    config_dir = os.path.join(get_data_dir(), 'config')
    os.makedirs(config_dir, exist_ok=True)
    return os.path.join(config_dir, 'app_config.json')


def get_storage_dir() -> str:
    """获取 storage 目录路径（可写）"""
    path = os.path.join(get_data_dir(), 'storage')
    os.makedirs(path, exist_ok=True)
    return path


def get_db_path() -> str:
    """
    获取全局数据库文件路径（可写）。
    打包环境: %APPDATA%/AgentMatrix/storage/agentmatrix.db
    开发环境: backend/storage/agentmatrix.db
    """
    return os.path.join(get_storage_dir(), 'agentmatrix.db')


def get_sandbox_db_path(sandbox_id: str) -> str:
    """获取沙盒数据库文件路径"""
    sandbox_dir = os.path.join(get_storage_dir(), 'sandboxes')
    os.makedirs(sandbox_dir, exist_ok=True)
    return os.path.join(sandbox_dir, f'{sandbox_id}.db')


def get_profiles_dir() -> str:
    """获取用户画像目录路径"""
    path = os.path.join(get_storage_dir(), 'profiles')
    os.makedirs(path, exist_ok=True)
    return path


def get_memory_dir() -> str:
    """获取长期记忆目录路径"""
    path = os.path.join(get_storage_dir(), 'memory')
    os.makedirs(path, exist_ok=True)
    return path


def get_backups_dir() -> str:
    """获取自动备份目录路径"""
    path = os.path.join(get_storage_dir(), 'backups')
    os.makedirs(path, exist_ok=True)
    return path


def get_log_file_path() -> str:
    """获取日志文件路径（可写）"""
    return os.path.join(get_logs_dir(), 'system.log')


def get_env_file_path() -> str:
    """
    获取 .env 文件路径。
    打包环境: %APPDATA%/AgentMatrix/.env
    开发环境: backend/.env
    """
    return os.path.join(get_data_dir(), '.env')


def initialize_app_dirs() -> None:
    """初始化所有应用目录（首次运行时调用）"""
    dirs = [
        get_logs_dir(),
        os.path.join(get_data_dir(), 'config'),
    ]
    for d in dirs:
        os.makedirs(d, exist_ok=True)
    logger.info(f"App data dir: {get_data_dir()}")
    if is_packaged():
        logger.info(f"Resource dir (MEIPASS): {get_resource_dir()}")