"""Patch Validator — 防止知识污染的最后一道防线

这是一个永久模块，不是 LearningEngine 的子组件。
任何写入 Skill Graph 的操作都必须经过 Validator。

校验维度:
1. 冲突检查: 是否与已有知识矛盾
2. 重复检查: 是否已存在
3. 置信度检查: 概念名称是否有效
4. 完整性检查: 必要字段是否齐全
5. 来源检查: Patch 来源是否可信
"""

import re, logging
from typing import List, Optional
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """校验结果"""
    passed: bool
    patch_type: str                # "knowledge" | "reasoning" | "workflow" | "skill"
    patch_name: str
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


class PatchValidator:
    """Patch 校验器 — 永久守门人

    规则:
    1. 概念名长度 2-60 字符
    2. 概念名不能是纯数字/纯符号
    3. 不能与已有节点重复
    4. 定义文本不能为空
    5. 推理模式至少 3 步
    6. 工作流至少 3 步
    """

    def __init__(self, graph):
        self.graph = graph  # SkillGraph 实例
        self.validation_log: List[ValidationResult] = []

    def validate_knowledge(self, patch) -> ValidationResult:
        """校验知识 Patch — 五维校验

        1. 重复检查: 是否已存在
        2. 长度检查: 概念名 2-60 字符
        3. 有效性检查: 概念名是否含中英文
        4. 完整性检查: 定义不能为空且 >= 10 字符
        5. 来源检查: Patch 来源是否可信
        6. 冲突检查: 与已有节点高度相似视为冲突
        """
        errors = []
        warnings = []

        # 1. 重复检查
        node_id = patch.concept_name.lower().replace(" ", "_").replace("-", "_")
        if node_id in self.graph.nodes:
            errors.append(f"重复概念: '{patch.concept_name}' 已存在")

        # 2. 长度检查
        if len(patch.concept_name) < 2:
            errors.append(f"概念名过短: '{patch.concept_name}'")
        if len(patch.concept_name) > 60:
            errors.append(f"概念名过长: {len(patch.concept_name)}字符")

        # 3. 有效性检查
        if not re.search(r'[\u4e00-\u9fffa-zA-Z]', patch.concept_name):
            errors.append(f"概念名无效: '{patch.concept_name}' 缺少有意义的内容")

        # 4. 定义检查
        if not patch.definition or len(patch.definition.strip()) < 10:
            errors.append(f"定义过短或为空: '{patch.definition[:20]}...'")

        # 5. 来源检查
        source = getattr(patch, 'source', 'auto_extract')
        trusted_sources = {"auto_extract", "verified", "deepseek", "manual", "user_confirmed"}
        if source and source not in trusted_sources:
            errors.append(f"来源不可信: '{source}'，允许的来源: {trusted_sources}")

        # 6. 冲突检查 — 相似度 >= 0.8 视为冲突（error），0.7-0.8 为警告
        similar = self.graph.find_similar_node(patch.concept_name, threshold=0.7)
        if similar and node_id not in self.graph.nodes:
            similarity = self._calc_similarity(patch.concept_name, similar.name)
            if similarity >= 0.8:
                errors.append(f"冲突节点: '{patch.concept_name}' 与已有节点 '{similar.name}' (id={similar.id}) 高度相似")
            else:
                warnings.append(f"相似节点已存在: '{similar.name}' (id={similar.id})，请确认非重复")

        result = ValidationResult(
            passed=len(errors) == 0,
            patch_type="knowledge",
            patch_name=patch.concept_name,
            errors=errors,
            warnings=warnings
        )
        self.validation_log.append(result)
        return result

    def _calc_similarity(self, name1: str, name2: str) -> float:
        """计算两个名称的相似度（0-1）"""
        n1 = name1.lower()
        n2 = name2.lower()
        if n1 == n2:
            return 1.0
        if n1 in n2 or n2 in n1:
            return 0.85
        words1 = set(n1.replace("-", " ").replace("_", " ").split())
        words2 = set(n2.replace("-", " ").replace("_", " ").split())
        if words1 and words2:
            return len(words1 & words2) / len(words1 | words2)
        return 0.0

    def validate_reasoning(self, patch) -> ValidationResult:
        """校验推理模式 Patch"""
        errors = []
        if len(patch.steps) < 3:
            errors.append(f"推理步骤不足: {len(patch.steps)} < 3")
        if not patch.pattern_name:
            errors.append("模式名称为空")

        result = ValidationResult(
            passed=len(errors) == 0,
            patch_type="reasoning",
            patch_name=patch.pattern_name,
            errors=errors
        )
        self.validation_log.append(result)
        return result

    def validate_workflow(self, patch) -> ValidationResult:
        """校验工作流 Patch"""
        errors = []
        if len(patch.steps) < 3:
            errors.append(f"工作流步骤不足: {len(patch.steps)} < 3")

        result = ValidationResult(
            passed=len(errors) == 0,
            patch_type="workflow",
            patch_name=patch.task_type,
            errors=errors
        )
        self.validation_log.append(result)
        return result

    def validate_skill(self, patch) -> ValidationResult:
        """校验技能 Patch"""
        errors = []
        if not patch.domain:
            errors.append("域名为空")

        result = ValidationResult(
            passed=len(errors) == 0,
            patch_type="skill",
            patch_name=patch.domain,
            errors=errors
        )
        self.validation_log.append(result)
        return result

    def get_stats(self) -> dict:
        """获取校验统计"""
        total = len(self.validation_log)
        passed = sum(1 for r in self.validation_log if r.passed)
        return {
            "total_validations": total,
            "passed": passed,
            "rejected": total - passed,
            "pass_rate": f"{passed/total*100:.1f}%" if total > 0 else "N/A"
        }