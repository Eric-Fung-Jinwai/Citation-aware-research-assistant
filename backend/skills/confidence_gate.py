from typing import Literal

CONFIDENCE_THRESHOLD = 33.0

_TIER_MAP: list[tuple[float, str]] = [
    (60.0, "High"),
    (45.0, "Moderate"),
    (33.0, "Low"),
    (0.0, "Very Low"),
]


def get_confidence_tier(score: float) -> str:
    for threshold, label in _TIER_MAP:
        if score >= threshold:
            return label
    return "Very Low"


def apply_confidence_gate(retro_result: dict) -> dict:
    """
    Wraps a stock-retro result dict. Never mutates the input.
    Returns a new dict with confidence_tier injected into data,
    or a 'blocked' dict if confidence < CONFIDENCE_THRESHOLD.
    """
    if retro_result.get("status") != "success":
        return retro_result

    data = retro_result.get("data", {})
    score = data.get("confidence_score")

    if score is None:
        return {
            **retro_result,
            "data": {
                **data,
                "confidence_tier": "Unknown",
                "confidence_warning": (
                    "Confidence score could not be parsed from report output. "
                    "Verify the LLM followed the 'Confidence: X%' format in Section 8 of the report."
                ),
            },
        }

    tier = get_confidence_tier(score)

    if score < CONFIDENCE_THRESHOLD:
        return {
            "status": "blocked",
            "error": (
                f"Report blocked: confidence {score:.1f}% is below the "
                f"{CONFIDENCE_THRESHOLD:.0f}% minimum threshold. "
                "Insufficient evidence to produce a reliable report."
            ),
            "confidence_score": score,
            "confidence_tier": tier,
            "source": "confidence-gate",
        }

    return {
        **retro_result,
        "data": {**data, "confidence_tier": tier},
    }