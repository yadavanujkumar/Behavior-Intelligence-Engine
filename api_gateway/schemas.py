"""
Pydantic schemas used by the FastAPI endpoints.

Separating schemas from ORM models keeps the API layer independent of the
database layer and enables independent versioning.
"""

import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Alert schemas
# ---------------------------------------------------------------------------

class AlertBase(BaseModel):
    track_id: int
    camera_id: str = "cam0"
    behavior_type: str
    severity: str
    message: str
    confidence: float = Field(ge=0.0, le=1.0)
    details: Optional[Dict[str, Any]] = {}


class AlertCreate(AlertBase):
    pass


class AlertResponse(AlertBase):
    id: int
    acknowledged: bool
    created_at: datetime.datetime

    model_config = {"from_attributes": True}


class AlertAcknowledge(BaseModel):
    acknowledged: bool = True


# ---------------------------------------------------------------------------
# Tracking log schemas
# ---------------------------------------------------------------------------

class TrackingLogCreate(BaseModel):
    track_id: int
    frame_number: int
    camera_id: str = "cam0"
    bbox_x1: float
    bbox_y1: float
    bbox_x2: float
    bbox_y2: float
    cx: float
    cy: float
    detection_confidence: float


class TrackingLogResponse(TrackingLogCreate):
    id: int
    timestamp: datetime.datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Behavior event schemas
# ---------------------------------------------------------------------------

class BehaviorEventResponse(BaseModel):
    id: int
    track_id: int
    camera_id: str
    behavior_type: str
    severity: str
    confidence: float
    details: Optional[Dict[str, Any]]
    started_at: datetime.datetime
    ended_at: Optional[datetime.datetime]
    is_active: bool

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Stats schema
# ---------------------------------------------------------------------------

class StatsResponse(BaseModel):
    total_alerts: int
    active_tracks: int
    alerts_by_type: Dict[str, int]
    alerts_by_severity: Dict[str, int]
    uptime_seconds: float
    cameras: List[str]
