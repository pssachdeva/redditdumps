"""Preprocessing functions for Reddit data."""

import html
import re
from typing import Literal

import pandas as pd


def preprocess(
    df: pd.DataFrame,
    type: Literal["submissions", "comments"] | None = None,
    text_col: str | None = None,
    parse_dates: bool = True,
    drop_deleted: bool = True,
    drop_moderator: bool = False,
    clean_text: bool = True,
) -> pd.DataFrame:
    """
    Preprocess Reddit data, auto-detecting submissions vs comments.

    Parameters
    ----------
    df : pd.DataFrame
        DataFrame containing Reddit data.
    type : {"submissions", "comments"}, optional
        Type of data. If not provided, auto-detects based on columns.
    text_col : str, optional
        Column containing the main text content. Defaults to "selftext" for
        submissions and "body" for comments.
    parse_dates : bool, default True
        Convert created_utc to datetime.
    drop_deleted : bool, default True
        Remove rows with deleted/removed authors or content.
    drop_moderator : bool, default False
        Remove moderator/AutoModerator posts (distinguished, stickied, or
        username/flair containing "moderator").
    clean_text : bool, default True
        Clean text content (unescape HTML, normalize whitespace).

    Returns
    -------
    pd.DataFrame
        Preprocessed DataFrame.

    Examples
    --------
    >>> df = read_zst("RS_2024-01.zst", subreddit="science")
    >>> df = preprocess(df)
    >>> df = read_zst("RC_2024-01.zst", subreddit="science")
    >>> df = preprocess(df, type="comments")
    """
    # Auto-detect type if not provided
    if type is None:
        type = _detect_type(df)

    # Set default text column based on type
    if text_col is None:
        text_col = "selftext" if type == "submissions" else "body"

    if type == "submissions":
        return _preprocess_submissions(
            df,
            text_col=text_col,
            parse_dates=parse_dates,
            drop_deleted=drop_deleted,
            drop_moderator=drop_moderator,
            clean_text=clean_text,
        )
    else:
        return _preprocess_comments(
            df,
            text_col=text_col,
            parse_dates=parse_dates,
            drop_deleted=drop_deleted,
            drop_moderator=drop_moderator,
            clean_text=clean_text,
        )


def _detect_type(df: pd.DataFrame) -> Literal["submissions", "comments"]:
    """Detect whether DataFrame contains submissions or comments."""
    if "selftext" in df.columns or "title" in df.columns:
        return "submissions"
    elif "body" in df.columns or "parent_id" in df.columns:
        return "comments"
    else:
        raise ValueError(
            "Could not detect data type from columns. "
            "Specify type='submissions' or type='comments'."
        )


def _preprocess_submissions(
    df: pd.DataFrame,
    text_col: str,
    parse_dates: bool,
    drop_deleted: bool,
    drop_moderator: bool,
    clean_text: bool,
) -> pd.DataFrame:
    """Preprocess submission data."""
    df = df.copy()

    if parse_dates:
        df = _parse_dates(df)

    if drop_deleted:
        df = _drop_deleted(df, text_col=text_col)

    if drop_moderator:
        df = _drop_moderator(df)

    if clean_text:
        df = _clean_text(df, text_col=text_col)
        if "title" in df.columns:
            df = _clean_text(df, text_col="title")

    return df


def _preprocess_comments(
    df: pd.DataFrame,
    text_col: str,
    parse_dates: bool,
    drop_deleted: bool,
    drop_moderator: bool,
    clean_text: bool,
) -> pd.DataFrame:
    """Preprocess comment data."""
    df = df.copy()

    if parse_dates:
        df = _parse_dates(df)

    if drop_deleted:
        df = _drop_deleted(df, text_col=text_col)

    if drop_moderator:
        df = _drop_moderator(df)

    if clean_text:
        df = _clean_text(df, text_col=text_col)

    return df


def _parse_dates(df: pd.DataFrame) -> pd.DataFrame:
    """Convert created_utc to datetime."""
    if "created_utc" in df.columns:
        df["created_utc"] = pd.to_datetime(df["created_utc"], unit="s", utc=True)
    return df


def _drop_deleted(df: pd.DataFrame, text_col: str) -> pd.DataFrame:
    """Remove rows with deleted/removed authors or missing content."""
    if "author" in df.columns:
        df = df[~df["author"].isin(["[deleted]", "[removed]"])]

    if text_col in df.columns:
        df = df[~df[text_col].isin(["[deleted]", "[removed]"])]
        df = df[df[text_col].notna()]

    return df


def _drop_moderator(df: pd.DataFrame) -> pd.DataFrame:
    """Remove moderator and AutoModerator posts."""
    # 1. Distinguished field (official mod/admin designation)
    if "distinguished" in df.columns:
        df = df[
            (df["distinguished"].isna())
            | (~df["distinguished"].isin(["moderator", "admin"]))
        ]

    # 2. Exact AutoModerator username match
    if "author" in df.columns:
        df = df[df["author"] != "AutoModerator"]

    # 3. Stickied posts
    if "stickied" in df.columns:
        df = df[df["stickied"] != True]  # noqa: E712

    # 4. Username or flair containing "moderator" (case-insensitive)
    if "author" in df.columns:
        df = df[~df["author"].str.contains("moderator", case=False, na=False)]

    if "author_flair_text" in df.columns:
        df = df[~df["author_flair_text"].str.contains("moderator", case=False, na=False)]

    if "author_flair_css_class" in df.columns:
        df = df[
            ~df["author_flair_css_class"].str.contains("moderator", case=False, na=False)
        ]

    return df


def _clean_text(df: pd.DataFrame, text_col: str) -> pd.DataFrame:
    """Clean text content: unescape HTML entities, normalize whitespace."""
    if text_col not in df.columns:
        return df

    def clean(text):
        if not isinstance(text, str):
            return text
        # Unescape HTML entities (e.g., &amp; -> &)
        text = html.unescape(text)
        # Normalize whitespace
        text = re.sub(r"\s+", " ", text).strip()
        return text

    df[text_col] = df[text_col].apply(clean)
    return df
