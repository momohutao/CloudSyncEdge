FROM crpi-e3xf1f4ufw4ehjak.cn-chengdu.personal.cr.aliyuncs.com/exp_hutianqi/python:3.10-slim

# 简化安装步骤：基础镜像已包含Python 3.10和pip
RUN apt-get update && apt-get install -y --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*  # 仅清理缓存，无需重复安装Python

WORKDIR /app
#COPY requirements.txt requirements.txt

# 使用阿里云pip源加速依赖安装
#RUN pip3 install -r requirements.txt -i https://mirrors.aliyun.com/pypi/simple/

#COPY . .
EXPOSE 8004 8000 8001 8002
CMD ["python", "-m", "debugpy", "--listen", "0.0.0.0:5678", "-m", "uvicorn", "northbound.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]