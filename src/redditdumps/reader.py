import io
import json
from collections import Counter
from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd
import zstandard as zstd
from tqdm import tqdm


Record = dict[str, Any]
RecordFilter = Callable[[Mapping[str, Any]], bool]


@dataclass
class ReadStats:
    """Cumulative statistics for one or more ZST reads."""

    lines_read: int = 0
    decoded_records: int = 0
    malformed_lines: int = 0
    matched_records: int = 0
    batches_yielded: int = 0


class _ByteTracker:
    """Wrapper to track bytes read from a file handle."""

    def __init__(self, fh):
        self.fh = fh
        self.bytes_read = 0

    def read(self, size=-1):
        data = self.fh.read(size)
        self.bytes_read += len(data)
        return data

    def readinto(self, b):
        n = self.fh.readinto(b)
        if n is not None:
            self.bytes_read += n
        return n

    def seek(self, offset, whence=0):
        return self.fh.seek(offset, whence)

    def tell(self):
        return self.fh.tell()


def iter_zst(
    file_path: str | Path,
    columns: list[str] | None = None,
    max_lines: int | None = None,
    progress: bool = True,
    estimate_progress: bool = True,
    record_filter: RecordFilter | None = None,
    stats: ReadStats | None = None,
    **filters: Any,
) -> Iterator[Record]:
    """Stream matching records from a Reddit ZST dump file."""
    file_path = Path(file_path)
    read_stats = stats if stats is not None else ReadStats()

    with open(file_path, "rb") as fh:
        # Optionally wrap file handle to track bytes for progress estimation
        if estimate_progress:
            tracker = _ByteTracker(fh)
            file_size = file_path.stat().st_size
            stream_source = tracker
        else:
            tracker = None
            stream_source = fh

        dctx = zstd.ZstdDecompressor()
        # Stream decompression avoids loading entire file into memory
        with dctx.stream_reader(stream_source) as reader:
            # Wrap binary stream as text for line-by-line JSON parsing
            text_stream = io.TextIOWrapper(reader, encoding="utf-8")

            if estimate_progress:
                pbar = tqdm(
                    desc=f"Reading {file_path.name}",
                    total=file_size,
                    unit="B",
                    unit_scale=True,
                    disable=not progress,
                )
            else:
                pbar = tqdm(
                    desc=f"Reading {file_path.name}",
                    unit=" lines",
                    disable=not progress,
                )

            try:
                last_bytes = 0
                for i, line in enumerate(text_stream):
                    if max_lines is not None and i >= max_lines:
                        break

                    read_stats.lines_read += 1

                    # Update progress based on compressed bytes or line count
                    if estimate_progress:
                        pbar.update(tracker.bytes_read - last_bytes)
                        last_bytes = tracker.bytes_read
                    else:
                        pbar.update(1)

                    try:
                        item = json.loads(line)
                    except json.JSONDecodeError:
                        read_stats.malformed_lines += 1
                        continue

                    read_stats.decoded_records += 1

                    if filters and not _matches_filters(item, filters):
                        continue

                    if record_filter is not None and not record_filter(item):
                        continue

                    read_stats.matched_records += 1

                    if columns is not None:
                        # Extract only requested columns; missing keys become None
                        item = {key: item.get(key) for key in columns}

                    pbar.set_postfix(hits=read_stats.matched_records)
                    yield item
            finally:
                pbar.close()


def read_zst_batches(
    file_path: str | Path,
    columns: list[str] | None = None,
    batch_size: int = 100_000,
    max_lines: int | None = None,
    progress: bool = True,
    estimate_progress: bool = True,
    record_filter: RecordFilter | None = None,
    stats: ReadStats | None = None,
    **filters: Any,
) -> Iterator[pd.DataFrame]:
    """Yield matching records as bounded pandas DataFrames."""
    if batch_size <= 0:
        raise ValueError("batch_size must be greater than zero")

    read_stats = stats if stats is not None else ReadStats()
    batch: list[Record] = []

    for item in iter_zst(
        file_path=file_path,
        columns=columns,
        max_lines=max_lines,
        progress=progress,
        estimate_progress=estimate_progress,
        record_filter=record_filter,
        stats=read_stats,
        **filters,
    ):
        batch.append(item)
        if len(batch) == batch_size:
            read_stats.batches_yielded += 1
            yield pd.DataFrame(batch)
            batch = []

    if batch:
        read_stats.batches_yielded += 1
        yield pd.DataFrame(batch)


def read_zst(
    file_path: str | Path,
    columns: list[str] | None = None,
    max_lines: int | None = None,
    progress: bool = True,
    estimate_progress: bool = True,
    **filters: Any,
) -> pd.DataFrame:
    """
    Read a Reddit ZST dump file into a pandas DataFrame.

    This compatibility API collects all matching records in memory. Use
    ``iter_zst`` or ``read_zst_batches`` for bounded-memory processing.
    """
    return pd.DataFrame(
        list(
            iter_zst(
                file_path=file_path,
                columns=columns,
                max_lines=max_lines,
                progress=progress,
                estimate_progress=estimate_progress,
                **filters,
            )
        )
    )


def _matches_filters(item: dict, filters: dict[str, Any]) -> bool:
    """
    Check if an item matches all filter criteria.

    String comparisons are case-insensitive by default.

    Parameters
    ----------
    item : dict
        A dictionary representing a single Reddit record.
    filters : dict[str, Any]
        Filter conditions where keys are field names and values are the
        expected values. Values can be single items or collections (list,
        tuple, set) for OR matching.

    Returns
    -------
    bool
        True if the item matches all filters, False otherwise.

    Examples
    --------
    >>> _matches_filters({"subreddit": "science", "score": 10}, {"subreddit": "science"})
    True
    >>> _matches_filters({"subreddit": "Science"}, {"subreddit": "science"})
    True
    >>> _matches_filters({"subreddit": "science"}, {"subreddit": ["Science", "News"]})
    True
    >>> _matches_filters({"subreddit": "pics"}, {"subreddit": "science"})
    False
    """
    for key, value in filters.items():
        item_value = item.get(key)

        if isinstance(value, (list, tuple, set)):
            # Multiple values use OR logic (match any)
            if not _value_matches_any(item_value, value):
                return False
        else:
            if not _values_equal(item_value, value):
                return False
    return True


def _values_equal(item_value: Any, filter_value: Any) -> bool:
    """Compare two values, case-insensitive for strings."""
    if isinstance(item_value, str) and isinstance(filter_value, str):
        return item_value.lower() == filter_value.lower()
    return item_value == filter_value


def _value_matches_any(item_value: Any, filter_values: list | tuple | set) -> bool:
    """Check if item_value matches any of the filter values, case-insensitive for strings."""
    for fv in filter_values:
        if _values_equal(item_value, fv):
            return True
    return False


def inspect_schema(
    file_path: str | Path,
    sample_size: int = 1000,
    progress: bool = True,
) -> dict[str, dict[str, Any]]:
    """
    Inspect the schema of a ZST file by sampling records.

    Parameters
    ----------
    file_path : str or Path
        Path to the .zst file.
    sample_size : int, default 1000
        Number of records to sample for schema inference.
    progress : bool, default True
        Show a progress bar while reading.

    Returns
    -------
    dict
        Dictionary mapping column names to info about the column:
        - "type": Most common Python type observed
        - "count": Number of records where this column appeared
        - "sample": A sample value from the column

    Examples
    --------
    >>> schema = inspect_schema("RC_2024-01.zst")
    >>> print(schema["body"])
    {'type': 'str', 'count': 1000, 'sample': 'This is a comment...'}
    """
    file_path = Path(file_path)
    column_info: dict[str, dict[str, Any]] = {}
    type_counts: dict[str, Counter] = {}

    with open(file_path, "rb") as fh:
        dctx = zstd.ZstdDecompressor()
        with dctx.stream_reader(fh) as reader:
            text_stream = io.TextIOWrapper(reader, encoding="utf-8")

            pbar = tqdm(
                desc=f"Inspecting {file_path.name}",
                unit=" lines",
                total=sample_size,
                disable=not progress,
            )

            for i, line in enumerate(text_stream):
                if i >= sample_size:
                    break

                pbar.update(1)

                try:
                    item = json.loads(line)
                except json.JSONDecodeError:
                    continue

                for key, value in item.items():
                    if key not in column_info:
                        column_info[key] = {"count": 0, "sample": None}
                        type_counts[key] = Counter()

                    column_info[key]["count"] += 1
                    type_counts[key][type(value).__name__] += 1

                    # Store first non-null sample, truncating long strings
                    if column_info[key]["sample"] is None and value is not None:
                        if isinstance(value, str) and len(value) > 100:
                            column_info[key]["sample"] = value[:100] + "..."
                        else:
                            column_info[key]["sample"] = value

            pbar.close()

    # Determine the most common type for each column
    for key in column_info:
        most_common = type_counts[key].most_common(1)
        column_info[key]["type"] = most_common[0][0] if most_common else "unknown"

    # Sort by count descending so most common columns appear first
    return dict(sorted(column_info.items(), key=lambda x: -x[1]["count"]))
