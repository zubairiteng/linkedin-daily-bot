"""
Card Generator module for LinkedIn Daily Bot.
Generates reusable, high-contrast, professional 1200x1200px (1:1 square) tech infographic cards
using Pillow for maximum visual engagement on LinkedIn feeds and ads.

Specifications:
- Canvas: 1200x1200px square PNG
- Colors:
    * Royal blue (#153EAB): Main background
    * Deep blue (#10245A): Background depth & card containers
    * Gold (#D4AF37): Numbers, circle badges, and separators
    * Yellow (#FFD54A): Headline emphasis (Line 2)
    * White (#FFFFFF): Main text, headlines, and descriptions
- Typography:
    * Main headline: Montserrat ExtraBold (76-92px, default 84px)
    * Introduction: Inter Medium (36-40px, default 38px)
    * Step headings: Montserrat Bold (44-50px, default 46px)
    * Step descriptions: Inter Regular (34-38px, default 34px)
    * Footer: Inter SemiBold (28-32px, default 30px)
"""

from dataclasses import dataclass, field
import logging
import os
from pathlib import Path
from typing import List, Tuple, Optional
from PIL import Image, ImageDraw, ImageFont

logger = logging.getLogger(__name__)

# Color Palette Constants
COLOR_ROYAL_BLUE = "#153EAB"
COLOR_DEEP_BLUE = "#10245A"
COLOR_CARD_BG = "#173EA6"
COLOR_GOLD = "#D4AF37"
COLOR_YELLOW = "#FFD54A"
COLOR_WHITE = "#FFFFFF"

# Fonts Directory
FONTS_DIR = Path(__file__).resolve().parent / "fonts"


@dataclass
class CardContent:
    """Structured data required to render the 1200x1200 square tech infographic template."""
    badge: str               # TOPIC / CATEGORY
    headline_line1: str      # Main headline line 1 (White)
    headline_line2: str      # Headline emphasis line 2 (Yellow)
    subtitle: str            # Introduction (Inter Medium, White)
    points: List[Tuple[str, str, str]]  # list of (number_str, title, description)
    brand_name: str = "[Zubair Ahmad | AI Trainer]"


def _load_font(family: str, weight: str, size: int) -> ImageFont.ImageFont:
    """
    Load exact typography using local font files in src/fonts/, with system fallback.
    family: 'montserrat' or 'inter'
    weight: 'regular', 'medium', 'semibold', 'bold', 'extrabold'
    size: int
    """
    family_l = family.lower()
    weight_l = weight.lower()

    try:
        if family_l == "montserrat":
            if weight_l == "extrabold":
                p = FONTS_DIR / "Montserrat-ExtraBold.ttf"
            elif weight_l in ("bold", "semibold"):
                p = FONTS_DIR / "Montserrat-Bold.ttf"
            else:
                p = FONTS_DIR / "Montserrat-Bold.ttf"
            if p.exists():
                return ImageFont.truetype(str(p), size)

        elif family_l == "inter":
            inter_p = FONTS_DIR / "Inter[opsz,wght].ttf"
            if inter_p.exists():
                font = ImageFont.truetype(str(inter_p), size)
                w_map = {
                    "regular": 400,
                    "medium": 500,
                    "semibold": 600,
                    "bold": 700,
                }
                w_val = w_map.get(weight_l, 400)
                try:
                    font.set_variation_by_axes([18, w_val])
                except Exception:
                    pass
                return font
    except Exception as e:
        logger.warning(f"Error loading local font {family} {weight}: {e}")

    # Fallback to system fonts
    candidates = [
        # Windows
        'C:/Windows/Fonts/segoeuib.ttf' if "bold" in weight_l else 'C:/Windows/Fonts/segoeui.ttf',
        'C:/Windows/Fonts/arialbd.ttf' if "bold" in weight_l else 'C:/Windows/Fonts/arial.ttf',
        # Linux
        '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf' if "bold" in weight_l else '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
        '/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf' if "bold" in weight_l else '/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf',
    ]
    for cand in candidates:
        if os.path.exists(cand):
            try:
                return ImageFont.truetype(cand, size)
            except Exception:
                continue

    return ImageFont.load_default()


def _wrap_text_to_width(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.ImageFont,
    max_width: int = 860,
    max_lines: int = 2
) -> List[str]:
    """Wrap description text cleanly to at most max_lines within max_width pixels."""
    if "\n" in text:
        lines = [line.strip() for line in text.split("\n") if line.strip()]
        return lines[:max_lines]

    words = text.split()
    lines = []
    current = ""
    for w in words:
        test = (current + " " + w).strip()
        bbox = draw.textbbox((0, 0), test, font=font)
        if (bbox[2] - bbox[0]) > max_width:
            if current:
                lines.append(current)
            current = w
        else:
            current = test
    if current:
        lines.append(current)

    # Shorten and add ellipsis if exceeding max_lines
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        while lines[-1] and (draw.textbbox((0, 0), lines[-1] + "...", font=font)[2] - draw.textbbox((0, 0), lines[-1] + "...", font=font)[0]) > max_width:
            parts = lines[-1].split()
            if len(parts) <= 1:
                break
            lines[-1] = " ".join(parts[:-1])
        if not lines[-1].endswith("..."):
            lines[-1] += "..."

    return lines


def generate_infographic_card(content: CardContent, output_path: Path) -> Path:
    """
    Render a 1200x1200px production tech infographic card matching the exact specifications.
    Returns the path to the saved PNG file.
    """
    width, height = 1200, 1200
    img = Image.new("RGB", (width, height))
    draw = ImageDraw.Draw(img)

    # 1. Background gradient: Royal Blue #153EAB at top down to Deep Blue #10245A depth at bottom
    # RGB(#153EAB) = (21, 62, 171) -> RGB(#10245A) = (16, 36, 90)
    for y in range(height):
        ratio = y / height
        r = int(21 * (1 - ratio) + 14 * ratio)
        g = int(62 * (1 - ratio) + 32 * ratio)
        b = int(171 * (1 - ratio) + 85 * ratio)
        draw.line([(0, y), (width, y)], fill=(r, g, b))

    # 2. Typography
    f_h1 = _load_font("montserrat", "extrabold", 84)
    f_h2 = _load_font("montserrat", "extrabold", 84)
    f_topic = _load_font("montserrat", "bold", 30)
    f_intro = _load_font("inter", "medium", 38)
    f_step_h = _load_font("montserrat", "bold", 46)
    f_step_num = _load_font("montserrat", "extrabold", 54)
    f_step_desc = _load_font("inter", "regular", 34)
    f_footer = _load_font("inter", "semibold", 30)

    margin_left = 70
    margin_right = 1130

    # 3. Topic Header & Separator Line
    topic_text = content.badge.upper()
    draw.text((margin_left, 55), topic_text, fill=COLOR_WHITE, font=f_topic)
    t_bbox = draw.textbbox((margin_left, 55), topic_text, font=f_topic)
    line_x_start = t_bbox[2] + 25
    if line_x_start < margin_right:
        draw.line([(line_x_start, 72), (margin_right, 72)], fill=COLOR_GOLD, width=5)

    # 4. Main Headline (Line 1: White, Line 2: Yellow emphasis)
    h1 = content.headline_line1.strip()
    h2 = content.headline_line2.strip()
    if not h2 and " " in h1:
        # Auto-split single headline if line2 is empty
        words = h1.split()
        mid = len(words) // 2
        h1 = " ".join(words[:mid])
        h2 = " ".join(words[mid:])

    draw.text((margin_left, 110), h1, fill=COLOR_WHITE, font=f_h1)
    if h2:
        draw.text((margin_left, 200), h2, fill=COLOR_YELLOW, font=f_h2)

    # 5. Introduction (Inter Medium, White)
    intro_lines = _wrap_text_to_width(draw, content.subtitle, f_intro, max_width=1060, max_lines=2)
    intro_y = 310
    for line in intro_lines:
        draw.text((margin_left, intro_y), line, fill=COLOR_WHITE, font=f_intro)
        intro_y += 46

    # 6. Steps Layout
    steps = content.points[:3]
    card_h = 175
    card_spacing = 30
    start_y = 410

    circle_x = 135
    circle_r = 66

    # Draw vertical connecting line in Gold (#D4AF37) between circle centers
    if len(steps) > 1:
        c1_cy = start_y + card_h // 2
        last_cy = start_y + (len(steps) - 1) * (card_h + card_spacing) + card_h // 2
        draw.line([(circle_x, c1_cy), (circle_x, last_cy)], fill=COLOR_GOLD, width=6)

    for i, (num, title, desc) in enumerate(steps):
        card_y = start_y + i * (card_h + card_spacing)
        cy = card_y + card_h // 2

        # Card container box (Deep blue depth #173EA6)
        draw.rounded_rectangle(
            [(circle_x, card_y), (margin_right, card_y + card_h)],
            radius=14,
            fill=COLOR_CARD_BG
        )

        # Gold circle badge (#D4AF37)
        draw.ellipse(
            [(circle_x - circle_r, cy - circle_r), (circle_x + circle_r, cy + circle_r)],
            fill=COLOR_GOLD
        )

        # Circle number (White, Montserrat ExtraBold, centered)
        num_str = str(num).zfill(2) if str(num).isdigit() else str(num)
        n_bbox = draw.textbbox((0, 0), num_str, font=f_step_num)
        nw = n_bbox[2] - n_bbox[0]
        nh = n_bbox[3] - n_bbox[1]
        draw.text((circle_x - nw / 2, cy - nh / 2 - 4), num_str, fill=COLOR_WHITE, font=f_step_num)

        # Step Heading (White, Montserrat Bold)
        text_x = circle_x + circle_r + 30
        draw.text((text_x, card_y + 24), title, fill=COLOR_WHITE, font=f_step_h)

        # Step Description (White, Inter Regular, max 2 short lines)
        desc_lines = _wrap_text_to_width(draw, desc, f_step_desc, max_width=860, max_lines=2)
        desc_y = card_y + 82
        for dl in desc_lines:
            draw.text((text_x, desc_y), dl, fill=COLOR_WHITE, font=f_step_desc)
            desc_y += 42

    # 7. Footer
    draw.line([(margin_left, 1070), (margin_right, 1070)], fill=COLOR_GOLD, width=5)
    brand_text = content.brand_name or "[Zubair Ahmad | AI Trainer]"
    draw.text((margin_left, 1105), brand_text, fill=COLOR_WHITE, font=f_footer)

    save_text = "Save for later"
    s_bbox = draw.textbbox((0, 0), save_text, font=f_footer)
    sw = s_bbox[2] - s_bbox[0]
    draw.text((margin_right - sw, 1105), save_text, fill=COLOR_WHITE, font=f_footer)

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(output_path, "PNG", optimize=True)
    logger.info(f"Generated visual tech card at: {output_path} ({os.path.getsize(output_path)} bytes)")
    return output_path


def get_placeholder_template() -> CardContent:
    """Return the exact default template specification matching the user reference image."""
    return CardContent(
        badge="TOPIC / CATEGORY",
        headline_line1="YOUR MAIN",
        headline_line2="HEADLINE HERE",
        subtitle="Add a clear, useful introduction here.",
        points=[
            ("01", "Step one title", "Explain the action clearly.\nKeep it brief and practical."),
            ("02", "Step two title", "Explain the action clearly.\nKeep it brief and practical."),
            ("03", "Step three title", "Explain the action clearly.\nKeep it brief and practical."),
        ],
        brand_name="[Your name / brand]"
    )


if __name__ == "__main__":
    import sys
    out = Path("generated_template.png")
    if len(sys.argv) > 1:
        out = Path(sys.argv[1])
    generate_infographic_card(get_placeholder_template(), out)
    print(f"Generated reference template: {out.resolve()}")
