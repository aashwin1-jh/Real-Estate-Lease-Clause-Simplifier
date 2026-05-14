"""
Tests for prompts.py — verify system prompt structure and few-shot examples.

Run with: pytest tests/test_prompts.py -v
"""

import json
import pytest
from prompts import SYSTEM_PROMPT, load_few_shot_examples, build_messages


class TestSystemPrompt:
    def test_prompt_is_not_empty(self):
        assert len(SYSTEM_PROMPT) > 100

    def test_prompt_mentions_8th_grade(self):
        assert "8th-grade" in SYSTEM_PROMPT or "8th grade" in SYSTEM_PROMPT

    def test_prompt_prohibits_advice(self):
        lower = SYSTEM_PROMPT.lower()
        assert "not provide legal advice" in lower or "never" in lower

    def test_prompt_specifies_json_output(self):
        assert "simplified_text" in SYSTEM_PROMPT
        assert "tenant_obligations" in SYSTEM_PROMPT
        assert "landlord_obligations" in SYSTEM_PROMPT
        assert "tenant_rights" in SYSTEM_PROMPT
        assert "ambiguity_flag" in SYSTEM_PROMPT

    def test_prompt_mentions_ambiguity(self):
        assert "ambiguity" in SYSTEM_PROMPT.lower()


class TestFewShotExamples:
    @pytest.fixture
    def examples(self):
        return load_few_shot_examples()

    def test_loads_examples(self, examples):
        assert isinstance(examples, list)
        assert len(examples) >= 3  # at least 3 few-shot examples

    def test_example_structure(self, examples):
        for ex in examples:
            assert "input_clause" in ex
            assert "expected_output" in ex
            assert isinstance(ex["input_clause"], str)
            assert len(ex["input_clause"]) > 20

    def test_expected_output_structure(self, examples):
        required_keys = [
            "simplified_text",
            "tenant_obligations",
            "landlord_obligations",
            "tenant_rights",
            "ambiguity_flag",
            "ambiguity_note",
        ]
        for ex in examples:
            output = ex["expected_output"]
            for key in required_keys:
                assert key in output, f"Missing key '{key}' in example output"

    def test_obligations_are_lists(self, examples):
        for ex in examples:
            output = ex["expected_output"]
            assert isinstance(output["tenant_obligations"], list)
            assert isinstance(output["landlord_obligations"], list)
            assert isinstance(output["tenant_rights"], list)

    def test_ambiguity_flag_is_bool(self, examples):
        for ex in examples:
            assert isinstance(ex["expected_output"]["ambiguity_flag"], bool)

    def test_at_least_one_ambiguous_example(self, examples):
        """Ensure at least one example demonstrates ambiguity flagging."""
        has_ambiguous = any(ex["expected_output"]["ambiguity_flag"] for ex in examples)
        assert has_ambiguous, "Need at least one few-shot example with ambiguity_flag=True"


class TestBuildMessages:
    def test_returns_list(self):
        messages = build_messages("Tenant shall pay rent.")
        assert isinstance(messages, list)

    def test_ends_with_user_message(self):
        clause = "Tenant shall pay rent on the first of each month."
        messages = build_messages(clause)
        assert messages[-1]["role"] == "user"
        assert messages[-1]["content"] == clause

    def test_alternating_roles(self):
        messages = build_messages("Test clause.")
        for i in range(0, len(messages) - 1, 2):
            assert messages[i]["role"] == "user"
            assert messages[i + 1]["role"] == "assistant"

    def test_assistant_messages_are_valid_json(self):
        messages = build_messages("Test clause.")
        for msg in messages:
            if msg["role"] == "assistant":
                parsed = json.loads(msg["content"])
                assert "simplified_text" in parsed
