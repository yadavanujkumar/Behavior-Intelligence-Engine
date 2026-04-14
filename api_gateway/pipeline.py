"""
Core processing pipeline that ties all services together.

The Pipeline class is a singleton that:
  1. Captures frames from the video source.
  2. Runs person detection (YOLOv8).
  3. Updates the tracker (DeepSORT).
  4. Updates trajectories and runs behavior analysis.
  5. Generates alerts and persists everything to the database.
  6. Provides the latest annotated frame for the MJPEG video feed.

It runs in a background thread so that the FastAPI server stays responsive.
"""

import threading
import time
from typing import List, Optional

import cv2
import numpy as np

from alert_service.alert_generator import Alert, AlertGenerator
from behavior_service.analyzers import BehaviorAnalyzer
from behavior_service.heatmap import HeatmapGenerator
from behavior_service.trajectory import TrajectoryStore
from config.logger import get_logger
from config.settings import cfg
from detection_service.detector import PersonDetector
from tracking_service.tracker import DeepSORTTracker

logger = get_logger(__name__)


class Pipeline:
    """
    Orchestrates the end-to-end detection → tracking → analysis → alert pipeline.

    Thread model: one background daemon thread calls `_run_loop()` continuously.
    The FastAPI route handlers read shared state (latest_frame, alert_queue, stats)
    without blocking the pipeline loop.
    """

    def __init__(self):
        self._lock = threading.Lock()

        # Services
        self.detector: Optional[PersonDetector] = None
        self.tracker: Optional[DeepSORTTracker] = None
        self.trajectory_store = TrajectoryStore()
        self.behavior_analyzer = BehaviorAnalyzer()
        self.alert_generator = AlertGenerator()

        # Video capture
        self._cap: Optional[cv2.VideoCapture] = None
        self.frame_width = cfg.frame_width
        self.frame_height = cfg.frame_height

        # Shared state (read by API routes)
        self._latest_frame: Optional[np.ndarray] = None
        self._latest_frame_heatmap: Optional[np.ndarray] = None
        self._alert_queue: List[Alert] = []
        self._stats = {
            "total_alerts": 0,
            "active_tracks": 0,
            "alerts_by_type": {},
            "alerts_by_severity": {},
            "frame_count": 0,
            "fps": 0.0,
        }
        self._start_time = time.time()
        self._heatmap: Optional[HeatmapGenerator] = None

        # Control
        self._running = False
        self._thread: Optional[threading.Thread] = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Initialise services and start the processing thread."""
        logger.info("Starting BIE pipeline …")
        self._init_services()
        self._open_capture()
        self._running = True
        self._thread = threading.Thread(
            target=self._run_loop, name="pipeline", daemon=True
        )
        self._thread.start()
        logger.info("Pipeline thread started.")

    def stop(self) -> None:
        logger.info("Stopping pipeline …")
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
        if self._cap:
            self._cap.release()
        logger.info("Pipeline stopped.")

    # ------------------------------------------------------------------
    # Initialisation helpers
    # ------------------------------------------------------------------

    def _init_services(self) -> None:
        """Load ML models and create service instances."""
        try:
            self.detector = PersonDetector()
        except Exception as exc:
            logger.error("Failed to initialise detector: %s", exc)
            self.detector = None

        try:
            self.tracker = DeepSORTTracker()
        except Exception as exc:
            logger.error("Failed to initialise tracker: %s", exc)
            self.tracker = None

    def _open_capture(self) -> None:
        """Open the video source (webcam, file, or RTSP URL)."""
        source = cfg.video_source
        # Convert '0' → 0 (integer index for webcam)
        try:
            source = int(source)
        except (ValueError, TypeError):
            pass

        self._cap = cv2.VideoCapture(source)
        if not self._cap.isOpened():
            logger.warning(
                "Could not open video source '%s'. Pipeline will retry.", source
            )

        self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.frame_width)
        self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.frame_height)
        self._cap.set(cv2.CAP_PROP_FPS, cfg.frame_fps)

        self._heatmap = HeatmapGenerator(
            width=int(self._cap.get(cv2.CAP_PROP_FRAME_WIDTH)) or self.frame_width,
            height=int(self._cap.get(cv2.CAP_PROP_FRAME_HEIGHT)) or self.frame_height,
        )

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------

    def _run_loop(self) -> None:
        """Continuously process frames until stopped."""
        fps_counter = 0
        fps_timer = time.time()

        while self._running:
            if not self._cap or not self._cap.isOpened():
                time.sleep(0.5)
                self._open_capture()
                continue

            ret, frame = self._cap.read()
            if not ret:
                logger.warning("Frame read failed – source may have ended; looping.")
                self._cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                time.sleep(0.05)
                continue

            self._process_frame(frame)

            fps_counter += 1
            elapsed = time.time() - fps_timer
            if elapsed >= 1.0:
                fps = fps_counter / elapsed
                fps_counter = 0
                fps_timer = time.time()
                with self._lock:
                    self._stats["fps"] = round(fps, 1)

    def _process_frame(self, frame: np.ndarray) -> None:
        """Run the full pipeline on a single frame."""
        annotated = frame.copy()

        # 1. Detect persons
        detections = []
        if self.detector:
            try:
                detections = self.detector.detect(frame)
            except Exception as exc:
                logger.error("Detection error: %s", exc)

        # 2. Track persons
        tracks = []
        if self.tracker and detections is not None:
            try:
                tracks = self.tracker.update(detections, frame)
            except Exception as exc:
                logger.error("Tracking error: %s", exc)

        # 3. Update trajectories + run behavior analysis
        alerts_this_frame: List[Alert] = []
        active_ids = [t.track_id for t in tracks]

        for track in tracks:
            # Draw track on annotated frame
            x1, y1, x2, y2 = (int(v) for v in track.bbox)
            cv2.rectangle(annotated, (x1, y1), (x2, y2), (255, 100, 0), 2)
            cv2.putText(
                annotated,
                f"ID:{track.track_id}",
                (x1, max(y1 - 8, 0)),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 100, 0), 2,
            )

            # Update trajectory
            rec = self.trajectory_store.update(
                track.track_id, track.centroid[0], track.centroid[1]
            )

            # Analyze behavior
            behavior_results = self.behavior_analyzer.analyze(rec)

            for result in behavior_results:
                alert = self.alert_generator.generate(result)
                if alert:
                    alerts_this_frame.append(alert)
                    # Overlay alert label on frame
                    cv2.putText(
                        annotated,
                        f"! {result.behavior_type}",
                        (x1, y2 + 16),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2,
                    )

        # Purge stale trajectory records
        self.trajectory_store.remove_stale(active_ids)

        # 4. Update heatmap
        if self._heatmap:
            self._heatmap.update([(t.centroid[0], t.centroid[1]) for t in tracks])
            heatmap_frame = self._heatmap.render_overlay(annotated)
        else:
            heatmap_frame = annotated

        # 5. Update shared state
        with self._lock:
            self._latest_frame = annotated
            self._latest_frame_heatmap = heatmap_frame
            self._alert_queue.extend(alerts_this_frame)
            # Keep last 500 alerts in memory
            if len(self._alert_queue) > 500:
                self._alert_queue = self._alert_queue[-500:]
            self._stats["active_tracks"] = len(tracks)
            self._stats["frame_count"] += 1
            self._stats["total_alerts"] += len(alerts_this_frame)

            for alert in alerts_this_frame:
                atype = alert.behavior_type
                sev = alert.severity
                self._stats["alerts_by_type"][atype] = (
                    self._stats["alerts_by_type"].get(atype, 0) + 1
                )
                self._stats["alerts_by_severity"][sev] = (
                    self._stats["alerts_by_severity"].get(sev, 0) + 1
                )

    # ------------------------------------------------------------------
    # Public accessors (thread-safe reads)
    # ------------------------------------------------------------------

    def get_latest_frame(self, heatmap: bool = False) -> Optional[np.ndarray]:
        with self._lock:
            if heatmap:
                return self._latest_frame_heatmap.copy() if self._latest_frame_heatmap is not None else None
            return self._latest_frame.copy() if self._latest_frame is not None else None

    def get_alerts(self, limit: int = 50, severity: Optional[str] = None) -> List[Alert]:
        with self._lock:
            alerts = list(reversed(self._alert_queue))
            if severity:
                alerts = [a for a in alerts if a.severity == severity]
            return alerts[:limit]

    def get_stats(self) -> dict:
        with self._lock:
            stats = dict(self._stats)
            stats["uptime_seconds"] = round(time.time() - self._start_time, 1)
            return stats

    def acknowledge_alert(self, alert_index: int) -> bool:
        with self._lock:
            alerts = list(reversed(self._alert_queue))
            if 0 <= alert_index < len(alerts):
                alerts[alert_index].acknowledged = True
                return True
            return False


# Singleton pipeline instance
pipeline = Pipeline()
