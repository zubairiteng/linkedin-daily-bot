"""
Post generator module for LinkedIn Daily Bot.
Uses LLM with strict few-shot human tone prompts, coupled with the PostValidator
to automatically regenerate drafts if any rule is violated (up to 3 retries).
"""

import logging
from typing import Optional, Tuple
from .news_fetcher import NewsStory
from .config import config
from .llm_provider import LLMProvider, GeminiProvider, get_llm_provider
from .validator import validate_post, ValidationResult, BANNED_PHRASES, split_post_components

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = f"""You are a master LinkedIn tech creator writing viral, high-engagement developer posts for Zubair Ahmad's profile.
Target Audience: Software developers, CS students, tech professionals, AI engineers, and tech founders.

Language: Clean, punchy, conversational, and authoritative English.
Goal: Maximum organic reach, saves, shares, and high comment velocity that triggers the LinkedIn feed algorithm.

Core High-Engagement Formula:
1. HOOK (Line 1): Start with a bold pattern interrupt, a painful developer mistake, or a counter-intuitive reality that stops the mobile scroll in 2 seconds. Must be under 12 words.
2. CONTEXT (Line 2): Explain in 1 short sentence why this matters right now for modern developers.
3. ACTIONABLE VALUE (Lines 3-5): Exactly 3 numbered practical tips (1️⃣, 2️⃣, 3️⃣ or 1., 2., 3.). People hit 'Like' and 'Save' when they see structured, actionable practices rather than vague summaries.
4. TAKEAWAY: One crisp, memorable takeaway sentence.
5. LOW-FRICTION COMMENT TRIGGER (Final Line): Ask a simple, 2-second question (e.g. A vs B choice, or Agree/Disagree) that compels people to drop a comment instantly.
6. HASHTAGS: Exactly 3 to 5 relevant hashtags on a separate line.

Strict Rules (Violation will cause the post to be rejected):
1. Line count: 4 to 10 short readable lines (use blank line breaks so it is easily skimmable on mobile screens).
2. Word count: 70 to 160 words total across all body lines.
3. NO corporate PR jargon, accounting fluff, or dry press release summaries.
4. NO self-introductions (never say 'As an AI Trainer' or 'As a CS Lecturer'). Dive straight into the insight.
5. ABSOLUTELY NO EXTERNAL LINKS OR URLS. Never include any web link in the post body (to maximize LinkedIn algorithmic reach).
6. Use 2 to 4 functional, clean emojis (like 1️⃣, 2️⃣, 3️⃣, 💡, 👇) for visual hierarchy. NO emoji spam.
7. BANNED words and clichés (NEVER use any of these):
{', '.join(BANNED_PHRASES)}
8. NO em-dashes (—). Use standard punctuation.
9. NO bolding (**word**), NO markdown headers (#).

---
HIGH-ENGAGEMENT POST EXAMPLES:

Example 1 (AI Coding & Developer Productivity):
Most developers are using AI coding assistants completely wrong.

They ask Cursor or Copilot to generate 200 lines at once, and then spend 2 hours debugging hallucinations.

Here is the 3-step formula senior engineers follow instead:
1️⃣ Break features into single modular functions before prompting.
2️⃣ Feed your database schemas and type definitions first.
3️⃣ Treat every AI suggestion as an unverified pull request.

The goal is not typing faster. The goal is architecting cleaner systems. 💡

Which coding tool do you use daily?
A) Cursor
B) VS Code + Copilot
C) Claude / ChatGPT web
Drop your choice below 👇

#AICoding #Python #SoftwareEngineering #DeveloperProductivity #TechCommunity

Example 2 (AI Careers, Students & FYP):
If you are still building a basic CRUD web app for your portfolio, stop.

Tech hiring has fundamentally shifted. Recruiters do not need another generic clone.

To stand out in competitive job markets, add these 3 elements:
1️⃣ Integrate a local open-source LLM or RAG pipeline.
2️⃣ Build over real, domain-specific custom documents.
3️⃣ Ship a live demo with clean GitHub documentation and unit tests.

Practical implementation always beats theoretical certificates. 💡

What is the biggest roadblock in your current project? Drop it below 👇

#TechCareers #ComputerScience #Python #GenerativeAI #SoftwareEngineering

Example 3 (Open Source AI & Local LLMs):
Open-source AI has permanently broken cloud monopoly.

You no longer need an expensive monthly subscription to run powerful models on your machine.

Here are 3 high-value skills to master right now:
1️⃣ Run local models with Ollama and connect them to Python scripts.
2️⃣ Fine-tune lightweight models on proprietary datasets.
3️⃣ Build multi-agent workflows with strict validation gates.

The developers who master local AI setups will lead the next decade. 💡

Do you prefer cloud APIs or local open-source models? Let me know below 👇

#OpenSourceAI #DeepSeek #Python #MachineLearning #AIEngineering
---
Output ONLY the post text. Do not wrap in quotes or code blocks.
"""


class PostGenerator:
    """
    Generates and validates LinkedIn posts using an LLM provider.
    Supports Google Gemini (via google-genai), Anthropic Claude, and OpenAI.
    """

    def __init__(
        self,
        llm_provider: Optional[LLMProvider] = None,
        provider: Optional[str] = None,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        max_retries: int = 3
    ):
        if llm_provider is not None:
            self.llm = llm_provider
        else:
            # Resolve provider from parameters or .env
            p_name = (provider or config.llm_provider).lower()
            if p_name == "gemini":
                gemini_key = api_key or config.gemini_api_key
                gemini_model = model or config.gemini_model or "gemini-2.5-flash"
                self.llm = GeminiProvider(api_key=gemini_key, model_name=gemini_model)
            else:
                self.llm = get_llm_provider(config)

        self.max_retries = max_retries

    def _build_user_prompt(self, story: NewsStory, feedback: Optional[str] = None) -> str:
        """Construct user prompt for LLM."""
        prompt = (
            f"Here is today's verified tech development:\n"
            f"- Topic: {story.topic_name}\n"
            f"- Headline: {story.title}\n"
            f"- Outlet/Source: {story.source}\n"
            f"- Published: {story.published_at.strftime('%A, %B %d, %Y')}\n"
            f"- Summary: {story.summary}\n\n"
            f"Write a viral, high-engagement LinkedIn post in English following the Hook -> Context -> 3 Actionable Tips -> Low-friction Question formula. "
            f"Do NOT include any external links or URLs. "
            f"Do NOT start with or use self-labels like 'As an AI Trainer' or 'As a CS Lecturer'; dive directly into the insight."
        )

        if feedback:
            prompt += (
                f"\n\nCRITICAL FIX REQUIRED:\n"
                f"Your previous attempt was REJECTED by our automated validator with these errors:\n"
                f"{feedback}\n"
                f"Rewrite the post and ensure every single error is completely fixed."
            )
        return prompt

    def generate_post(self, story: NewsStory) -> Tuple[str, ValidationResult]:
        """
        Generate a validated post for the given story.
        Retries up to self.max_retries times if validation fails.
        """
        logger.info(f"Generating post for story: '{story.title}' ({story.topic_name})")
        feedback: Optional[str] = None
        last_result: Optional[ValidationResult] = None
        last_draft = ""

        for attempt in range(1, self.max_retries + 1):
            logger.info(f"Post generation attempt {attempt}/{self.max_retries}")
            user_prompt = self._build_user_prompt(story, feedback)

            try:
                raw_draft = self.llm.generate(
                    system_prompt=SYSTEM_PROMPT,
                    user_prompt=user_prompt,
                    temperature=0.6 if attempt == 1 else 0.4  # Lower temperature on retry
                )
            except Exception as e:
                logger.error(f"LLM generation failed on attempt {attempt}: {e}")
                raise

            # Strip any accidental URL outputted by LLM to ensure maximum organic reach
            draft = raw_draft.strip()
            body_lines, hashtags, existing_link = split_post_components(draft)
            if existing_link:
                draft = draft.replace(existing_link, "").strip()

            validation = validate_post(draft)
            last_result = validation
            last_draft = draft

            if validation.is_valid:
                logger.info(f"Post successfully validated on attempt {attempt}: {validation.summary()}")
                return draft, validation

            # Format feedback for LLM retry
            error_list = "\n".join(f"- {err}" for err in validation.errors)
            feedback = (
                f"Validation failed:\n{error_list}\n"
                f"Previous rejected text was:\n\"\"\"\n{draft}\n\"\"\""
            )
            logger.warning(
                f"Attempt {attempt} failed validation: {'; '.join(validation.errors)}. Retrying..."
            )

        logger.error(f"Failed to generate valid post after {self.max_retries} attempts.")
        return last_draft, last_result

    def generate_card_content(self, story: NewsStory, post_text: str):
        """
        Generate structured English content for the 1200x1200 visual tech infographic card.
        Uses LLM to summarize the key rules and falls back reliably if parsing fails.
        """
        import json
        import re
        from .card_generator import CardContent

        card_prompt = (
            f"Based on this tech topic:\n"
            f"- Topic: {story.topic_name}\n"
            f"- Title: {story.title}\n"
            f"- Context: {story.summary}\n\n"
            f"Create structured data for a 1200x1200px square royal blue tech infographic card in English.\n"
            f"Style rules:\n"
            f"- badge: Topic/Category in 2 to 4 uppercase words (e.g. 'AI CODING TOOLS', 'AGENTIC WORKFLOWS')\n"
            f"- headline_line1: 2 to 4 punchy uppercase words (white text)\n"
            f"- headline_line2: 2 to 4 punchy uppercase words (yellow accent emphasis)\n"
            f"- subtitle: A clear, useful 1-sentence introduction (10 to 16 words max)\n"
            f"- points: exactly 3 actionable steps with [number, step_title, step_description]\n"
            f"  * number: '01', '02', '03'\n"
            f"  * step_title: 2 to 4 bold words\n"
            f"  * step_description: 2 short lines (10 to 18 words total)\n\n"
            f"Output strictly valid JSON with this exact schema:\n"
            f"{{\n"
            f'  "badge": "AI CODING TOOLS",\n'
            f'  "headline_line1": "MASTER CURSOR &",\n'
            f'  "headline_line2": "AI CODING TODAY",\n'
            f'  "subtitle": "Essential practices to write cleaner code and eliminate bugs.",\n'
            f'  "points": [\n'
            f'    ["01", "Modular Prompting", "Break large tasks into single functions.\\nNever ask AI to build everything at once."],\n'
            f'    ["02", "Feed Type Definitions", "Always provide interfaces and data schemas.\\nEliminate hallucinated properties early."],\n'
            f'    ["03", "Rigorous Verification", "Treat AI code as an unverified PR.\\nAlways run unit tests before merging."]\n'
            f'  ]\n'
            f"}}"
        )

        try:
            raw = self.llm.generate(
                system_prompt="You are a senior graphic designer and technical writer. Output ONLY a valid JSON object matching the requested schema.",
                user_prompt=card_prompt,
                temperature=0.3
            )
            match = re.search(r"\{.*\}", raw, re.DOTALL)
            if match:
                data = json.loads(match.group(0))
                badge = data.get("badge", "PRACTICAL AI GUIDE")
                h1 = data.get("headline_line1", "3 ESSENTIAL RULES")
                h2 = data.get("headline_line2", "FOR MODERN DEVELOPERS")
                sub = data.get("subtitle", "Essential practices to write clean code and build faster.")
                pts = [
                    (str(p[0]), str(p[1]), str(p[2]))
                    for p in data.get("points", [])
                    if len(p) >= 3
                ]
                if len(pts) >= 3:
                    return CardContent(
                        badge=badge,
                        headline_line1=h1,
                        headline_line2=h2,
                        subtitle=sub,
                        points=pts[:3],
                        brand_name="Zubair Ahmad"
                    )
        except Exception as e:
            logger.warning(f"Card JSON generation failed ({e}), using robust topic fallback.")

        # Reliable default fallback
        return CardContent(
            badge="AI DEVELOPER ROADMAP",
            headline_line1="3 CORE AI RULES",
            headline_line2="FOR 2026 DEVELOPERS",
            subtitle="Essential practices to write clean code, avoid bugs, and build faster.",
            points=[
                ("01", "Modular Prompting", "Never ask AI to build an entire feature at once.\nBreak tasks into small modular functions."),
                ("02", "Context & Schema First", "Feed database models and type signatures first.\nEliminates hallucinated logic completely."),
                ("03", "Review & Unit Testing", "Treat AI suggestions as a first draft.\nAlways verify edge cases with unit tests.")
            ],
            brand_name="Zubair Ahmad"
        )


def create_gemini_generator(
    api_key: Optional[str] = None,
    model: str = "gemini-2.5-flash",
    max_retries: int = 3
) -> PostGenerator:
    """Create a PostGenerator configured with Google Gemini (gemini-2.5-flash)."""
    gemini_key = api_key or config.gemini_api_key
    provider = GeminiProvider(api_key=gemini_key, model_name=model)
    return PostGenerator(llm_provider=provider, max_retries=max_retries)

