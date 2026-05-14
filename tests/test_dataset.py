"""
Tests for the test clause dataset — validate structure and coverage.

Run with: pytest tests/test_dataset.py -v
"""

import json
import os
import pytest


@pytest.fixture
def test_clauses():
    path = os.path.join(os.path.dirname(__file__), "..", "evaluation", "test_clauses.json")
    with open(path, "r") as f:
        return json.load(f)


class TestDatasetStructure:
    def test_is_list(self, test_clauses):
        assert isinstance(test_clauses, list)

    def test_has_30_clauses(self, test_clauses):
        assert len(test_clauses) == 30

    def test_required_fields(self, test_clauses):
        required = ["id", "category", "clause_text", "key_obligations"]
        for clause in test_clauses:
            for field in required:
                assert field in clause, f"Clause {clause.get('id', '?')} missing '{field}'"

    def test_unique_ids(self, test_clauses):
        ids = [c["id"] for c in test_clauses]
        assert len(ids) == len(set(ids)), "Duplicate clause IDs found"

    def test_clause_text_length(self, test_clauses):
        for clause in test_clauses:
            word_count = len(clause["clause_text"].split())
            assert word_count >= 30, f"Clause {clause['id']} is too short ({word_count} words)"
            assert word_count <= 400, f"Clause {clause['id']} is too long ({word_count} words)"

    def test_key_obligations_not_empty(self, test_clauses):
        for clause in test_clauses:
            assert len(clause["key_obligations"]) >= 1, (
                f"Clause {clause['id']} has no key_obligations"
            )


class TestDatasetCoverage:
    EXPECTED_CATEGORIES = [
        "security_deposit", "maintenance", "termination", "liability",
        "pets", "late_fees", "noise_conduct", "subletting",
        "insurance", "utilities",
    ]

    def test_all_categories_present(self, test_clauses):
        categories = set(c["category"] for c in test_clauses)
        for cat in self.EXPECTED_CATEGORIES:
            assert cat in categories, f"Missing category: {cat}"

    def test_at_least_two_per_category(self, test_clauses):
        from collections import Counter
        counts = Counter(c["category"] for c in test_clauses)
        for cat in self.EXPECTED_CATEGORIES:
            assert counts.get(cat, 0) >= 2, (
                f"Category '{cat}' has only {counts.get(cat, 0)} clauses (need >= 2)"
            )

    def test_has_edge_cases(self, test_clauses):
        """Check that the dataset includes clauses with cross-references."""
        cross_ref_keywords = ["see section", "see exhibit", "as set forth in", "schedule a"]
        has_cross_ref = False
        for clause in test_clauses:
            lower = clause["clause_text"].lower()
            if any(kw in lower for kw in cross_ref_keywords):
                has_cross_ref = True
                break
        assert has_cross_ref, "Dataset should include at least one clause with cross-references"
