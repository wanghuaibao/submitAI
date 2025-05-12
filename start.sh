#!/bin/bash
# 自动化产品提交工具启动脚本

# 检查Python环境
echo "检查Python环境..."
if command -v python3 &>/dev/null; then
    PYTHON_CMD=python3
elif command -v python &>/dev/null; then
    PYTHON_CMD=python
else
    echo "错误: 找不到Python。请安装Python 3.8或更高版本。"
    exit 1
fi

# 检查虚拟环境
if [ ! -d "venv" ]; then
    echo "创建虚拟环境..."
    $PYTHON_CMD -m venv venv
    if [ $? -ne 0 ]; then
        echo "错误: 创建虚拟环境失败。请确保已安装venv模块。"
        exit 1
    fi
fi

# 激活虚拟环境
echo "激活虚拟环境..."
if [ -f "venv/bin/activate" ]; then
    source venv/bin/activate
elif [ -f "venv/Scripts/activate" ]; then
    source venv/Scripts/activate
else
    echo "错误: 找不到虚拟环境激活脚本。"
    exit 1
fi

# 安装依赖
echo "安装依赖..."
pip install -r requirements.txt
if [ $? -ne 0 ]; then
    echo "错误: 安装依赖失败。"
    exit 1
fi

# 检查Playwright是否已安装
echo "检查Playwright浏览器..."
if ! $PYTHON_CMD -c "from playwright.sync_api import sync_playwright; print('Playwright已安装')" 2>/dev/null; then
    echo "安装Playwright浏览器..."
    playwright install chromium
    if [ $? -ne 0 ]; then
        echo "错误: 安装Playwright浏览器失败。"
        exit 1
    fi
fi

# 创建必要的目录
echo "创建目录结构..."
mkdir -p app/web/templates app/web/static uploads/logos uploads/screenshots logs submissions

# 检查环境变量文件
if [ ! -f ".env" ]; then
    echo "创建示例.env文件..."
    cat > .env << EOF
# Grok API密钥 - 用于AI辅助提交
GROK_API_KEY=your-grok-api-key-here

# 设置为true开启调试模式
DEBUG=false

# 浏览器配置
HEADLESS=true  # 设置为false可以看到浏览器界面
EOF
    echo "请编辑.env文件，设置正确的API密钥。"
fi

# 启动应用
echo "启动应用..."
$PYTHON_CMD app.py 