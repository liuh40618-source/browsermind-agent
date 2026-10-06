# BrowserMind Dockerfile
# 基于 slim Python，安装 Chromium 供 Playwright 使用
FROM python:3.12-slim

# 避免 Python 生成 .pyc 并让 stdout/stderr 直接输出（容器内无缓冲）
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

WORKDIR /app

# 1. 先装依赖（利用 Docker 层缓存：requirements 不变则不重装）
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && playwright install --with-deps chromium

# 2. 复制项目代码
COPY . .

# 3. 容器内运行所需的系统依赖（playwright install --with-deps 已处理大部分）
# 暴露端口：config.py 默认 8000
EXPOSE 8000

# 启动 FastAPI 服务（数据目录挂载见 docker-compose.yml）
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
