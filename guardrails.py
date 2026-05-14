"""
guardrails.py — Input validation and output filtering for the Lease Clause Simplifier.

Input guardrails:
- check_too_short(): reject inputs under 10 words
- check_too_long(): warn on inputs over 350 words
- check_cross_references(): detect references to other sections

Output guardrails:
- check_advisory_language(): find and flag advisory sentences
- redact_advisory_sentences(): remove advisory sentences and add a note

Used by app.py before and after the LLM call.
"""

import re


# --- Input Guardrails ---

def count_words(text: str) -> int:
    """Count words in a string."""
    return len(text.split())


def check_too_short(text: str, min_words: int = 10) -> bool:
    """Return True if the input is too short to be a real clause."""
    return count_words(text) < min_words


def check_too_long(text: str, max_words: int = 350) -> bool:
    """Return True if the input exceeds the recommended length."""
    return count_words(text) > max_words


CROSS_REF_PATTERNS = [
    "see section", "see article", "see exhibit", "see schedule",
    "as defined in", "per section", "per article", "per exhibit",
    "pursuant to section", "pursuant to article",
    "in accordance with section", "in accordance with article",
    "subject to section", "subject to article",
    "as set forth in section", "as set forth in exhibit",
    "referred to in section", "referred to in article",
]


def check_cross_references(text: str) -> bool:
    """Return True if the clause contains references to other sections."""
    lower = text.lower()
    return any(p in lower for p in CROSS_REF_PATTERNS)


# --- Output Guardrails ---

ADVISORY_PHRASES = [
    "you should", "i recommend", "consider negotiating",
    "it is advisable", "we suggest", "you may want to",
    "you might want to", "it would be wise", "we advise",
    "you ought to", "i suggest", "you are advised to",
]


def check_advisory_language(text: str) -> list[str]:
    """
    Return a list of sentences containing advisory language.
    """
    sentences = text.replace("!", ".").replace("?", ".").split(".")
    flagged = []
    for sentence in sentences:
        lower = sentence.lower().strip()
        if any(phrase in lower for phrase in ADVISORY_PHRASES):
            flagged.append(sentence.strip())
    return flagged


def redact_advisory_sentences(text: str) -> tuple[str, list[str]]:
    """
    Remove advisory sentences from the text.
    
    Returns:
        (cleaned_text, list_of_redacted_sentences)
    """
    sentences = text.replace("!", ".").replace("?", ".").split(".")
    kept = []
    redacted = []
    for sentence in sentences:
        lower = sentence.lower().strip()
        if not lower:
            continue
        if any(phrase in lower for phrase in ADVISORY_PHRASES):
            redacted.append(sentence.strip())
        else:
            kept.append(sentence.strip())
    
    cleaned = ". ".join(kept)
    if cleaned and not cleaned.endswith("."):
        cleaned += "."
    
    return cleaned, redacted
