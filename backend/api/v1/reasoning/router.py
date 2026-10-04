"""Reasoning Graph API 路由

GET  /api/v1/reasoning/patterns — 获取所有推理模式列表
POST /api/v1/reasoning/match    — 匹配最佳推理模式
"""

from fastapi import APIRouter, HTTPException
from typing import List, Optional
from pydantic import BaseModel

router = APIRouter(prefix="", tags=["reasoning"])

# 模块级单例，保证 usage_count 等状态在请求间持久
_reasoning_graph_instance = None


def _get_reasoning_graph():
    global _reasoning_graph_instance
    if _reasoning_graph_instance is None:
        from core.graphs.reasoning_graph import ReasoningGraph
        _reasoning_graph_instance = ReasoningGraph()
    return _reasoning_graph_instance


class PatternItem(BaseModel):
    pattern_id: str
    pattern_name: str
    pattern_type: str
    steps: List[str] = []
    applicable_domains: List[str] = []
    applicable_task_types: List[str] = []
    usage_count: int = 0
    avg_effectiveness: float = 0.0


class PatternsResponse(BaseModel):
    patterns: List[PatternItem]
    total: int


class MatchRequest(BaseModel):
    task_type: str
    domain: Optional[str] = ""
    keywords: Optional[List[str]] = []


class MatchResponse(BaseModel):
    matched: bool
    pattern: Optional[PatternItem] = None


def _to_pattern_item(pattern) -> PatternItem:
    return PatternItem(
        pattern_id=pattern.pattern_id,
        pattern_name=pattern.pattern_name,
        pattern_type=pattern.pattern_type,
        steps=list(pattern.steps),
        applicable_domains=list(pattern.applicable_domains),
        applicable_task_types=list(pattern.applicable_task_types),
        usage_count=pattern.usage_count,
        avg_effectiveness=pattern.avg_effectiveness,
    )


@router.get("/patterns", response_model=PatternsResponse)
async def get_patterns():
    """获取所有推理模式列表"""
    try:
        graph = _get_reasoning_graph()
        patterns = [_to_pattern_item(p) for p in graph.get_all_patterns()]
        return PatternsResponse(patterns=patterns, total=len(patterns))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取推理模式列表异常: {str(e)}")


@router.post("/match", response_model=MatchResponse)
async def match_pattern(body: MatchRequest):
    """匹配最佳推理模式

    匹配优先级:
    1. task_type + domain 完全匹配
    2. task_type 匹配
    3. domain 匹配
    4. 关键词匹配
    """
    try:
        graph = _get_reasoning_graph()
        pattern = graph.match(
            task_type=body.task_type,
            domain=body.domain or "",
            keywords=body.keywords or [],
        )
        if pattern is None:
            return MatchResponse(matched=False, pattern=None)
        return MatchResponse(matched=True, pattern=_to_pattern_item(pattern))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"推理模式匹配异常: {str(e)}")
