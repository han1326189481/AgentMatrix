from typing import Dict, Any, List, Optional, Tuple
import json
import os
import logging
import time

logger = logging.getLogger(__name__)


class SimpleCache:
    def __init__(self, maxsize: int = 100, ttl: int = 300):
        self.maxsize = maxsize
        self.ttl = ttl
        self.cache: Dict[str, Tuple[Any, float]] = {}
    
    def __contains__(self, key: str) -> bool:
        if key in self.cache:
            _, timestamp = self.cache[key]
            if time.time() - timestamp < self.ttl:
                return True
            del self.cache[key]
        return False
    
    def __getitem__(self, key: str) -> Any:
        if key in self:
            return self.cache[key][0]
        raise KeyError(key)
    
    def __setitem__(self, key: str, value: Any) -> None:
        if len(self.cache) >= self.maxsize:
            oldest_key = min(self.cache.keys(), key=lambda k: self.cache[k][1])
            del self.cache[oldest_key]
        self.cache[key] = (value, time.time())
    
    def clear(self) -> None:
        self.cache.clear()
    
    @property
    def size(self) -> int:
        return len(self.cache)


class KnowledgeService:
    def __init__(self):
        self.knowledge_base: Dict[str, List[str]] = {}
        self.knowledge_file = "knowledge/knowledge_base.json"
        self.search_cache = SimpleCache(maxsize=500, ttl=300)
        self._load_knowledge_base()

    def _load_knowledge_base(self) -> None:
        if os.path.exists(self.knowledge_file):
            try:
                with open(self.knowledge_file, "r", encoding="utf-8") as f:
                    self.knowledge_base = json.load(f)
                logger.info(f"Loaded knowledge base with {len(self.knowledge_base)} keywords")
            except Exception as e:
                logger.error(f"Failed to load knowledge base: {e}")
                self._init_default_knowledge()
        else:
            self._init_default_knowledge()

    def _init_default_knowledge(self) -> None:
        self.knowledge_base = {
            "AI": [
                "AI助手可以帮助自动化日常任务",
                "AI模型需要持续训练优化",
                "AI技术正在快速发展",
                "大语言模型具备上下文理解能力",
                "AI可以用于自然语言处理和生成"
            ],
            "校园": [
                "校园场景需要考虑学生隐私",
                "校园网络环境相对封闭",
                "校园AI需要注重教育价值",
                "校园场景涉及多角色协作",
                "校园信息化建设需要循序渐进"
            ],
            "规划": [
                "规划需要明确目标和时间节点",
                "多方利益相关者参与很重要",
                "规划需要考虑资源约束",
                "规划应有可执行的实施路径",
                "规划需要定期评估和调整"
            ],
            "方案": [
                "方案需要有可行性分析",
                "方案应包含实施步骤",
                "方案需要考虑风险评估",
                "方案应有明确的预期成果",
                "方案需要成本效益分析"
            ],
            "系统": [
                "系统设计需要考虑扩展性",
                "系统架构应遵循模块化原则",
                "系统需要良好的容错机制",
                "系统性能需要持续监控",
                "系统安全是首要考虑因素"
            ],
            "开发": [
                "开发需要遵循编码规范",
                "代码需要充分测试",
                "开发过程需要版本控制",
                "代码需要良好的文档",
                "开发应采用敏捷方法论"
            ],
            "general": [
                "持续学习是成长的关键",
                "良好的沟通是团队协作的基础",
                "用户体验是产品成功的关键",
                "数据驱动决策更可靠",
                "创新源于不断尝试"
            ]
        }
        self._save_knowledge_base()

    def _save_knowledge_base(self) -> None:
        os.makedirs(os.path.dirname(self.knowledge_file), exist_ok=True)
        with open(self.knowledge_file, "w", encoding="utf-8") as f:
            json.dump(self.knowledge_base, f, ensure_ascii=False, indent=2)

    def search_by_keywords(self, keywords: List[str], limit: int = 5) -> List[str]:
        cache_key = f"search_keywords_{hash(tuple(sorted(keywords)))}_{limit}"
        if cache_key in self.search_cache:
            return self.search_cache[cache_key]

        results = []
        for keyword in keywords:
            keyword_lower = keyword.lower()
            for kb_key, kb_items in self.knowledge_base.items():
                if keyword_lower in kb_key.lower():
                    results.extend(kb_items[:limit])
                else:
                    for item in kb_items:
                        if keyword_lower in item.lower():
                            results.append(item)
        
        unique_results = list(set(results))[:limit * 2]
        self.search_cache[cache_key] = unique_results
        return unique_results

    def search(self, query: str, limit: int = 5) -> Dict[str, List[str]]:
        cache_key = f"search_query_{hash(query)}_{limit}"
        if cache_key in self.search_cache:
            return self.search_cache[cache_key]

        results = {}
        query_lower = query.lower()
        
        for keyword, content_list in self.knowledge_base.items():
            if query_lower in keyword.lower():
                results[keyword] = content_list[:limit]
            else:
                matching_content = [c for c in content_list if query_lower in c.lower()]
                if matching_content:
                    results[keyword] = matching_content[:limit]
        
        self.search_cache[cache_key] = results
        return results

    def add_knowledge(self, keyword: str, content: List[str]) -> None:
        if keyword not in self.knowledge_base:
            self.knowledge_base[keyword] = []
        self.knowledge_base[keyword].extend(content)
        self.knowledge_base[keyword] = list(set(self.knowledge_base[keyword]))
        self._save_knowledge_base()
        self.search_cache.clear()
        logger.info(f"Added {len(content)} items to keyword '{keyword}'")

    def delete_knowledge(self, keyword: str) -> bool:
        if keyword in self.knowledge_base:
            del self.knowledge_base[keyword]
            self._save_knowledge_base()
            self.search_cache.clear()
            logger.info(f"Deleted keyword '{keyword}'")
            return True
        return False

    def update_knowledge(self, keyword: str, content: List[str]) -> bool:
        if keyword in self.knowledge_base:
            self.knowledge_base[keyword] = content
            self._save_knowledge_base()
            self.search_cache.clear()
            logger.info(f"Updated keyword '{keyword}'")
            return True
        return False

    def get_all_keywords(self) -> List[str]:
        return list(self.knowledge_base.keys())

    def get_knowledge_by_keyword(self, keyword: str) -> Optional[List[str]]:
        return self.knowledge_base.get(keyword)

    def get_knowledge_stats(self) -> Dict[str, Any]:
        total_items = sum(len(items) for items in self.knowledge_base.values())
        return {
            "total_keywords": len(self.knowledge_base),
            "total_items": total_items,
            "average_items_per_keyword": total_items / len(self.knowledge_base) if self.knowledge_base else 0,
            "cache_size": self.search_cache.size
        }

    def enhance_content(self, original_content: str, keywords: List[str]) -> str:
        cache_key = f"enhance_{hash(original_content)}_{hash(tuple(sorted(keywords)))}"
        if cache_key in self.search_cache:
            return self.search_cache[cache_key]

        knowledge_items = self.search_by_keywords(keywords)
        if not knowledge_items:
            self.search_cache[cache_key] = original_content
            return original_content
        
        enhanced = f"【知识增强】\n{original_content}\n\n参考知识:\n"
        for i, item in enumerate(knowledge_items, 1):
            enhanced += f"{i}. {item}\n"
        
        self.search_cache[cache_key] = enhanced
        return enhanced

    def warm_cache(self) -> None:
        for keyword in self.knowledge_base:
            self.search(keyword)
        logger.info("Knowledge cache warmed up")