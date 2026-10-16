"""
Unit tests for database deduplication and topic rotation.
"""

import tempfile
from pathlib import Path
from src.database import Database, clean_url


def test_clean_url():
    """Verify UTM parameters and query tracking strings are stripped."""
    dirty_url = "https://techcrunch.com/2026/10/15/ai-breakthrough/?utm_source=twitter&utm_medium=social&utm_campaign=launch&ref=homepage"
    cleaned = clean_url(dirty_url)
    assert "utm_source" not in cleaned
    assert "utm_medium" not in cleaned
    assert "ref" not in cleaned
    assert cleaned == "https://techcrunch.com/2026/10/15/ai-breakthrough"


def test_url_deduplication():
    """Verify identical or tracking-parameter URLs are recognized as duplicate."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path = Path(tmp_dir) / "test_posted.db"
        db = Database(db_path)

        url1 = "https://news.ycombinator.com/item?id=12345"
        assert not db.is_url_posted(url1)

        db.record_post(
            topic_id="ai_ml",
            title="Sample AI News Headline",
            url=url1,
            content="Sample post content for testing.",
            status="posted"
        )

        assert db.is_url_posted(url1)
        # Same URL with tracking parameter should also be recognized
        assert db.is_url_posted(url1 + "&utm_source=test")


def test_title_similarity_deduplication():
    """Verify similar titles from different outlets are recognized as duplicates."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path = Path(tmp_dir) / "test_posted.db"
        db = Database(db_path)

        title1 = "SpaceX Successfully Catches Starship Super Heavy Booster On Launch Pad"
        url1 = "https://space.com/article-1"
        db.record_post(
            topic_id="elon_musk",
            title=title1,
            url=url1,
            content="SpaceX caught the booster.",
            status="posted"
        )

        # Similar title with slight variation
        title2 = "SpaceX Catches Starship Super Heavy Booster on Launch Pad"
        assert db.is_similar_title_posted(title2, threshold=0.70)

        # Completely different title should not be flagged
        title3 = "Bill Gates Pledges New Clean Tech Funding"
        assert not db.is_similar_title_posted(title3, threshold=0.70)


def test_topic_rotation_tracking():
    """Verify the database properly returns the last posted topic."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path = Path(tmp_dir) / "test_posted.db"
        db = Database(db_path)

        assert db.get_last_posted_topic() is None

        db.record_post(
            topic_id="elon_musk",
            title="Elon Musk Announcement",
            url="https://example.com/elon-1",
            content="Elon Musk post.",
            status="posted"
        )
        assert db.get_last_posted_topic() == "elon_musk"

        db.record_post(
            topic_id="openai_ceo",
            title="OpenAI Update",
            url="https://example.com/openai-1",
            content="OpenAI post.",
            status="posted"
        )
        assert db.get_last_posted_topic() == "openai_ceo"
