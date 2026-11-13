"""
CLI utility to generate and preview LinkedIn Infographic Cards using the production template.

Usage:
    # 1. Generate the standard reference placeholder template:
    python scripts/generate_template.py --placeholder

    # 2. Generate a custom card:
    python scripts/generate_template.py --topic "AI TOOLS" --h1 "MASTER CURSOR" --h2 "IN 2026" --out my_card.png
"""

import argparse
from pathlib import Path
import sys

# Ensure project root is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.card_generator import (
    CardContent,
    generate_infographic_card,
    get_placeholder_template
)


def main():
    parser = argparse.ArgumentParser(description="Generate 1200x1200px LinkedIn Tech Infographic Cards")
    parser.add_argument("--placeholder", action="store_true", help="Generate the official reference placeholder template")
    parser.add_argument("--topic", type=str, default="TOPIC / CATEGORY", help="Category badge text")
    parser.add_argument("--h1", type=str, default="YOUR MAIN", help="Headline Line 1 (White)")
    parser.add_argument("--h2", type=str, default="HEADLINE HERE", help="Headline Line 2 (Yellow emphasis)")
    parser.add_argument("--intro", type=str, default="Add a clear, useful introduction here.", help="Introduction sentence")
    parser.add_argument("--brand", type=str, default="[Zubair Ahmad | AI Trainer]", help="Footer brand name")
    parser.add_argument("--out", type=str, default="custom_template.png", help="Output PNG path")
    args = parser.parse_args()

    out_path = Path(args.out)

    if args.placeholder:
        content = get_placeholder_template()
    else:
        content = CardContent(
            badge=args.topic,
            headline_line1=args.h1,
            headline_line2=args.h2,
            subtitle=args.intro,
            points=[
                ("01", "Step one title", "Explain the action clearly.\nKeep it brief and practical."),
                ("02", "Step two title", "Explain the action clearly.\nKeep it brief and practical."),
                ("03", "Step three title", "Explain the action clearly.\nKeep it brief and practical.")
            ],
            brand_name=args.brand
        )

    res = generate_infographic_card(content, out_path)
    print(f"Successfully generated 1200x1200px infographic card: {res.resolve()}")


if __name__ == "__main__":
    main()
