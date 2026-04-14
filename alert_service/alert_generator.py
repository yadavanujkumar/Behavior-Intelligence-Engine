"""
Alert generator.

Converts BehaviorResult events into rich Alert objects, optionally enriching
the message with an LLM-generated natural-language narrative.

Flow:
  BehaviorResult -> cooldown check -> AlertGenerator -> Alert (stored in DB)
"""

import time
from dataclasses import dataclass, field
from typing import Dict, Optional, Tuple

from config.logger import get_logger
from config.settings import cfg

logger = get_logger(__name__)


@dataclass
class Alert:
    """A structured alert ready to be stored and served via the API."""
    track_id: int
    behavior_type: str
    severity: str
    confidence: float
    message: str
    camera_id: str = "cam0"
    details: dict = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    acknowledged: bool = False


# ---------------------------------------------------------------------------
# Rule-based narrative templates (fallback when LLM is unavailable)
# ---------------------------------------------------------------------------

_TEMPLATES: Dict[str, str] = {
    "loitering": (
        "ALERT: Person ID {track_id} has been loitering in the same area for "
        "{duration_seconds:.0f} seconds near coordinates ({anchor_x:.0f}, {anchor_y:.0f}). "
        "Severity: {severity}."
    ),
    "repeated_path": (
        "ALERT: Person ID {track_id} has traversed the same route {loop_count} times. "
        "This repeated movement pattern may indicate surveillance or pre-planned activity. "
        "Severity: {severity}."
    ),
    "sudden_motion": (
        "ALERT: Person ID {track_id} exhibited a sudden velocity spike "
        "(current: {current_velocity:.1f} px/s, mean: {mean_velocity:.1f} px/s). "
        "This may indicate a chase, flight, or altercation. Severity: {severity}."
    ),
}


def _render_template(behavior_type: str, track_id: int, severity: str, details: dict) -> str:
    """Fill in the rule-based template for a given behavior type."""
    template = _TEMPLATES.get(
        behavior_type,
        "ALERT: Person ID {track_id} triggered behavior '{behavior_type}'. Severity: {severity}.",
    )
    try:
        return template.format(
            track_id=track_id,
            severity=severity,
            behavior_type=behavior_type,
            **details,
        )
    except KeyError:
        return (
            f"ALERT: Person ID {track_id} triggered '{behavior_type}' behavior. "
            f"Severity: {severity}."
        )


# ---------------------------------------------------------------------------
# LLM narrative enrichment
# ---------------------------------------------------------------------------

def _llm_enrich(template_message: str) -> str:
    """
    Use OpenAI Chat API to rephrase the alert as a natural-language narrative.

    Falls back to the template message if the API is unavailable or misconfigured.
    """
    if not cfg.openai_api_key or cfg.openai_api_key == "your_openai_key_here":
        logger.debug("OpenAI key not set – using template narrative.")
        return template_message

    try:
        import openai  # deferred import so the module works without openai installed

        client = openai.OpenAI(api_key=cfg.openai_api_key)
        prompt = (
            "You are a security operations AI. Rewrite the following machine-generated "
            "security alert as a concise, professional, single-sentence narrative "
            "suitable for a human security operator. Keep all facts intact.\n\n"
            f"Alert: {template_message}"
        )
        response = client.chat.completions.create(
            model=cfg.openai_model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=120,
            temperature=0.3,
        )
        return response.choices[0].message.content.strip()
    except Exception as exc:
        logger.warning("LLM enrichment failed (%s); using template.", exc)
        return template_message


# ---------------------------------------------------------------------------
# AlertGenerator
# ---------------------------------------------------------------------------

class AlertGenerator:
    """
    Creates Alert objects from BehaviorResult instances.

    Implements a per-(track_id, behavior_type) cooldown to prevent alert storms.
    """

    def __init__(self, cooldown: int = cfg.alert_cooldown):
        self.cooldown = cooldown
        # Maps (track_id, behavior_type) -> last alert timestamp
        self._last_alert: Dict[Tuple[int, str], float] = {}

    def generate(self, behavior_result) -> Optional[Alert]:
        """
        Generate an Alert for a BehaviorResult, respecting the cooldown window.

        Parameters
        ----------
        behavior_result : BehaviorResult (from behavior_service.analyzers)

        Returns
        -------
        Alert or None
        """
        key = (behavior_result.track_id, behavior_result.behavior_type)
        now = time.time()

        if key in self._last_alert:
            elapsed = now - self._last_alert[key]
            if elapsed < self.cooldown:
                logger.debug(
                    "Cooldown active for %s – skipping alert (%ds remaining).",
                    key,
                    int(self.cooldown - elapsed),
                )
                return None

        self._last_alert[key] = now

        # Build template message first
        template_msg = _render_template(
            behavior_result.behavior_type,
            behavior_result.track_id,
            behavior_result.severity,
            behavior_result.details,
        )

        # Optionally enrich with LLM
        message = _llm_enrich(template_msg)

        alert = Alert(
            track_id=behavior_result.track_id,
            behavior_type=behavior_result.behavior_type,
            severity=behavior_result.severity,
            confidence=behavior_result.confidence,
            message=message,
            details=behavior_result.details,
            timestamp=now,
        )

        logger.info(
            "Generated alert | ID:%d | %s | %s | %s",
            alert.track_id,
            alert.behavior_type,
            alert.severity,
            alert.message[:80],
        )
        return alert
