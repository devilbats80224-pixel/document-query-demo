FROM python:3.12-slim-bookworm@sha256:44cf1793efa7c7a476bb0f2cff81443f4a072c90c1cb127e2924933daa3e8c64
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 HOME=/tmp \
    LITEON_SETTINGS_PATH=/tmp/document-demo/settings.json
WORKDIR /app
COPY requirements-docker.txt ./
RUN python -m pip install --no-cache-dir -r requirements-docker.txt
COPY --chown=10001:10001 *.py ./
COPY --chown=10001:10001 demo ./demo
USER 10001:10001
EXPOSE 8775
CMD ["python","-B","-m","uvicorn","api_fastapi:app","--host","0.0.0.0","--port","8775"]
