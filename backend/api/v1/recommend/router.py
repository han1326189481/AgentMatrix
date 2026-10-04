"""知识推荐 API 路由

GET /api/v1/recommend — 基于 Skill Graph + Capability Graph 的精准推荐
"""

from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional
from pydantic import BaseModel

router = APIRouter()


class RecommendationItem(BaseModel):
    type: str
    node: str
    node_id: str
    reason: str
    priority: float


class RecommendationResponse(BaseModel):
    should_intervene: bool
    recommendations: List[RecommendationItem]
    reason: str
    total: int


@router.get("/", response_model=RecommendationResponse)
async def get_recommendations(
    user_id: str = Query("default", description="用户ID"),
    current_task: str = Query("", description="当前任务描述"),
    active_nodes: str = Query("", description="逗号分隔的活跃节点ID列表"),
    limit: int = Query(5, ge=1, le=20, description="最大推荐数"),
):
    """获取知识推荐

    基于四类来源推荐：
    1. 当前任务的子主题（has_part）
    2. 学习路径下一步（next_step）
    3. 能力图谱缺口（Capability Graph）
    4. 长期目标的前置知识（Goal prerequisite）
    """
    try:
        from core.graphs import get_skill_graph
        from core.engines.knowledge_recommendation import KnowledgeRecommendation

        skill_graph = get_skill_graph()

        # 构建 PersonalBrain
        try:
            from core.personal_brain.brain import PersonalBrain
            brain = PersonalBrain(user_id=user_id)
        except ImportError:
            brain = None

        # 解析活跃节点
        node_list = [n.strip() for n in active_nodes.split(",") if n.strip()] if active_nodes else []

        recommender = KnowledgeRecommendation(skill_graph, brain)
        result = recommender.recommend_for_context(
            current_task=current_task,
            active_nodes=node_list,
            intent_graph=None,
            limit=limit,
        )

        return RecommendationResponse(**result)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"推荐服务异常: {str(e)}")


@router.get("/health")
async def recommend_health():
    """推荐服务健康检查"""
    return {
        "status": "ok",
        "service": "knowledge_recommendation",
        "version": "v3.0"
    }