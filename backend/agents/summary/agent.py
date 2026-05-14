from agents.base.agent import BaseAgent, AgentInput, AgentOutput
from typing import Dict, Any, List, Tuple
import json
import re

class SummaryAgent(BaseAgent):
    def __init__(self):
        super().__init__("summary", "Summary Agent")
        self.local_model = "qwen2.5:1.5b"
    
    async def execute(self, input_data: AgentInput) -> AgentOutput:
        await self._set_status("processing")
        await self._set_current_task(f"摘要生成: {input_data.content[:50]}...")
        
        try:
            # 1. 解析 Knowledge Agent 的输出
            parsed_data = self._parse_knowledge_output(input_data.content)
            
            # 2. 提取用户原始问题
            original_question = parsed_data.get("original_question", input_data.content)
            
            # 3. 提取关键词
            keywords = self._extract_keywords(input_data.content, parsed_data.get("knowledge_points", []))
            
            # 4. 提取需求点
            requirements = self._extract_requirements(original_question, parsed_data.get("knowledge_points", []))
            
            # 5. 生成方案大纲
            outline = self._generate_outline(original_question, keywords, requirements)
            
            # 6. 构建结构化输出
            summary_result = {
                "task": self._extract_task(original_question),
                "original_question": original_question,
                "keywords": keywords,
                "knowledge_points": parsed_data.get("knowledge_points", []),
                "requirements": requirements,
                "outline": outline,
                "summary": self._generate_brief_summary(original_question, keywords, requirements)
            }
            
            await self._set_status("idle")
            await self._set_current_task(None)
            
            return AgentOutput(
                content=json.dumps(summary_result, ensure_ascii=False, indent=2),
                success=True,
                message="摘要生成完成",
                metadata={
                    "word_count": len(summary_result["task"]),
                    "keyword_count": len(keywords),
                    "knowledge_count": len(summary_result["knowledge_points"]),
                    "requirement_count": len(requirements),
                    "outline_sections": len(outline),
                    "model_used": self.local_model
                },
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
    
    def _parse_knowledge_output(self, content: str) -> Dict[str, Any]:
        """解析 Knowledge Agent 的输出格式"""
        result = {
            "original_question": "",
            "knowledge_points": []
        }
        
        # 提取用户查询
        query_match = re.search(r'用户查询[:：]\s*(.*?)\n', content)
        if query_match:
            result["original_question"] = query_match.group(1).strip()
        
        # 提取领域知识
        domain_knowledge_pattern = r'【领域知识】\s*(.*?)(?=\n【|$)'
        domain_match = re.search(domain_knowledge_pattern, content, re.DOTALL)
        if domain_match:
            domain_content = domain_match.group(1)
            for line in domain_content.strip().split("\n"):
                line = line.strip()
                if line and line[0].isdigit():
                    # 解析格式: 1. [类型] 内容 来源: xxx | 置信度: x.x
                    line = re.sub(r'^\d+\.\s*', '', line)
                    source_match = re.search(r'来源[:：]\s*([^\|]+)', line)
                    confidence_match = re.search(r'置信度[:：]\s*([\d.]+)', line)
                    content_part = re.sub(r'来源[:：][^\|]+\|?\s*', '', line)
                    content_part = re.sub(r'置信度[:：][\d.]+\s*', '', content_part)
                    content_part = re.sub(r'^\[\w+\]\s*', '', content_part).strip()
                    
                    if content_part:
                        result["knowledge_points"].append({
                            "type": "领域知识",
                            "content": content_part,
                            "source": source_match.group(1).strip() if source_match else "roletxt/knowledge.txt",
                            "confidence": float(confidence_match.group(1)) if confidence_match else 0.8
                        })
        
        # 提取通用知识
        general_knowledge_pattern = r'【通用知识】\s*(.*?)(?=\n【|$)'
        general_match = re.search(general_knowledge_pattern, content, re.DOTALL)
        if general_match:
            general_content = general_match.group(1)
            for line in general_content.strip().split("\n"):
                line = line.strip()
                if line and line[0].isdigit():
                    content_part = re.sub(r'^\d+\.\s*', '', line).strip()
                    if content_part:
                        result["knowledge_points"].append({
                            "type": "通用知识",
                            "content": content_part,
                            "source": "knowledge_base.json",
                            "confidence": 0.7
                        })
        
        # 如果没有解析到结构化知识，尝试直接提取文本
        if not result["knowledge_points"] and not result["original_question"]:
            result["original_question"] = content
        
        return result
    
    def _extract_task(self, content: str) -> str:
        """提取核心任务描述"""
        task_patterns = [
            r"(生成|创建|设计|规划|撰写|制定|编写|分析|评估)\s+(.+?)(。|？|\n|$)",
            r"(需要|想要|希望|需求|请求)\s+(.+?)(。|？|\n|$)"
        ]
        
        for pattern in task_patterns:
            match = re.search(pattern, content)
            if match:
                return f"{match.group(1)}{match.group(2)}"
        
        # 如果没有匹配到，返回前60个字符作为任务描述
        clean_content = re.sub(r'【.*?】', '', content).strip()
        return clean_content[:60] if len(clean_content) > 60 else clean_content
    
    def _extract_keywords(self, content: str, knowledge_points: List[Dict]) -> List[str]:
        """从内容和知识点中提取关键词"""
        keywords_found = []
        
        # 预定义的关键词列表（包含知识库中的关键词）
        predefined_keywords = [
            "AI", "人工智能", "校园", "教育", "规划", "方案", "系统", 
            "开发", "设计", "报告", "分析", "研究", "评估", "优化",
            "马拉松", "活动策划", "运动会", "志愿服务", "端云协同",
            "多智能体", "RAG", "国产操作系统", "麒麟系统", "统信UOS",
            "会议", "文档", "办公", "安全", "预算", "时间", "目标"
        ]
        
        content_lower = content.lower()
        for kw in predefined_keywords:
            if kw.lower() in content_lower and kw not in keywords_found:
                keywords_found.append(kw)
        
        # 从知识点中提取关键词
        for point in knowledge_points:
            point_content = point.get("content", "")
            for kw in predefined_keywords:
                if kw.lower() in point_content.lower() and kw not in keywords_found:
                    keywords_found.append(kw)
        
        return keywords_found[:8]
    
    def _extract_requirements(self, question: str, knowledge_points: List[Dict]) -> List[str]:
        """提取用户需求点"""
        requirements = []
        
        # 从问题中提取需求
        requirement_patterns = [
            (r"(需要|必须|应该|应当)\s+(.+?)(。|？|\n|$)", "需要"),
            (r"(确保|保证)\s+(.+?)(。|？|\n|$)", "确保"),
            (r"(考虑|考虑到)\s+(.+?)(。|？|\n|$)", "考虑"),
            (r"(包含|包括)\s+(.+?)(。|？|\n|$)", "包含"),
            (r"(符合|遵循)\s+(.+?)(。|？|\n|$)", "符合")
        ]
        
        for pattern, prefix in requirement_patterns:
            matches = re.findall(pattern, question)
            for match in matches:
                req = f"{prefix}{match[1]}"
                if req not in requirements and len(req) > 3:
                    requirements.append(req)
        
        # 从知识点中提取相关需求
        for point in knowledge_points:
            content = point.get("content", "")
            # 提取知识中的关键点作为需求参考
            if "需要" in content or "应" in content:
                # 提取包含"需要"或"应"的短句
                sentences = re.split(r'[。；;]', content)
                for sentence in sentences:
                    if "需要" in sentence or "应" in sentence:
                        sentence = sentence.strip()
                        if sentence and len(sentence) > 5 and sentence not in requirements:
                            requirements.append(sentence)
        
        return requirements[:6]
    
    def _generate_outline(self, question: str, keywords: List[str], requirements: List[str]) -> List[str]:
        """根据任务和需求生成方案大纲"""
        outline = []
        
        # 分析任务类型确定大纲结构
        task_type = self._determine_task_type(question, keywords)
        
        if task_type == "活动策划":
            outline = [
                "一、活动概述",
                "二、活动目标",
                "三、活动流程安排",
                "四、人员分工",
                "五、预算规划",
                "六、安全保障措施",
                "七、应急预案"
            ]
        elif task_type == "方案设计":
            outline = [
                "一、需求分析",
                "二、方案目标",
                "三、方案设计",
                "四、实施步骤",
                "五、风险评估",
                "六、预期成果"
            ]
        elif task_type == "文档撰写":
            outline = [
                "一、引言",
                "二、主体内容",
                "三、结论",
                "四、参考文献"
            ]
        elif task_type == "分析报告":
            outline = [
                "一、问题描述",
                "二、现状分析",
                "三、解决方案",
                "四、实施建议"
            ]
        else:
            # 默认大纲
            outline = [
                "一、任务概述",
                "二、核心需求",
                "三、解决方案",
                "四、实施计划"
            ]
        
        return outline
    
    def _determine_task_type(self, question: str, keywords: List[str]) -> str:
        """确定任务类型"""
        question_lower = question.lower()
        
        if any(kw in question_lower for kw in ["活动", "策划", "组织", "赛事", "运动会"]):
            return "活动策划"
        elif any(kw in question_lower for kw in ["方案", "设计", "规划", "系统"]):
            return "方案设计"
        elif any(kw in question_lower for kw in ["报告", "文档", "撰写", "编写"]):
            return "文档撰写"
        elif any(kw in question_lower for kw in ["分析", "评估", "研究"]):
            return "分析报告"
        
        return "通用任务"
    
    def _generate_brief_summary(self, question: str, keywords: List[str], requirements: List[str]) -> str:
        """生成简短摘要"""
        summary = f"用户需求：{question[:40]}..." if len(question) > 40 else question
        if keywords:
            summary += f" | 关键词：{', '.join(keywords[:3])}"
        if requirements:
            summary += f" | 需求点：{len(requirements)}项"
        return summary
