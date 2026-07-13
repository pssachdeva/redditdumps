"""Tests for redditdumps reader functions."""

import json
import tempfile
from pathlib import Path

import pandas as pd
import pytest
import zstandard as zstd

import redditdumps as rd


@pytest.fixture
def sample_zst_file():
    """Create a temporary ZST file with sample Reddit data."""
    records = [
        {
            "id": "abc123",
            "author": "user1",
            "body": "This is a comment",
            "score": 10,
            "subreddit": "python",
            "created_utc": 1700000000,
        },
        {
            "id": "def456",
            "author": "user2",
            "body": "Another comment",
            "score": 5,
            "subreddit": "science",
            "created_utc": 1700000100,
        },
        {
            "id": "ghi789",
            "author": "user1",
            "body": "Third comment",
            "score": 20,
            "subreddit": "python",
            "created_utc": 1700000200,
        },
    ]

    with tempfile.NamedTemporaryFile(suffix=".zst", delete=False) as f:
        cctx = zstd.ZstdCompressor()
        with cctx.stream_writer(f) as writer:
            for record in records:
                line = json.dumps(record) + "\n"
                writer.write(line.encode("utf-8"))
        temp_path = f.name

    yield Path(temp_path)

    # Cleanup
    Path(temp_path).unlink()


class TestReadZst:
    def test_read_all(self, sample_zst_file):
        df = rd.read_zst(sample_zst_file, progress=False)
        assert len(df) == 3
        assert "body" in df.columns
        assert "author" in df.columns

    def test_read_with_columns(self, sample_zst_file):
        df = rd.read_zst(sample_zst_file, columns=["id", "author"], progress=False)
        assert len(df) == 3
        assert list(df.columns) == ["id", "author"]

    def test_read_with_filter(self, sample_zst_file):
        df = rd.read_zst(sample_zst_file, subreddit="python", progress=False)
        assert len(df) == 2
        assert all(df["subreddit"] == "python")

    def test_read_with_multi_value_filter(self, sample_zst_file):
        df = rd.read_zst(
            sample_zst_file, subreddit=["python", "science"], progress=False
        )
        assert len(df) == 3

    def test_read_with_max_lines(self, sample_zst_file):
        df = rd.read_zst(sample_zst_file, max_lines=2, progress=False)
        assert len(df) == 2

    def test_read_with_author_filter(self, sample_zst_file):
        df = rd.read_zst(sample_zst_file, author="user1", progress=False)
        assert len(df) == 2
        assert all(df["author"] == "user1")

    def test_read_filter_case_insensitive(self, sample_zst_file):
        # Filter with different case than data ("python" in data, "Python" in filter)
        df = rd.read_zst(sample_zst_file, subreddit="Python", progress=False)
        assert len(df) == 2
        assert all(df["subreddit"] == "python")

    def test_read_multi_filter_case_insensitive(self, sample_zst_file):
        # Filter with mixed case in list
        df = rd.read_zst(
            sample_zst_file, subreddit=["PYTHON", "Science"], progress=False
        )
        assert len(df) == 3


class TestIterZst:
    def test_iterates_matching_records(self, sample_zst_file):
        records = list(rd.iter_zst(sample_zst_file, subreddit="python", progress=False))
        assert [record["id"] for record in records] == ["abc123", "ghi789"]

    def test_applies_predicate_before_column_selection(self, sample_zst_file):
        records = list(
            rd.iter_zst(
                sample_zst_file,
                columns=["id"],
                record_filter=lambda record: record["created_utc"] >= 1700000100,
                progress=False,
            )
        )
        assert records == [{"id": "def456"}, {"id": "ghi789"}]

    def test_updates_stats(self, sample_zst_file):
        stats = rd.ReadStats()
        records = list(
            rd.iter_zst(
                sample_zst_file,
                subreddit="python",
                stats=stats,
                progress=False,
            )
        )
        assert len(records) == 2
        assert stats.lines_read == 3
        assert stats.decoded_records == 3
        assert stats.malformed_lines == 0
        assert stats.matched_records == 2

    def test_generator_can_close_early(self, sample_zst_file):
        records = rd.iter_zst(sample_zst_file, progress=False)
        assert next(records)["id"] == "abc123"
        records.close()

    def test_counts_and_skips_malformed_json(self, tmp_path):
        path = tmp_path / "malformed.zst"
        lines = [
            json.dumps({"id": "good-1"}),
            "not json",
            json.dumps({"id": "good-2"}),
        ]
        with path.open("wb") as file_handle:
            compressor = zstd.ZstdCompressor()
            with compressor.stream_writer(file_handle) as writer:
                writer.write(("\n".join(lines) + "\n").encode())

        stats = rd.ReadStats()
        records = list(rd.iter_zst(path, stats=stats, progress=False))

        assert [record["id"] for record in records] == ["good-1", "good-2"]
        assert stats.lines_read == 3
        assert stats.decoded_records == 2
        assert stats.malformed_lines == 1
        assert stats.matched_records == 2

    def test_max_lines_counts_raw_lines(self, sample_zst_file):
        stats = rd.ReadStats()
        records = list(
            rd.iter_zst(
                sample_zst_file,
                max_lines=2,
                stats=stats,
                progress=False,
            )
        )
        assert [record["id"] for record in records] == ["abc123", "def456"]
        assert stats.lines_read == 2


class TestReadZstBatches:
    def test_yields_full_and_partial_batches(self, sample_zst_file):
        stats = rd.ReadStats()
        batches = list(
            rd.read_zst_batches(
                sample_zst_file,
                batch_size=2,
                stats=stats,
                progress=False,
            )
        )
        assert [len(batch) for batch in batches] == [2, 1]
        assert stats.batches_yielded == 2
        assert pd.concat(batches, ignore_index=True)["id"].tolist() == [
            "abc123",
            "def456",
            "ghi789",
        ]

    def test_filters_before_batching(self, sample_zst_file):
        batches = list(
            rd.read_zst_batches(
                sample_zst_file,
                batch_size=2,
                subreddit="python",
                progress=False,
            )
        )
        assert len(batches) == 1
        assert batches[0]["id"].tolist() == ["abc123", "ghi789"]

    def test_rejects_nonpositive_batch_size(self, sample_zst_file):
        with pytest.raises(ValueError, match="batch_size"):
            list(rd.read_zst_batches(sample_zst_file, batch_size=0, progress=False))

    def test_yields_no_batches_when_nothing_matches(self, sample_zst_file):
        batches = list(
            rd.read_zst_batches(
                sample_zst_file,
                subreddit="missing",
                progress=False,
            )
        )
        assert batches == []

    def test_accumulates_stats_across_files(self, sample_zst_file):
        stats = rd.ReadStats()
        for _ in range(2):
            list(
                rd.read_zst_batches(
                    sample_zst_file,
                    batch_size=2,
                    stats=stats,
                    progress=False,
                )
            )
        assert stats.lines_read == 6
        assert stats.matched_records == 6
        assert stats.batches_yielded == 4


class TestInspectSchema:
    def test_inspect_schema(self, sample_zst_file):
        schema = rd.inspect_schema(sample_zst_file, sample_size=3, progress=False)
        assert "body" in schema
        assert "author" in schema
        assert schema["body"]["type"] == "str"
        assert schema["score"]["type"] == "int"
        assert schema["body"]["count"] == 3
