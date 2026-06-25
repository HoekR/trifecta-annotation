"""TRIFECTA automated FrameNet annotation pipeline (17th–20th c. historical food texts)."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("trifecta-annotation")
except PackageNotFoundError:
    __version__ = "0.1.0"

from trifecta_annotation.pipeline import annotate_record
from trifecta_annotation.schemas import (
    FrameClassification,
    KwicInput,
    TrifectaAnnotation,
    TrifectaFrame,
)
from trifecta_annotation.step_b import classify_context

__all__ = [
    "__version__",
    "FrameClassification",
    "KwicInput",
    "TrifectaAnnotation",
    "TrifectaFrame",
    "annotate_record",
    "classify_context",
]
