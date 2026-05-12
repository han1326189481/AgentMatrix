# AgentMatrix

**多智能体动态协同与国产算力优化平台**

基于多Agent协同 + 动态算力路由的AI系统，旨在降低API调用成本、提高响应速度、优化国产算力利用率。

## 核心特性

- **多Agent协同架构**: Knowledge、Summary、Writer、Review、Judge、Result六大Agent协同工作
- **动态算力路由**: 智能判断任务复杂度，简单任务本地完成，复杂任务云端增强
- **本地-云端混合推理**: 结合国产轻量模型与云端大型模型
- **世界书/知识包系统**: 每个Agent拥有专属Prompt和知识包
- **AI工作流可视化**: 实时展示Agent工作状态、推理流程和KPI数据

## 技术栈

| 分类 | 技术 |
|------|------|
| 前端 | React, Next.js, TailwindCSS |
| 后端 | FastAPI |
| 本地模型 | Ollama (Qwen2.5-3B, DeepSeek-R1-Distill) |
| 云端API | Gemini API |
| 数据存储 | SQLite, JSON, FAISS (后期) |

## 项目结构

```
AgentMatrix/
├── frontend/          # 前端项目 (Next.js)
├── backend/           # 后端项目 (FastAPI)
├── shared/            # 共享模块
├── configs/           # 配置文件
├── docs/              # 文档
├── scripts/           # 脚本
└── .github/           # GitHub配置
```

## 快速开始

### 环境要求

- Python 3.12+
- Node.js 20+
- Ollama (本地模型支持)

### 安装依赖

```bash
# 后端依赖
cd backend
pip install -e .

# 前端依赖
cd frontend
npm install
```

### 启动服务

```bash
# 启动后端
cd backend
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# 启动前端
cd frontend
npm run dev
```

## 核心工作流

```
用户输入
    ↓
Knowledge Agent (知识检索)
    ↓
Summary Agent (需求摘要)
    ↓
Writer Agent (内容生成)
    ↓
Review Agent (质量评审)
    ↓
Judge Agent (复杂度判断)
    ↓
本地输出 / 云端API调用
    ↓
Result Agent (成果导出)
```

## 开发指南

详细文档请参考 [docs/development/getting-started.md](docs/development/getting-started.md)

## 贡献

欢迎贡献代码！请阅读 [CONTRIBUTING.md](CONTRIBUTING.md) 了解贡献流程。

## 许可证

MIT License - 详见 [LICENSE](LICENSE)