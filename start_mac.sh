#!/bin/bash
# FinRobot DeepSeek - macOS 一键启动脚本

PROJECT_DIR="/Users/xuhang/Downloads/stockets-main"
cd "$PROJECT_DIR"

# 设置 Node.js 路径
export PATH="/Users/xuhang/.local/node-v20.18.0-darwin-arm64/bin:$PATH"

# 激活 Python 虚拟环境
source venv/bin/activate

# 验证配置文件
if [ ! -f "config_api_keys" ] || [ ! -f "OAI_CONFIG_LIST" ]; then
    echo "❌ 错误：缺少 config_api_keys 或 OAI_CONFIG_LIST 文件"
    echo "请在项目根目录创建这两个配置文件并填入 API 密钥"
    exit 1
fi

# 确保 data 目录存在
mkdir -p data

# 启动后端 API 服务（后台）
echo "🚀 启动后端 API 服务（端口 8888）..."
python server.py &
BACKEND_PID=$!

# 等待后端启动
sleep 3

# 检查后端是否启动成功
if ! kill -0 $BACKEND_PID 2>/dev/null; then
    echo "❌ 后端启动失败，请检查错误信息"
    exit 1
fi

echo "✅ 后端已启动 (PID: $BACKEND_PID)"

# 启动前端开发服务器
echo "🚀 启动前端开发服务器（端口 5173）..."
echo ""
echo "========================================="
echo "  访问地址: http://localhost:5173"
echo "  后端API:  http://localhost:8888/api"
echo "========================================="
echo ""

# 设置退出时清理后台进程
trap "echo '正在关闭服务...'; kill $BACKEND_PID 2>/dev/null; exit" INT TERM EXIT

npm run dev
