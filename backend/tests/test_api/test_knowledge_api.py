import pytest
from knowledge.service import KnowledgeService


class TestKnowledgeService:
    def test_search(self):
        service = KnowledgeService()
        results = service.search("AI")
        
        assert isinstance(results, dict)
        assert "AI" in results

    def test_add_knowledge(self):
        service = KnowledgeService()
        service.add_knowledge("test_keyword", ["test content"])
        
        result = service.get_knowledge_by_keyword("test_keyword")
        assert result is not None
        assert "test content" in result
        
        service.delete_knowledge("test_keyword")

    def test_enhance_content(self):
        service = KnowledgeService()
        enhanced = service.enhance_content("测试内容", ["AI"])
        
        assert "知识增强" in enhanced
        assert "测试内容" in enhanced

    def test_get_stats(self):
        service = KnowledgeService()
        stats = service.get_knowledge_stats()
        
        assert "total_keywords" in stats
        assert "total_items" in stats
        assert stats["total_keywords"] > 0
