"""Known column schemas for Reddit data dumps."""

# Common columns that appear in both submissions and comments
COMMON_COLUMNS = [
    "id",
    "author",
    "author_fullname",
    "created_utc",
    "score",
    "ups",
    "downs",
    "subreddit",
    "subreddit_id",
    "permalink",
    "edited",
    "stickied",
    "locked",
    "archived",
    "distinguished",
    "gilded",
    "controversiality",
    "total_awards_received",
    "retrieved_on",
]

# Columns specific to comments (RC_ files)
COMMENT_COLUMNS = COMMON_COLUMNS + [
    "body",
    "parent_id",
    "link_id",
    "is_submitter",
    "collapsed",
    "collapsed_reason",
    "comment_type",
]

# Columns specific to submissions (RS_ files)
SUBMISSION_COLUMNS = COMMON_COLUMNS + [
    "title",
    "selftext",
    "url",
    "domain",
    "is_self",
    "is_video",
    "is_original_content",
    "over_18",
    "spoiler",
    "num_comments",
    "num_crossposts",
    "upvote_ratio",
    "thumbnail",
    "media",
    "link_flair_text",
    "link_flair_type",
]

# Minimal columns for lightweight analysis
MINIMAL_COMMENT_COLUMNS = [
    "id",
    "author",
    "body",
    "score",
    "created_utc",
    "subreddit",
    "parent_id",
    "link_id",
]

MINIMAL_SUBMISSION_COLUMNS = [
    "id",
    "author",
    "title",
    "selftext",
    "score",
    "created_utc",
    "subreddit",
    "url",
    "num_comments",
]
