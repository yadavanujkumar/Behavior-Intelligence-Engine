"""
Integration tests for the FastAPI endpoints.

Uses TestClient with mocked pipeline + DB so no ML models or DB are needed.
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from unittest.mock import patch, MagicMock


def make_mock_pipeline():
    """Return a mock Pipeline with sensible defaults."""
    mock = MagicMock()
    mock.get_alerts.return_value = []
    mock.get_stats.return_value = {
        "total_alerts": 0,
        "active_tracks": 0,
        "alerts_by_type": {},
        "alerts_by_severity": {},
        "uptime_seconds": 10.0,
        "fps": 25.0,
        "frame_count": 250,
    }
    mock.get_latest_frame.return_value = None
    return mock


# Build a fake database.models module to satisfy imports
def _make_db_mock():
    db_mock = MagicMock()
    db_mock.init_db = MagicMock(return_value=None)
    db_mock.get_db = MagicMock(return_value=iter([]))
    db_mock.Alert = MagicMock()
    db_mock.BehaviorEvent = MagicMock()
    db_mock.TrackingLog = MagicMock()
    return db_mock


@pytest.fixture(scope="module")
def client():
    mock_pipeline_instance = make_mock_pipeline()
    db_mock = _make_db_mock()

    # Patch all heavy / unavailable modules before any app import
    with patch.dict("sys.modules", {
        "ultralytics": MagicMock(),
        "deep_sort_realtime": MagicMock(),
        "deep_sort_realtime.deepsort_tracker": MagicMock(),
        "torch": MagicMock(),
        "cv2": MagicMock(),
        "openai": MagicMock(),
        "psycopg2": MagicMock(),
        "psycopg2.extensions": MagicMock(),
        "sqlalchemy": MagicMock(),
        "sqlalchemy.orm": MagicMock(),
        "database": MagicMock(),
        "database.models": db_mock,
    }):
        # Reload api_gateway.main fresh under mocked environment
        if "api_gateway.main" in sys.modules:
            del sys.modules["api_gateway.main"]
        if "api_gateway.pipeline" in sys.modules:
            del sys.modules["api_gateway.pipeline"]

        with patch("api_gateway.pipeline.pipeline", mock_pipeline_instance):
            from fastapi.testclient import TestClient
            from api_gateway.main import app
            with TestClient(app, raise_server_exceptions=True) as c:
                yield c


class TestHealthEndpoint:
    def test_root_returns_ok(self, client):
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "Behavior Intelligence Engine" in data["service"]


class TestStatsEndpoint:
    def test_stats_returns_valid_schema(self, client):
        response = client.get("/stats")
        assert response.status_code == 200
        data = response.json()
        assert "total_alerts" in data
        assert "active_tracks" in data
        assert "uptime_seconds" in data

    def test_stats_values_are_numeric(self, client):
        response = client.get("/stats")
        data = response.json()
        assert isinstance(data["total_alerts"], int)
        assert isinstance(data["uptime_seconds"], (int, float))


class TestAlertsEndpoint:
    def test_alerts_returns_list(self, client):
        response = client.get("/alerts")
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_alerts_limit_param(self, client):
        response = client.get("/alerts?limit=10")
        assert response.status_code == 200

    def test_alerts_invalid_limit(self, client):
        response = client.get("/alerts?limit=0")
        assert response.status_code == 422  # Pydantic validation error
