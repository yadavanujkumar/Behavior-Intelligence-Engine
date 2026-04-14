"""Unit tests for the alert generator / cooldown logic."""

import sys, os, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from alert_service.alert_generator import Alert, AlertGenerator, _render_template
from behavior_service.analyzers import BehaviorResult


def make_result(track_id=1, behavior_type="loitering", severity="medium"):
    return BehaviorResult(
        track_id=track_id,
        behavior_type=behavior_type,
        severity=severity,
        confidence=0.9,
        details={"duration_seconds": 130, "anchor_x": 100.0, "anchor_y": 200.0, "radius": 80},
    )


class TestAlertGenerator:
    def test_generates_alert(self):
        gen = AlertGenerator(cooldown=0)
        result = make_result()
        alert = gen.generate(result)
        assert alert is not None
        assert alert.track_id == 1
        assert alert.behavior_type == "loitering"
        assert len(alert.message) > 10

    def test_cooldown_suppresses_duplicate(self):
        gen = AlertGenerator(cooldown=60)
        result = make_result()
        alert1 = gen.generate(result)
        alert2 = gen.generate(result)
        assert alert1 is not None
        assert alert2 is None   # suppressed by cooldown

    def test_cooldown_per_behavior_type(self):
        gen = AlertGenerator(cooldown=60)
        loiter = make_result(behavior_type="loitering")
        motion = make_result(behavior_type="sudden_motion")
        a1 = gen.generate(loiter)
        a2 = gen.generate(motion)  # different type – should not be suppressed
        assert a1 is not None
        assert a2 is not None

    def test_cooldown_expires(self):
        gen = AlertGenerator(cooldown=1)
        result = make_result()
        gen.generate(result)
        time.sleep(1.1)
        alert = gen.generate(result)
        assert alert is not None  # cooldown expired


class TestRenderTemplate:
    def test_loitering_template(self):
        msg = _render_template(
            "loitering", 5, "high",
            {"duration_seconds": 200, "anchor_x": 50, "anchor_y": 60, "radius": 80},
        )
        assert "Person ID 5" in msg
        assert "200" in msg

    def test_repeated_path_template(self):
        msg = _render_template(
            "repeated_path", 7, "medium",
            {"loop_count": 4, "segment_length": 20, "similarity_threshold": 0.85},
        )
        assert "Person ID 7" in msg
        assert "4" in msg

    def test_sudden_motion_template(self):
        msg = _render_template(
            "sudden_motion", 3, "high",
            {"current_velocity": 300.0, "mean_velocity": 10.0, "velocity_spike": 290.0, "threshold": 50},
        )
        assert "Person ID 3" in msg

    def test_unknown_type_fallback(self):
        msg = _render_template("unknown_behavior", 1, "low", {})
        assert "Person ID 1" in msg
