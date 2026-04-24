# abomination

X archive tool — scrapes all posts and replies from a target X account and generates a local markdown archive.

## Setup

```bash
cd scraper
python -m venv ../venv
source ../venv/bin/activate
pip install -r requirements.txt
```

## Usage

### First run (login to X)
```bash
python scraper/scrape.py --username YOUR_X_USERNAME --password YOUR_X_PASSWORD
```

### Subsequent runs (uses saved cookies)
```bash
python scraper/scrape.py
```

### Generate markdown archive
```bash
python scraper/to_markdown.py
```

### Options
- `--skip-replies` — Only fetch tweets, skip reply fetching
- `--retry-failed` — Retry tweets that failed reply fetching
- `--email YOUR_EMAIL` — Provide email for 2FA verification

## Structure

- `data/<target>/raw/tweets.json` — All tweets (JSON, source of truth)
- `data/<target>/raw/replies/{tweet_id}.json` — Replies per tweet
- `archive/<target>/index.md` — Table of contents
- `archive/<target>/posts/{date}-{id}.md` — One markdown file per post + replies

## Resume

The scraper saves progress after each page. If interrupted, just run it again — it skips already-fetched tweets.
