"""
Browser-based scraper for X/Twitter search.
Injects fetch calls into the browser via Chrome DevTools MCP.
Saves results to data/raw/ as JSON, then generates markdown.

This script generates JavaScript snippets that should be run
in the browser console on x.com (where you're logged in).
The browser handles auth, transaction IDs, and anti-bot measures.

Usage:
    1. Open x.com in Chrome and log in
    2. Open DevTools console (F12)
    3. Run: python scraper/browser_scrape.py > /tmp/scrape.js
    4. Paste the output into the console

    OR use the automated approach with Chrome DevTools MCP.
"""

import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data" / "raw"

# This generates a self-contained JS script that runs in the browser
SCRAPE_JS = """
(async () => {
  const TARGET = "Abombination81";
  const DELAY = 3000;
  const MAX_PAGES = 200;

  const allTweets = [];
  const seenIds = new Set();
  let cursor = null;
  let page = 0;

  // Get CSRF token from cookies
  const ct0 = document.cookie.match(/ct0=([^;]+)/)?.[1] || "";
  if (!ct0) {
    // Try from meta tag
    const meta = document.querySelector('meta[name="csrf-token"]');
  }

  const FEATURES = %FEATURES%;

  async function searchPage(query, cursor) {
    const variables = {
      rawQuery: query,
      count: 20,
      querySource: "typed_query",
      product: "Latest",
      withGrokTranslatedBio: false,
    };
    if (cursor) variables.cursor = cursor;

    const params = new URLSearchParams({
      variables: JSON.stringify(variables),
      features: JSON.stringify(FEATURES),
    });

    const r = await fetch(`/i/api/graphql/GcXk9vN_d1jUfHNqLacXQA/SearchTimeline?${params}`, {
      credentials: "include",
      headers: {
        "x-csrf-token": ct0,
        "x-twitter-auth-type": "OAuth2Session",
        "x-twitter-active-user": "yes",
        "authorization": "Bearer AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs%%3D1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA",
        "content-type": "application/json",
      },
    });

    if (r.status === 429) {
      console.log("Rate limited, waiting 16 min...");
      await new Promise(resolve => setTimeout(resolve, 16 * 60 * 1000));
      return searchPage(query, cursor);
    }

    if (!r.ok) {
      console.error(`HTTP ${r.status}`);
      return { tweets: [], cursor: null };
    }

    const data = await r.json();
    const instructions = data?.data?.search_by_raw_query?.search_timeline?.timeline?.instructions || [];

    const tweets = [];
    let nextCursor = null;

    for (const inst of instructions) {
      for (const entry of (inst.entries || [])) {
        if (entry.entryId?.startsWith("tweet-")) {
          const result = entry.content?.itemContent?.tweet_results?.result;
          const tweet = parseTweet(result);
          if (tweet) tweets.push(tweet);
        }
        if (entry.entryId?.startsWith("cursor-bottom")) {
          nextCursor = entry.content?.value;
        }
      }
    }

    return { tweets, cursor: nextCursor };
  }

  function parseTweet(result) {
    if (!result) return null;
    if (result.__typename === "TweetWithVisibilityResults") result = result.tweet;
    if (!result?.legacy) return null;

    const legacy = result.legacy;
    const user = result.core?.user_results?.result?.legacy || {};
    const views = result.views?.count ? parseInt(result.views.count) : 0;

    const media = [];
    for (const m of (legacy.entities?.media || [])) {
      media.push({ type: m.type || "photo", url: m.media_url_https || "" });
    }

    return {
      id: legacy.id_str || result.rest_id || "",
      author: user.screen_name || "unknown",
      author_name: user.name || "unknown",
      text: legacy.full_text || "",
      created_at: legacy.created_at || "",
      likes: legacy.favorite_count || 0,
      retweets: legacy.retweet_count || 0,
      reply_count: legacy.reply_count || 0,
      quote_count: legacy.quote_count || 0,
      views: views,
      media: media,
      is_retweet: !!legacy.retweeted_status_result,
      url: `https://x.com/${user.screen_name}/status/${legacy.id_str}`,
    };
  }

  // Date slices for comprehensive search
  const slices = [];
  const now = new Date();
  let d = new Date("2024-01-01");
  while (d < now) {
    const end = new Date(d);
    end.setMonth(end.getMonth() + 1);
    if (end > now) end.setTime(now.getTime() + 86400000);
    slices.push([d.toISOString().split("T")[0], end.toISOString().split("T")[0]]);
    d = end;
  }

  console.log(`Searching ${slices.length} date slices for from:${TARGET}`);

  for (let i = 0; i < slices.length; i++) {
    const [since, until] = slices[i];
    const query = `from:${TARGET} since:${since} until:${until}`;
    console.log(`Slice [${i+1}/${slices.length}]: ${since} to ${until}`);

    cursor = null;
    let sliceCount = 0;

    while (true) {
      const result = await searchPage(query, cursor);

      for (const tweet of result.tweets) {
        if (!seenIds.has(tweet.id)) {
          seenIds.add(tweet.id);
          allTweets.push(tweet);
          sliceCount++;
        }
      }

      if (!result.cursor || result.tweets.length === 0) break;
      cursor = result.cursor;
      await new Promise(resolve => setTimeout(resolve, DELAY));
    }

    if (sliceCount > 0) console.log(`  +${sliceCount} tweets (total: ${allTweets.length})`);
    await new Promise(resolve => setTimeout(resolve, DELAY));
  }

  // Also search without date filter for anything missed
  console.log("Final pass: no date filter");
  cursor = null;
  let passes = 0;
  while (passes < MAX_PAGES) {
    passes++;
    const result = await searchPage(`from:${TARGET}`, cursor);
    let newCount = 0;
    for (const tweet of result.tweets) {
      if (!seenIds.has(tweet.id)) {
        seenIds.add(tweet.id);
        allTweets.push(tweet);
        newCount++;
      }
    }
    if (newCount > 0) console.log(`  Pass ${passes}: +${newCount} (total: ${allTweets.length})`);
    if (!result.cursor || result.tweets.length === 0) break;
    cursor = result.cursor;
    await new Promise(resolve => setTimeout(resolve, DELAY));
  }

  console.log(`\\nDone! Total: ${allTweets.length} tweets`);

  // Store in window for retrieval
  window.__SCRAPED_TWEETS = allTweets;

  // Also trigger download
  const blob = new Blob([JSON.stringify(allTweets, null, 2)], {type: "application/json"});
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = "abombination81_tweets.json";
  a.click();
  URL.revokeObjectURL(url);

  return { total: allTweets.length, sample: allTweets.slice(0, 3).map(t => t.text.substring(0, 80)) };
})()
"""

FEATURES = {
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
}

if __name__ == "__main__":
    js = SCRAPE_JS.replace("%FEATURES%", json.dumps(FEATURES))
    print(js)
