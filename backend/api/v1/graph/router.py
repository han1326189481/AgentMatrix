"""Skill Graph API 路由

GET /api/v1/graph/stats  — Skill Graph 统计信息
GET /api/v1/graph/search — Skill Graph 节点搜索
"""

from fastapi import APIRouter, HTTPException, Query
from typing import List, Dict
from pydantic import BaseModel

router = APIRouter(prefix="", tags=["graph"])


class GraphStatsResponse(BaseModel):
    total_nodes: int
    total_edges: int
    domain_nodes: int
    concept_nodes: int
    skill_nodes: int
    edge_types: Dict[str, int]


class GraphNodeItem(BaseModel):
    id: str
    name: str
    node_type: str
    domain: str = ""
    description: str = ""
    metadata: Dict = {}


class GraphSearchResponse(BaseModel):
    query: str
    results: List[GraphNodeItem]
    count: int


@router.get("/stats", response_model=GraphStatsResponse)
async def get_graph_stats():
    """获取 Skill Graph 统计信息"""
    try:
        from core.graphs import get_skill_graph
        skill_graph = get_skill_graph()
        stats = skill_graph.stats()
        return GraphStatsResponse(**stats)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Skill Graph 统计异常: {str(e)}")


@router.get("/search", response_model=GraphSearchResponse)
async def search_graph(
    q: str = Query(..., description="搜索关键词"),
    top_k: int = Query(5, ge=1, le=50, description="返回结果数量"),
):
    """搜索 Skill Graph 节点（关键词匹配）"""
    try:
        from core.graphs import get_skill_graph
        skill_graph = get_skill_graph()
        nodes = skill_graph.search_by_name(q, top_k=top_k)
        results = [GraphNodeItem(**n.to_dict()) for n in nodes]
        return GraphSearchResponse(query=q, results=results, count=len(results))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Skill Graph 搜索异常: {str(e)}")
