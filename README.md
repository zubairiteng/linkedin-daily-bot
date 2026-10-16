# 🚀 LinkedIn Daily Bot

An autonomous Python bot that researches fresh tech news daily, crafts concise, natural, human-sounding LinkedIn posts using an LLM, and publishes them directly to your personal LinkedIn profile using the official LinkedIn OAuth 2.0 API.

---

## 🌟 Key Features

- **Daily News Curation:** Researches news from the past 24 hours across 4 rotating topics:
  1. Machine Learning & AI industry updates
  2. Elon Musk's latest activities (Tesla, xAI, SpaceX, Neuralink)
  3. Bill Gates' latest activities & climate investments
  4. Sam Altman & OpenAI news
- **Anti-Repetition & Topic Rotation:** Never repeats the same topic or person on consecutive days.
- **Strict Deduplication:** Avoids duplicate posts by canonical URL and title similarity matching (`>= 0.70` similarity) against a local SQLite database (`posted.db`).
- **Strict Anti-AI Post Writing Rules:**
  - Exactly 3 to 4 short lines, max ~60 words total.
  - Line 1 states news plainly with concrete facts (numbers, names, dates).
  - Lines 2-3 share real human perspective and why it matters in everyday conversational English.
  - Optional last line: a thoughtful takeaway or genuine question.
  - Exactly 3 to 5 relevant hashtags on a separate line.
  - **Zero AI Buzzwords:** Automatically rejects and regenerates posts containing banned clichés like *"delve"*, *"game-changer"*, *"revolutionize"*, *"in today's fast-paced world"*, *"tapestry"*, *"buckle up"*, etc.
  - **Zero Formatting Clutter:** No em-dashes (`—`), no emoji spam (max 1 tasteful emoji or none), no markdown bolding (`**`), no numbered listicles.
  - Automated post validator with up to 3 smart retry cycles.
- **Official LinkedIn API Integration:**
  - Implements OAuth 2.0 with scopes `w_member_social`, `openid`, `profile`.
  - One-time browser authorization script (`auth.py`) that captures tokens into `token.json`.
  - Modern REST Posts API (`/rest/posts`) with fallback to UGC Posts (`/v2/ugcPosts`).
  - No browser automation (Selenium/Playwright) required.
- **Safety & Review Modes:**
  - `AUTO_POST=true`: Posts directly to LinkedIn.
  - `AUTO_POST=false`: Sends draft to your Telegram chat with interactive **[Approve & Post]** / **[Reject]** buttons.
  - `--dry-run` CLI flag: Preview fetched stories and generated posts without publishing.
  - **Filler Protection:** Automatically skips the day if no fresh (< 24h) news is found.
- **Swappable LLM Providers:** Google Gemini (`gemini-2.5-flash` via `google-genai`), Anthropic Claude (`claude-3-5-sonnet-20241022`), or OpenAI (`gpt-4o-mini`).
- **Free Default News Source:** Uses Google News RSS queries (no API key required). Supports NewsAPI and GNews.

---

## 📁 Project Structure

```
linkedin-daily-bot/
├── .github/
│   └── workflows/
│       └── daily_post.yml         # Daily GitHub Actions cron (10:00 AM PKT / 05:00 UTC)
├── src/
│   ├── __init__.py
│   ├── config.py                  # Environment config and topic definitions
│   ├── database.py                # SQLite (posted.db) deduplication & topic rotation
│   ├── news_fetcher.py            # Multi-topic news fetcher & ranking
│   ├── validator.py               # Human-tone rule checker & validator
│   ├── llm_provider.py            # Swappable LLM clients (Anthropic / OpenAI)
│   ├── post_generator.py          # Few-shot prompts with auto-retry on validation failure
│   ├── linkedin_client.py         # Official LinkedIn API client with token expiry handling
│   └── telegram_notifier.py       # Telegram bot approval workflow
├── tests/
│   ├── __init__.py
│   ├── test_validator.py          # 27 unit tests verifying all post-writing rules
│   └── test_news_dedup.py         # Unit tests for URL cleaning and similarity deduplication
├── scripts/
│   ├── schedule_windows.ps1       # Automated Windows Task Scheduler script
│   └── run_cron.sh                # Linux / macOS cron runner script
├── auth.py                        # One-time OAuth 2.0 browser authorization script
├── main.py                        # Main CLI entrypoint
├── requirements.txt               # Dependencies
├── .env.example                   # Environment variables template
├── .gitignore                     # Git ignore rules
└── README.md                      # Comprehensive documentation
```

---

## 🛠️ Step-by-Step Setup

### Step 1: Clone & Create Virtual Environment

```bash
# Navigate to the project directory
cd linkedin-daily-bot

# Create Python virtual environment
python -m venv venv

# Activate virtual environment
# Windows (PowerShell):
.\venv\Scripts\Activate.ps1
# Windows (CMD):
.\venv\Scripts\activate.bat
# Linux / macOS:
source venv/bin/activate

# Install required dependencies
pip install -r requirements.txt
```

---

### Step 2: Create a LinkedIn Developer App

To post to your personal LinkedIn profile using the official API, you need a free LinkedIn Developer App:

1. Go to the [LinkedIn Developer Portal](https://www.linkedin.com/developers/apps).
2. Click **Create app**.
3. Fill in the required details:
   - **App name:** e.g., `My Daily Tech Pulse`
   - **LinkedIn Page:** Link your company page (or create a quick personal company page if you don't have one).
   - **App logo:** Upload any square image (min 100x100px).
   - Agree to terms and click **Create app**.
4. Go to the **Products** tab of your app and request access to:
   - **Share on LinkedIn** (provides `w_member_social` permission).
   - **Sign In with LinkedIn using OpenID Connect** (provides `openid` and `profile` permissions to identify your member URN).
   *(Access to these two products is granted instantly).*
5. Go to the **Auth** tab:
   - Note your **Client ID** and **Client Secret**.
   - Under **OAuth 2.0 settings**, click the edit pencil next to **Authorized redirect URLs for your app**.
   - Add: `http://localhost:8080/callback`
   - Click **Update**.

---

### Step 3: Configure Environment Variables (`.env`)

Copy `.env.example` to `.env`:

```bash
cp .env.example .env
```

Open `.env` in any text editor and fill in your values:

```env
# 1. LinkedIn Credentials (from Step 2)
LINKEDIN_CLIENT_ID=your_client_id_here
LINKEDIN_CLIENT_SECRET=your_client_secret_here
LINKEDIN_REDIRECT_URI=http://localhost:8080/callback

# 2. LLM Provider (Google Gemini default, or anthropic / openai)
LLM_PROVIDER=gemini
GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_MODEL=gemini-2.5-flash

# Optional Anthropic Claude:
ANTHROPIC_API_KEY=sk-ant-api03-...
ANTHROPIC_MODEL=claude-3-5-sonnet-20241022

# 3. News Source (rss is free and requires no key)
NEWS_SOURCE=rss

# 4. Mode and Safety Controls
AUTO_POST=false

# 5. Telegram Review Bot (Optional, needed if AUTO_POST=false)
TELEGRAM_BOT_TOKEN=123456789:ABCdefGHIjklMNO...
TELEGRAM_CHAT_ID=987654321
```

---

### Step 4: Run One-Time LinkedIn Authorization (`auth.py`)

Run the authorization script in your terminal:

```bash
python auth.py
```

**What happens:**
1. A temporary local server starts on `http://localhost:8080/callback`.
2. Your default web browser opens the LinkedIn OAuth authorization page.
3. Sign in to your LinkedIn account and click **Allow**.
4. The local server captures the authorization code, exchanges it for an access token, fetches your profile member URN (`urn:li:person:...`), and saves everything to `token.json`.
5. You will see a success message in your terminal and browser.

> [!NOTE]
> LinkedIn personal access tokens are typically valid for **60 days**. When the token expires, `main.py` will log a clear message prompting you to re-run `python auth.py`.

---

### Step 5: Test with Dry Run

Test the entire news fetching, story selection, post writing, and validation pipeline without publishing to LinkedIn:

```bash
python main.py --dry-run
```

You can also test a specific topic:
```bash
python main.py --dry-run --topic elon_musk
python main.py --dry-run --topic bill_gates
python main.py --dry-run --topic openai_ceo
python main.py --dry-run --topic ai_ml
```

---

## 🤖 Telegram Approval Setup (`AUTO_POST=false`)

When `AUTO_POST=false`, the bot drafts the post and sends it to your Telegram chat before posting. You can review the post and approve it with one click:

1. Open Telegram and search for [@BotFather](https://t.me/BotFather).
2. Send `/newbot`, choose a name and username (e.g., `my_linkedin_bot`).
3. Copy the HTTP API token provided by BotFather into `TELEGRAM_BOT_TOKEN` in `.env`.
4. Send a message to your new bot (e.g., `/start`).
5. To get your numeric user chat ID:
   - Search for [@userinfobot](https://t.me/userinfobot) on Telegram and start it (it replies with your numeric ID).
   - Copy this ID into `TELEGRAM_CHAT_ID` in `.env`.
6. When the bot runs, it will send the draft post to Telegram with **[✅ Approve & Post]** and **[❌ Reject]** buttons. You can also reply with `"approve"` or `"reject"`.

*(If Telegram is not configured, the bot falls back to an interactive terminal prompt `[y/N]` so you can review locally).*

---

## ⏰ Daily Scheduling (Human-Mimic Random Schedule)

The GitHub Actions workflow mimics real human posting habits by triggering once daily starting at **8:00 AM Pakistan Standard Time (03:00 UTC)** and sleeping for an unpredictable, randomized duration before publishing:

### Option 1: GitHub Actions (Recommended — Runs Free in the Cloud)

Runs autonomously in the cloud even when your personal computer is turned off.

1. **Create a new Private GitHub Repository:**
   - Go to [github.com/new](https://github.com/new) and create a repository named `linkedin-daily-bot`.
   - **Crucial:** Make sure you choose **Private** to keep your code and configuration private.

2. **Push your code to GitHub:**
   ```bash
   git init
   git add .
   git commit -m "feat: complete linkedin-daily-bot with human-mimic schedule"
   git branch -M main
   git remote add origin https://github.com/<YOUR-GITHUB-USERNAME>/linkedin-daily-bot.git
   git push -u origin main
   ```

3. **Configure GitHub Secrets:**
   In your GitHub repository, go to **Settings > Secrets and variables > Actions**, click **New repository secret**, and add:
   - `GEMINI_API_KEY`: Your Gemini API key from Google AI Studio.
   - `LINKEDIN_CLIENT_ID`: Your LinkedIn App Client ID.
   - `LINKEDIN_CLIENT_SECRET`: Your LinkedIn App Client Secret.
   - `LINKEDIN_TOKEN_JSON`: Paste the entire content of your local `token.json` file.
   - *(Optional)* `TELEGRAM_BOT_TOKEN` & `TELEGRAM_CHAT_ID`: If you want Telegram alerts.
   - *(Optional)* `GEMINI_MODEL`: Defaults to `gemini-2.5-flash` with automatic fallback.

4. **How the Human-Mimic Behavior Works:**
   - The workflow triggers daily at `03:00 UTC` (8:00 AM PKT).
   - A randomized delay step sleeps for an unpredictable amount of time (between 0 and 5 hours by default) before publishing.
   - `posted.db` is automatically restored and cached between runs via `actions/cache`, ensuring topic rotation and URL deduplication work seamlessly without polluting your git history.
   - You can trigger the bot anytime manually from **Actions > Daily LinkedIn News Post > Run workflow** (with an option to skip the random delay for immediate testing).

---

### Option 2: Windows Task Scheduler

Use the included PowerShell setup script to register a daily task:

1. Open PowerShell and run:
   ```powershell
   .\scripts\schedule_windows.ps1 -Time "10:00 AM"
   ```
2. The task `LinkedInDailyBot` will be registered to run every day at 10:00 AM local time.
3. To test run it immediately:
   ```powershell
   Start-ScheduledTask -TaskName "LinkedInDailyBot"
   ```
4. To remove the task:
   ```powershell
   .\scripts\schedule_windows.ps1 -Unregister
   ```

---

### Option 3: Linux / macOS Crontab

1. Open crontab in edit mode:
   ```bash
   crontab -e
   ```
2. Add the cron entry:
   - If your server timezone is already in PKT:
     ```bash
     0 10 * * * cd /path/to/linkedin-daily-bot && ./scripts/run_cron.sh
     ```
   - If your server timezone is UTC:
     ```bash
     0 5 * * * cd /path/to/linkedin-daily-bot && ./scripts/run_cron.sh
     ```

---

## 🧪 Unit Testing

Run the full pytest suite to verify all 31 unit tests:

```bash
pytest -v
```

Tests include:
- Validation of 3-line and 4-line posts.
- Word count limits (<= 60 words).
- Rejection of all banned AI buzzwords and clichés (*delve*, *game-changer*, *revolutionize*, *unleash*, *tapestry*, etc.).
- Hashtag count enforcement (3 to 5 hashtags).
- Emoji spam prevention (max 1 emoji).
- Em-dash ban enforcement (`—`).
- Markdown formatting prevention.
- Listicle prevention.
- URL query-stripping deduplication and title similarity matching.
- SQLite topic rotation tracking.

---

## 📋 Post-Writing Rules Reference

Every generated post adheres to these strict rules:

| Rule | Requirement |
| :--- | :--- |
| **Line Count** | Exactly 3 to 4 short lines of body text |
| **Word Count** | Maximum ~60 words total in the body text |
| **Line 1 Hook** | Plain statement of fact with a number, name, or date |
| **Lines 2-3** | Why it matters in everyday conversational English (natural human voice) |
| **Optional Line 4** | A brief genuine question or thoughtful takeaway |
| **Hashtags** | Exactly 3 to 5 hashtags on a separate line |
| **Link** | The article URL placed on its own line at the end |
| **Banned Clichés** | *delve, game-changer, revolutionize, unleash, unlock, in today's fast-paced world, landscape, tapestry, testament, it's important to note, navigate, leverage, cutting-edge, ever-evolving, buckle up, let that sink in, here's the thing* |
| **Formatting** | No em-dashes (`—`), max 1 emoji (or none), no markdown bolding (`**`), no numbered lists |

---

## 🔒 Security & Privacy

- `token.json`, `posted.db`, `bot.log`, and `.env` are automatically ignored by `.gitignore`.
- Secrets are never hardcoded in source files.
- In GitHub Actions, secrets are securely injected from GitHub Secrets at runtime.

---

## 📄 License

MIT License. Free for personal and commercial use.
