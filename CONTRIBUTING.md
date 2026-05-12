# 贡献指南

欢迎为 AgentMatrix 项目贡献代码！

## 行为准则

### 我们的承诺

为了营造一个开放和友好的环境，我们承诺让每位贡献者都能享受无骚扰的体验。

### 我们的标准

- 使用友好和包容的语言
- 尊重不同的观点和经验
- 优雅地接受建设性批评
- 关注对社区最有利的事情
- 对其他社区成员表现出同理心

## 贡献流程

### 1. Fork 仓库

在 GitHub 上点击 "Fork" 按钮，将仓库克隆到你的账号下。

### 2. 克隆仓库

```bash
git clone https://github.com/your-username/AgentMatrix.git
cd AgentMatrix
```

### 3. 创建功能分支

```bash
git checkout -b feature/your-feature-name
```

分支命名规范：
- `feature/xxx`: 新功能开发
- `bugfix/xxx`: Bug修复
- `hotfix/xxx`: 紧急修复
- `docs/xxx`: 文档更新
- `refactor/xxx`: 代码重构

### 4. 开发

遵循代码规范：
- 前端：ESLint + Prettier
- 后端：Ruff + Black

### 5. 提交代码

```bash
git add .
git commit -m "feat: 描述你的更改"
```

Commit 信息规范（Conventional Commits）：
- `feat`: 新功能
- `fix`: Bug修复
- `docs`: 文档更新
- `style`: 代码格式（不影响代码运行的变动）
- `refactor`: 重构（既不新增功能，也不修复bug）
- `perf`: 性能优化
- `test`: 测试相关
- `chore`: 构建/工具/依赖更新

### 6. 推送到远程

```bash
git push origin feature/your-feature-name
```

### 7. 创建 Pull Request

在 GitHub 上创建 PR，描述你的更改：
- 更改的目的
- 解决的问题（关联Issue）
- 测试方法

### 8. Code Review

等待项目维护者审查代码。可能需要进行修改。

### 9. 合并

审查通过后，代码将被合并到 `develop` 分支。

## 代码规范

### Python 代码规范

- 使用 Ruff 进行静态检查
- 使用 Black 进行代码格式化
- 遵循 PEP8 标准
- 类型提示必须完整

### TypeScript 代码规范

- 使用 ESLint 进行静态检查
- 使用 Prettier 进行代码格式化
- React 组件使用函数式组件 + Hooks
- 类型定义完整

### 提交信息规范

```
<type>(<scope>): <description>

[optional body]

[optional footer(s)]
```

示例：
```
feat(agent): 添加知识检索功能

- 实现 Knowledge Agent
- 添加向量检索支持
- 更新配置文件

Closes #123
```

## Issue 模板

### Bug Report

```
**问题描述**
清晰描述问题

**复现步骤**
1. 步骤1
2. 步骤2
3. 预期行为

**实际行为**
描述实际发生的情况

**环境信息**
- 操作系统：
- Python/Node.js 版本：
- 项目版本：
```

### Feature Request

```
**功能描述**
清晰描述需要的功能

**需求背景**
为什么需要这个功能

**实现建议**
（可选）你对实现的想法
```

## 测试指南

### 运行测试

```bash
# 后端测试
cd backend
pytest

# 前端测试
cd frontend
npm test
```

### 测试要求

- 新增功能必须有对应的单元测试
- Bug修复必须有回归测试
- 测试覆盖率应保持在 80% 以上

## 沟通渠道

- GitHub Issues: 报告问题和功能请求
- GitHub Discussions: 讨论设计和架构
- Slack/Discord: 实时交流（如有）

## 许可证

贡献的代码将遵循项目的 MIT 许可证。