"""Lightweight utilities for processing Reddit data dumps in ZST format."""

from redditdumps.preprocess import preprocess
from redditdumps.reader import inspect_schema, read_zst
from redditdumps.schema import (
    COMMENT_COLUMNS,
    COMMON_COLUMNS,
    MINIMAL_COMMENT_COLUMNS,
    MINIMAL_SUBMISSION_COLUMNS,
    SUBMISSION_COLUMNS,
)

__version__ = "0.1.0"

__all__ = [
    # Functions
    "read_zst",
    "inspect_schema",
    "preprocess",
    # Schema constants
    "COMMON_COLUMNS",
    "COMMENT_COLUMNS",
    "SUBMISSION_COLUMNS",
    "MINIMAL_COMMENT_COLUMNS",
    "MINIMAL_SUBMISSION_COLUMNS",
]
