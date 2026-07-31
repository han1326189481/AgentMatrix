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
        )


class PersonalBrain:
    """个人智脑 — 系统的用户感知层（JSON 文件持久化）"""

    # 文件 I/O 锁（线程安全）
    _file_lock = threading.Lock()

    def __init__(self, user_id: str):
        self.user_id = user_id
        self.profile = self._load_profile()
        self.capability = CapabilityGraph(user_id)

    @property
    def _profile_path(self) -> str:
        """获取用户画像文件路径"""
        return os.path.join(get_profiles_dir(), f"{self.user_id}.json")

    def build_context(self) -> str:
        """构建注入 Prompt 的上下文字符串"""
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
        return "\n".join(parts)

    def update_from_session(self, session_data: dict):
        """从会话中更新画像并持久化到文件"""
        # 更新能力图谱
        skill_nodes = session_data.get("skill_nodes", [])
        for node_id in skill_nodes:
            self.capability.update(node_id, "practice",
                                   evidence=f"会话 {session_data.get('session_id')}")

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