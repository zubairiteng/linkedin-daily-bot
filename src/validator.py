"""
Validator module for LinkedIn posts.
Enforces strict rules for post length, line count, banned AI buzzwords,
formatting, hashtags, and emoji limits.
"""

from dataclasses import dataclass, field
import re
from typing import List, Dict, Any
from urllib.parse import urlparse

import unicodedata

# Banned AI buzzwords and clichés (checked case-insensitively)
BANNED_PHRASES = [
    "delve",
    "delving",
    "game-changer",
    "game changer",
    "revolutionize",
    "revolutionizing",
    "revolutionary",
    "unleash",
    "unleashing",
    "unlock",
    "unlocking",
    "in today's fast-paced world",
    "in todays fast-paced world",
    "fast-paced world",
    "landscape",
    "tapestry",
    "testament",
    "it's important to note",
    "its important to note",
    "navigate",
    "navigating",
    "leverage",
    "leveraging",
    "cutting-edge",
    "cutting edge",
    "ever-evolving",
    "ever evolving",
    "buckle up",
    "let that sink in",
    "here's the thing",
    "heres the thing",
]

def count_emojis(text: str) -> int:
    """
    Count visual emoji symbols in text.
    Handles high unicode pictographs, emoticons, and symbols.
    """
    count = 0
    for char in text:
        cp = ord(char)
        # Skip variation selectors and ZWJ
        if cp in (0xFE0E, 0xFE0F, 0x200D) or (0xE0020 <= cp <= 0xE007F):
            continue
        # Check standard emoji / symbol codepoint ranges
        is_emoji = (
            (0x1F300 <= cp <= 0x1FAFF) or  # Pictographs, Emoticons, Transport, Symbols
            (0x2600 <= cp <= 0x27BF) or    # Miscellaneous Symbols, Dingbats
            (unicodedata.category(char) in ("So", "Sk") and cp > 0x2000)
        )
        if is_emoji:
            count += 1
    return count

# Markdown indicators (bold, headers, bullet list items)
MARKDOWN_PATTERNS = [
    (re.compile(r"\*\*[^*]+\*\*"), "Bold markdown (**text**)"),
    (re.compile(r"__[^_]+__"), "Bold markdown (__text__)"),
    (re.compile(r"^#+\s+", re.MULTILINE), "Markdown header (#)"),
    (re.compile(r"^\s*[\*\-•]\s+", re.MULTILINE), "Bullet list marker"),
    (re.compile(r"^\s*\d+[\.\)]\s+", re.MULTILINE), "Numbered listicle"),
    (re.compile(r"`[^`]+`"), "Inline code/backticks"),
]


@dataclass
class ValidationResult:
    """Outcome of validating a LinkedIn post."""
    is_valid: bool
    errors: List[str] = field(default_factory=list)
    metrics: Dict[str, Any] = field(default_factory=dict)

    def summary(self) -> str:
        """Human-readable validation summary."""
        if self.is_valid:
            return (
                f"VALID: {self.metrics.get('body_lines')} body lines, "
                f"{self.metrics.get('word_count')} words, "
                f"{self.metrics.get('hashtag_count')} hashtags, "
                f"{self.metrics.get('emoji_count')} emoji(s)"
            )
        return "FAILED: " + "; ".join(self.errors)


def is_url(text: str) -> bool:
    """Check if string is a standalone URL."""
    text = text.strip()
    if not (text.startswith("http://") or text.startswith("https://")):
        return False
    try:
        parsed = urlparse(text)
        return bool(parsed.scheme and parsed.netloc)
    except Exception:
        return False


def is_hashtag_line(line: str) -> bool:
    """Check if a line consists predominantly of hashtags."""
    tokens = [t.strip() for t in line.split() if t.strip()]
    if not tokens:
        return False
    hashtag_tokens = [t for t in tokens if t.startswith("#")]
    # If 70% or more tokens are hashtags, consider it a hashtag line
    return len(hashtag_tokens) / len(tokens) >= 0.7


def split_post_components(content: str):
    """
    Split post into:
    - body_lines: main thoughts/lines (excluding hashtag line and link line)
    - hashtags: list of hashtag strings
    - link: optional URL string
    """
    raw_lines = [line.strip() for line in content.strip().splitlines()]
    non_empty_lines = [l for l in raw_lines if l]

    body_lines: List[str] = []
    hashtags: List[str] = []
    link: str = ""

    for line in non_empty_lines:
        if is_url(line):
            link = line
        elif is_hashtag_line(line):
            found_tags = re.findall(r"#\w+", line)
            hashtags.extend(found_tags)
        else:
            # Check if this line has inline hashtags at the end
            found_tags = re.findall(r"#\w+", line)
            if found_tags and len(found_tags) >= 3:
                # Treated as hashtag line
                hashtags.extend(found_tags)
            else:
                body_lines.append(line)

    return body_lines, hashtags, link


def validate_post(content: str, max_words: int = 130) -> ValidationResult:
    """
    Validate a LinkedIn post string according to strict high-engagement rules:
    - Exactly 3 to 5 short lines of body text.
    - Max ~130 words total in the body text (comfortably fits Urdu sentences with technical English terms).
    - No banned AI buzzwords / clichés.
    - 3 to 5 hashtags on a separate line.
    - No em-dashes (—).
    - Max 1 emoji (or none).
    - No bold/markdown formatting or numbered listicles.
    """
    errors: List[str] = []
    content_clean = content.strip()

    if not content_clean:
        return ValidationResult(is_valid=False, errors=["Post content is empty."])

    body_lines, hashtags, link = split_post_components(content_clean)

    # 1. Line count check: Exactly 3 to 4 short body lines
    body_line_count = len(body_lines)
    if body_line_count < 3:
        errors.append(f"Too few body lines: {body_line_count} (must be exactly 3 to 4 lines).")
    elif body_line_count > 4:
        errors.append(f"Too many body lines: {body_line_count} (must be exactly 3 to 4 lines).")

    # 2. Word count check: Max ~60 words in body text
    body_text = " ".join(body_lines)
    words = re.findall(r"\b[\w'-]+\b", body_text)
    word_count = len(words)
    if word_count > max_words:
        errors.append(f"Word count exceeds limit: {word_count} words (max is {max_words}).")
    elif word_count < 15:
        errors.append(f"Post is suspiciously short: {word_count} words (minimum ~15 words expected).")

    # 3. Banned phrases check (case-insensitive)
    lower_content = content_clean.lower()
    banned_found: List[str] = []
    for phrase in BANNED_PHRASES:
        pattern = r"\b" + re.escape(phrase) + r"\b"
        if re.search(pattern, lower_content):
            banned_found.append(phrase)

    if banned_found:
        errors.append(f"Contains banned AI clichés/buzzwords: {', '.join(banned_found)}.")

    # 4. Hashtag count check: 3 to 5 relevant hashtags
    hashtag_count = len(hashtags)
    if hashtag_count < 3:
        errors.append(f"Too few hashtags: {hashtag_count} (must have 3 to 5 hashtags).")
    elif hashtag_count > 5:
        errors.append(f"Too many hashtags: {hashtag_count} (must have 3 to 5 hashtags).")

    # 5. Em-dash check: No em-dashes (—) allowed
    if "—" in content_clean or "--" in content_clean:
        errors.append("Em-dash ('—' or '--') detected. Em-dashes are banned.")

    # 6. Emoji count check: Max 1 emoji across post, no spam
    emoji_count = count_emojis(content_clean)
    if emoji_count > 1:
        errors.append(f"Emoji spam detected: {emoji_count} emojis found (max 1 emoji or none allowed).")

    # 7. Markdown / bold / listicle check
    for pattern, desc in MARKDOWN_PATTERNS:
        if pattern.search(content_clean):
            errors.append(f"Contains disallowed formatting: {desc}.")

    metrics = {
        "body_lines": body_line_count,
        "word_count": word_count,
        "hashtag_count": hashtag_count,
        "emoji_count": emoji_count,
        "has_link": bool(link),
        "banned_words_found": banned_found,
    }

    is_valid = len(errors) == 0
    return ValidationResult(is_valid=is_valid, errors=errors, metrics=metrics)
