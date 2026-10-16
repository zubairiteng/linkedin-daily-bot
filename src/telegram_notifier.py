"""
Telegram Notifier module for LinkedIn Daily Bot.
Sends draft posts to the user's Telegram chat and polls for
approval ("approve" or inline button click) before posting.
"""

import logging
import time
from typing import Optional
import requests

from .config import Config
from .news_fetcher import NewsStory

logger = logging.getLogger(__name__)


class TelegramNotifier:
    """Manages Telegram notifications and interactive post approvals."""

    def __init__(self, config: Config):
        self.config = config
        self.token = config.telegram_bot_token.strip()
        self.chat_id = config.telegram_chat_id.strip()
        self.base_url = f"https://api.telegram.org/bot{self.token}" if self.token else ""

    def is_configured(self) -> bool:
        """Check if Telegram bot credentials are provided."""
        return bool(self.token and self.chat_id)

    def send_message(self, text: str, reply_markup: Optional[dict] = None) -> Optional[int]:
        """Send a message to the configured Telegram chat. Returns message_id if successful."""
        if not self.is_configured():
            logger.warning("Telegram is not configured. Skipping Telegram notification.")
            return None

        url = f"{self.base_url}/sendMessage"
        payload = {
            "chat_id": self.chat_id,
            "text": text,
            "disable_web_page_preview": True,
        }
        if reply_markup:
            payload["reply_markup"] = reply_markup

        try:
            res = requests.post(url, json=payload, timeout=15)
            if res.status_code == 200:
                data = res.json()
                return data.get("result", {}).get("message_id")
            else:
                logger.error(f"Failed to send Telegram message ({res.status_code}): {res.text}")
        except Exception as e:
            logger.error(f"Error communicating with Telegram: {e}")
        return None

    def request_approval(self, story: NewsStory, post_content: str) -> bool:
        """
        Send draft to Telegram with inline buttons and wait for user approval.
        If Telegram is not configured, falls back to interactive terminal input.
        """
        if not self.is_configured():
            print("\n" + "=" * 60)
            print(" AUTO_POST=false and Telegram is not configured in .env.")
            print(" Fallback to terminal approval:")
            print("=" * 60)
            print(f"Topic:  {story.topic_name}")
            print(f"Source: {story.source}")
            print("-" * 60)
            print(post_content)
            print("=" * 60)
            try:
                ans = input("\nApprove and publish this post to LinkedIn? [y/N]: ").strip().lower()
                return ans in ("y", "yes", "approve")
            except (KeyboardInterrupt, EOFError):
                return False

        # Format message for Telegram
        msg_text = (
            f"📢 *LinkedIn Daily Bot - Draft Post Review*\n\n"
            f"📌 *Topic:* {story.topic_name}\n"
            f"📰 *Headline:* {story.title}\n"
            f"🔗 *Source:* {story.source}\n\n"
            f"─────────────────────\n"
            f"{post_content}\n"
            f"─────────────────────\n\n"
            f"Click a button below or reply with 'approve' or 'reject'."
        )

        reply_markup = {
            "inline_keyboard": [
                [
                    {"text": "✅ Approve & Post", "callback_data": "approve_post"},
                    {"text": "❌ Reject", "callback_data": "reject_post"},
                ]
            ]
        }

        sent_msg_id = self.send_message(msg_text, reply_markup=reply_markup)
        if not sent_msg_id:
            logger.error("Failed to send review message to Telegram. Post not approved.")
            return False

        logger.info(
            f"Draft sent to Telegram. Waiting up to {self.config.telegram_poll_timeout_seconds}s "
            "for user approval..."
        )

        # Get initial offset
        offset = 0
        try:
            updates_res = requests.get(f"{self.base_url}/getUpdates?offset=-1", timeout=10).json()
            if updates_res.get("ok") and updates_res.get("result"):
                offset = updates_res["result"][-1]["update_id"] + 1
        except Exception:
            offset = 0

        start_time = time.time()
        timeout = self.config.telegram_poll_timeout_seconds

        while time.time() - start_time < timeout:
            try:
                poll_url = f"{self.base_url}/getUpdates?offset={offset}&timeout=20"
                res = requests.get(poll_url, timeout=30)
                if res.status_code != 200:
                    time.sleep(3)
                    continue

                data = res.json()
                if not data.get("ok"):
                    time.sleep(3)
                    continue

                for update in data.get("result", []):
                    offset = max(offset, update["update_id"] + 1)

                    # Check 1: Inline button click
                    if "callback_query" in update:
                        cb = update["callback_query"]
                        cb_data = cb.get("data")
                        cb_id = cb.get("id")

                        # Answer callback query to stop loading spinner
                        try:
                            requests.post(
                                f"{self.base_url}/answerCallbackQuery",
                                json={"callback_query_id": cb_id},
                                timeout=5
                            )
                        except Exception:
                            pass

                        if cb_data == "approve_post":
                            self.send_message("✅ Post approved! Publishing to LinkedIn now...")
                            logger.info("Post approved via Telegram button.")
                            return True
                        elif cb_data == "reject_post":
                            self.send_message("❌ Post rejected. Draft will not be posted.")
                            logger.info("Post rejected via Telegram button.")
                            return False

                    # Check 2: Direct text reply
                    if "message" in update and "text" in update["message"]:
                        text = update["message"]["text"].strip().lower()
                        chat_id = str(update["message"]["chat"]["id"])
                        if chat_id == self.chat_id:
                            if text in ("approve", "yes", "y", "/approve"):
                                self.send_message("✅ Post approved! Publishing to LinkedIn now...")
                                logger.info("Post approved via Telegram text reply.")
                                return True
                            elif text in ("reject", "no", "n", "/reject"):
                                self.send_message("❌ Post rejected. Draft will not be posted.")
                                logger.info("Post rejected via Telegram text reply.")
                                return False

            except Exception as e:
                logger.warning(f"Error during Telegram update polling: {e}")
                time.sleep(5)

        logger.warning(f"Telegram approval timed out after {timeout} seconds.")
        self.send_message("⏳ Approval timed out. The post has been cancelled.")
        return False
