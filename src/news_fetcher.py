"""
News Fetcher module for LinkedIn Daily Bot.
Fetches fresh news (past 24 hours) across configured topics,
deduplicates against SQLite database, and handles daily topic rotation.
"""

from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
import html
import logging
import re
import time
from typing import List, Optional, Dict
import urllib.parse
import feedparser
import requests

from .config import Config, TopicConfig
from .database import Database, clean_url

logger = logging.getLogger(__name__)

# User-Agent header for HTTP requests
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}


@dataclass
class NewsStory:
    """Represents a fresh news article."""
    topic_id: str
    topic_name: str
    title: str
    url: str
    summary: str
    source: str
    published_at: datetime
    importance_score: float = 0.0

    def to_dict(self) -> dict:
        return {
            "topic_id": self.topic_id,
            "topic_name": self.topic_name,
            "title": self.title,
            "url": self.url,
            "summary": self.summary,
            "source": self.source,
            "published_at": self.published_at.isoformat(),
            "importance_score": self.importance_score,
        }


def strip_html(raw_html: str) -> str:
    """Strip HTML tags and unescape entities."""
    if not raw_html:
        return ""
    text = re.sub(r"<[^>]+>", " ", raw_html)
    text = html.unescape(text)
    return " ".join(text.split())


class NewsFetcher:
    """Fetches, deduplicates, and ranks news articles."""

    def __init__(self, config: Config, database: Database):
        self.config = config
        self.db = database

    def fetch_google_news_rss(self, topic: TopicConfig, max_results: int = 15) -> List[NewsStory]:
        """Fetch news from Google News RSS using the topic's search query."""
        encoded_query = urllib.parse.quote(topic.rss_query)
        rss_url = f"https://news.google.com/rss/search?q={encoded_query}&hl=en-US&gl=US&ceid=US:en"

        stories: List[NewsStory] = []
        try:
            response = requests.get(rss_url, headers=HEADERS, timeout=12)
            if response.status_code != 200:
                logger.warning(f"Google News RSS returned status {response.status_code} for query: {topic.rss_query}")
                return []

            feed = feedparser.parse(response.content)
            now_utc = datetime.now(timezone.utc)
            # Accept news up to 30 hours old to account for timezones
            cutoff_time = now_utc - timedelta(hours=30)

            for entry in feed.entries[:max_results]:
                title = entry.get("title", "").strip()
                url = entry.get("link", "").strip()
                summary_raw = entry.get("summary", "")
                summary = strip_html(summary_raw)

                # Source name
                source = "News Outlet"
                if "source" in entry and isinstance(entry["source"], dict):
                    source = entry["source"].get("title", source)
                elif " - " in title:
                    parts = title.rsplit(" - ", 1)
                    title = parts[0].strip()
                    source = parts[1].strip()

                # Parse publication time
                published_at = now_utc
                if "published_parsed" in entry and entry["published_parsed"]:
                    try:
                        published_at = datetime.fromtimestamp(
                            time.mktime(entry["published_parsed"]),
                            tz=timezone.utc
                        )
                    except Exception:
                        published_at = now_utc

                # Freshness check: must be within the cutoff window
                if published_at < cutoff_time:
                    continue

                if not title or not url:
                    continue

                # Calculate basic importance score
                hours_old = max(0.1, (now_utc - published_at).total_seconds() / 3600)
                freshness_factor = 1.0 / (1.0 + (hours_old / 6.0))  # higher if more recent
                
                # Check for major tier-1 tech publications
                reputable_domains = [
                    "reuters", "bloomberg", "wsj", "techcrunch", "theverge",
                    "wired", "cnbc", "ft.com", "ars technica", "nature", "mit technology review"
                ]
                source_bonus = 1.3 if any(d in source.lower() for d in reputable_domains) else 1.0
                importance_score = round(freshness_factor * source_bonus * 10, 2)

                stories.append(NewsStory(
                    topic_id=topic.id,
                    topic_name=topic.name,
                    title=title,
                    url=clean_url(url),
                    summary=summary,
                    source=source,
                    published_at=published_at,
                    importance_score=importance_score,
                ))

        except Exception as e:
            logger.error(f"Error fetching Google News RSS for {topic.name}: {e}")

        return stories

    def fetch_newsapi(self, topic: TopicConfig, max_results: int = 15) -> List[NewsStory]:
        """Fetch news from NewsAPI if configured."""
        if not self.config.news_api_key:
            return []

        yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d")
        url = "https://newsapi.org/v2/everything"
        params = {
            "q": topic.search_keywords,
            "from": yesterday,
            "sortBy": "relevancy",
            "pageSize": max_results,
            "language": "en",
            "apiKey": self.config.news_api_key,
        }

        stories: List[NewsStory] = []
        try:
            res = requests.get(url, params=params, headers=HEADERS, timeout=10)
            if res.status_code == 200:
                data = res.json()
                for art in data.get("articles", []):
                    title = art.get("title", "")
                    art_url = art.get("url", "")
                    if not title or not art_url or title == "[Removed]":
                        continue
                    pub_str = art.get("publishedAt", "")
                    try:
                        pub_dt = datetime.fromisoformat(pub_str.replace("Z", "+00:00"))
                    except Exception:
                        pub_dt = datetime.now(timezone.utc)

                    stories.append(NewsStory(
                        topic_id=topic.id,
                        topic_name=topic.name,
                        title=title,
                        url=clean_url(art_url),
                        summary=art.get("description", "") or "",
                        source=art.get("source", {}).get("name", "NewsAPI"),
                        published_at=pub_dt,
                        importance_score=8.0,
                    ))
        except Exception as e:
            logger.error(f"Error fetching NewsAPI for {topic.name}: {e}")
        return stories

    def fetch_for_topic(self, topic_id: str) -> List[NewsStory]:
        """Fetch stories for a topic using configured provider and deduplicate."""
        topic = self.config.topics.get(topic_id)
        if not topic:
            logger.error(f"Unknown topic_id: {topic_id}")
            return []

        # 1. Fetch from source
        if self.config.news_source == "newsapi" and self.config.news_api_key:
            stories = self.fetch_newsapi(topic)
        else:
            stories = self.fetch_google_news_rss(topic)

        # 2. Filter duplicates against local SQLite database
        fresh_stories: List[NewsStory] = []
        for story in stories:
            if self.db.is_url_posted(story.url):
                logger.debug(f"Skipping already posted URL: {story.url}")
                continue
            if self.db.is_similar_title_posted(story.title):
                logger.debug(f"Skipping similar headline: {story.title}")
                continue
            fresh_stories.append(story)

        # Sort by importance / freshness
        fresh_stories.sort(key=lambda s: s.importance_score, reverse=True)
        return fresh_stories

    def select_story_of_the_day(
        self,
        force_topic_id: Optional[str] = None
    ) -> Optional[NewsStory]:
        """
        Select the single best story of the day:
        - Rotates topics: never picks the same topic on consecutive days.
        - Prioritizes topics posted least recently.
        - Skips if no good fresh news is found.
        """
        all_topic_ids = list(self.config.topics.keys())

        if force_topic_id:
            if force_topic_id not in self.config.topics:
                raise ValueError(f"Invalid force_topic_id '{force_topic_id}'. Valid: {all_topic_ids}")
            eligible_topic_ids = [force_topic_id]
            logger.info(f"Topic forced via flag: {force_topic_id}")
        else:
            last_posted_topic = self.db.get_last_posted_topic()
            logger.info(f"Last posted topic: {last_posted_topic}")

            # Exclude last posted topic to guarantee rotation across consecutive days
            if last_posted_topic and last_posted_topic in all_topic_ids:
                eligible_topic_ids = [tid for tid in all_topic_ids if tid != last_posted_topic]
            else:
                eligible_topic_ids = all_topic_ids

            # Sort eligible topics by least posted frequency in the past 14 days
            topic_counts = self.db.get_topic_counts(days_lookback=14)
            eligible_topic_ids.sort(key=lambda tid: topic_counts.get(tid, 0))
            logger.info(f"Eligible topics for today (sorted by rotation priority): {eligible_topic_ids}")

        # Try to find the top story among eligible topics
        best_candidate: Optional[NewsStory] = None

        for topic_id in eligible_topic_ids:
            stories = self.fetch_for_topic(topic_id)
            if stories:
                logger.info(
                    f"Found {len(stories)} fresh stories for topic '{topic_id}'. "
                    f"Top pick: '{stories[0].title}' (Score: {stories[0].importance_score})"
                )
                # First topic in rotation priority with fresh news wins
                best_candidate = stories[0]
                break
            else:
                logger.warning(f"No fresh news found for topic '{topic_id}'. Checking next eligible topic.")

        if not best_candidate:
            logger.warning(
                "No fresh, non-duplicate news found across eligible topics for the past 24 hours. "
                "Skipping today's post to prevent filler content."
            )
            return None

        return best_candidate
