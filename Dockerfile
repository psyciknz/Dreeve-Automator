FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DREEVE_UI_DATA_DIR=/data

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY ui ./ui
COPY src ./src
COPY wsgi.py .

# Unprivileged user; /data is created owned by it so a *named* volume inherits that ownership.
RUN useradd --create-home --uid 10001 app \
    && mkdir -p /data \
    && chown app:app /data
USER app

VOLUME /data
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=3)"

# One worker on purpose: config writes are serialised with an in-process lock.
# Threads give concurrency without giving up that guarantee.
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "1", "--threads", "4", "--access-logfile", "-", "wsgi:app"]
