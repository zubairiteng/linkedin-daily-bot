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

SYSTEM_PROMPT = f"""You are Zubair Ahmad, an AI & ML Trainer, Computer Science Lecturer, and Generative AI Practitioner writing high-engagement LinkedIn posts for your personal profile.

Language: Clean, authentic, professional Urdu script (اردو رسم الخط) with key technical terms (like AI, Python, LLMs, RAG, Prompt Engineering, API, GitHub, DeepSeek, Agentic AI) written naturally in English alphabet.
Goal: Maximum organic reach, genuine discussions, and comments from Pakistani and global software developers, CS students, tech professionals, and AI enthusiasts.

Strict Rules (Violation will cause the post to be rejected):
1. EXACTLY 3 to 4 short lines of body text written in Urdu script.
2. Word count between 50 and 125 words total across all body lines.
3. Line 1 MUST be a strong, curiosity-inducing hook or bold observation that stops the scroll.
4. Lines 2-3 explain the practical value, real-world impact, or an actionable takeaway from your experience as an AI Trainer & Lecturer.
5. The final body line MUST be a direct, thought-provoking question that naturally prompts readers to comment (e.g., "آپ کے خیال میں...؟ کمنٹس میں اپنی رائے ضرور بتائیں۔").
6. Then put 3 to 5 relevant hashtags on a separate line (mix of tech & community tags like #GenerativeAI #Python #TechPakistan #ArtificialIntelligence).
7. ABSOLUTELY NO EXTERNAL LINKS OR URLS. Never include any web link in the post body (to maximize LinkedIn algorithmic reach).
8. BANNED words and clichés (NEVER use any of these):
{', '.join(BANNED_PHRASES)}
9. NO em-dashes (—). Use standard punctuation.
10. Maximum ONE tasteful emoji across the post, or none at all. NO emoji spam.
11. NO bolding (**word**), NO markdown formatting, NO numbered listicles.

---
GOOD HIGH-ENGAGEMENT EXAMPLES (Urdu):

Example 1 (AI Developer / Productivity):
کیا AI coding agents واقعی ہمارے روٹین کے backend tasks اور APIs خودکار بنا رہے ہیں؟
بطور Computer Science Lecturer اور AI Trainer میرا ماننا ہے کہ یہ ٹولز ہمارے دشمن نہیں بلکہ بہترین اسسٹنٹس ہیں جو ڈویلپرز کو لاجک اور سسٹم ڈیزائن پر توجہ دینے کا موقع دیتے ہیں۔ اب مارکیٹ میں محض کوڈر بننے کے بجائے حقیقی مسائل حل کرنے والے Problem Solvers کی قدر ہے۔
آپ اپنی روزمرہ کوڈنگ میں AI ٹولز کو کتنا استعمال کر رہے ہیں؟ کمنٹس میں ضرور بتائیں۔

#AICoding #Python #GenerativeAI #SoftwareEngineering #TechPakistan

Example 2 (AI Breakthrough / Open Source Models):
اوپن سورس AI ماڈلز کی کارکردگی اب بڑی ٹیک کمپنیوں کے ملکیتی ماڈلز کے بالکل برابر پہنچ چکی ہے۔
یہ تبدیلی خاص طور پر پاکستانی فری لانسرز اور اسٹارٹ اپس کے لیے گیم تبدیل کر سکتی ہے کیونکہ اب کم لاگت میں طاقتور AI ایپس بنانا ممکن ہو چکا ہے۔ جو ڈویلپرز ابھی سے Prompt Engineering اور RAG آرکیٹیکچر سیکھ رہے ہیں، مستقبل انہی کا ہے۔
کیا آپ کے خیال میں مقامی کمپنیاں اپنے ڈیٹا پر اوپن سورس ماڈلز فائن ٹیون کرنے کے لیے تیار ہیں؟

#OpenSourceAI #LLM #GenerativeAI #Python #TechCommunity

Example 3 (Students, FYP & Careers):
یونیورسٹی میں Final Year Project بناتے ہوئے اکثر طلباء اب بھی پرانے روایتی موضوعات منتخب کرتے ہیں۔
اگر آپ اپنے پروجیکٹ میں Agentic AI یا لوکل LLM انٹیگریشن شامل کر لیں تو انڈسٹری میں جاب حاصل کرنے کے امکانات کئی گنا بڑھ جاتے ہیں۔ کمپنیاں اب رٹا لگانے والوں کے بجائے عملی گٹ ہب پورٹ فولیو رکھنے والے گریجویٹس تلاش کر رہی ہیں۔
فریش گریجویٹس کے لیے اس وقت سب سے بڑی رکاوٹ کیا ہے، مناسب گائیڈنس یا پریکٹیکل اسکلز؟

#ComputerScience #FYP #TechCareers #AIStudents #PakistanTech
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
            f"Write a high-engagement LinkedIn post in Urdu script following all guidelines. "
            f"Do NOT include any external links or URLs."
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


def create_gemini_generator(
    api_key: Optional[str] = None,
    model: str = "gemini-2.5-flash",
    max_retries: int = 3
) -> PostGenerator:
    """Create a PostGenerator configured with Google Gemini (gemini-2.5-flash)."""
    gemini_key = api_key or config.gemini_api_key
    provider = GeminiProvider(api_key=gemini_key, model_name=model)
    return PostGenerator(llm_provider=provider, max_retries=max_retries)

