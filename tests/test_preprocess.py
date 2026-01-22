"""Tests for redditdumps preprocess functions."""

import pandas as pd
import pytest

from redditdumps.preprocess import (
    _clean_text,
    _detect_type,
    _drop_deleted,
    _parse_dates,
    preprocess,
)


@pytest.fixture
def sample_submissions_df():
    """Create a sample submissions DataFrame."""
    return pd.DataFrame(
        {
            "id": ["abc123", "def456", "ghi789"],
            "author": ["user1", "[deleted]", "user3"],
            "title": ["First post", "Second post", "Third &amp; post"],
            "selftext": ["Hello world", "[removed]", "Some   extra   spaces"],
            "score": [10, 5, 20],
            "subreddit": ["python", "python", "science"],
            "created_utc": [1700000000, 1700000100, 1700000200],
        }
    )


@pytest.fixture
def sample_comments_df():
    """Create a sample comments DataFrame."""
    return pd.DataFrame(
        {
            "id": ["abc123", "def456", "ghi789"],
            "author": ["user1", "[deleted]", "user3"],
            "body": ["Nice post!", "[removed]", "I &amp; agree"],
            "parent_id": ["t3_xyz", "t1_abc", "t1_def"],
            "score": [10, 5, 20],
            "subreddit": ["python", "python", "science"],
            "created_utc": [1700000000, 1700000100, 1700000200],
        }
    )


class TestDetectType:
    def test_detect_submissions_by_selftext(self):
        df = pd.DataFrame({"selftext": ["text"], "author": ["user"]})
        assert _detect_type(df) == "submissions"

    def test_detect_submissions_by_title(self):
        df = pd.DataFrame({"title": ["text"], "author": ["user"]})
        assert _detect_type(df) == "submissions"

    def test_detect_comments_by_body(self):
        df = pd.DataFrame({"body": ["text"], "author": ["user"]})
        assert _detect_type(df) == "comments"

    def test_detect_comments_by_parent_id(self):
        df = pd.DataFrame({"parent_id": ["t3_abc"], "author": ["user"]})
        assert _detect_type(df) == "comments"

    def test_detect_unknown_raises(self):
        df = pd.DataFrame({"author": ["user"], "score": [10]})
        with pytest.raises(ValueError, match="Could not detect data type"):
            _detect_type(df)


class TestParseDates:
    def test_parse_dates(self):
        df = pd.DataFrame({"created_utc": [1700000000, 1700000100]})
        result = _parse_dates(df)
        assert result["created_utc"].dtype == "datetime64[s, UTC]"

    def test_parse_dates_missing_column(self):
        df = pd.DataFrame({"author": ["user1"]})
        result = _parse_dates(df)
        assert "created_utc" not in result.columns


class TestDropDeleted:
    def test_drop_deleted_authors(self):
        df = pd.DataFrame(
            {
                "author": ["user1", "[deleted]", "[removed]", "user4"],
                "body": ["a", "b", "c", "d"],
            }
        )
        result = _drop_deleted(df, text_col="body")
        assert len(result) == 2
        assert "[deleted]" not in result["author"].values
        assert "[removed]" not in result["author"].values

    def test_drop_deleted_text(self):
        df = pd.DataFrame(
            {
                "author": ["user1", "user2", "user3"],
                "body": ["hello", "[deleted]", "[removed]"],
            }
        )
        result = _drop_deleted(df, text_col="body")
        assert len(result) == 1
        assert result.iloc[0]["body"] == "hello"

    def test_drop_deleted_missing_columns(self):
        df = pd.DataFrame({"score": [1, 2, 3]})
        result = _drop_deleted(df, text_col="body")
        assert len(result) == 3


class TestCleanText:
    def test_unescape_html_entities(self):
        df = pd.DataFrame({"body": ["Hello &amp; world", "Test &lt;tag&gt;"]})
        result = _clean_text(df, text_col="body")
        assert result.iloc[0]["body"] == "Hello & world"
        assert result.iloc[1]["body"] == "Test <tag>"

    def test_normalize_whitespace(self):
        df = pd.DataFrame({"body": ["too   many   spaces", "newlines\n\nhere"]})
        result = _clean_text(df, text_col="body")
        assert result.iloc[0]["body"] == "too many spaces"
        assert result.iloc[1]["body"] == "newlines here"

    def test_clean_text_missing_column(self):
        df = pd.DataFrame({"author": ["user1"]})
        result = _clean_text(df, text_col="body")
        assert "body" not in result.columns

    def test_clean_text_non_string(self):
        df = pd.DataFrame({"body": ["hello", None, 123]})
        result = _clean_text(df, text_col="body")
        assert result.iloc[0]["body"] == "hello"
        assert result.iloc[1]["body"] is None
        assert result.iloc[2]["body"] == 123


class TestPreprocess:
    def test_preprocess_submissions_auto_detect(self, sample_submissions_df):
        result = preprocess(sample_submissions_df)
        # user1 and user3 survive; user2 dropped (deleted author + removed text)
        assert len(result) == 2
        assert result["created_utc"].dtype == "datetime64[s, UTC]"

    def test_preprocess_comments_auto_detect(self, sample_comments_df):
        result = preprocess(sample_comments_df)
        # user1 and user3 survive; user2 dropped (deleted author + removed body)
        assert len(result) == 2
        assert result["created_utc"].dtype == "datetime64[s, UTC]"

    def test_preprocess_explicit_type(self, sample_submissions_df):
        result = preprocess(sample_submissions_df, type="submissions")
        assert len(result) == 2

    def test_preprocess_custom_text_col(self):
        df = pd.DataFrame(
            {
                "author": ["user1", "user2"],
                "selftext": ["normal", "normal"],
                "custom_text": ["keep", "[deleted]"],
                "created_utc": [1700000000, 1700000100],
            }
        )
        result = preprocess(df, text_col="custom_text")
        assert len(result) == 1
        assert result.iloc[0]["custom_text"] == "keep"

    def test_preprocess_disable_options(self, sample_submissions_df):
        result = preprocess(
            sample_submissions_df,
            parse_dates=False,
            drop_deleted=False,
            clean_text=False,
        )
        assert len(result) == 3
        assert result["created_utc"].dtype == "int64"
        assert "&amp;" in result.iloc[2]["title"]

    def test_preprocess_cleans_title_for_submissions(self):
        df = pd.DataFrame(
            {
                "author": ["user1"],
                "title": ["Hello &amp; world"],
                "selftext": ["text"],
                "created_utc": [1700000000],
            }
        )
        result = preprocess(df)
        assert result.iloc[0]["title"] == "Hello & world"
