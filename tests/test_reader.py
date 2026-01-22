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


class TestInspectSchema:
    def test_inspect_schema(self, sample_zst_file):
        schema = rd.inspect_schema(sample_zst_file, sample_size=3, progress=False)
        assert "body" in schema
        assert "author" in schema
        assert schema["body"]["type"] == "str"
        assert schema["score"]["type"] == "int"
        assert schema["body"]["count"] == 3
