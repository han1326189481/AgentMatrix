"""知识库子包。

V2.5 (2026-10-04) 修正导出
--------------------------
原先这里 `from .service import KnowledgeService` —— 导出的是**旧的 JSON 字典实现**，
而生产实际使用的是 `knowledge/mysql_service.py` 里的 **SQLite 实现**（同名类）。
两个类同名同职责、导出指向未在役的那一个，是本包最容易误导人的历史坑。

旧实现（`knowledge/service.py`）已删除。现在统一导出 SQLite 实现。
"""

from .mysql_service import KnowledgeService, get_knowledge_service

__all__ = ["KnowledgeService", "get_knowledge_service"]
