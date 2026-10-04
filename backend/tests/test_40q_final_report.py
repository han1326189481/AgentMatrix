"""
Skill Engine V2.1 — 40题跨领域综合测试报告
计算机(10) + 办公(10) + AI(10) + 日常生活(10)

测试 Pipeline: TaskClassifier → ReviewEngine → TemplateEngine
"""
import sys
import os
import json
import time
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.skill_engine.task_engine import TaskClassifier
from core.skill_engine.review_engine import ReviewEngine
from core.skill_engine.template_engine import TemplateEngine

# ============================================================
# 40道精选测试题目
# ============================================================
QUESTIONS = {
    "计算机领域": [
        {"id": "CS01", "q": "Python中如何读取文件？请给出示例代码"},
        {"id": "CS02", "q": "什么是Git？请简要说明其核心概念"},
        {"id": "CS03", "q": "写一个Python函数实现快速排序算法"},
        {"id": "CS04", "q": "设计RESTful API有哪些最佳实践？"},
        {"id": "CS05", "q": "什么是Docker容器化？与虚拟机有什么区别？"},
        {"id": "CS06", "q": "设计一个微服务架构中的服务间通信方案"},
        {"id": "CS07", "q": "分析量子计算对现代密码学的影响"},
        {"id": "CS08", "q": "RAG系统中如何优化文档分块策略？"},
        {"id": "CS09", "q": "解释一下MCP（Model Context Protocol）是什么"},
        {"id": "CS10", "q": "如何在Linux中排查内存泄漏问题？"},
    ],
    "办公领域": [
        {"id": "OF01", "q": "如何写一封正式的商务邮件？"},
        {"id": "OF02", "q": "写一份项目周报的模板"},
        {"id": "OF03", "q": "策划一个团队建设活动方案"},
        {"id": "OF04", "q": "写一份市场调研分析报告的大纲"},
        {"id": "OF05", "q": "如何做一次有效的PPT演讲？"},
        {"id": "OF06", "q": "会议纪要应该怎么写？"},
        {"id": "OF07", "q": "对某创业公司进行SWOT分析"},
        {"id": "OF08", "q": "如何制定年度工作计划？"},
        {"id": "OF09", "q": "商务谈判中有什么技巧？"},
        {"id": "OF10", "q": "写一份校园创业计划书"},
    ],
    "AI领域": [
        {"id": "AI01", "q": "什么是Transformer架构？请简要说明"},
        {"id": "AI02", "q": "解释一下Attention机制的原理"},
        {"id": "AI03", "q": "大语言模型的Prompt Engineering有哪些技巧？"},
        {"id": "AI04", "q": "对比分析RAG和Fine-tuning的适用场景"},
        {"id": "AI05", "q": "什么是Agent？AI Agent与普通LLM有什么区别？"},
        {"id": "AI06", "q": "多Agent系统中如何实现任务编排？"},
        {"id": "AI07", "q": "深度学习中的梯度消失问题如何解决？"},
        {"id": "AI08", "q": "如何评估一个LLM的输出质量？"},
        {"id": "AI09", "q": "解释一下LangChain框架的核心概念"},
        {"id": "AI10", "q": "向量数据库在AI应用中起什么作用？"},
    ],
    "日常生活": [
        {"id": "DA01", "q": "今天天气怎么样？"},
        {"id": "DA02", "q": "推荐一道简单的家常菜及其做法"},
        {"id": "DA03", "q": "写一首关于春天的短诗"},
        {"id": "DA04", "q": "如何保持健康的生活方式？"},
        {"id": "DA05", "q": "推荐几本值得阅读的好书"},
        {"id": "DA06", "q": "写一个周末旅行计划"},
        {"id": "DA07", "q": "如何缓解工作压力？"},
        {"id": "DA08", "q": "养宠物需要注意哪些事项？"},
        {"id": "DA09", "q": "写一段广告文案推广新开的咖啡店"},
        {"id": "DA10", "q": "如何在有限预算下装修小户型？"},
    ],
}

# 模拟 Writer Agent 输出（根据问题类型生成合理内容）
SIMULATED_OUTPUTS = {
    "CS01": "## Python文件读取\n\nPython提供了多种文件读取方式：\n\n```python\n# 方式1: open + read\nwith open('file.txt', 'r', encoding='utf-8') as f:\n    content = f.read()\n\n# 方式2: 逐行读取\nwith open('file.txt', 'r') as f:\n    for line in f:\n        print(line.strip())\n\n# 方式3: readlines\nwith open('file.txt', 'r') as f:\n    lines = f.readlines()\n```",
    "CS02": "## Git核心概念\n\nGit是一个分布式版本控制系统，核心概念包括：\n\n1. **仓库(Repository)**: 存储项目所有文件和历史记录\n2. **提交(Commit)**: 保存当前工作目录的快照\n3. **分支(Branch)**: 独立的开发线，便于并行开发\n4. **合并(Merge)**: 将不同分支的修改合并到一起\n5. **远程(Remote)**: 远程仓库，用于团队协作",
    "CS03": "## 快速排序实现\n\n```python\ndef quick_sort(arr):\n    if len(arr) <= 1:\n        return arr\n    pivot = arr[len(arr) // 2]\n    left = [x for x in arr if x < pivot]\n    middle = [x for x in arr if x == pivot]\n    right = [x for x in arr if x > pivot]\n    return quick_sort(left) + middle + quick_sort(right)\n```\n\n时间复杂度：平均O(n log n)，最坏O(n²)\n空间复杂度：O(log n)",
    "CS04": "## RESTful API最佳实践\n\n### 1. URL设计\n- 使用名词而非动词：`/users` 而非 `/getUsers`\n- 使用复数形式：`/users/123`\n- 层级关系：`/users/123/orders`\n\n### 2. HTTP方法\n- GET: 获取资源\n- POST: 创建资源\n- PUT: 完整更新\n- PATCH: 部分更新\n- DELETE: 删除资源\n\n### 3. 状态码\n- 200: 成功\n- 201: 创建成功\n- 400: 请求错误\n- 404: 未找到\n- 500: 服务器错误\n\n### 4. 版本控制\n- URL版本：`/api/v1/users`\n- Header版本：`Accept: application/vnd.api.v1+json`",
    "CS05": "## Docker容器化\n\nDocker是一个开源的应用容器引擎，让开发者可以打包应用及其依赖到轻量级容器中。\n\n### 与虚拟机的区别\n| 特性 | Docker | 虚拟机 |\n|------|--------|--------|\n| 启动速度 | 秒级 | 分钟级 |\n| 资源占用 | MB级 | GB级 |\n| 隔离级别 | 进程级 | 操作系统级 |\n| 镜像大小 | MB级 | GB级 |\n\n### 核心概念\n- **镜像(Image)**: 只读模板\n- **容器(Container)**: 镜像的运行实例\n- **Dockerfile**: 构建镜像的脚本\n- **Docker Compose**: 多容器编排",
    "CS06": "## 微服务间通信方案\n\n### 1. 同步通信\n- **REST API**: 简单易用，适合查询场景\n- **gRPC**: 高性能，支持双向流，适合内部服务\n\n### 2. 异步通信\n- **消息队列(RabbitMQ/Kafka)**: 解耦、削峰、异步处理\n- **事件总线**: 发布-订阅模式，适合事件驱动架构\n\n### 3. 服务发现\n- **Consul/Eureka**: 服务注册与发现\n- **Kubernetes Service**: K8s原生支持\n\n### 4. 容错机制\n- **熔断器(Circuit Breaker)**: 防止级联故障\n- **重试+指数退避**: 处理临时故障\n- **超时控制**: 防止资源耗尽",
    "CS07": "## 量子计算对密码学的影响\n\n### 1. Shor算法威胁\nShor算法能够在多项式时间内分解大整数，直接威胁RSA和ECC等公钥密码体系。\n\n### 2. Grover算法影响\nGrover算法提供平方级加速，使AES-128的有效安全性降至64位。\n\n### 3. 后量子密码学\nNIST已标准化CRYSTALS-Kyber、CRYSTALS-Dilithium等后量子算法。\n\n### 4. 过渡策略\n建议采用混合密码方案，同时支持传统算法和后量子算法。",
    "CS08": "## RAG文档分块策略优化\n\n### 1. 分块大小选择\n- **小分块(128-256 tokens)**: 精确匹配，适合事实性问答\n- **中分块(512-1024 tokens)**: 平衡精度和上下文\n- **大分块(2048+ tokens)**: 保留完整上下文\n\n### 2. 重叠策略\n- 分块间保留10-20%重叠\n- 使用句子边界自然切分\n\n### 3. 语义分块\n- 基于段落结构分块\n- 使用Markdown标题层级\n- 保留代码块完整性\n\n### 4. 元数据增强\n- 添加文档标题、章节信息\n- 保留层级关系",
    "CS09": "## MCP协议详解\n\nMCP（Model Context Protocol）是一种开放协议，用于标准化AI模型与外部工具/数据源之间的交互。\n\n### 核心概念\n- **Server**: 提供工具和资源的服务端\n- **Client**: 调用工具的AI应用\n- **Tool**: 可执行的操作（如搜索、计算）\n- **Resource**: 可访问的数据（如文件、数据库）\n\n### 优势\n- 统一接口，减少重复开发\n- 插件化架构，易于扩展\n- 标准化协议，跨模型兼容",
    "CS10": "## Linux内存泄漏排查\n\n### 1. 监控工具\n- **top/htop**: 实时查看进程内存使用\n- **free -m**: 查看系统内存概况\n- **vmstat**: 虚拟内存统计\n\n### 2. 深入分析\n- **pmap -x PID**: 查看进程内存映射\n- **valgrind**: 内存泄漏检测工具\n- **/proc/PID/smaps**: 详细内存信息\n\n### 3. 排查步骤\n1. 确认内存增长趋势\n2. 定位可疑进程\n3. 分析内存分配模式\n4. 使用profiling工具定位代码\n5. 修复并验证",
    "OF01": "## 商务邮件写作指南\n\n### 基本结构\n1. **主题行**: 简明扼要，突出核心内容\n2. **称呼**: 尊敬的XX先生/女士\n3. **正文**: 开门见山，分段清晰\n4. **结尾**: 礼貌总结，期待回复\n5. **签名**: 姓名、职位、联系方式\n\n### 注意事项\n- 使用正式语言，避免口语化\n- 检查拼写和语法\n- 附件需提前说明\n- 及时回复邮件",
    "OF02": "## 项目周报模板\n\n### 项目名称：XXX\n### 报告周期：2026年X月X日 - X月X日\n### 报告人：XXX\n\n### 一、本周进展\n1. 完成需求分析文档\n2. 完成数据库设计评审\n3. 前端页面开发进度80%\n\n### 二、遇到的问题\n1. 第三方API接口响应慢\n2. 团队成员请假影响进度\n\n### 三、下周计划\n1. 完成前端页面开发\n2. 开始后端接口联调\n3. 准备项目中期评审\n\n### 四、风险提示\n- 接口联调可能延期1-2天\n- 需要协调测试资源",
    "OF03": "## 团队建设活动方案\n\n### 一、活动主题\n凝心聚力，共创未来\n\n### 二、活动目标\n- 增强团队凝聚力\n- 提升跨部门沟通\n- 缓解工作压力\n\n### 三、活动安排\n- **时间**: 2026年8月15日（周六）\n- **地点**: 郊区拓展基地\n- **人数**: 30人\n- **预算**: 5000元\n\n### 四、活动流程\n| 时间 | 内容 |\n|------|------|\n| 09:00 | 集合出发 |\n| 10:00 | 破冰游戏 |\n| 12:00 | 午餐 |\n| 14:00 | 团队挑战 |\n| 17:00 | 总结分享 |\n\n### 五、安全预案\n- 购买团体意外险\n- 配备急救箱\n- 提前查看天气预报",
    "OF04": "## 市场调研分析报告大纲\n\n### 一、调研概述\n- 调研目的\n- 调研范围\n- 调研方法\n\n### 二、市场环境分析\n- 宏观环境（PEST分析）\n- 行业现状与趋势\n- 市场规模与增长率\n\n### 三、竞争分析\n- 主要竞争对手\n- 竞争格局（波特五力）\n- SWOT分析\n\n### 四、用户分析\n- 目标用户画像\n- 用户需求与痛点\n- 购买决策因素\n\n### 五、结论与建议\n- 市场机会\n- 战略建议\n- 风险提示",
    "OF05": "## PPT演讲技巧\n\n### 一、内容准备\n1. 明确演讲目的\n2. 结构清晰：开场-主体-结尾\n3. 每页一个核心观点\n4. 图文并茂，避免文字堆砌\n\n### 二、视觉设计\n- 使用统一模板\n- 字体不小于24pt\n- 配色不超过3种\n- 动画适度使用\n\n### 三、演讲技巧\n- 开场吸引注意力\n- 与观众保持眼神交流\n- 控制语速和语调\n- 准备应对提问\n\n### 四、时间管理\n- 提前演练计时\n- 留出Q&A时间\n- 准备备用内容",
    "OF06": "## 会议纪要写作要点\n\n### 基本要素\n- 会议主题\n- 时间地点\n- 参会人员\n- 主持人/记录人\n\n### 内容结构\n1. **会议议题**: 逐一列出讨论议题\n2. **讨论要点**: 各方观点摘要\n3. **决议事项**: 明确的决策结果\n4. **待办事项**: 责任人+截止时间\n5. **下次会议**: 时间和议题\n\n### 写作技巧\n- 客观记录，不掺杂个人观点\n- 决议事项要明确具体\n- 待办事项SMART化\n- 24小时内发送给参会者",
    "OF07": "## SWOT分析报告\n\n### 公司概况\n某校园社交创业公司，面向大学生群体\n\n### 优势(Strengths)\n- 精准的用户群体定位\n- 年轻有活力的团队\n- 低获客成本\n\n### 劣势(Weaknesses)\n- 资金有限\n- 品牌知名度低\n- 变现模式不成熟\n\n### 机会(Opportunities)\n- 校园市场蓝海\n- 社交电商趋势\n- 政策支持大学生创业\n\n### 威胁(Threats)\n- 巨头可能进入该领域\n- 用户留存难度大\n- 校园政策变化风险\n\n### 战略建议\n1. 聚焦差异化功能\n2. 建立校园大使网络\n3. 探索多元化变现",
    "OF08": "## 年度工作计划制定\n\n### 一、目标设定\n- 年度总目标（SMART原则）\n- 季度分解目标\n- 关键成果指标(KPI)\n\n### 二、重点工作\n| 季度 | 重点任务 | 里程碑 |\n|------|----------|--------|\n| Q1 | 产品V1.0上线 | 3月发布 |\n| Q2 | 用户增长 | 10万用户 |\n| Q3 | 商业化探索 | 首笔收入 |\n| Q4 | 规模化运营 | 盈亏平衡 |\n\n### 三、资源规划\n- 人力资源配置\n- 预算分配\n- 技术投入\n\n### 四、风险管理\n- 关键风险识别\n- 应对预案\n- 定期复盘机制",
    "OF09": "## 商务谈判技巧\n\n### 一、谈判前准备\n1. 明确谈判目标和底线\n2. 了解对方需求和背景\n3. 准备数据和案例支撑\n4. 制定BATNA（最佳替代方案）\n\n### 二、谈判中策略\n- 先听后说，了解对方诉求\n- 强调共同利益而非对立\n- 适当让步换取更大利益\n- 使用客观标准来论证\n\n### 三、沟通技巧\n- 保持冷静专业\n- 使用开放性问题\n- 注意非语言信号\n- 适时总结确认\n\n### 四、谈判后跟进\n- 书面确认协议要点\n- 建立后续沟通机制\n- 维护长期合作关系",
    "OF10": "## 校园创业计划书\n\n### 一、项目概述\n本项目旨在打造校园二手交易平台，连接校内学生进行闲置物品交易。\n\n### 二、市场分析\n- 目标用户：在校大学生\n- 市场规模：全国3000万大学生\n- 需求痛点：毕业季大量闲置物品处理\n\n### 三、商业模式\n- 交易佣金：5%\n- 广告收入\n- 增值服务（验货、物流）\n\n### 四、运营计划\n- 首批入驻10所高校\n- 校园大使招募\n- 线上推广+线下活动\n\n### 五、财务预测\n- 启动资金：10万元\n- 预计6个月盈亏平衡\n- 首年GMV目标：500万元",
    "AI01": "## Transformer架构\n\nTransformer是2017年由Google提出的革命性神经网络架构，彻底改变了NLP领域。\n\n### 核心组件\n1. **Self-Attention**: 让每个词关注序列中所有其他词\n2. **Multi-Head Attention**: 多个注意力头并行计算\n3. **Position Encoding**: 注入位置信息\n4. **Feed-Forward Network**: 非线性变换\n5. **Layer Normalization**: 稳定训练\n\n### 优势\n- 并行计算，训练速度快\n- 长距离依赖建模能力强\n- 可扩展性强（GPT、BERT均基于此）",
    "AI02": "## Attention机制原理\n\nAttention机制的核心思想是让模型在处理输入时，能够动态地关注更重要的部分。\n\n### 计算步骤\n1. **计算相似度**: Query与Key点积得到注意力分数\n2. **缩放**: 除以√d_k防止梯度消失\n3. **Softmax**: 归一化得到注意力权重\n4. **加权求和**: 权重与Value相乘得到输出\n\n### 公式\nAttention(Q,K,V) = softmax(QK^T/√d_k)V\n\n### 变体\n- Self-Attention: Q=K=V\n- Cross-Attention: Q来自Decoder，K,V来自Encoder\n- Multi-Head: 多个注意力头并行",
    "AI03": "## Prompt Engineering技巧\n\n### 1. 角色设定\n赋予LLM特定角色，如\"你是一位资深Python工程师\"\n\n### 2. Few-Shot提示\n提供2-3个示例，帮助模型理解期望输出格式\n\n### 3. 思维链(Chain-of-Thought)\n引导模型逐步推理：\"让我们一步步思考\"\n\n### 4. 结构化输出\n明确要求JSON、Markdown等格式\n\n### 5. 约束条件\n设定字数、格式、风格等限制\n\n### 6. 负面提示\n明确说明不要做什么：\"不要使用专业术语\"",
    "AI04": "## RAG vs Fine-tuning对比\n\n### RAG (检索增强生成)\n- **适用场景**: 需要外部知识、实时数据\n- **优势**: 知识可更新、幻觉少、成本低\n- **劣势**: 依赖检索质量、延迟较高\n\n### Fine-tuning (微调)\n- **适用场景**: 特定风格、领域专业术语\n- **优势**: 风格一致、推理快\n- **劣势**: 知识固化、成本高、需要标注数据\n\n### 选择建议\n| 场景 | 推荐方案 |\n|------|----------|\n| 企业知识库问答 | RAG |\n| 客服机器人 | RAG + Fine-tuning |\n| 代码生成 | Fine-tuning |\n| 实时新闻分析 | RAG |",
    "AI05": "## AI Agent vs 普通LLM\n\n### 普通LLM\n- 单次输入输出\n- 无自主行动能力\n- 无外部工具调用\n\n### AI Agent\n- 具备自主决策能力\n- 可调用外部工具(搜索、计算、API)\n- 具有记忆和规划能力\n- 能分解复杂任务\n\n### Agent核心组件\n1. **LLM大脑**: 推理和决策\n2. **工具集**: 外部能力扩展\n3. **记忆系统**: 短期+长期记忆\n4. **规划模块**: 任务分解与执行",
    "AI06": "## 多Agent任务编排\n\n### 1. 编排模式\n- **顺序编排**: Agent按固定顺序执行\n- **并行编排**: 多个Agent同时工作\n- **条件编排**: 根据结果动态路由\n- **循环编排**: 迭代优化直到满足条件\n\n### 2. 通信机制\n- 消息传递\n- 共享内存/黑板模式\n- 事件驱动\n\n### 3. 协调策略\n- 中心化调度器\n- 去中心化协商\n- 混合模式\n\n### 4. 容错设计\n- Agent心跳检测\n- 任务超时重试\n- 状态检查点",
    "AI07": "## 梯度消失问题解决方案\n\n### 问题原因\n在深层网络中，反向传播时梯度逐层衰减，导致浅层参数无法更新。\n\n### 解决方案\n1. **ReLU激活函数**: 避免Sigmoid/Tanh的饱和区\n2. **Batch Normalization**: 标准化每层输入\n3. **残差连接(ResNet)**: 跨层直连，梯度可直接传播\n4. **LSTM/GRU**: 门控机制缓解梯度消失\n5. **梯度裁剪**: 限制梯度最大值\n6. **合理初始化**: Xavier/He初始化",
    "AI08": "## LLM输出质量评估\n\n### 1. 自动评估指标\n- **BLEU/ROUGE**: 文本相似度\n- **Perplexity**: 语言模型困惑度\n- **BERTScore**: 语义相似度\n\n### 2. 人工评估维度\n- **准确性**: 事实是否正确\n- **相关性**: 是否回答用户问题\n- **流畅性**: 语言是否自然\n- **完整性**: 是否覆盖关键信息\n- **安全性**: 是否有害内容\n\n### 3. LLM-as-Judge\n使用更强的LLM来评估输出质量\n\n### 4. 多维度评分\n建立评分卡，从多个维度系统评估",
    "AI09": "## LangChain框架核心概念\n\n### 1. Chains(链)\n将多个组件串联成工作流\n\n### 2. Agents(智能体)\n动态决策调用哪些工具\n\n### 3. Tools(工具)\n搜索引擎、计算器、API等\n\n### 4. Memory(记忆)\n对话历史管理\n\n### 5. Retrievers(检索器)\n文档检索和向量搜索\n\n### 6. Prompt Templates\n可复用的提示模板\n\n### 典型工作流\nUser Input → Prompt Template → LLM → Output Parser → Next Step",
    "AI10": "## 向量数据库在AI中的作用\n\n### 核心功能\n将非结构化数据（文本、图像）转换为向量表示，支持相似度搜索。\n\n### 主要应用\n1. **语义搜索**: 基于含义而非关键词\n2. **RAG系统**: 知识库检索增强\n3. **推荐系统**: 相似内容推荐\n4. **异常检测**: 偏离正常模式的向量\n\n### 主流方案\n- Pinecone: 托管向量数据库\n- Milvus: 开源分布式向量数据库\n- Chroma: 轻量级嵌入式方案\n- FAISS: Facebook开源向量检索库\n\n### 关键指标\n- 召回率(Recall)\n- 查询延迟\n- 索引构建速度",
    "DA01": "你好！今天天气不错，适合出门活动。不过建议出门前查看一下当地的天气预报，因为不同地区天气差异较大。",
    "DA02": "## 番茄炒蛋做法\n\n### 食材\n- 番茄2个\n- 鸡蛋3个\n- 葱花、盐、糖适量\n\n### 步骤\n1. 鸡蛋打散，加少许盐\n2. 番茄切块\n3. 热油炒鸡蛋，盛出备用\n4. 炒番茄至出汁\n5. 加入鸡蛋翻炒\n6. 加盐和少许糖调味\n7. 撒葱花出锅\n\n这道菜简单快手，营养丰富，非常适合新手！",
    "DA03": "春风拂面暖洋洋，\n百花争艳吐芬芳。\n柳枝摇曳燕归来，\n万物复苏好时光。",
    "DA04": "## 健康生活方式指南\n\n### 饮食\n- 均衡营养，多吃蔬果\n- 减少加工食品\n- 定时定量，不暴饮暴食\n\n### 运动\n- 每周至少150分钟中等强度运动\n- 结合有氧和力量训练\n- 选择喜欢的运动方式\n\n### 作息\n- 保证7-8小时睡眠\n- 固定作息时间\n- 睡前远离电子设备\n\n### 心理健康\n- 学会压力管理\n- 保持社交联系\n- 培养兴趣爱好",
    "DA05": "## 好书推荐\n\n1. **《人类简史》** - 尤瓦尔·赫拉利\n   从宏观视角回顾人类发展历程\n\n2. **《思考，快与慢》** - 丹尼尔·卡尼曼\n   了解人类思维的两种模式\n\n3. **《三体》** - 刘慈欣\n   中国科幻巅峰之作\n\n4. **《非暴力沟通》** - 马歇尔·卢森堡\n   改善人际沟通的实用指南\n\n5. **《刻意练习》** - 安德斯·艾利克森\n   揭秘如何成为领域专家",
    "DA06": "## 周末旅行计划\n\n### 目的地：杭州\n### 时间：周六-周日\n\n### 周六\n- 08:00 出发\n- 10:00 到达西湖，漫步苏堤\n- 12:00 楼外楼午餐\n- 14:00 灵隐寺\n- 17:00 入住酒店\n- 19:00 河坊街夜市\n\n### 周日\n- 08:00 早餐\n- 09:00 龙井村品茶\n- 12:00 农家菜午餐\n- 14:00 返程\n\n### 预算\n- 交通：200元\n- 住宿：300元\n- 餐饮：300元\n- 门票：100元",
    "DA07": "## 缓解工作压力\n\n### 1. 时间管理\n- 使用番茄工作法\n- 分清优先级（重要/紧急矩阵）\n- 学会拒绝不合理的任务\n\n### 2. 身体调节\n- 规律运动释放内啡肽\n- 深呼吸放松法\n- 保证充足睡眠\n\n### 3. 心理调节\n- 正念冥想\n- 写日记整理情绪\n- 与朋友倾诉\n\n### 4. 工作习惯\n- 定期休息，避免长时间连续工作\n- 创造舒适的工作环境\n- 设定工作与生活的边界",
    "DA08": "## 养宠物注意事项\n\n### 1. 前期准备\n- 评估自己的时间和经济能力\n- 了解不同宠物的习性和需求\n- 准备必要的用品（食物、窝、玩具）\n\n### 2. 日常养护\n- 定时定量喂食\n- 定期疫苗接种\n- 保持清洁卫生\n- 适当运动\n\n### 3. 法律与责任\n- 办理相关证件\n- 遛狗牵绳\n- 不随意遗弃\n\n### 4. 常见问题\n- 掉毛期加强梳理\n- 分离焦虑训练\n- 老年宠物特殊护理",
    "DA09": "## 新店开业广告文案\n\n☕ **晨光咖啡，温暖你的每一天**\n\n精选阿拉比卡咖啡豆，\n匠心手冲，每一杯都是艺术品。\n\n🎉 **开业特惠**\n- 全场饮品买一送一\n- 会员充值100送30\n- 前100名顾客送限量杯具\n\n📍 地址：XX路XX号\n📅 活动时间：2026年8月1日-8月7日\n\n# 一杯好咖啡，开启美好一天\n# 晨光咖啡 # 新店开业",
    "DA10": "## 小户型装修攻略\n\n### 一、空间利用\n- 多功能家具（沙发床、折叠桌）\n- 墙面收纳系统\n- 榻榻米储物\n\n### 二、视觉扩容\n- 浅色系为主色调\n- 大面积镜子\n- 统一地板延伸视觉\n\n### 三、预算分配\n| 项目 | 预算占比 |\n|------|----------|\n| 硬装 | 40% |\n| 家具 | 30% |\n| 软装 | 20% |\n| 预留 | 10% |\n\n### 四、省钱技巧\n- 网购比价\n- 淡季装修\n- DIY部分装饰",
}


def main():
    classifier = TaskClassifier()
    engine = ReviewEngine()
    te = TemplateEngine()

    print("=" * 80)
    print("  AgentMatrix Skill Engine V2.1 — 40题跨领域综合测试")
    print(f"  测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)

    all_results = []
    domain_stats = {}

    for domain, items in QUESTIONS.items():
        print(f"\n{'#' * 80}")
        print(f"# {domain} ({len(items)}题)")
        print(f"{'#' * 80}")

        domain_results = []
        for item in items:
            qid = item["id"]
            q = item["q"]
            output = SIMULATED_OUTPUTS.get(qid, "这是一个测试回答内容。")

            t0 = time.time()

            # 1. TaskClassifier
            profile = classifier.classify(q)
            task_type = profile.task_type.value

            # 2. ReviewEngine
            skill_path = {
                "计算机领域": ["root", "tech"],
                "办公领域": ["root", "business"],
                "AI领域": ["root", "tech", "ai"],
                "日常生活": ["root", "daily"],
            }[domain]

            report = engine.review(
                user_task=q,
                summary=f"{domain}测试",
                writer_output=output,
                skill_path=skill_path,
            )

            # 3. TemplateEngine
            domain_map = {
                "计算机领域": "tech",
                "办公领域": "business",
                "AI领域": "tech",
                "日常生活": "daily",
            }
            tmpl = te.select_template(user_query=q, domain=domain_map[domain])

            elapsed = round((time.time() - t0) * 1000, 1)

            result = {
                "id": qid,
                "domain": domain,
                "question": q[:60] + ("..." if len(q) > 60 else ""),
                "task_type": task_type,
                "difficulty": report["difficulty"]["threshold"],
                "diff_level": report["difficulty"]["level"],
                "review_score": report["review_score"],
                "pass": "PASS" if report["pass"] else "FAIL",
                "risk": report["risk"]["level"],
                "confidence": report["confidence"],
                "template": tmpl.meta.template_id if tmpl else "none",
                "elapsed_ms": elapsed,
                "top_dim": max(report["dimensions"], key=lambda d: report["dimensions"][d]["score"]),
                "low_dim": min(report["dimensions"], key=lambda d: report["dimensions"][d]["score"]),
            }

            domain_results.append(result)
            all_results.append(result)

            # 进度输出
            print(f"  {qid} | {task_type:10s} | diff={report['difficulty']['threshold']:.2f}({report['difficulty']['level']:6s}) | "
                  f"score={report['review_score']:.2f} | {result['pass']} | "
                  f"risk={report['risk']['level']} | conf={report['confidence']:.2f} | "
                  f"top={ result['top_dim']} | low={ result['low_dim']} | "
                  f"tmpl={result['template']} | {elapsed}ms")

        # 领域统计
        scores = [r["review_score"] for r in domain_results]
        diffs = [r["difficulty"] for r in domain_results]
        pass_count = sum(1 for r in domain_results if r["pass"] == "PASS")
        domain_stats[domain] = {
            "avg_score": round(sum(scores) / len(scores), 2),
            "avg_diff": round(sum(diffs) / len(diffs), 2),
            "pass_rate": f"{pass_count}/{len(domain_results)}",
            "types": list(set(r["task_type"] for r in domain_results)),
        }

    # ============================================================
    # 汇总报告
    # ============================================================
    print("\n\n")
    print("=" * 80)
    print("  汇总报告")
    print("=" * 80)

    print(f"\n{'领域':<12} {'平均分':<8} {'平均难度':<10} {'通过率':<10} {'任务类型'}")
    print("-" * 80)
    total_pass = 0
    total_scores = []
    total_diffs = []
    for domain, stats in domain_stats.items():
        print(f"{domain:<12} {stats['avg_score']:<8} {stats['avg_diff']:<10} {stats['pass_rate']:<10} {', '.join(stats['types'])}")
        total_pass += int(stats["pass_rate"].split("/")[0])
        total_scores.extend([r["review_score"] for r in all_results if r["domain"] == domain])
        total_diffs.extend([r["difficulty"] for r in all_results if r["domain"] == domain])

    print("-" * 80)
    print(f"{'总计':<12} {round(sum(total_scores)/len(total_scores),2):<8} {round(sum(total_diffs)/len(total_diffs),2):<10} {total_pass}/{len(all_results)}")

    # 难度分布
    diff_levels = {"simple": 0, "medium": 0, "complex": 0, "expert": 0}
    for r in all_results:
        diff_levels[r["diff_level"]] = diff_levels.get(r["diff_level"], 0) + 1
    print(f"\n难度分布: simple={diff_levels['simple']}, medium={diff_levels['medium']}, complex={diff_levels['complex']}, expert={diff_levels['expert']}")

    # 模板命中
    tmpl_hits = sum(1 for r in all_results if r["template"] != "none")
    print(f"模板命中: {tmpl_hits}/{len(all_results)}")

    # 风险分布
    risk_levels = {"low": 0, "medium": 0, "high": 0}
    for r in all_results:
        risk_levels[r["risk"]] = risk_levels.get(r["risk"], 0) + 1
    print(f"风险分布: low={risk_levels['low']}, medium={risk_levels['medium']}, high={risk_levels['high']}")

    # 平均耗时
    avg_elapsed = round(sum(r["elapsed_ms"] for r in all_results) / len(all_results), 1)
    print(f"平均耗时: {avg_elapsed}ms")

    # 详细维度分析
    print(f"\n{'='*80}")
    print("  各维度平均分")
    print(f"{'='*80}")
    dim_names = ["accuracy", "professional", "completeness", "reasoning", "structure", "actionable"]
    print(f"{'领域':<12}", end="")
    for d in dim_names:
        print(f"{d:<12}", end="")
    print()
    print("-" * 84)

    for domain in domain_stats:
        domain_results = [r for r in all_results if r["domain"] == domain]
        # Recalculate from engine for dimension details
        print(f"{domain:<12}", end="")
        for d in dim_names:
            dim_scores = []
            for item in QUESTIONS[domain]:
                qid = item["id"]
                output = SIMULATED_OUTPUTS.get(qid, "测试回答")
                skill_path = {
                    "计算机领域": ["root", "tech"],
                    "办公领域": ["root", "business"],
                    "AI领域": ["root", "tech", "ai"],
                    "日常生活": ["root", "daily"],
                }[domain]
                report = engine.review(
                    user_task=item["q"], summary=f"{domain}测试",
                    writer_output=output, skill_path=skill_path, use_cache=False,
                )
                dim_scores.append(report["dimensions"][d]["score"])
            avg = round(sum(dim_scores) / len(dim_scores), 2)
            print(f"{avg:<12}", end="")
        print()

    # 典型问题详情
    print(f"\n{'='*80}")
    print("  各领域最高/最低分问题")
    print(f"{'='*80}")

    for domain in domain_stats:
        domain_results = [r for r in all_results if r["domain"] == domain]
        best = max(domain_results, key=lambda r: r["review_score"])
        worst = min(domain_results, key=lambda r: r["review_score"])
        print(f"\n{domain}:")
        print(f"  最高: {best['id']} ({best['review_score']:.2f}) — {best['question']}")
        print(f"        type={best['task_type']}, diff={best['difficulty']}, risk={best['risk']}, top_dim={best['top_dim']}")
        print(f"  最低: {worst['id']} ({worst['review_score']:.2f}) — {worst['question']}")
        print(f"        type={worst['task_type']}, diff={worst['difficulty']}, risk={worst['risk']}, low_dim={worst['low_dim']}")

    print(f"\n{'='*80}")
    print("  测试完成")
    print(f"{'='*80}")

    return all_results, domain_stats


if __name__ == "__main__":
    main()