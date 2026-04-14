"""
DeepSORT-based multi-object tracker.

Wraps the deep_sort_realtime library to assign persistent IDs to detected
persons across frames.  The tracker is stateful – one Tracker instance should
be kept alive for the lifetime of a video stream.

Track lifecycle:
  - A track is "tentative" for the first N_INIT frames.
  - Once confirmed it receives a stable integer ID.
  - A track is deleted after MAX_AGE frames without a match.
"""

from dataclasses import dataclass
from typing import List, Optional, Tuple

import cv2
import numpy as np

from config.logger import get_logger
from config.settings import cfg
from detection_service.detector import Detection

logger = get_logger(__name__)


@dataclass
class TrackedPerson:
    """A single confirmed tracked individual in one frame."""

    track_id: int
    bbox: Tuple[float, float, float, float]  # (x1, y1, x2, y2)
    centroid: Tuple[float, float]            # (cx, cy)
    confidence: float
    is_confirmed: bool = True


class DeepSORTTracker:
    """
    Manages person tracking via DeepSORT.

    Parameters
    ----------
    max_age : int
        Frames to keep a lost track alive before deletion.
    n_init : int
        Frames required before a track is confirmed.
    max_cosine_dist : float
        Cosine distance threshold for ReID feature matching.
    """

    def __init__(
        self,
        max_age: int = cfg.deepsort_max_age,
        n_init: int = cfg.deepsort_n_init,
        max_cosine_dist: float = cfg.deepsort_max_cosine_dist,
    ):
        self.max_age = max_age
        self.n_init = n_init
        self.max_cosine_dist = max_cosine_dist
        self._tracker = None
        self._init_tracker()

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _init_tracker(self) -> None:
        """Instantiate the DeepSORT tracker."""
        try:
            from deep_sort_realtime.deepsort_tracker import DeepSort

            self._tracker = DeepSort(
                max_age=self.max_age,
                n_init=self.n_init,
                max_cosine_distance=self.max_cosine_dist,
                nn_budget=None,
                embedder="mobilenet",   # lightweight ReID embedder
                half=False,
                bgr=True,              # OpenCV frame format
                embedder_gpu=cfg.detection_device != "cpu",
            )
            logger.info("DeepSORT tracker initialised (max_age=%d, n_init=%d).", self.max_age, self.n_init)
        except ImportError as exc:
            logger.error("deep_sort_realtime not installed: %s", exc)
            raise

    @staticmethod
    def _det_to_ltrb(det: Detection) -> List:
        """
        Convert a Detection to the format expected by deep_sort_realtime:
          [[x1, y1, x2, y2], confidence, class_id]
        """
        x1, y1, x2, y2 = det.bbox
        return ([x1, y1, x2, y2], det.confidence, det.class_id)

    @staticmethod
    def _bbox_centroid(bbox: Tuple) -> Tuple[float, float]:
        x1, y1, x2, y2 = bbox
        return ((x1 + x2) / 2.0, (y1 + y2) / 2.0)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def update(
        self, detections: List[Detection], frame: np.ndarray
    ) -> List[TrackedPerson]:
        """
        Feed new detections for the current frame and return confirmed tracks.

        Parameters
        ----------
        detections : List[Detection]
            Raw detections from the person detector.
        frame : np.ndarray
            Current BGR frame (used by the ReID embedder).

        Returns
        -------
        List[TrackedPerson]
            All currently confirmed tracked persons.
        """
        if self._tracker is None:
            return []

        raw_dets = [self._det_to_ltrb(d) for d in detections]

        try:
            tracks = self._tracker.update_tracks(raw_dets, frame=frame)
        except Exception as exc:
            logger.error("DeepSORT update error: %s", exc)
            return []

        tracked_persons: List[TrackedPerson] = []
        for track in tracks:
            if not track.is_confirmed():
                continue
            ltrb = track.to_ltrb()
            x1, y1, x2, y2 = ltrb
            bbox = (float(x1), float(y1), float(x2), float(y2))
            centroid = self._bbox_centroid(bbox)
            tracked_persons.append(
                TrackedPerson(
                    track_id=int(track.track_id),
                    bbox=bbox,
                    centroid=centroid,
                    confidence=track.det_conf if track.det_conf else 1.0,
                )
            )

        logger.debug("Active tracks: %d", len(tracked_persons))
        return tracked_persons

    def draw_tracks(
        self,
        frame: np.ndarray,
        tracks: List[TrackedPerson],
        color: Tuple[int, int, int] = (255, 100, 0),
        thickness: int = 2,
    ) -> np.ndarray:
        """Annotate frame with track bounding boxes and IDs."""
        annotated = frame.copy()
        for t in tracks:
            x1, y1, x2, y2 = (int(v) for v in t.bbox)
            cv2.rectangle(annotated, (x1, y1), (x2, y2), color, thickness)
            label = f"ID:{t.track_id}"
            cv2.putText(
                annotated,
                label,
                (x1, max(y1 - 8, 0)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                color,
                thickness,
            )
        return annotated
