"""
Convert scraped JSON data to AI-readable Markdown files.

Usage:
    python scraper/to_markdown.py --target USERNAME
"""

import argparse
import json
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_TARGET_USER = "Abombination81"


def target_paths(target: str) -> dict:
    data_dir = PROJECT_ROOT / "data" / target / "raw"
    archive_dir = PROJECT_ROOT / "archive" / target
    return {
        "data_dir": data_dir,
        "replies_dir": data_dir / "replies",
        "tweets_file": data_dir / "tweets.json",
        "archive_dir": archive_dir,
        "posts_dir": archive_dir / "posts",
        "threads_dir": archive_dir / "threads",
    }


def parse_date(date_str: str) -> datetime:
    """Parse X date format to datetime."""
    formats = [
        "%a %b %d %H:%M:%S %z %Y",  # Twitter API format
        "%Y-%m-%dT%H:%M:%S%z",  # ISO format
        "%Y-%m-%dT%H:%M:%S.%f%z",  # ISO with microseconds
    ]
    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    # Fallback: return epoch
    return datetime(2000, 1, 1)


def format_date(date_str: str) -> str:
    """Format date for display."""
    dt = parse_date(date_str)
    return dt.strftime("%Y-%m-%d %H:%M")


def date_prefix(date_str: str) -> str:
    """Get YYYY-MM-DD prefix for filenames."""
    dt = parse_date(date_str)
    return dt.strftime("%Y-%m-%d")


def sanitize_filename(text: str, max_len: int = 50) -> str:
    """Make text safe for filenames."""
    safe = "".join(c if c.isalnum() or c in "-_ " else "" for c in text)
    return safe.strip().replace(" ", "-")[:max_len]


def tweet_to_markdown(tweet: dict, replies: list[dict], target_user: str) -> str:
    """Convert a single tweet + replies to markdown."""
    lines = []
    date_display = format_date(tweet["created_at"]) if tweet.get("created_at") else "Unknown date"

    lines.append(f"# @{target_user} -- {date_display}\n")
    lines.append(f"> {tweet['text']}\n")

    # Metadata
    meta_parts = []
    if tweet.get("likes"):
        meta_parts.append(f"Likes: {tweet['likes']}")
    if tweet.get("retweets"):
        meta_parts.append(f"Retweets: {tweet['retweets']}")
    if tweet.get("reply_count"):
        meta_parts.append(f"Replies: {tweet['reply_count']}")
    if meta_parts:
        lines.append(f"**{' | '.join(meta_parts)}**\n")

    if tweet.get("url"):
        lines.append(f"[Original post]({tweet['url']})\n")

    # Media
    if tweet.get("media"):
        lines.append("### Media\n")
        for m in tweet["media"]:
            lines.append(f"- [{m.get('type', 'media')}]({m.get('url', '')})")
        lines.append("")

    # Replies
    if replies:
        lines.append("---\n")
        lines.append("## Replies\n")
        for reply in replies:
            reply_date = format_date(reply["created_at"]) if reply.get("created_at") else ""
            lines.append(f"### @{reply.get('author', 'unknown')} -- {reply_date}\n")
            lines.append(f"{reply['text']}\n")
            if reply.get("likes"):
                lines.append(f"*Likes: {reply['likes']}*\n")

    return "\n".join(lines)


def generate_index(tweets: list[dict], target_user: str) -> str:
    """Generate index.md table of contents."""
    lines = []
    lines.append(f"# Archive of @{target_user}\n")
    lines.append(f"Total posts: {len(tweets)}\n")
    lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n")
    lines.append("---\n")

    # Group by month
    months: dict[str, list] = {}
    for tweet in tweets:
        dt = parse_date(tweet.get("created_at", ""))
        month_key = dt.strftime("%Y-%m")
        months.setdefault(month_key, []).append(tweet)

    for month_key in sorted(months.keys(), reverse=True):
        month_tweets = months[month_key]
        dt = parse_date(month_tweets[0].get("created_at", ""))
        lines.append(f"## {dt.strftime('%B %Y')}\n")

        for tweet in month_tweets:
            prefix = date_prefix(tweet.get("created_at", ""))
            tid = tweet["id"]
            preview = tweet["text"][:80].replace("\n", " ")
            filename = f"{prefix}-{tid}.md"
            likes = tweet.get("likes", 0)
            lines.append(f"- [{preview}...](posts/{filename}) ({likes} likes)")

        lines.append("")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Convert scraped tweets to markdown")
    parser.add_argument("--target", default=DEFAULT_TARGET_USER, help="Target X username (without @)")
    args = parser.parse_args()

    target_user = args.target
    paths = target_paths(target_user)
    posts_dir = paths["posts_dir"]
    threads_dir = paths["threads_dir"]
    archive_dir = paths["archive_dir"]
    replies_dir = paths["replies_dir"]
    tweets_file = paths["tweets_file"]

    posts_dir.mkdir(parents=True, exist_ok=True)
    threads_dir.mkdir(parents=True, exist_ok=True)

    if not tweets_file.exists():
        print(f"No tweets.json found at {tweets_file}. Run scrape.py first.")
        return

    tweets = json.loads(tweets_file.read_text())
    print(f"Loaded {len(tweets)} tweets")

    generated = 0
    for tweet in tweets:
        tid = tweet["id"]
        prefix = date_prefix(tweet.get("created_at", ""))

        reply_file = replies_dir / f"{tid}.json"
        replies = []
        if reply_file.exists():
            replies = json.loads(reply_file.read_text())

        md = tweet_to_markdown(tweet, replies, target_user)
        out_file = posts_dir / f"{prefix}-{tid}.md"
        out_file.write_text(md)
        generated += 1

    index_md = generate_index(tweets, target_user)
    index_file = archive_dir / "index.md"
    index_file.write_text(index_md)

    print(f"Generated {generated} post files + index.md in {archive_dir}")


if __name__ == "__main__":
    main()
