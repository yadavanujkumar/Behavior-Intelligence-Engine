# 🔍 Behavior Intelligence Engine

> A production-ready, AI-powered real-time surveillance system that detects
> suspicious human behavior from video streams using computer vision, deep
> learning tracking, and temporal behavior analysis.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                        VIDEO SOURCE                                  │
│           (Webcam / CCTV / RTSP / Video File)                       │
└────────────────────────────┬────────────────────────────────────────┘
                             │ OpenCV frames
                             ▼
┌────────────────────────────────────────────────────────────────────┐
│                    DETECTION SERVICE                                │
│          YOLOv8 (Ultralytics) – person detection                   │
│          Returns: bounding boxes + confidence scores               │
└────────────────────────────┬───────────────────────────────────────┘
                             │ Detections
                             ▼
┌────────────────────────────────────────────────────────────────────┐
│                    TRACKING SERVICE                                 │
│          DeepSORT – multi-object tracking with ReID                │
│          Returns: confirmed TrackedPerson objects with stable IDs  │
└────────────────────────────┬───────────────────────────────────────┘
                             │ TrackedPersons
                             ▼
┌────────────────────────────────────────────────────────────────────┐
│                    BEHAVIOR SERVICE                                 │
│  ┌─────────────────┐ ┌──────────────────┐ ┌──────────────────┐    │
│  │LoiteringDetector│ │RepeatedPathDetect│ │SuddenMotionDetect│    │
│  └────────┬────────┘ └────────┬─────────┘ └────────┬─────────┘    │
│           └──────────────────▼──────────────────────┘              │
│                    BehaviorResult events                            │
│                    + HeatmapGenerator                               │
└────────────────────────────┬───────────────────────────────────────┘
                             │ BehaviorResults
                             ▼
┌────────────────────────────────────────────────────────────────────┐
│                    ALERT SERVICE                                    │
│          AlertGenerator with per-ID cooldown                       │
│          Rule-based templates + optional OpenAI LLM enrichment     │
│          Returns: structured Alert objects                         │
└────────────────────────────┬───────────────────────────────────────┘
                             │ Alerts
                             ▼
┌────────────────────────────────────────────────────────────────────┐
│                    API GATEWAY (FastAPI)                            │
│  GET /video_feed           – MJPEG live stream                     │
│  GET /video_feed/heatmap   – MJPEG heatmap overlay                 │
│  GET /alerts               – real-time alert queue                 │
│  PATCH /alerts/{id}/ack    – acknowledge an alert                  │
│  GET /stats                – system statistics                     │
│  GET /db/alerts            – persisted alerts (PostgreSQL)         │
│  GET /db/tracking_logs     – raw tracking logs                     │
│  GET /db/behavior_events   – behavior event history                │
└────────────────────────────┬───────────────────────────────────────┘
                             │ REST/MJPEG
                             ▼
┌────────────────────────────────────────────────────────────────────┐
│                    REACT DASHBOARD                                  │
│  • Live video panel (normal / heatmap toggle)                      │
│  • Real-time alerts panel with severity filter + ACK               │
│  • KPI stats cards (active tracks, alerts, FPS, uptime)            │
│  • Bar + pie charts (alerts by type and severity)                  │
└────────────────────────────────────────────────────────────────────┘
                             │
                             ▼
┌────────────────────────────────────────────────────────────────────┐
│                    PostgreSQL 15                                    │
│  Tables: tracking_logs | behavior_events | alerts                  │
└────────────────────────────────────────────────────────────────────┘
```

---

## Project Structure

```
Behavior-Intelligence-Engine/
├── detection_service/          # YOLOv8 person detection
│   ├── detector.py
│   ├── requirements.txt
│   └── Dockerfile
├── tracking_service/           # DeepSORT multi-object tracking
│   ├── tracker.py
│   ├── requirements.txt
│   └── Dockerfile
├── behavior_service/           # Trajectory analysis & behavior detection
│   ├── analyzers.py            # LoiteringDetector, RepeatedPathDetector, SuddenMotionDetector
│   ├── trajectory.py           # TrajectoryStore & TrajectoryRecord
│   ├── heatmap.py              # Movement heatmap generator
│   ├── requirements.txt
│   └── Dockerfile
├── alert_service/              # Alert generation with LLM enrichment
│   ├── alert_generator.py
│   ├── requirements.txt
│   └── Dockerfile
├── api_gateway/                # FastAPI server (all services orchestrated here)
│   ├── main.py                 # FastAPI app + MJPEG endpoints
│   ├── pipeline.py             # Background processing pipeline
│   ├── schemas.py              # Pydantic request/response models
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/                   # React + Tailwind CSS dashboard
│   ├── src/
│   │   ├── App.js
│   │   ├── index.js
│   │   └── components/
│   │       ├── VideoFeed.js
│   │       ├── AlertsPanel.js
│   │       ├── StatsPanel.js
│   │       └── BehaviorChart.js
│   ├── public/index.html
│   ├── package.json
│   ├── tailwind.config.js
│   ├── nginx.conf
│   └── Dockerfile
├── database/
│   ├── models.py               # SQLAlchemy ORM models
│   ├── init.sql                # PostgreSQL initialisation
│   └── __init__.py
├── config/
│   ├── settings.py             # Centralised configuration (env vars)
│   ├── logger.py               # Rotating file + console logger
│   └── .env.example            # Template for environment variables
├── tests/
│   ├── test_behavior_analyzers.py
│   ├── test_alert_generator.py
│   └── test_api.py
├── logs/                       # Runtime log output (git-ignored)
├── docker-compose.yml
├── .gitignore
└── README.md
```

---

## Quick Start (Docker – Recommended)

### Prerequisites

- Docker ≥ 24 and Docker Compose ≥ 2.20
- A webcam connected at `/dev/video0` **or** a video file path

### 1 – Clone & configure

```bash
git clone https://github.com/yadavanujkumar/Behavior-Intelligence-Engine.git
cd Behavior-Intelligence-Engine

# Copy and edit the environment file
cp config/.env.example .env
```

Edit `.env` to set:

| Variable | Description |
|---|---|
| `VIDEO_SOURCE` | `0` for webcam, or path/URL to a file/RTSP stream |
| `OPENAI_API_KEY` | Optional – enables LLM-enriched alert messages |
| `LOITERING_TIME_THRESHOLD` | Seconds before loitering is flagged (default: 120) |
| `SPEED_THRESHOLD` | Pixels/second for sudden motion detection (default: 50) |

### 2 – Start all services

```bash
docker-compose up --build
```

> **Note:** If you have no webcam, comment out the `devices:` block in
> `docker-compose.yml` and set `VIDEO_SOURCE` to a video file path.
> A demo video is not bundled to keep the repository lightweight; any
> `.mp4` file with people walking can be used.

### 3 – Access the dashboard

| Service | URL |
|---|---|
| React Dashboard | http://localhost:3000 |
| FastAPI (Swagger UI) | http://localhost:8000/docs |
| Live Video Feed | http://localhost:8000/video_feed |
| Heatmap Feed | http://localhost:8000/video_feed/heatmap |

---

## Running Locally Without Docker

### Backend

```bash
# Create and activate a virtual environment
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate

# Install all Python dependencies
pip install -r api_gateway/requirements.txt

# Export environment variables (or copy .env.example to .env)
export VIDEO_SOURCE=0
export DATABASE_URL=postgresql://bie_user:bie_pass@localhost:5432/behavior_intelligence

# Start PostgreSQL separately, then:
uvicorn api_gateway.main:app --host 0.0.0.0 --port 8000 --reload
```

### Frontend

```bash
cd frontend
npm install
REACT_APP_API_URL=http://localhost:8000 npm start
```

---

## Running Tests

```bash
pip install pytest numpy fastapi pydantic httpx
python -m pytest tests/ -v
```

---

## API Reference

### `GET /`
Health check. Returns `{"status": "ok", ...}`.

### `GET /video_feed`
MJPEG live video stream with bounding boxes and track IDs overlaid.
Consume directly in an `<img>` tag.

### `GET /video_feed/heatmap`
Same as `/video_feed` but with the movement heatmap overlay blended in.

### `GET /alerts`
**Query params:** `limit` (int, 1–500), `severity` (low/medium/high)

Returns the most recent in-memory alerts as a JSON array:
```json
[{
  "track_id": 3,
  "behavior_type": "loitering",
  "severity": "high",
  "confidence": 0.92,
  "message": "Person ID 3 has been loitering near entrance for 2 minutes...",
  "camera_id": "cam0",
  "details": {"duration_seconds": 130, "anchor_x": 320.0, "anchor_y": 240.0},
  "timestamp": 1713082200.5,
  "acknowledged": false
}]
```

### `PATCH /alerts/{index}/ack`
Acknowledge an alert. Body: `{"acknowledged": true}`.

### `GET /stats`
```json
{
  "total_alerts": 12,
  "active_tracks": 3,
  "alerts_by_type": {"loitering": 7, "repeated_path": 3, "sudden_motion": 2},
  "alerts_by_severity": {"high": 4, "medium": 6, "low": 2},
  "uptime_seconds": 3600.0,
  "cameras": ["cam0"]
}
```

---

## Behavior Detection Logic

### Loitering
A person is considered loitering when they remain within a configurable
**radius** (default: 80 px) of an anchor point for longer than the
**time threshold** (default: 120 s).  The anchor resets whenever the person
moves beyond the radius.  Severity escalates to `high` when time doubles.

### Repeated Path Traversal
The trajectory is divided into fixed-length segments (20 positions each).
The latest segment is compared against all historical segments using
normalised mean Euclidean distance.  When ≥ N similar segments are found
(default: 3 loops), an alert is raised.

### Sudden Motion
A rolling mean of velocity (pixels/second) is maintained.  When the latest
velocity exceeds both the **absolute speed threshold** (default: 50 px/s)
and the rolling mean by at least 50% of the threshold, a sudden-motion
alert is raised.

---

## Configuration Reference

All settings are in `config/settings.py` and can be overridden via environment
variables or the `.env` file.

| Variable | Default | Description |
|---|---|---|
| `DETECTION_MODEL` | `yolov8n.pt` | YOLOv8 variant (n/s/m/l/x) |
| `DETECTION_CONFIDENCE` | `0.5` | Min detection confidence |
| `DETECTION_DEVICE` | `cpu` | `cpu` or `cuda` |
| `LOITERING_TIME_THRESHOLD` | `120` | Seconds before loitering alert |
| `LOITERING_RADIUS` | `80` | Pixel radius for loitering zone |
| `SPEED_THRESHOLD` | `50` | px/s threshold for sudden motion |
| `TRAJECTORY_HISTORY` | `100` | Max positions per tracked ID |
| `REPEATED_PATH_MIN_LOOPS` | `3` | Min route repetitions to alert |
| `OPENAI_API_KEY` | _(empty)_ | Enables LLM alert narratives |
| `ALERT_COOLDOWN` | `30` | Seconds between same-type alerts per ID |
| `VIDEO_SOURCE` | `0` | Webcam index, file path, or RTSP URL |
| `FRAME_FPS` | `30` | Target capture FPS |

---

## Tech Stack

| Layer | Technology |
|---|---|
| Object Detection | YOLOv8 (Ultralytics) |
| Multi-Object Tracking | DeepSORT with MobileNet ReID |
| Backend API | FastAPI + Uvicorn |
| Video Processing | OpenCV |
| Deep Learning | PyTorch |
| LLM Alerts | OpenAI GPT API |
| Database | PostgreSQL 15 + SQLAlchemy |
| Frontend | React 18 + Tailwind CSS + Recharts |
| Containerisation | Docker + Docker Compose |

---

## Extending the System

### Adding a new behavior detector
1. Create a class with an `analyze(record: TrajectoryRecord) -> Optional[BehaviorResult]` method in `behavior_service/analyzers.py`.
2. Register it in `BehaviorAnalyzer.__init__`.

### Swapping in an ML model (LSTM / Autoencoder)
The `BehaviorAnalyzer` class is modular.  Replace the rule-based analyzers with
a trained sequence model – the pipeline contract (input: `TrajectoryRecord`,
output: `List[BehaviorResult]`) stays the same.

### Adding a new camera
Set `VIDEO_SOURCE` to the RTSP URL or device path and redeploy.  Each pipeline
instance handles one source; run multiple containers for multi-camera setups.

---

## License

MIT – see [LICENSE](LICENSE).
