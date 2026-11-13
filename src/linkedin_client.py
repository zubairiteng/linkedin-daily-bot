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

    def upload_image(self, image_path: Path) -> str:
        """
        Upload an image binary to LinkedIn using the v2 Assets API.
        Returns the registered asset URN (e.g. urn:li:digitalmediaAsset:...).
        """
        image_path = Path(image_path)
        if not image_path.exists():
            raise FileNotFoundError(f"Image not found at '{image_path}'")

        # 1. Register Upload
        reg_url = "https://api.linkedin.com/v2/assets?action=registerUpload"
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }
        reg_payload = {
            "registerUploadRequest": {
                "recipes": ["urn:li:digitalmediaRecipe:feedshare-image"],
                "owner": self.author_urn,
                "supportedUploadMechanism": ["SYNCHRONOUS_UPLOAD"]
            }
        }

        logger.info(f"Registering image upload with LinkedIn for: {image_path.name}")
        reg_res = requests.post(reg_url, headers=headers, json=reg_payload, timeout=20)
        if reg_res.status_code != 200:
            raise RuntimeError(f"LinkedIn image registration failed ({reg_res.status_code}): {reg_res.text}")

        data = reg_res.json().get("value", {})
        asset_urn = data.get("asset")
        upload_url = data.get("uploadMechanism", {}).get(
            "com.linkedin.digitalmedia.uploading.MediaUploadHttpRequest", {}
        ).get("uploadUrl")

        if not asset_urn or not upload_url:
            raise RuntimeError("Missing asset URN or uploadUrl in LinkedIn registration response")

        # 2. Upload binary bytes
        logger.info(f"Uploading image binary ({image_path.stat().st_size} bytes) to LinkedIn CDN...")
        with open(image_path, "rb") as f:
            upload_res = requests.put(
                upload_url,
                data=f.read(),
                headers={"Authorization": f"Bearer {self.access_token}"},
                timeout=30
            )

        if upload_res.status_code not in (200, 201):
            raise RuntimeError(f"LinkedIn image binary upload failed ({upload_res.status_code}): {upload_res.text}")

        logger.info(f"Successfully uploaded image to LinkedIn! Asset URN: {asset_urn}")
        return asset_urn

    def post(self, text: str, image_path: Optional[Path] = None) -> Dict[str, Any]:
        """
        Publish a post to the authenticated LinkedIn member's personal feed.
        If image_path is provided, uploads and attaches the visual infographic.
        Falls back to text post if no image is supplied or if image upload fails.
        """
        # Re-check token validity before attempting post
        self._load_token()

        asset_urn = None
        if image_path:
            try:
                asset_urn = self.upload_image(image_path)
            except Exception as e:
                logger.warning(f"Failed to upload image ({e}). Falling back to text post...")

        # If we have an uploaded image asset, publish via UGC Posts API with IMAGE category
        if asset_urn:
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
                        "shareMediaCategory": "IMAGE",
                        "media": [
                            {
                                "status": "READY",
                                "description": {
                                    "text": "Tech Infographic & Roadmap"
                                },
                                "media": asset_urn,
                                "title": {
                                    "text": "Practical AI Guide"
                                }
                            }
                        ]
                    }
                },
                "visibility": {
                    "com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"
                }
            }

            logger.info("Posting visual content via LinkedIn UGC Posts API...")
            res = requests.post(ugc_url, headers=ugc_headers, json=ugc_payload, timeout=20)
            if res.status_code in (200, 201):
                data = res.json() if res.text else {}
                post_urn = data.get("id", "urn:li:ugcPost:unknown")
                logger.info(f"Successfully posted visual card to LinkedIn! Post URN: {post_urn}")
                return {
                    "success": True,
                    "method": "ugc_posts_image",
                    "post_urn": post_urn,
                    "status_code": res.status_code,
                    "asset_urn": asset_urn,
                }
            elif res.status_code == 401:
                raise LinkedInAuthError(
                    "LinkedIn returned 401 Unauthorized. Access token is invalid or has been revoked. "
                    "Please run 'python auth.py' to re-authenticate."
                )
            else:
                logger.warning(f"Image post failed ({res.status_code}): {res.text}. Trying text fallback...")

        # Text-only post fallback (REST Posts API -> UGC Posts API)
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
