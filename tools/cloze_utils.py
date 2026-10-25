"""Token-safe spans shared by the content builder and its validator."""
import re


def cloze_span(text: str, target: str) -> tuple[int, int]:
    if not target:
        return -1, -1
    match = re.search(r"(?<!\w)" + re.escape(target) + r"(?!\w)", text, re.IGNORECASE)
    return match.span() if match else (-1, -1)


def valid_cloze_span(text: str, target: str, start: int, end: int) -> bool:
    return (
        0 <= start < end <= len(text)
        and text[start:end].casefold() == target.casefold()
        and (start == 0 or re.match(r"\w", text[start - 1]) is None)
        and (end == len(text) or re.match(r"\w", text[end]) is None)
    )
