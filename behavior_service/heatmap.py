"""
Movement heatmap generator.

Accumulates centroid positions across all frames and renders a colour-coded
heatmap overlay that can be blended onto the video feed.
"""

import cv2
import numpy as np

from config.logger import get_logger

logger = get_logger(__name__)


class HeatmapGenerator:
    """
    Maintains an accumulation buffer and generates OpenCV heatmap overlays.

    Parameters
    ----------
    width, height : int
        Frame dimensions.
    decay_factor : float
        How quickly old heat fades per frame (0 = no decay, 1 = full reset).
    """

    def __init__(self, width: int, height: int, decay_factor: float = 0.002):
        self.width = width
        self.height = height
        self.decay_factor = decay_factor
        # Accumulation buffer (float32 for precision)
        self._buffer = np.zeros((height, width), dtype=np.float32)

    def update(self, points: list) -> None:
        """
        Add centroid points to the heatmap buffer.

        Parameters
        ----------
        points : list of (x, y) tuples
        """
        # Apply gentle decay to old heat
        self._buffer *= (1.0 - self.decay_factor)

        for x, y in points:
            cx, cy = int(round(x)), int(round(y))
            if 0 <= cx < self.width and 0 <= cy < self.height:
                # Gaussian splat – draw a small blob per person
                cv2.circle(self._buffer, (cx, cy), radius=20, color=1.0, thickness=-1)

    def render_overlay(
        self, frame: np.ndarray, alpha: float = 0.4
    ) -> np.ndarray:
        """
        Blend the heatmap onto the frame.

        Parameters
        ----------
        frame : np.ndarray
            BGR source frame.
        alpha : float
            Overlay opacity (0 = invisible, 1 = opaque).

        Returns
        -------
        np.ndarray
            Frame with heatmap blended in.
        """
        # Normalise buffer to [0, 255]
        norm = cv2.normalize(self._buffer, None, 0, 255, cv2.NORM_MINMAX)
        norm_uint8 = norm.astype(np.uint8)

        # Apply COLORMAP_JET (blue=cold, red=hot)
        colormap = cv2.applyColorMap(norm_uint8, cv2.COLORMAP_JET)

        # Blend with original frame
        overlay = cv2.addWeighted(frame, 1.0 - alpha, colormap, alpha, 0)
        return overlay

    def reset(self) -> None:
        self._buffer.fill(0)
