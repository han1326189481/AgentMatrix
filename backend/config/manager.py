import json
import os
from typing import Dict, Any, Optional

CONFIG_FILE = os.path.join(os.path.dirname(__file__), 'app_config.json')

def load_config() -> Dict[str, Any]:
    """加载配置文件"""
    if not os.path.exists(CONFIG_FILE):
        return {
            "models": [],
            "default_provider": "deepseek",
            "api_keys": {
                "deepseek": "",
                "openai": ""
            }
        }
    
    try:
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"加载配置文件失败: {e}")
        return {
            "models": [],
            "default_provider": "deepseek",
            "api_keys": {
                "deepseek": "",
                "openai": ""
            }
        }

def save_config(config: Dict[str, Any]) -> bool:
    """保存配置到文件"""
    try:
        os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"保存配置文件失败: {e}")
        return False

def get_api_key(provider: str) -> str:
    """获取指定服务商的API Key"""
    config = load_config()
    return config.get("api_keys", {}).get(provider, "")

def set_api_key(provider: str, api_key: str) -> bool:
    """设置指定服务商的API Key"""
    config = load_config()
    if "api_keys" not in config:
        config["api_keys"] = {}
    config["api_keys"][provider] = api_key
    return save_config(config)

def add_model(model_config: Dict[str, Any]) -> bool:
    """添加模型配置"""
    config = load_config()
    if "models" not in config:
        config["models"] = []
    
    # 检查是否已存在
    existing = next((m for m in config["models"] if m.get("name") == model_config.get("name")), None)
    if existing:
        # 更新现有配置
        existing.update(model_config)
    else:
        config["models"].append(model_config)
    
    return save_config(config)

def get_models() -> list:
    """获取所有模型配置"""
    config = load_config()
    return config.get("models", [])

def remove_model(model_name: str) -> bool:
    """删除模型配置"""
    config = load_config()
    config["models"] = [m for m in config.get("models", []) if m.get("name") != model_name]
    return save_config(config)