# -*- mode: python ; coding: utf-8 -*-
"""
AgentMatrix 完整后端 PyInstaller 打包配置
迭代 7 — 单文件 EXE + 资源嵌入
"""
import os

# 后端根目录
backend_dir = os.path.dirname(os.path.abspath(SPECPATH))

# ── 数据文件（嵌入到 sys._MEIPASS） ──
datas = [
    # 提示词模板（只读）
    ('prompts', 'prompts'),
    # 评分规则（只读）
    ('configs', 'configs'),
    # 默认配置文件（首次运行时复制到 APPDATA）
    (os.path.join('config', 'app_config.json'), 'config'),
    # 环境变量文件（含 API Key 等配置）
    ('.env', '.'),
]

# 过滤不存在的路径
datas = [(src, dst) for src, dst in datas if os.path.exists(os.path.join(backend_dir, src))]

# ── 隐藏导入 ──
hiddenimports = [
    # Web Framework
    'uvicorn', 'uvicorn.loops', 'uvicorn.loops.auto',
    'uvicorn.protocols', 'uvicorn.protocols.http',
    'uvicorn.protocols.http.auto',
    'uvicorn.protocols.websockets',
    'uvicorn.protocols.websockets.auto',
    'uvicorn.lifespan', 'uvicorn.lifespan.on',
    'fastapi', 'starlette',
    # WebSocket
    'socketio', 'python_socketio',
    'engineio', 'engineio.async_drivers',
    'engineio.async_drivers.asgi',
    # Database
    'sqlalchemy', 'pymysql',
    # HTTP
    'httpx', 'httpcore',
    # Configuration
    'pydantic', 'pydantic_settings',
    'yaml', 'dotenv',
    # Export (optional)
    'docx', 'pptx',
    # Logging
    'loguru',
    # Standard library often missed
    'asyncio', 'json', 'logging', 're', 'io',
    'multiprocessing', 'email', 'email.mime',
    'email.mime.text', 'email.mime.multipart',
    # AgentMatrix internal
    'agents', 'agents.base', 'agents.base.agent',
    'agents.base.agent_registry', 'agents.base.utils',
    'agents.knowledge', 'agents.writer',
    'agents.review', 'agents.judge',
    'agents.result', 'agents.summary',
    'api', 'api.v1', 'api.v1.router',
    'api.v1.agents', 'api.v1.agents.router',
    'api.v1.chat', 'api.v1.chat.router',
    'api.v1.config', 'api.v1.config.router',
    'api.v1.export', 'api.v1.export.router',
    'api.v1.knowledge', 'api.v1.knowledge.router',
    'api.v1.metrics', 'api.v1.metrics.router',
    'api.v1.workflow', 'api.v1.workflow.router',
    'api.v1.sandbox', 'api.v1.sandbox.router',
    'api.websocket', 'api.websocket.manager',
    'app', 'app.config', 'app.database', 'app.dependencies',
    'config', 'config.manager',
    'core', 'core.llm', 'core.llm.client',
    'core.llm.ollama_client',
    'core.model_registry',
    'core.workflow', 'core.workflow.service',
    'core.dynamic_router', 'core.dynamic_router.router',
    'core.export',
    'core.knowledge',
    # V3: Graphs（IntentGraph/SkillGraph/ReasoningGraph/CapabilityGraph）
    'core.graphs', 'core.graphs.intent_graph',
    'core.graphs.skill_graph', 'core.graphs.reasoning_graph',
    'core.graphs.capability_graph', 'core.graphs.graph_builder',
    # V3: Engines（CognitiveController/Decomposer/Planner/LearningEngine etc.）
    'core.engines', 'core.engines.cognitive_controller',
    'core.engines.decomposer', 'core.engines.local_planner',
    'core.engines.learning_engine', 'core.engines.patch_validator',
    'core.engines.knowledge_recommendation',
    # V3: Personal Brain
    'core.personal_brain', 'core.personal_brain.brain',
    # V3: Memory Store（长期记忆 JSON 文件存储）
    'core.memory_store', 'core.memory_store.store', 'core.memory_store.extractor',
    # V3: Sandbox（多沙盒架构）
    'core.sandbox', 'core.sandbox.service',
    # V3: Skill Engine V2
    'core.skill_engine', 'core.skill_engine.intent_cache',
    'core.skill_engine.intent_analyzer', 'core.skill_engine.skill_manager',
    'core.skill_engine.skill_learner', 'core.skill_engine.task_engine',
    'core.skill_engine.template_engine', 'core.skill_engine.review_engine',
    'core.skill_engine.prompt_builder', 'core.skill_engine.skill_tree',
    'core.skill_engine.models',
    # V3.2: Vision Plugin（视觉模型插件）
    'core.llm.vision_plugin',
    # V3.4: 抱怨关键词检测 + 澄清问题生成
    'agents.knowledge.complaint_keywords',
    'agents.knowledge.clarify_generator',
    # V3.5: Web Search 插件 + 时效性知识库
    'core.llm.web_search_plugin',
    'knowledge.timely_knowledge_service',
    'models.timely_knowledge',
    # V3.5.1: 云端模型设置 API（密钥管理/模型切换）
    'api.v1.settings', 'api.v1.settings.router',
    'knowledge', 'knowledge.service',
    'knowledge.mysql_service',
    'models', 'models.agent', 'models.workflow',
    'models.knowledge', 'models.db_models', 'models.timely_knowledge',
    'prompts', 'prompts.template_manager',
    'services', 'services.agent_service',
    'shared', 'shared.platform',
    'utils', 'utils.logger',
]

a = Analysis(
    ['run.py'],
    pathex=[backend_dir],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter', 'tkinter.ttk', 'tkinter.tix',
        'matplotlib', 'scipy', 'PIL.ImageQt',
        'test', 'tests', 'unittest',
        'pytest', '_pytest',
    ],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='agentmatrix-backend',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,  # 保留控制台（Rust sidecar 用 CREATE_NO_WINDOW 隐藏）
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)