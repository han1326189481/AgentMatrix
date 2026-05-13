from agents.base.agent import BaseAgent, AgentInput, AgentOutput
from typing import Dict, Any
from knowledge.service import KnowledgeService

class KnowledgeAgent(BaseAgent):
    def __init__(self):
        super().__init__("knowledge", "Knowledge Agent")
        self.knowledge_service = KnowledgeService()
        self.common_keywords = ["AI", "人工智能", "校园", "教育", "规划", "方案", "系统", "开发", "设计", "报告", "分析"]
    
    async def execute(self, input_data: AgentInput) -> AgentOutput:
        await self._set_status("processing")
        await self._set_current_task(f"检索知识: {input_data.content[:50]}...")
        
        try:
            enhanced_content = self._retrieve_knowledge(input_data.content)
            knowledge_items = self._search_knowledge_base(self._extract_keywords(input_data.content))
            
            await self._set_status("idle")
            await self._set_current_task(None)
            
            return AgentOutput(
                content=enhanced_content,
                success=True,
                message="知识检索完成",
                metadata={"knowledge_count": len(knowledge_items)}
            )
        
        except Exception as e:
            await self._set_error(str(e))
            await self._set_status("error")
            return AgentOutput(
                content="",
                success=False,
                message=str(e)
            )
    
    def _retrieve_knowledge(self, query: str) -> str:
        keywords = self._extract_keywords(query)
        return self.knowledge_service.enhance_content(query, keywords)
    
    def _extract_keywords(self, text: str) -> list:
        found = []
        for kw in self.common_keywords:
            if kw in text:
                found.append(kw)
        return found or ["general"]
    
    def _search_knowledge_base(self, keywords: list) -> list:
        return self.knowledge_service.search_by_keywords(keywords)