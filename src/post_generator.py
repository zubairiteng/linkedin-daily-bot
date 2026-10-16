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

SYSTEM_PROMPT = f"""You are a tech professional writing short, thoughtful daily updates for your personal LinkedIn profile.
Your posts must sound 100% human, authentic, and grounded—NEVER like AI-generated promotional fluff.

Strict Rules (Violation will cause the post to be rejected):
1. EXACTLY 3 to 4 short lines of body text.
2. MAXIMUM ~60 words total across all body lines. Be concise and crisp.
3. Line 1 MUST be a factual hook that states the news plainly with a concrete number, name, or date.
4. Lines 2-3 explain why it matters in simple everyday conversational English, written like a real person sharing an honest thought. First-person perspective ("I think", "In my experience") is fine.
5. Optional 4th line can be a short genuine question or takeaway.
6. Then put 3 to 5 relevant hashtags on a separate line (e.g. #AI #TechNews #Engineering).
7. Put the exact article link at the very end on its own line.
8. ABSOLUTELY BANNED words and clichés (NEVER use any of these):
{', '.join(BANNED_PHRASES)}
9. NO em-dashes (—). Use regular punctuation (commas, periods).
10. NO emoji spam. Use at most ONE tasteful emoji, or none at all. NO "🚀🔥💡" combos.
11. NO bolding (**word**), NO markdown formatting, NO numbered listicles or bullet points.
12. DO NOT invent facts or stats. Use only the facts present in the news provided.

---
GOOD HUMAN-STYLE EXAMPLES:

Example 1:
Anthropic released updated benchmarks on Tuesday showing a 40% reduction in code generation latency.
For daily developer workflows, smaller response lags keep you in flow much better than bigger models with long pauses.
Curious if you value speed or reasoning depth more in your daily coding?

#ArtificialIntelligence #Coding #SoftwareEngineering #TechNews

https://techcrunch.com/sample-1

Example 2:
SpaceX completed the fifth Starship flight on Sunday and caught the booster directly on the launch pad.
Seeing a 230-foot rocket stage return cleanly turns orbital hardware into rapid turnaround infrastructure.
It completely changes the cost equation for heavy payload delivery.

#SpaceX #ElonMusk #Aerospace #Engineering

https://space.com/sample-2

Example 3:
Bill Gates committed $1.5 billion through Breakthrough Energy yesterday to co-finance commercial green cement facilities.
Heavy industry generates huge emissions but usually struggles to attract early private risk capital.
Targeting industrial emissions directly is where climate funding will make the biggest dent.

#CleanEnergy #BillGates #ClimateTech #Sustainability

https://bloomberg.com/sample-3
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
            f"Here is today's verified news story:\n"
            f"- Topic: {story.topic_name}\n"
            f"- Headline: {story.title}\n"
            f"- Outlet/Source: {story.source}\n"
            f"- Published: {story.published_at.strftime('%A, %B %d, %Y')}\n"
            f"- Summary: {story.summary}\n"
            f"- Article URL: {story.url}\n\n"
            f"Write a short LinkedIn post following all guidelines. "
            f"Include the article URL '{story.url}' at the very bottom."
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

            # Ensure the authentic article URL is cleanly attached at the end
            draft = raw_draft.strip()
            body_lines, hashtags, existing_link = split_post_components(draft)
            
            # If model generated a placeholder URL from few-shot examples, swap it
            if existing_link and existing_link != story.url:
                draft = draft.replace(existing_link, story.url)
            elif not existing_link and story.url:
                draft = f"{draft}\n\n{story.url}"

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


def create_gemini_generator(
    api_key: Optional[str] = None,
    model: str = "gemini-2.5-flash",
    max_retries: int = 3
) -> PostGenerator:
    """Create a PostGenerator configured with Google Gemini (gemini-2.5-flash)."""
    gemini_key = api_key or config.gemini_api_key
    provider = GeminiProvider(api_key=gemini_key, model_name=model)
    return PostGenerator(llm_provider=provider, max_retries=max_retries)

