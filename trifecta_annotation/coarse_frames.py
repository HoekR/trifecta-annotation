"""Coarse macro-frames for simplified INCEpTION / silver annotation."""

from __future__ import annotations

from enum import Enum

from trifecta_annotation.schemas import TrifectaFrame


class CoarseFrame(str, Enum):
    FOOD_TRANSFORM = "FOOD_TRANSFORM"
    MEDICAL_CURE = "MEDICAL_CURE"
    CONSUMPTION = "CONSUMPTION"
    OUT_OF_SCOPE = "OUT_OF_SCOPE"


def coarse_frame_from_fine(
    frame: TrifectaFrame | None,
    *,
    dropped: bool = False,
) -> CoarseFrame:
    """Map fine TRIFECTA macro-frame to team coarse scheme."""
    if dropped or frame is None or frame == TrifectaFrame.NONE:
        return CoarseFrame.OUT_OF_SCOPE
    if frame in (TrifectaFrame.COOKING_CREATION, TrifectaFrame.PRESERVING):
        return CoarseFrame.FOOD_TRANSFORM
    if frame == TrifectaFrame.CURE:
        return CoarseFrame.MEDICAL_CURE
    if frame == TrifectaFrame.INGESTION:
        return CoarseFrame.CONSUMPTION
    return CoarseFrame.OUT_OF_SCOPE
