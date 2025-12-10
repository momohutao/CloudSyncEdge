# ECU库Docker镜像
FROM python:3.9-slim as builder

# 安装构建依赖
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# 设置工作目录
WORKDIR /app

# 复制依赖文件
COPY requirements.txt .
COPY setup.py .

# 安装依赖
RUN pip install --user --no-cache-dir -r requirements.txt

# 复制项目文件
COPY . .

# 安装项目
RUN pip install --user --no-cache-dir .

# 生产阶段
FROM python:3.9-slim

# 设置环境变量
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    ECU_ENV=production \
    DATABASE_URL=sqlite+aiosqlite:///./data/ecu.db

# 创建非root用户
RUN groupadd -r ecu && useradd -r -g ecu ecu

# 创建必要的目录
RUN mkdir -p /app/data /app/logs \
    && chown -R ecu:ecu /app

# 切换到非root用户
USER ecu

# 设置工作目录
WORKDIR /app

# 从构建阶段复制已安装的包
COPY --from=builder /root/.local /home/ecu/.local

# 复制项目文件
COPY --chown=ecu:ecu . .

# 确保本地bin目录在PATH中
ENV PATH=/home/ecu/.local/bin:$PATH

# 暴露端口（如果需要）
# EXPOSE 8000

# 运行ECU库
CMD ["python", "-m", "ecu_lib.main", "--interactive"]