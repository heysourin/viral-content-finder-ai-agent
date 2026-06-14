"""
TrendPulse — AI Content Idea Agent
Flask server with SSE-based real-time progress.

Usage:
    python run.py
"""
import asyncio
import json
import sys
import threading
import time
import webbrowser
from queue import Queue

from flask import Flask, render_template, Response

import config
from scrapers.reddit_scraper import scrape_all_subreddits
from scrapers.x_scraper import scrape_all_accounts
from analyzer.trend_analyzer import analyze_trends
from generator.idea_generator import generate_ideas

app = Flask(__name__)
LAST_ANALYSIS_CACHE = None


@app.route("/")
def index():
    """Serve the dashboard."""
    return render_template("index.html")


@app.route("/api/scan")
def scan():
    """
    SSE endpoint that runs the full scrape → analyze → generate pipeline.
    Streams progress events and finally the results.
    """
    def event_stream():
        message_queue = Queue()

        def run_pipeline():
            """Run the async pipeline in a separate thread."""
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            async def _progress(msg: str):
                message_queue.put(("progress", msg))

            async def _run():
                try:
                    # Phase 1: Scrape Reddit
                    await _progress("Starting Reddit scraper...")
                    reddit_posts = await scrape_all_subreddits(progress_callback=_progress)

                    # Phase 2: Scrape X
                    await _progress("Starting X (Twitter) scraper...")
                    x_tweets = await scrape_all_accounts(progress_callback=_progress)

                    # Phase 3: Analyze trends
                    await _progress("Analyzing trends and scoring virality...")
                    analysis = analyze_trends(reddit_posts, x_tweets)
                    
                    global LAST_ANALYSIS_CACHE
                    LAST_ANALYSIS_CACHE = analysis

                    # Phase 4: Generate content ideas
                    await _progress("Sending top trends to Gemini AI...")
                    ideas_result = await generate_ideas(
                        analysis["top_combined"],
                        progress_callback=_progress,
                    )

                    # Combine final result
                    result = {
                        "top_reddit": analysis["top_reddit"],
                        "top_x": analysis["top_x"],
                        "summary_stats": analysis["summary_stats"],
                        "trend_summary": ideas_result.get("trend_summary", ""),
                        "ideas": ideas_result.get("ideas", []),
                    }

                    await _progress("All done! Rendering results...")
                    message_queue.put(("result", json.dumps(result)))

                except Exception as e:
                    message_queue.put(("error_msg", str(e)))
                    message_queue.put(("result", json.dumps({
                        "top_reddit": [],
                        "top_x": [],
                        "summary_stats": {},
                        "trend_summary": f"Error: {str(e)}",
                        "ideas": [],
                    })))

                finally:
                    message_queue.put(("done", ""))

            loop.run_until_complete(_run())
            loop.close()

        # Start the pipeline in a background thread
        thread = threading.Thread(target=run_pipeline, daemon=True)
        thread.start()

        # Stream events from the queue
        while True:
            event_type, data = message_queue.get()

            if event_type == "done":
                break

            yield f"event: {event_type}\ndata: {data}\n\n"

    return Response(
        event_stream(),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


@app.route("/api/retry_ai")
def retry_ai():
    """
    SSE endpoint that ONLY runs the Gemini AI generation using cached scraped data.
    """
    def event_stream():
        message_queue = Queue()

        def run_pipeline():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            async def _progress(msg: str):
                message_queue.put(("progress", msg))

            async def _run():
                global LAST_ANALYSIS_CACHE
                try:
                    if not LAST_ANALYSIS_CACHE:
                        raise ValueError("No cached data available. Please run a full scan first.")

                    analysis = LAST_ANALYSIS_CACHE
                    
                    # Phase 4: Generate content ideas
                    await _progress("Resending top trends to Gemini AI...")
                    ideas_result = await generate_ideas(
                        analysis["top_combined"],
                        progress_callback=_progress,
                    )

                    # Combine final result
                    result = {
                        "top_reddit": analysis["top_reddit"],
                        "top_x": analysis["top_x"],
                        "summary_stats": analysis["summary_stats"],
                        "trend_summary": ideas_result.get("trend_summary", ""),
                        "ideas": ideas_result.get("ideas", []),
                    }

                    await _progress("All done! Rendering results...")
                    message_queue.put(("result", json.dumps(result)))

                except Exception as e:
                    message_queue.put(("error_msg", str(e)))
                    message_queue.put(("result", json.dumps({
                        "top_reddit": [],
                        "top_x": [],
                        "summary_stats": {},
                        "trend_summary": f"Error: {str(e)}",
                        "ideas": [],
                    })))

                finally:
                    message_queue.put(("done", ""))

            loop.run_until_complete(_run())
            loop.close()

        thread = threading.Thread(target=run_pipeline, daemon=True)
        thread.start()

        while True:
            event_type, data = message_queue.get()
            if event_type == "done":
                break
            yield f"event: {event_type}\ndata: {data}\n\n"

    return Response(
        event_stream(),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


def open_browser():
    """Open the dashboard in the default browser after a short delay."""
    time.sleep(1.5)
    url = f"http://{config.HOST}:{config.PORT}"
    print(f"\n  🌐 Opening dashboard: {url}\n")
    webbrowser.open(url)


def main():
    # Check for Gemini API key
    if not config.GEMINI_API_KEY:
        print("\n" + "=" * 55)
        print("  ⚠  GEMINI_API_KEY not found!")
        print("=" * 55)
        print("  1. Get a free key: https://aistudio.google.com/apikey")
        print("  2. Create a .env file with:")
        print("     GEMINI_API_KEY=your_key_here")
        print("=" * 55)
        print("\n  The agent will still scrape Reddit and X,")
        print("  but won't generate AI content ideas.\n")

    print("\n" + "=" * 55)
    print("  ⚡ TrendPulse — AI Content Idea Agent")
    print("=" * 55)
    print(f"  Dashboard: http://{config.HOST}:{config.PORT}")
    print("  Press Ctrl+C to stop")
    print("=" * 55 + "\n")

    # Open browser in background
    threading.Thread(target=open_browser, daemon=True).start()

    # Start Flask
    app.run(
        host=config.HOST,
        port=config.PORT,
        debug=False,
        threaded=True,
    )


if __name__ == "__main__":
    main()
