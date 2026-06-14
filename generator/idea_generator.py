"""
Content Idea Generator — Uses Gemini AI to generate content ideas
based on trending posts from Reddit and X.
"""
import asyncio
import json
import re
from google import genai

import config


def _build_prompt(top_posts: list[dict]) -> str:
    """Build the prompt for Gemini with trending post data."""

    # Format Reddit posts
    reddit_section = ""
    x_section = ""

    for i, post in enumerate(top_posts, 1):
        if post.get("source") == "reddit":
            reddit_section += (
                f"{i}. [r/{post.get('subreddit', 'unknown')}] \"{post.get('title', '')}\"\n"
                f"   Score: {post.get('score', 0)} upvotes, {post.get('comments', 0)} comments\n"
                f"   Virality: {post.get('normalized_score', 0)}/100\n\n"
            )
        elif post.get("source") == "x":
            text = post.get("text", "")[:200]  # Truncate long tweets
            x_section += (
                f"{i}. [@{post.get('handle', 'unknown')}] \"{text}\"\n"
                f"   Engagement: {post.get('likes', 0)} likes, {post.get('retweets', 0)} retweets, {post.get('replies', 0)} replies\n"
                f"   Virality: {post.get('normalized_score', 0)}/100\n\n"
            )

    prompt = f"""You are a content strategist for a creator who covers AI, machine learning, coding tools, and tech. 
Analyze these trending posts from Reddit and X (Twitter) and generate content ideas.

=== TRENDING REDDIT POSTS ===
{reddit_section if reddit_section else "No Reddit data available."}

=== TRENDING X (TWITTER) POSTS ===
{x_section if x_section else "No X data available."}

Based on these viral trends, generate exactly {config.CONTENT_IDEAS_COUNT} content ideas exclusively for SHORT-FORM VIDEO (Instagram Reels, TikTok, YouTube Shorts).

CRITICAL REQUIREMENT - MUST BE TRANSFORMATIVE:
Do NOT just summarize the information. You must transform the original information into a highly engaging, opinionated, or actionable video concept designed specifically to convert viewers into followers.
Transform the content by adding:
- A contrarian take or strong opinion
- A "how this actually affects you" breakdown
- A step-by-step actionable tutorial derived from the news
- A dramatic shift in perspective

For EACH idea, provide:
1. **title**: A catchy, specific video title (not generic)
2. **hook**: An aggressive, attention-grabbing spoken hook (first 3 seconds)
3. **format**: "Instagram Reel / TikTok / YouTube Short"
4. **why_viral**: 1-2 sentences explaining why this specific *transformative angle* will convert viewers to followers based on current trends.
5. **talking_points**: 3-5 key script beats to cover the transformation
6. **source_trends**: Which trending posts inspired this idea (reference by subreddit or handle)

Return your response as valid JSON in this exact format:
{{
  "ideas": [
    {{
      "title": "...",
      "hook": "...",
      "format": "Instagram Reel",
      "why_viral": "...",
      "talking_points": ["...", "...", "..."],
      "source_trends": ["...", "..."]
    }}
  ],
  "trend_summary": "A 2-3 sentence overview of the biggest AI/tech themes trending right now."
}}

IMPORTANT: 
- EVERY idea must be a short-form video.
- EVERY idea must be transformative, not just reporting the news.
- Return ONLY valid JSON, no markdown formatting or code blocks.
"""
    return prompt


def _extract_json(text: str) -> dict:
    """Extract JSON from Gemini response, handling markdown code blocks."""
    # Try to find JSON in code blocks first
    code_block_match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
    if code_block_match:
        text = code_block_match.group(1)
    
    # Try to parse the text as JSON
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Try to find JSON object in the text
        json_match = re.search(r"\{.*\}", text, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(0))
            except json.JSONDecodeError:
                pass
    
    return {"ideas": [], "trend_summary": "Failed to parse AI response."}


async def generate_ideas(top_posts: list[dict], progress_callback=None) -> dict:
    """
    Generate content ideas using Gemini AI based on trending posts.
    
    Args:
        top_posts: List of top trending posts (Reddit + X combined).
        progress_callback: Optional async callable for progress updates.
    
    Returns:
        Dict with 'ideas' list and 'trend_summary' string.
    """
    if not config.GEMINI_API_KEY:
        return {
            "ideas": [],
            "trend_summary": "⚠ No Gemini API key configured. Add GEMINI_API_KEY to your .env file.",
            "error": True,
        }

    if progress_callback:
        await progress_callback("Generating content ideas with Gemini AI...")

    try:
        client = genai.Client(api_key=config.GEMINI_API_KEY)
        prompt = _build_prompt(top_posts)

        # Retry logic with model fallback for 503 errors
        max_retries = 3
        response = None
        current_model = "gemini-2.5-flash"
        
        for attempt in range(max_retries):
            try:
                response = await client.aio.models.generate_content(
                    model=current_model,
                    contents=prompt,
                )
                break  # Success
            except Exception as e:
                err_str = str(e)
                if "503" in err_str or "UNAVAILABLE" in err_str:
                    if attempt < max_retries - 1:
                        if progress_callback:
                            await progress_callback(f"⚠ Gemini API busy (503). Retrying in {2 * (attempt + 1)}s...")
                        await asyncio.sleep(2 * (attempt + 1))
                        
                        # Fallback to an older model on the last retry
                        if attempt == max_retries - 2:
                            current_model = "gemini-1.5-flash"
                        continue
                # If it's not a 503 or we ran out of retries, raise it
                raise e

        if not response:
            raise Exception("Failed to get response from Gemini after retries")

        result = _extract_json(response.text)

        if progress_callback:
            idea_count = len(result.get("ideas", []))
            await progress_callback(f"Gemini generated {idea_count} content ideas!")

        return result

    except Exception as e:
        error_msg = f"Gemini API error: {str(e)}"
        if progress_callback:
            await progress_callback(f"⚠ {error_msg}")

        return {
            "ideas": [],
            "trend_summary": error_msg,
            "error": True,
        }
