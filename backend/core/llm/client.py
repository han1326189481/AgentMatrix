from typing import Dict, Any, Optional
import aiohttp
import logging
from app.config import settings

try:
    from config.manager import load_config
except ImportError:
    def load_config():
        return {"models": [], "api_keys": {}}

logger = logging.getLogger(__name__)


class LLMClient:
    # DeepSeek 定价（元/百万token）
    DEEPSEEK_INPUT_PRICE = 1.0    # ¥1 / 百万输入 token
    DEEPSEEK_OUTPUT_PRICE = 4.0   # ¥4 / 百万输出 token

    def __init__(self):
        self.ollama_host = settings.ollama_host
        self.ollama_model = settings.ollama_model
        self.gemini_api_key = settings.gemini_api_key
        self.gemini_model = settings.gemini_model
        self.deepseek_api_key = getattr(settings, 'deepseek_api_key', '')
        self.deepseek_api_base = getattr(settings, 'deepseek_api_base', 'https://api.deepseek.com/v1')
        self.deepseek_model = getattr(settings, 'deepseek_model', 'deepseek-v4-pro')
        self.dynamic_ollama_host = None

        # V4.1: Token 侧信道 — 累积每次调用的 token 消耗，供 CostTracker 消费
        self._local_tokens = {"input": 0, "output": 0, "calls": 0}
        self._cloud_tokens = {"input": 0, "output": 0, "calls": 0}

    async def generate_local(self, prompt: str, system_prompt: str = None, model: str = None) -> str:
        host = self.dynamic_ollama_host or self.ollama_host
        url = f"{host}/api/generate"
        payload = {
            "model": model or self.ollama_model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "num_ctx": 16384,
                "num_predict": 4096,
                "num_thread": 4
            }
        }
        if system_prompt:
            payload["system"] = system_prompt

        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=180)) as session:
                async with session.post(url, json=payload) as response:
                    if response.status == 200:
                        data = await response.json()
                        # V4.1: 捕获 Ollama token 计数（prompt_eval_count + eval_count）
                        prompt_tokens = data.get("prompt_eval_count", 0)
                        eval_tokens = data.get("eval_count", 0)
                        if prompt_tokens > 0 or eval_tokens > 0:
                            self._local_tokens["input"] += prompt_tokens
                            self._local_tokens["output"] += eval_tokens
                            self._local_tokens["calls"] += 1
                            logger.debug(
                                f"[Ollama] Token: prompt={prompt_tokens}, "
                                f"completion={eval_tokens}, "
                                f"cumulative_local={self._local_tokens}"
                            )
                        return data.get("response", "")
                    else:
                        error_text = await response.text()
                        logger.error(f"Ollama error: {response.status} - {error_text}")
                        return f"Error: {response.status}"
        except Exception as e:
            logger.error(f"Failed to call Ollama: {e}")
            return f"Error: {str(e)}"

    async def generate_local_stream(self, prompt: str, system_prompt: str = None, model: str = None):
        """流式调用 Ollama"""
        host = self.dynamic_ollama_host or self.ollama_host
        url = f"{host}/api/generate"
        payload = {
            "model": model or self.ollama_model,
            "prompt": prompt,
            "stream": True,
            "options": {
                "num_ctx": 16384,
                "num_predict": 4096,
                "num_thread": 4,
                "temperature": 0.3
            }
        }
        if system_prompt:
            payload["system"] = system_prompt

        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=120)) as session:
                async with session.post(url, json=payload) as response:
                    if response.status == 200:
                        async for line in response.content:
                            if line:
                                try:
                                    data = line.decode('utf-8').strip()
                                    if data:
                                        import json
                                        json_data = json.loads(data)
                                        response_text = json_data.get("response", "")
                                        done = json_data.get("done", False)
                                        if response_text:
                                            yield response_text
                                        if done:
                                            break
                                except:
                                    continue
                    else:
                        error_text = await response.text()
                        logger.error(f"Ollama streaming error: {response.status} - {error_text}")
                        yield f"Error: {response.status}"
        except Exception as e:
            logger.error(f"Failed to call Ollama stream: {e}")
            yield f"Error: {str(e)}"

    async def generate_cloud(self, prompt: str, system_prompt: str = None, model: str = None) -> str:
        # 优先检查用户配置的模型
        try:
            user_config = load_config()
            user_models = user_config.get("models", [])
            
            if user_models:
                # 如果指定了 model 名称，尝试匹配用户配置的模型
                if model:
                    for m in user_models:
                        if m.get("name") == model or m.get("model") == model:
                            # .env 中的 key 优先级高于用户配置
                            if self.deepseek_api_key:
                                m = dict(m)  # 不修改原始配置
                                m["api_key"] = self.deepseek_api_key
                            logger.info(f"[Cloud] 使用用户配置的模型: {m['name']} (provider={m.get('provider')})")
                            return await self.generate_by_config(prompt, m, system_prompt)
                
                # 没有指定 model 或没匹配到，使用第一个用户配置的模型
                first_model = dict(user_models[0])
                # .env 中的 key 优先级高于用户配置
                if self.deepseek_api_key:
                    first_model["api_key"] = self.deepseek_api_key
                logger.info(f"[Cloud] 使用第一个用户配置的模型: {first_model['name']} (provider={first_model.get('provider')})")
                return await self.generate_by_config(prompt, first_model, system_prompt)
        except Exception as e:
            logger.warning(f"[Cloud] 读取用户配置失败，回退到默认 DeepSeek: {e}")
        
        # 回退：使用默认的 DeepSeek 配置
        if not self.deepseek_api_key:
            logger.error("DeepSeek API key not set")
            return "Error: DeepSeek API Key 未设置"

        url = "https://api.deepseek.com/v1/chat/completions"
        
        logger.info(f"[DeepSeek] API URL: {url}")
        logger.info(f"[DeepSeek] API Key: 已配置 (长度: {len(self.deepseek_api_key)})")

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": model or self.deepseek_model,
            "messages": messages,
            "temperature": 0.7,
            "max_tokens": 4096
        }
        logger.info(f"[DeepSeek] 使用模型: {model or self.deepseek_model}")

        headers = {
            "Authorization": f"Bearer {self.deepseek_api_key}",
            "Content-Type": "application/json"
        }

        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=60)) as session:
                async with session.post(url, json=payload, headers=headers) as response:
                    logger.info(f"[DeepSeek] Response status: {response.status}")
                    
                    if response.status == 200:
                        data = await response.json()
                        choices = data.get("choices", [])
                        if choices:
                            usage = data.get('usage', {})
                            prompt_tokens = usage.get('prompt_tokens', 0)
                            completion_tokens = usage.get('completion_tokens', 0)
                            total_tokens = usage.get('total_tokens', 0)

                            # V4.1: 累积云端 token 消耗到侧信道
                            if prompt_tokens > 0 or completion_tokens > 0:
                                self._cloud_tokens["input"] += prompt_tokens
                                self._cloud_tokens["output"] += completion_tokens
                                self._cloud_tokens["calls"] += 1
                                cost = (prompt_tokens / 1_000_000) * self.DEEPSEEK_INPUT_PRICE + \
                                       (completion_tokens / 1_000_000) * self.DEEPSEEK_OUTPUT_PRICE
                                logger.info(
                                    f"[DeepSeek] API调用成功 — "
                                    f"prompt: {prompt_tokens}, completion: {completion_tokens}, "
                                    f"total: {total_tokens}, cost: ¥{cost:.6f}"
                                )

                            return choices[0].get("message", {}).get("content", "")
                        logger.warning("[DeepSeek] API返回但没有choices")
                        return ""
                    elif response.status == 401:
                        error_text = await response.text()
                        logger.error(f"[DeepSeek] 认证失败: {error_text}")
                        return f"Error: 401 认证失败，请检查 API Key 是否正确 - {error_text}"
                    elif response.status == 400:
                        error_text = await response.text()
                        logger.error(f"[DeepSeek] 请求错误: {response.status} - {error_text}")
                        return f"Error: 400 请求格式错误 - {error_text}"
                    elif response.status == 404:
                        error_text = await response.text()
                        logger.error(f"[DeepSeek] 404错误: {error_text}")
                        return f"Error: 404 路径不存在 - {error_text}"
                    else:
                        error_text = await response.text()
                        logger.error(f"[DeepSeek] 错误: {response.status} - {error_text}")
                        return f"Error: {response.status} - {error_text}"
        except Exception as e:
            logger.error(f"[DeepSeek] 调用失败: {e}", exc_info=True)
            return f"Error: 调用 DeepSeek 失败 - {str(e)}"

    async def generate_cloud_with_history(
        self,
        messages: list,
        model: str = None,
    ) -> str:
        """V4.2: 云端生成 — 支持多轮对话历史

        用于上下文溢出后切换到云端模型时，传递完整对话历史。
        messages 格式: [{"role": "system"|"user"|"assistant", "content": "..."}]
        """
        if not self.deepseek_api_key:
            logger.error("[CloudHistory] DeepSeek API key not set")
            return "Error: DeepSeek API Key 未设置"

        url = "https://api.deepseek.com/v1/chat/completions"

        payload = {
            "model": model or self.deepseek_model,
            "messages": messages,
            "temperature": 0.7,
            "max_tokens": 4096,
        }
        logger.info(
            f"[CloudHistory] 使用模型: {model or self.deepseek_model}, "
            f"消息数: {len(messages)}"
        )

        headers = {
            "Authorization": f"Bearer {self.deepseek_api_key}",
            "Content-Type": "application/json",
        }

        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=120)) as session:
                async with session.post(url, json=payload, headers=headers) as response:
                    logger.info(f"[CloudHistory] Response status: {response.status}")

                    if response.status == 200:
                        data = await response.json()
                        choices = data.get("choices", [])
                        if choices:
                            usage = data.get("usage", {})
                            prompt_tokens = usage.get("prompt_tokens", 0)
                            completion_tokens = usage.get("completion_tokens", 0)

                            # V4.1: 累积云端 token 消耗
                            if prompt_tokens > 0 or completion_tokens > 0:
                                self._cloud_tokens["input"] += prompt_tokens
                                self._cloud_tokens["output"] += completion_tokens
                                self._cloud_tokens["calls"] += 1
                                cost = (prompt_tokens / 1_000_000) * self.DEEPSEEK_INPUT_PRICE + \
                                       (completion_tokens / 1_000_000) * self.DEEPSEEK_OUTPUT_PRICE
                                logger.info(
                                    f"[CloudHistory] API调用成功 — "
                                    f"prompt: {prompt_tokens}, completion: {completion_tokens}, "
                                    f"cost: ¥{cost:.6f}"
                                )

                            return choices[0].get("message", {}).get("content", "")
                        logger.warning("[CloudHistory] API返回但没有choices")
                        return ""
                    elif response.status == 401:
                        error_text = await response.text()
                        logger.error(f"[CloudHistory] 认证失败: {error_text}")
                        return f"Error: 401 认证失败 - {error_text}"
                    else:
                        error_text = await response.text()
                        logger.error(f"[CloudHistory] 错误: {response.status} - {error_text}")
                        return f"Error: {response.status} - {error_text}"
        except Exception as e:
            logger.error(f"[CloudHistory] 调用失败: {e}", exc_info=True)
            return f"Error: 调用 DeepSeek 失败 - {str(e)}"

    async def generate_by_config(self, prompt: str, model_config: dict, system_prompt: str = None) -> str:
        """使用配置好的模型来生成内容"""
        provider = model_config.get("provider", "deepseek")
        model_name = model_config.get("model", "deepseek-v4-pro")
        api_key = model_config.get("api_key", self.deepseek_api_key)
        temperature = model_config.get("temperature", 0.7)
        max_tokens = model_config.get("max_tokens", 4096)
        
        logger.info(f"[ConfigModel] 使用配置模型: provider={provider}, model={model_name}")
        
        if provider == "ollama":
            return await self.generate_local(prompt, system_prompt, model_name)
        
        # 处理云服务商（DeepSeek/OpenAI等）
        if not api_key:
            logger.error(f"[ConfigModel] API Key未设置 (provider: {provider})")
            return f"Error: {provider} API Key 未设置"
        
        url = self._get_provider_url(provider)
        
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        
        payload = {
            "model": model_name,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens
        }
        
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=60)) as session:
                async with session.post(url, json=payload, headers=headers) as response:
                    logger.info(f"[ConfigModel] Response status: {response.status}")

                    if response.status == 200:
                        data = await response.json()
                        choices = data.get("choices", [])
                        if choices:
                            # V3.1: 记录 Token 消耗（供云端调用成本分析）
                            usage = data.get('usage', {})
                            prompt_tokens = usage.get('prompt_tokens', 0)
                            completion_tokens = usage.get('completion_tokens', 0)
                            total_tokens = usage.get('total_tokens', 0)

                            # V4.1: 累积云端 token 消耗到侧信道
                            if prompt_tokens > 0 or completion_tokens > 0:
                                self._cloud_tokens["input"] += prompt_tokens
                                self._cloud_tokens["output"] += completion_tokens
                                self._cloud_tokens["calls"] += 1

                            if total_tokens > 0:
                                cost = (prompt_tokens / 1_000_000) * self.DEEPSEEK_INPUT_PRICE + \
                                       (completion_tokens / 1_000_000) * self.DEEPSEEK_OUTPUT_PRICE
                                logger.info(
                                    f"[ConfigModel] Token消耗 — "
                                    f"prompt: {prompt_tokens}, "
                                    f"completion: {completion_tokens}, "
                                    f"total: {total_tokens}, cost: ¥{cost:.6f}"
                                )
                            logger.info("[ConfigModel] API调用成功")
                            return choices[0].get("message", {}).get("content", "")
                        return ""
                    else:
                        error_text = await response.text()
                        logger.error(f"[ConfigModel] 错误: {response.status} - {error_text}")
                        return f"Error: {response.status} - {error_text}"
        except Exception as e:
            logger.error(f"[ConfigModel] 调用失败: {e}", exc_info=True)
            return f"Error: 调用失败 - {str(e)}"
    
    def _get_provider_url(self, provider: str) -> str:
        """根据服务商获取API URL"""
        urls = {
            "deepseek": "https://api.deepseek.com/v1/chat/completions",
            "openai": "https://api.openai.com/v1/chat/completions",
            "gemini": "https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent",
            "anthropic": "https://api.anthropic.com/v1/messages"
        }
        return urls.get(provider, "https://api.deepseek.com/v1/chat/completions")

    async def generate(self, prompt: str, use_cloud: bool = False, system_prompt: str = None, model: str = None) -> str:
        if use_cloud:
            return await self.generate_cloud(prompt, system_prompt, model=model)
        return await self.generate_local(prompt, system_prompt, model)

    async def generate_stream(self, prompt: str, use_cloud: bool = False, system_prompt: str = None, model: str = None):
        """流式生成内容"""
        if use_cloud:
            # 云服务暂时不支持流式，返回普通结果
            result = await self.generate_cloud(prompt, system_prompt)
            yield result
        else:
            async for chunk in self.generate_local_stream(prompt, system_prompt, model):
                yield chunk

    # ============================================================
    # V4.1: Token 侧信道 — 供 CostTracker 消费
    # ============================================================

    def get_and_reset_tokens(self) -> Dict[str, Any]:
        """获取并重置累积的 token 消耗数据

        每次 workflow 执行完成后调用，获取该次 workflow 产生的 token 消耗。
        返回后内部计数器归零，准备下一次 workflow。

        Returns:
            {
                "local": {"input": int, "output": int, "calls": int},
                "cloud": {"input": int, "output": int, "calls": int},
            }
        """
        result = {
            "local": dict(self._local_tokens),
            "cloud": dict(self._cloud_tokens),
        }
        self._local_tokens = {"input": 0, "output": 0, "calls": 0}
        self._cloud_tokens = {"input": 0, "output": 0, "calls": 0}
        return result

    @staticmethod
    def calc_cloud_cost(input_tokens: int, output_tokens: int) -> float:
        """计算云端 API 调用成本（元）

        Args:
            input_tokens: 输入 token 数
            output_tokens: 输出 token 数

        Returns:
            成本（元），保留 6 位小数精度
        """
        cost = (input_tokens / 1_000_000) * LLMClient.DEEPSEEK_INPUT_PRICE + \
               (output_tokens / 1_000_000) * LLMClient.DEEPSEEK_OUTPUT_PRICE
        return round(cost, 6)

    @staticmethod
    def calc_local_savings(input_tokens: int, output_tokens: int) -> float:
        """计算本地模型节省的成本（元）

        即：如果这些 token 走云端 API 需要多少钱

        Args:
            input_tokens: 本地模型输入 token 数
            output_tokens: 本地模型输出 token 数

        Returns:
            节省金额（元）
        """
        return LLMClient.calc_cloud_cost(input_tokens, output_tokens)


_llm_client: Optional[LLMClient] = None


def get_llm_client() -> LLMClient:
    global _llm_client
    if _llm_client is None:
        _llm_client = LLMClient()
    return _llm_client
