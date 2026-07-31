"""时效性知识库数据模型 V1.0 (2026-07-31)

与权威知识库(knowledge_base表)分离的第二持久化数据库。
存储场景：地点、美食、天气、旅行、网友评价等只需时效性、不需权威性的信息。

TTL机制：
- 存入时记录 created_at 和 expires_at
- 默认TTL=30天，超期自动标记 is_stale=True
- 用户再次提问相关内容时，若命中过期条目，触发web search更新
"""
from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, Index
from sqlalchemy.sql import func
from app.database import Base


class TimelyKnowledgeItem(Base):
    """时效性知识库条目（地点/美食/天气/旅行/评价等）"""
    __tablename__ = "timely_knowledge_base"

    id = Column(Integer, primary_key=True, autoincrement=True)
    # 查询关键词（用于检索匹配，如"北京牛街美食推荐"）
    query = Column(String(255), nullable=False, comment="用户原始查询或关键词")
    # 知识内容（web search返回的摘要）
    content = Column(Text, nullable=False, comment="时效性知识内容")
    # 分类：location/food/weather/travel/review/other
    category = Column(String(50), nullable=False, default="other", comment="分类")
    # 来源（如"web_search:deepseek"或具体URL）
    source = Column(String(255), nullable=False, default="web_search", comment="来源")
    # 置信度（web search结果通常0.6-0.8，不强制权威校验）
    confidence = Column(Integer, nullable=False, default=70, comment="置信度(0-100)")

    # TTL时效性字段
    created_at = Column(DateTime, server_default=func.now(), comment="存入时间")
    expires_at = Column(DateTime, nullable=False, comment="过期时间(默认30天后)")
    is_stale = Column(Boolean, nullable=False, default=False, comment="是否已过期(落后信息)")

    __table_args__ = (
        Index("idx_timely_query", "query"),
        Index("idx_timely_category", "category"),
        Index("idx_timely_stale", "is_stale"),
        Index("idx_timely_query_category", "query", "category"),
    )

    def __repr__(self):
        return f"<TimelyKnowledgeItem(query={self.query}, category={self.category}, is_stale={self.is_stale})>"
