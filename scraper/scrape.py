"""
Scrape all tweets and replies from @Abombination81 on X.
Uses direct GraphQL API calls (no twikit dependency).

Usage:
    1. Using browser cookies (recommended):
       python scraper/scrape.py --auth-token AUTH_TOKEN --ct0 CT0_VALUE

    2. Subsequent runs (uses saved cookies):
       python scraper/scrape.py

    To get auth_token and ct0:
       Open x.com in Chrome -> F12 -> Application -> Cookies -> https://x.com
       Copy the values of 'auth_token' and 'ct0'
"""

import asyncio
import json
import sys
import argparse
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import httpx

DEFAULT_TARGET_USER = "Abombination81"
PROJECT_ROOT = Path(__file__).resolve().parent.parent
COOKIES_FILE = PROJECT_ROOT / "scraper" / "cookies.json"


def target_paths(target: str) -> dict:
    data_dir = PROJECT_ROOT / "data" / target / "raw"
    return {
        "data_dir": data_dir,
        "replies_dir": data_dir / "replies",
        "progress_file": data_dir / "progress.json",
        "failed_file": data_dir / "failed.json",
        "tweets_file": data_dir / "tweets.json",
    }

REQUEST_DELAY = 2.5
REPLY_FETCH_DELAY = 3.5
RATE_LIMIT_WAIT = 15 * 60 + 30

BEARER_TOKEN = "AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs%3D1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA"

GRAPHQL_ENDPOINTS = {
    "UserByScreenName": "https://api.x.com/graphql/xmU6X_CKVnQ5lSrCbAmJsg/UserByScreenName",
    "UserTweets": "https://api.x.com/graphql/E3opETHurmVJflFsUBVuUQ/UserTweets",
    "TweetDetail": "https://api.x.com/graphql/nBS-WpgA6ZG0CyNHD517JQ/TweetDetail",
    "SearchTimeline": "https://x.com/i/api/graphql/GcXk9vN_d1jUfHNqLacXQA/SearchTimeline",
}

USER_FEATURES = json.dumps({
    "hidden_profile_subscriptions_enabled": True,
    "rweb_tipjar_consumption_enabled": True,
    "responsive_web_graphql_exclude_directive_enabled": True,
    "verified_phone_label_enabled": False,
    "subscriptions_verification_info_is_identity_verified_enabled": True,
    "subscriptions_verification_info_verified_since_enabled": True,
    "highlights_tweets_tab_ui_enabled": True,
    "responsive_web_twitter_article_notes_tab_enabled": True,
    "subscriptions_feature_can_gift_premium": True,
    "creator_subscriptions_tweet_preview_api_enabled": True,
    "responsive_web_graphql_skip_user_profile_image_extensions_enabled": False,
    "responsive_web_graphql_timeline_navigation_enabled": True,
})

TWEET_FEATURES = json.dumps({
    "rweb_tipjar_consumption_enabled": True,
    "responsive_web_graphql_exclude_directive_enabled": True,
    "verified_phone_label_enabled": False,
    "creator_subscriptions_tweet_preview_api_enabled": True,
    "responsive_web_graphql_timeline_navigation_enabled": True,
    "responsive_web_graphql_skip_user_profile_image_extensions_enabled": False,
    "communities_web_enable_tweet_community_results_fetch": True,
    "c9s_tweet_anatomy_moderator_badge_enabled": True,
    "articles_preview_enabled": True,
    "responsive_web_edit_tweet_api_enabled": True,
    "graphql_is_translatable_rweb_tweet_is_translatable_enabled": True,
    "view_counts_everywhere_api_enabled": True,
    "longform_notetweets_consumption_enabled": True,
    "responsive_web_twitter_article_tweet_consumption_enabled": True,
    "tweet_awards_web_tipping_enabled": False,
    "creator_subscriptions_quote_tweet_preview_enabled": False,
    "freedom_of_speech_not_reach_fetch_enabled": True,
    "standardized_nudges_misinfo": True,
    "tweet_with_visibility_results_prefer_gql_limited_actions_policy_enabled": True,
    "rweb_video_timestamps_enabled": True,
    "longform_notetweets_rich_text_read_enabled": True,
    "longform_notetweets_inline_media_enabled": True,
    "responsive_web_enhance_cards_enabled": False,
})

SEARCH_FEATURES = json.dumps({
    "rweb_video_screen_enabled": False,
    "profile_label_improvements_pcf_label_in_post_enabled": True,
    "responsive_web_profile_redirect_enabled": False,
    "rweb_tipjar_consumption_enabled": False,
    "verified_phone_label_enabled": False,
    "creator_subscriptions_tweet_preview_api_enabled": True,
    "responsive_web_graphql_timeline_navigation_enabled": True,
    "responsive_web_graphql_skip_user_profile_image_extensions_enabled": False,
    "premium_content_api_read_enabled": False,
    "communities_web_enable_tweet_community_results_fetch": True,
    "c9s_tweet_anatomy_moderator_badge_enabled": True,
    "responsive_web_grok_analyze_button_fetch_trends_enabled": False,
    "responsive_web_grok_analyze_post_followups_enabled": True,
    "responsive_web_jetfuel_frame": True,
    "responsive_web_grok_share_attachment_enabled": True,
    "responsive_web_grok_annotations_enabled": True,
    "articles_preview_enabled": True,
    "responsive_web_edit_tweet_api_enabled": True,
    "graphql_is_translatable_rweb_tweet_is_translatable_enabled": True,
    "view_counts_everywhere_api_enabled": True,
    "longform_notetweets_consumption_enabled": True,
    "responsive_web_twitter_article_tweet_consumption_enabled": True,
    "content_disclosure_indicator_enabled": True,
    "content_disclosure_ai_generated_indicator_enabled": True,
    "responsive_web_grok_show_grok_translated_post": False,
    "responsive_web_grok_analysis_button_from_backend": True,
    "post_ctas_fetch_enabled": True,
    "freedom_of_speech_not_reach_fetch_enabled": True,
    "standardized_nudges_misinfo": True,
    "tweet_with_visibility_results_prefer_gql_limited_actions_policy_enabled": True,
    "longform_notetweets_rich_text_read_enabled": True,
    "longform_notetweets_inline_media_enabled": False,
    "responsive_web_grok_image_annotation_enabled": True,
    "responsive_web_grok_imagine_annotation_enabled": True,
    "responsive_web_grok_community_note_auto_translation_is_enabled": False,
    "responsive_web_enhance_cards_enabled": False,
})


@dataclass(frozen=True)
class ReplyData:
    id: str
    author: str
    author_name: str
    text: str
    created_at: str
    likes: int


@dataclass(frozen=True)
class TweetData:
    id: str
    author: str
    author_name: str
    text: str
    created_at: str
    likes: int
    retweets: int
    reply_count: int
    quote_count: int
    views: int = 0
    media: list = field(default_factory=list)
    replies: list = field(default_factory=list)
    is_retweet: bool = False
    url: str = ""


def load_json_file(path: Path) -> any:
    if path.exists():
        return json.loads(path.read_text())
    return None


def save_json_file(path: Path, data: any) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False))


def load_progress(progress_file: Path) -> dict:
    return load_json_file(progress_file) or {
        "fetched_tweet_ids": [],
        "replies_fetched_for": [],
    }


def load_failed(failed_file: Path) -> list:
    return load_json_file(failed_file) or []


class XClient:
    def __init__(self, auth_token: str, ct0: str) -> None:
        self.cookies = {"auth_token": auth_token, "ct0": ct0}
        self.headers = {
            "authorization": f"Bearer {BEARER_TOKEN}",
            "x-csrf-token": ct0,
            "x-twitter-active-user": "yes",
            "x-twitter-auth-type": "OAuth2Session",
            "x-twitter-client-language": "en",
            "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36",
            "content-type": "application/json",
            "referer": "https://x.com/",
        }
        self.client = httpx.AsyncClient(
            cookies=self.cookies,
            headers=self.headers,
            timeout=30.0,
            follow_redirects=True,
        )

    async def close(self) -> None:
        await self.client.aclose()

    async def _get(self, url: str, params: dict) -> dict:
        resp = await self.client.get(url, params=params)
        if resp.status_code == 429:
            print(f"  Rate limited. Waiting {RATE_LIMIT_WAIT}s...")
            await asyncio.sleep(RATE_LIMIT_WAIT)
            resp = await self.client.get(url, params=params)
        resp.raise_for_status()
        return resp.json()

    async def get_user(self, screen_name: str) -> dict:
        params = {
            "variables": json.dumps({"screen_name": screen_name, "withSafetyModeUserFields": True}),
            "features": USER_FEATURES,
        }
        data = await self._get(GRAPHQL_ENDPOINTS["UserByScreenName"], params)
        return data["data"]["user"]["result"]

    async def get_user_tweets(self, user_id: str, cursor: Optional[str] = None) -> tuple[list[dict], Optional[str]]:
        variables = {
            "userId": user_id,
            "count": 40,
            "includePromotedContent": False,
            "withQuickPromoteEligibilityTweetFields": False,
            "withVoice": True,
            "withV2Timeline": True,
        }
        if cursor:
            variables["cursor"] = cursor

        params = {
            "variables": json.dumps(variables),
            "features": TWEET_FEATURES,
        }
        data = await self._get(GRAPHQL_ENDPOINTS["UserTweets"], params)

        tweets = []
        next_cursor = None

        timeline = data.get("data", {}).get("user", {}).get("result", {}).get("timeline_v2", {}).get("timeline", {})
        instructions = timeline.get("instructions", [])

        for instruction in instructions:
            if instruction.get("type") == "TimelineAddEntries":
                for entry in instruction.get("entries", []):
                    entry_id = entry.get("entryId", "")

                    if entry_id.startswith("tweet-"):
                        tweet_result = self._extract_tweet_from_entry(entry)
                        if tweet_result:
                            tweets.append(tweet_result)

                    elif entry_id.startswith("cursor-bottom"):
                        content = entry.get("content", {})
                        next_cursor = content.get("value") or content.get("itemContent", {}).get("value")

        return tweets, next_cursor

    async def search_tweets(self, query: str, cursor: Optional[str] = None) -> tuple[list[dict], Optional[str]]:
        variables = {
            "rawQuery": query,
            "count": 20,
            "querySource": "typed_query",
            "product": "Latest",
            "withGrokTranslatedBio": False,
        }
        if cursor:
            variables["cursor"] = cursor

        params = {
            "variables": json.dumps(variables),
            "features": SEARCH_FEATURES,
        }
        data = await self._get(GRAPHQL_ENDPOINTS["SearchTimeline"], params)

        tweets = []
        next_cursor = None

        timeline = data.get("data", {}).get("search_by_raw_query", {}).get("search_timeline", {}).get("timeline", {})
        instructions = timeline.get("instructions", [])

        for instruction in instructions:
            entries = instruction.get("entries", [])
            if not entries:
                continue
            for entry in entries:
                entry_id = entry.get("entryId", "")
                if entry_id.startswith("tweet-"):
                    tweet_result = self._extract_tweet_from_entry(entry)
                    if tweet_result:
                        tweets.append(tweet_result)
                elif entry_id.startswith("cursor-bottom"):
                    content = entry.get("content", {})
                    next_cursor = content.get("value") or content.get("itemContent", {}).get("value")

        return tweets, next_cursor

    async def get_tweet_detail(self, tweet_id: str) -> list[dict]:
        variables = {
            "focalTweetId": tweet_id,
            "with_rux_injections": False,
            "rankingMode": "Relevance",
            "includePromotedContent": False,
            "withCommunity": True,
            "withQuickPromoteEligibilityTweetFields": False,
            "withBirdwatchNotes": True,
            "withVoice": True,
            "withV2Timeline": True,
        }
        params = {
            "variables": json.dumps(variables),
            "features": TWEET_FEATURES,
        }
        data = await self._get(GRAPHQL_ENDPOINTS["TweetDetail"], params)

        replies = []
        instructions = data.get("data", {}).get("threaded_conversation_with_injections_v2", {}).get("instructions", [])

        for instruction in instructions:
            if instruction.get("type") == "TimelineAddEntries":
                for entry in instruction.get("entries", []):
                    entry_id = entry.get("entryId", "")
                    if entry_id.startswith("conversationthread-"):
                        items = entry.get("content", {}).get("items", [])
                        for item in items:
                            tweet_result = self._extract_tweet_from_item(item)
                            if tweet_result and tweet_result["id"] != tweet_id:
                                replies.append(tweet_result)

        return replies

    def _extract_tweet_from_entry(self, entry: dict) -> Optional[dict]:
        try:
            content = entry.get("content", {})
            item_content = content.get("itemContent", {})
            return self._parse_tweet_result(item_content.get("tweet_results", {}).get("result", {}))
        except (KeyError, TypeError, AttributeError):
            return None

    def _extract_tweet_from_item(self, item: dict) -> Optional[dict]:
        try:
            item_content = item.get("item", {}).get("itemContent", {})
            return self._parse_tweet_result(item_content.get("tweet_results", {}).get("result", {}))
        except (KeyError, TypeError, AttributeError):
            return None

    def _parse_tweet_result(self, result: dict) -> Optional[dict]:
        if not result or result.get("__typename") not in ("Tweet", "TweetWithVisibilityResults"):
            return None

        if result.get("__typename") == "TweetWithVisibilityResults":
            result = result.get("tweet", result)

        core = result.get("core", {}).get("user_results", {}).get("result", {})
        legacy = result.get("legacy", {})
        user_legacy = core.get("legacy", {})

        if not legacy:
            return None

        media = []
        for m in legacy.get("entities", {}).get("media", []):
            media.append({
                "type": m.get("type", "photo"),
                "url": m.get("media_url_https", ""),
            })

        views_data = result.get("views", {})
        views = int(views_data.get("count", 0)) if views_data.get("count") else 0

        screen_name = user_legacy.get("screen_name", "unknown")

        return {
            "id": legacy.get("id_str", result.get("rest_id", "")),
            "author": screen_name,
            "author_name": user_legacy.get("name", "unknown"),
            "text": legacy.get("full_text", ""),
            "created_at": legacy.get("created_at", ""),
            "likes": legacy.get("favorite_count", 0),
            "retweets": legacy.get("retweet_count", 0),
            "reply_count": legacy.get("reply_count", 0),
            "quote_count": legacy.get("quote_count", 0),
            "views": views,
            "media": media,
            "is_retweet": bool(legacy.get("retweeted_status_result")),
            "url": f"https://x.com/{screen_name}/status/{legacy.get('id_str', '')}",
        }


async def fetch_all_tweets(client: XClient, user_id: str, progress: dict, progress_file: Path) -> list[dict]:
    all_tweets = []
    cursor = None
    page = 0

    while True:
        page += 1
        try:
            tweets, next_cursor = await client.get_user_tweets(user_id, cursor)
        except httpx.HTTPStatusError as e:
            print(f"  HTTP error on page {page}: {e.response.status_code}")
            if e.response.status_code == 429:
                await asyncio.sleep(RATE_LIMIT_WAIT)
                continue
            break
        except Exception as e:
            print(f"  Error on page {page}: {e}")
            break

        if not tweets:
            print(f"  Page {page}: no more tweets. Done.")
            break

        batch = []
        for tweet in tweets:
            if tweet["id"] not in progress["fetched_tweet_ids"]:
                batch.append(tweet)
                progress["fetched_tweet_ids"].append(tweet["id"])

        all_tweets.extend(batch)
        print(f"  Page {page}: +{len(batch)} tweets (total: {len(all_tweets)})")

        save_json_file(progress_file, progress)

        if not next_cursor:
            print("  No more pages.")
            break

        cursor = next_cursor
        await asyncio.sleep(REQUEST_DELAY)

    return all_tweets


def generate_date_slices(start_date: str = "2020-01-01", months: int = 2) -> list[tuple[str, str]]:
    """Generate date ranges for sliced searching."""
    slices = []
    start = datetime.strptime(start_date, "%Y-%m-%d")
    end = datetime.now()

    current = start
    while current < end:
        slice_end = current + timedelta(days=months * 30)
        if slice_end > end:
            slice_end = end + timedelta(days=1)
        slices.append((current.strftime("%Y-%m-%d"), slice_end.strftime("%Y-%m-%d")))
        current = slice_end

    return slices


async def fetch_tweets_via_search(client: XClient, screen_name: str, progress: dict, progress_file: Path) -> list[dict]:
    """Use SearchTimeline with date-slicing to get tweets beyond the 3200 timeline limit."""
    all_tweets = []
    date_slices = generate_date_slices("2024-01-01", months=1)

    print(f"  Searching across {len(date_slices)} date slices...")

    for i, (since, until) in enumerate(date_slices):
        query = f"from:{screen_name} since:{since} until:{until}"
        print(f"\n  Slice [{i+1}/{len(date_slices)}]: {since} to {until}")

        cursor = None
        slice_count = 0
        page = 0

        while True:
            page += 1
            try:
                tweets, next_cursor = await client.search_tweets(query, cursor)
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 429:
                    print(f"    Rate limited. Waiting...")
                    await asyncio.sleep(RATE_LIMIT_WAIT)
                    continue
                print(f"    HTTP error: {e.response.status_code}")
                break
            except Exception as e:
                print(f"    Error: {e}")
                break

            if not tweets:
                break

            batch = []
            for tweet in tweets:
                if tweet["id"] not in progress["fetched_tweet_ids"]:
                    batch.append(tweet)
                    progress["fetched_tweet_ids"].append(tweet["id"])

            all_tweets.extend(batch)
            slice_count += len(batch)

            if not next_cursor:
                break

            cursor = next_cursor
            await asyncio.sleep(REQUEST_DELAY)

        if slice_count > 0:
            print(f"    +{slice_count} tweets (running total: {len(all_tweets)})")
            save_json_file(progress_file, progress)

    return all_tweets


async def fetch_replies_for_tweet(client: XClient, tweet_id: str) -> list[dict]:
    try:
        return await client.get_tweet_detail(tweet_id)
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 429:
            print(f"    Rate limited on replies for {tweet_id}. Waiting...")
            await asyncio.sleep(RATE_LIMIT_WAIT)
            return await fetch_replies_for_tweet(client, tweet_id)
        print(f"    HTTP error fetching replies for {tweet_id}: {e.response.status_code}")
    except Exception as e:
        print(f"    Error fetching replies for {tweet_id}: {e}")
    return []


def load_cookies() -> tuple[str, str]:
    if not COOKIES_FILE.exists():
        return "", ""
    data = json.loads(COOKIES_FILE.read_text())
    return data.get("auth_token", ""), data.get("ct0", "")


def save_cookies(auth_token: str, ct0: str) -> None:
    save_json_file(COOKIES_FILE, {"auth_token": auth_token, "ct0": ct0})


async def main() -> None:
    parser = argparse.ArgumentParser(description="Scrape tweets from an X account")
    parser.add_argument("--target", default=DEFAULT_TARGET_USER, help="Target X username (without @)")
    parser.add_argument("--auth-token", help="auth_token cookie from browser DevTools")
    parser.add_argument("--ct0", help="ct0 cookie from browser DevTools")
    parser.add_argument("--skip-replies", action="store_true", help="Skip fetching replies")
    parser.add_argument("--retry-failed", action="store_true", help="Retry failed reply fetches")
    args = parser.parse_args()

    target_user = args.target
    paths = target_paths(target_user)
    data_dir = paths["data_dir"]
    replies_dir = paths["replies_dir"]
    progress_file = paths["progress_file"]
    failed_file = paths["failed_file"]
    tweets_file = paths["tweets_file"]

    data_dir.mkdir(parents=True, exist_ok=True)
    replies_dir.mkdir(parents=True, exist_ok=True)

    # Resolve auth
    auth_token = args.auth_token or ""
    ct0 = args.ct0 or ""

    if not auth_token or not ct0:
        auth_token, ct0 = load_cookies()

    if not auth_token or not ct0:
        print("No auth. Provide --auth-token and --ct0, or run once with them to save cookies.")
        sys.exit(1)

    save_cookies(auth_token, ct0)
    print("Cookies ready.")

    client = XClient(auth_token, ct0)

    try:
        # Get user
        print(f"\nFetching user @{target_user}...")
        user = await client.get_user(target_user)
        user_id = user.get("rest_id", "")
        user_legacy = user.get("legacy", {})
        print(f"Found: {user_legacy.get('name')} (@{user_legacy.get('screen_name')}) — {user_legacy.get('statuses_count', '?')} tweets")

        # Load progress
        progress = load_progress(progress_file)
        failed = load_failed(failed_file)

        # Phase 1: Timeline endpoint (recent tweets)
        print(f"\n--- Phase 1: Timeline endpoint (already have {len(progress['fetched_tweet_ids'])}) ---")
        new_tweets = await fetch_all_tweets(client, user_id, progress, progress_file)
        print(f"  Timeline: {len(new_tweets)} new tweets")

        # Phase 2: Search endpoint with date-slicing (older tweets)
        print(f"\n--- Phase 2: Search with date-slicing (finding older tweets) ---")
        search_tweets = await fetch_tweets_via_search(client, target_user, progress, progress_file)
        print(f"  Search: {len(search_tweets)} additional tweets")

        new_tweets.extend(search_tweets)

        # Merge with existing
        existing_tweets = load_json_file(tweets_file) or []
        existing_ids = {t["id"] for t in existing_tweets}

        for tweet in new_tweets:
            if tweet["id"] not in existing_ids:
                existing_tweets.append(tweet)

        existing_tweets.sort(key=lambda t: t.get("created_at", ""), reverse=True)
        save_json_file(tweets_file, existing_tweets)
        print(f"\nSaved {len(existing_tweets)} total tweets to {tweets_file}")

        # Fetch replies
        if not args.skip_replies:
            tweets_needing_replies = [
                t for t in existing_tweets
                if t["id"] not in progress["replies_fetched_for"]
                and t.get("reply_count", 0) > 0
            ]

            if args.retry_failed:
                retry_ids = set(failed)
                tweets_needing_replies.extend(
                    t for t in existing_tweets if t["id"] in retry_ids
                )
                failed = []

            print(f"\nFetching replies for {len(tweets_needing_replies)} tweets...")
            new_failed = []

            for i, tweet in enumerate(tweets_needing_replies):
                tid = tweet["id"]
                print(f"  [{i+1}/{len(tweets_needing_replies)}] Tweet {tid} ({tweet.get('reply_count', '?')} replies)...")

                replies = await fetch_replies_for_tweet(client, tid)

                if replies:
                    reply_file = replies_dir / f"{tid}.json"
                    save_json_file(reply_file, replies)
                    print(f"    Saved {len(replies)} replies")
                elif tweet.get("reply_count", 0) > 0:
                    new_failed.append(tid)

                progress["replies_fetched_for"].append(tid)
                save_json_file(progress_file, progress)
                await asyncio.sleep(REPLY_FETCH_DELAY)

            if new_failed:
                all_failed = list(set(failed + new_failed))
                save_json_file(failed_file, all_failed)
                print(f"\n{len(new_failed)} tweets failed reply fetch. Saved to {failed_file}")

        print(f"\nDone! Run `python scraper/to_markdown.py --target {target_user}` to generate markdown archive.")

    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(main())
