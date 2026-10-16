"""
LinkedIn OAuth 2.0 Authentication Script.
One-time setup script to authorize the LinkedIn Daily Bot.
Starts a temporary local server, opens your browser for consent,
and saves the access token, member URN, and expiration time to token.json.
"""

from datetime import datetime, timezone
import http.server
import json
import logging
import os
from pathlib import Path
import secrets
import sys
import threading
import time
import urllib.parse
import webbrowser
import requests
from dotenv import load_dotenv

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("auth")

ROOT_DIR = Path(__file__).resolve().parent
load_dotenv(ROOT_DIR / ".env", override=True)

CLIENT_ID = os.getenv("LINKEDIN_CLIENT_ID", "").strip()
CLIENT_SECRET = os.getenv("LINKEDIN_CLIENT_SECRET", "").strip()
REDIRECT_URI = os.getenv("LINKEDIN_REDIRECT_URI", "http://localhost:8080/callback").strip()
TOKEN_FILE = ROOT_DIR / os.getenv("LINKEDIN_TOKEN_FILE", "token.json")
SCOPES = ["w_member_social", "openid", "profile"]

# Shared state between HTTP server handler and main thread
auth_result = {
    "code": None,
    "error": None,
    "state_received": None
}


class OAuthCallbackHandler(http.server.BaseHTTPRequestHandler):
    """Temporary HTTP handler to capture the OAuth authorization code."""

    def log_message(self, format, *args):
        # Silence default HTTP server access logs
        pass

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path != "/callback":
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"Not Found")
            return

        params = urllib.parse.parse_qs(parsed.query)

        if "error" in params:
            err = params["error"][0]
            desc = params.get("error_description", ["Unknown error"])[0]
            auth_result["error"] = f"{err}: {desc}"
            self.send_response(400)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            html_content = f"""
            <html><body style="font-family: sans-serif; text-align: center; padding: 50px;">
                <h1 style="color: #e53e3e;">Authorization Failed</h1>
                <p>{err}: {desc}</p>
                <p>You can close this tab and inspect your console.</p>
            </body></html>
            """
            self.wfile.write(html_content.encode("utf-8"))
            return

        if "code" in params:
            auth_result["code"] = params["code"][0]
            auth_result["state_received"] = params.get("state", [None])[0]

            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            html_content = """
            <html><body style="font-family: sans-serif; text-align: center; padding: 50px; background-color: #f7fafc;">
                <h1 style="color: #0077b5;">LinkedIn Authorization Successful!</h1>
                <p style="font-size: 1.1rem; color: #4a5568;">
                    Access credentials received. You can now close this tab and return to the terminal.
                </p>
            </body></html>
            """
            self.wfile.write(html_content.encode("utf-8"))


def exchange_code_for_token(code: str) -> dict:
    """Exchange authorization code for an OAuth access token."""
    token_url = "https://www.linkedin.com/oauth/v2/accessToken"
    payload = {
        "grant_type": "authorization_code",
        "code": code,
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "redirect_uri": REDIRECT_URI,
    }
    headers = {"Content-Type": "application/x-www-form-urlencoded"}

    response = requests.post(token_url, data=payload, headers=headers, timeout=15)
    if response.status_code != 200:
        err_msg = f"Token exchange failed ({response.status_code}): {response.text}"
        if response.status_code == 401 and "invalid_client" in response.text:
            err_msg += (
                "\n\n--> CAUSE: 'invalid_client / Client authentication failed' means LinkedIn rejected the LINKEDIN_CLIENT_SECRET.\n"
                "--> FIX:\n"
                "    1. Open https://www.linkedin.com/developers/apps\n"
                "    2. Click on your App (Client ID: " + CLIENT_ID + ")\n"
                "    3. Go to the 'Auth' tab -> 'Application credentials'\n"
                "    4. Click the copy icon next to 'Primary Client Secret'\n"
                "    5. Paste it into .env as LINKEDIN_CLIENT_SECRET=<copied_secret>\n"
            )
        raise RuntimeError(err_msg)

    return response.json()


def get_member_urn(access_token: str) -> str:
    """
    Fetch the authenticated user's member ID and format as URN (urn:li:person:ID).
    Uses the OpenID Connect userinfo endpoint.
    """
    headers = {"Authorization": f"Bearer {access_token}"}

    # 1. Try standard OpenID Connect userinfo
    try:
        res = requests.get("https://api.linkedin.com/v2/userinfo", headers=headers, timeout=10)
        if res.status_code == 200:
            userinfo = res.json()
            sub = userinfo.get("sub")
            if sub:
                logger.info(f"Retrieved member identity for: {userinfo.get('name', 'LinkedIn User')}")
                return f"urn:li:person:{sub}"
    except Exception as e:
        logger.debug(f"userinfo endpoint check failed: {e}")

    # 2. Fallback to legacy /v2/me endpoint
    try:
        res = requests.get("https://api.linkedin.com/v2/me", headers=headers, timeout=10)
        if res.status_code == 200:
            me = res.json()
            mid = me.get("id")
            if mid:
                return f"urn:li:person:{mid}"
    except Exception as e:
        logger.debug(f"/v2/me endpoint check failed: {e}")

    raise RuntimeError("Could not determine LinkedIn Member URN. Ensure 'openid' and 'profile' scopes are granted.")


def main():
    print("=" * 70)
    print(" LinkedIn Daily Bot - OAuth 2.0 Setup")
    print("=" * 70)

    if not CLIENT_ID or not CLIENT_SECRET:
        print("\n[ERROR] Missing LinkedIn credentials in .env file!")
        print("Please edit .env and configure:")
        print("  LINKEDIN_CLIENT_ID=your_id")
        print("  LINKEDIN_CLIENT_SECRET=your_secret")
        print("  LINKEDIN_REDIRECT_URI=http://localhost:8080/callback\n")
        print("Check the README.md for step-by-step instructions on creating")
        print("your LinkedIn Developer App and enabling 'Share on LinkedIn'.")
        sys.exit(1)

    # Parse port and host from redirect URI
    parsed_redirect = urllib.parse.urlparse(REDIRECT_URI)
    host = parsed_redirect.hostname or "localhost"
    port = parsed_redirect.port or 8080

    # Start local server
    server = http.server.HTTPServer((host, port), OAuthCallbackHandler)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()

    state = secrets.token_urlsafe(16)
    scope_str = "%20".join(SCOPES)
    encoded_redirect = urllib.parse.quote(REDIRECT_URI, safe="")
    auth_url = (
        f"https://www.linkedin.com/oauth/v2/authorization?"
        f"response_type=code&"
        f"client_id={CLIENT_ID}&"
        f"redirect_uri={encoded_redirect}&"
        f"state={state}&"
        f"scope={scope_str}"
    )

    print(f"\n1. Starting temporary local listener at {REDIRECT_URI}")
    print("2. Opening your default browser for LinkedIn authorization...")
    print(f"\nIf your browser does not open automatically, visit this link:\n\n{auth_url}\n")

    webbrowser.open(auth_url)

    # Wait for callback
    print("Waiting for callback from LinkedIn (timeout 120 seconds)...")
    start_time = time.time()
    while time.time() - start_time < 120:
        if auth_result["code"] or auth_result["error"]:
            break
        time.sleep(0.5)

    server.shutdown()

    if auth_result["error"]:
        print(f"\n[FAILED] Authorization error: {auth_result['error']}")
        sys.exit(1)

    code = auth_result["code"]
    if not code:
        print("\n[FAILED] Authorization timed out after 120 seconds. Please try again.")
        sys.exit(1)

    if auth_result["state_received"] != state:
        print("\n[FAILED] State parameter mismatch! Possible CSRF attack detected.")
        sys.exit(1)

    print("\nAuthorization code received! Exchanging for access token...")
    try:
        token_data = exchange_code_for_token(code)
    except Exception as e:
        print(f"\n[FAILED] Token exchange failed: {e}")
        sys.exit(1)

    access_token = token_data.get("access_token")
    expires_in = token_data.get("expires_in", 5184000)  # default 60 days
    refresh_token = token_data.get("refresh_token")
    expires_at = time.time() + expires_in

    print("Fetching LinkedIn member profile URN...")
    try:
        member_urn = get_member_urn(access_token)
    except Exception as e:
        print(f"\n[FAILED] Member URN retrieval failed: {e}")
        sys.exit(1)

    token_payload = {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "expires_in": expires_in,
        "expires_at": expires_at,
        "expires_at_iso": datetime.fromtimestamp(expires_at, tz=timezone.utc).isoformat(),
        "author_urn": member_urn,
        "scope": " ".join(SCOPES),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    with open(TOKEN_FILE, "w", encoding="utf-8") as f:
        json.dump(token_payload, f, indent=2)

    print("\n" + "=" * 70)
    print(" [SUCCESS] LinkedIn Authentication Completed!")
    print("=" * 70)
    print(f"Token saved to: {TOKEN_FILE}")
    print(f"Author URN:     {member_urn}")
    print(f"Expires in:     {expires_in // 86400} days ({token_payload['expires_at_iso']})")
    print("\nYou are all set! You can now run:")
    print("  python main.py --dry-run")
    print("=" * 70)


if __name__ == "__main__":
    main()
