"""知识库服务测试 — 针对**在役的 SQLite 实现**。

V2.5 (2026-10-04) 重写说明
--------------------------
本文件原先 `from knowledge.service import KnowledgeService`，测的是**旧版 JSON 字典实现**
（`backend/knowledge/service.py`）。那个实现与 `knowledge/mysql_service.py` 的 SQLite 实现
**同名同职责**，而 `knowledge/__init__.py` 导出的恰恰是旧的那个 —— 于是：

1. 这个测试跑绿了**完全不反映生产知识库**（断言命中的是旧实现里硬编码的内置字典）；
2. 旧实现的 `_save_knowledge_base()` 还会把仓库内 `knowledge/knowledge_base.json` 整文件重写。

旧实现已删除，测试改为打在役实现，并用**临时 SQLite 库**隔离，
绝不触碰 `backend/storage/agentmatrix.db`。
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


@pytest.fixture()
def kb(tmp_path, monkeypatch):
    """真实 SQLite KnowledgeService + 临时数据库（隔离生产库）"""
    from app.database import Base
    import models.knowledge  # noqa: F401 — 把 KnowledgeItem 注册到 Base.metadata
    import knowledge.mysql_service as ms

    engine = create_engine(f"sqlite:///{tmp_path / 'kb.db'}")
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    # 拦掉模块级导入的 get_global_session，全部方法都走临时库
    monkeypatch.setattr(ms, "get_global_session", lambda: SessionLocal())

    service = ms.KnowledgeService()
    service.seed_default_knowledge()
    try:
        yield service
    finally:
        engine.dispose()


def test_export_points_to_sqlite_implementation():
    """`from knowledge import KnowledgeService` 必须拿到在役的 SQLite 实现

    这是本次要锁死的回归点：旧实现曾与 SQLite 实现同名，且被 __init__ 优先导出，
    导致外部拿到的是未在役的类。
    """
    from knowledge import KnowledgeService as exported
    from knowledge import get_knowledge_service as exported_factory
    from knowledge.mysql_service import (
        KnowledgeService as sqlite_impl,
        get_knowledge_service as sqlite_factory,
    )

    assert exported is sqlite_impl
    assert exported_factory is sqlite_factory
    assert callable(exported_factory)


def test_seed_and_stats(kb):
    stats = kb.get_knowledge_stats()
    assert set(stats) >= {"total_keywords", "total_items", "total_categories", "cache_size"}
    assert stats["total_items"] > 0
    assert stats["total_keywords"] > 0
    assert stats["total_categories"] > 0


def test_seed_is_idempotent(kb):
    """重复 seed 不应重复插入"""
    before = kb.get_knowledge_stats()["total_items"]
    assert kb.seed_default_knowledge() == 0
    assert kb.get_knowledge_stats()["total_items"] == before


def test_add_query_update_delete(kb):
    kid = kb.add_knowledge("测试关键词", "内容A", category="测试类", confidence=0.9, source="pytest")
    assert isinstance(kid, int)

    assert kb.get_knowledge_by_keyword("测试关键词") == ["内容A"]

    assert kb.update_knowledge("测试关键词", "内容B") is True
    assert kb.get_knowledge_by_keyword("测试关键词") == ["内容B"]

    assert "测试关键词" in kb.get_all_keywords()
    assert "测试类" in kb.get_all_categories()
    assert kb.get_knowledge_by_keyword("不存在的关键词") is None

    assert kb.delete_knowledge("测试关键词") == 1
    assert kb.get_knowledge_by_keyword("测试关键词") is None


def test_search_returns_dict_keyed_by_keyword(kb):
    results = kb.search("AI")
    assert isinstance(results, dict)
    assert "AI" in results
    assert all(isinstance(v, list) for v in results.values())


def test_search_by_keywords_and_category(kb):
    kb.add_knowledge("独有标签X", "独有内容X", category="独有分类X")
    assert "独有内容X" in kb.search_by_keywords(["独有标签X"])
    hits = kb.search_by_category("独有分类X")
    assert any(item["keyword"] == "独有标签X" for item in hits)


def test_enhance_content(kb):
    enhanced = kb.enhance_content("测试内容", ["AI"])
    assert "【知识增强】" in enhanced
    assert "测试内容" in enhanced


def test_enhance_content_without_match_returns_original(kb):
    """没有任何参考知识时，enhance 必须原样返回（不能凭空造内容）"""
    original = "一段毫无关键词命中的文本"
    assert kb.enhance_content(original, ["绝对不存在的关键词ZZZ"]) == original
