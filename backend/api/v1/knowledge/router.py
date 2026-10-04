"""知识库 API 路由 - MySQL 持久化版本"""
from fastapi import APIRouter, HTTPException
from typing import List
from pydantic import BaseModel
from knowledge.mysql_service import get_knowledge_service

router = APIRouter()

_knowledge_service = get_knowledge_service()


class KnowledgeItemModel(BaseModel):
    keyword: str
    content: List[str]


class KnowledgeAddModel(BaseModel):
    keyword: str
    content: str
    category: str = "general"
    confidence: float = 0.8
    source: str = "system"


@router.get("/")
async def get_all_knowledge():
    stats = _knowledge_service.get_knowledge_stats()
    keywords = _knowledge_service.get_all_keywords()
    return {
        "keywords": keywords,
        "stats": stats
    }


@router.get("/stats")
async def get_knowledge_stats():
    return _knowledge_service.get_knowledge_stats()


@router.get("/keyword/{keyword}")
async def get_knowledge_by_keyword(keyword: str):
    content = _knowledge_service.get_knowledge_by_keyword(keyword)
    if content is None:
        raise HTTPException(status_code=404, detail=f"Keyword {keyword} not found")
    return {
        "keyword": keyword,
        "content": content
    }


@router.post("/")
async def add_knowledge(item: KnowledgeAddModel):
    kid = _knowledge_service.add_knowledge(
        item.keyword, item.content, item.category, item.confidence, item.source
    )
    return {"status": "success", "keyword": item.keyword, "id": kid}


@router.put("/keyword/{keyword}")
async def update_knowledge(keyword: str, content: str):
    success = _knowledge_service.update_knowledge(keyword, content)
    if not success:
        raise HTTPException(status_code=404, detail=f"Keyword {keyword} not found")
    return {"status": "success", "keyword": keyword}


@router.delete("/keyword/{keyword}")
async def delete_knowledge(keyword: str):
    count = _knowledge_service.delete_knowledge(keyword)
    if count == 0:
        raise HTTPException(status_code=404, detail=f"Keyword {keyword} not found")
    return {"status": "success", "keyword": keyword, "deleted": count}


@router.get("/search")
async def search_knowledge(query: str, limit: int = 5):
    results = _knowledge_service.search(query, limit)
    return {
        "query": query,
        "results": results,
        "count": len(results)
    }


@router.post("/enhance")
async def enhance_content(content: str, keywords: List[str]):
    enhanced = _knowledge_service.enhance_content(content, keywords)
    return {
        "original": content,
        "enhanced": enhanced,
        "keywords": keywords
    }


@router.get("/categories")
async def get_categories():
    return {"categories": _knowledge_service.get_all_categories()}