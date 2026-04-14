FROM python:3.11-slim

WORKDIR /app

COPY alert_service/requirements.txt ./alert_service/requirements.txt
RUN pip install --no-cache-dir -r alert_service/requirements.txt

COPY config/ ./config/
COPY alert_service/ ./alert_service/

ENV PYTHONPATH=/app
