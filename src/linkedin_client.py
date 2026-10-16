"""
LinkedIn Client module for LinkedIn Daily Bot.
Uses the official LinkedIn API (REST Posts API and UGC fallback)
with saved OAuth 2.0 tokens from token.json.
"""

from datetime import datetime, timezone
import json
import logging
from pathlib import Path
import time
from typing import Optional, Dict, Any
import requests

from .config import Config

logger = logging.getLogger(__name__)


class LinkedInAuthError(Exception):
    """Raised when authentication credentials are missing or expired."""
    pass


class LinkedInClient:
    """Client for posting content to LinkedIn via the official API."""

    def __init__(self, config: Config):
        self.config = config
        self.token_file: Path = config.token_file
        self.token_data: Optional[Dict[str, Any]] = None
        self._load_token()

    def _load_token(self) -> None:
        """Load and validate the saved token.json."""
        if not self.token_file.exists():
            raise LinkedInAuthError(
                f"LinkedIn token file not found at '{self.token_file}'. "
                f"Please run 'python auth.py' to authenticate your LinkedIn account."
            )

        try:
            with open(self.token_file, "r", encoding="utf-8") as f:
                self.token_data = json.load(f)
        except Exception as e:
            raise LinkedInAuthError(f"Could not read '{self.token_file}': {e}. Please re-run 'python auth.py'.")

        # Check for necessary fields
        access_token = self.token_data.get("access_token")
        author_urn = self.token_data.get("author_urn")
        expires_at = self.token_data.get("expires_at", 0)

        if not access_token or not author_urn:
            raise LinkedInAuthError(
                f"Incomplete token data in '{self.token_file}'. "
                f"Please re-run 'python auth.py' to refresh your session."
            )

        # Check expiry
        now = time.time()
        if now >= expires_at:
            exp_iso = self.token_data.get("expires_at_iso", "expired")
            raise LinkedInAuthError(
                f"LinkedIn access token has expired (expired at {exp_iso}). "
                f"Please re-run 'python auth.py' to generate a fresh token."
            )

        # Log days remaining
        days_left = int((expires_at - now) / 86400)
        logger.debug(f"LinkedIn token active ({days_left} days remaining until expiration).")

    @property
    def access_token(self) -> str:
        return self.token_data["access_token"]

    @property
    def author_urn(self) -> str:
        return self.token_data["author_urn"]

    def post(self, text: str) -> Dict[str, Any]:
        """
        Publish a post to the authenticated LinkedIn member's personal feed.
        First attempts the modern REST Posts API (/rest/posts),
        falling back to UGC Posts (/v2/ugcPosts) if necessary.
        """
        # Re-check token validity before attempting post
        self._load_token()

        # 1. Attempt Modern REST Posts API (recommended for Share on LinkedIn)
        rest_url = "https://api.linkedin.com/rest/posts"
        rest_headers = {
            "Authorization": f"Bearer {self.access_token}",
            "LinkedIn-Version": "202401",
            "X-Restli-Protocol-Version": "2.0.0",
            "Content-Type": "application/json",
        }
        rest_payload = {
            "author": self.author_urn,
            "commentary": text,
            "visibility": "PUBLIC",
            "distribution": {
                "feedDistribution": "MAIN_FEED",
                "targetEntities": [],
                "thirdPartyDistributionChannels": []
            },
            "lifecycleState": "PUBLISHED",
            "isReshareDisabledByAuthor": False
        }

        logger.info(f"Posting to LinkedIn via REST Posts API as {self.author_urn}...")
        try:
            res = requests.post(rest_url, headers=rest_headers, json=rest_payload, timeout=20)
            if res.status_code == 201:
                post_urn = res.headers.get("x-restli-id") or res.headers.get("x-linkedin-id") or "posted"
                logger.info(f"Successfully posted to LinkedIn! Post URN: {post_urn}")
                return {
                    "success": True,
                    "method": "rest_posts",
                    "post_urn": post_urn,
                    "status_code": res.status_code,
                }
            elif res.status_code == 401:
                raise LinkedInAuthError(
                    "LinkedIn returned 401 Unauthorized. Access token is invalid or has been revoked. "
                    "Please run 'python auth.py' to re-authenticate."
                )
            else:
                logger.warning(
                    f"REST Posts API returned {res.status_code}: {res.text}. "
                    "Attempting fallback to UGC Posts API (/v2/ugcPosts)..."
                )
        except LinkedInAuthError:
            raise
        except Exception as e:
            logger.warning(f"Error calling REST Posts API: {e}. Trying UGC fallback...")

        # 2. Fallback to UGC Posts API
        ugc_url = "https://api.linkedin.com/v2/ugcPosts"
        ugc_headers = {
            "Authorization": f"Bearer {self.access_token}",
            "X-Restli-Protocol-Version": "2.0.0",
            "Content-Type": "application/json",
        }
        ugc_payload = {
            "author": self.author_urn,
            "lifecycleState": "PUBLISHED",
            "specificContent": {
                "com.linkedin.ugc.ShareContent": {
                    "shareCommentary": {
                        "text": text
                    },
                    "shareMediaCategory": "NONE"
                }
            },
            "visibility": {
                "com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"
            }
        }

        logger.info("Posting via LinkedIn UGC Posts API (/v2/ugcPosts)...")
        res2 = requests.post(ugc_url, headers=ugc_headers, json=ugc_payload, timeout=20)
        if res2.status_code in (200, 201):
            data = res2.json() if res2.text else {}
            post_urn = data.get("id", "urn:li:ugcPost:unknown")
            logger.info(f"Successfully posted to LinkedIn via UGC API! Post URN: {post_urn}")
            return {
                "success": True,
                "method": "ugc_posts",
                "post_urn": post_urn,
                "status_code": res2.status_code,
            }
        elif res2.status_code == 401:
            raise LinkedInAuthError(
                "LinkedIn returned 401 Unauthorized. Access token is invalid or has been revoked. "
                "Please run 'python auth.py' to re-authenticate."
            )
        else:
            raise RuntimeError(f"LinkedIn posting failed ({res2.status_code}): {res2.text}")
