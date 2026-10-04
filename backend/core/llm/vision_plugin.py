"""VisionPlugin — 视觉识别插件（可插拔，非 Agent）

V4.4 统一模型架构:
- 主模型与视觉模型统一为 qwen2.5vl:7b（原生多模态，文本/图片同一模型）
- 不再需要「卸载主模型 → 加载视觉模型 → 识别 → 卸载 → 重载主模型」的互斥切换流程
- keep_alive=5m：模型常驻显存，识别请求直接复用
- 单图顺序处理：同一时间只处理一张图片（保持串行约束，避免并发请求互相干扰）

★ 视觉分流策略（2026-09-22 佳文定版，不可违反）:
- **常规识别一律本地**。本插件就是本地路径，任何"用户传图 → 需要看内容"的
  简单任务都由这里处理，**不调用云端 API**：零 API 成本、零网络延迟、数据不出本机。
- **云端视觉（DeepSeek-V4.1-Flash，API id `deepseek-flash`）只用于少数显式场景**，不是每次识别的默认动作：
    1. 自学习三层筛网第 2 层 —— 名词/片段拆解与权威源比对（离线/半离线批处理，
       不是用户问答的实时路径）
    2. 本地识别明确失败或产物不可用，且该场景值得付云端成本时的显式升级
- 因此：**本文件不得为了"顺手"而引入 implicit 的云端调用**。云端视觉入口必须
  由调用方显式触发（见 docs/云端模型与增强调用清单.md 的 C 层）。

设计原则（遵循规则十一）:
- 只负责"识别"：客观描述图片所见内容，不思考、不推理、不考虑用户画像和上下文
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
import re
import threading
import time
import urllib.request
from typing import Callable, List, Optional

logger = logging.getLogger(__name__)

# 修复方案 A：外层围栏识别 —— 仅当信息串为 markdown/md 时判定为"模型错误包裹了文档输出"。
# 代码截图的合法输出（```python 等语言围栏）不在此列，不会被剥离。
_FENCE_INFO_RE = re.compile(r"^```(?:markdown|md)\s*$", re.IGNORECASE)

# 进度回调类型：(current_index, total, phase, status_message) -> None
ProgressCallback = Callable[[int, int, str, str], None]

# 进程级全局锁 — 串行化所有识别请求
# V4.4: 不再是为了显存互斥（统一模型后无需切换），
# 而是保持「同一时间只处理一张图片」的约束，避免并发识别请求互相干扰
_vision_lock = threading.Lock()


class VisionPlugin:
    """视觉识别插件 — 封装 qwen2.5vl:7b 多模态调用

    V4.4: 视觉模型 = 主模型，识别请求直接复用常驻模型，零切换开销。

    ★ 本类**不包含任何云端调用**：所有识别走本地 Ollama，成本为 0。
      云端视觉（DeepSeek-V4.1-Flash，API id `deepseek-flash`）不在本类内隐式发起，必须由调用方显式触发，
      且仅限自学习筛网拆解比对等少数场景（详见模块 docstring 的分流策略）。

    非 Agent，不参与 5 Agent 执行顺序，作为 Knowledge Agent 的工具类使用。

    并发安全：通过全局 _vision_lock 串行化所有识别请求。
    若两个请求同时到达，第二个会阻塞等待第一个完成后才执行。
    """

    def __init__(self, ollama_host: Optional[str] = None, vision_model: Optional[str] = None):
        # 延迟读取配置，避免循环导入
        if ollama_host is None:
            from app.config import settings
            ollama_host = getattr(settings, "ollama_host", "http://localhost:11434")
        if vision_model is None:
            from app.config import settings
            # V4.4: 与主模型统一，默认 qwen2.5vl:7b
            vision_model = getattr(settings, "ollama_vision_model", "qwen2.5vl:7b")

        self.ollama_host = ollama_host
        self.vision_model = vision_model

        logger.info(
            f"VisionPlugin initialized (V4.4 统一模型): vision_model={self.vision_model}, "
            f"host={self.ollama_host}"
        )

    def _call_vision(self, image_b64: str, prompt: str) -> str:
        """调用多模态模型识别单张图片

        使用 Ollama /api/chat 端点，messages 中携带 images 字段。
        V4.4: keep_alive=5m — 与主模型统一，保持常驻不卸载。

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
            "keep_alive": "5m",  # V4.4: 模型常驻，无需用完即卸载
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

        约束模型只描述所见内容，不思考不补充。
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

    @staticmethod
    def _normalize_output(text: str) -> str:
        """修复方案 A：确定性后处理，收敛视觉识别输出的格式契约。

        依据 docs/vision_benchmark 实测（2 轮 × 4 样本）：
        1. 7/8 次输出被 ```markdown 围栏整体包裹（提示词从未要求）——
           若不剥离，下游 Markdown 渲染会把整篇内容显示成一坨灰色代码块。
        2. 首尾偶带空白行/尾随空格。

        处理规则（全部确定性，零模型调用）：
        - 仅当首行为 ```markdown / ```md（允许大小写与尾随空白）且末行为 ``` 时，
          剥去这一对围栏。**代码截图的合法输出是 ```python 等语言围栏，
          不匹配本规则，绝不会被误剥。**
        - 剥离后 strip 首尾空白。

        幂等：已干净的输出原样返回；失败占位符（[图片识别失败: ...]）不受影响。
        """
        if not text:
            return text
        lines = text.splitlines()
        # 首尾去空行后仍需 >= 2 行才可能构成"围栏对"
        while lines and not lines[0].strip():
            lines.pop(0)
        while lines and not lines[-1].strip():
            lines.pop()
        if len(lines) >= 2 and _FENCE_INFO_RE.match(lines[0].strip()) and lines[-1].strip() == "```":
            lines = lines[1:-1]
            # 围栏内部可能仍有首尾空行，再清一次
            while lines and not lines[0].strip():
                lines.pop(0)
            while lines and not lines[-1].strip():
                lines.pop()
            return "\n".join(lines)
        return "\n".join(lines) if lines else text.strip()

    def recognize_images(
        self,
        images_base64: List[str],
        on_progress: Optional[ProgressCallback] = None,
    ) -> List[str]:
        """识别多张图片（顺序处理）

        同步方法 — 调用方应使用 asyncio.to_thread() 在线程池中执行。

        V4.4 流程（统一模型，无切换）：
        1. 获取全局锁（排队等待其他识别请求完成）
        2. 逐张识别图片（模型常驻，每张直接调用）
        3. 释放锁

        Args:
            images_base64: 图片 base64 编码列表（最多 9 张）
            on_progress: 进度回调 (current_index_1based, total, status_message)

        Returns:
            识别结果列表，与输入图片一一对应
        """
        total = len(images_base64)
        if total == 0:
            return []

        # 限制最多 9 张（保持原约束，避免单请求处理时间过长）
        if total > 9:
            logger.warning(
                f"[VisionPlugin] 图片数量 {total} 超过上限 9，只处理前 9 张"
            )
            images_base64 = images_base64[:9]
            total = 9

        # 获取全局锁，串行化所有识别请求
        # 阻塞等待 — 若另一个请求正在识别，当前线程会在此等待
        if on_progress:
            on_progress(0, total, "preparing", "正在准备视觉识别...")

        with _vision_lock:
            logger.info(
                f"[VisionPlugin] 获取全局锁，开始识别 {total} 张图片，"
                f"模型: {self.vision_model} (V4.4 统一模型，无切换)"
            )

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

                    # 修复方案 A：确定性后处理（剥外层 markdown 围栏 + 修剪空白）
                    result = self._normalize_output(result)

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

            if on_progress:
                on_progress(total, total, "completed", "视觉识别完成")

            logger.info(f"[VisionPlugin] 全部 {total} 张图片识别完成")

            return descriptions
