"""
llm.py — LLM call logic for the Lease Clause Simplifier.

Provides:
- simplify_clause(clause_text: str) -> dict
    Sends the clause to Claude with the system prompt + few-shot examples,
    parses the JSON response, and returns a dict with:
    {
        "simplified_text": str,
        "tenant_obligations": list[str],
        "landlord_obligations": list[str],
        "tenant_rights": list[str],
        "ambiguity_flag": bool,
        "ambiguity_note": str | None
    }

Configuration:
- Model: claude-sonnet-4-20250514
- Temperature: 0.2
- Max input: 500 words (raises ValueError if exceeded)
- Retry: exponential backoff, max 2 retries (SDK built-in, covers 429 + 5xx)

Dependencies:
- anthropic SDK
- python-dotenv for API key loading
- prompts.py for system prompt and message building
"""

import json
import os

import anthropic
from dotenv import load_dotenv

from prompts import SYSTEM_PROMPT, build_messages

load_dotenv()

_MODEL = "claude-sonnet-4-6"
_MAX_WORDS = 500
_TEMPERATURE = 0.2
_MAX_TOKENS = 1024

# The SDK retries 429 + 5xx with exponential backoff by default (max_retries=2).
_client = anthropic.Anthropic(
    api_key=os.environ.get("ANTHROPIC_API_KEY"),
    max_retries=2,
)


def simplify_clause(clause_text: str) -> dict:
    """
    Simplify a residential lease clause using Claude.

    Args:
        clause_text: The raw lease clause text to simplify.

    Returns:
        A dict with keys: simplified_text, tenant_obligations,
        landlord_obligations, tenant_rights, ambiguity_flag, ambiguity_note.

    Raises:
        ValueError: If the clause is empty or exceeds 500 words.
        anthropic.APIError: For unrecoverable API errors after retries.
    """
    _validate_input(clause_text)

    messages = build_messages(clause_text)

    response = _client.messages.create(
        model=_MODEL,
        max_tokens=_MAX_TOKENS,
        temperature=_TEMPERATURE,
        system=SYSTEM_PROMPT,
        messages=messages,
    )

    raw_text = next(
        (block.text for block in response.content if block.type == "text"), ""
    )

    return _parse_response(raw_text)


def _validate_input(clause_text: str) -> None:
    """Raise ValueError if the input is empty or too long."""
    stripped = clause_text.strip()
    if not stripped:
        raise ValueError(
            "Please paste a lease clause before clicking Simplify."
        )
    word_count = len(stripped.split())
    if word_count > _MAX_WORDS:
        raise ValueError(
            f"This clause is {word_count} words, which exceeds the 500-word limit. "
            "Please paste one clause at a time, or split a longer clause into smaller sections."
        )


def _parse_response(raw_text: str) -> dict:
    """Parse the model's JSON response into a Python dict."""
    try:
        # Strip markdown code fences if the model wraps the JSON
        text = raw_text.strip()
        if text.startswith("```"):
            lines = text.splitlines()
            text = "\n".join(
                line for line in lines if not line.startswith("```")
            ).strip()
        result = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"The model returned an unexpected response format. "
            f"Raw output: {raw_text[:200]}"
        ) from exc

    # Ensure all required keys are present with sane defaults
    result.setdefault("ambiguity_flag", False)
    result.setdefault("ambiguity_note", None)
    result.setdefault("tenant_obligations", [])
    result.setdefault("landlord_obligations", [])
    result.setdefault("tenant_rights", [])

    return result
