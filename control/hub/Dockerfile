FROM python:3.12-slim
WORKDIR /app
COPY hub/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY hub/server.py hub/mqtt_bridge.py ./
COPY viewer3d /app/viewer
ENV VIEWER_DIR=/app/viewer PYTHONUNBUFFERED=1
RUN useradd -r -u 10001 hub
USER hub
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=3s CMD python -c "import urllib.request as u; u.urlopen('http://127.0.0.1:8080/health', timeout=2)"
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8080", "--ws-ping-interval", "15", "--ws-ping-timeout", "15"]
