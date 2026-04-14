"""
FastAPI application – Behavior Intelligence Engine API Gateway.

Endpoints:
  GET  /                  Health check
  GET  /video_feed        MJPEG live video stream
  GET  /video_feed/heatmap MJPEG heatmap overlay stream
  GET  /alerts            List recent in-memory alerts
  POST /alerts/{id}/ack   Acknowledge an alert
  GET  /stats             System statistics
  GET  /behavior_events   Recent behavior events from DB
  GET  /tracking_logs     Recent tracking logs from DB

Startup: initialises the processing pipeline in a background thread.
"""

import asyncio
import time
from contextlib import asynccontextmanager
from typing import List, Optional

import cv2
import numpy as np
from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy.orm import Session

from api_gateway.pipeline import pipeline
from api_gateway.schemas import (
    AlertAcknowledge,
    AlertResponse,
    BehaviorEventResponse,
    StatsResponse,
    TrackingLogResponse,
)
from config.logger import get_logger
from config.settings import cfg
from database.models import Alert as AlertModel
from database.models import BehaviorEvent, TrackingLog, get_db, init_db

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Lifespan – startup / shutdown
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start pipeline on startup, stop on shutdown."""
    logger.info("BIE API Gateway starting up …")
    try:
        init_db()
        logger.info("Database tables ensured.")
    except Exception as exc:
        logger.warning("DB init failed (running without persistence): %s", exc)

    pipeline.start()
    yield
    pipeline.stop()
    logger.info("BIE API Gateway shut down.")


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Behavior Intelligence Engine",
    description=(
        "Real-time AI surveillance system for detecting suspicious human "
        "behavior using computer vision, tracking, and temporal analysis."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=cfg.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# MJPEG frame generator helpers
# ---------------------------------------------------------------------------

def _frame_to_jpeg(frame: np.ndarray) -> bytes:
    """Encode an OpenCV BGR frame as JPEG bytes."""
    ret, buf = cv2.imencode(
        ".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, cfg.mjpeg_quality]
    )
    return buf.tobytes() if ret else b""


def _placeholder_frame(message: str = "No feed available") -> bytes:
    """Generate a black frame with a status message."""
    placeholder = np.zeros((480, 640, 3), dtype=np.uint8)
    cv2.putText(
        placeholder,
        message,
        (80, 240),
        cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 255), 2,
    )
    return _frame_to_jpeg(placeholder)


async def _mjpeg_generator(heatmap: bool = False):
    """Async generator that yields MJPEG multipart frames."""
    while True:
        frame = pipeline.get_latest_frame(heatmap=heatmap)
        if frame is not None:
            jpeg = _frame_to_jpeg(frame)
        else:
            jpeg = _placeholder_frame()

        yield (
            b"--frame\r\n"
            b"Content-Type: image/jpeg\r\n\r\n" + jpeg + b"\r\n"
        )
        await asyncio.sleep(1.0 / cfg.frame_fps)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/", tags=["Health"])
async def root():
    return {"status": "ok", "service": "Behavior Intelligence Engine", "version": "1.0.0"}


@app.get("/video_feed", tags=["Video"])
async def video_feed():
    """
    MJPEG live video stream with bounding boxes and track IDs overlaid.

    Consume in an HTML <img> tag:
      <img src="http://localhost:8000/video_feed" />
    """
    return StreamingResponse(
        _mjpeg_generator(heatmap=False),
        media_type="multipart/x-mixed-replace; boundary=frame",
    )


@app.get("/video_feed/heatmap", tags=["Video"])
async def video_feed_heatmap():
    """MJPEG stream with movement heatmap overlay."""
    return StreamingResponse(
        _mjpeg_generator(heatmap=True),
        media_type="multipart/x-mixed-replace; boundary=frame",
    )


@app.get("/alerts", response_model=List[dict], tags=["Alerts"])
async def get_alerts(
    limit: int = Query(50, ge=1, le=500),
    severity: Optional[str] = Query(None, description="Filter by severity: low/medium/high"),
):
    """
    Return the most recent alerts from the in-memory alert queue.

    The queue is updated in real-time by the pipeline thread.
    """
    alerts = pipeline.get_alerts(limit=limit, severity=severity)
    return [
        {
            "track_id": a.track_id,
            "behavior_type": a.behavior_type,
            "severity": a.severity,
            "confidence": round(a.confidence, 3),
            "message": a.message,
            "camera_id": a.camera_id,
            "details": a.details,
            "timestamp": a.timestamp,
            "acknowledged": a.acknowledged,
        }
        for a in alerts
    ]


@app.patch("/alerts/{alert_index}/ack", tags=["Alerts"])
async def acknowledge_alert(alert_index: int, body: AlertAcknowledge):
    """Acknowledge (mark as seen) an alert by its position in the queue."""
    success = pipeline.acknowledge_alert(alert_index)
    if not success:
        raise HTTPException(status_code=404, detail="Alert index out of range.")
    return {"acknowledged": body.acknowledged}


@app.get("/stats", response_model=StatsResponse, tags=["Stats"])
async def get_stats():
    """Return system-wide statistics: active tracks, alert counts, FPS, uptime."""
    stats = pipeline.get_stats()
    return StatsResponse(
        total_alerts=stats.get("total_alerts", 0),
        active_tracks=stats.get("active_tracks", 0),
        alerts_by_type=stats.get("alerts_by_type", {}),
        alerts_by_severity=stats.get("alerts_by_severity", {}),
        uptime_seconds=stats.get("uptime_seconds", 0.0),
        cameras=["cam0"],
    )


# ---------------------------------------------------------------------------
# Database-backed routes
# ---------------------------------------------------------------------------

@app.get("/db/alerts", response_model=List[AlertResponse], tags=["Database"])
async def get_db_alerts(
    limit: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
):
    """Retrieve persisted alerts from PostgreSQL."""
    return (
        db.query(AlertModel)
        .order_by(AlertModel.created_at.desc())
        .limit(limit)
        .all()
    )


@app.get("/db/tracking_logs", response_model=List[TrackingLogResponse], tags=["Database"])
async def get_tracking_logs(
    limit: int = Query(100, ge=1, le=1000),
    track_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
):
    """Retrieve raw tracking logs from PostgreSQL."""
    q = db.query(TrackingLog)
    if track_id is not None:
        q = q.filter(TrackingLog.track_id == track_id)
    return q.order_by(TrackingLog.timestamp.desc()).limit(limit).all()


@app.get("/db/behavior_events", response_model=List[BehaviorEventResponse], tags=["Database"])
async def get_behavior_events(
    limit: int = Query(50, ge=1, le=500),
    active_only: bool = Query(False),
    db: Session = Depends(get_db),
):
    """Retrieve behavior events from PostgreSQL."""
    q = db.query(BehaviorEvent)
    if active_only:
        q = q.filter(BehaviorEvent.is_active == True)
    return q.order_by(BehaviorEvent.started_at.desc()).limit(limit).all()
