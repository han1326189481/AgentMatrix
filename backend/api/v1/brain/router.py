"""Personal Brain API 路由

GET   /api/v1/brain/{user_id}             — 获取用户画像
GET   /api/v1/brain/{user_id}/capability   — 获取能力图谱
PATCH /api/v1/brain/{user_id}/capability   — 更新能力等级
"""

from fastapi import APIRouter, HTTPException
from typing import List, Dict, Optional
from pydantic import BaseModel

router = APIRouter(prefix="", tags=["brain"])


# 合法 proficiency 取值（与 Proficiency 枚举一致）
VALID_PROFICIENCY = {"none", "theory", "practice", "proficient", "expert"}


class UserProfileResponse(BaseModel):
    user_id: str
    display_name: str = ""
    identity: str = ""
    long_term_goals: List[str] = []
    preferences: Dict = {}
    expression_style: str = ""
    learning_stage: str = ""


class CapabilityNodeItem(BaseModel):
    skill_node_id: str
    proficiency: str
    evidence: List[str] = []
    last_practiced: Optional[str] = None
    practice_count: int = 0


class CapabilityResponse(BaseModel):
    user_id: str
    nodes: List[CapabilityNodeItem]
    total: int


class CapabilityUpdateRequest(BaseModel):
    skill_node_id: str
    proficiency: str  # none | theory | practice | proficient | expert
    evidence: Optional[str] = None


class CapabilityUpdateResponse(BaseModel):
    status: str
    user_id: str
    skill_node_id: str
    proficiency: str


@router.get("/{user_id}", response_model=UserProfileResponse)
async def get_user_profile(user_id: str):
    """获取用户画像"""
    try:
        from core.personal_brain.brain import PersonalBrain
        brain = PersonalBrain(user_id=user_id)
        profile = brain.profile
        return UserProfileResponse(
            user_id=profile.user_id,
            display_name=profile.display_name,
            identity=profile.identity,
            long_term_goals=profile.long_term_goals,
            preferences=profile.preferences,
            expression_style=profile.expression_style,
            learning_stage=profile.learning_stage,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取用户画像异常: {str(e)}")


@router.get("/{user_id}/capability", response_model=CapabilityResponse)
async def get_user_capability(user_id: str):
    """获取用户能力图谱"""
    try:
        from core.personal_brain.brain import PersonalBrain
        brain = PersonalBrain(user_id=user_id)
        cap = brain.capability
        nodes = [
            CapabilityNodeItem(
                skill_node_id=n.skill_node_id,
                proficiency=n.proficiency.value if hasattr(n.proficiency, "value") else str(n.proficiency),
                evidence=n.evidence,
                last_practiced=n.last_practiced,
                practice_count=n.practice_count,
            )
            for n in cap.nodes.values()
        ]
        return CapabilityResponse(user_id=user_id, nodes=nodes, total=len(nodes))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取能力图谱异常: {str(e)}")


@router.patch("/{user_id}/capability", response_model=CapabilityUpdateResponse)
async def update_user_capability(user_id: str, body: CapabilityUpdateRequest):
    """更新用户能力等级"""
    if body.proficiency not in VALID_PROFICIENCY:
        raise HTTPException(
            status_code=400,
            detail=f"无效的 proficiency: '{body.proficiency}', 必须是 {sorted(VALID_PROFICIENCY)} 之一",
        )
    try:
        from core.personal_brain.brain import PersonalBrain
        from core.graphs.capability_graph import Proficiency
        brain = PersonalBrain(user_id=user_id)
        proficiency_enum = Proficiency(body.proficiency)
        brain.capability.update(
            body.skill_node_id,
            proficiency_enum,
            evidence=body.evidence or "",
        )
        return CapabilityUpdateResponse(
            status="updated",
            user_id=user_id,
            skill_node_id=body.skill_node_id,
            proficiency=body.proficiency,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"更新能力等级异常: {str(e)}")
