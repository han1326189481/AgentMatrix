from agents.base.agent import BaseAgent, AgentInput, AgentOutput
from knowledge.service import KnowledgeService
from prompts.template_manager import get_prompt_manager
from typing import Dict, Any, List, Optional
import json
import os

class KnowledgeAgent(BaseAgent):
    def __init__(self):
        super().__init__("knowledge", "Knowledge Agent")
        self.local_model = "qwen2.5:1.5b"
        self.knowledge_service = KnowledgeService()
        self.prompt_manager = get_prompt_manager()
        
        # 永久记忆 - 身份认知规则
        self.identity_rules = [
            "我是 Knowledge Agent，负责知识检索和知识增强",
            "我不干预其他 Agent 的工作流程",
            "我只提供知识支持，不直接回答用户问题",
            "我的输出是增强后的上下文，供后续 Agent 使用"
        ]
        
        # 系统级关键词（身份识别）- 高优先级
        self.system_keywords = ["我是谁", "你是谁", "knowledge agent", "知识助手", "你的职责", "你的任务"]
        
        # 越权检测关键词 - 防止执行其他Agent的任务
        self.intervention_keywords = [
            "帮我写", "生成", "总结", "评价", "判断", "导出",
            "你去做", "代替我", "帮我完成", "执行", "撰写",
            "创作", "设计", "策划", "报告", "方案"
        ]
        
        # 从 role.txt 加载领域知识
        self.domain_knowledge = self._load_domain_knowledge()
        
    def _load_domain_knowledge(self) -> List[Dict[str, Any]]:
        """从 roletxt/knowledge.txt 加载领域知识"""
        domain_knowledge = []
        role_file = "roletxt/knowledge.txt"
        
        if os.path.exists(role_file):
            try:
                with open(role_file, "r", encoding="utf-8") as f:
                    content = f.read()
                
                # 处理文件中多个JSON数组的情况
                import re
                # 匹配所有 JSON 数组（非贪婪模式）
                array_pattern = r'\[([^\[\]]*?)\]'
                matches = re.findall(array_pattern, content, re.DOTALL)
                
                for match in matches:
                    # 在匹配内容周围加上括号重新构建数组
                    try:
                        data = json.loads('[' + match + ']')
                        if isinstance(data, list):
                            for item in data:
                                if isinstance(item, dict) and 'keywords' in item and 'content' in item:
                                    domain_knowledge.append(item)
                    except json.JSONDecodeError:
                        continue
                
                # 再匹配所有单独的 JSON 对象
                obj_pattern = r'\{[^{}]+\}'
                obj_matches = re.findall(obj_pattern, content)
                for match in obj_matches:
                    try:
                        data = json.loads(match)
                        if isinstance(data, dict) and 'keywords' in data and 'content' in data:
                            # 检查是否已存在
                            exists = False
                            for item in domain_knowledge:
                                if item.get("keywords") == data.get("keywords"):
                                    exists = True
                                    break
                            if not exists:
                                domain_knowledge.append(data)
                    except json.JSONDecodeError:
                        continue
                
            except Exception as e:
                print(f"Failed to load domain knowledge: {e}")
        
        return domain_knowledge
    
    def _detect_identity_query(self, content: str) -> bool:
        """检测是否为身份询问"""
        content_lower = content.lower()
        for kw in self.system_keywords:
            if kw.lower() in content_lower:
                return True
        return False
    
    def _detect_intervention(self, content: str) -> bool:
        """检测是否试图让Knowledge Agent执行其他Agent的任务"""
        content_lower = content.lower()
        for kw in self.intervention_keywords:
            if kw.lower() in content_lower:
                return True
        return False
    
    def _return_identity_info(self) -> AgentOutput:
        """返回身份信息"""
        identity_content = "\n".join(self.identity_rules)
        return AgentOutput(
            content=identity_content,
            success=True,
            message="身份识别完成",
            metadata={
                "knowledge_type": "identity",
                "knowledge_count": 0,
                "matched_keywords": [],
                "enhanced": False,
                "model_used": self.local_model
            }
        )
    
    def _reject_intervention(self) -> AgentOutput:
        """拒绝越权请求"""
        return AgentOutput(
            content="我是 Knowledge Agent，仅负责知识检索和增强。\n"
                    "如需内容生成、总结、评审等功能，请等待后续 Agent 处理。",
            success=True,
            message="检测到跨角色请求，已拒绝执行",
            metadata={
                "knowledge_type": "system",
                "knowledge_count": 0,
                "matched_keywords": [],
                "enhanced": False,
                "reason": "role_boundary"
            }
        )
    
    def _extract_keywords(self, content: str) -> List[str]:
        """分层提取关键词：系统级 → 领域级 → 通用级"""
        keywords_found = []
        content_lower = content.lower()
        
        print(f"[DEBUG] 原始内容: {content}")
        print(f"[DEBUG] 小写内容: {content_lower}")
        
        # 1. 检查领域知识关键词（来自 role.txt）
        for item in self.domain_knowledge:
            for kw in item.get("keywords", []):
                kw_lower = kw.lower()
                if kw_lower in content_lower and kw not in keywords_found:
                    keywords_found.append(kw)
                    print(f"[DEBUG] 匹配到领域关键词: {kw}")
        
        # 2. 补充通用关键词（包含知识库中的所有关键词）
        common_keywords = ["AI", "人工智能", "校园", "教育", "规划", "方案", 
                          "系统", "开发", "设计", "报告", "分析", "端云协同",
                          "多智能体", "RAG", "检索增强", "知识蒸馏",
                          "马拉松", "活动策划", "运动会", "志愿服务", "赛事",
                          "跑步", "活动", "策划", "组织", "安全", "预算"]
        for kw in common_keywords:
            kw_lower = kw.lower()
            if kw_lower in content_lower and kw not in keywords_found:
                keywords_found.append(kw)
                print(f"[DEBUG] 匹配到通用关键词: {kw}")
        
        # 3. 直接从知识库关键词匹配
        for kb_keyword in self.knowledge_service.get_all_keywords():
            if kb_keyword.lower() in content_lower and kb_keyword not in keywords_found:
                keywords_found.append(kb_keyword)
                print(f"[DEBUG] 匹配到知识库关键词: {kb_keyword}")
        
        print(f"[DEBUG] 最终关键词列表: {keywords_found}")
        return keywords_found or ["general"]
    
    def _search_domain_knowledge(self, keywords: List[str]) -> List[Dict[str, Any]]:
        """搜索领域知识库（来自 role.txt）"""
        results = []
        content_lower = " ".join(keywords).lower()
        
        for item in self.domain_knowledge:
            item_keywords = item.get("keywords", [])
            for kw in item_keywords:
                if kw.lower() in content_lower:
                    results.append({
                        "knowledge_type": "definition",
                        "query": kw,
                        "content": item.get("content", ""),
                        "source": "roletxt/knowledge.txt",
                        "confidence": 0.9
                    })
                    break
        
        return results
    
    def _search_knowledge_base(self, keywords: List[str]) -> List[str]:
        """搜索通用知识库（knowledge_base.json）"""
        return self.knowledge_service.search_by_keywords(keywords, limit=5)
    
    def _enhance_content(self, original: str, domain_items: List[Dict[str, Any]], 
                         general_items: List[str], keywords: List[str]) -> str:
        """构建知识增强内容"""
        if not domain_items and not general_items:
            return original
        
        enhanced = f"【知识增强】\n用户查询: {original}\n\n"
        
        # 添加领域知识
        if domain_items:
            enhanced += "【领域知识】\n"
            for i, item in enumerate(domain_items, 1):
                enhanced += f"{i}. [{item.get('knowledge_type', 'fact')}] {item.get('content', '')}\n"
                enhanced += f"   来源: {item.get('source', 'unknown')} | 置信度: {item.get('confidence', 0.8)}\n\n"
        
        # 添加通用知识
        if general_items:
            enhanced += "【通用知识】\n"
            for i, item in enumerate(general_items, 1):
                enhanced += f"{i}. {item}\n"
        
        enhanced += f"\n【匹配关键词】{', '.join(keywords)}"
        
        return enhanced
    
    async def execute(self, input_data: AgentInput) -> AgentOutput:
        await self._set_status("processing")
        await self._set_current_task(f"检索知识: {input_data.content[:50]}...")
        
        try:
            # 1. 身份检测 - 最高优先级
            if self._detect_identity_query(input_data.content):
                await self._set_status("idle")
                await self._set_current_task(None)
                return self._return_identity_info()
            
            # 2. 先提取关键词（无论是否越权都尝试检索知识）
            keywords = self._extract_keywords(input_data.content)
            print(f"[DEBUG] 提取到的关键词: {keywords}")
            
            # 3. 搜索领域知识（来自 role.txt）
            domain_knowledge_items = self._search_domain_knowledge(keywords)
            print(f"[DEBUG] 领域知识搜索结果数量: {len(domain_knowledge_items)}")
            
            # 4. 搜索通用知识库（来自 knowledge_base.json）
            general_knowledge_items = self._search_knowledge_base(keywords)
            print(f"[DEBUG] 通用知识搜索结果数量: {len(general_knowledge_items)}")
            
            # 5. 越权检测 - 如果有可检索的知识，即使有越权关键词也先返回知识
            has_knowledge = len(domain_knowledge_items) > 0 or len(general_knowledge_items) > 0
            print(f"[DEBUG] 是否有知识: {has_knowledge}, 是否越权: {self._detect_intervention(input_data.content)}")
            
            if self._detect_intervention(input_data.content) and not has_knowledge:
                # 只有纯粹的越权请求（没有可检索知识）才拒绝
                print(f"[DEBUG] 拒绝越权请求")
                await self._set_status("idle")
                await self._set_current_task(None)
                return self._reject_intervention()
            
            # 6. 构建增强内容
            enhanced_content = self._enhance_content(
                input_data.content,
                domain_knowledge_items,
                general_knowledge_items,
                keywords
            )
            
            # 7. 统计知识条目数量
            total_knowledge_count = len(domain_knowledge_items) + len(general_knowledge_items)
            
            await self._set_status("idle")
            await self._set_current_task(None)
            
            return AgentOutput(
                content=enhanced_content,
                success=True,
                message="知识检索完成",
                metadata={
                    "knowledge_type": "enhanced",
                    "knowledge_count": total_knowledge_count,
                    "domain_knowledge_count": len(domain_knowledge_items),
                    "general_knowledge_count": len(general_knowledge_items),
                    "matched_keywords": keywords,
                    "enhanced": total_knowledge_count > 0,
                    "model_used": self.local_model
                }
            )
        
        except Exception as e:
            await self._set_error(str(e))
            await self._set_status("error")
            return AgentOutput(
                content="",
                success=False,
                message=str(e)
            )
