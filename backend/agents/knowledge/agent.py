from agents.base.agent import BaseAgent, AgentInput, AgentOutput
from typing import Dict, Any


class KnowledgeAgent(BaseAgent):
    def __init__(self):
        super().__init__("knowledge", "Knowledge Agent")
    
    async def execute(self, input_data: AgentInput) -> AgentOutput:
        await self._set_status("processing")
        await self._set_current_task(f"检索知识: {input_data.content[:50]}...")
        
        try:
            enhanced_content = self._retrieve_knowledge(input_data.content)
            
            await self._set_status("idle")
            await self._set_current_task(None)
            
            return AgentOutput(
                content=enhanced_content,
                success=True,
                message="知识检索完成",
                metadata={"knowledge_count": 3}
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
        knowledge_items = self._search_knowledge_base(keywords)
        return self._enhance_content(query, knowledge_items)
    
    def _extract_keywords(self, text: str) -> list:
        common_keywords = ["AI", "校园", "规划", "方案", "系统", "开发"]
        found = []
        for kw in common_keywords:
            if kw in text:
                found.append(kw)
        return found or ["general"]
    
    def _search_knowledge_base(self, keywords: list) -> list:
        mock_knowledge = {
            "AI": ["AI助手可以帮助自动化日常任务", "AI模型需要持续训练优化"],
            "校园": ["校园场景需要考虑学生隐私", "校园网络环境相对封闭"],
            "规划": ["规划需要明确目标和时间节点", "多方利益相关者参与很重要"],
            "general": ["通用知识条目1", "通用知识条目2"]
        }
        
        result = []
        for kw in keywords:
            result.extend(mock_knowledge.get(kw, []))
        return result[:5]
    
    def _enhance_content(self, original: str, knowledge_items: list) -> str:
        if knowledge_items:
            enhanced = f"【知识增强】\n{original}\n\n参考知识:\n"
            for i, item in enumerate(knowledge_items, 1):
                enhanced += f"{i}. {item}\n"
            return enhanced
        return original