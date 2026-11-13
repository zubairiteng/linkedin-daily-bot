"""
Unit tests for card_generator module.
Verifies the 1200x1200 square tech infographic card generation and styling rules.
"""

from pathlib import Path
from PIL import Image
import pytest

from src.card_generator import (
    CardContent,
    generate_infographic_card,
    get_placeholder_template,
    _load_font,
    _wrap_text_to_width
)


def test_get_placeholder_template():
    """Verify placeholder template content matches user specifications."""
    tpl = get_placeholder_template()
    assert tpl.badge == "TOPIC / CATEGORY"
    assert tpl.headline_line1 == "YOUR MAIN"
    assert tpl.headline_line2 == "HEADLINE HERE"
    assert len(tpl.points) == 3
    assert tpl.brand_name == "[Your name / brand]"


def test_generate_infographic_card(tmp_path):
    """Verify card generator renders an exact 1200x1200px PNG image."""
    tpl = get_placeholder_template()
    out_path = tmp_path / "test_card.png"

    result_path = generate_infographic_card(tpl, out_path)
    assert result_path.exists()
    assert result_path.stat().st_size > 50000  # Should be high-res PNG

    with Image.open(result_path) as img:
        assert img.size == (1200, 1200)
        assert img.format == "PNG"
        assert img.mode == "RGB"


def test_wrap_text_to_width():
    """Verify text wrapping limits to max_lines and respects width."""
    from PIL import ImageDraw
    dummy = Image.new("RGB", (100, 100))
    draw = ImageDraw.Draw(dummy)
    font = _load_font("inter", "regular", 34)

    long_text = "This is a very long technical description explaining how developers should write clean code, avoid critical bugs, and verify their implementations thoroughly."
    lines = _wrap_text_to_width(draw, long_text, font, max_width=860, max_lines=2)
    assert len(lines) <= 2


def test_custom_content_card(tmp_path):
    """Verify card generation with dynamic custom technical content."""
    content = CardContent(
        badge="AI CODING TOOLS",
        headline_line1="MASTER CURSOR &",
        headline_line2="AI CODING TODAY",
        subtitle="Essential practices to write cleaner code and eliminate bugs.",
        points=[
            ("01", "Modular Prompts", "Break complex tasks into small functions.\nNever generate entire features at once."),
            ("02", "Feed Type Schemas", "Provide interface signatures and data models.\nEliminates hallucinated attributes completely."),
            ("03", "Unit Test Checks", "Treat AI output as an unreviewed pull request.\nAlways verify edge cases with tests.")
        ],
        brand_name="[Zubair Ahmad | AI Trainer]"
    )
    out_path = tmp_path / "custom_tech_card.png"
    result = generate_infographic_card(content, out_path)
    assert result.exists()

    with Image.open(result) as img:
        assert img.size == (1200, 1200)
