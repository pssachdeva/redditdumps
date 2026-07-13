# redditdumps

Lightweight Python utilities for processing Reddit data dumps in ZST format.

These dumps are commonly found on Academic Torrents (Pushshift archives) and contain newline-delimited JSON compressed with Zstandard.

## Installation

```bash
uv add redditdumps
```

Or with pip:

```bash
pip install redditdumps
```

## Usage

### Read a ZST file into a DataFrame

```python
import redditdumps as rd

# Read entire file
df = rd.read_zst("RC_2024-01.zst")

# Filter by subreddit
df = rd.read_zst("RC_2024-01.zst", subreddit="science")

# Filter by multiple subreddits
df = rd.read_zst("RC_2024-01.zst", subreddit=["science", "askscience"])

# Select specific columns
df = rd.read_zst("RC_2024-01.zst", columns=["author", "body", "score"])

# Combine filters
df = rd.read_zst(
    "RC_2024-01.zst",
    subreddit="python",
    columns=rd.MINIMAL_COMMENT_COLUMNS,
    max_lines=100000,
)
```

### Stream records with bounded memory

Use `iter_zst` when you want one decoded record at a time:

```python
for record in rd.iter_zst("RC_2024-01.zst", subreddit="science"):
    process(record)
```

Use `read_zst_batches` to receive bounded pandas DataFrames. Exact filters and
the optional predicate run before records enter a batch.

```python
start_utc = 1704067200
end_utc = 1706745600
stats = rd.ReadStats()

for batch in rd.read_zst_batches(
    "RC_2024-01.zst",
    subreddit="science",
    record_filter=lambda record: (
        start_utc <= int(record["created_utc"]) < end_utc
    ),
    batch_size=100_000,
    stats=stats,
):
    process(batch)

print(stats)
```

`read_zst` remains available when the complete result fits in memory.

### Inspect file schema

```python
# Discover columns in a file
schema = rd.inspect_schema("RC_2024-01.zst", sample_size=1000)
for col, info in schema.items():
    print(f"{col}: {info['type']} ({info['count']} records)")
```

### Built-in column schemas

```python
# Common column sets for convenience
rd.COMMENT_COLUMNS       # All standard comment fields
rd.SUBMISSION_COLUMNS    # All standard submission fields
rd.MINIMAL_COMMENT_COLUMNS   # Lightweight subset for comments
rd.MINIMAL_SUBMISSION_COLUMNS  # Lightweight subset for submissions
```

## File naming conventions

- `RC_*.zst` - Reddit Comments
- `RS_*.zst` - Reddit Submissions
