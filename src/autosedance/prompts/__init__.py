"""Prompt templates for different models."""

from .scriptwriter import SCRIPTWRITER_SYSTEM, SCRIPTWRITER_USER
from .segmenter import SEGMENTER_SYSTEM, SEGMENTER_USER
from .analyzer import ANALYZER_SYSTEM, ANALYZER_USER

__all__ = [
    "SCRIPTWRITER_SYSTEM",
    "SCRIPTWRITER_USER",
    "SEGMENTER_SYSTEM",
    "SEGMENTER_USER",
    "ANALYZER_SYSTEM",
    "ANALYZER_USER",
]
