FROM python:3.11-slim

WORKDIR /srv/brand-normalize

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY ofs_brand_core ./ofs_brand_core
COPY config ./config
COPY cli.py .

# 数据卷挂载点（运行容器时挂载，不打包进镜像）:
#   品牌库          -v /host/matcher.db:/data/matcher.db:ro
#   SCS 凭据(只读)  -v /host/secrets:/secrets:ro
ENV BRAND_DATA_PATH=/data/matcher.db \
    SCS_ENABLED=1 \
    SCS_TOKEN_FILE=/secrets/scs-token.json \
    HOST=0.0.0.0 \
    PORT=8000

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s \
  CMD python -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8000/health')"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
