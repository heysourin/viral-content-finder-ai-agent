"""
X (Twitter) Scraper — Uses Playwright with persistent browser context
to scrape recent tweets from configured accounts.

First run opens a VISIBLE browser so you can log in to X.
The session is saved to browser_data/ for subsequent runs.
"""
import asyncio
import json
import os
import re
from playwright.async_api import async_playwright, BrowserContext

import config


def _parse_engagement(text: str) -> int:
    """Parse engagement numbers like '1.2K', '15M', '340' etc."""
    if not text:
        return 0
    text = text.strip().upper()
    try:
        if "M" in text:
            return int(float(text.replace("M", "").replace(",", "")) * 1_000_000)
        elif "K" in text:
            return int(float(text.replace("K", "").replace(",", "")) * 1_000)
        else:
            return int(re.sub(r"[^\d]", "", text) or 0)
    except (ValueError, TypeError):
        return 0


async def _is_logged_in(context: BrowserContext) -> bool:
    """
    Check if we're logged in by visiting an actual profile page
    and seeing if tweets are visible.
    """
    page = await context.new_page()
    try:
        # Visit a known active account's profile
        await page.goto("https://x.com/AnthropicAI", wait_until="domcontentloaded", timeout=20000)
        await asyncio.sleep(4)

        # Check for login wall indicators in the page content
        content = await page.content()
        login_indicators = [
            "Sign in to X",
            "Log in to X",
            "Refuse non-essential",
            "Sign in</span>",
            "Create your account",
            'href="/i/flow/login"',
        ]

        for indicator in login_indicators:
            if indicator in content:
                print("  ℹ X login wall detected")
                return False

        # Also check if any tweets actually loaded
        tweets = await page.query_selector_all('article[data-testid="tweet"]')
        if len(tweets) > 0:
            print(f"  ✓ X login confirmed ({len(tweets)} tweets visible)")
            return True

        # No login wall but also no tweets — probably need login
        print("  ℹ No tweets visible — likely need login")
        return False

    except Exception as e:
        print(f"  ⚠ Login check failed: {e}")
        return False
    finally:
        await page.close()


async def _prompt_login(context: BrowserContext):
    """Open X login page in the visible browser and wait for the user to log in."""
    page = await context.new_page()
    await page.goto("https://x.com/i/flow/login", wait_until="domcontentloaded", timeout=30000)

    print("\n" + "=" * 60)
    print("  🔐 X (Twitter) Login Required")
    print("=" * 60)
    print("  A browser window has opened at x.com/login.")
    print("  Please log in to your X account.")
    print("  The agent will detect the login automatically...")
    print("=" * 60 + "\n")

    # Wait until we can see tweets on a profile (login confirmed)
    for attempt in range(90):  # 3 minutes max
        await asyncio.sleep(2)
        try:
            url = page.url
            # If we've been redirected to home or away from login flow
            if "home" in url or (
                "x.com" in url
                and "login" not in url
                and "flow" not in url
            ):
                print("  ✅ Login successful! Continuing...\n")
                await asyncio.sleep(2)
                await page.close()
                return
        except Exception:
            pass

    print("  ⚠ Login timeout after 3 minutes. Will try to continue...\n")
    await page.close()


async def _dismiss_popups(page):
    """Try to dismiss cookie consent and other overlays."""
    popup_selectors = [
        # Cookie consent buttons
        '[data-testid="xMigrationBottomBar"] button',
        'button[aria-label="Close"]',
        # "Not now" / "Dismiss" buttons
        'div[role="button"]:has-text("Not now")',
        'div[role="button"]:has-text("Dismiss")',
        # Cookie accept
        'button:has-text("Accept all cookies")',
        'button:has-text("Accept")',
    ]

    for selector in popup_selectors:
        try:
            el = page.locator(selector).first
            if await el.is_visible(timeout=500):
                await el.click()
                await asyncio.sleep(0.5)
        except Exception:
            pass


async def scrape_account(context: BrowserContext, handle: str) -> list[dict]:
    """Scrape recent tweets from a single X account."""
    page = await context.new_page()
    tweets = []

    try:
        url = f"https://x.com/{handle}"
        await page.goto(url, wait_until="domcontentloaded", timeout=25000)

        # Dismiss any popups/overlays
        await _dismiss_popups(page)

        # Wait for tweets with longer timeout
        try:
            await page.wait_for_selector(
                'article[data-testid="tweet"]',
                timeout=20000,
            )
        except Exception:
            # One more try after dismissing popups
            await _dismiss_popups(page)
            try:
                await page.wait_for_selector(
                    'article[data-testid="tweet"]',
                    timeout=10000,
                )
            except Exception:
                print(f"  ⚠ @{handle}: no tweets found (may need login)")
                await page.close()
                return []

        await asyncio.sleep(2)

        # Scroll down to load more tweets
        await page.evaluate("window.scrollBy(0, 2000)")
        await asyncio.sleep(2)

        tweet_elements = await page.query_selector_all(
            'article[data-testid="tweet"]'
        )

        for tweet_el in tweet_elements[: config.X_TWEETS_PER_ACCOUNT]:
            try:
                # Tweet text
                text_el = await tweet_el.query_selector(
                    'div[data-testid="tweetText"]'
                )
                tweet_text = await text_el.inner_text() if text_el else ""

                if not tweet_text.strip():
                    continue

                # Engagement metrics from the group's aria-label
                likes = 0
                retweets = 0
                replies = 0
                views = 0

                group_el = await tweet_el.query_selector('div[role="group"]')
                if group_el:
                    aria_label = await group_el.get_attribute("aria-label") or ""
                    reply_m = re.search(
                        r"(\d[\d,]*)\s*repl", aria_label, re.IGNORECASE
                    )
                    repost_m = re.search(
                        r"(\d[\d,]*)\s*repost", aria_label, re.IGNORECASE
                    )
                    like_m = re.search(
                        r"(\d[\d,]*)\s*like", aria_label, re.IGNORECASE
                    )
                    view_m = re.search(
                        r"(\d[\d,]*)\s*view", aria_label, re.IGNORECASE
                    )

                    replies = (
                        int(reply_m.group(1).replace(",", ""))
                        if reply_m
                        else 0
                    )
                    retweets = (
                        int(repost_m.group(1).replace(",", ""))
                        if repost_m
                        else 0
                    )
                    likes = (
                        int(like_m.group(1).replace(",", ""))
                        if like_m
                        else 0
                    )
                    views = (
                        int(view_m.group(1).replace(",", ""))
                        if view_m
                        else 0
                    )

                # Timestamp
                time_el = await tweet_el.query_selector("time")
                timestamp = (
                    await time_el.get_attribute("datetime") if time_el else ""
                )

                # Tweet link
                link_el = await tweet_el.query_selector(
                    'a[href*="/status/"]'
                )
                tweet_url = ""
                if link_el:
                    tweet_url = await link_el.get_attribute("href")
                    if tweet_url and tweet_url.startswith("/"):
                        tweet_url = f"https://x.com{tweet_url}"

                tweets.append(
                    {
                        "source": "x",
                        "handle": handle,
                        "text": tweet_text.strip(),
                        "url": tweet_url,
                        "likes": likes,
                        "retweets": retweets,
                        "replies": replies,
                        "views": views,
                        "time_posted": timestamp,
                    }
                )

            except Exception:
                continue

        if tweets:
            print(f"  ✓ @{handle}: {len(tweets)} tweets")

    except Exception as e:
        print(f"  ⚠ @{handle}: {e}")
    finally:
        await page.close()

    return tweets


async def scrape_all_accounts(progress_callback=None) -> list[dict]:
    """
    Scrape tweets from all configured X accounts.
    Uses persistent browser context so login session survives across runs.
    Opens a VISIBLE browser on first run for login.
    """
    all_tweets = []

    os.makedirs(config.BROWSER_DATA_DIR, exist_ok=True)

    async with async_playwright() as p:
        # Always start VISIBLE so user can see what's happening
        # (and log in if needed)
        context = await p.chromium.launch_persistent_context(
            user_data_dir=config.BROWSER_DATA_DIR,
            executable_path="/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
            headless=False,
            viewport={"width": 1280, "height": 900},
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
        )

        # Inject cookies from cookies.json if it exists
        cookies_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), "cookies.json")
        if os.path.exists(cookies_file):
            if progress_callback:
                await progress_callback("Loading cookies from cookies.json to bypass login...")
            try:
                with open(cookies_file, "r") as f:
                    raw_cookies = json.load(f)
                pw_cookies = []
                for rc in raw_cookies:
                    pc = {
                        "name": rc.get("name"),
                        "value": rc.get("value"),
                        "domain": rc.get("domain"),
                        "path": rc.get("path", "/"),
                    }
                    if "expirationDate" in rc:
                        pc["expires"] = rc["expirationDate"]
                    if "httpOnly" in rc:
                        pc["httpOnly"] = rc["httpOnly"]
                    if "secure" in rc:
                        pc["secure"] = rc["secure"]
                    
                    # Playwright expects Strict, Lax, None. Map or drop.
                    same_site = rc.get("sameSite", "").lower()
                    if same_site in ["strict", "lax"]:
                        pc["sameSite"] = same_site.capitalize()
                    elif same_site in ["no_restriction", "none"]:
                        pc["sameSite"] = "None"
                    
                    pw_cookies.append(pc)
                await context.add_cookies(pw_cookies)
                print(f"  ✓ Injected {len(pw_cookies)} cookies from cookies.json")
            except Exception as e:
                print(f"  ⚠ Failed to load cookies.json: {e}")

        # Check login status by actually looking for tweets
        if progress_callback:
            await progress_callback("Checking X login status...")

        logged_in = await _is_logged_in(context)

        if not logged_in:
            if progress_callback:
                await progress_callback(
                    "⚠ X login required — a browser window has opened. Please log in!"
                )
            await _prompt_login(context)

            # Trust that _prompt_login succeeded if it didn't throw/timeout
            logged_in = True
            
            # Give X an extra moment to settle cookies after manual login
            await asyncio.sleep(5)

        # Scrape accounts one at a time (X is stricter about rate limits)
        batch_size = 2
        for i in range(0, len(config.X_ACCOUNTS), batch_size):
            batch = config.X_ACCOUNTS[i : i + batch_size]

            if progress_callback:
                names = ", ".join(f"@{a}" for a in batch)
                await progress_callback(f"Scraping X: {names}")

            tasks = [scrape_account(context, handle) for handle in batch]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            for result in results:
                if isinstance(result, list):
                    all_tweets.extend(result)

            # Delay between batches to avoid rate limits
            if i + batch_size < len(config.X_ACCOUNTS):
                await asyncio.sleep(3)

        await context.close()

    if progress_callback:
        await progress_callback(
            f"X done — found {len(all_tweets)} tweets across {len(config.X_ACCOUNTS)} accounts"
        )

    return all_tweets
