from fastapi import FastAPI, Request, Form, File, UploadFile, BackgroundTasks
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pathlib import Path
import uvicorn
import os
import uuid
import shutil
from datetime import datetime, timedelta
import json
from typing import List, Optional
from dotenv import load_dotenv
import re

# 加载环境变量
load_dotenv()

# 导入提交处理器
from submitAI import SubmissionProcessor

# 确保目录存在
os.makedirs("app/web/static", exist_ok=True)
os.makedirs("app/web/templates", exist_ok=True)
os.makedirs("outputs", exist_ok=True)
os.makedirs("submissions", exist_ok=True)
os.makedirs("uploads", exist_ok=True)
os.makedirs("uploads/logos", exist_ok=True)
os.makedirs("uploads/screenshots", exist_ok=True)

# 获取 Grok API 密钥
GROK_API_KEY = os.getenv("GROK_API_KEY")

# 创建应用
app = FastAPI(title="自动化产品提交工具 - 简化版")

# 添加关闭事件处理器
@app.on_event("shutdown")
async def shutdown_event():
    """应用关闭时清理资源"""
    print("正在关闭应用，清理资源...")
    if submission_processor:
        await submission_processor.shutdown()
    print("资源清理完成")

# 设置静态文件目录
app.mount("/static", StaticFiles(directory="app/web/static"), name="static")
# 设置上传文件访问
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")
# 设置日志文件访问
app.mount("/logs", StaticFiles(directory="logs"), name="logs")

# 设置模板目录
templates = Jinja2Templates(directory="app/web/templates")

# 创建提交处理器实例（使用OpenAI API密钥）
submission_processor = SubmissionProcessor(openai_api_key=GROK_API_KEY)

# 模拟存储
submissions = {}

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """首页"""
    return templates.TemplateResponse("index.html", {"request": request, "user": None})

@app.get("/guide", response_class=HTMLResponse)
async def guide(request: Request):
    """使用指南页面"""
    return templates.TemplateResponse("guide.html", {"request": request, "user": None})

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    """控制面板"""
    return templates.TemplateResponse("dashboard.html", {"request": request, "user": None})

@app.get("/new-submission", response_class=HTMLResponse)
async def new_submission_form(request: Request):
    """提交表单页面"""
    return templates.TemplateResponse("new_submission.html", {"request": request, "user": None})

async def save_upload_file(upload_file: UploadFile, folder: str) -> str:
    """保存上传的文件并返回文件路径"""
    if not upload_file:
        return None
        
    # 创建一个唯一的文件名
    file_extension = upload_file.filename.split(".")[-1]
    unique_filename = f"{uuid.uuid4()}.{file_extension}"
    file_path = f"{folder}/{unique_filename}"
    
    # 保存文件
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(upload_file.file, buffer)
    
    return file_path

@app.post("/submit")
async def submit(
    request: Request,
    product_name: str = Form(...),
    product_url: str = Form(...),
    short_description: str = Form(...),
    product_description: str = Form(...),
    product_category: str = Form(...),
    pricing_model: str = Form(...),
    product_tags: str = Form(None),
    email: str = Form(...),
    target_directories: List[str] = Form(...),
    product_logo: UploadFile = File(...),
    product_screenshot: Optional[UploadFile] = File(None)
):
    """处理提交"""
    # 创建提交ID
    submission_id = str(uuid.uuid4())
    
    # 保存上传的文件
    logo_path = await save_upload_file(product_logo, "uploads/logos")
    screenshot_path = None
    if product_screenshot:
        screenshot_path = await save_upload_file(product_screenshot, "uploads/screenshots")
    
    # 处理产品标签
    tags = []
    if product_tags:
        tags = [tag.strip() for tag in product_tags.split(",") if tag.strip()]
    
    # 创建提交对象
    submission = {
        "id": submission_id,
        "product_name": product_name,
        "product_url": product_url,
        "short_description": short_description,
        "product_description": product_description,
        "product_category": product_category,
        "pricing_model": pricing_model,
        "product_tags": tags,
        "target_directories": target_directories,
        "email": email,
        "logo_path": logo_path,
        "screenshot_path": screenshot_path,
        "created_at": datetime.now().isoformat(),
        "status": "pending",  # 初始状态为待处理
        "results": []
    }
    
    # 为每个目标目录创建一个初始结果
    for directory in target_directories:
        result = {
            "directory_url": directory,
            "has_submission_form": True,
            "is_success": None,  # 尚未提交
            "short_reason_if_failed": "",
            "submitted_at": None  # 尚未提交
        }
        submission["results"].append(result)
    
    # 存储提交
    submissions[submission_id] = submission
    
    # 保存到文件
    with open(f"submissions/{submission_id}.json", "w", encoding="utf-8") as f:
        json.dump(submission, f, indent=2, ensure_ascii=False)
    
    # 重定向到提交列表
    return RedirectResponse(url="/submissions", status_code=303)

@app.get("/submissions", response_class=HTMLResponse)
async def list_submissions(request: Request):
    """提交列表页面"""
    # 从文件加载所有提交
    all_submissions = []
    for file in Path("submissions").glob("*.json"):
        with open(file, "r", encoding="utf-8") as f:
            all_submissions.append(json.load(f))
    
    # 按创建时间排序（最新的在前面）
    all_submissions.sort(key=lambda x: x["created_at"], reverse=True)
    
    return templates.TemplateResponse(
        "submissions.html", 
        {"request": request, "user": None, "submissions": all_submissions}
    )

@app.get("/submission/{submission_id}", response_class=HTMLResponse)
async def view_submission(request: Request, submission_id: str):
    """查看提交详情"""
    # 从文件加载提交
    try:
        with open(f"submissions/{submission_id}.json", "r", encoding="utf-8") as f:
            submission = json.load(f)
    except:
        submission = None
    
    if not submission:
        return RedirectResponse(url="/submissions")
    
    return templates.TemplateResponse(
        "submission_detail.html", 
        {"request": request, "user": None, "submission": submission}
    )

@app.get("/submission/{submission_id}/logs", response_class=HTMLResponse)
async def view_submission_logs(request: Request, submission_id: str):
    """查看提交处理日志"""
    # 加载提交信息
    try:
        with open(f"submissions/{submission_id}.json", "r", encoding="utf-8") as f:
            submission = json.load(f)
    except FileNotFoundError:
        print(f"错误: 提交文件 submissions/{submission_id}.json 未找到.")
        return RedirectResponse(url="/submissions")
    except Exception as e:
        print(f"读取提交文件 submissions/{submission_id}.json 时发生错误: {str(e)}")
        return RedirectResponse(url="/submissions")
    
    all_logs = []
    
    # 1. 控制台特定日志 (logs/submissions/{submission_id}_console.log)
    console_log_path = f"logs/submissions/{submission_id}_console.log"
    if os.path.exists(console_log_path):
        try:
            with open(console_log_path, "r", encoding="utf-8") as f:
                for line in f:
                    clean_line = line.strip()
                    if clean_line: # 确保行不为空
                        all_logs.append(f"[CONSOLE] {clean_line}")
        except Exception as e:
            print(f"读取控制台日志 {console_log_path} 失败: {str(e)}")
    
    # 2. 提交器日志 (logs/submitter_YYYY-MM-DD.log)
    log_dates = [
        datetime.now().strftime('%Y-%m-%d'), 
        (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
    ]
    for date_str in log_dates:
        submitter_log_path = f"logs/submitter_{date_str}.log"
        if os.path.exists(submitter_log_path):
            try:
                with open(submitter_log_path, "r", encoding="utf-8") as f:
                    for line in f:
                        if submission_id in line:
                            clean_line = re.sub(r'^\[[A-Z]+\]\s+\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d+:\s+', '', line.strip())
                            if clean_line:
                                all_logs.append(clean_line)
            except Exception as e:
                print(f"读取提交器日志 {submitter_log_path} 失败: {str(e)}")
    
    # 3. 通用服务器日志 (logs/server.log) 和浏览器日志 (logs/browser.log) - 仅当包含 submission_id
    general_log_files = ["logs/server.log", "logs/browser.log"]
    for log_file_path in general_log_files:
        if os.path.exists(log_file_path):
            try:
                with open(log_file_path, "r", encoding="utf-8") as f:
                    for line in f:
                        if submission_id in line:
                            clean_line = line.strip()
                            if clean_line:
                                all_logs.append(clean_line)
            except Exception as e:
                print(f"读取通用日志 {log_file_path} 失败: {str(e)}")
    
    # 4. Agent 特定输出日志 (logs/submissions/{submission_id}_*.txt)
    submissions_log_dir = "logs/submissions"
    if os.path.exists(submissions_log_dir):
        try:
            for filename in os.listdir(submissions_log_dir):
                if filename.startswith(f"{submission_id}_") and filename.endswith(".txt"):
                    with open(os.path.join(submissions_log_dir, filename), "r", encoding="utf-8") as f:
                        for line in f:
                            clean_line = line.strip()
                            if clean_line:
                                all_logs.append(f"[AGENT_OUTPUT:{filename}] {clean_line}")
        except Exception as e:
            print(f"搜索 agent 输出日志失败: {str(e)}")
    
    # 检查截图是否存在
    screenshots = []
    screenshot_folder = "logs/submissions"
    if os.path.exists(screenshot_folder):
        for file in os.listdir(screenshot_folder):
            if file.startswith(f"{submission_id}_") and file.endswith(".png"):
                screenshot_url = f"/logs/submissions/{file}"
                file_path = os.path.join(screenshot_folder, file)
                if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
                    screenshots.append(screenshot_url)
    # 通用浏览器错误截图 (如果它们能通过文件名或其他方式关联到 submission_id)
    browser_error_screenshot_folder = "logs/browser"
    if os.path.exists(browser_error_screenshot_folder):
        for file in os.listdir(browser_error_screenshot_folder):
            if submission_id in file and file.endswith(".png") and ("error" in file.lower() or "navigation" in file.lower()):
                screenshot_url = f"/logs/browser/{file}"
                screenshots.append(screenshot_url)
    
    # 去重并保持顺序
    unique_logs = []
    seen = set()
    for log_entry in all_logs:
        if log_entry not in seen:
            unique_logs.append(log_entry)
            seen.add(log_entry)
    
    print(f"为 submission_id {submission_id} 加载了 {len(unique_logs)} 条唯一日志.")
    
    debug_mode = os.getenv("DEBUG", "False").lower() in ('true', '1', 't')
    
    return templates.TemplateResponse(
        "submission_logs.html", 
        {
            "request": request, 
            "user": None, 
            "submission": submission, # 完整的 submission 对象
            "submitter_logs": unique_logs,
            "screenshots": screenshots, # 确保截图列表也传递
            "debug": debug_mode,
            "submission_id": submission_id
        }
    )

async def process_submission_background(submission_id: str):
    """在后台处理提交请求"""
    await submission_processor.process_submission(submission_id)
    
@app.post("/start-submission/{submission_id}")
async def start_submission(submission_id: str, background_tasks: BackgroundTasks):
    """开始处理提交"""
    try:
        # 读取提交
        with open(f"submissions/{submission_id}.json", "r", encoding="utf-8") as f:
            submission = json.load(f)
        
        # 更新状态为处理中
        submission["status"] = "running"
        with open(f"submissions/{submission_id}.json", "w", encoding="utf-8") as f:
            json.dump(submission, f, indent=2, ensure_ascii=False)
        
        # 在后台任务中处理提交
        background_tasks.add_task(process_submission_background, submission_id)
        
        return RedirectResponse(url=f"/submission/{submission_id}", status_code=303)
    except Exception as e:
        print(f"开始提交失败: {str(e)}")
        return RedirectResponse(url="/submissions", status_code=303)

@app.delete("/api/submissions/{submission_id}")
async def delete_submission(submission_id: str):
    """删除指定的提交"""
    file_path = f"submissions/{submission_id}.json"
    
    # 检查文件是否存在
    if not os.path.exists(file_path):
        return {"success": False, "message": "提交不存在"}
    
    try:
        # 删除提交文件
        os.remove(file_path)
        
        # 删除相关的日志文件
        console_log_path = f"logs/submissions/{submission_id}_console.log"
        if os.path.exists(console_log_path):
            os.remove(console_log_path)
        
        return {"success": True, "message": "提交已成功删除"}
    except Exception as e:
        return {"success": False, "message": f"删除失败: {str(e)}"}

# 创建templates目录和所需模板
if not os.path.exists("app/web/templates/new_submission.html"):
    with open("app/web/templates/new_submission.html", "w") as f:
        f.write("""{% extends "base.html" %}

{% block content %}
<div class="max-w-2xl mx-auto bg-white p-6 rounded-lg shadow-md">
    <h1 class="text-2xl font-bold mb-6">创建新提交</h1>
    
    <form action="/submit" method="post" class="space-y-4" enctype="multipart/form-data">
        <div>
            <label class="block text-gray-700">产品名称 *</label>
            <input type="text" name="product_name" required class="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring focus:ring-blue-500 focus:ring-opacity-50">
        </div>
        
        <div>
            <label class="block text-gray-700">产品网址 *</label>
            <input type="url" name="product_url" required class="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring focus:ring-blue-500 focus:ring-opacity-50">
        </div>
        
        <div>
            <label class="block text-gray-700">简短描述 *</label>
            <input type="text" name="short_description" required placeholder="简短概括您的工具（150字以内）" maxlength="150" class="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring focus:ring-blue-500 focus:ring-opacity-50">
        </div>
        
        <div>
            <label class="block text-gray-700">详细描述 *</label>
            <textarea name="product_description" required rows="4" placeholder="详细介绍您的工具功能和优势" class="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring focus:ring-blue-500 focus:ring-opacity-50"></textarea>
        </div>
        
        <div>
            <label class="block text-gray-700">产品分类 *</label>
            <select name="product_category" required class="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring focus:ring-blue-500 focus:ring-opacity-50">
                <option value="">-- 请选择 --</option>
                <option value="text">文本生成</option>
                <option value="image">图像生成</option>
                <option value="video">视频制作</option>
                <option value="audio">音频处理</option>
                <option value="chatbot">聊天机器人</option>
                <option value="content">内容创建</option>
                <option value="marketing">营销工具</option>
                <option value="productivity">生产力工具</option>
                <option value="research">研究分析</option>
                <option value="coding">编程辅助</option>
                <option value="other">其他</option>
            </select>
        </div>
        
        <div>
            <label class="block text-gray-700">价格模型 *</label>
            <select name="pricing_model" required class="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring focus:ring-blue-500 focus:ring-opacity-50">
                <option value="">-- 请选择 --</option>
                <option value="free">完全免费</option>
                <option value="freemium">基础免费 + 付费高级版</option>
                <option value="paid">付费</option>
                <option value="subscription">订阅制</option>
                <option value="one_time">一次性付费</option>
            </select>
        </div>
        
        <div>
            <label class="block text-gray-700">产品标签</label>
            <input type="text" name="product_tags" placeholder="以逗号分隔，例如：AI,自动化,工具" class="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring focus:ring-blue-500 focus:ring-opacity-50">
        </div>
        
        <div>
            <label class="block text-gray-700">产品Logo *</label>
            <input type="file" name="product_logo" accept="image/png, image/jpeg" required class="mt-1 block w-full text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded-full file:border-0 file:text-sm file:font-semibold file:bg-blue-50 file:text-blue-700 hover:file:bg-blue-100">
            <p class="text-sm text-gray-500 mt-1">推荐尺寸: 512x512像素，格式: JPG或PNG</p>
        </div>
        
        <div>
            <label class="block text-gray-700">产品截图</label>
            <input type="file" name="product_screenshot" accept="image/png, image/jpeg" class="mt-1 block w-full text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded-full file:border-0 file:text-sm file:font-semibold file:bg-blue-50 file:text-blue-700 hover:file:bg-blue-100">
            <p class="text-sm text-gray-500 mt-1">产品界面截图，推荐尺寸: 1280x720像素</p>
        </div>
        
        <div>
            <label class="block text-gray-700">目标目录网站 *</label>
            <div class="mt-2 space-y-2">
                <label class="inline-flex items-center">
                    <input type="checkbox" name="target_directories" value="https://aitools.neilpatel.com/submit/" checked class="rounded border-gray-300 text-blue-600 shadow-sm focus:border-blue-300 focus:ring focus:ring-blue-200 focus:ring-opacity-50">
                    <span class="ml-2">NeilPatel AI Tools</span>
                </label>
                <label class="inline-flex items-center">
                    <input type="checkbox" name="target_directories" value="https://aitoolslist.io/submit-ai-tool/" checked class="rounded border-gray-300 text-blue-600 shadow-sm focus:border-blue-300 focus:ring focus:ring-blue-200 focus:ring-opacity-50">
                    <span class="ml-2">AI Tools List</span>
                </label>
                <label class="inline-flex items-center">
                    <input type="checkbox" name="target_directories" value="https://free-ai-tools-directory.com/submit-request/" class="rounded border-gray-300 text-blue-600 shadow-sm focus:border-blue-300 focus:ring focus:ring-blue-200 focus:ring-opacity-50">
                    <span class="ml-2">Free AI Tools Directory</span>
                </label>
                <label class="inline-flex items-center">
                    <input type="checkbox" name="target_directories" value="https://gpt3demo.com/partner/request" class="rounded border-gray-300 text-blue-600 shadow-sm focus:border-blue-300 focus:ring focus:ring-blue-200 focus:ring-opacity-50">
                    <span class="ml-2">GPT3 Demo</span>
                </label>
                <label class="inline-flex items-center">
                    <input type="checkbox" name="target_directories" value="https://www.insidr.ai/submit-tools/" class="rounded border-gray-300 text-blue-600 shadow-sm focus:border-blue-300 focus:ring focus:ring-blue-200 focus:ring-opacity-50">
                    <span class="ml-2">Insidr.ai</span>
                </label>
                <label class="inline-flex items-center">
                    <input type="checkbox" name="target_directories" value="https://www.humanornot.co/submit-tool" class="rounded border-gray-300 text-blue-600 shadow-sm focus:border-blue-300 focus:ring focus:ring-blue-200 focus:ring-opacity-50">
                    <span class="ml-2">HumanOrNot</span>
                </label>
                <label class="inline-flex items-center">
                    <input type="checkbox" name="target_directories" value="https://www.rundown.ai/submit" class="rounded border-gray-300 text-blue-600 shadow-sm focus:border-blue-300 focus:ring focus:ring-blue-200 focus:ring-opacity-50">
                    <span class="ml-2">Rundown.ai</span>
                </label>
            </div>
        </div>
        
        <div>
            <label class="block text-gray-700">联系邮箱 *</label>
            <input type="email" name="email" required class="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring focus:ring-blue-500 focus:ring-opacity-50">
        </div>
        
        <div class="pt-4">
            <button type="submit" class="w-full bg-blue-600 hover:bg-blue-700 text-white font-bold py-2 px-4 rounded-full transition">
                保存并提交
            </button>
        </div>
    </form>
</div>
{% endblock %}""")

if not os.path.exists("app/web/templates/submissions.html"):
    with open("app/web/templates/submissions.html", "w") as f:
        f.write("""{% extends "base.html" %}

{% block content %}
<div class="max-w-5xl mx-auto">
    <div class="flex justify-between items-center mb-6">
        <h1 class="text-2xl font-bold">我的提交</h1>
        <a href="/new-submission" class="bg-blue-600 hover:bg-blue-700 text-white font-bold py-2 px-4 rounded-full transition">新建提交</a>
    </div>
    
    {% if submissions %}
    <div class="bg-white rounded-lg shadow-md overflow-hidden">
        <table class="min-w-full divide-y divide-gray-200">
            <thead class="bg-gray-50">
                <tr>
                    <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">产品名称</th>
                    <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">目标网站数</th>
                    <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">状态</th>
                    <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">创建时间</th>
                    <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">操作</th>
                </tr>
            </thead>
            <tbody class="bg-white divide-y divide-gray-200">
                {% for submission in submissions %}
                <tr>
                    <td class="px-6 py-4 whitespace-nowrap">{{ submission.product_name }}</td>
                    <td class="px-6 py-4 whitespace-nowrap">{{ submission.target_directories|length }}</td>
                    <td class="px-6 py-4 whitespace-nowrap">
                        {% if submission.status == "completed" %}
                        <span class="px-2 inline-flex text-xs leading-5 font-semibold rounded-full bg-green-100 text-green-800">
                            已完成
                        </span>
                        {% elif submission.status == "running" %}
                        <span class="px-2 inline-flex text-xs leading-5 font-semibold rounded-full bg-blue-100 text-blue-800">
                            进行中
                        </span>
                        {% elif submission.status == "pending" %}
                        <span class="px-2 inline-flex text-xs leading-5 font-semibold rounded-full bg-yellow-100 text-yellow-800">
                            待处理
                        </span>
                        {% else %}
                        <span class="px-2 inline-flex text-xs leading-5 font-semibold rounded-full bg-red-100 text-red-800">
                            失败
                        </span>
                        {% endif %}
                    </td>
                    <td class="px-6 py-4 whitespace-nowrap">{{ submission.created_at.split("T")[0] }}</td>
                    <td class="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                        <a href="/submission/{{ submission.id }}" class="text-blue-600 hover:text-blue-900">查看</a>
                    </td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
    </div>
    {% else %}
    <div class="bg-white p-6 rounded-lg shadow-md text-center">
        <p class="text-gray-500">您还没有提交记录</p>
        <a href="/new-submission" class="mt-4 inline-block bg-blue-600 hover:bg-blue-700 text-white font-bold py-2 px-6 rounded-full transition">创建第一个提交</a>
    </div>
    {% endif %}
</div>
{% endblock %}""")

if not os.path.exists("app/web/templates/submission_detail.html"):
    with open("app/web/templates/submission_detail.html", "w") as f:
        f.write("""{% extends "base.html" %}

{% block content %}
<div class="max-w-5xl mx-auto">
    <div class="mb-6">
        <a href="/submissions" class="text-blue-600 hover:text-blue-800">← 返回提交列表</a>
    </div>
    
    <div class="bg-white p-6 rounded-lg shadow-md mb-6">
        <div class="flex justify-between items-start">
            <h1 class="text-2xl font-bold">{{ submission.product_name }}</h1>
            
            <div>
                {% if submission.status == "completed" %}
                <span class="px-2 inline-flex text-xs leading-5 font-semibold rounded-full bg-green-100 text-green-800">
                    已完成
                </span>
                {% elif submission.status == "running" %}
                <span class="px-2 inline-flex text-xs leading-5 font-semibold rounded-full bg-blue-100 text-blue-800">
                    进行中
                </span>
                {% elif submission.status == "pending" %}
                <span class="px-2 inline-flex text-xs leading-5 font-semibold rounded-full bg-yellow-100 text-yellow-800">
                    待处理
                </span>
                <form action="/start-submission/{{ submission.id }}" method="post" class="mt-2">
                    <button type="submit" class="bg-blue-600 hover:bg-blue-700 text-white text-xs px-3 py-1 rounded-full transition">
                        开始提交
                    </button>
                </form>
                {% else %}
                <span class="px-2 inline-flex text-xs leading-5 font-semibold rounded-full bg-red-100 text-red-800">
                    失败
                </span>
                {% endif %}
            </div>
        </div>
        
        <div class="mt-6 grid grid-cols-1 md:grid-cols-2 gap-x-8 gap-y-4">
            <div>
                <h2 class="text-lg font-semibold mb-2">基本信息</h2>
                
                <div class="space-y-3">
                    <div>
                        <span class="text-gray-500">产品网址:</span>
                        <a href="{{ submission.product_url }}" target="_blank" class="ml-2 text-blue-600 hover:text-blue-800">{{ submission.product_url }}</a>
                    </div>
                    
                    <div>
                        <span class="text-gray-500">简短描述:</span>
                        <span class="ml-2">{{ submission.short_description }}</span>
                    </div>
                    
                    <div>
                        <span class="text-gray-500">分类:</span>
                        <span class="ml-2">{{ submission.product_category }}</span>
                    </div>
                    
                    <div>
                        <span class="text-gray-500">价格模型:</span>
                        <span class="ml-2">{{ submission.pricing_model }}</span>
                    </div>
                    
                    {% if submission.product_tags %}
                    <div>
                        <span class="text-gray-500">标签:</span>
                        <div class="mt-1">
                            {% for tag in submission.product_tags %}
                            <span class="inline-block bg-gray-100 rounded-full px-3 py-1 text-xs font-semibold text-gray-700 mr-2 mb-2">{{ tag }}</span>
                            {% endfor %}
                        </div>
                    </div>
                    {% endif %}
                    
                    <div>
                        <span class="text-gray-500">联系邮箱:</span>
                        <span class="ml-2">{{ submission.email }}</span>
                    </div>
                </div>
            </div>
            
            <div>
                <h2 class="text-lg font-semibold mb-2">详细描述</h2>
                <p class="text-gray-700 whitespace-pre-wrap">{{ submission.product_description }}</p>
            </div>
        </div>
        
        <div class="mt-6 grid grid-cols-1 md:grid-cols-2 gap-8">
            {% if submission.logo_path %}
            <div>
                <h2 class="text-lg font-semibold mb-2">产品Logo</h2>
                <img src="/{{ submission.logo_path }}" alt="{{ submission.product_name }} Logo" class="max-w-full h-auto rounded-lg shadow-sm">
            </div>
            {% endif %}
            
            {% if submission.screenshot_path %}
            <div>
                <h2 class="text-lg font-semibold mb-2">产品截图</h2>
                <img src="/{{ submission.screenshot_path }}" alt="{{ submission.product_name }} 截图" class="max-w-full h-auto rounded-lg shadow-sm">
            </div>
            {% endif %}
        </div>
    </div>
    
    <div class="bg-white p-6 rounded-lg shadow-md">
        <h2 class="text-xl font-bold mb-4">提交状态</h2>
        
        <div class="space-y-6">
            {% for result in submission.results %}
            <div class="border-b border-gray-200 pb-4 {% if loop.last %}border-b-0{% endif %}">
                <div class="flex justify-between items-start">
                    <h3 class="text-lg font-semibold">{{ result.directory_url }}</h3>
                    
                    <div>
                        {% if result.is_success == true %}
                        <span class="px-2 inline-flex text-xs leading-5 font-semibold rounded-full bg-green-100 text-green-800">
                            提交成功
                        </span>
                        {% elif result.is_success == false %}
                        <span class="px-2 inline-flex text-xs leading-5 font-semibold rounded-full bg-red-100 text-red-800">
                            提交失败
                        </span>
                        {% else %}
                        <span class="px-2 inline-flex text-xs leading-5 font-semibold rounded-full bg-gray-100 text-gray-800">
                            尚未提交
                        </span>
                        {% endif %}
                    </div>
                </div>
                
                {% if result.submitted_at %}
                <div class="mt-2 text-sm text-gray-500">
                    提交时间: {{ result.submitted_at }}
                </div>
                {% endif %}
                
                {% if result.short_reason_if_failed %}
                <div class="mt-2 text-sm text-red-600">
                    失败原因: {{ result.short_reason_if_failed }}
                </div>
                {% endif %}
            </div>
            {% endfor %}
        </div>
    </div>
</div>
{% endblock %}""")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001) 