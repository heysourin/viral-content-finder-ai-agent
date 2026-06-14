"""
Reddit Scraper — Uses HTTP requests to fetch hot posts from old.reddit.com.
No login, no API keys, no browser needed. Much faster and more reliable than Playwright.
"""
import asyncio
import re
from html import unescape
from concurrent.futures import ThreadPoolExecutor

import requests

import config


def _strip_html(text: str) -> str:
    """Remove HTML tags from a string."""
    return re.sub(r"<[^>]+>", "", text).strip()


def _parse_posts(html: str, subreddit: str) -> list[dict]:
    """Parse posts from old.reddit.com HTML using data attributes."""
    posts = []

    # Find all "thing" div opening tags (each is a post)
    for match in re.finditer(
        r'<div\s+class="[^"]*\bthing\b[^"]*\blink\b[^"]*"([^>]*)>',
        html,
    ):
        tag = match.group(0)
        pos = match.end()

        # Skip promoted/ad posts
        if 'data-promoted="true"' in tag:
            continue

        # Grab a chunk of HTML after the opening tag to find child elements
        chunk = html[pos : pos + 4000]

        # --- Extract from data attributes on the opening tag ---
        score_m = re.search(r'data-score="(-?\d+)"', tag)
        comments_m = re.search(r'data-comments-count="(\d+)"', tag)
        url_m = re.search(r'data-url="([^"]*)"', tag)
        permalink_m = re.search(r'data-permalink="([^"]*)"', tag)

        # --- Extract title from child <a> tag ---
        title_m = re.search(
            r'<a[^>]*class="[^"]*title[^"]*"[^>]*>(.*?)</a>',
            chunk,
            re.DOTALL,
        )

        title = _strip_html(unescape(title_m.group(1))) if title_m else ""
        if not title:
            continue

        # --- URL: prefer permalink (goes to comments) ---
        post_url = ""
        if permalink_m:
            post_url = f"https://old.reddit.com{permalink_m.group(1)}"
        elif url_m:
            url_val = url_m.group(1)
            post_url = url_val if url_val.startswith("http") else f"https://old.reddit.com{url_val}"

        # --- Timestamp ---
        time_m = re.search(r'datetime="([^"]*)"', chunk)

        # --- Flair ---
        flair_m = re.search(
            r'class="[^"]*linkflairlabel[^"]*"[^>]*title="([^"]*)"',
            chunk,
        )
        if not flair_m:
            flair_m = re.search(
                r'class="[^"]*linkflairlabel[^"]*"[^>]*>([^<]*)<',
                chunk,
            )

        score = int(score_m.group(1)) if score_m else 0
        comments = int(comments_m.group(1)) if comments_m else 0

        posts.append({
            "source": "reddit",
            "subreddit": subreddit,
            "title": title,
            "url": post_url,
            "score": score,
            "comments": comments,
            "flair": unescape(flair_m.group(1).strip()) if flair_m else "",
            "time_posted": time_m.group(1) if time_m else "",
        })

        if len(posts) >= config.REDDIT_POSTS_PER_SUB:
            break

    return posts


def _fetch_subreddit_sync(subreddit: str) -> list[dict]:
    """Fetch hot posts from a single subreddit (synchronous)."""
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "DNT": "1",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
    }
    cookies = {
        "over18": "1",           # bypass age gates
        "_options": '{"pref_quarantine_optin":true}',  # bypass quarantine walls
    }

    url = f"https://old.reddit.com/r/{subreddit}/hot/"

    try:
        resp = requests.get(
            url,
            headers=headers,
            cookies=cookies,
            timeout=15,
            allow_redirects=True,
        )
        resp.raise_for_status()

        # IMPORTANT: unescape HTML entities first — old.reddit.com uses
        # &#32; (encoded spaces) in class names which breaks regex matching
        posts = _parse_posts(unescape(resp.text), subreddit)
        if posts:
            print(f"  ✓ r/{subreddit}: {len(posts)} posts")
        else:
            print(f"  ⚠ r/{subreddit}: page loaded but no posts found")
        return posts

    except requests.exceptions.HTTPError as e:
        print(f"  ⚠ r/{subreddit}: HTTP {e.response.status_code}")
        return []
    except Exception as e:
        print(f"  ⚠ r/{subreddit}: {e}")
        return []


async def scrape_all_subreddits(progress_callback=None) -> list[dict]:
    """
    Scrape all configured subreddits using HTTP requests (no browser needed).

    Args:
        progress_callback: Optional async callable(message: str) for progress updates.

    Returns:
        List of post dicts from all subreddits.
    """
    all_posts = []
    loop = asyncio.get_event_loop()

    if progress_callback:
        await progress_callback("Scraping Reddit (via HTTP — no browser needed)...")

    with ThreadPoolExecutor(max_workers=5) as executor:
        # Run all subreddits concurrently (they're just HTTP requests)
        batch_size = 5
        for i in range(0, len(config.SUBREDDITS), batch_size):
            batch = config.SUBREDDITS[i : i + batch_size]

            if progress_callback:
                names = ", ".join(f"r/{s}" for s in batch)
                await progress_callback(f"Scraping Reddit: {names}")

            futures = [
                loop.run_in_executor(executor, _fetch_subreddit_sync, sub)
                for sub in batch
            ]
            results = await asyncio.gather(*futures)

            for result in results:
                all_posts.extend(result)

    if progress_callback:
        await progress_callback(
            f"Reddit done — found {len(all_posts)} posts across {len(config.SUBREDDITS)} subreddits"
        )

    return all_posts
