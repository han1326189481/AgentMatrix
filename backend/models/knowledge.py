"""知识库 MySQL 数据模型"""
from sqlalchemy import Column, Integer, String, Text, Float, DateTime, Index
from sqlalchemy.sql import func
from app.database import Base


class KnowledgeItem(Base):
    __tablename__ = "knowledge_base"

    id = Column(Integer, primary_key=True, autoincrement=True)
    keyword = Column(String(255), nullable=False, comment="关键词")
    content = Column(Text, nullable=False, comment="知识内容")
    category = Column(String(100), nullable=True, default="general", comment="知识分类")
    confidence = Column(Float, nullable=False, default=0.8, comment="置信度")
    source = Column(String(255), nullable=False, default="system", comment="来源")
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间")

    __table_args__ = (
        Index("idx_keyword", "keyword"),
        Index("idx_category", "category"),
        Index("idx_keyword_category", "keyword", "category"),
    )

    def __repr__(self):
        return f"<KnowledgeItem(keyword={self.keyword}, category={self.category})>"