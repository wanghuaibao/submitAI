# 自动化产品提交工具 - Web版

这个项目基于[submit-a-tool](https://github.com/oldcai/submit-a-tool)开源项目，是一个Web界面的自动化产品提交工具。它允许用户通过网页界面提交产品信息到多个目录网站，无需手动操作每一步。

## 功能特点

- 用户友好的Web界面
- 支持提交到多个目录网站
- AI驱动的表单填写和验证处理
- 实时查看提交进度和结果
- 支持截图上传
- 用户认证和任务管理

## 技术栈

- **后端**: FastAPI, Python 3.11+
- **前端**: HTML, JavaScript, Tailwind CSS
- **自动化**: browser-use库 + Playwright
- **AI**: OpenAI API, Claude API

## 安装要求

- Python 3.11或更高版本
- Playwright (用于浏览器自动化)
- OpenAI API密钥 (用于LLM集成)
- Claude API密钥 (用于LLM集成)

## 安装步骤

1. **克隆仓库:**

```bash
git clone https://github.com/your-username/submit-a-tool-web
cd submit-a-tool-web
```

2. **安装依赖:**

```bash
pip install -r requirements.txt
playwright install chromium
```

3. **设置环境变量:**

创建一个`.env`文件，包含以下内容:

```
OPENAI_API_KEY=your_openai_api_key
CLAUDE_API_KEY=your_claude_api_key
SECRET_KEY=your_secret_key_for_jwt
```

## 运行应用

启动应用服务器:

```bash
python run.py
```

然后在浏览器中访问 http://localhost:8000

## 使用说明

1. **注册/登录**:
   - 使用邮箱和密码创建一个账户
   - 登录你的账户

2. **创建提交**:
   - 点击"创建提交"按钮
   - 填写产品信息
   - 提供目标目录网站链接
   - 可选: 上传产品截图
   - 点击"开始提交"按钮

3. **查看结果**:
   - 在控制面板中查看所有提交任务
   - 点击任务可查看详细信息和提交结果

## 架构说明

这个Web应用构建在原始`submit-a-tool`项目的基础上，添加了以下组件:

- **FastAPI后端**: 处理用户请求和任务管理
- **用户认证**: 使用JWT令牌进行用户认证
- **异步任务处理**: 异步处理提交任务
- **Web界面**: 用户友好的现代界面

## 注意事项

- 自动提交需要AI API密钥，可以使用系统默认的，但会有使用限制
- 对于需要邮件验证的网站，需要提供邮箱密码才能自动处理验证
- 某些复杂的验证码可能需要人工干预

## 贡献

欢迎贡献！请随时提交问题报告或拉取请求。

## 许可证

与原始项目相同。 