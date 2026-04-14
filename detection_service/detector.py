"""
YOLOv8-based human detector.

Wraps the Ultralytics YOLO model and exposes a simple `detect(frame)` API
that returns a list of Detection namedtuples (bbox, confidence).

Architecture note:
  The detector is intentionally stateless – it processes one frame at a time.
  Tracking state lives in the tracking_service.
"""

from dataclasses import dataclass
from typing import List, Optional, Tuple

import cv2
import numpy as np

from config.logger import get_logger
from config.settings import cfg

logger = get_logger(__name__)


@dataclass
class Detection:
    """A single person detection in a frame."""

    bbox: Tuple[float, float, float, float]  # (x1, y1, x2, y2) pixels
    confidence: float
    class_id: int = 0  # YOLO class 0 = person


class PersonDetector:
    """
    Loads a YOLOv8 model and runs inference on BGR frames.

    Parameters
    ----------
    model_path : str
        Path or Ultralytics model identifier (e.g. 'yolov8n.pt').
    confidence : float
        Minimum detection confidence to keep.
    device : str
        Torch device string ('cpu', 'cuda', 'cuda:0', etc.).
    """

    PERSON_CLASS_ID = 0  # COCO class ID for 'person'

    def __init__(
        self,
        model_path: str = cfg.detection_model,
        confidence: float = cfg.detection_confidence,
        device: str = cfg.detection_device,
    ):
        self.confidence = confidence
        self.device = device
        self._model = None
        self._load_model(model_path)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _load_model(self, model_path: str) -> None:
        """Lazy-load YOLOv8 model; catch import errors gracefully."""
        try:
            from ultralytics import YOLO  # imported here to keep the module
                                           # importable even without GPU env

            logger.info("Loading YOLOv8 model: %s on device: %s", model_path, self.device)
            self._model = YOLO(model_path)
            self._model.to(self.device)
            logger.info("YOLOv8 model loaded successfully.")
        except ImportError as exc:
            logger.error("Ultralytics not installed: %s", exc)
            raise
        except Exception as exc:
            logger.error("Failed to load YOLO model '%s': %s", model_path, exc)
            raise

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def detect(self, frame: np.ndarray) -> List[Detection]:
        """
        Run person detection on a single BGR frame.

        Parameters
        ----------
        frame : np.ndarray
            OpenCV BGR image.

        Returns
        -------
        List[Detection]
            Detections filtered to 'person' class and above confidence threshold.
        """
        if self._model is None:
            logger.warning("Model not loaded; returning empty detections.")
            return []

        try:
            results = self._model.predict(
                source=frame,
                conf=self.confidence,
                classes=[self.PERSON_CLASS_ID],
                verbose=False,
                device=self.device,
            )
        except Exception as exc:
            logger.error("YOLO inference error: %s", exc)
            return []

        detections: List[Detection] = []
        for result in results:
            if result.boxes is None:
                continue
            for box in result.boxes:
                # box.xyxy shape: (1, 4) – convert to flat tuple
                x1, y1, x2, y2 = box.xyxy[0].cpu().numpy().tolist()
                conf = float(box.conf[0].cpu().numpy())
                detections.append(
                    Detection(
                        bbox=(x1, y1, x2, y2),
                        confidence=conf,
                        class_id=int(box.cls[0].cpu().numpy()),
                    )
                )

        logger.debug("Detected %d persons in frame.", len(detections))
        return detections

    def draw_detections(
        self,
        frame: np.ndarray,
        detections: List[Detection],
        color: Tuple[int, int, int] = (0, 255, 0),
        thickness: int = 2,
    ) -> np.ndarray:
        """Draw detection bounding boxes on a copy of the frame."""
        annotated = frame.copy()
        for det in detections:
            x1, y1, x2, y2 = (int(v) for v in det.bbox)
            cv2.rectangle(annotated, (x1, y1), (x2, y2), color, thickness)
            label = f"person {det.confidence:.2f}"
            cv2.putText(
                annotated,
                label,
                (x1, max(y1 - 5, 0)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                color,
                thickness,
            )
        return annotated
