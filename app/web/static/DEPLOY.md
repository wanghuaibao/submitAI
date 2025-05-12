# 部署指南

本文档提供将自动化产品提交工具部署到公共服务器的详细步骤。

## 部署方式选择

您可以选择以下几种方式部署应用：

1. **直接部署**：在支持Python的VPS或云服务器上直接运行
2. **Docker部署**：使用Docker容器化部署
3. **PaaS服务**：使用Heroku、Vercel等平台即服务

以下是每种方式的详细步骤。

## 1. 直接部署到VPS或云服务器

### 前提条件

- 一个运行Linux的VPS或云服务器(如Ubuntu 20.04+)
- 具有root或sudo权限的账户
- 域名(可选，但推荐)

### 步骤

#### 1.1 安装依赖

连接到您的服务器，然后运行以下命令：

```bash
# 更新系统
sudo apt update
sudo apt upgrade -y

# 安装Python和必要工具
sudo apt install -y python3 python3-pip python3-venv git nginx

# 安装支持Playwright的依赖
sudo apt install -y libgbm1 libasound2 libnspr4 libnss3 libxss1 libxtst6 xvfb
```

#### 1.2 克隆项目

```bash
# 创建应用目录
mkdir -p /var/www/submitai
cd /var/www/submitai

# 克隆仓库
git clone <项目仓库URL> .

# 创建虚拟环境
python3 -m venv venv
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt

# 安装Playwright浏览器
playwright install chromium
```

#### 1.3 配置环境变量

```bash
# 创建.env文件
cat > .env << EOL
# Grok API密钥
GROK_API_KEY=your-grok-api-key-here

# 设置为true启用调试模式
DEBUG=false

# 浏览器配置
HEADLESS=true
EOL

# 设置正确的权限
chmod 600 .env
```

#### 1.4 配置Systemd服务

创建服务文件：

```bash
sudo nano /etc/systemd/system/submitai.service
```

添加以下内容：

```
[Unit]
Description=SubmitAI Application
After=network.target

[Service]
User=www-data
Group=www-data
WorkingDirectory=/var/www/submitai
ExecStart=/var/www/submitai/venv/bin/python -m uvicorn simple_app:app --host 0.0.0.0 --port 8000
Restart=always
Environment="PATH=/var/www/submitai/venv/bin"
Environment="PYTHONPATH=/var/www/submitai"

[Install]
WantedBy=multi-user.target
```

启动服务：

```bash
# 调整目录权限
sudo chown -R www-data:www-data /var/www/submitai

# 启动服务
sudo systemctl daemon-reload
sudo systemctl start submitai
sudo systemctl enable submitai
```

#### 1.5 配置Nginx反向代理

创建Nginx配置文件：

```bash
sudo nano /etc/nginx/sites-available/submitai
```

添加以下内容：

```
server {
    listen 80;
    server_name your-domain.com;  # 替换为您的域名

    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /static {
        alias /var/www/submitai/app/web/static;
        expires 1d;
    }

    location /uploads {
        alias /var/www/submitai/uploads;
        expires 1d;
    }
}
```

激活配置：

```bash
sudo ln -s /etc/nginx/sites-available/submitai /etc/nginx/sites-enabled/
sudo nginx -t  # 检查配置是否正确
sudo systemctl restart nginx
```

#### 1.6 配置SSL（可选但推荐）

使用Certbot安装SSL证书：

```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d your-domain.com
```

## 2. Docker部署

### 前提条件

- 安装了Docker和Docker Compose的服务器

### 步骤

#### 2.1 创建Dockerfile

在项目根目录创建`Dockerfile`：

```
FROM mcr.microsoft.com/playwright:v1.40.0-focal

WORKDIR /app

# 复制依赖文件
COPY requirements.txt .

# 安装依赖
RUN pip install --no-cache-dir -r requirements.txt

# 复制应用代码
COPY . .

# 创建必要的目录
RUN mkdir -p app/web/static uploads/logos uploads/screenshots logs submissions

# 设置权限
RUN chmod +x start.sh

# 暴露端口
EXPOSE 8000

# 启动命令
CMD ["python", "-m", "uvicorn", "simple_app:app", "--host", "0.0.0.0", "--port", "8000"]
```

#### 2.2 创建docker-compose.yml

```yaml
version: '3'

services:
  submitai:
    build: .
    container_name: submitai
    restart: always
    ports:
      - "8000:8000"
    volumes:
      - ./uploads:/app/uploads
      - ./logs:/app/logs
      - ./submissions:/app/submissions
    environment:
      - GROK_API_KEY=your-grok-api-key-here
      - DEBUG=false
      - HEADLESS=true
```

#### 2.3 启动服务

```bash
docker-compose up -d
```

## 3. 部署到Heroku

### 前提条件

- Heroku账户
- 已安装Heroku CLI

### 步骤

#### 3.1 准备应用

创建`Procfile`文件：

```
web: uvicorn simple_app:app --host=0.0.0.0 --port=$PORT
```

创建`runtime.txt`文件：

```
python-3.9.16
```

#### 3.2 部署到Heroku

```bash
# 登录Heroku
heroku login

# 创建应用
heroku create submitai-app

# 设置环境变量
heroku config:set GROK_API_KEY=your-grok-api-key-here
heroku config:set DEBUG=false
heroku config:set HEADLESS=true

# 部署应用
git push heroku main

# 打开应用
heroku open
```

## 注意事项

1. **数据持久化**：确保挂载卷或设置适当的存储机制，以保存用户上传的文件和提交数据。
2. **资源需求**：运行浏览器自动化需要足够的CPU和内存资源，推荐至少2GB RAM。
3. **安全性**：确保.env文件和API密钥安全存储，不对外暴露。
4. **监控**：设置监控和日志收集，以便及时发现和解决问题。

## 故障排除

如果遇到部署问题，请检查：

1. 应用日志：`journalctl -u submitai.service`
2. Nginx日志：`/var/log/nginx/error.log`
3. 确保所有依赖都已正确安装
4. 确保端口没有被防火墙阻止

如需进一步帮助，请联系支持团队。 