FROM python:3.11-slim

WORKDIR /app

# System dependencies for OpenCV
RUN apt-get update && apt-get install -y --no-install-recommends \
    libglib2.0-0 libsm6 libxext6 libxrender-dev libgl1 \
    && rm -rf /var/lib/apt/lists/*

COPY detection_service/requirements.txt ./detection_service/requirements.txt
RUN pip install --no-cache-dir -r detection_service/requirements.txt

COPY config/ ./config/
COPY detection_service/ ./detection_service/

ENV PYTHONPATH=/app
CMD ["python", "-m", "detection_service.detector"]
