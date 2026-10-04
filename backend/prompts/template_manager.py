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
        from shared.platform import get_prompts_dir
        prompts_dir = get_prompts_dir()
        self.templates_dir = os.path.join(prompts_dir, "templates")
        self.rules_dir = os.path.join(prompts_dir, "rules")
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
                    template="基于以下知识，请增强用户查询并生成结构化需求摘要：\n\n知识：\n{knowledge}\n\n用户查询：\n{query}\n\n输出格式：\n{{\"task\": \"核心任务\", \"keywords\": [\"关键词1\", \"关键词2\"], \"knowledge_items\": [\"知识条目\"], \"requirements\": [\"需求\"], \"outline\": [\"大纲章节\"], \"task_type\": \"任务类型\", \"summary\": \"需求摘要\"}}",
                    description="知识检索与需求摘要一体化模板",
                    placeholders=["knowledge", "query"]
                )
            },
            "writer": {
                "generate": PromptTemplate(
                    name="generate",
                    template="根据以下任务描述和知识摘要，生成详细的内容：\n\n任务：{task}\n关键词：{keywords}\n知识条目：{knowledge}\n\n请生成专业、详细的内容，使用Markdown格式：",
                    description="内容生成模板",
                    placeholders=["task", "keywords", "knowledge"]
                )
            },
            "review": {
                "review": PromptTemplate(
                    name="review",
                    template="请评审以下内容的质量并评估难度阈值：\n\n内容：\n{content}\n\n评估维度：1) 结构完整性 2) 需求相关性 3) 内容丰富度 4) 专业性 5) 可执行性\n\n输出格式：\n{{\"review_score\": 分数, \"difficulty_threshold\": 难度阈值, \"dimensions\": {{\"structure\": 0.0, \"relevance\": 0.0, \"richness\": 0.0, \"professional\": 0.0, \"actionable\": 0.0}}, \"issues\": [问题列表], \"suggestions\": [建议列表], \"pass\": true/false}}",
                    description="质量评审与难度评估模板",
                    placeholders=["content"]
                )
            },
            "judge": {
                "routing": PromptTemplate(
                    name="routing",
                    template="基于Review Agent的评审结果进行路由决策：\n\n难度阈值：{difficulty_threshold}\n质量评分：{review_score}\n\n决策规则：\n- difficulty_threshold < 0.35 → local_output\n- 0.35-0.65 + review_score >= 0.70 → local_output\n- 0.35-0.65 + review_score < 0.70 → cloud_enhance + polish\n- 0.65-0.80 + review_score >= 0.80 → local_output\n- 0.65-0.80 + review_score < 0.80 → cloud_enhance + full_rewrite\n- > 0.80 → cloud_enhance + full_rewrite\n\n输出格式：\n{{\"decision\": \"local_output或cloud_enhance\", \"cloud_mode\": \"none/polish/full_rewrite\", \"difficulty_threshold\": 0.0, \"review_score\": 0.0, \"reason\": [\"理由\"]}}",
                    description="路由决策模板",
                    placeholders=["difficulty_threshold", "review_score"]
                )
            },
            "result": {
                "format": PromptTemplate(
                    name="format",
                    template="请格式化以下最终结果：\n\n执行方式：{execution_type}\n内容：\n{content}\n\n格式化输出（Markdown格式）：",
                    description="结果格式化模板",
                    placeholders=["execution_type", "content"]
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
