# AgentMatrix 安装说明

> 多智能体动态协同与国产算力优化平台\
> 版本: v0.1.0 | 日期: 2026-05-17

***

## 目录

1. [环境准备](#一环境准备)
2. [快速安装（Windows）](#二快速安装windows)
3. [手动安装（Windows）](#三手动安装windows)
4. [手动安装（Linux/macOS）](#四手动安装linuxmacos)
5. [安装验证](#五安装验证)
6. [常见问题](#六常见问题)

***

## 一、环境准备

### 1.1 系统要求

| 组件      | 最低版本                                    | 检查命令               |
| ------- | --------------------------------------- | ------------------ |
| 操作系统    | Windows 10+ / macOS 12+ / Ubuntu 22.04+ | -                  |
| Python  | 3.12.0+                                 | `python --version` |
| Node.js | 20.0.0+                                 | `node --version`   |
| npm     | 9.0.0+                                  | `npm --version`    |
| Git     | 2.40.0+                                 | `git --version`    |

### 1.2 安装 Python 3.12+

**Windows:**

1. 访问 <https://www.python.org/downloads/>
2. 下载 Python 3.12 安装包
3. 安装时勾选 "Add Python to PATH"
4. 验证: `python --version`

**Linux:**

```bash
sudo add-apt-repository ppa:deadsnakes/ppa
sudo apt update
sudo apt install python3.12 python3.12-venv
```

**macOS:**

```bash
brew install python@3.12
```

### 1.3 安装 Node.js 20+

**Windows/macOS:**

1. 访问 <https://nodejs.org/>
2. 下载 Node.js 20 LTS 版本
3. 安装完成后验证: `node --version` 和 `npm --version`

**Linux:**

```bash
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt install nodejs
```

### 1.4 安装 Ollama

**Windows:**

1. 访问 <https://ollama.com/download/windows>
2. 下载并安装
3. 验证: `ollama --version`

**Linux:**

```bash
curl -fsSL https://ollama.com/install.sh | sh
```

**macOS:**

```bash
brew install ollama
```

***

## 二、快速安装（Windows）

### 2.1 获取项目代码

```powershell
# 克隆仓库
git clone <repository-url>
cd AgentMatrix
```

### 2.2 一键安装

```powershell
# 以管理员身份打开 PowerShell
# cd 到项目目录后运行:

# 1. 启动 Ollama 服务（如果尚未运行）
Start-Process ollama -ArgumentList "serve" -WindowStyle Normal

# 2. 下载所需的本地模型（各约需 5-15 分钟）
ollama pull qwen2.5:1.5b
ollama pull phi4-mini:3.8b

# 3. 安装后端依赖
cd backend
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install fastapi uvicorn pydantic python-dotenv aiohttp sqlalchemy loguru websockets psutil
cd ..

# 4. 安装前端依赖
cd frontend
npm install
cd ..
```

### 2.3 配置环境变量

```powershell
# 设置 Ollama 端口（如果默认 11434 被占用）
$env:OLLAMA_HOST = "0.0.0.0:11435"

# 可选：设置 DeepSeek API Key
# 创建 backend/.env 文件并添加:
# DEEPSEEK_API_KEY=sk-your-api-key-here
```

### 2.4 启动服务

```powershell
# 方式一：使用一键脚本
.\start.ps1

# 方式二：手动启动
# 终端 1 - 后端
cd backend
.\venv\Scripts\Activate.ps1
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# 终端 2 - 前端
cd frontend
npm run dev
```

### 2.5 访问

- 前端: <http://localhost:3000>
- 后端 API 文档: <http://localhost:8000/docs>
- 健康检查: <http://localhost:8000/health>

***

## 三、手动安装（Windows）

### 3.1 克隆项目

```powershell
git clone <repository-url>
cd AgentMatrix
```

### 3.2 后端安装

```powershell
# 进入后端目录
cd backend

# 创建虚拟环境
python -m venv venv

# 激活虚拟环境
.\venv\Scripts\Activate.ps1

# 注意: 如果遇到执行策略限制，先运行:
# Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser

# 安装核心依赖
pip install fastapi==0.110.0 uvicorn==0.29.0 pydantic==2.6.0
pip install python-dotenv==1.0.0 aiohttp==3.9.0 sqlalchemy==2.0.0
pip install loguru==0.7.0 websockets==12.0 psutil==5.9.0
pip install python-pptx==0.6.23 python-docx==1.1.0 pymdown-extensions==10.0.0

# 可选: 安装开发依赖
pip install pytest pytest-asyncio httpx ruff black pre-commit

# 返回项目根目录
cd ..
```

### 3.3 前端安装

```powershell
# 进入前端目录
cd frontend

# 安装依赖
npm install

# 返回项目根目录
cd ..
```

### 3.4 配置

**创建后端配置文件** **`backend/.env`:**

```powershell
# 在 backend 目录下创建 .env 文件
New-Item -Path backend\.env -ItemType File -Force

# 内容如下:
@"
SERVER_HOST=0.0.0.0
SERVER_PORT=8000
SERVER_RELOAD=true
LOG_LEVEL=INFO
DATABASE_URL=sqlite:///./agentmatrix.db
OLLAMA_HOST=http://localhost:11435
OLLAMA_MODEL=qwen2.5:1.5b
OLLAMA_REVIEW_MODEL=phi4-mini:3.8b
DEEPSEEK_API_KEY=
DEEPSEEK_API_BASE=https://api.deepseek.com/v1
DEEPSEEK_MODEL=deepseek-r1-distill
COMPLEXITY_THRESHOLD=0.65
ALLOWED_ORIGINS=http://localhost:3000,http://localhost:8000
"@ | Out-File -FilePath backend\.env -Encoding UTF8
```

**创建前端配置文件** **`frontend/.env.local`:**

```powershell
@"
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_WS_URL=ws://localhost:8000
"@ | Out-File -FilePath frontend\.env.local -Encoding UTF8
```

### 3.5 Ollama 模型安装

```powershell
# 确保 Ollama 正在运行
ollama serve

# 新建终端，下载模型
ollama pull qwen2.5:1.5b   # ~986MB, 约5-10分钟
ollama pull phi4-mini:3.8b  # ~2.5GB, 约10-20分钟

# 验证
ollama list
```

### 3.6 启动

启动三个终端窗口：

**终端 1 - Ollama:**

```powershell
# 如果尚未运行
ollama serve
```

**终端 2 - 后端:**

```powershell
cd backend
.\venv\Scripts\Activate.ps1
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

**终端 3 - 前端:**

```powershell
cd frontend
npm run dev
```

***

## 四、手动安装（Linux/macOS）

### 4.1 克隆项目

```bash
git clone <repository-url>
cd AgentMatrix
```

### 4.2 后端安装

```bash
cd backend

# 创建虚拟环境
python3 -m venv venv
source venv/bin/activate

# 安装依赖
pip install fastapi uvicorn pydantic python-dotenv aiohttp sqlalchemy loguru websockets psutil
pip install python-pptx python-docx pymdown-extensions

cd ..
```

### 4.3 前端安装

```bash
cd frontend
npm install
cd ..
```

### 4.4 配置

```bash
# 后端配置
cat > backend/.env << 'EOF'
SERVER_HOST=0.0.0.0
SERVER_PORT=8000
OLLAMA_HOST=http://localhost:11434
OLLAMA_MODEL=qwen2.5:1.5b
OLLAMA_REVIEW_MODEL=phi4-mini:3.8b
DEEPSEEK_API_KEY=
DEEPSEEK_API_BASE=https://api.deepseek.com/v1
DEEPSEEK_MODEL=deepseek-r1-distill
COMPLEXITY_THRESHOLD=0.65
ALLOWED_ORIGINS=http://localhost:3000,http://localhost:8000
EOF

# 前端配置
cat > frontend/.env.local << 'EOF'
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_WS_URL=ws://localhost:8000
EOF
```

### 4.5 Ollama 模型

```bash
# Linux: 注意 Ollama 默认端口是 11434
ollama pull qwen2.5:1.5b
ollama pull phi4-mini:3.8b
```

### 4.6 启动

```bash
# 终端 1 - Ollama
ollama serve

# 终端 2 - 后端
cd backend
source venv/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# 终端 3 - 前端
cd frontend
npm run dev
```

***

## 五、安装验证

### 5.1 验证 Ollama

```bash
# 检查服务状态
ollama list

# 预期输出:
# NAME              ID              SIZE      MODIFIED
# phi4-mini:3.8b    78fad5d182a7    2.5 GB    ...
# qwen2.5:1.5b      65ec06548149    986 MB    ...
```

### 5.2 验证后端

```bash
# 健康检查 API
curl http://localhost:8000/health

# 预期输出包含:
# {"status":"healthy","agents":{"knowledge":{"status":"ready"},...}}
```

浏览器访问 <http://localhost:8000/docs> 查看 API 文档。

### 5.3 验证前端

浏览器访问 <http://localhost:3000，预期看到> AgentMatrix 主界面：

- ✅ 顶部任务输入框
- ✅ 左侧 Agent 舰队列表
- ✅ 中间流水线可视化
- ✅ 右侧输出面板

### 5.4 端到端验证

在前端输入框中输入一个简单测试任务：

```
"你好，请介绍一下你自己"
```

预期结果：

1. 6 个 Agent 依次执行（流水线动画）
2. 因为复杂度低，全部由本地模型完成
3. 左侧 "成本节省" 指标增加
4. 右侧显示最终结果

***

## 六、常见问题

### Q1: PowerShell 无法激活虚拟环境？

```
错误: "无法加载文件 .\venv\Scripts\Activate.ps1，因为在此系统上禁止运行脚本。"

解决:
以管理员身份运行 PowerShell，执行:
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

### Q2: pip install 报错？

```
错误: "Could not find a version that satisfies the requirement..."

解决:
1. 确保 Python >= 3.12: python --version
2. 更新 pip: python -m pip install --upgrade pip
3. 如果在公司网络，配置代理: pip install --proxy=http://proxy:port ...
```

### Q3: npm install 报错？

```
错误: "npm ERR! code ERESOLVE"

解决:
1. 删除 node_modules 和 package-lock.json
2. 重新安装: npm install
3. 或使用: npm install --legacy-peer-deps
```

### Q4: Ollama 连接失败？

```
错误: "Failed to call Ollama: Connection refused"

解决:
1. 确认 Ollama 正在运行: ollama list
2. 检查端口号:
   - Windows (本项目配置): 11435
   - Linux/macOS 默认: 11434
3. 测试连接: curl http://localhost:11435/api/tags
4. 如果端口不对，修改 backend/.env 中的 OLLAMA_HOST
```

### Q5: 前端页面空白？

```
可能原因:
1. 后端服务未启动
2. 端口号不匹配
3. CORS 配置问题

解决:
1. 确认后端正在运行: curl http://localhost:8000/health
2. 检查 frontend/.env.local 配置
3. 打开浏览器开发者工具 (F12) 查看错误信息
```

### Q6: 模型下载速度慢？

```
解决:
1. 使用代理加速下载
2. 仅下载需要的模型（可以只安装一个）
3. 最低要求: 至少安装 qwen2.5:1.5b
```

### Q7: 如何获取 DeepSeek API Key？

```
1. 访问 https://platform.deepseek.com/
2. 注册账号并登录
3. 进入 "API Keys" 页面
4. 创建新的 API Key
5. 将 Key 添加到 backend/.env 中的 DEEPSEEK_API_KEY
```

### Q8: 不想使用云端 API，可以吗？

```
可以。不设置 DEEPSEEK_API_KEY 即可。
所有任务将由本地 Ollama 模型处理。
```

***

## 七、开发工具配置（可选）

### 7.1 代码质量工具

```bash
# 后端代码检查
cd backend
pip install ruff black pre-commit
ruff check .
black .

# 前端代码检查
cd frontend
npm run lint
npm run format
```

### 7.2 VS Code 配置

项目 `.vscode/` 目录已包含推荐配置：

- `launch.json` - 调试配置
- `settings.json` - 编辑器设置
- `tasks.json` - 任务配置

### 7.3 运行测试

```bash
cd backend
pytest tests/ -v
```

***

## 八、目录结构说明

```
AgentMatrix/
├── backend/                  # 后端服务 (FastAPI + Python)
│   ├── agents/               # 6 个 Agent 实现
│   │   ├── base/             # Agent 基类和注册中心
│   │   ├── knowledge/        # Knowledge Agent (知识检索)
│   │   ├── summary/          # Summary Agent (需求摘要)
│   │   ├── writer/           # Writer Agent (内容生成)
│   │   ├── review/           # Review Agent (质量评审)
│   │   ├── judge/            # Judge Agent (复杂度判断)
│   │   └── result/           # Result Agent (成果导出)
│   ├── api/                  # API 路由
│   │   ├── v1/               # v1 版本 API
│   │   └── websocket/        # WebSocket 管理
│   ├── core/                 # 核心业务逻辑
│   │   ├── workflow/         # 工作流编排
│   │   ├── llm/              # LLM 客户端
│   │   └── dynamic_router/   # 动态算力路由
│   ├── models/               # Pydantic 数据模型
│   ├── prompts/              # Prompt 模板
│   ├── knowledge/            # 知识库服务
│   ├── config/               # 配置管理
│   ├── services/             # 聚合服务层
│   ├── app/                  # 应用入口
│   │   ├── main.py           # FastAPI 入口
│   │   ├── config.py         # 全局配置
│   │   └── database.py       # 数据库初始化
│   └── tests/                # 测试
│
├── frontend/                 # 前端服务 (Next.js + React)
│   ├── src/
│   │   ├── app/              # Next.js App Router
│   │   ├── components/       # React 组件
│   │   │   └── layout/       # 主界面布局
│   │   ├── stores/           # Zustand 状态管理
│   │   ├── services/api/     # API 调用封装
│   │   └── types/            # TypeScript 类型定义
│   ├── package.json          # 依赖清单
│   └── next.config.js        # Next.js 配置
│
├── configs/                  # 配置文件
├── docs/                     # 文档
│   ├── TECH_REPORT.md        # 技术报告
│   ├── DEPLOYMENT.md         # 部署文档
│   └── INSTALL.md            # 安装说明 (本文档)
│
├── start.ps1                 # Windows 一键启动脚本
├── stop.ps1                  # Windows 停止脚本
└── README.md                 # 项目说明
```

