from sqlalchemy import Column, Integer, String, Text, DateTime, Float, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base
from datetime import datetime


class ChatSession(Base):
    __tablename__ = "chat_sessions"
    
    id = Column(String, primary_key=True, index=True)
    user_id = Column(String, index=True)
    title = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    messages = relationship("ChatMessage", back_populates="session")
    executions = relationship("WorkflowExecution", back_populates="session")


class ChatMessage(Base):
    __tablename__ = "chat_messages"
    
    id = Column(String, primary_key=True, index=True)
    session_id = Column(String, ForeignKey("chat_sessions.id"))
    role = Column(String)
    content = Column(Text)
    timestamp = Column(DateTime, default=datetime.utcnow)
    
    session = relationship("ChatSession", back_populates="messages")


class WorkflowExecution(Base):
    __tablename__ = "workflow_executions"
    
    id = Column(String, primary_key=True, index=True)
    session_id = Column(String, ForeignKey("chat_sessions.id"))
    user_input = Column(Text)
    final_result = Column(Text)
    executed_locally = Column(Boolean)
    complexity_score = Column(Float)
    total_duration = Column(Float)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    session = relationship("ChatSession", back_populates="executions")
    steps = relationship("WorkflowStepRecord", back_populates="execution")


class WorkflowStepRecord(Base):
    __tablename__ = "workflow_steps"
    
    id = Column(String, primary_key=True, index=True)
    execution_id = Column(String, ForeignKey("workflow_executions.id"))
    agent_id = Column(String)
    agent_name = Column(String)
    input_content = Column(Text)
    output_content = Column(Text)
    success = Column(Boolean)
    duration = Column(Float)
    step_order = Column(Integer)
    
    execution = relationship("WorkflowExecution", back_populates="steps")


class KnowledgeEntry(Base):
    __tablename__ = "knowledge_entries"
    
    id = Column(Integer, primary_key=True, index=True)
    keyword = Column(String, index=True)
    content = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class MetricRecord(Base):
    __tablename__ = "metric_records"
    
    id = Column(Integer, primary_key=True, index=True)
    metric_type = Column(String, index=True)
    value = Column(Float)
    timestamp = Column(DateTime, default=datetime.utcnow)
    additional_info = Column(Text)
