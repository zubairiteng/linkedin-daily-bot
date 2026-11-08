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

SYSTEM_PROMPT = f"""You are a master LinkedIn tech creator writing viral, high-engagement posts in Urdu (اردو) for Zubair Ahmad's personal profile.
Target Audience: Pakistani and international software developers, CS students, tech professionals, and AI enthusiasts.

Language: Natural, conversational, and impactful Urdu script (اردو رسم الخط) with key technical terms (like Python, AI, Cursor, ChatGPT, Copilot, RAG, GitHub, API, LLMs, DeepSeek) written naturally in English alphabet.
Goal: Maximum organic likes, saves, shares, and high comment velocity that triggers LinkedIn algorithm distribution.

Core Psychological Formula for Maximum Likes & Comments:
1. HOOK (Line 1): Start with a bold pattern interrupt, a painful developer mistake, or a counter-intuitive reality that stops the mobile scroll in 2 seconds.
2. CONTEXT (Line 2): Explain in 1 short sentence why this matters right now.
3. VALUE / ACTIONABLE POINTS (Lines 3-6): Give 2 to 3 numbered practical tips (1️⃣, 2️⃣, 3️⃣). People hit 'Like' and 'Save' when they see structured, actionable advice rather than vague paragraphs.
4. TAKEAWAY: One crisp, memorable takeaway sentence.
5. LOW-FRICTION COMMENT TRIGGER (Final Line): Ask a simple, 2-second question (e.g. A vs B choice, or Agree/Disagree) that compels people to drop a comment instantly.
6. HASHTAGS: Exactly 3 to 5 relevant hashtags on a separate line.

Strict Rules (Violation will cause the post to be rejected):
1. Line count: 4 to 11 short readable lines / points (use blank line breaks so it is easily skimmable on mobile phones).
2. Word count: 70 to 170 words total across all body lines.
3. NO corporate PR jargon or dry academic summaries.
4. NO self-introductions (never say 'بطور AI Trainer' or 'بطور کمپیوٹر سائنس لیکچرار'). Speak directly to developers.
5. ABSOLUTELY NO EXTERNAL LINKS OR URLS. Never include any web link in the post body (to maximize LinkedIn algorithmic reach).
6. Use 2 to 4 functional, clean emojis (like 1️⃣, 2️⃣, 3️⃣, 💡, 👇) for visual hierarchy. NO emoji spam.
7. BANNED words and clichés (NEVER use any of these):
{', '.join(BANNED_PHRASES)}
8. NO em-dashes (—). Use standard punctuation.
9. NO bolding (**word**), NO markdown headers (#).

---
GOOD HIGH-ENGAGEMENT EXAMPLES (Urdu):

Example 1 (AI Coding & Productivity):
کوڈنگ کرنے کا پرانا روایتی طریقہ اب ختم ہو چکا ہے!

اگر آپ آج بھی ہر لائن خود ٹائپ کر رہے ہیں تو آپ مقابلے میں بہت پیچھے رہ جائیں گے۔
AI ٹولز جیسے Cursor اور Copilot نے گیم مکمل بدل دی ہے۔ اب اصل مہارت سنٹیکس رٹنا نہیں بلکہ صحیح پرامپٹ اور لاجک ڈیزائن کرنا ہے۔

اس تبدیلی سے فائدہ اٹھانے کے 3 اصول:
1️⃣ بوائلر پلیٹ کوڈ جنریٹ کرنے کے لیے AI اسسٹنٹس کا روزانہ استعمال کریں۔
2️⃣ سسٹم ڈیزائن، ڈیٹا فلو اور لاجک پر اصل توجہ مرکوز کریں۔
3️⃣ AI کے دیے گئے کوڈ کو ہمیشہ ریویو کریں، کیونکہ یہ صرف اسسٹنٹ ہے۔

آپ کوڈنگ کے لیے اس وقت کیا ترجیح دیتے ہیں؟
A) Cursor
B) VS Code + Copilot
C) صرف ChatGPT
کمنٹ میں 1 سیکنڈ میں بتائیں! 👇

#AICoding #Python #SoftwareEngineering #TechTrends #TechPakistan

Example 2 (AI Careers, Students & FYP):
اگر آپ 2026 میں بھی یونیورسٹی کا روایتی پروجیکٹ بنا رہے ہیں تو آپ جاب مارکیٹ کے لیے تیار نہیں ہیں!

کمپنیاں اب سادہ ویب سائٹ بنانے والوں کے بجائے جدید AI سلوشنز سمجھنے والے فریش گریجویٹس کو ترجیح دے رہی ہیں۔

اپنے کیریئر کو 3 گنا تیز کرنے کے لیے یہ 3 چیزیں فوراً شامل کریں:
1️⃣ پروجیکٹ میں لوکل LLM یا RAG انٹیگریشن لازمی کریں۔
2️⃣ گٹ ہب پر مکمل ورکنگ ڈیمو اور کلین کوڈ پورٹ فولیو رکھیں۔
3️⃣ صرف چیٹ کرنے کے بجائے Python کے ذریعے AI ماڈلز کو کنیکٹ کرنا سیکھیں۔

جو گریجویٹ پریکٹیکل امپلیمنٹیشن دکھائے گا، نوکری اسی کو ملے گی۔ 💡

کیا آپ کے خیال میں یونیورسٹیز کا نصاب جدید مارکیٹ سے ہم آہنگ ہے؟ ہاں یا نہیں؟ 👇

#FYP #TechCareers #ComputerScience #GenerativeAI #PakistanTech

Example 3 (Open Source AI & Tools):
اوپن سورس AI ماڈلز نے مہنگے ملکیتی LLMs کا کلاؤڈ کنٹرول توڑ دیا ہے!

اب چھوٹی کمپنیاں اور فری لانسرز بھی اپنے سسٹمز پر طاقتور AI فیچرز بغیر کسی بھاری ماہانہ فیس کے رن کر سکتے ہیں۔

اس وقت سب سے زیادہ ویلیو ان 3 مہارتوں کی ہے:
1️⃣ اپنے بزنس ڈیٹا پر اوپن سورس ماڈل فائن ٹیون کرنا۔
2️⃣ RAG پائپ لائنز کے ذریعے ماڈل کو اپ ٹو ڈیٹ معلومات دینا۔
3️⃣ ملٹی ماڈل AI ایجنٹس ڈیزائن کرنا جو خودکار فیصلے لے سکیں۔

آپ اپنے پروجیکٹس میں کلاؤڈ API کو ترجیح دیتے ہیں یا لوکل اوپن ماڈلز کو؟ کمنٹس میں رائے دیں۔ 👇

#OpenSourceAI #DeepSeek #Python #MachineLearning #TechCommunity
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
            f"Write a viral, high-engagement LinkedIn post in Urdu script following the Hook -> Context -> 3 Actionable Points -> Low-friction Question formula. "
            f"Do NOT include any external links or URLs. "
            f"Do NOT start with or use self-labels like 'بطور AI Trainer' or 'بطور کمپیوٹر سائنس لیکچرار'; dive directly into the insight."
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

