"""
Rule-based behavior analyzers.

Each analyzer is a stateless function (or a small class) that receives a
TrajectoryRecord and returns a BehaviorResult if suspicious activity is
detected, or None if the person looks normal.

Design principle: analyzers are kept separate from the trajectory store so
that ML-based classifiers can be swapped in without changing the pipeline.

Detected behaviors:
  1. Loitering         – staying in a small area for longer than the threshold
  2. Repeated path     – traversing the same route multiple times
  3. Sudden motion     – velocity spike far above the moving average
"""

import math
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np

from behavior_service.trajectory import TrajectoryRecord
from config.settings import cfg


@dataclass
class BehaviorResult:
    """Outcome of a behavior analysis pass for one person."""

    track_id: int
    behavior_type: str          # 'loitering' | 'repeated_path' | 'sudden_motion'
    severity: str               # 'low' | 'medium' | 'high'
    confidence: float           # 0–1
    details: dict = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)


# ---------------------------------------------------------------------------
# 1. Loitering Detector
# ---------------------------------------------------------------------------

class LoiteringDetector:
    """
    Detects when a person stays within a fixed radius for longer than a
    configurable time threshold.

    Algorithm:
      - On each call, check whether the latest position is within RADIUS pixels
        of a stored anchor point.
      - If yes, accumulate time.  If no, reset the anchor.
      - When accumulated time exceeds THRESHOLD, emit a BehaviorResult.
    """

    def __init__(
        self,
        time_threshold: int = cfg.loitering_time_threshold,
        radius: int = cfg.loitering_radius,
    ):
        self.time_threshold = time_threshold
        self.radius = radius

    def analyze(self, record: TrajectoryRecord) -> Optional[BehaviorResult]:
        if not record.positions:
            return None

        latest = record.positions[-1]

        # -- Start or reset anchor --
        if record.loiter_anchor is None:
            record.loiter_anchor = (latest.x, latest.y)
            record.loiter_start_ts = latest.ts
            return None

        ax, ay = record.loiter_anchor
        dist = math.hypot(latest.x - ax, latest.y - ay)

        if dist <= self.radius:
            # Still within zone – check duration
            duration = latest.ts - record.loiter_start_ts
            if duration >= self.time_threshold:
                severity = (
                    "high" if duration >= self.time_threshold * 2
                    else "medium"
                )
                return BehaviorResult(
                    track_id=record.track_id,
                    behavior_type="loitering",
                    severity=severity,
                    confidence=min(1.0, duration / (self.time_threshold * 2)),
                    details={
                        "duration_seconds": round(duration, 1),
                        "anchor_x": round(ax, 1),
                        "anchor_y": round(ay, 1),
                        "radius": self.radius,
                    },
                )
        else:
            # Person moved outside zone – reset
            record.loiter_anchor = (latest.x, latest.y)
            record.loiter_start_ts = latest.ts

        return None


# ---------------------------------------------------------------------------
# 2. Repeated Path Detector
# ---------------------------------------------------------------------------

class RepeatedPathDetector:
    """
    Detects when a person repeatedly traverses the same spatial route.

    Algorithm:
      - Divide the trajectory history into equal-length segments.
      - Compute the pairwise Fréchet-like distance between the latest segment
        and all previous segments.
      - If REPEATED_PATH_MIN_LOOPS similar segments are found, flag.
    """

    SEGMENT_LENGTH = 20   # positions per segment

    def __init__(
        self,
        min_loops: int = cfg.repeated_path_min_loops,
        similarity_threshold: float = cfg.repeated_path_similarity,
    ):
        self.min_loops = min_loops
        self.similarity_threshold = similarity_threshold

    @staticmethod
    def _segment_similarity(seg_a: np.ndarray, seg_b: np.ndarray) -> float:
        """
        Compute similarity in [0, 1] between two equal-length path segments.
        Uses normalised mean Euclidean distance, scaled to the bounding box.
        """
        if len(seg_a) != len(seg_b) or len(seg_a) == 0:
            return 0.0

        dists = np.linalg.norm(seg_a - seg_b, axis=1)
        mean_dist = float(np.mean(dists))

        # Normalise by the diagonal of the bounding box of seg_a
        span = np.max(seg_a, axis=0) - np.min(seg_a, axis=0)
        diagonal = float(np.linalg.norm(span)) or 1.0
        normalised_dist = mean_dist / diagonal

        return max(0.0, 1.0 - normalised_dist)

    def analyze(self, record: TrajectoryRecord) -> Optional[BehaviorResult]:
        positions = list(record.positions)
        if len(positions) < self.SEGMENT_LENGTH * (self.min_loops + 1):
            # Not enough data yet
            return None

        pts = np.array([[p.x, p.y] for p in positions])

        # Extract all non-overlapping segments
        segments = [
            pts[i: i + self.SEGMENT_LENGTH]
            for i in range(0, len(pts) - self.SEGMENT_LENGTH + 1, self.SEGMENT_LENGTH)
        ]

        if len(segments) < 2:
            return None

        latest_seg = segments[-1]
        similar_count = 0

        for seg in segments[:-1]:
            sim = self._segment_similarity(latest_seg, seg)
            if sim >= self.similarity_threshold:
                similar_count += 1

        if similar_count >= self.min_loops - 1:
            return BehaviorResult(
                track_id=record.track_id,
                behavior_type="repeated_path",
                severity="medium",
                confidence=min(1.0, similar_count / self.min_loops),
                details={
                    "loop_count": similar_count + 1,
                    "segment_length": self.SEGMENT_LENGTH,
                    "similarity_threshold": self.similarity_threshold,
                },
            )

        return None


# ---------------------------------------------------------------------------
# 3. Sudden Motion Detector
# ---------------------------------------------------------------------------

class SuddenMotionDetector:
    """
    Detects abrupt, erratic movement by comparing the latest velocity against
    a rolling average.

    Algorithm:
      - Maintain a rolling window of velocities.
      - Raise an alert when the latest velocity exceeds the mean by
        SPEED_THRESHOLD pixels/second AND is above an absolute minimum.
    """

    MIN_HISTORY = 10  # minimum velocity samples before analysis

    def __init__(self, speed_threshold: float = cfg.speed_threshold):
        self.speed_threshold = speed_threshold

    def analyze(self, record: TrajectoryRecord) -> Optional[BehaviorResult]:
        velocities = list(record.velocities)
        if len(velocities) < self.MIN_HISTORY:
            return None

        mean_v = float(np.mean(velocities[:-1]))
        latest_v = velocities[-1]

        spike = latest_v - mean_v

        if latest_v > self.speed_threshold and spike > self.speed_threshold * 0.5:
            severity = "high" if spike > self.speed_threshold * 2 else "medium"
            return BehaviorResult(
                track_id=record.track_id,
                behavior_type="sudden_motion",
                severity=severity,
                confidence=min(1.0, spike / (self.speed_threshold * 3)),
                details={
                    "current_velocity": round(latest_v, 2),
                    "mean_velocity": round(mean_v, 2),
                    "velocity_spike": round(spike, 2),
                    "threshold": self.speed_threshold,
                },
            )

        return None


# ---------------------------------------------------------------------------
# Composite Analyzer
# ---------------------------------------------------------------------------

class BehaviorAnalyzer:
    """
    Runs all individual analyzers and aggregates results.

    This is the main entry point used by the pipeline.
    """

    def __init__(self):
        self.loitering = LoiteringDetector()
        self.repeated_path = RepeatedPathDetector()
        self.sudden_motion = SuddenMotionDetector()

    def analyze(self, record: TrajectoryRecord) -> List[BehaviorResult]:
        """Run all analyzers and return any triggered results."""
        results: List[BehaviorResult] = []
        for analyzer in (self.loitering, self.repeated_path, self.sudden_motion):
            result = analyzer.analyze(record)
            if result is not None:
                results.append(result)
        return results
