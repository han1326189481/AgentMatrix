from agents.base.agent import BaseAgent, AgentInput, AgentOutput
from typing import Dict, Any
import json


class KnowledgeAgent(BaseAgent):
    def __init__(self):
        super().__init__("knowledge", "Knowledge Agent")
        self.local_model = "qwen2.5:1.5b"
    
    async def execute(self, input_data: AgentInput) -> AgentOutput:
        await self._set_status("processing")
        await self._set_current_task(f"检索知识: {input_data.content[:50]}...")
        
        try:
            if input_data.use_llm:
                enhanced_content = await self._retrieve_knowledge_with_llm(input_data.content)
            else:
                enhanced_content = self._retrieve_knowledge(input_data.content)
            
            await self._set_status("idle")
            await self._set_current_task(None)
            
            return AgentOutput(
                content=enhanced_content,
                success=True,
                message="知识检索完成",
                metadata={"knowledge_count": 3, "model_used": self.local_model},
                model_used=self.local_model
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
    
    async def _retrieve_knowledge_with_llm(self, query: str) -> str:
        prompt = f"""
请针对以下用户问题，提供相关的背景知识和参考信息：

用户问题：{query}

请以结构化的方式输出相关知识，包括：
1. 核心概念解释
2. 相关背景信息
3. 关键点总结

输出格式：
【知识增强】
{query}

参考知识：
1. ...
2. ...
3. ...
"""
        response = await self._call_llm(prompt, model=self.local_model, temperature=0.3)
        return response or self._retrieve_knowledge(query)
    
    def _extract_keywords(self, text: str) -> list:
        common_keywords = ["AI", "校园", "规划", "方案", "系统", "开发", "人工智能", "教育"]
        found = []
        for kw in common_keywords:
            if kw in text:
                found.append(kw)
        return found or ["general"]
    
    def _search_knowledge_base(self, keywords: list) -> list:
        mock_knowledge = {
            "AI": ["AI助手可以帮助自动化日常任务", "AI模型需要持续训练优化", "大语言模型具备上下文理解能力"],
            "人工智能": ["人工智能涵盖机器学习、深度学习等技术", "AI应用正在改变各个行业"],
            "校园": ["校园场景需要考虑学生隐私保护", "校园网络环境相对封闭安全", "教育信息化是发展趋势"],
            "规划": ["规划需要明确目标和时间节点", "多方利益相关者参与很重要", "可行性分析是关键"],
            "方案": ["完整方案应包含目标、步骤、预算", "方案需要经过多轮评审优化"],
            "系统": ["系统设计应遵循模块化原则", "可扩展性是重要考量因素"],
            "开发": ["敏捷开发可以提高效率", "需求变更管理很重要"],
            "教育": ["教育数字化转型正在加速", "个性化学习是未来趋势"],
            "general": ["通用知识条目：问题分析方法论", "通用知识条目：项目管理基础"]
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