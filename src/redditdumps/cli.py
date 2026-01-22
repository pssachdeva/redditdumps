"""Command-line interface for redditdumps."""

from pathlib import Path
from typing import Annotated, Optional

import typer

from redditdumps.preprocess import preprocess
from redditdumps.reader import inspect_schema, read_zst

app = typer.Typer(
    name="redditdumps",
    help="Utilities for processing Reddit data dumps in ZST format.",
    no_args_is_help=True,
)


@app.command()
def read(
    file_path: Annotated[Path, typer.Argument(help="Path to the .zst file")],
    output: Annotated[
        Path, typer.Option("--output", "-o", help="Output file path (CSV or Parquet)")
    ],
    subreddit: Annotated[
        Optional[str],
        typer.Option("--subreddit", "-s", help="Filter by subreddit (comma-separated for multiple)"),
    ] = None,
    columns: Annotated[
        Optional[str],
        typer.Option("--columns", "-c", help="Comma-separated list of columns"),
    ] = None,
    max_lines: Annotated[
        Optional[int],
        typer.Option("--max-lines", "-n", help="Maximum lines to read"),
    ] = None,
    do_preprocess: Annotated[
        bool,
        typer.Option("--preprocess", "-p", help="Apply preprocessing"),
    ] = False,
    no_progress: Annotated[
        bool,
        typer.Option("--no-progress", help="Disable progress bar"),
    ] = False,
):
    """Read a ZST file and save to CSV or Parquet."""
    # Parse columns if provided
    cols = [c.strip() for c in columns.split(",")] if columns else None

    # Build filter kwargs
    filters = {}
    if subreddit:
        subs = [s.strip() for s in subreddit.split(",")]
        filters["subreddit"] = subs if len(subs) > 1 else subs[0]

    # Read the file
    df = read_zst(
        file_path,
        columns=cols,
        max_lines=max_lines,
        progress=not no_progress,
        **filters,
    )

    # Optionally preprocess
    if do_preprocess:
        df = preprocess(df)

    # Save based on file extension
    if output.suffix == ".parquet":
        df.to_parquet(output, index=False)
    else:
        df.to_csv(output, index=False)

    typer.echo(f"Saved {len(df)} records to {output}")


@app.command()
def inspect(
    file_path: Annotated[Path, typer.Argument(help="Path to the .zst file")],
    sample_size: Annotated[
        int,
        typer.Option("--sample-size", "-n", help="Number of records to sample"),
    ] = 1000,
    no_progress: Annotated[
        bool,
        typer.Option("--no-progress", help="Disable progress bar"),
    ] = False,
):
    """Inspect the schema of a ZST file."""
    schema = inspect_schema(
        file_path,
        sample_size=sample_size,
        progress=not no_progress,
    )

    typer.echo(f"\nFound {len(schema)} columns:\n")
    typer.echo(f"{'Column':<30} {'Type':<10} {'Count':<8} Sample")
    typer.echo("-" * 80)

    for col, info in schema.items():
        sample = str(info["sample"])[:35] if info["sample"] is not None else "None"
        typer.echo(f"{col:<30} {info['type']:<10} {info['count']:<8} {sample}")


if __name__ == "__main__":
    app()
