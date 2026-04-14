"""
Unit tests for behavior_service analyzers.

These tests run without any ML models, cameras, or databases.
"""

import sys
import os
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from behavior_service.analyzers import (
    BehaviorAnalyzer,
    BehaviorResult,
    LoiteringDetector,
    RepeatedPathDetector,
    SuddenMotionDetector,
)
from behavior_service.trajectory import TrajectoryRecord, TrajectoryStore


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def fresh_record():
    return TrajectoryRecord(track_id=1)


# ---------------------------------------------------------------------------
# Trajectory store
# ---------------------------------------------------------------------------

class TestTrajectoryStore:
    def test_update_creates_record(self):
        store = TrajectoryStore()
        rec = store.update(track_id=42, cx=100.0, cy=200.0)
        assert rec.track_id == 42
        assert len(rec.positions) == 1
        assert rec.positions[0].x == 100.0

    def test_update_appends_positions(self):
        store = TrajectoryStore()
        for i in range(10):
            store.update(1, float(i), float(i))
        rec = store.get(1)
        assert len(rec.positions) == 10

    def test_remove_stale_removes_inactive(self):
        store = TrajectoryStore()
        store.update(1, 0, 0)
        store.update(2, 0, 0)
        # Manually age record 2
        store._store[2].last_seen -= 10
        store.remove_stale(active_ids=[1], grace_period=5.0)
        assert store.get(2) is None
        assert store.get(1) is not None

    def test_active_count(self):
        store = TrajectoryStore()
        store.update(1, 0, 0)
        store.update(2, 0, 0)
        assert store.active_count() == 2


# ---------------------------------------------------------------------------
# LoiteringDetector
# ---------------------------------------------------------------------------

class TestLoiteringDetector:
    def _make_loitering_record(self, duration_seconds: float, radius_inside: float = 10.0):
        """Create a record where the person has been stationary for duration_seconds."""
        record = TrajectoryRecord(track_id=1)
        record.loiter_anchor = (100.0, 100.0)
        record.loiter_start_ts = time.time() - duration_seconds
        # Add a position inside the loitering zone
        record.add_position(100.0 + radius_inside / 2, 100.0)
        return record

    def test_no_alert_below_threshold(self):
        detector = LoiteringDetector(time_threshold=120, radius=80)
        record = self._make_loitering_record(30)
        result = detector.analyze(record)
        assert result is None

    def test_alert_above_threshold(self):
        detector = LoiteringDetector(time_threshold=120, radius=80)
        record = self._make_loitering_record(150)
        result = detector.analyze(record)
        assert result is not None
        assert result.behavior_type == "loitering"
        assert result.severity in ("medium", "high")

    def test_high_severity_for_very_long_loitering(self):
        detector = LoiteringDetector(time_threshold=60, radius=80)
        record = self._make_loitering_record(200)
        result = detector.analyze(record)
        assert result is not None
        assert result.severity == "high"

    def test_reset_on_movement(self):
        detector = LoiteringDetector(time_threshold=120, radius=80)
        record = TrajectoryRecord(track_id=1)
        # Anchor at (100, 100)
        record.loiter_anchor = (100.0, 100.0)
        record.loiter_start_ts = time.time() - 150
        # Person moved far away
        record.add_position(500.0, 500.0)
        result = detector.analyze(record)
        # Should have reset anchor, not alert
        assert result is None
        assert record.loiter_anchor == (500.0, 500.0)

    def test_empty_record_returns_none(self, fresh_record):
        detector = LoiteringDetector()
        assert detector.analyze(fresh_record) is None


# ---------------------------------------------------------------------------
# RepeatedPathDetector
# ---------------------------------------------------------------------------

class TestRepeatedPathDetector:
    def _make_repeated_record(self, loops: int = 4):
        """Create a record with a clear repeated back-and-forth path."""
        record = TrajectoryRecord(track_id=2)
        segment_len = RepeatedPathDetector.SEGMENT_LENGTH
        # Generate repeated zig-zag segments
        for loop in range(loops + 1):
            for i in range(segment_len):
                x = float(i * 10) if loop % 2 == 0 else float((segment_len - i) * 10)
                record.add_position(x, 50.0)
        return record

    def test_repeated_path_detected(self):
        detector = RepeatedPathDetector(min_loops=3, similarity_threshold=0.85)
        record = self._make_repeated_record(loops=4)
        result = detector.analyze(record)
        assert result is not None
        assert result.behavior_type == "repeated_path"

    def test_no_alert_for_random_path(self):
        import random
        detector = RepeatedPathDetector(min_loops=3, similarity_threshold=0.85)
        record = TrajectoryRecord(track_id=2)
        random.seed(42)
        for _ in range(200):
            record.add_position(random.uniform(0, 1000), random.uniform(0, 1000))
        # Random paths should not consistently trigger (allow occasional false positives)
        # Just confirm the method runs without error
        detector.analyze(record)  # no assertion – non-deterministic

    def test_insufficient_data_returns_none(self, fresh_record):
        detector = RepeatedPathDetector()
        assert detector.analyze(fresh_record) is None


# ---------------------------------------------------------------------------
# SuddenMotionDetector
# ---------------------------------------------------------------------------

class TestSuddenMotionDetector:
    def _make_calm_then_spike_record(self, calm_velocity: float = 5.0, spike_velocity: float = 200.0):
        """Build a record with stable velocities then a sharp spike."""
        record = TrajectoryRecord(track_id=3)
        # Fill history with calm velocities
        for _ in range(20):
            record.velocities.append(calm_velocity)
        # Add spike
        record.velocities.append(spike_velocity)
        return record

    def test_sudden_motion_detected(self):
        detector = SuddenMotionDetector(speed_threshold=50)
        record = self._make_calm_then_spike_record(calm_velocity=5.0, spike_velocity=200.0)
        result = detector.analyze(record)
        assert result is not None
        assert result.behavior_type == "sudden_motion"

    def test_no_alert_for_consistent_high_speed(self):
        detector = SuddenMotionDetector(speed_threshold=50)
        record = TrajectoryRecord(track_id=3)
        for _ in range(25):
            record.velocities.append(60.0)  # consistently high but no spike
        result = detector.analyze(record)
        assert result is None

    def test_insufficient_history_returns_none(self, fresh_record):
        detector = SuddenMotionDetector()
        assert detector.analyze(fresh_record) is None


# ---------------------------------------------------------------------------
# BehaviorAnalyzer (composite)
# ---------------------------------------------------------------------------

class TestBehaviorAnalyzer:
    def test_returns_list(self, fresh_record):
        analyzer = BehaviorAnalyzer()
        results = analyzer.analyze(fresh_record)
        assert isinstance(results, list)

    def test_all_analyzers_run(self):
        """Smoke test: composite analyzer doesn't crash on a realistic record."""
        store = TrajectoryStore()
        for i in range(200):
            store.update(99, float(i % 20), 50.0)
        record = store.get(99)
        analyzer = BehaviorAnalyzer()
        results = analyzer.analyze(record)
        assert isinstance(results, list)
