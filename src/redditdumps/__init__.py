"""Lightweight utilities for processing Reddit data dumps in ZST format."""

from redditdumps.preprocess import preprocess
from redditdumps.reader import (
    ReadStats,
    inspect_schema,
    iter_zst,
    read_zst,
    read_zst_batches,
)
from redditdumps.schema import (
    COMMENT_COLUMNS,
    COMMON_COLUMNS,
    MINIMAL_COMMENT_COLUMNS,
    MINIMAL_SUBMISSION_COLUMNS,
    SUBMISSION_COLUMNS,
)

__version__ = "0.2.0"

__all__ = [
    # Functions
    "iter_zst",
    "read_zst",
    "read_zst_batches",
    "inspect_schema",
    "preprocess",
    "ReadStats",
    # Schema constants
    "COMMON_COLUMNS",
    "COMMENT_COLUMNS",
    "SUBMISSION_COLUMNS",
    "MINIMAL_COMMENT_COLUMNS",
    "MINIMAL_SUBMISSION_COLUMNS",
]
