FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libglib2.0-0 libsm6 libxext6 libxrender-dev libgl1 \
    && rm -rf /var/lib/apt/lists/*

COPY tracking_service/requirements.txt ./tracking_service/requirements.txt
RUN pip install --no-cache-dir -r tracking_service/requirements.txt

COPY config/ ./config/
COPY detection_service/ ./detection_service/
COPY tracking_service/ ./tracking_service/

ENV PYTHONPATH=/app
