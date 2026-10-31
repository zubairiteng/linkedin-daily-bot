"""
Unit tests for the LinkedIn post validator.
"""

import pytest
from src.validator import validate_post, BANNED_PHRASES


def test_valid_three_line_post():
    """Valid post with 3 lines, concrete numbers, 4 hashtags, no emojis, link at end."""
    content = (
        "OpenAI released custom GPT benchmarks yesterday showing a 35% speedup.\n"
        "Lower latency matters a lot when integrating models into real-time voice apps.\n"
        "Curious if anyone has noticed real performance gains in production?\n\n"
        "#AI #OpenAI #TechNews #MachineLearning\n\n"
        "https://techcrunch.com/example-story"
    )
    result = validate_post(content)
    assert result.is_valid, f"Expected valid, got errors: {result.errors}"
    assert result.metrics["body_lines"] == 3
    assert result.metrics["word_count"] <= 60
    assert result.metrics["hashtag_count"] == 4
    assert result.metrics["emoji_count"] == 0
    assert result.metrics["has_link"] is True


def test_valid_four_line_post_with_one_emoji():
    """Valid post with 4 lines, 1 allowed emoji, 3 hashtags."""
    content = (
        "SpaceX caught the 232-foot Starship booster on the pad Sunday morning.\n"
        "Reusing heavy boosters within hours flips the unit economics of spaceflight.\n"
        "It turns rocket launches into routine turnaround infrastructure.\n"
        "Would love to hear your thoughts on this milestone.\n\n"
        "#SpaceX #Engineering #Aerospace 🚀"
    )
    result = validate_post(content)
    assert result.is_valid, f"Expected valid, got errors: {result.errors}"
    assert result.metrics["body_lines"] == 4
    assert result.metrics["emoji_count"] == 1
    assert result.metrics["hashtag_count"] == 3


def test_reject_too_few_lines():
    """Posts with fewer than 3 body lines must fail."""
    content = (
        "Bill Gates funded a clean cement company today.\n"
        "Heavy industry accounts for huge emissions.\n\n"
        "#CleanEnergy #Climate #Tech"
    )
    result = validate_post(content)
    assert not result.is_valid
    assert any("Too few body lines" in err for err in result.errors)


def test_reject_too_many_lines():
    """Posts with more than 4 body lines must fail."""
    content = (
        "Tesla launched its Robotaxi Cybercab prototype in California.\n"
        "It lacks steering wheels and pedals entirely.\n"
        "Elon Musk expects volume production before 2027.\n"
        "Regulatory clearance will remain the biggest hurdle.\n"
        "Are you excited to ride in one someday?\n\n"
        "#Tesla #AutonomousVehicles #Robotics"
    )
    result = validate_post(content)
    assert not result.is_valid
    assert any("Too many body lines" in err for err in result.errors)


def test_reject_excessive_words():
    """Posts exceeding max words (130 words) must fail."""
    content = (
        "Yesterday in San Francisco, an extremely long and unnecessarily verbose announcement was made by several prominent technology executives regarding recent advancements in artificial intelligence models and distributed GPU compute clusters across global enterprise data centers worldwide.\n"
        "This announcement went into tremendous detail about why having massive amounts of memory bandwidth allows developers to train larger models without experiencing significant bottleneck issues during communication phases and network fabric saturation across multiple servers in high density racks with redundant power supplies and specialized cooling mechanisms.\n"
        "We are closely watching how this trend develops over the coming months and years as hardware prices continue to evolve across the competitive computing industry with new accelerators entering the market from multiple chip manufacturers worldwide offering different cost performance tradeoffs for hyperscalers and engineering teams building foundation models.\n\n"
        "#AI #Hardware #Tech"
    )
    result = validate_post(content, max_words=130)
    assert not result.is_valid
    assert any("Word count exceeds limit" in err for err in result.errors)


def test_valid_urdu_post():
    """Valid high-engagement Urdu post with English tech terms and no external links."""
    content = (
        "کیا AI coding agents واقعی ہمارے روٹین کے backend tasks اور APIs خودکار بنا رہے ہیں؟\n"
        "بطور Computer Science Lecturer اور AI Trainer میرا ماننا ہے کہ یہ ٹولز ہمارے دشمن نہیں بلکہ بہترین اسسٹنٹس ہیں جو ڈویلپرز کو لاجک اور سسٹم ڈیزائن پر توجہ دینے کا موقع دیتے ہیں۔ اب مارکیٹ میں محض کوڈر بننے کے بجائے حقیقی مسائل حل کرنے والے Problem Solvers کی قدر ہے۔\n"
        "آپ اپنی روزمرہ کوڈنگ میں AI ٹولز کو کتنا استعمال کر رہے ہیں؟ کمنٹس میں ضرور بتائیں۔\n\n"
        "#AICoding #Python #GenerativeAI #SoftwareEngineering #TechPakistan"
    )
    result = validate_post(content)
    assert result.is_valid, f"Expected valid, got errors: {result.errors}"
    assert result.metrics["body_lines"] == 3
    assert 50 <= result.metrics["word_count"] <= 130
    assert result.metrics["hashtag_count"] == 5
    assert result.metrics["has_link"] is False


@pytest.mark.parametrize("banned_word", [
    "delve",
    "game-changer",
    "revolutionize",
    "unleash",
    "unlock",
    "in today's fast-paced world",
    "landscape",
    "tapestry",
    "testament",
    "it's important to note",
    "navigate",
    "leverage",
    "cutting-edge",
    "ever-evolving",
    "buckle up",
    "let that sink in",
    "here's the thing",
])
def test_reject_banned_phrases(banned_word):
    """Every single banned phrase must be caught and rejected."""
    content = (
        f"Sam Altman announced a new model to {banned_word} in October.\n"
        "This update could shift how developers approach practical automation.\n"
        "What do you think about this direction?\n\n"
        "#AI #OpenAI #TechNews"
    )
    result = validate_post(content)
    assert not result.is_valid
    assert any("banned AI clichés/buzzwords" in err for err in result.errors)


def test_reject_em_dash():
    """Em-dashes (—) are strictly prohibited."""
    content = (
        "Google released their latest Gemini report today — with new benchmarks.\n"
        "It shows significant improvements on reasoning tasks.\n"
        "Will you test this model on your daily workflow?\n\n"
        "#AI #Google #Benchmarks"
    )
    result = validate_post(content)
    assert not result.is_valid
    assert any("Em-dash" in err for err in result.errors)


def test_reject_emoji_spam():
    """More than 1 emoji must trigger rejection."""
    content = (
        "xAI activated the 100k H100 Colossus cluster in Memphis this week.\n"
        "Training runs of this scale reduce training epochs by weeks.\n"
        "Excited to see what Grok 3 brings to the table.\n\n"
        "🚀🔥💡 #xAI #ElonMusk #AI"
    )
    result = validate_post(content)
    assert not result.is_valid
    assert any("Emoji spam detected" in err for err in result.errors)


def test_reject_markdown_formatting():
    """Markdown bold or headings must be rejected."""
    content = (
        "**OpenAI** just released new documentation for developers on Monday.\n"
        "The simplified endpoints should save hours during integration.\n"
        "Have you checked out the new docs yet?\n\n"
        "#OpenAI #Developers #API"
    )
    result = validate_post(content)
    assert not result.is_valid
    assert any("disallowed formatting" in err for err in result.errors)


def test_reject_numbered_listicle():
    """Numbered listicles must be rejected."""
    content = (
        "1. Anthropic launched Sonnet 3.5 computer use yesterday.\n"
        "2. The agent can navigate web browsers and desktop tools.\n"
        "3. This is a very interesting step forward.\n\n"
        "#AI #Anthropic #Agents"
    )
    result = validate_post(content)
    assert not result.is_valid
    assert any("Numbered listicle" in err for err in result.errors)


def test_reject_too_few_or_too_many_hashtags():
    """Hashtags must be strictly between 3 and 5."""
    # Only 2 hashtags -> fails
    content_few = (
        "Bill Gates shared his annual reading list on Tuesday.\n"
        "Most books focus on climate engineering and global health.\n"
        "Which book is currently on your nightstand?\n\n"
        "#Books #BillGates"
    )
    result_few = validate_post(content_few)
    assert not result_few.is_valid
    assert any("Too few hashtags" in err for err in result_few.errors)

    # 6 hashtags -> fails
    content_many = (
        "Bill Gates shared his annual reading list on Tuesday.\n"
        "Most books focus on climate engineering and global health.\n"
        "Which book is currently on your nightstand?\n\n"
        "#Books #BillGates #Reading #Climate #Tech #Health"
    )
    result_many = validate_post(content_many)
    assert not result_many.is_valid
    assert any("Too many hashtags" in err for err in result_many.errors)
