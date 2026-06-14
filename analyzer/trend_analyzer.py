"""
Trend Analyzer — Scores, ranks, and groups scraped posts by virality.
"""
import re
from collections import defaultdict

import config


def _compute_reddit_virality(post: dict) -> float:
    """Compute virality score for a Reddit post."""
    score = post.get("score", 0)
    comments = post.get("comments", 0)
    return score * 0.7 + comments * 0.3


def _compute_x_virality(tweet: dict) -> float:
    """Compute virality score for an X tweet."""
    likes = tweet.get("likes", 0)
    retweets = tweet.get("retweets", 0)
    replies = tweet.get("replies", 0)
    return likes + retweets * 2 + replies * 1.5


def _normalize_scores(posts: list[dict], key: str = "virality_score") -> list[dict]:
    """Normalize scores to 0-100 scale within a group."""
    if not posts:
        return posts

    max_score = max(p.get(key, 0) for p in posts)
    if max_score == 0:
        return posts

    for post in posts:
        post["normalized_score"] = round((post.get(key, 0) / max_score) * 100, 1)

    return posts


def _extract_keywords(text: str) -> set[str]:
    """Extract meaningful keywords from text for topic grouping."""
    # Common stop words to filter out
    stop_words = {
        "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
        "have", "has", "had", "do", "does", "did", "will", "would", "could",
        "should", "may", "might", "can", "shall", "to", "of", "in", "for",
        "on", "with", "at", "by", "from", "as", "into", "about", "like",
        "through", "after", "over", "between", "out", "against", "during",
        "without", "before", "under", "around", "among", "it", "its",
        "this", "that", "these", "those", "i", "me", "my", "we", "our",
        "you", "your", "he", "she", "they", "them", "his", "her", "their",
        "what", "which", "who", "when", "where", "why", "how", "all",
        "each", "every", "both", "few", "more", "most", "some", "any",
        "no", "not", "only", "own", "same", "so", "than", "too", "very",
        "just", "don", "now", "and", "but", "or", "if", "then", "else",
        "new", "get", "got", "use", "using", "used", "one", "two",
    }

    words = re.findall(r"[a-zA-Z]{3,}", text.lower())
    return {w for w in words if w not in stop_words}


def analyze_trends(reddit_posts: list[dict], x_tweets: list[dict]) -> dict:
    """
    Analyze and rank all posts by virality.
    
    Returns:
        {
            "top_reddit": [...],    # Top Reddit posts sorted by virality
            "top_x": [...],         # Top X tweets sorted by virality
            "top_combined": [...],  # Top posts across both platforms
            "summary_stats": {...}  # Quick stats
        }
    """
    # Score Reddit posts
    for post in reddit_posts:
        post["virality_score"] = _compute_reddit_virality(post)

    # Score X tweets
    for tweet in x_tweets:
        tweet["virality_score"] = _compute_x_virality(tweet)

    # Sort by virality
    reddit_sorted = sorted(reddit_posts, key=lambda p: p["virality_score"], reverse=True)
    x_sorted = sorted(x_tweets, key=lambda p: p["virality_score"], reverse=True)

    # Normalize within each source
    reddit_sorted = _normalize_scores(reddit_sorted)
    x_sorted = _normalize_scores(x_sorted)

    # Combined ranking (use normalized scores so Reddit and X are comparable)
    combined = reddit_sorted + x_sorted
    combined = sorted(combined, key=lambda p: p.get("normalized_score", 0), reverse=True)

    # Summary stats
    stats = {
        "total_reddit_posts": len(reddit_posts),
        "total_x_tweets": len(x_tweets),
        "subreddits_scraped": len(set(p.get("subreddit", "") for p in reddit_posts)),
        "x_accounts_scraped": len(set(t.get("handle", "") for t in x_tweets)),
        "top_subreddit": _top_subreddit(reddit_sorted),
        "top_x_account": _top_x_account(x_sorted),
    }

    return {
        "top_reddit": reddit_sorted[:100],
        "top_x": x_sorted[:100],
        "top_combined": combined[:config.TOP_POSTS_FOR_AI],
        "summary_stats": stats,
    }


def _top_subreddit(posts: list[dict]) -> str:
    """Find subreddit with highest average virality."""
    if not posts:
        return "N/A"
    sub_scores = defaultdict(list)
    for p in posts:
        sub_scores[p.get("subreddit", "")].append(p.get("virality_score", 0))
    
    best = max(sub_scores.items(), key=lambda x: sum(x[1]) / len(x[1]))
    return best[0]


def _top_x_account(tweets: list[dict]) -> str:
    """Find X account with highest average engagement."""
    if not tweets:
        return "N/A"
    account_scores = defaultdict(list)
    for t in tweets:
        account_scores[t.get("handle", "")].append(t.get("virality_score", 0))
    
    best = max(account_scores.items(), key=lambda x: sum(x[1]) / len(x[1]))
    return f"@{best[0]}"
