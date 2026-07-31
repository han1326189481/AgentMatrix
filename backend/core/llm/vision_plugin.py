"""VisionPlugin — 视觉模型插件（可插拔，非 Agent）

设计原则（遵循规则十一）:
- 只负责"识别"：客观描述图片所见内容，不思考、不推理、不考虑用户画像和上下文
- 互斥加载：与主模型 Qwen2.5 互斥，切换前先卸载主模型，识别完立即卸载视觉模型
- keep_alive=0：用完即卸载，释放显存给主模型
- 单图顺序处理：同一时间只处理一张图片，避免显存峰值叠加（8GB VRAM 限制）
- 输出格式约束：
  - PPT/Word 截图 → Markdown 格式（含标题层级、列表、表格结构）
  - 代码片段截图 → 代码块（带语言标签）
  - 普通图片 → 客观描述（不臆测、不补充）

使用方式:
    from core.llm.vision_plugin import VisionPlugin

    plugin = VisionPlugin()
    descriptions = await plugin.recognize_images(
        images_base64=[img1_b64, img2_b64],
        on_progress=lambda idx, total, status: broadcast(idx, total, status),
    )
    # descriptions: List[str] — 每张图片的识别结果（Markdown 格式）
"""
import base64
import json
import logging
import threading
import time
import urllib.request
from typing import Callable, List, Optional

logger = logging.getLogger(__name__)

# 进度回调类型：(current_index, total, phase, status_message) -> None
ProgressCallback = Callable[[int, int, str, str], None]

# V3.2: 进程级全局锁 — 保护视觉模型互斥加载流程
# 8GB VRAM 无法并发加载两个 MiniCPM-V（5.5GB × 2 = 11GB > 8GB），
# 必须串行化整个「卸载主模型 → 加载视觉模型 → 识别 → 卸载视觉模型 → 重载主模型」流程
_vision_lock = threading.Lock()


class VisionPlugin:
    """视觉模型插件 — 封装 MiniCPM-V 调用 + 互斥加载机制

    非 Agent，不参与 5 Agent 执行顺序，作为 Knowledge Agent 的工具类使用。

    并发安全：通过全局 _vision_lock 串行化所有识别请求。
    若两个请求同时到达，第二个会阻塞等待第一个完成（含主模型重载）后才执行，
    确保 8GB 显存不会因并发加载而 OOM。
    """

    def __init__(self, ollama_host: Optional[str] = None, vision_model: Optional[str] = None):
        # 延迟读取配置，避免循环导入
        if ollama_host is None:
            from app.config import settings
            ollama_host = getattr(settings, "ollama_host", "http://localhost:11434")
        if vision_model is None:
            from app.config import settings
            # 优先从 .env 读取 OLLAMA_VISION_MODEL，默认 minicpm-v:latest
            vision_model = getattr(settings, "ollama_vision_model", "minicpm-v:latest")

        self.ollama_host = ollama_host
        self.vision_model = vision_model
        # 主模型名（用于互斥加载前的卸载）
        from core.model_registry import get_model
        self.main_model = get_model("default")

        logger.info(
            f"VisionPlugin initialized: vision_model={self.vision_model}, "
            f"main_model={self.main_model}, host={self.ollama_host}"
        )

    def _unload_model(self, model: str) -> bool:
        """卸载指定模型（keep_alive=0 立即释放显存）

        通过发送空 chat 请求 + keep_alive=0 实现：
        Ollama 收到后会把该模型从内存中卸载。
        """
        payload = {
            "model": model,
            "messages": [],
            "keep_alive": 0,
        }
        try:
            req = urllib.request.Request(
                f"{self.ollama_host}/api/chat",
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            urllib.request.urlopen(req, timeout=30)
            logger.info(f"[VisionPlugin] 卸载模型: {model} (keep_alive=0)")
            return True
        except Exception as e:
            logger.warning(f"[VisionPlugin] 卸载模型 {model} 失败: {e}")
            return False

    def _wait_for_model_unloaded(
        self, model: str, max_wait_seconds: float = 5.0, poll_interval: float = 0.3
    ) -> bool:
        """P1-9 修复：轮询 Ollama 确认模型已卸载完成（替代固定 time.sleep）

        Ollama 卸载模型后显存释放有延迟（7B 模型可能需 2-3 秒），
        固定 sleep(1) 可能不够导致后续加载视觉模型时 OOM，
        或浪费等待时间。轮询 /api/ps 确认模型不再驻留更可靠。

        Args:
            model: 要确认卸载的模型名
            max_wait_seconds: 最大等待时间（默认 5 秒，避免永久阻塞）
            poll_interval: 轮询间隔（默认 300ms）

        Returns:
            True=模型已卸载（或超时但视为已卸载，仅记录警告）
            False=轮询过程异常（调用方应继续流程，不阻塞）
        """
        deadline = time.time() + max_wait_seconds
        try:
            while time.time() < deadline:
                req = urllib.request.Request(
                    f"{self.ollama_host}/api/ps",
                    headers={"Content-Type": "application/json"},
                    method="GET",
                )
                with urllib.request.urlopen(req, timeout=5) as resp:
                    ps_data = json.loads(resp.read().decode("utf-8"))

                # /api/ps 返回 { "models": [{ "name": "...", ... }] }
                loaded_models = [m.get("name", "") for m in ps_data.get("models", [])]
                # Ollama 可能返回带 :latest 后缀的名称，做归一化比较
                model_base = model.split(":")[0]
                still_loaded = any(
                    m == model or m.startswith(model_base + ":") or m == model_base
                    for m in loaded_models
                )
                if not still_loaded:
                    logger.info(
                        f"[VisionPlugin] 确认模型 {model} 已卸载 "
                        f"(耗时 {max_wait_seconds - (deadline - time.time()):.2f}s)"
                    )
                    return True
                time.sleep(poll_interval)

            # 超时：模型可能仍在卸载中，但不阻塞流程（继续加载视觉模型）
            # 若显存未释放足够，Ollama 会自动处理或后续 _call_vision 报错
            logger.warning(
                f"[VisionPlugin] 等待模型 {model} 卸载超时 ({max_wait_seconds}s)，"
                f"继续执行（可能由 Ollama 自动处理）"
            )
            return True
        except Exception as e:
            # P1-9 修复：轮询异常时回退到固定等待，而非零等待
            # 场景：旧版 Ollama 不支持 /api/ps、网络超时、JSON 解析失败
            # 零等待会导致显存未释放就加载视觉模型，8GB 显存极易 OOM
            logger.warning(
                f"[VisionPlugin] 轮询模型卸载状态异常: {e}，"
                f"回退到固定等待 1.5 秒"
            )
            time.sleep(1.5)
            return True

    def _call_vision(self, image_b64: str, prompt: str) -> str:
        """调用视觉模型识别单张图片

        使用 Ollama /api/chat 端点，messages 中携带 images 字段。
        keep_alive=0 确保用完即卸载。

        Args:
            image_b64: 图片的 base64 编码字符串（不含 data:image/... 前缀）
            prompt: 识别指令

        Returns:
            模型返回的识别结果（Markdown 格式）
        """
        payload = {
            "model": self.vision_model,
            "messages": [
                {
                    "role": "user",
                    "content": prompt,
                    "images": [image_b64],
                }
            ],
            "stream": False,
            "options": {
                "num_predict": 2048,
                "temperature": 0.1,  # 低温度确保客观描述
            },
            "keep_alive": 0,  # 用完即卸载，释放显存
        }

        req = urllib.request.Request(
            f"{self.ollama_host}/api/chat",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        resp = urllib.request.urlopen(req, timeout=180)
        data = json.loads(resp.read())
        return data.get("message", {}).get("content", "")

    def _build_recognition_prompt(self, image_index: int, total: int) -> str:
        """构建识别指令

        约束视觉模型只描述所见内容，不思考不补充。
        对 PPT/Word 输出 Markdown 格式，对代码输出代码块。
        """
        return (
            "请识别这张图片的所有内容，以 Markdown 格式输出。\n"
            "要求：\n"
            "1. 如果是 PPT/Word/文档截图：保留标题层级（# / ## / ###），"
            "列表项用 - 或 1. 2.，表格用 Markdown 表格格式\n"
            "2. 如果是代码截图：用 ```代码块``` 输出，并标注语言（如 ```python）\n"
            "3. 如果是普通图片：客观描述所见内容，不要臆测或补充\n"
            "4. 只输出看到的内容，不要添加任何解释、分析或建议\n"
            "5. 保持原文语言（中文输出中文，英文输出英文）\n"
        )

    def _strip_data_prefix(self, base64_str: str) -> str:
        """移除 base64 字符串的 data:image/...;base64, 前缀"""
        if base64_str.startswith("data:"):
            # 格式: data:image/jpeg;base64,/9j/4AAQ...
            comma_idx = base64_str.find(",")
            if comma_idx > 0:
                return base64_str[comma_idx + 1:]
        return base64_str

    def recognize_images(
        self,
        images_base64: List[str],
        on_progress: Optional[ProgressCallback] = None,
    ) -> List[str]:
        """识别多张图片（顺序处理，遵循 8GB 显存约束）

        同步方法 — 调用方应使用 asyncio.to_thread() 在线程池中执行。

        完整流程：
        1. 卸载主模型 Qwen2.5（keep_alive=0）
        2. 逐张识别图片（每张识别完用 keep_alive=0 确保不驻留）
        3. 最后再加载主模型（通过一次空 generate 恢复）

        并发安全：整个流程持有 _vision_lock，第二个请求会阻塞等待。
        使用 try/finally 确保锁一定被释放，即使识别过程异常也不会死锁。

        Args:
            images_base64: 图片 base64 编码列表（最多 9 张）
            on_progress: 进度回调 (current_index_1based, total, status_message)

        Returns:
            识别结果列表，与输入图片一一对应
        """
        total = len(images_base64)
        if total == 0:
            return []

        # 限制最多 9 张（规则十一：单图顺序处理，避免显存峰值叠加）
        if total > 9:
            logger.warning(
                f"[VisionPlugin] 图片数量 {total} 超过上限 9，只处理前 9 张"
            )
            images_base64 = images_base64[:9]
            total = 9

        # V3.2: 获取全局锁，串行化所有视觉识别请求
        # 阻塞等待 — 若另一个请求正在识别，当前线程会在此等待
        # 通过 on_progress 通知前端当前处于排队状态
        if on_progress:
            on_progress(0, total, "switching", "正在等待视觉模型就绪...")

        # V3.2 修复：使用 with 上下文管理器替代 acquire/release
        # 避免 acquire() 与 try 之间发生异常导致锁永不释放（死锁）
        with _vision_lock:
            logger.info(f"[VisionPlugin] 获取全局锁，开始识别 {total} 张图片")

            logger.info(
                f"[VisionPlugin] 开始识别 {total} 张图片，"
                f"视觉模型: {self.vision_model}"
            )

            # Step 1: 卸载主模型，释放显存
            # P1-9 修复：替换 time.sleep(1) 为轮询确认卸载完成
            # 固定 sleep(1) 不可靠：7B 模型卸载可能需 2-3 秒，1 秒不够会 OOM
            if on_progress:
                on_progress(0, total, "switching", "正在切换至视觉模型...")
            self._unload_model(self.main_model)
            self._wait_for_model_unloaded(self.main_model, max_wait_seconds=5.0)

            # Step 2: 逐张识别
            descriptions: List[str] = []
            for idx, img_b64 in enumerate(images_base64):
                current = idx + 1
                img_b64 = self._strip_data_prefix(img_b64)
                img_size_kb = len(img_b64) / 1024

                if on_progress:
                    on_progress(current, total, "recognizing",
                               f"正在识别第 {current}/{total} 张图片...")

                logger.info(
                    f"[VisionPlugin] 识别第 {current}/{total} 张图片 "
                    f"(大小: {img_size_kb:.1f} KB)"
                )

                try:
                    start = time.time()
                    prompt = self._build_recognition_prompt(current, total)
                    result = self._call_vision(img_b64, prompt)
                    elapsed = time.time() - start

                    logger.info(
                        f"[VisionPlugin] 第 {current}/{total} 张识别完成: "
                        f"{len(result)} 字, 耗时 {elapsed:.2f}s"
                    )
                    descriptions.append(result)
                except Exception as e:
                    logger.error(
                        f"[VisionPlugin] 第 {current}/{total} 张识别失败: {e}",
                        exc_info=True,
                    )
                    descriptions.append(f"[图片识别失败: {str(e)}]")

            # Step 3: 视觉模型已通过 keep_alive=0 自动卸载
            if on_progress:
                on_progress(total, total, "completed", "视觉识别完成，正在切换回主模型...")

            logger.info(
                f"[VisionPlugin] 全部 {total} 张图片识别完成，"
                f"视觉模型已自动卸载 (keep_alive=0)"
            )

            # V3.2: 在锁释放前重载主模型，确保下一个请求获取锁时主模型已就绪
            # 避免并发场景下「请求A重载主模型」与「请求B卸载主模型」交叉执行
            self._reload_main_model_internal()

            return descriptions

    def _reload_main_model_internal(self) -> bool:
        """内部方法：重载主模型（在锁内调用，不重新获取锁）"""
        payload = {
            "model": self.main_model,
            "prompt": "",
            "stream": False,
            "options": {"num_predict": 0},
            "keep_alive": "5m",
        }
        try:
            req = urllib.request.Request(
                f"{self.ollama_host}/api/generate",
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            urllib.request.urlopen(req, timeout=60)
            logger.info(
                f"[VisionPlugin] 主模型 {self.main_model} 已重新加载 (keep_alive=5m)"
            )
            return True
        except Exception as e:
            logger.warning(
                f"[VisionPlugin] 主模型 {self.main_model} 重新加载失败: {e}"
            )
            return False

    def reload_main_model(self) -> bool:
        """重新加载主模型（向后兼容接口）

        V3.2 起，主模型重载已在 recognize_images() 内部完成（锁保护下）。
        此方法保留仅为向后兼容，实际不再需要外部调用。
        若直接调用，会在无锁状态下重载，仅用于异常恢复场景。
        """
        return self._reload_main_model_internal()
