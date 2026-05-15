from agents.base.agent import BaseAgent, AgentInput, AgentOutput
from typing import Dict, Any, List
import json
import re

class WriterAgent(BaseAgent):
    def __init__(self):
        super().__init__("writer", "Writer Agent")
        self.local_model = "phi4-mini:3.8b"
        self.templates = self._load_templates()
    
    def _load_templates(self) -> Dict[str, Dict[str, str]]:
        """加载写作模板"""
        return {
            "活动策划": {
                "sections": [
                    {"title": "活动概述", "content": "请简要介绍活动的背景、目的和意义。"},
                    {"title": "活动目标", "content": "明确活动的具体目标和预期成果。"},
                    {"title": "活动流程安排", "content": "详细描述活动的时间安排和流程。"},
                    {"title": "人员分工", "content": "说明各岗位的职责和分工。"},
                    {"title": "预算规划", "content": "列出活动所需的各项费用预算。"},
                    {"title": "安全保障措施", "content": "制定安全保障和风险防控措施。"},
                    {"title": "应急预案", "content": "制定突发事件的应急处理方案。"}
                ],
                "format": "markdown"
            },
            "方案设计": {
                "sections": [
                    {"title": "需求分析", "content": "分析用户需求和痛点。"},
                    {"title": "方案目标", "content": "明确方案要达到的目标。"},
                    {"title": "方案设计", "content": "详细描述方案的设计思路和架构。"},
                    {"title": "实施步骤", "content": "制定实施方案的具体步骤。"},
                    {"title": "风险评估", "content": "评估可能遇到的风险和应对措施。"},
                    {"title": "预期成果", "content": "描述方案实施后的预期效果。"}
                ],
                "format": "markdown"
            },
            "文档撰写": {
                "sections": [
                    {"title": "引言", "content": "介绍文档的背景和目的。"},
                    {"title": "主体内容", "content": "详细阐述核心内容。"},
                    {"title": "结论", "content": "总结主要观点和成果。"},
                    {"title": "参考文献", "content": "列出引用的参考资料。"}
                ],
                "format": "markdown"
            },
            "分析报告": {
                "sections": [
                    {"title": "问题描述", "content": "描述分析的问题和背景。"},
                    {"title": "现状分析", "content": "分析当前现状和问题根源。"},
                    {"title": "解决方案", "content": "提出解决问题的方案。"},
                    {"title": "实施建议", "content": "给出具体的实施建议。"}
                ],
                "format": "markdown"
            },
            "会议纪要": {
                "sections": [
                    {"title": "会议基本信息", "content": "记录会议时间、地点、主持人、参会人员等基本信息。"},
                    {"title": "会议议程", "content": "列出会议讨论的主要议题。"},
                    {"title": "讨论内容", "content": "详细记录各议题的讨论过程和要点。"},
                    {"title": "决议事项", "content": "明确会议形成的决议和决定。"},
                    {"title": "行动项", "content": "列出需要执行的任务、责任人及截止日期。"},
                    {"title": "下次会议安排", "content": "确定下次会议的时间和议题。"}
                ],
                "format": "markdown"
            },
            "志愿活动": {
                "sections": [
                    {"title": "活动背景", "content": "介绍志愿活动的背景和意义。"},
                    {"title": "活动目标", "content": "明确志愿活动的具体目标。"},
                    {"title": "活动时间与地点", "content": "说明活动的时间安排和地点。"},
                    {"title": "志愿者招募", "content": "说明志愿者的招募条件和方式。"},
                    {"title": "活动流程", "content": "详细描述活动的具体流程。"},
                    {"title": "注意事项", "content": "列出志愿者需要注意的事项和要求。"}
                ],
                "format": "markdown"
            },
            "操作指南": {
                "sections": [
                    {"title": "概述", "content": "介绍操作指南的目的和适用范围。"},
                    {"title": "准备工作", "content": "列出操作前需要准备的工具和条件。"},
                    {"title": "操作步骤", "content": "详细描述具体的操作步骤。"},
                    {"title": "注意事项", "content": "列出操作过程中需要注意的事项。"},
                    {"title": "常见问题", "content": "解答常见问题和故障排除方法。"},
                    {"title": "安全提示", "content": "强调操作安全注意事项。"}
                ],
                "format": "markdown"
            },
            "实验报告": {
                "sections": [
                    {"title": "实验目的", "content": "说明实验的目的和意义。"},
                    {"title": "实验原理", "content": "介绍实验的理论基础和原理。"},
                    {"title": "实验器材", "content": "列出实验所需的仪器和材料。"},
                    {"title": "实验步骤", "content": "详细描述实验的操作步骤。"},
                    {"title": "实验数据", "content": "记录实验过程中获得的数据。"},
                    {"title": "数据处理与分析", "content": "对实验数据进行处理和分析。"},
                    {"title": "实验结论", "content": "总结实验结果和得出结论。"},
                    {"title": "思考题", "content": "提出相关的思考问题。"}
                ],
                "format": "markdown"
            },
            "通用任务": {
                "sections": [
                    {"title": "任务概述", "content": "介绍任务的背景和目标。"},
                    {"title": "核心需求", "content": "分析任务的核心需求。"},
                    {"title": "解决方案", "content": "提出解决问题的方案。"},
                    {"title": "实施计划", "content": "制定实施计划和时间表。"}
                ],
                "format": "markdown"
            }
        }
    
    async def execute(self, input_data: AgentInput) -> AgentOutput:
        await self._set_status("processing")
        await self._set_current_task(f"内容生成: {input_data.content[:50]}...")
        
        try:
            # 1. 解析 Summary Agent 的输出
            parsed = self._parse_summary(input_data.content)
            
            # 2. 确定任务类型
            task_type = self._determine_task_type(parsed)
            
            # 3. 获取写作模板
            template = self.templates.get(task_type, self.templates["通用任务"])
            
            # 4. 检查是否需要补充知识
            missing_knowledge = await self._check_missing_knowledge(parsed)
            
            # 5. 如果有缺失知识，增加复杂度
            complexity_increased = len(missing_knowledge) > 0
            
            # 6. 使用 LLM 和知识生成内容（根据规范，Writer Agent 应始终使用 LLM）
            content = await self._generate_content_with_llm(parsed, template, use_cloud=input_data.use_cloud)
            
            await self._set_status("idle")
            await self._set_current_task(None)
            
            return AgentOutput(
                content=content,
                success=True,
                message="内容生成完成",
                metadata={
                    "content_length": len(content),
                    "model_used": self.local_model,
                    "task_type": task_type,
                    "complexity_increased": complexity_increased,
                    "missing_knowledge_count": len(missing_knowledge)
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
    
    def _parse_summary(self, content: str) -> Dict[str, Any]:
        """解析 Summary Agent 的输出"""
        try:
            parsed = json.loads(content)
            return {
                "task": parsed.get("task", ""),
                "original_question": parsed.get("original_question", ""),
                "keywords": parsed.get("keywords", []),
                "knowledge_points": parsed.get("knowledge_points", []),
                "requirements": parsed.get("requirements", []),
                "outline": parsed.get("outline", []),
                "summary": parsed.get("summary", "")
            }
        except:
            return {
                "task": content,
                "original_question": content,
                "keywords": [],
                "knowledge_points": [],
                "requirements": [],
                "outline": [],
                "summary": content
            }
    
    def _determine_task_type(self, parsed: Dict[str, Any]) -> str:
        """根据关键词确定任务类型"""
        keywords = parsed.get("keywords", [])
        task = parsed.get("task", "").lower()
        
        # 检查任务类型关键词
        if any(kw.lower() in task for kw in ["活动", "策划", "组织", "赛事", "运动会"]):
            return "活动策划"
        elif any(kw.lower() in task for kw in ["方案", "设计", "规划", "系统"]):
            return "方案设计"
        elif any(kw.lower() in task for kw in ["报告", "文档", "撰写", "编写"]):
            return "文档撰写"
        elif any(kw.lower() in task for kw in ["分析", "评估", "研究"]):
            return "分析报告"
        elif any(kw.lower() in task for kw in ["会议", "纪要", "记录", "讨论"]):
            return "会议纪要"
        elif any(kw.lower() in task for kw in ["志愿", "志愿者", "义工", "服务"]):
            return "志愿活动"
        elif any(kw.lower() in task for kw in ["操作", "指南", "手册", "教程", "使用说明"]):
            return "操作指南"
        elif any(kw.lower() in task for kw in ["实验", "报告", "科学", "研究"]):
            return "实验报告"
        
        # 检查关键词
        for keyword in keywords:
            if keyword in ["活动策划", "运动会", "赛事"]:
                return "活动策划"
            elif keyword in ["方案", "系统", "设计"]:
                return "方案设计"
            elif keyword in ["会议纪要", "会议", "纪要"]:
                return "会议纪要"
            elif keyword in ["志愿服务", "志愿者", "义工"]:
                return "志愿活动"
            elif keyword in ["操作指南", "手册", "教程"]:
                return "操作指南"
            elif keyword in ["实验报告", "实验"]:
                return "实验报告"
            elif keyword in ["报告", "文档"]:
                return "文档撰写"
            elif keyword in ["分析", "评估"]:
                return "分析报告"
        
        return "通用任务"
    
    async def _check_missing_knowledge(self, parsed: Dict[str, Any]) -> List[str]:
        """检查是否需要补充知识"""
        missing_topics = []
        knowledge_points = parsed.get("knowledge_points", [])
        existing_topics = set()
        
        # 收集已有知识的主题
        for point in knowledge_points:
            content = point.get("content", "")
            # 提取主题关键词
            topic_keywords = ["预算", "安全", "流程", "分工", "目标", "风险", "实施"]
            for kw in topic_keywords:
                if kw in content:
                    existing_topics.add(kw)
        
        # 检查大纲中是否有未覆盖的主题
        outline = parsed.get("outline", [])
        for section in outline:
            section_lower = section.lower()
            if "预算" in section_lower and "预算" not in existing_topics:
                missing_topics.append("预算")
            elif "安全" in section_lower and "安全" not in existing_topics:
                missing_topics.append("安全")
            elif "流程" in section_lower and "流程" not in existing_topics:
                missing_topics.append("流程")
            elif "分工" in section_lower and "分工" not in existing_topics:
                missing_topics.append("人员分工")
            elif "风险" in section_lower and "风险" not in existing_topics:
                missing_topics.append("风险评估")
        
        return missing_topics
    
    def _generate_content_with_template(self, parsed: Dict[str, Any], template: Dict[str, Any]) -> str:
        """使用模板生成内容"""
        task = parsed.get("task", "")
        keywords = parsed.get("keywords", [])
        knowledge_points = parsed.get("knowledge_points", [])
        requirements = parsed.get("requirements", [])
        outline = parsed.get("outline", [])
        
        content = f"# {task}\n\n"
        
        # 使用自定义大纲（如果有）
        if outline:
            for i, section in enumerate(outline, 1):
                # 提取章节标题（去除序号）
                title = re.sub(r'^[\d一二三四五六七八九十]+[、.．]\s*', '', section)
                content += f"## {section}\n"
                
                # 查找相关知识
                related_knowledge = [
                    kp for kp in knowledge_points 
                    if any(kw in kp.get('content', '') for kw in keywords[:3])
                ]
                
                # 查找相关需求
                related_requirements = [
                    req for req in requirements 
                    if any(kw in req for kw in keywords[:3])
                ]
                
                # 生成章节内容
                content += self._generate_section_content(title, related_knowledge, related_requirements)
                content += "\n"
        else:
            # 使用模板章节
            for i, section in enumerate(template["sections"], 1):
                content += f"## {i}、{section['title']}\n"
                content += self._generate_section_content(section["title"], knowledge_points, requirements)
                content += "\n"
        
        content += "## 总结\n"
        content += "以上是根据您的需求生成的方案，如需进一步细化或调整，请提供更多信息。\n"
        
        return content
    
    def _generate_section_content(self, title: str, knowledge_points: List[Dict], requirements: List[str]) -> str:
        """生成单个章节的内容"""
        content = ""
        
        # 查找相关知识
        related_knowledge = []
        for kp in knowledge_points:
            kp_content = kp.get("content", "")
            # 检查知识是否与章节标题相关
            if any(word in title for word in ["概述", "目标", "流程", "分工", "预算", "安全", "应急", "需求", "设计", "实施", "风险", "成果"]):
                # 如果章节标题包含这些词，认为所有知识都相关
                related_knowledge.append(kp_content)
            elif any(keyword in kp_content for keyword in ["活动", "策划", "方案", "设计"]):
                related_knowledge.append(kp_content)
        
        # 添加知识内容
        if related_knowledge:
            for i, knowledge in enumerate(related_knowledge[:3], 1):
                content += f"- {knowledge}\n"
            content += "\n"
        
        # 添加需求内容
        if requirements:
            content += "**关键要求：**\n"
            for req in requirements[:3]:
                content += f"- {req}\n"
            content += "\n"
        
        # 如果没有知识，添加默认内容
        if not related_knowledge:
            content += "本章节内容需要根据具体需求进一步细化。\n"
        
        return content
    
    async def _generate_content_with_llm(self, parsed: Dict[str, Any], template: Dict[str, Any], use_cloud: bool = False) -> str:
        """使用LLM生成内容"""
        task = parsed.get("task", "")
        keywords = parsed.get("keywords", [])
        knowledge_points = parsed.get("knowledge_points", [])
        requirements = parsed.get("requirements", [])
        outline = parsed.get("outline", [])
        
        # 构建知识参考字符串
        knowledge_str = ""
        if knowledge_points:
            knowledge_str = "参考知识：\n"
            for i, kp in enumerate(knowledge_points, 1):
                knowledge_str += f"{i}. [{kp.get('type', '')}] {kp.get('content', '')}\n"
        
        # 构建需求字符串
        requirements_str = ""
        if requirements:
            requirements_str = "关键要求：\n"
            for i, req in enumerate(requirements, 1):
                requirements_str += f"{i}. {req}\n"
        
        # 构建大纲字符串
        outline_str = ""
        if outline:
            outline_str = "建议大纲：\n"
            for section in outline:
                outline_str += f"- {section}\n"
        
        prompt = f"""
你是一位专业的内容创作助手。请根据以下信息，为用户生成一份高质量、专业的方案文档。

## 任务要求
任务：{task}
关键词：{", ".join(keywords)}

## 参考知识
{knowledge_str if knowledge_str else "暂无参考知识"}

## 用户需求
{requirements_str if requirements_str else "暂无明确需求"}

## 建议大纲
{outline_str if outline_str else "无建议大纲"}

## 输出要求
1. **专业性**：内容必须专业、准确、有深度
2. **完整性**：覆盖主题的各个关键方面
3. **实用性**：提供可操作的建议和方案
4. **结构化**：使用清晰的 Markdown 格式，包含标题、段落、列表等
5. **逻辑性**：内容要有条理，逻辑清晰
6. **详细性**：提供足够的细节和具体内容

## 格式规范
- 使用 # 一级标题、## 二级标题、### 三级标题
- 使用有序列表和无序列表
- 重要内容可以使用 **粗体** 强调
- 代码相关内容使用 `反引号` 或代码块

请开始撰写专业的方案文档：
"""
        
        response = await self._call_llm(prompt, model=self.local_model, use_cloud=use_cloud, temperature=0.3, max_tokens=4096)
        
        if response:
            return response
        
        # 如果LLM失败，使用模板生成
        return self._generate_content_with_template(parsed, template)
