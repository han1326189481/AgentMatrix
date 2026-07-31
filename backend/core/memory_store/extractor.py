"""MemoryExtractor — 对话结束后自动提取关键信息存入长期记忆

设计原则:
- 使用本地模型提取，零云端成本（模型由 ModelRegistry 配置）
- 异步执行，不阻塞主工作流
- 提取失败静默降级，不影响用户体验
- 提取结果经 MemoryStore.add() 自动过滤低重要性条目
"""
import json
import logging
import asyncio
from typing import List, Dict, Optional

from core.model_registry import get_model

logger = logging.getLogger(__name__)

EXTRACTION_PROMPT = """你是一个信息提取助手。请从以下对话中提取用户的关键信息，以JSON格式输出。

用户输入：{user_input}
助手回复（摘要）：{response_summary}

请提取以下类型的信息（每条信息一句话概括）：
1. fact: 用户陈述的事实性信息（如身份、背景、经历）
2. preference: 用户的偏好和倾向（如喜欢什么、不喜欢什么）
3. goal: 用户的目标和计划（如想做什么、打算做什么）
4. event: 用户提到的事件（如发生了什么、参加了什么）

输出格式（严格JSON数组，无其他文字）：
[
  {{"content": "信息内容", "category": "fact|preference|goal|event", "importance": 0.0-1.0}}
]

规则：
- importance 根据信息的重要性和持久性评分：临时信息0.3-0.5，个人偏好0.5-0.7，身份/目标0.7-0.9
- 如果没有可提取的信息，返回空数组 []
- 每条content不超过50字，简洁准确
- 只提取用户明确表达的信息，不要推测"""


class MemoryExtractor:
    """从对话中自动提取关键信息存入长期记忆"""

    def __init__(self, llm_client=None, memory_store=None):
        self._llm_client = llm_client
        self._memory_store = memory_store

    async def extract_and_store(
        self, user_input: str, response: str, user_id: str = "default"
    ) -> List[str]:
        """从对话中提取关键信息并存储到长期记忆

        Args:
            user_input: 用户原始输入
            response: 助手最终回复
            user_id: 用户ID

        Returns:
            成功存储的记忆ID列表
        """
        if not user_input or not response:
            return []

        # 截取回复前500字作为摘要（本地小模型处理能力有限）
        response_summary = response[:500] if len(response) > 500 else response

        try:
            extracted = await self._extract(user_input, response_summary)
            if not extracted:
                return []

            stored_ids = []
            for item in extracted:
                content = item.get("content", "").strip()
                category = item.get("category", "general")
                importance = float(item.get("importance", 0.5))

                if not content or len(content) < 3:
                    continue

                # 通过 MemoryStore 存储（自动过滤低重要性）
                if self._memory_store:
                    mem_id = self._memory_store.add(
                        content=content,
                        importance=importance,
                        source="auto",
                        category=category,
                    )
                    if mem_id:
                        stored_ids.append(mem_id)
                        logger.debug(f"Auto memory stored: [{category}] {content} (importance={importance:.2f})")

            if stored_ids:
                logger.info(f"MemoryExtractor: stored {len(stored_ids)} memories from conversation")
            return stored_ids

        except Exception as e:
            logger.warning(f"MemoryExtractor failed (non-critical): {e}")
            return []

    async def _extract(self, user_input: str, response_summary: str) -> List[Dict]:
        """调用本地LLM提取关键信息"""
        prompt = EXTRACTION_PROMPT.format(
            user_input=user_input,
            response_summary=response_summary,
        )

        if self._llm_client:
            try:
                raw_output = await self._llm_client.generate_local(
                    prompt=prompt,
                    system_prompt="你是一个精确的信息提取助手，只输出JSON格式数据。",
                    model=get_model("extractor"),
                )
                return self._parse_output(raw_output)
            except Exception as e:
                logger.warning(f"LLM extraction failed, falling back to rule-based: {e}")

        # 回退：基于规则的关键词提取
        return self._rule_based_extract(user_input, response_summary)

    def _parse_output(self, raw: str) -> List[Dict]:
        """解析LLM输出的JSON"""
        if not raw:
            return []

        # 清理输出：移除可能的markdown代码块标记
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            lines = cleaned.split("\n")
            # 移除第一行（```json）和最后一行（```）
            cleaned = "\n".join(lines[1:-1]) if len(lines) > 2 else cleaned
            cleaned = cleaned.strip()

        try:
            result = json.loads(cleaned)
            if isinstance(result, list):
                return result
            elif isinstance(result, dict) and "content" in result:
                return [result]
        except json.JSONDecodeError:
            # 尝试提取JSON数组
            import re
            match = re.search(r'\[.*\]', cleaned, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group())
                except json.JSONDecodeError:
                    pass

        logger.debug(f"Failed to parse extraction output: {raw[:200]}")
        return []

    def _rule_based_extract(self, user_input: str, response_summary: str) -> List[Dict]:
        """基于规则的回退提取（不依赖LLM）"""
        results = []

        # 简单偏好检测
        preference_keywords = ["喜欢", "偏好", "习惯", "常用", "经常", "讨厌", "不喜欢"]
        goal_keywords = ["想", "打算", "计划", "目标", "希望", "需要", "要学", "要了解"]
        fact_keywords = ["我是", "我在", "我住", "我的", "我做", "我从事"]

        combined = user_input + " " + response_summary[:300]

        for kw in preference_keywords:
            if kw in combined:
                # 简单提取包含关键词的句子片段
                idx = combined.find(kw)
                snippet = combined[max(0, idx-10):idx+30].strip()
                if len(snippet) > 5:
                    results.append({
                        "content": snippet[:50],
                        "category": "preference",
                        "importance": 0.4,
                    })
                    break

        for kw in goal_keywords:
            if kw in combined:
                idx = combined.find(kw)
                snippet = combined[max(0, idx-10):idx+50].strip()
                if len(snippet) > 5:
                    results.append({
                        "content": snippet[:50],
                        "category": "goal",
                        "importance": 0.5,
                    })
                    break

        for kw in fact_keywords:
            if kw in combined:
                idx = combined.find(kw)
                snippet = combined[max(0, idx-5):idx+40].strip()
                if len(snippet) > 5:
                    results.append({
                        "content": snippet[:50],
                        "category": "fact",
                        "importance": 0.5,
                    })
                    break

        return results


# 全局单例
_extractor: Optional[MemoryExtractor] = None


def get_memory_extractor(llm_client=None, memory_store=None) -> MemoryExtractor:
    global _extractor
    if _extractor is None or llm_client is not None:
        _extractor = MemoryExtractor(llm_client=llm_client, memory_store=memory_store)
    return _extractor