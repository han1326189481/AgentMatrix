from typing import Dict, Any, Optional
import os
import json
import logging

logger = logging.getLogger(__name__)


class PromptTemplate:
    def __init__(self, name: str, template: str, description: str = "", placeholders: list = None):
        self.name = name
        self.template = template
        self.description = description
        self.placeholders = placeholders or []

    def render(self, **kwargs) -> str:
        try:
            return self.template.format(**kwargs)
        except KeyError as e:
            logger.warning(f"Missing placeholder {e} in template {self.name}")
            return self.template

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "placeholders": self.placeholders,
            "template": self.template
        }


class PromptManager:
    def __init__(self):
        self.templates: Dict[str, Dict[str, PromptTemplate]] = {}
        self.templates_dir = "prompts/templates"
        self.rules_dir = "prompts/rules"
        self._load_templates()

    def _load_templates(self) -> None:
        os.makedirs(self.templates_dir, exist_ok=True)
        os.makedirs(self.rules_dir, exist_ok=True)

        for agent_id in os.listdir(self.templates_dir):
            agent_dir = os.path.join(self.templates_dir, agent_id)
            if os.path.isdir(agent_dir):
                self.templates[agent_id] = {}
                for filename in os.listdir(agent_dir):
                    if filename.endswith(".txt"):
                        template_name = filename[:-4]
                        filepath = os.path.join(agent_dir, filename)
                        try:
                            with open(filepath, "r", encoding="utf-8") as f:
                                content = f.read()
                            
                            template = PromptTemplate(
                                name=template_name,
                                template=content,
                                description=f"Template for {agent_id} - {template_name}"
                            )
                            self.templates[agent_id][template_name] = template
                        except Exception as e:
                            logger.error(f"Failed to load template {filepath}: {e}")

        if not self.templates:
            self._init_default_templates()

    def _init_default_templates(self) -> None:
        default_templates = {
            "knowledge": {
                "enhance": PromptTemplate(
                    name="enhance",
                    template="基于以下知识，请增强用户查询：\n\n知识：\n{knowledge}\n\n用户查询：\n{query}\n\n增强后的查询：",
                    description="知识增强模板",
                    placeholders=["knowledge", "query"]
                )
            },
            "summary": {
                "extract": PromptTemplate(
                    name="extract",
                    template="请分析以下内容，提取任务目标和关键词：\n\n内容：\n{content}\n\n输出格式：\n{{\"task\": \"任务描述\", \"keywords\": [\"关键词1\", \"关键词2\"]}}",
                    description="任务提取模板",
                    placeholders=["content"]
                )
            },
            "writer": {
                "generate": PromptTemplate(
                    name="generate",
                    template="根据以下任务描述和关键词，生成详细的内容：\n\n任务：{task}\n关键词：{keywords}\n\n请生成专业、详细的内容：",
                    description="内容生成模板",
                    placeholders=["task", "keywords"]
                )
            },
            "review": {
                "review": PromptTemplate(
                    name="review",
                    template="请评审以下内容的质量：\n\n内容：\n{content}\n\n请评估：1) 内容完整性 2) 逻辑结构 3) 语言质量\n\n输出格式：\n{{\"score\": 分数, \"issues\": [问题列表], \"suggestions\": [建议列表]}}",
                    description="质量评审模板",
                    placeholders=["content"]
                )
            },
            "judge": {
                "complexity": PromptTemplate(
                    name="complexity",
                    template="请判断以下任务的复杂度（0-1）：\n\n任务：{task}\n内容：{content}\n\n复杂度评分：",
                    description="复杂度判断模板",
                    placeholders=["task", "content"]
                )
            },
            "result": {
                "format": PromptTemplate(
                    name="format",
                    template="请格式化以下结果：\n\n执行方式：{execution_type}\n复杂度：{complexity}\n内容：\n{content}\n\n格式化输出：",
                    description="结果格式化模板",
                    placeholders=["execution_type", "complexity", "content"]
                )
            }
        }

        self.templates = default_templates
        self._save_templates()

    def _save_templates(self) -> None:
        for agent_id, templates in self.templates.items():
            agent_dir = os.path.join(self.templates_dir, agent_id)
            os.makedirs(agent_dir, exist_ok=True)
            
            for name, template in templates.items():
                filepath = os.path.join(agent_dir, f"{name}.txt")
                with open(filepath, "w", encoding="utf-8") as f:
                    f.write(template.template)

    def get_template(self, agent_id: str, template_name: str) -> Optional[PromptTemplate]:
        return self.templates.get(agent_id, {}).get(template_name)

    def add_template(self, agent_id: str, template: PromptTemplate) -> None:
        if agent_id not in self.templates:
            self.templates[agent_id] = {}
        self.templates[agent_id][template.name] = template
        self._save_templates()

    def remove_template(self, agent_id: str, template_name: str) -> bool:
        if agent_id in self.templates and template_name in self.templates[agent_id]:
            del self.templates[agent_id][template_name]
            self._save_templates()
            return True
        return False

    def get_all_templates(self) -> Dict[str, Dict[str, Dict[str, Any]]]:
        result = {}
        for agent_id, templates in self.templates.items():
            result[agent_id] = {
                name: template.to_dict()
                for name, template in templates.items()
            }
        return result

    def get_agent_templates(self, agent_id: str) -> Dict[str, Dict[str, Any]]:
        return {
            name: template.to_dict()
            for name, template in self.templates.get(agent_id, {}).items()
        }


_prompt_manager: Optional[PromptManager] = None


def get_prompt_manager() -> PromptManager:
    global _prompt_manager
    if _prompt_manager is None:
        _prompt_manager = PromptManager()
    return _prompt_manager
