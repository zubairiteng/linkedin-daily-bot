"""
Helper script used by GitHub Actions to safely restore
.env and token.json from environment variables without bash quoting or escaping issues.
"""

import json
import os
import sys
from pathlib import Path


def main():
    root_dir = Path(__file__).resolve().parent.parent

    # 1. Restore token.json
    token_json_str = os.environ.get("LINKEDIN_TOKEN_JSON", "").strip()
    if not token_json_str:
        print("\n[ERROR] LINKEDIN_TOKEN_JSON secret is empty or missing in GitHub Secrets!", file=sys.stderr)
        print("Please go to GitHub Repository -> Settings -> Secrets and variables -> Actions", file=sys.stderr)
        print("and add a secret named 'LINKEDIN_TOKEN_JSON' with your token.json content.\n", file=sys.stderr)
        sys.exit(1)

    token_path = root_dir / "token.json"
    try:
        token_data = json.loads(token_json_str)
        with open(token_path, "w", encoding="utf-8") as f:
            json.dump(token_data, f, indent=2)
        print("Successfully restored token.json (valid JSON parsed).")
    except json.JSONDecodeError:
        with open(token_path, "w", encoding="utf-8") as f:
            f.write(token_json_str)
        print("Successfully restored token.json (written as raw string).")

    # 2. Restore .env
    client_id = os.environ.get("LINKEDIN_CLIENT_ID", "").strip()
    client_secret = os.environ.get("LINKEDIN_CLIENT_SECRET", "").strip()
    gemini_key = os.environ.get("GEMINI_API_KEY", "").strip()
    gemini_model = os.environ.get("GEMINI_MODEL", "gemini-3.5-flash-lite").strip()
    telegram_token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    telegram_chat_id = os.environ.get("TELEGRAM_CHAT_ID", "").strip()

    env_lines = [
        f"LINKEDIN_CLIENT_ID={client_id}",
        f"LINKEDIN_CLIENT_SECRET={client_secret}",
        "LINKEDIN_REDIRECT_URI=http://localhost:8080/callback",
        "LINKEDIN_TOKEN_FILE=token.json",
        "LLM_PROVIDER=gemini",
        f"GEMINI_API_KEY={gemini_key}",
        f"GEMINI_MODEL={gemini_model}",
        "NEWS_SOURCE=rss",
        "AUTO_POST=true",
        f"TELEGRAM_BOT_TOKEN={telegram_token}",
        f"TELEGRAM_CHAT_ID={telegram_chat_id}",
        "DATABASE_PATH=posted.db",
        "LOG_FILE=bot.log",
        "LOG_LEVEL=INFO",
    ]

    env_path = root_dir / ".env"
    with open(env_path, "w", encoding="utf-8") as f:
        f.write("\n".join(env_lines) + "\n")
    print("Successfully restored .env configuration.")


if __name__ == "__main__":
    main()
