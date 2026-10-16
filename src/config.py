"""
Configuration management for LinkedIn Daily Bot.
Loads settings from .env file and provides structured access.
"""

from dataclasses import dataclass, field
import os
from pathlib import Path
from typing import Dict, List
from dotenv import load_dotenv

# Load .env file from project root (override=True ensures .env values take precedence)
ROOT_DIR = Path(__file__).resolve().parent.parent
load_dotenv(ROOT_DIR / ".env", override=True)


@dataclass(frozen=True)
class TopicConfig:
    """Represents a monitored news topic."""
    id: str
    name: str
    rss_query: str
    search_keywords: str


# The four configured topics to rotate
TOPICS: Dict[str, TopicConfig] = {
    "ai_ml": TopicConfig(
        id="ai_ml",
        name="Machine Learning & AI Updates",
        rss_query='"artificial intelligence" OR "machine learning" when:1d',
        search_keywords="artificial intelligence machine learning LLM",
    ),
    "elon_musk": TopicConfig(
        id="elon_musk",
        name="Elon Musk Activities",
        rss_query='"Elon Musk" AND (Tesla OR SpaceX OR xAI OR Neuralink) when:1d',
        search_keywords="Elon Musk Tesla SpaceX xAI Neuralink",
    ),
    "bill_gates": TopicConfig(
        id="bill_gates",
        name="Bill Gates Activities",
        rss_query='"Bill Gates" when:1d',
        search_keywords="Bill Gates Breakthrough Energy Gates Foundation",
    ),
    "openai_ceo": TopicConfig(
        id="openai_ceo",
        name="Sam Altman & OpenAI News",
        rss_query='("Sam Altman" OR "OpenAI") when:1d',
        search_keywords="Sam Altman OpenAI ChatGPT",
    ),
}


@dataclass
class Config:
    """Application configuration container."""
    # Base paths
    root_dir: Path = ROOT_DIR
    token_file: Path = ROOT_DIR / os.getenv("LINKEDIN_TOKEN_FILE", "token.json")
    database_path: Path = ROOT_DIR / os.getenv("DATABASE_PATH", "posted.db")
    log_file: Path = ROOT_DIR / os.getenv("LOG_FILE", "bot.log")
    log_level: str = os.getenv("LOG_LEVEL", "INFO").upper()

    # LinkedIn OAuth 2.0
    linkedin_client_id: str = os.getenv("LINKEDIN_CLIENT_ID", "")
    linkedin_client_secret: str = os.getenv("LINKEDIN_CLIENT_SECRET", "")
    linkedin_redirect_uri: str = os.getenv("LINKEDIN_REDIRECT_URI", "http://localhost:8080/callback")
    linkedin_scopes: List[str] = field(default_factory=lambda: ["w_member_social", "openid", "profile"])

    # LLM Settings
    llm_provider: str = os.getenv("LLM_PROVIDER", "anthropic").lower()
    anthropic_api_key: str = os.getenv("ANTHROPIC_API_KEY", "")
    anthropic_model: str = os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-20241022")
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    openai_model: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    gemini_api_key: str = os.getenv("GEMINI_API_KEY", "")
    gemini_model: str = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")

    # News sources
    news_source: str = os.getenv("NEWS_SOURCE", "rss").lower()
    news_api_key: str = os.getenv("NEWS_API_KEY", "")
    gnews_api_key: str = os.getenv("GNEWS_API_KEY", "")

    # Mode and Safety
    auto_post: bool = os.getenv("AUTO_POST", "false").lower() in ("true", "1", "yes")
    telegram_bot_token: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    telegram_chat_id: str = os.getenv("TELEGRAM_CHAT_ID", "")
    telegram_poll_timeout_seconds: int = int(os.getenv("TELEGRAM_POLL_TIMEOUT_SECONDS", "7200"))

    # Configured topics
    topics: Dict[str, TopicConfig] = field(default_factory=lambda: TOPICS)

    def validate_llm_config(self) -> None:
        """Validate LLM credentials based on chosen provider."""
        if self.llm_provider == "anthropic" and not self.anthropic_api_key:
            raise ValueError(
                "ANTHROPIC_API_KEY is not set in .env. "
                "Please add your Anthropic API key or set LLM_PROVIDER=gemini."
            )
        if self.llm_provider == "openai" and not self.openai_api_key:
            raise ValueError(
                "OPENAI_API_KEY is not set in .env. "
                "Please add your OpenAI API key or set LLM_PROVIDER=gemini."
            )
        if self.llm_provider == "gemini" and not self.gemini_api_key:
            raise ValueError(
                "GEMINI_API_KEY is not set in .env. "
                "Please add your Gemini API key to use LLM_PROVIDER=gemini."
            )

    def validate_linkedin_config(self) -> None:
        """Validate LinkedIn client credentials."""
        if not self.linkedin_client_id or not self.linkedin_client_secret:
            raise ValueError(
                "LINKEDIN_CLIENT_ID and LINKEDIN_CLIENT_SECRET must be configured in .env "
                "to use LinkedIn features."
            )


# Global default configuration instance
config = Config()
