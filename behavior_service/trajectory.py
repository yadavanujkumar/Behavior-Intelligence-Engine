"""
Trajectory store and analysis utilities.

Each tracked person has a TrajectoryRecord that stores:
  - recent positions (capped at TRAJECTORY_HISTORY entries)
  - timestamps for loitering calculations
  - velocity history for sudden-motion detection
"""

import time
from collections import deque
from dataclasses import dataclass, field
from typing import Deque, Dict, List, Optional, Tuple

import numpy as np

from config.settings import cfg


@dataclass
class Position:
    """A single 2-D position with timestamp."""
    x: float
    y: float
    ts: float = field(default_factory=time.time)  # Unix timestamp

    def as_array(self) -> np.ndarray:
        return np.array([self.x, self.y])


@dataclass
class TrajectoryRecord:
    """All trajectory data for one tracked person."""
    track_id: int
    positions: Deque[Position] = field(default_factory=lambda: deque(maxlen=cfg.trajectory_history))
    velocities: Deque[float] = field(default_factory=lambda: deque(maxlen=50))
    first_seen: float = field(default_factory=time.time)
    last_seen: float = field(default_factory=time.time)

    # Loitering helpers
    loiter_start_ts: Optional[float] = None
    loiter_anchor: Optional[Tuple[float, float]] = None  # centre of loitering zone

    # Repeated-path helpers
    path_segment_count: int = 0

    def add_position(self, x: float, y: float) -> None:
        """Record a new position and compute velocity."""
        now = time.time()
        new_pos = Position(x=x, y=y, ts=now)

        if self.positions:
            prev = self.positions[-1]
            dt = max(now - prev.ts, 1e-6)
            dist = float(np.linalg.norm(new_pos.as_array() - prev.as_array()))
            velocity = dist / dt          # pixels per second
            self.velocities.append(velocity)

        self.positions.append(new_pos)
        self.last_seen = now

    @property
    def age_seconds(self) -> float:
        """How long (s) this person has been tracked."""
        return self.last_seen - self.first_seen

    def recent_positions(self, n: int) -> List[Position]:
        """Return last n positions as a list."""
        pos_list = list(self.positions)
        return pos_list[-n:] if len(pos_list) >= n else pos_list


class TrajectoryStore:
    """
    In-memory store for all active trajectory records.

    Thread-safety note: for production scale, wrap write operations in a Lock.
    """

    def __init__(self):
        self._store: Dict[int, TrajectoryRecord] = {}

    def update(self, track_id: int, cx: float, cy: float) -> TrajectoryRecord:
        """Add or update a trajectory record for track_id."""
        if track_id not in self._store:
            self._store[track_id] = TrajectoryRecord(track_id=track_id)

        record = self._store[track_id]
        record.add_position(cx, cy)
        return record

    def get(self, track_id: int) -> Optional[TrajectoryRecord]:
        return self._store.get(track_id)

    def remove_stale(self, active_ids: List[int], grace_period: float = 5.0) -> None:
        """Remove trajectories for IDs not seen recently."""
        now = time.time()
        stale = [
            tid
            for tid, rec in self._store.items()
            if tid not in active_ids and (now - rec.last_seen) > grace_period
        ]
        for tid in stale:
            del self._store[tid]

    def all_records(self) -> Dict[int, TrajectoryRecord]:
        return dict(self._store)

    def active_count(self) -> int:
        return len(self._store)
