FROM python:3.11-slim

WORKDIR /app

# System dependencies for OpenCV
RUN apt-get update && apt-get install -y --no-install-recommends \
    libglib2.0-0 libsm6 libxext6 libxrender-dev libgl1 \
    && rm -rf /var/lib/apt/lists/*

COPY api_gateway/requirements.txt ./api_gateway/requirements.txt
RUN pip install --no-cache-dir -r api_gateway/requirements.txt

# Copy all services so imports work
COPY config/ ./config/
COPY database/ ./database/
COPY detection_service/ ./detection_service/
COPY tracking_service/ ./tracking_service/
COPY behavior_service/ ./behavior_service/
COPY alert_service/ ./alert_service/
COPY api_gateway/ ./api_gateway/

RUN mkdir -p /app/logs

ENV PYTHONPATH=/app

EXPOSE 8000

CMD ["uvicorn", "api_gateway.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
