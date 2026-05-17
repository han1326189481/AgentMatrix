from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict, Optional, List
import httpx
import asyncio
from core.llm.client import get_llm_client

# 导入配置管理器
from config.manager import load_config, save_config, get_api_key, set_api_key, add_model, get_models, remove_model

router = APIRouter()

class ConfigUpdate(BaseModel):
    deepseek_api_key: Optional[str] = None
    ollama_host: Optional[str] = None

class ConnectionTestResult(BaseModel):
    success: bool
    message: str
    details: Dict[str, str] = {}

class ModelConfig(BaseModel):
    name: str
    provider: str
    model: str
    api_key: Optional[str] = None
    display_name: Optional[str] = None
    max_tokens: int = 2048
    temperature: float = 0.7

# 存储运行时配置
_runtime_config = {
    "ollama_host": None,
    "deepseek_api_key": None
}

# 初始化时加载配置
_config = load_config()
_runtime_config["deepseek_api_key"] = _config.get("api_keys", {}).get("deepseek", "")

@router.get("/")
async def get_config():
    """获取当前配置"""
    client = get_llm_client()
    ollama_host = _runtime_config["ollama_host"] or client.ollama_host
    
    # 加载配置文件
    config = load_config()
    
    return {
        "ollama_host": ollama_host,
        "ollama_model": client.ollama_model,
        "deepseek_api_key_set": bool(_runtime_config["deepseek_api_key"] or client.deepseek_api_key),
        "deepseek_model": client.deepseek_model,
        "models": get_models()
    }

@router.post("/")
async def update_config(config: ConfigUpdate):
    """更新配置"""
    client = get_llm_client()
    
    if config.deepseek_api_key is not None:
        _runtime_config["deepseek_api_key"] = config.deepseek_api_key
        client.deepseek_api_key = config.deepseek_api_key
        
        # 保存到配置文件
        set_api_key("deepseek", config.deepseek_api_key)
    
    if config.ollama_host is not None:
        _runtime_config["ollama_host"] = config.ollama_host
        client.dynamic_ollama_host = config.ollama_host
    
    return {"message": "配置更新成功", "saved": True}

@router.get("/models")
async def list_models():
    """获取所有模型配置"""
    return {"models": get_models()}

@router.post("/models")
async def create_model(model: ModelConfig):
    """添加或更新模型配置"""
    model_dict = model.dict()
    
    # 保存到配置文件
    success = add_model(model_dict)
    
    if success:
        return {"message": "模型配置保存成功", "model": model_dict}
    else:
        raise HTTPException(status_code=500, detail="保存模型配置失败")

@router.delete("/models/{model_name}")
async def delete_model(model_name: str):
    """删除模型配置"""
    success = remove_model(model_name)
    
    if success:
        return {"message": "模型删除成功"}
    else:
        raise HTTPException(status_code=404, detail="模型不存在")

class ValidateKeyRequest(BaseModel):
    provider: str
    api_key: str
    model: str = "deepseek-chat"

@router.post("/validate-key")
async def validate_api_key(request: ValidateKeyRequest):
    """验证API密钥是否有效"""
    import logging
    logger = logging.getLogger(__name__)
    
    if not request.provider or not request.api_key:
        return {"success": False, "message": "服务商和API密钥不能为空"}
    
    logger.info(f"[密钥验证] provider={request.provider}, key_length={len(request.api_key)}")
    
    url = "https://api.deepseek.com/v1/chat/completions"
    if request.provider == "openai":
        url = "https://api.openai.com/v1/chat/completions"
    
    payload = {
        "model": request.model,
        "messages": [{"role": "user", "content": "test"}],
        "max_tokens": 5
    }
    headers = {
        "Authorization": f"Bearer {request.api_key}",
        "Content-Type": "application/json"
    }
    
    try:
        async with httpx.AsyncClient(timeout=15.0) as http_client:
            response = await http_client.post(url, json=payload, headers=headers)
            
            if response.status_code == 200:
                logger.info("[密钥验证] API密钥验证成功")
                return {"success": True, "message": "API密钥验证成功"}
            elif response.status_code == 401:
                logger.error("[密钥验证] API密钥无效")
                return {"success": False, "message": "API密钥无效，请检查密钥是否正确"}
            elif response.status_code == 403:
                logger.error("[密钥验证] API密钥无权限")
                return {"success": False, "message": "API密钥无权限访问该模型"}
            else:
                error_text = response.text[:200]
                logger.error(f"[密钥验证] 错误: {response.status_code} - {error_text}")
                return {"success": False, "message": f"验证失败: {response.status_code}"}
    except Exception as e:
        logger.error(f"[密钥验证] 调用异常: {e}")
        return {"success": False, "message": f"验证失败: {str(e)}"}

async def _check_ollama_port(host: str) -> bool:
    """检查指定端口是否有Ollama服务"""
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            response = await client.get(f"{host}/api/tags")
            return response.status_code == 200
    except:
        return False

class DetectOllamaRequest(BaseModel):
    host: Optional[str] = None
    port: Optional[str] = None

@router.post("/detect-ollama")
async def detect_ollama(request: DetectOllamaRequest = DetectOllamaRequest()):
    """自动检测Ollama服务端口"""
    client = get_llm_client()
    
    # 如果用户指定了端口，优先使用
    if request.host or request.port:
        # 构建用户指定的host
        if request.host:
            # 如果用户提供的host已经是完整URL，直接使用
            if request.host.startswith("http://") or request.host.startswith("https://"):
                test_host = request.host
            else:
                # 否则，组合host和port
                port = request.port or "11434"
                test_host = f"http://{request.host}:{port}"
        elif request.port:
            # 只提供了port
            test_host = f"http://localhost:{request.port}"
        
        # 测试用户指定的host
        if await _check_ollama_port(test_host):
            _runtime_config["ollama_host"] = test_host
            client.dynamic_ollama_host = test_host
            return {
                "ollama_host": test_host,
                "message": f"检测到 Ollama 服务: {test_host}"
            }
        else:
            return {
                "ollama_host": test_host,
                "message": f"未检测到 Ollama 服务在 {test_host}，请检查地址和端口是否正确"
            }
    
    # 常见的Ollama端口列表
    ports_to_check = [
        "http://localhost:11434",
        "http://localhost:11435", 
        "http://localhost:11436",
        "http://localhost:8080",
        "http://localhost:8000",
    ]
    
    # 检查当前配置的host
    current_host = _runtime_config["ollama_host"] or client.ollama_host
    if current_host and await _check_ollama_port(current_host):
        return {
            "ollama_host": current_host,
            "message": f"检测到 Ollama 服务: {current_host}（当前配置）"
        }
    
    # 依次检查其他端口
    for host in ports_to_check:
        if host == current_host:
            continue
        if await _check_ollama_port(host):
            _runtime_config["ollama_host"] = host
            client.dynamic_ollama_host = host
            return {
                "ollama_host": host,
                "message": f"检测到 Ollama 服务: {host}"
            }
    
    # 如果都没找到，返回默认值
    default_host = "http://localhost:11434"
    return {
        "ollama_host": default_host,
        "message": "未检测到 Ollama 服务，请手动配置"
    }

class TestOllamaRequest(BaseModel):
    host: Optional[str] = None
    port: Optional[str] = None

@router.post("/test-ollama")
async def test_ollama_connection(request: TestOllamaRequest = TestOllamaRequest()):
    """测试Ollama连接"""
    client = get_llm_client()
    
    # 如果用户指定了host/port，先更新配置
    if request.host or request.port:
        if request.host:
            if request.host.startswith("http://") or request.host.startswith("https://"):
                test_host = request.host
            else:
                port = request.port or "11434"
                test_host = f"http://{request.host}:{port}"
        elif request.port:
            test_host = f"http://localhost:{request.port}"
        else:
            test_host = None
        
        if test_host:
            _runtime_config["ollama_host"] = test_host
            client.dynamic_ollama_host = test_host
    
    try:
        # 使用实际的LLM客户端来测试连接
        result = await client.generate_local("Hello", model="qwen2.5:1.5b")
        if "Error" in result:
            return ConnectionTestResult(
                success=False,
                message="Ollama 连接失败",
                details={"error": result}
            )
        return ConnectionTestResult(
            success=True,
            message="Ollama 连接成功",
            details={"response": result[:30] + "..." if len(result) > 30 else result}
        )
    except Exception as e:
        return ConnectionTestResult(
            success=False,
            message="Ollama 连接失败",
            details={"error": str(e)}
        )

@router.post("/test-deepseek")
async def test_deepseek_connection():
    """测试DeepSeek连接"""
    import logging
    logger = logging.getLogger(__name__)
    
    client = get_llm_client()
    
    # 优先使用运行时配置
    api_key = _runtime_config.get("deepseek_api_key") or client.deepseek_api_key
    
    logger.info(f"[测试DeepSeek] API Key 长度: {len(api_key) if api_key else 0}")
    
    if not api_key:
        logger.error("[测试DeepSeek] API Key 未设置")
        return ConnectionTestResult(
            success=False,
            message="DeepSeek API Key 未设置",
            details={"error": "请先在设置中输入并保存 API Key"}
        )
    
    # 检查 API Key 格式
    if not api_key.startswith("sk-"):
        logger.warning(f"[测试DeepSeek] API Key 格式可能不正确，不以 sk- 开头")
        return ConnectionTestResult(
            success=False,
            message="API Key 格式可能不正确",
            details={"error": "DeepSeek API Key 应该以 'sk-' 开头，请检查您的 Key"}
        )
    
    logger.info("[测试DeepSeek] 开始调用 DeepSeek API...")
    
    # 直接使用 httpx 调用，不经过 client 的 generate_cloud 方法
    url = "https://api.deepseek.com/v1/chat/completions"
    payload = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "user", "content": "Hi"}
        ],
        "max_tokens": 10
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as http_client:
            logger.info(f"[测试DeepSeek] 发送请求到: {url}")
            response = await http_client.post(url, json=payload, headers=headers)
            
            logger.info(f"[测试DeepSeek] 响应状态码: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                logger.info(f"[测试DeepSeek] API 调用成功")
                response_text = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                return ConnectionTestResult(
                    success=True,
                    message="DeepSeek 连接成功",
                    details={"response": response_text[:100] if response_text else "成功"}
                )
            else:
                error_text = response.text
                logger.error(f"[测试DeepSeek] API 调用失败: {response.status_code} - {error_text}")
                return ConnectionTestResult(
                    success=False,
                    message=f"DeepSeek 连接失败 (状态码: {response.status_code})",
                    details={"error": error_text}
                )
    except Exception as e:
        logger.error(f"[测试DeepSeek] 调用异常: {e}", exc_info=True)
        return ConnectionTestResult(
            success=False,
            message=f"DeepSeek 连接失败",
            details={"error": str(e)}
        )