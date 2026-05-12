from fastapi import APIRouter, Depends, HTTPException
from typing import Dict, Any, List
from pydantic import BaseModel

router = APIRouter()


class KnowledgeQuery(BaseModel):
    query: str
    top_k: int = 5


class KnowledgeEntry(BaseModel):
    id: str
    content: str
    score: float
    category: str


@router.post("/query", response_model=List[KnowledgeEntry])
async def query_knowledge(query: KnowledgeQuery):
    return [
        KnowledgeEntry(
            id="1",
            content="示例知识库内容1",
            score=0.95,
            category="general"
        ),
        KnowledgeEntry(
            id="2",
            content="示例知识库内容2",
            score=0.88,
            category="general"
        )
    ]


@router.get("/categories")
async def get_categories():
    return ["general", "technical", "business", "product"]


@router.post("/add")
async def add_knowledge(entry: Dict[str, Any]):
    return {"status": "success", "message": "知识条目已添加"}


@router.delete("/{entry_id}")
async def delete_knowledge(entry_id: str):
    return {"status": "success", "message": "知识条目已删除"}