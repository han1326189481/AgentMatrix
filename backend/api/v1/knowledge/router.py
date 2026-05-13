from fastapi import APIRouter, Depends, HTTPException
from typing import Dict, Any, List
from pydantic import BaseModel
from knowledge.service import KnowledgeService

router = APIRouter()

_knowledge_service = KnowledgeService()


class KnowledgeItem(BaseModel):
    keyword: str
    content: List[str]


@router.get("/")
async def get_all_knowledge():
    stats = _knowledge_service.get_knowledge_stats()
    return {
        "knowledge_base": _knowledge_service.knowledge_base,
        "keywords": _knowledge_service.get_all_keywords(),
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
async def add_knowledge(item: KnowledgeItem):
    _knowledge_service.add_knowledge(item.keyword, item.content)
    return {"status": "success", "keyword": item.keyword}


@router.put("/keyword/{keyword}")
async def update_knowledge(keyword: str, content: List[str]):
    success = _knowledge_service.update_knowledge(keyword, content)
    if not success:
        raise HTTPException(status_code=404, detail=f"Keyword {keyword} not found")
    return {"status": "success", "keyword": keyword}


@router.delete("/keyword/{keyword}")
async def delete_knowledge(keyword: str):
    success = _knowledge_service.delete_knowledge(keyword)
    if not success:
        raise HTTPException(status_code=404, detail=f"Keyword {keyword} not found")
    return {"status": "success", "keyword": keyword}


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
