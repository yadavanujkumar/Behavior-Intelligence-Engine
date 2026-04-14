"""
SQLAlchemy ORM models for the Behavior Intelligence Engine.

Tables:
  - tracking_logs  : raw detection + tracking records per frame
  - behavior_events: detected behavior incidents per tracked person
  - alerts         : generated alert messages (with LLM narrative)
"""

import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Float,
    Integer,
    String,
    Text,
    create_engine,
)
from sqlalchemy.orm import declarative_base, sessionmaker

from config.settings import cfg

Base = declarative_base()


class TrackingLog(Base):
    """One record per detected person per frame."""

    __tablename__ = "tracking_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    track_id = Column(Integer, nullable=False, index=True)
    frame_number = Column(Integer, nullable=False)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow, index=True)
    camera_id = Column(String(64), default="cam0")

    # Bounding box (pixel coordinates)
    bbox_x1 = Column(Float)
    bbox_y1 = Column(Float)
    bbox_x2 = Column(Float)
    bbox_y2 = Column(Float)

    # Centroid position
    cx = Column(Float)
    cy = Column(Float)

    detection_confidence = Column(Float)


class BehaviorEvent(Base):
    """A detected behavior event for a tracked individual."""

    __tablename__ = "behavior_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    track_id = Column(Integer, nullable=False, index=True)
    camera_id = Column(String(64), default="cam0")
    behavior_type = Column(String(64), nullable=False)  # loitering / repeated_path / sudden_motion
    severity = Column(String(16), default="medium")      # low / medium / high
    confidence = Column(Float, default=1.0)
    details = Column(JSON)                               # extra numeric data
    started_at = Column(DateTime, default=datetime.datetime.utcnow)
    ended_at = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=True)


class Alert(Base):
    """A human-readable alert generated for a behavior event."""

    __tablename__ = "alerts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    behavior_event_id = Column(Integer, nullable=True)
    track_id = Column(Integer, nullable=False, index=True)
    camera_id = Column(String(64), default="cam0")
    behavior_type = Column(String(64))
    severity = Column(String(16), default="medium")
    message = Column(Text, nullable=False)               # LLM-generated narrative
    acknowledged = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, index=True)


# ---------------------------------------------------------------------------
# Database engine & session factory
# ---------------------------------------------------------------------------

engine = create_engine(
    cfg.database_url,
    pool_size=cfg.database_pool_size,
    max_overflow=20,
    pool_pre_ping=True,
    echo=False,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db():
    """Create all tables (idempotent)."""
    Base.metadata.create_all(bind=engine)


def get_db():
    """FastAPI dependency – yield a DB session, then close it."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
