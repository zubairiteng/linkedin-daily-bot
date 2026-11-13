"""
Card Generator module for LinkedIn Daily Bot.
Generates sleek, high-contrast, professional 1080x1350px (4:5 portrait) tech infographic cards
using Pillow for maximum visual takeover and engagement on the LinkedIn mobile app.
"""

from dataclasses import dataclass
import logging
import os
from pathlib import Path
from typing import List, Tuple
from PIL import Image, ImageDraw, ImageFont

logger = logging.getLogger(__name__)


@dataclass
class CardContent:
    """Structured data required to render a high-engagement tech card."""
    badge: str
    headline_line1: str
    headline_line2: str
    subtitle: str
    points: List[Tuple[str, str, str]]  # list of (number_str, title, description)


def _get_font(size: int, bold: bool = False) -> ImageFont.ImageFont:
    """Find and load clean modern typography across Windows and Linux runners."""
    candidates = [
        # Windows
        'C:/Windows/Fonts/segoeuib.ttf' if bold else 'C:/Windows/Fonts/segoeui.ttf',
        'C:/Windows/Fonts/arialbd.ttf' if bold else 'C:/Windows/Fonts/arial.ttf',
        'C:/Windows/Fonts/calibrib.ttf' if bold else 'C:/Windows/Fonts/calibri.ttf',
        # Linux (GitHub Actions Ubuntu)
        '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf' if bold else '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
        '/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf' if bold else '/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf',
        '/usr/share/fonts/truetype/freefont/FreeSansBold.ttf' if bold else '/usr/share/fonts/truetype/freefont/FreeSans.ttf',
    ]
    for p in candidates:
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                continue
    return ImageFont.load_default()


def _wrap_text(text: str, max_chars: int = 50) -> List[str]:
    """Wrap description text cleanly across multiple lines."""
    words = text.split()
    lines = []
    current = ""
    for w in words:
        if len(current + " " + w) > max_chars:
            lines.append(current)
            current = w
        else:
            current = (current + " " + w).strip()
    if current:
        lines.append(current)
    return lines


def generate_infographic_card(content: CardContent, output_path: Path) -> Path:
    """
    Render a 1080x1350px high-contrast tech card and save to disk.
    Returns the path to the saved PNG file.
    """
    width, height = 1080, 1350
    # Canvas
    img = Image.new("RGB", (width, height), color="#080C14")
    draw = ImageDraw.Draw(img)

    # Outer decorative frame
    draw.rounded_rectangle(
        [(36, 36), (width - 36, height - 36)],
        radius=30,
        outline="#1E293B",
        width=2,
        fill="#0D1322"
    )

    # Top Category Badge Pill
    badge_text = content.badge.upper()
    pill_font = _get_font(20, bold=True)
    draw.rounded_rectangle([(70, 70), (460, 120)], radius=16, outline="#38BDF8", width=2, fill="#0F2338")
    draw.text((95, 83), badge_text, fill="#38BDF8", font=pill_font)

    # Headlines
    h1_font = _get_font(42, bold=True)
    draw.text((70, 150), content.headline_line1, fill="#FFFFFF", font=h1_font)
    draw.text((70, 205), content.headline_line2, fill="#38BDF8", font=h1_font)

    # Subtitle
    sub_font = _get_font(23, bold=False)
    draw.text((70, 275), content.subtitle, fill="#94A3B8", font=sub_font)

    # 3 Content Boxes
    card_y = 340
    box_height = 245
    box_spacing = 30

    card_title_font = _get_font(28, bold=True)
    card_num_font = _get_font(26, bold=True)
    card_desc_font = _get_font(21, bold=False)

    for num, title, desc in content.points[:3]:
        # Container box
        draw.rounded_rectangle(
            [(70, card_y), (width - 70, card_y + box_height)],
            radius=22,
            outline="#334155",
            width=1,
            fill="#131B2E"
        )
        # Number badge
        draw.rounded_rectangle([(95, card_y + 24), (155, card_y + 78)], radius=12, fill="#1E293B")
        draw.text((108, card_y + 34), num, fill="#38BDF8", font=card_num_font)

        # Title
        draw.text((175, card_y + 34), title, fill="#F8FAFC", font=card_title_font)

        # Body description
        lines = _wrap_text(desc, max_chars=54)
        text_y = card_y + 98
        for line in lines:
            draw.text((95, text_y), line, fill="#94A3B8", font=card_desc_font)
            text_y += 32

        card_y += box_height + box_spacing

    # Footer Divider & Branding
    draw.line([(70, height - 110), (width - 70, height - 110)], fill="#1E293B", width=2)
    footer_font = _get_font(21, bold=True)
    draw.text((70, height - 85), "📌 Save this post for your next project", fill="#64748B", font=footer_font)
    draw.text((width - 430, height - 85), "Zubair Ahmad | AI Practitioner", fill="#38BDF8", font=footer_font)

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(output_path, "PNG", optimize=True)
    logger.info(f"Generated visual tech card at: {output_path} ({os.path.getsize(output_path)} bytes)")
    return output_path
