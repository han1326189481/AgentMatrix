"""Personal Brain — 用户认知画像（JSON 文件持久化）

七维画像:
1. Identity   — 身份（学生/开发者/管理者）
2. Goal       — 长期目标
3. Preference — 表达偏好
4. Capability — 能力图谱
5. Project    — 当前项目
6. Memory     — 关键记忆
7. Context    — 会话上下文

持久化路径: storage/profiles/{user_id}.json
"""

from dataclasses import dataclass, field, asdict
from typing import List, Dict, Optional
import json
import os
import shutil
import threading
import logging
from shared.platform import get_profiles_dir
from core.graphs.capability_graph import CapabilityGraph

logger = logging.getLogger(__name__)


@dataclass
class UserProfile:
    user_id: str
    display_name: str = ""
    identity: str = ""              # "student" | "developer" | "researcher" | "professional"
    long_term_goals: List[str] = field(default_factory=list)
    preferences: Dict = field(default_factory=dict)
    expression_style: str = ""      # "concise_technical" | "verbose_explanatory"
    learning_stage: str = ""        # "beginner" | "intermediate" | "advanced"
    # ---- 以下为「画像信息自动填写模板」所需的身份字段（2026-10-10 新增）----
    #: 均由纯正则抽取器写入，需用户确认后才落盘（见 extractor 的 CONFIRM_REQUIRED）
    school: str = ""                # 学校全称，如「XX大学」
    school_short: str = ""          # 学校简称/校区
    major: str = ""                 # 专业，如「计算机科学与技术」
    class_name: str = ""            # 班级，如「计科2301」
    grade_year: str = ""            # 年级，如「2023级」/「大三」
    degree_stage: str = ""          # 培养阶段，如「本科」/「硕士」
    #: 学号等强身份标识**不入画像**（见 extractor.SENSITIVE_FIELDS）。
    #: 本地画像只保留「用于填模板且语义粗粒度」的字段，强标识不进内存更不进云端。

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "UserProfile":
        return cls(
            user_id=data.get("user_id", ""),
            display_name=data.get("display_name", ""),
            identity=data.get("identity", ""),
            long_term_goals=data.get("long_term_goals", []),
            preferences=data.get("preferences", {}),
            expression_style=data.get("expression_style", ""),
            learning_stage=data.get("learning_stage", ""),
            school=data.get("school", ""),
            school_short=data.get("school_short", ""),
            major=data.get("major", ""),
            class_name=data.get("class_name", ""),
            grade_year=data.get("grade_year", ""),
            degree_stage=data.get("degree_stage", ""),
        )


class PersonalBrain:
    """个人智脑 — 系统的用户感知层（JSON 文件持久化）"""

    # 文件 I/O 锁（线程安全）
    _file_lock = threading.Lock()

    def __init__(self, user_id: str):
        self.user_id = user_id
        self.profile = self._load_profile()
        self.capability = CapabilityGraph(user_id)
        self._load_capability()

    @property
    def _profile_path(self) -> str:
        """获取用户画像文件路径"""
        return os.path.join(get_profiles_dir(), f"{self.user_id}.json")

    def build_context(self) -> str:
        """构建注入 Prompt 的上下文字符串。

        ⚠️ 安全边界（2026-10-10 佳文确认的设计）：
        画像**存储在本地**，但本方法返回的字符串会作为 prompt 上下文
        在 Judge 判走云端增强时被一并外发。因此这里**只输出粗粒度标签**，
        姓名/学号/班级等原始值一律不进上下文。
        正确表述是「本地存储 + 外发前脱敏」，而非「绝不外发」。
        """
        parts = []
        if self.profile.identity:
            parts.append(f"用户身份: {self.profile.identity}")
        if self.profile.long_term_goals:
            parts.append(f"长期目标: {', '.join(self.profile.long_term_goals)}")
        if self.profile.preferences:
            prefs = ", ".join(f"{k}={v}" for k, v in self.profile.preferences.items())
            parts.append(f"偏好: {prefs}")
        if self.profile.expression_style:
            parts.append(f"表达风格: {self.profile.expression_style}")
        if self.profile.learning_stage:
            parts.append(f"学习阶段: {self.profile.learning_stage}")
        # ---- 身份字段：只放粗粒度脱敏结果，原始值绝不进 prompt ----
        masked = self.masked_identity()
        if masked:
            parts.append(f"背景(已脱敏): {', '.join(f'{k}={v}' for k, v in masked.items())}")
        return "\n".join(parts)

    def masked_identity(self) -> dict:
        """返回可外发的粗粒度身份描述（纯规则，零模型）。

        ⚠️ 姓名**不参与**：姓名在中文语境下无法模糊化到仍有信息量，
        而模板自动填充走的是本地路径，不需要外发。
        """
        try:
            from core.engines.profile_extractor import mask_for_cloud
            return mask_for_cloud({
                "major": self.profile.major,
                "class_name": self.profile.class_name,
                "degree_stage": self.profile.degree_stage,
                "grade_year": self.profile.grade_year,
            })
        except Exception as e:
            logger.warning(f"masked_identity 失败，退回空结果: {e}")
            return {}

    def autofill_variables(self, variables: list) -> list:
        """用本地画像回填模板变量（**仅本地**，不进 prompt）。

        绑定规则见 core/engines/profile_autofill.py 的 BINDINGS。
        仅当画像字段有值、且该变量**尚无 default_value** 时才写入。
        """
        try:
            from core.engines.profile_autofill import autofill_variables
            return autofill_variables(variables, {
                "display_name": self.profile.display_name,
                "school": self.profile.school or self.profile.school_short,
                "major": self.profile.major,
                "class_name": self.profile.class_name,
                "grade_year": self.profile.grade_year,
                "degree_stage": self.profile.degree_stage,
            })
        except Exception as e:
            logger.warning(f"autofill_variables 失败，返回原变量: {e}")
            return variables

    def update_from_session(self, session_data: dict):
        """从会话中更新画像并持久化到文件"""
        # 更新能力图谱
        skill_nodes = session_data.get("skill_nodes", [])
        for node_id in skill_nodes:
            self.capability.update(node_id, "practice",
                                   evidence=f"会话 {session_data.get('session_id')}")

        # ⚠️ 2026-10-10 修正：能力图谱的改动原先完全不落盘。
        # 这里的 capability.update() 只改内存，随后 if has_changes 为假时
        # 连 _save_profile() 都不调 → 会话里练过的技能重启即丢，
        # 且 API 层 PATCH /capability 也是无效写入（对象随请求丢弃）。
        # 现在能力图谱与画像同文件同生命周期，任一变更都触发持久化。
        capability_changed = bool(skill_nodes)

        # 根据技能节点推断用户身份
        has_changes = False
        if skill_nodes:
            domain = skill_nodes[-1] if len(skill_nodes) > 1 else "daily"
            new_identity = self.profile.identity
            if domain in ("coding", "tech", "ai"):
                new_identity = "developer"
            elif domain in ("education", "campus", "academic"):
                new_identity = "student"
            elif domain in ("business", "office"):
                new_identity = "professional"

            if new_identity and new_identity != self.profile.identity:
                self.profile.identity = new_identity
                has_changes = True

            if not self.profile.learning_stage:
                self.profile.learning_stage = "intermediate"
                has_changes = True

            if has_changes:
                self._save_profile()

        if capability_changed:
            self._save_capability()

    # ---- 身份信息抽取（2026-10-10 新增，纯规则零模型）----

    def extract_profile_from_text(self, text: str) -> dict:
        """从用户输入抽取身份信息，**不落盘**，供上层做确认弹窗。

        Returns:
            ExtractionResult.to_dict()：
            {"fields": {...}, "evidence": {...},
             "sensitive_found": [...], "pending_confirm": true}

        ⚠️ 抽取结果**必须经用户确认**才能调 apply_extracted_profile 落盘。
        误抽取比漏抽取危险：把错学号填进开题报告比不填严重得多。
        """
        try:
            from core.engines.profile_extractor import ProfileExtractor
            return ProfileExtractor().extract(text).to_dict()
        except Exception as e:
            logger.warning(f"extract_profile_from_text 失败: {e}")
            return {"fields": {}, "evidence": {}, "sensitive_found": [],
                    "pending_confirm": True}

    def apply_extracted_profile(self, fields: Dict[str, str],
                                confirmed: bool = False) -> Dict[str, str]:
        """把已确认的身份字段写入画像并落盘。

        Args:
            fields:    字段名 → 值（必须是 UserProfile 上的合法字段）
            confirmed: 是否已经过用户确认。**False 时只返回将要写入的内容，不落盘。**

        Returns:
            {"applied": [...], "skipped": [...]}，applied 为实际写入的字段名。
        """
        allowed = {"display_name", "school", "school_short", "major",
                   "class_name", "grade_year", "degree_stage"}
        applied, skipped = [], []

        for key, val in (fields or {}).items():
            if key not in allowed:
                skipped.append(key)
                continue
            if not str(val or "").strip():
                continue
            setattr(self.profile, key, str(val).strip())
            applied.append(key)

        if not confirmed:
            # 未确认：只回显，不落盘
            return {"applied": [], "pending": applied, "skipped": skipped}

        if applied:
            self._save_profile()
        return {"applied": applied, "skipped": skipped}

    def _load_profile(self) -> UserProfile:
        """从 JSON 文件加载用户画像，文件不存在时返回空画像"""
        try:
            if os.path.exists(self._profile_path):
                with self._file_lock:
                    with open(self._profile_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                profile = UserProfile.from_dict(data)
                logger.debug(f"Profile loaded: {self._profile_path} (identity={profile.identity})")
                return profile
        except json.JSONDecodeError as e:
            logger.warning(f"Profile file corrupted, resetting: {self._profile_path} error={e}")
        except Exception as e:
            logger.warning(f"Failed to load profile: {self._profile_path} error={e}")

        return UserProfile(user_id=self.user_id)

    def _save_profile(self):
        """将用户画像持久化到 JSON 文件"""
        try:
            with self._file_lock:
                with open(self._profile_path, "w", encoding="utf-8") as f:
                    json.dump(self.profile.to_dict(), f, ensure_ascii=False, indent=2)
            logger.debug(f"Profile saved: {self._profile_path}")
        except Exception as e:
            logger.error(f"Failed to save profile: {self._profile_path} error={e}")

    # ============================================================
    # 能力图谱持久化（2026-10-10 新增，修「PATCH 无效写入」）
    #
    # 与画像共用同一个 JSON 文件的 `capability` 子键，而不是另开文件。
    # 理由：复用 `_profile_path` ⇒ 自动沿用 conftest 里
    # `_isolate_personal_brain_profiles` 对 `get_profiles_dir` 的 patch，
    # 不需要为能力图谱再写一条 fixture，也就不存在「新路径忘记隔离」
    # 这个 9/24 同款漏网口。
    # ============================================================

    def _load_capability(self):
        """从画像文件恢复能力图谱；文件不存在或无该键时保持为空图。"""
        try:
            if not os.path.exists(self._profile_path):
                return
            with self._file_lock:
                with open(self._profile_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
            raw = data.get("capability")
            if not raw:
                return
            self.capability = CapabilityGraph.from_dict(raw, user_id=self.user_id)
            logger.debug(
                f"Capability restored: {len(self.capability.nodes)} 节点"
            )
        except json.JSONDecodeError as e:
            # 文件损坏时画像已单独处理过；这里静默降级为空图，
            # 不能因能力图谱读不出来就让整个 PersonalBrain 构造失败。
            logger.warning(f"Capability data unreadable, starting empty: {e}")
        except Exception as e:
            logger.warning(f"Failed to load capability: {e}")

    def _save_capability(self):
        """把能力图谱写回画像文件的 `capability` 子键（原子写 + 保留 .bak）。

        不整体重写 profile 子键 —— 只改 capability 那一个字段，
        避免并发下把画像字段写成旧值。
        """
        try:
            data = {}
            if os.path.exists(self._profile_path):
                with self._file_lock:
                    with open(self._profile_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
            data["capability"] = self.capability.to_dict()

            with self._file_lock:
                if os.path.exists(self._profile_path):
                    shutil.copy2(self._profile_path, self._profile_path + ".bak")
                tmp = self._profile_path + ".tmp"
                with open(tmp, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                os.replace(tmp, self._profile_path)
            logger.debug(
                f"Capability saved: {len(self.capability.nodes)} 节点"
            )
        except Exception as e:
            logger.error(
                f"Failed to save capability: {self._profile_path} error={e}"
            )

    def save(self):
        """显式持久化画像 + 能力图谱。

        API 层改完能力等级后必须调用，否则改动只存在于请求生命周期内的
        临时对象上（这正是 PATCH 失效的根因）。
        """
        self._save_profile()
        self._save_capability()