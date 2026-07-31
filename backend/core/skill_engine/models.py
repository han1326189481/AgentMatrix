"""
Skill Engine V2 — 核心数据模型

定义 SkillBook、SkillTree、ReviewReport 等结构化数据类。
所有数据模型都是 YAML 可序列化的 dataclass / dict 结构。
"""

import os
import copy
import yaml
from typing import Dict, Any, List, Optional, Set
from dataclasses import dataclass, field
from datetime import datetime

# 从独立模块重导出 SkillTreeNode 和 SkillTree（向后兼容）
from .skill_tree import SkillTreeNode, SkillTree


# ============================================================
# SkillBook — 技能书核心数据模型
# ============================================================

@dataclass
class SkillMeta:
    """技能书元数据"""
    skill_id: str
    name: str
    version: str = "1.0.0"
    parent: Optional[str] = None
    model: str = ""  # 空字符串表示使用 ModelRegistry 默认模型
    created: str = ""
    updated: str = ""

    def to_dict(self) -> dict:
        return {
            "skill_id": self.skill_id,
            "name": self.name,
            "version": self.version,
            "parent": self.parent,
            "model": self.model,
            "created": self.created or datetime.now().strftime("%Y-%m-%d"),
            "updated": self.updated or datetime.now().strftime("%Y-%m-%d"),
        }

    def get_effective_model(self, agent_id: str = "default") -> str:
        """获取有效模型名：空字符串时回退到 ModelRegistry

        Args:
            agent_id: Agent ID，用于从 ModelRegistry 获取对应模型

        Returns:
            模型名（如 "qwen2.5:7b"）
        """
        if self.model:
            return self.model
        from core.model_registry import get_model
        return get_model(agent_id)

    @classmethod
    def from_dict(cls, data: dict) -> "SkillMeta":
        return cls(
            skill_id=data.get("skill_id", ""),
            name=data.get("name", ""),
            version=data.get("version", "1.0.0"),
            parent=data.get("parent"),
            model=data.get("model", ""),
            created=data.get("created", ""),
            updated=data.get("updated", ""),
        )


@dataclass
class RoleDefinition:
    """角色定义"""
    title: str = ""
    description: str = ""
    tone: str = "neutral"
    language: str = "zh-CN"

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "description": self.description,
            "tone": self.tone,
            "language": self.language,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "RoleDefinition":
        return cls(
            title=data.get("title", ""),
            description=data.get("description", ""),
            tone=data.get("tone", "neutral"),
            language=data.get("language", "zh-CN"),
        )


@dataclass
class DomainKnowledge:
    """领域知识"""
    keywords: Dict[str, Any] = field(default_factory=dict)
    ontology: Dict[str, Any] = field(default_factory=dict)
    examples: List[Dict[str, str]] = field(default_factory=list)
    constraints: List[str] = field(default_factory=list)
    confidence: float = 0.85

    def to_dict(self) -> dict:
        return {
            "keywords": self.keywords,
            "ontology": self.ontology,
            "examples": self.examples,
            "constraints": self.constraints,
            "confidence": self.confidence,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "DomainKnowledge":
        return cls(
            keywords=data.get("keywords", {}),
            ontology=data.get("ontology", {}),
            examples=data.get("examples", []),
            constraints=data.get("constraints", []),
            confidence=data.get("confidence", 0.85),
        )


@dataclass
class OutputFormat:
    """输出格式定义"""
    format: str = "markdown"
    max_length: int = 4096
    sections: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "format": self.format,
            "max_length": self.max_length,
            "sections": self.sections,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "OutputFormat":
        return cls(
            format=data.get("format", "markdown"),
            max_length=data.get("max_length", 4096),
            sections=data.get("sections", []),
        )


@dataclass
class ScoringDimensions:
    """评分维度配置（Review Agent 专用）"""
    dimensions: Dict[str, float] = field(default_factory=dict)
    pass_threshold: float = 0.65
    difficulty_matrix: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "dimensions": self.dimensions,
            "pass_threshold": self.pass_threshold,
            "difficulty_matrix": self.difficulty_matrix,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ScoringDimensions":
        return cls(
            dimensions=data.get("dimensions", {}),
            pass_threshold=data.get("pass_threshold", 0.65),
            difficulty_matrix=data.get("difficulty_matrix", {}),
        )


class SkillBook:
    """技能书 — 完整的数据对象（非 Prompt 文本）"""

    def __init__(
        self,
        meta: SkillMeta,
        role: RoleDefinition = None,
        capabilities: List[str] = None,
        knowledge: DomainKnowledge = None,
        output: OutputFormat = None,
        forbidden: List[str] = None,
        scoring: ScoringDimensions = None,
    ):
        self.meta = meta or SkillMeta(skill_id="base", name="通用技能")
        self.role = role or RoleDefinition()
        self.capabilities = capabilities or []
        self.knowledge = knowledge or DomainKnowledge()
        self.output = output or OutputFormat()
        self.forbidden = forbidden or []
        self.scoring = scoring or ScoringDimensions()

    # ===== 序列化 =====

    def to_dict(self) -> dict:
        return {
            "meta": self.meta.to_dict(),
            "role": self.role.to_dict(),
            "capabilities": self.capabilities,
            "knowledge": self.knowledge.to_dict(),
            "output": self.output.to_dict(),
            "forbidden": self.forbidden,
            "scoring": self.scoring.to_dict(),
        }

    def to_yaml(self) -> str:
        return yaml.dump(self.to_dict(), allow_unicode=True, default_flow_style=False)

    def save(self, filepath: str):
        """保存到 YAML 文件"""
        with open(filepath, "w", encoding="utf-8") as f:
            yaml.dump(self.to_dict(), f, allow_unicode=True, default_flow_style=False)

    @classmethod
    def from_dict(cls, data: dict) -> "SkillBook":
        return cls(
            meta=SkillMeta.from_dict(data.get("meta", {})),
            role=RoleDefinition.from_dict(data.get("role", {})),
            capabilities=data.get("capabilities", []),
            knowledge=DomainKnowledge.from_dict(data.get("knowledge", {})),
            output=OutputFormat.from_dict(data.get("output", {})),
            forbidden=data.get("forbidden", []),
            scoring=ScoringDimensions.from_dict(data.get("scoring", {})),
        )

    @classmethod
    def from_yaml(cls, filepath: str) -> "SkillBook":
        """从 YAML 文件加载"""
        with open(filepath, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        if data is None:
            data = {}
        return cls.from_dict(data)

    # ===== 合并 =====

    @staticmethod
    def merge(stack: List["SkillBook"]) -> "SkillBook":
        """合并技能栈：子节点覆盖父节点，特定字段有特殊合并规则"""
        if not stack:
            return SkillBook(SkillMeta(skill_id="base", name="通用技能"))

        if len(stack) == 1:
            return stack[0]

        result = SkillBook(
            meta=SkillMeta(
                skill_id=stack[-1].meta.skill_id,
                name=stack[-1].meta.name,
                version=stack[-1].meta.version,
                parent=stack[-1].meta.parent,
                model=stack[-1].meta.model,
            ),
            role=RoleDefinition(
                title=stack[-1].role.title,
                description=stack[-1].role.description,
                tone=stack[-1].role.tone,
                language=stack[-1].role.language,
            ),
            output=OutputFormat(
                format=stack[-1].output.format,
                max_length=stack[-1].output.max_length,
                sections=list(stack[-1].output.sections),
            ),
        )

        # capabilities: 交集（所有层都支持的能力才保留）
        cap_set = set(stack[0].capabilities)
        for s in stack[1:]:
            cap_set &= set(s.capabilities)
        result.capabilities = sorted(cap_set)

        # keywords: 合并（子节点追加）
        merged_kw = {}
        for s in stack:
            for category, kw_map in s.knowledge.keywords.items():
                if category not in merged_kw:
                    merged_kw[category] = {} if isinstance(kw_map, dict) else []
                if isinstance(kw_map, dict) and isinstance(merged_kw[category], dict):
                    merged_kw[category].update(kw_map)
                elif isinstance(kw_map, list) and isinstance(merged_kw[category], list):
                    merged_kw[category].extend(kw_map)
                else:
                    merged_kw[category] = kw_map
        result.knowledge.keywords = merged_kw

        # ontology: 合并（子节点覆盖）
        merged_onto = {}
        for s in stack:
            onto = s.knowledge.ontology
            if isinstance(onto, dict):
                merged_onto.update(onto)
            elif isinstance(onto, list):
                for item in onto:
                    if isinstance(item, dict) and "term" in item:
                        merged_onto[item["term"]] = item
        result.knowledge.ontology = merged_onto

        # examples: 合并（子节点优先）
        merged_examples = []
        for s in stack:
            merged_examples.extend(s.knowledge.examples)
        result.knowledge.examples = merged_examples

        # constraints: 合并去重
        merged_constraints = []
        seen = set()
        for s in stack:
            for c in s.knowledge.constraints:
                if c not in seen:
                    merged_constraints.append(c)
                    seen.add(c)
        result.knowledge.constraints = merged_constraints

        # forbidden: 合并去重
        merged_forbidden = []
        seen = set()
        for s in stack:
            for f in s.forbidden:
                if f not in seen:
                    merged_forbidden.append(f)
                    seen.add(f)
        result.forbidden = merged_forbidden

        # confidence: 取最深层
        result.knowledge.confidence = stack[-1].knowledge.confidence

        # scoring: 子节点覆盖
        merged_scoring = {}
        for s in stack:
            if s.scoring.dimensions:
                merged_scoring = s.scoring.dimensions
        result.scoring = ScoringDimensions(
            dimensions=merged_scoring,
            pass_threshold=stack[-1].scoring.pass_threshold,
            difficulty_matrix=stack[-1].scoring.difficulty_matrix,
        )

        return result

    # ===== Patch 支持 =====

    def apply_patch(self, patch: "SkillPatch"):
        """应用技能补丁（Skill Learning 使用）"""
        for kw_category, kw_map in patch.added_keywords.items():
            if kw_category not in self.knowledge.keywords:
                self.knowledge.keywords[kw_category] = {}
            self.knowledge.keywords[kw_category].update(kw_map)

        self.knowledge.constraints.extend(patch.added_constraints)
        self.knowledge.examples.extend(patch.added_examples)
        self.forbidden.extend(patch.added_forbidden)

        if patch.added_ontology:
            if isinstance(self.knowledge.ontology, dict):
                self.knowledge.ontology.update(patch.added_ontology)
            else:
                self.knowledge.ontology = patch.added_ontology

    def __repr__(self):
        return f"SkillBook({self.meta.skill_id}, v{self.meta.version}, caps={self.capabilities})"


# ============================================================
# SkillPatch — 技能补丁
# ============================================================

@dataclass
class SkillPatch:
    """技能补丁（Skill Learning 产出）"""
    domain: str
    added_keywords: Dict[str, Dict[str, List[str]]] = field(default_factory=dict)
    added_constraints: List[str] = field(default_factory=list)
    added_examples: List[Dict[str, str]] = field(default_factory=list)
    added_forbidden: List[str] = field(default_factory=list)
    added_ontology: Dict[str, Any] = field(default_factory=dict)

    def save_pending(self, skill_id: str):
        """保存为待审核补丁"""
        pending_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            "prompts", "skills", "_pending_patches"
        )
        os.makedirs(pending_dir, exist_ok=True)
        filename = f"{skill_id.replace('.', '_')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.yaml"
        filepath = os.path.join(pending_dir, filename)
        with open(filepath, "w", encoding="utf-8") as f:
            yaml.dump({
                "domain": self.domain,
                "added_keywords": self.added_keywords,
                "added_constraints": self.added_constraints,
                "added_examples": self.added_examples,
                "added_forbidden": self.added_forbidden,
                "added_ontology": self.added_ontology,
            }, f, allow_unicode=True, default_flow_style=False)


# ============================================================
# ReviewReport — 多维评审报告
# ============================================================

@dataclass
class DimensionScore:
    """单个维度评分"""
    score: float = 0.0
    weight: float = 0.2
    issues: List[Dict[str, str]] = field(default_factory=list)
    suggestion: str = ""

    def to_dict(self) -> dict:
        return {
            "score": self.score,
            "weight": self.weight,
            "issues": self.issues,
            "suggestion": self.suggestion,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "DimensionScore":
        return cls(
            score=data.get("score", 0.0),
            weight=data.get("weight", 0.2),
            issues=data.get("issues", []),
            suggestion=data.get("suggestion", ""),
        )


@dataclass
class ReviewReport:
    """多维评审报告 — 替代单一 score"""
    reviewer: str = ""  # 空字符串表示使用 ModelRegistry 默认模型
    skill_domain: str = "daily"
    timestamp: str = ""

    # 六维评分
    dimensions: Dict[str, DimensionScore] = field(default_factory=dict)

    # 综合指标
    weighted_score: float = 0.0
    passed: bool = False

    # 风险
    risk_level: str = "low"  # low / medium / high / critical
    risk_factors: List[str] = field(default_factory=list)
    risk_mitigation: str = ""

    # 置信度
    confidence: float = 0.0

    # 难度
    difficulty_threshold: float = 0.0
    difficulty_level: str = "simple"  # simple / medium / complex / expert
    difficulty_reason: str = ""

    def to_dict(self) -> dict:
        return {
            "meta": {
                "reviewer": self.reviewer,
                "skill_domain": self.skill_domain,
                "timestamp": self.timestamp or datetime.now().isoformat(),
            },
            "dimensions": {k: v.to_dict() for k, v in self.dimensions.items()},
            "overall": {
                "weighted_score": round(self.weighted_score, 2),
                "pass": self.passed,
            },
            "risk": {
                "level": self.risk_level,
                "factors": self.risk_factors,
                "mitigation": self.risk_mitigation,
            },
            "confidence": self.confidence,
            "difficulty": {
                "threshold": round(self.difficulty_threshold, 2),
                "level": self.difficulty_level,
                "reason": self.difficulty_reason,
            },
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ReviewReport":
        meta = data.get("meta", {})
        overall = data.get("overall", {})
        risk = data.get("risk", {})
        difficulty = data.get("difficulty", {})

        dims = {}
        for name, dim_data in data.get("dimensions", {}).items():
            dims[name] = DimensionScore.from_dict(dim_data)

        return cls(
            reviewer=meta.get("reviewer", ""),
            skill_domain=meta.get("skill_domain", "daily"),
            timestamp=meta.get("timestamp", ""),
            dimensions=dims,
            weighted_score=overall.get("weighted_score", 0.0),
            passed=overall.get("pass", False),
            risk_level=risk.get("level", "low"),
            risk_factors=risk.get("factors", []),
            risk_mitigation=risk.get("mitigation", ""),
            confidence=data.get("confidence", 0.0),
            difficulty_threshold=difficulty.get("threshold", 0.0),
            difficulty_level=difficulty.get("level", "simple"),
            difficulty_reason=difficulty.get("reason", ""),
        )


# ============================================================
# V3 Learning Engine — KnowledgePatch & WorkflowPatch
# ============================================================

@dataclass
class KnowledgePatch:
    """知识补丁（Learning Engine V3 产出）"""
    concept_name: str
    definition: str
    domain: str = "root"
    related_concepts: List[str] = field(default_factory=list)
    confidence: float = 0.8
    source: str = "auto_extract"

    def to_dict(self) -> dict:
        return {
            "concept_name": self.concept_name,
            "definition": self.definition,
            "domain": self.domain,
            "related_concepts": self.related_concepts,
            "confidence": self.confidence,
            "source": self.source,
        }


@dataclass
class WorkflowPatch:
    """工作流补丁（Learning Engine V3 产出）"""
    task_type: str
    steps: List[str] = field(default_factory=list)
    optimization: str = ""

    def to_dict(self) -> dict:
        return {
            "task_type": self.task_type,
            "steps": self.steps,
            "optimization": self.optimization,
        }


@dataclass
class ReasoningPatch:
    """推理模式补丁（Learning Engine V3 产出）

    与 ReasoningNode 配合使用：
    - LearningEngine.learn() 从文本中提取推理模式 → 生成 ReasoningPatch
    - PatchValidator.validate_reasoning() 校验 ReasoningPatch
    - 通过后注册到 ReasoningGraph
    """
    pattern_id: str
    pattern_name: str
    pattern_type: str  # analysis_pattern / writing_pattern / coding_pattern / ...
    steps: List[str] = field(default_factory=list)
    applicable_domains: List[str] = field(default_factory=list)
    applicable_task_types: List[str] = field(default_factory=list)
    template: str = ""
    confidence: float = 0.8
    source: str = "auto_extract"

    def to_dict(self) -> dict:
        return {
            "pattern_id": self.pattern_id,
            "pattern_name": self.pattern_name,
            "pattern_type": self.pattern_type,
            "steps": self.steps,
            "applicable_domains": self.applicable_domains,
            "applicable_task_types": self.applicable_task_types,
            "template": self.template,
            "confidence": self.confidence,
            "source": self.source,
        }


# ============================================================
# IntentCacheEntry — 意图缓存条目
# ============================================================

@dataclass
class IntentCacheEntry:
    """意图缓存条目"""
    fingerprint: str
    original_query: str
    normalized_query: str
    detected_domain: str
    skill_path: List[str] = field(default_factory=list)
    result: Optional[Dict[str, Any]] = None
    created_at: str = ""
    ttl: int = 300
    hit_count: int = 0
    confidence: float = 0.0

    def is_expired(self) -> bool:
        if not self.created_at:
            return False
        try:
            created = datetime.fromisoformat(self.created_at)
            return (datetime.now() - created).total_seconds() > self.ttl
        except (ValueError, TypeError):
            return False

    def hit(self):
        self.hit_count += 1

    def to_dict(self) -> dict:
        return {
            "fingerprint": self.fingerprint,
            "original_query": self.original_query,
            "normalized_query": self.normalized_query,
            "detected_domain": self.detected_domain,
            "skill_path": self.skill_path,
            "result": self.result,
            "created_at": self.created_at,
            "ttl": self.ttl,
            "hit_count": self.hit_count,
            "confidence": self.confidence,
        }