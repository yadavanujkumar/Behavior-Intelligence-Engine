"""
Shared configuration loader for all BIE microservices.

Reads settings from environment variables (populated from .env / docker-compose env).
Every service imports this module so configuration lives in one place.
"""

import os
from dataclasses import dataclass


@dataclass
class Config:
    # ---- Database -----------------------------------------------------------
    database_url: str = os.getenv(
        "DATABASE_URL",
        "postgresql://bie_user:bie_pass@localhost:5432/behavior_intelligence",
    )
    database_pool_size: int = int(os.getenv("DATABASE_POOL_SIZE", "10"))

    # ---- Detection ----------------------------------------------------------
    detection_model: str = os.getenv("DETECTION_MODEL", "yolov8n.pt")
    detection_confidence: float = float(os.getenv("DETECTION_CONFIDENCE", "0.5"))
    detection_device: str = os.getenv("DETECTION_DEVICE", "cpu")

    # ---- Tracking -----------------------------------------------------------
    deepsort_max_age: int = int(os.getenv("DEEPSORT_MAX_AGE", "30"))
    deepsort_n_init: int = int(os.getenv("DEEPSORT_N_INIT", "3"))
    deepsort_max_cosine_dist: float = float(
        os.getenv("DEEPSORT_MAX_COSINE_DIST", "0.4")
    )

    # ---- Behavior -----------------------------------------------------------
    loitering_time_threshold: int = int(
        os.getenv("LOITERING_TIME_THRESHOLD", "120")
    )
    loitering_radius: int = int(os.getenv("LOITERING_RADIUS", "80"))
    speed_threshold: float = float(os.getenv("SPEED_THRESHOLD", "50"))
    trajectory_history: int = int(os.getenv("TRAJECTORY_HISTORY", "100"))
    repeated_path_min_loops: int = int(os.getenv("REPEATED_PATH_MIN_LOOPS", "3"))
    repeated_path_similarity: float = float(
        os.getenv("REPEATED_PATH_SIMILARITY", "0.85")
    )

    # ---- Alert --------------------------------------------------------------
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    openai_model: str = os.getenv("OPENAI_MODEL", "gpt-3.5-turbo")
    alert_cooldown: int = int(os.getenv("ALERT_COOLDOWN", "30"))

    # ---- Video --------------------------------------------------------------
    video_source: str = os.getenv("VIDEO_SOURCE", "0")
    frame_width: int = int(os.getenv("FRAME_WIDTH", "1280"))
    frame_height: int = int(os.getenv("FRAME_HEIGHT", "720"))
    frame_fps: int = int(os.getenv("FRAME_FPS", "30"))
    mjpeg_quality: int = int(os.getenv("MJPEG_QUALITY", "80"))

    # ---- API ----------------------------------------------------------------
    api_host: str = os.getenv("API_HOST", "0.0.0.0")
    api_port: int = int(os.getenv("API_PORT", "8000"))
    cors_origins: list = None  # populated in __post_init__
    jwt_secret: str = os.getenv("JWT_SECRET", "change_me_in_production")
    jwt_algorithm: str = os.getenv("JWT_ALGORITHM", "HS256")

    # ---- Logging ------------------------------------------------------------
    log_level: str = os.getenv("LOG_LEVEL", "INFO")
    log_file: str = os.getenv("LOG_FILE", "/app/logs/bie.log")

    def __post_init__(self):
        raw = os.getenv(
            "CORS_ORIGINS", "http://localhost:3000,http://frontend:3000"
        )
        self.cors_origins = [o.strip() for o in raw.split(",")]


# Singleton – import `cfg` throughout the codebase
cfg = Config()
