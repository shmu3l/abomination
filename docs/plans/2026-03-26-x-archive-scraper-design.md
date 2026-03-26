# X Account Archive Scraper — Design

## Goal

Archive all posts and replies from [@Abombination81](https://x.com/Abombination81) locally in JSON (source of truth) + Markdown (AI-readable).

## Approach

Python scraper using **twikit** — no API key needed, uses browser session cookies.

## Directory Structure

```
abomination/
├── scraper/
│   ├── scrape.py           # Main: fetch all tweets + replies
│   ├── to_markdown.py      # JSON → Markdown converter
│   └── requirements.txt    # twikit
├── data/raw/
│   ├── tweets.json         # All tweets array
│   └── replies/
│       └── {tweet_id}.json # Replies per tweet
├── archive/
│   ├── index.md            # TOC sorted by date
│   ├── posts/
│   │   └── {date}-{tweet_id}.md
│   └── threads/
│       └── {date}-{tweet_id}-thread.md
└── README.md
```

## Scraper Workflow

1. Auth with X using cookies from user's browser
2. Fetch all tweets from @Abombination81 (paginated, newest first)
3. For each tweet, fetch reply threads
4. Save raw JSON to `data/raw/`
5. Generate markdown in `archive/`

## JSON Schema (per tweet)

```json
{
  "id": "string",
  "author": "string",
  "text": "string",
  "created_at": "ISO8601",
  "likes": 0,
  "retweets": 0,
  "media": [{ "type": "photo|video", "url": "string" }],
  "replies": [
    {
      "id": "string",
      "author": "string",
      "text": "string",
      "created_at": "ISO8601",
      "likes": 0
    }
  ]
}
```

## Markdown Format (per post)

```markdown
# Post by @Abombination81 — YYYY-MM-DD

> [tweet text]

**Likes:** N | **Retweets:** N | **Replies:** N

## Replies

### @user1 — YYYY-MM-DD
reply text...
```

## Tech Stack

- Python 3.12+
- twikit (X scraping, no API key)
- asyncio (concurrent reply fetching)

## Auth

User exports cookies from their logged-in X browser session (e.g., via browser extension or manually copying `auth_token` and `ct0` cookies).

## Rate Limiting

- twikit handles rate limits internally
- Add configurable delay between requests as safety margin
- Resume capability: skip already-fetched tweet IDs

## Error Handling

- Save progress after each page of tweets (crash-safe)
- Log failed tweet/reply fetches for retry
- Retry file: `data/raw/failed.json`
