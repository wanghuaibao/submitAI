@echo off
REM 自动化产品提交工具启动脚本 - Windows版

echo 检查Python环境...
where python >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo 错误: 找不到Python。请安装Python 3.8或更高版本。
    exit /b 1
)

REM 检查虚拟环境
if not exist "venv" (
    echo 创建虚拟环境...
    python -m venv venv
    if %ERRORLEVEL% neq 0 (
        echo 错误: 创建虚拟环境失败。请确保已安装venv模块。
        exit /b 1
    )
)

REM 激活虚拟环境
echo 激活虚拟环境...
call venv\Scripts\activate.bat
if %ERRORLEVEL% neq 0 (
    echo 错误: 激活虚拟环境失败。
    exit /b 1
)

REM 安装依赖
echo 安装依赖...
pip install -r requirements.txt
if %ERRORLEVEL% neq 0 (
    echo 错误: 安装依赖失败。
    exit /b 1
)

REM 检查Playwright是否已安装
echo 检查Playwright浏览器...
python -c "from playwright.sync_api import sync_playwright; print('Playwright已安装')" 2>nul
if %ERRORLEVEL% neq 0 (
    echo 安装Playwright浏览器...
    playwright install chromium
    if %ERRORLEVEL% neq 0 (
        echo 错误: 安装Playwright浏览器失败。
        exit /b 1
    )
)

REM 创建必要的目录
echo 创建目录结构...
mkdir app\web\templates app\web\static uploads\logos uploads\screenshots logs submissions 2>nul

REM 检查环境变量文件
if not exist ".env" (
    echo 创建示例.env文件...
    (
        echo # Grok API密钥 - 用于AI辅助提交
        echo GROK_API_KEY=your-grok-api-key-here
        echo.
        echo # 设置为true开启调试模式
        echo DEBUG=false
        echo.
        echo # 浏览器配置
        echo HEADLESS=true  # 设置为false可以看到浏览器界面
    ) > .env
    echo 请编辑.env文件，设置正确的API密钥。
)

REM 启动应用
echo 启动应用...
python app.py 