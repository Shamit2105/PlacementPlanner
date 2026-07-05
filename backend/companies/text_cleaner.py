import re

from bs4 import BeautifulSoup


class TextCleaner:
    MIN_LINE_LENGTH = 15

    NOISE_PATTERNS = [
        r"copyright.*",
        r"all rights reserved.*",
        r"privacy policy.*",
        r"terms of service.*",
        r"cookie policy.*",
        r"share this.*",
        r"follow us.*",
        r"subscribe.*",
        r"advertisement.*",
        r"sign in.*",
        r"login.*",
        r"register.*",
        r"table of contents.*",
    ]

    @classmethod
    def clean(cls, text: str) -> str:

        if not text:
            return ""

        # Remove HTML while preserving paragraph/list boundaries.
        text = BeautifulSoup(text, "html.parser").get_text("\n")

        # Remove URLs
        text = re.sub(r"https?://\S+", " ", text)

        # Remove Emails
        text = re.sub(r"\S+@\S+", " ", text)

        # Remove markdown code fences
        text = re.sub(r"```.*?```", " ", text, flags=re.S)

        # Collapse spaces inside lines
        text = re.sub(r"[ \t]+", " ", text)

        # Collapse newlines
        text = re.sub(r"\n\s*\n+", "\n", text)

        cleaned = []

        for line in text.splitlines():
            line = line.strip()

            if len(line) < cls.MIN_LINE_LENGTH:
                continue

            lower = line.lower()

            skip = False

            for pattern in cls.NOISE_PATTERNS:
                if re.match(pattern, lower):
                    skip = True

                    break

            if not skip:
                cleaned.append(line)

        return "\n".join(cleaned)
