"""Reasoning Graph — 推理模式图谱

这是 V3 最大的创新点。
学习的不再是 Knowledge，而是 Reasoning Pattern。

节点类型:
- analysis_pattern    : 分析类模式（对比分析、因果分析、SWOT分析）
- writing_pattern    : 写作类模式（论证、叙事、说明）
- coding_pattern     : 编码类模式（设计→实现→测试→优化）
- decision_pattern   : 决策类模式（评估→权衡→选择→验证）
- explanation_pattern: 解释类模式（定义→原理→举例→总结）
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional
from copy import deepcopy
import re
import os
import logging

logger = logging.getLogger(__name__)


@dataclass
class ReasoningNode:
    """推理模式节点"""
    pattern_id: str                    # "comparison_analysis"
    pattern_name: str                  # "对比分析模式"
    pattern_type: str                  # "analysis_pattern"
    steps: List[str] = field(default_factory=list)
    applicable_domains: List[str] = field(default_factory=list)
    applicable_task_types: List[str] = field(default_factory=list)
    template: str = ""                 # Prompt 模板
    usage_count: int = 0
    avg_effectiveness: float = 0.0     # 平均效果评分
    metadata: Dict = field(default_factory=dict)  # 来源标记等元信息

    def build_prompt(self, user_task: str) -> str:
        """用推理模式构建 Prompt"""
        step_instructions = "\n".join(
            f"{i+1}. {step}" for i, step in enumerate(self.steps)
        )
        return f"""请按照以下推理结构组织你的回答：

{step_instructions}

用户问题: {user_task}

请严格遵循上述结构，每个部分都要有实质性内容。"""


class ReasoningGraph:
    """推理模式图谱 — 思维方式的图结构

    边类型:
    - applicable_to: 模式适用于某领域
    - derived_from : 从哪个模式演化而来
    - composed_of  : 由哪些子模式组成
    - alternative_to: 替代模式
    """

    # 预置推理模式（种子数据）
    PRESET_PATTERNS = {
        "comparison_analysis": ReasoningNode(
            pattern_id="comparison_analysis",
            pattern_name="对比分析模式",
            pattern_type="analysis_pattern",
            steps=["背景与问题", "对比维度定义", "逐维对比分析", "优劣总结", "选择建议"],
            applicable_domains=["tech", "business"],
            applicable_task_types=["analysis", "planning"],
            template="## 背景\n## 对比维度\n## 逐维分析\n## 总结\n## 建议"
        ),
        "problem_solution": ReasoningNode(
            pattern_id="problem_solution",
            pattern_name="问题解决模式",
            pattern_type="analysis_pattern",
            steps=["问题定义", "原因分析", "方案设计", "方案评估", "实施建议"],
            applicable_domains=["tech", "daily"],
            applicable_task_types=["analysis", "coding"],
            template="## 问题\n## 原因\n## 方案\n## 评估\n## 建议"
        ),
        "concept_explanation": ReasoningNode(
            pattern_id="concept_explanation",
            pattern_name="概念解释模式",
            pattern_type="explanation_pattern",
            steps=["定义", "核心原理", "关键特性", "应用场景", "举例说明"],
            applicable_domains=["tech", "ai"],
            applicable_task_types=["qa"],
            template="## 定义\n## 原理\n## 特性\n## 应用\n## 举例"
        ),
        "argumentative_writing": ReasoningNode(
            pattern_id="argumentative_writing",
            pattern_name="论证写作模式",
            pattern_type="writing_pattern",
            steps=["观点提出", "论据支撑", "反驳与回应", "深化论证", "结论"],
            applicable_domains=["business", "daily"],
            applicable_task_types=["writing"],
            template="## 观点\n## 论据\n## 回应\n## 深化\n## 结论"
        ),
        "code_design_implement": ReasoningNode(
            pattern_id="code_design_implement",
            pattern_name="编码设计实现模式",
            pattern_type="coding_pattern",
            steps=["需求分析", "架构设计", "核心实现", "边界处理", "测试验证"],
            applicable_domains=["tech"],
            applicable_task_types=["coding"],
            template="## 分析\n## 设计\n## 实现\n## 边界\n## 测试"
        ),
    }

    # 自学习模式持久化路径（与 skill_graph.yaml 同目录）
    _YAML_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                              "reasoning_graph.yaml")

    def __init__(self):
        self.patterns: Dict[str, ReasoningNode] = {}
        # 加载预置模式（深拷贝，避免实例间共享状态）
        for pid, pattern in self.PRESET_PATTERNS.items():
            self.patterns[pid] = deepcopy(pattern)
        # 加载自学习模式（覆盖同 pattern_id 的预置模式）
        self._load_learned_patterns()

    # ========== 持久化（仅持久化自学习模式，不动预置种子） ==========

    def _load_learned_patterns(self):
        """从 yaml 加载自学习推理模式（预置模式不持久化，重启自动恢复）"""
        try:
            import yaml as _yaml
            if os.path.exists(self._YAML_PATH):
                with open(self._YAML_PATH, "r", encoding="utf-8") as f:
                    data = _yaml.safe_load(f) or {}
                for p in data.get("learned_patterns", []):
                    node = ReasoningNode(
                        pattern_id=p.get("pattern_id", ""),
                        pattern_name=p.get("pattern_name", ""),
                        pattern_type=p.get("pattern_type", "analysis_pattern"),
                        steps=p.get("steps", []),
                        applicable_domains=p.get("applicable_domains", []),
                        applicable_task_types=p.get("applicable_task_types", []),
                        template=p.get("template", ""),
                        usage_count=p.get("usage_count", 0),
                        avg_effectiveness=p.get("avg_effectiveness", 0.0),
                    )
                    # 标记来源为自学习
                    node.metadata = {"source": "auto_extract"} if hasattr(node, "metadata") else {}
                    self.patterns[node.pattern_id] = node
        except Exception as e:
            logger.warning(f"加载自学习推理模式失败: {e}")

    def save_learned_patterns(self):
        """持久化自学习推理模式到 yaml（预置模式不写入）"""
        try:
            import yaml as _yaml
            # 只持久化非预置模式
            preset_ids = set(self.PRESET_PATTERNS.keys())
            learned = []
            for pid, p in self.patterns.items():
                if pid in preset_ids:
                    continue
                learned.append({
                    "pattern_id": p.pattern_id,
                    "pattern_name": p.pattern_name,
                    "pattern_type": p.pattern_type,
                    "steps": p.steps,
                    "applicable_domains": p.applicable_domains,
                    "applicable_task_types": p.applicable_task_types,
                    "template": p.template,
                    "usage_count": p.usage_count,
                    "avg_effectiveness": p.avg_effectiveness,
                })
            data = {"learned_patterns": learned}
            with open(self._YAML_PATH, "w", encoding="utf-8") as f:
                _yaml.dump(data, f, allow_unicode=True, default_flow_style=False)
            logger.info(f"ReasoningGraph: 已持久化 {len(learned)} 个自学习模式")
        except Exception as e:
            logger.warning(f"持久化自学习推理模式失败: {e}")

    def match(self, task_type: str, domain: str = "",
              keywords: Optional[List[str]] = None) -> Optional[ReasoningNode]:
        """匹配最佳推理模式

        匹配优先级:
        1. task_type + domain 完全匹配
        2. task_type 匹配
        3. domain 匹配
        4. 关键词匹配
        """
        candidates = []

        for pattern in self.patterns.values():
            score = 0
            if task_type in pattern.applicable_task_types:
                score += 5
            if domain and domain in pattern.applicable_domains:
                score += 3
            if keywords:
                for kw in keywords:
                    if kw.lower() in pattern.pattern_name.lower():
                        score += 2
            if score > 0:
                candidates.append((score, pattern))

        if not candidates:
            return None

        candidates.sort(key=lambda x: (x[0], -len(x[1].applicable_task_types)), reverse=True)
        best = candidates[0][1]
        best.usage_count += 1
        return best

    def register(self, pattern: ReasoningNode):
        """注册新的推理模式"""
        self.patterns[pattern.pattern_id] = pattern

    def extract_from_text(self, text: str) -> Optional[ReasoningNode]:
        """从 Writer 输出中提取推理模式

        检测 Markdown 结构模式:
        - "背景 → 分析 → 举例 → 总结"
        - "问题 → 原因 → 方案 → 验证"
        - "定义 → 原理 → 应用 → 对比"
        """
        if not text:
            return None

        headers = re.findall(r'^#{1,3}\s+(.+?)$', text, re.MULTILINE)
        if len(headers) < 3:
            return None

        # 匹配已知模式关键词
        pattern_keyword_map = {
            "background_analysis_example_summary": ["背景", "分析", "举例", "总结"],
            "problem_cause_solution_verify": ["问题", "原因", "方案", "验证"],
            "definition_principle_application_compare": ["定义", "原理", "应用", "对比"],
            "swot_analysis": ["优势", "劣势", "机会", "威胁"],
        }

        for pattern_id, keywords in pattern_keyword_map.items():
            matched = []
            for kw in keywords:
                if any(kw in h for h in headers):
                    matched.append(kw)
            if len(matched) >= 3:
                return ReasoningNode(
                    pattern_id=pattern_id,
                    pattern_name=f"自动提取-{pattern_id}",
                    pattern_type="analysis_pattern",
                    steps=matched,
                    template="\n".join(f"## {s}" for s in matched)
                )

        return None

    def get_all_patterns(self) -> List[ReasoningNode]:
        """获取所有推理模式"""
        return list(self.patterns.values())

    def stats(self) -> dict:
        """获取统计信息"""
        by_type = {}
        for p in self.patterns.values():
            ptype = p.pattern_type
            by_type[ptype] = by_type.get(ptype, 0) + 1

        most_used = sorted(
            self.patterns.values(),
            key=lambda p: p.usage_count, reverse=True
        )[:3]
        most_used_info = [
            {"pattern_id": p.pattern_id, "pattern_name": p.pattern_name,
             "usage_count": p.usage_count}
            for p in most_used
        ]

        return {
            "total_patterns": len(self.patterns),
            "by_type": by_type,
            "most_used": most_used_info
        }