"""知识库持久化服务 — SQLite 引擎（零配置，打开即用）

替代原 MySQL 依赖，使用 SQLite 作为默认存储引擎。
导入路径保持不变（knowledge.mysql_service），确保向后兼容。
"""
from typing import Dict, Any, List, Optional, Tuple
import logging
import time
from app.database import get_global_session
from models.knowledge import KnowledgeItem

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
    """SQLite 持久化知识库服务"""

    def __init__(self):
        self.search_cache = SimpleCache(maxsize=500, ttl=300)
        self._initialized = False

    def _ensure_initialized(self):
        if self._initialized:
            return
        # SQLite 表由 init_global_db() 统一创建，这里只需标记已初始化
        self._initialized = True
        logger.info("KnowledgeService initialized (SQLite backend)")

    def seed_default_knowledge(self) -> int:
        """初始化默认知识库数据，返回插入条数"""
        self._ensure_initialized()
        session = get_global_session()
        try:
            existing_count = session.query(KnowledgeItem).count()
            if existing_count > 0:
                logger.info(f"Knowledge base already has {existing_count} items, skipping seed")
                return 0

            default_items = _get_default_knowledge_items()
            count = 0
            for item in default_items:
                session.add(KnowledgeItem(**item))
                count += 1
            session.commit()
            logger.info(f"Seeded {count} knowledge items into SQLite")
            return count
        except Exception as e:
            session.rollback()
            logger.error(f"Failed to seed knowledge base: {e}")
            raise
        finally:
            session.close()

    def search_by_keywords(self, keywords: List[str], limit: int = 5) -> List[str]:
        cache_key = f"search_kw_{hash(tuple(sorted(keywords)))}_{limit}"
        if cache_key in self.search_cache:
            return self.search_cache[cache_key]

        session = get_global_session()
        try:
            results = []
            for kw in keywords:
                items = (
                    session.query(KnowledgeItem)
                    .filter(KnowledgeItem.keyword.like(f"%{kw}%"))
                    .limit(limit)
                    .all()
                )
                for item in items:
                    if item.content not in results:
                        results.append(item.content)

                content_items = (
                    session.query(KnowledgeItem)
                    .filter(KnowledgeItem.content.like(f"%{kw}%"))
                    .limit(limit)
                    .all()
                )
                for item in content_items:
                    if item.content not in results:
                        results.append(item.content)

            unique_results = results[: limit * 2]
            self.search_cache[cache_key] = unique_results
            return unique_results
        finally:
            session.close()

    def search(self, query: str, limit: int = 5) -> Dict[str, List[str]]:
        cache_key = f"search_q_{hash(query)}_{limit}"
        if cache_key in self.search_cache:
            return self.search_cache[cache_key]

        session = get_global_session()
        try:
            results: Dict[str, List[str]] = {}
            items = (
                session.query(KnowledgeItem)
                .filter(
                    (KnowledgeItem.keyword.like(f"%{query}%"))
                    | (KnowledgeItem.content.like(f"%{query}%"))
                )
                .limit(limit * 3)
                .all()
            )
            for item in items:
                if item.keyword not in results:
                    results[item.keyword] = []
                results[item.keyword].append(item.content)

            self.search_cache[cache_key] = results
            return results
        finally:
            session.close()

    def search_by_category(self, category: str, limit: int = 20) -> List[Dict[str, Any]]:
        session = get_global_session()
        try:
            items = (
                session.query(KnowledgeItem)
                .filter(KnowledgeItem.category == category)
                .limit(limit)
                .all()
            )
            return [
                {
                    "keyword": item.keyword,
                    "content": item.content,
                    "category": item.category,
                    "confidence": item.confidence,
                    "source": item.source,
                }
                for item in items
            ]
        finally:
            session.close()

    def add_knowledge(self, keyword: str, content: str, category: str = "general",
                      confidence: float = 0.8, source: str = "system") -> int:
        session = get_global_session()
        try:
            item = KnowledgeItem(
                keyword=keyword,
                content=content,
                category=category,
                confidence=confidence,
                source=source,
            )
            session.add(item)
            session.commit()
            self.search_cache.clear()
            return item.id
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()

    def delete_knowledge(self, keyword: str) -> int:
        session = get_global_session()
        try:
            count = (
                session.query(KnowledgeItem)
                .filter(KnowledgeItem.keyword == keyword)
                .delete()
            )
            session.commit()
            self.search_cache.clear()
            return count
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()

    def update_knowledge(self, keyword: str, content: str) -> bool:
        session = get_global_session()
        try:
            items = (
                session.query(KnowledgeItem)
                .filter(KnowledgeItem.keyword == keyword)
                .all()
            )
            if not items:
                return False
            for item in items:
                item.content = content
            session.commit()
            self.search_cache.clear()
            return True
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()

    def get_all_keywords(self) -> List[str]:
        session = get_global_session()
        try:
            keywords = (
                session.query(KnowledgeItem.keyword)
                .distinct()
                .all()
            )
            return [k[0] for k in keywords]
        finally:
            session.close()

    def get_knowledge_by_keyword(self, keyword: str) -> Optional[List[str]]:
        session = get_global_session()
        try:
            items = (
                session.query(KnowledgeItem)
                .filter(KnowledgeItem.keyword == keyword)
                .all()
            )
            return [item.content for item in items] if items else None
        finally:
            session.close()

    def get_all_categories(self) -> List[str]:
        session = get_global_session()
        try:
            categories = (
                session.query(KnowledgeItem.category)
                .distinct()
                .all()
            )
            return [c[0] for c in categories if c[0]]
        finally:
            session.close()

    def get_knowledge_stats(self) -> Dict[str, Any]:
        session = get_global_session()
        try:
            total_items = session.query(KnowledgeItem).count()
            total_keywords = (
                session.query(KnowledgeItem.keyword)
                .distinct()
                .count()
            )
            total_categories = (
                session.query(KnowledgeItem.category)
                .distinct()
                .count()
            )
            return {
                "total_keywords": total_keywords,
                "total_items": total_items,
                "total_categories": total_categories,
                "cache_size": self.search_cache.size,
            }
        finally:
            session.close()

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


# ── 兼容别名 ──
MySQLKnowledgeService = KnowledgeService


def _get_default_knowledge_items() -> List[Dict[str, Any]]:
    """扩展的默认知识库数据"""
    items = [
        # ===== AI 与人工智能 =====
        {"keyword": "AI", "content": "人工智能（AI）是模拟人类智能的理论、方法、技术及应用系统的一门技术科学，核心领域包括机器学习、自然语言处理、计算机视觉等。", "category": "AI技术", "confidence": 0.95},
        {"keyword": "人工智能", "content": "人工智能技术正在快速发展，大语言模型（LLM）如GPT、DeepSeek等具备强大的上下文理解与生成能力，广泛应用于教育、医疗、金融等领域。", "category": "AI技术", "confidence": 0.95},
        {"keyword": "大语言模型", "content": "大语言模型（LLM）是通过海量文本数据训练的深度学习模型，能够理解和生成自然语言，具备上下文学习、推理、代码生成等能力。", "category": "AI技术", "confidence": 0.90},
        {"keyword": "机器学习", "content": "机器学习是AI的核心分支，通过算法让计算机从数据中自动学习模式和规律，包括监督学习、无监督学习、强化学习三类。", "category": "AI技术", "confidence": 0.90},
        {"keyword": "深度学习", "content": "深度学习是机器学习的一个子领域，使用多层神经网络来学习数据的层次化表示，在图像识别、语音识别、NLP等领域取得突破性进展。", "category": "AI技术", "confidence": 0.90},
        {"keyword": "RAG", "content": "RAG（检索增强生成）是一种将信息检索与文本生成相结合的技术架构，通过从外部知识库检索相关信息来增强大模型的回答准确性和可靠性。", "category": "AI技术", "confidence": 0.90},
        {"keyword": "多智能体", "content": "多智能体系统（Multi-Agent System）由多个相互交互的智能体组成，每个智能体有独立的角色和职责，通过协作完成复杂任务，是目前AI应用的重要架构模式。", "category": "AI技术", "confidence": 0.90},
        {"keyword": "端云协同", "content": "端云协同是指将终端设备的本地计算能力与云端强大的计算资源相结合，简单任务在本地处理以保证低延迟和隐私，复杂任务上传云端利用大模型增强。", "category": "AI技术", "confidence": 0.90},
        {"keyword": "知识蒸馏", "content": "知识蒸馏是一种模型压缩技术，通过让小型模型（学生模型）学习大型模型（教师模型）的输出分布，从而在保持性能的同时减少模型大小和推理成本。", "category": "AI技术", "confidence": 0.85},
        {"keyword": "AIGC", "content": "AIGC（AI Generated Content）是利用人工智能技术自动生成内容，包括文本、图像、音频、视频等多种形式，正在深刻改变内容创作行业。", "category": "AI技术", "confidence": 0.90},
        {"keyword": "提示词工程", "content": "提示词工程（Prompt Engineering）是设计和优化输入给大语言模型的提示词以获得高质量输出的技术，包括角色设定、few-shot示例、思维链等方法。", "category": "AI技术", "confidence": 0.85},
        # ===== 国产操作系统 =====
        {"keyword": "麒麟系统", "content": "麒麟操作系统（Kylin OS）是国产Linux发行版，由中国电子科技集团开发，广泛应用于政府、军工、金融等关键领域，支持x86、ARM等多种架构。", "category": "国产OS", "confidence": 0.95},
        {"keyword": "统信UOS", "content": "统信UOS（UnionTech OS）是基于Deepin深度操作系统开发的国产Linux发行版，由统信软件技术有限公司维护，面向党政军及行业客户。", "category": "国产OS", "confidence": 0.95},
        {"keyword": "deepin", "content": "深度操作系统（deepin）是武汉深之度科技有限公司开发的Linux发行版，以其美观的DDE桌面环境和良好的用户体验著称，是统信UOS的社区版基础。", "category": "国产OS", "confidence": 0.90},
        {"keyword": "鸿蒙", "content": "鸿蒙（HarmonyOS）是华为开发的分布式操作系统，采用微内核设计，支持多种设备形态，从手机、平板到智能穿戴、车载系统等全场景覆盖。", "category": "国产OS", "confidence": 0.95},
        {"keyword": "信创", "content": "信创（信息技术应用创新）是中国推动信息技术产业自主可控的战略，涵盖CPU、操作系统、数据库、中间件、办公软件等全产业链的国产化替代。", "category": "国产OS", "confidence": 0.95},
        {"keyword": "国产操作系统", "content": "国产操作系统主要包括麒麟、统信UOS、深度deepin、鸿蒙等，是国家信创战略的核心组成部分，旨在实现关键领域的信息技术自主可控。", "category": "国产OS", "confidence": 0.90},
        # ===== 办公软件 =====
        {"keyword": "WPS", "content": "WPS Office是金山办公开发的国产办公软件套件，包含文字、表格、演示、PDF等组件，与Microsoft Office高度兼容，是国内信创替代的首选方案。", "category": "办公软件", "confidence": 0.95},
        {"keyword": "Office", "content": "Microsoft Office是全球最广泛使用的办公软件套件，包括Word、Excel、PowerPoint等，支持文档编辑、数据分析、演示制作等功能。", "category": "办公软件", "confidence": 0.90},
        {"keyword": "办公软件", "content": "办公软件是用于日常办公文档处理、数据管理、演示汇报的工具，主流产品包括Microsoft Office、WPS Office、LibreOffice等。", "category": "办公软件", "confidence": 0.85},
        # ===== 校园场景 =====
        {"keyword": "校园", "content": "校园场景需要考虑学生隐私保护、教育公平性、网络安全等要素，AI在校园中的应用应注重教育价值而非单纯的技术展示。", "category": "校园场景", "confidence": 0.90},
        {"keyword": "教育", "content": "教育领域是AI应用的重要场景，包括智能辅导、自动批改、个性化学习路径推荐、教育数据分析等，应注重技术伦理和教育公平。", "category": "校园场景", "confidence": 0.90},
        {"keyword": "考试", "content": "考试是教育评价的重要手段，AI可用于智能组卷、自动阅卷、考试分析等，需确保公平性和安全性。", "category": "校园场景", "confidence": 0.85},
        {"keyword": "奖学金", "content": "奖学金是高校激励学生的重要机制，评选标准通常包括学业成绩、科研能力、社会实践等多维度评价。", "category": "校园场景", "confidence": 0.80},
        {"keyword": "就业", "content": "高校毕业生就业是社会关注焦点，学校应提供职业规划指导、实习机会对接、就业技能培训等支持服务。", "category": "校园场景", "confidence": 0.85},
        # ===== 活动策划 =====
        {"keyword": "马拉松", "content": "马拉松赛事策划需要制定详细的路线规划、安全保障方案、医疗保障措施、志愿者调度计划、物资补给方案和应急预案，通常需要提前3-6个月启动筹备。", "category": "活动策划", "confidence": 0.90},
        {"keyword": "运动会", "content": "校园运动会策划包括确定比赛项目（田径、球类等）、制定赛程安排、组织裁判团队、准备场地器材、安排后勤保障和医疗救护等。", "category": "活动策划", "confidence": 0.90},
        {"keyword": "活动策划", "content": "活动策划的核心要素包括：明确活动目标、确定目标受众、制定详细流程、预算规划、人员分工、场地选择、宣传推广、风险评估与应急预案。", "category": "活动策划", "confidence": 0.90},
        {"keyword": "志愿服务", "content": "志愿服务活动的组织需要明确服务目标、招募培训志愿者、制定服务计划、做好安全保障、建立激励机制，确保活动有序有效开展。", "category": "活动策划", "confidence": 0.85},
        # ===== 项目管理 =====
        {"keyword": "项目管理", "content": "项目管理是运用知识、技能、工具和技术来满足项目需求的过程，包括启动、规划、执行、监控和收尾五个阶段，核心要素是范围、时间、成本和质量。", "category": "项目管理", "confidence": 0.90},
        {"keyword": "预算", "content": "预算是对项目或活动所需资金的规划，包括收入预测和支出计划，应详细列出各项费用明细，预留10%-20%的应急资金。", "category": "项目管理", "confidence": 0.85},
        {"keyword": "风险管理", "content": "风险管理是识别、评估和应对项目中可能出现的风险，包括风险识别、风险分析、风险应对计划制定和风险监控四个步骤。", "category": "项目管理", "confidence": 0.85},
        # ===== 系统开发 =====
        {"keyword": "系统", "content": "系统设计需要考虑可扩展性、可靠性、安全性和性能，遵循模块化、高内聚低耦合的设计原则，选择合适的架构模式（微服务、单体、事件驱动等）。", "category": "系统开发", "confidence": 0.90},
        {"keyword": "开发", "content": "软件开发应遵循编码规范，采用版本控制（Git），进行充分的单元测试和集成测试，使用CI/CD流水线实现自动化构建和部署。", "category": "系统开发", "confidence": 0.90},
        {"keyword": "架构设计", "content": "系统架构设计是软件开发的蓝图，包括技术选型、模块划分、接口定义、数据流设计等，需要权衡性能、可维护性、可扩展性和成本。", "category": "系统开发", "confidence": 0.90},
        {"keyword": "技术选型", "content": "技术选型应综合考虑项目需求、团队能力、社区活跃度、长期维护成本、性能要求和安全性等因素，避免过度追求新技术而忽视稳定性。", "category": "系统开发", "confidence": 0.85},
        # ===== 数据分析 =====
        {"keyword": "数据分析", "content": "数据分析是通过统计和逻辑方法对数据进行系统性的检查、清洗、转换和建模，以发现有用信息、得出结论并支持决策的过程。", "category": "数据分析", "confidence": 0.90},
        {"keyword": "数据可视化", "content": "数据可视化是将数据以图形化方式呈现，帮助用户快速理解数据模式和趋势，常用工具包括ECharts、D3.js、Tableau、Matplotlib等。", "category": "数据分析", "confidence": 0.85},
        # ===== 生活常识 =====
        {"keyword": "健康", "content": "健康管理包括合理饮食、适量运动、充足睡眠和定期体检，建议每天运动30分钟、保持7-8小时睡眠、均衡摄入各类营养素。", "category": "生活常识", "confidence": 0.85},
        {"keyword": "营养", "content": "营养均衡的饮食应包括碳水化合物、蛋白质、脂肪、维生素、矿物质和膳食纤维六大类营养素，建议每天摄入12种以上食物。", "category": "生活常识", "confidence": 0.85},
        {"keyword": "急救", "content": "基本急救知识包括心肺复苏（CPR）、止血包扎、骨折固定、烧伤处理等，在紧急情况下可挽救生命，建议每个人都学习基本急救技能。", "category": "生活常识", "confidence": 0.85},
        {"keyword": "天气", "content": "天气预报是基于气象观测数据和数值模型预测未来天气状况，常见天气要素包括温度、湿度、降水、风速、气压等。", "category": "生活常识", "confidence": 0.80},
        # ===== 金融理财 =====
        {"keyword": "理财", "content": "个人理财是管理个人或家庭财务的过程，包括预算规划、储蓄、投资、保险、税务规划等，目标是实现财务安全和财富增值。", "category": "金融理财", "confidence": 0.85},
        {"keyword": "金融", "content": "金融行业涵盖银行、证券、保险、基金、信托等领域，是经济体系的核心，负责资金融通和资源配置。", "category": "金融理财", "confidence": 0.85},
        # ===== 法律常识 =====
        {"keyword": "法律", "content": "法律是由国家制定或认可并以国家强制力保证实施的行为规范体系，包括宪法、民法、刑法、行政法等，是维护社会秩序的基础。", "category": "法律常识", "confidence": 0.85},
        {"keyword": "知识产权", "content": "知识产权是对智力劳动成果所享有的专有权利，包括专利权、商标权、著作权（版权）、商业秘密等，保护创新者的合法权益。", "category": "法律常识", "confidence": 0.85},
        # ===== 方案设计 =====
        {"keyword": "方案", "content": "方案设计需要包含需求分析、目标设定、方案描述、实施步骤、资源需求、风险评估和预期成果等核心要素，确保方案的可行性和可操作性。", "category": "方案设计", "confidence": 0.90},
        {"keyword": "规划", "content": "规划需要明确目标、时间节点、资源配置和评估标准，应考虑多方利益相关者的需求，制定可执行的实施路径，并建立定期评估调整机制。", "category": "方案设计", "confidence": 0.90},
        {"keyword": "报告", "content": "报告撰写应遵循结构化原则，包括摘要、引言、方法、结果、讨论、结论等部分，使用客观、准确的语言，提供充分的论据和数据支持。", "category": "方案设计", "confidence": 0.85},
        # ===== 通用知识 =====
        {"keyword": "general", "content": "持续学习是个人成长的关键，良好的沟通能力是团队协作的基础，用户体验是产品成功的重要因素。", "category": "通用", "confidence": 0.70},
        {"keyword": "会议", "content": "高效会议应提前制定议程、控制时间、明确决策事项和行动项，会后及时发送会议纪要以确保执行到位。", "category": "通用", "confidence": 0.80},
        {"keyword": "文档", "content": "文档撰写应遵循清晰、简洁、准确的原则，使用结构化格式，包括标题、摘要、正文、结论等，适当的图表和示例可增强可读性。", "category": "通用", "confidence": 0.80},
    ]
    return items


# 全局单例
_knowledge_service: Optional[KnowledgeService] = None


def get_knowledge_service() -> KnowledgeService:
    global _knowledge_service
    if _knowledge_service is None:
        _knowledge_service = KnowledgeService()
    return _knowledge_service