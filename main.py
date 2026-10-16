"""
LinkedIn Daily Bot - Main Pipeline Entry Point.
Executes the full automated news research, curation, generation,
validation, and publishing pipeline.
"""

import argparse
from datetime import datetime, timezone
import logging
import sys
from pathlib import Path

from src.config import config, TOPICS
from src.database import Database
from src.news_fetcher import NewsFetcher
from src.llm_provider import get_llm_provider
from src.post_generator import PostGenerator
from src.linkedin_client import LinkedInClient, LinkedInAuthError
from src.telegram_notifier import TelegramNotifier


def setup_logging(log_file: Path, log_level: str = "INFO"):
    """Configure unified logging to both console and bot.log."""
    level = getattr(logging, log_level.upper(), logging.INFO)

    # Root logger
    root = logging.getLogger()
    root.setLevel(level)

    # Clean existing handlers
    root.handlers.clear()

    # Formatter
    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # File handler
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(level)
    file_handler.setFormatter(formatter)
    root.addHandler(file_handler)

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)
    root.addHandler(console_handler)


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="LinkedIn Daily Bot: Autonomous news research & LinkedIn publisher."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Fetch news, select story, generate and validate post, but do not post or send to Telegram."
    )
    parser.add_argument(
        "--topic",
        choices=list(TOPICS.keys()),
        default=None,
        help="Force a specific topic (ai_ml, elon_musk, bill_gates, openai_ceo) instead of daily rotation."
    )
    parser.add_argument(
        "--auto-post",
        dest="auto_post",
        action="store_true",
        default=None,
        help="Force auto-posting to LinkedIn without waiting for Telegram approval."
    )
    parser.add_argument(
        "--no-auto-post",
        dest="auto_post",
        action="store_false",
        help="Require Telegram/manual approval before posting to LinkedIn."
    )
    parser.add_argument(
        "--provider",
        choices=["gemini", "anthropic", "openai", "mock"],
        default=None,
        help="Override LLM provider (gemini, anthropic, openai, mock). Defaults to .env setting."
    )
    parser.add_argument(
        "--model",
        default=None,
        help="Override LLM model name (e.g. gemini-2.5-flash, claude-3-5-sonnet-20241022, gpt-4o-mini)."
    )
    return parser.parse_args()


def run_bot(
    dry_run: bool = False,
    force_topic: str = None,
    override_auto_post: bool = None,
    provider: str = None,
    model: str = None
) -> int:
    """Execute the daily bot run."""
    setup_logging(config.log_file, config.log_level)
    logger = logging.getLogger("main")

    # Apply CLI overrides to configuration if provided
    if provider:
        config.llm_provider = provider.lower()
    if model:
        if config.llm_provider == "gemini":
            config.gemini_model = model
        elif config.llm_provider == "anthropic":
            config.anthropic_model = model
        elif config.llm_provider == "openai":
            config.openai_model = model

    active_model = (
        config.gemini_model if config.llm_provider == "gemini"
        else config.anthropic_model if config.llm_provider == "anthropic"
        else config.openai_model if config.llm_provider == "openai"
        else "mock"
    )

    logger.info("=" * 65)
    logger.info(" Starting LinkedIn Daily Bot Run")
    logger.info(f" Mode:         {'DRY RUN' if dry_run else 'LIVE RUN'}")
    logger.info(f" LLM Provider: {config.llm_provider}")
    logger.info(f" LLM Model:    {active_model}")
    logger.info(f" Auto-Post:    {override_auto_post if override_auto_post is not None else config.auto_post}")
    logger.info("=" * 65)

    # 1. Initialize Database
    db = Database(config.database_path)

    # 2. Fetch fresh news & select story of the day with rotation
    fetcher = NewsFetcher(config=config, database=db)
    story = fetcher.select_story_of_the_day(force_topic_id=force_topic)

    if not story:
        logger.info(
            "No fresh, non-duplicate news was found for the past 24 hours. "
            "Skipping today's post to prevent filler content."
        )
        return 0

    logger.info(f"Selected Story: '{story.title}'")
    logger.info(f"Topic:          {story.topic_name}")
    logger.info(f"Source:         {story.source}")
    logger.info(f"URL:            {story.url}")

    # 3. Initialize LLM Provider & Post Generator
    try:
        # In dry-run mode, if LLM credentials are not yet configured, provide mock fallback
        llm = None
        try:
            config.validate_llm_config()
            llm = get_llm_provider(config)
        except ValueError as ve:
            if dry_run:
                logger.warning(f"{ve} Using mock LLM provider for dry run demonstration.")
                from src.llm_provider import MockLLMProvider
                llm = MockLLMProvider()
            else:
                logger.error(str(ve))
                return 1

        generator = PostGenerator(llm_provider=llm, max_retries=3)
        post_content, validation = generator.generate_post(story)

    except Exception as e:
        logger.error(f"Error during post generation: {e}")
        return 1

    if not validation.is_valid:
        logger.error(f"Generated post failed validation after all retries: {validation.errors}")
        return 1

    print("\n" + "=" * 65)
    print(" GENERATED LINKEDIN POST")
    print("=" * 65)
    print(post_content)
    print("=" * 65)
    print(f"Validation: {validation.summary()}\n")

    # 4. Handle Dry-Run Mode
    if dry_run:
        logger.info("Dry run completed successfully. No posts published or sent to Telegram.")
        return 0

    # Determine posting mode
    auto_post_active = config.auto_post if override_auto_post is None else override_auto_post

    # 5. Handle Telegram Approval if AUTO_POST is false
    if not auto_post_active:
        logger.info("AUTO_POST is false. Requesting approval...")
        notifier = TelegramNotifier(config)
        approved = notifier.request_approval(story, post_content)

        if not approved:
            logger.info("Post was rejected or approval timed out. Recording as rejected draft.")
            db.record_post(
                topic_id=story.topic_id,
                title=story.title,
                url=story.url,
                content=post_content,
                status="rejected"
            )
            return 0
        logger.info("Approval confirmed. Proceeding to publish to LinkedIn.")

    # 6. Publish to LinkedIn
    try:
        linkedin = LinkedInClient(config)
        result = linkedin.post(post_content)
        post_urn = result.get("post_urn", "published")

        # 7. Record post in database for deduplication and topic rotation
        db.record_post(
            topic_id=story.topic_id,
            title=story.title,
            url=story.url,
            content=post_content,
            status="posted",
            linkedin_urn=post_urn
        )
        logger.info(f"Run completed successfully! Post URN: {post_urn}")
        return 0

    except LinkedInAuthError as ae:
        logger.error(f"\n[AUTHENTICATION REQUIRED] {ae}")
        return 1
    except Exception as e:
        logger.error(f"Failed to publish post to LinkedIn: {e}")
        return 1


def main():
    args = parse_args()
    exit_code = run_bot(
        dry_run=args.dry_run,
        force_topic=args.topic,
        override_auto_post=args.auto_post,
        provider=args.provider,
        model=args.model
    )
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
