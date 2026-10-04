#!/bin/bash

# =================================================================
#  AgentMatrix 一键启动脚本 (麒麟/Linux版)
#  支持统信UOS、银河麒麟、中标麒麟、Ubuntu、Debian等Linux发行版
# =================================================================

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 打印彩色信息
print_info() {
    echo -e "${BLUE}[信息]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[成功]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[警告]${NC} $1"
}

print_error() {
    echo -e "${RED}[错误]${NC} $1"
}

# 获取脚本所在目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$SCRIPT_DIR/backend"
FRONTEND_DIR="$SCRIPT_DIR/frontend"

echo "=============================================="
echo "   AgentMatrix - 多智能体动态协同系统"
echo "   麒麟/Linux 一键启动脚本"
echo "=============================================="
echo ""

# -----------------------------------------------------------------------------
# 1. 检查Root权限
# -----------------------------------------------------------------------------
if [ "$EUID" -eq 0 ]; then
    print_warning "检测到Root权限，某些操作可能需要手动执行"
fi

# -----------------------------------------------------------------------------
# 2. 检查Python环境
# -----------------------------------------------------------------------------
print_info "检查Python环境..."
if ! command -v python3 &> /dev/null; then
    print_error "未检测到Python3，请先安装: sudo apt-get install python3 python3-pip"
    exit 1
fi

PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
print_success "Python版本: $PYTHON_VERSION"

# -----------------------------------------------------------------------------
# 3. 检查Node.js环境
# -----------------------------------------------------------------------------
print_info "检查Node.js环境..."
if ! command -v node &> /dev/null; then
    print_error "未检测到Node.js，请先安装"
    print_info "Ubuntu/Debian: sudo apt-get install nodejs npm"
    print_info "或从 https://nodejs.org 下载安装"
    exit 1
fi

NODE_VERSION=$(node --version 2>&1)
NPM_VERSION=$(npm --version 2>&1)
print_success "Node.js版本: $NODE_VERSION, npm版本: $NPM_VERSION"

# -----------------------------------------------------------------------------
# 4. 检查并安装后端依赖
# -----------------------------------------------------------------------------
print_info "检查后端依赖..."
cd "$BACKEND_DIR" || exit 1

# 创建虚拟环境（可选）
if [ ! -d "venv" ]; then
    print_info "创建Python虚拟环境..."
    python3 -m venv venv
    if [ $? -eq 0 ]; then
        print_success "虚拟环境创建成功"
    else
        print_warning "虚拟环境创建失败，将使用系统Python"
    fi
fi

# 安装后端依赖
print_info "安装后端Python依赖..."
if [ -d "venv" ]; then
    source venv/bin/activate
    pip install --upgrade pip -q
    pip install pydantic pydantic-settings fastapi uvicorn httpx python-dotenv python-socketio sqlalchemy -q
else
    pip3 install --user pydantic pydantic-settings fastapi uvicorn httpx python-dotenv python-socketio sqlalchemy -q
fi

if [ $? -eq 0 ]; then
    print_success "后端依赖安装完成"
else
    print_error "后端依赖安装失败"
    exit 1
fi

# -----------------------------------------------------------------------------
# 5. 检查并安装前端依赖
# -----------------------------------------------------------------------------
print_info "检查前端依赖..."
cd "$FRONTEND_DIR" || exit 1

if [ ! -d "node_modules" ]; then
    print_info "安装前端依赖（首次可能需要几分钟）..."
    npm install
    if [ $? -eq 0 ]; then
        print_success "前端依赖安装完成"
    else
        print_error "前端依赖安装失败"
        exit 1
    fi
else
    print_success "前端依赖已存在"
fi

# -----------------------------------------------------------------------------
# 6. 检查并启动Ollama
# -----------------------------------------------------------------------------
print_info "检查Ollama服务..."
if ! command -v ollama &> /dev/null; then
    print_warning "未检测到Ollama命令"
    print_info "请手动安装Ollama: https://ollama.com/download"
    print_info "或运行: curl -fsSL https://ollama.com/install.sh | sh"
else
    # 检查Ollama是否运行
    if ! pgrep -x "ollama" > /dev/null; then
        print_info "启动Ollama服务..."
        nohup ollama serve > /tmp/ollama.log 2>&1 &
        sleep 3
        if pgrep -x "ollama" > /dev/null; then
            print_success "Ollama服务已启动 (PID: $(pgrep -x ollama))"
        else
            print_warning "Ollama启动可能失败，请检查 /tmp/ollama.log"
        fi
    else
        print_success "Ollama服务已在运行 (PID: $(pgrep -x ollama))"
    fi

    # 显示可用模型
    print_info "可用本地模型:"
    ollama list 2>/dev/null | grep -E "NAME|qwen|phi|llama" || print_warning "未检测到模型"
fi

# -----------------------------------------------------------------------------
# 7. 启动后端服务
# -----------------------------------------------------------------------------
print_info "启动后端服务..."
cd "$BACKEND_DIR" || exit 1

# 激活虚拟环境
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# 检查端口是否被占用
if lsof -Pi :8000 -sTCP:LISTEN -t >/dev/null 2>&1; then
    print_warning "端口8000已被占用，后端可能已在运行"
    BACKEND_PID=$(lsof -t -i:8000)
    print_info "后端进程PID: $BACKEND_PID"
else
    # 后台启动后端
    nohup python3 -m uvicorn app.main:socket_app --host 0.0.0.0 --port 8000 --reload > /tmp/agentmatrix_backend.log 2>&1 &
    BACKEND_PID=$!
    sleep 3

    if ps -p $BACKEND_PID > /dev/null 2>&1; then
        print_success "后端服务已启动 (PID: $BACKEND_PID)"
        print_success "后端地址: http://localhost:8000"
        print_success "API文档: http://localhost:8000/docs"
    else
        print_error "后端启动失败，请检查 /tmp/agentmatrix_backend.log"
        exit 1
    fi
fi

# -----------------------------------------------------------------------------
# 8. 启动前端服务
# -----------------------------------------------------------------------------
print_info "启动前端服务..."
cd "$FRONTEND_DIR" || exit 1

# 检查端口是否被占用
if lsof -Pi :3000 -sTCP:LISTEN -t >/dev/null 2>&1; then
    print_warning "端口3000已被占用，前端可能已在运行"
    FRONTEND_PID=$(lsof -t -i:3000)
    print_info "前端进程PID: $FRONTEND_PID"
else
    # 后台启动前端
    nohup npm run dev > /tmp/agentmatrix_frontend.log 2>&1 &
    FRONTEND_PID=$!
    sleep 5

    if ps -p $FRONTEND_PID > /dev/null 2>&1; then
        print_success "前端服务已启动 (PID: $FRONTEND_PID)"
    else
        print_error "前端启动失败，请检查 /tmp/agentmatrix_frontend.log"
        exit 1
    fi
fi

# -----------------------------------------------------------------------------
# 9. 完成
# -----------------------------------------------------------------------------
echo ""
echo "=============================================="
print_success "系统启动完成！"
echo "=============================================="
echo ""
echo "访问地址:"
echo "  - 前端界面: ${GREEN}http://localhost:3000${NC}"
echo "  - 后端API:  ${GREEN}http://localhost:8000${NC}"
echo "  - API文档:  ${GREEN}http://localhost:8000/docs${NC}"
echo ""
echo "日志文件:"
echo "  - 后端日志: /tmp/agentmatrix_backend.log"
echo "  - 前端日志: /tmp/agentmatrix_frontend.log"
echo "  - Ollama日志: /tmp/ollama.log"
echo ""
echo "进程信息:"
echo "  - 后端 PID: $BACKEND_PID"
echo "  - 前端 PID: $FRONTEND_PID"
if command -v ollama &> /dev/null; then
    echo "  - Ollama PID: $(pgrep -x ollama 2>/dev/null || echo 'N/A')"
fi
echo ""
echo "停止服务:"
echo "  - 停止所有: pkill -f 'uvicorn\|next'"
echo "  - 停止后端: kill $BACKEND_PID"
echo "  - 停止前端: kill $FRONTEND_PID"
echo ""
echo "按 Ctrl+C 退出此脚本（服务将继续在后台运行）..."
echo "=============================================="

# 保持脚本运行，显示实时日志（可选）
if [ "$1" = "--follow" ] || [ "$1" = "-f" ]; then
    print_info "跟踪日志输出（Ctrl+C 停止跟踪，但服务继续运行）..."
    tail -f /tmp/agentmatrix_backend.log /tmp/agentmatrix_frontend.log 2>/dev/null || {
        print_warning "日志文件不存在或无法访问"
    }
fi

# 等待用户中断
wait
