"""
Unit tests for input guardrails and output filtering.

Run with: pytest tests/test_guardrails.py -v
"""

import pytest

from guardrails import (
    check_advisory_language,
    check_cross_references,
    check_too_long,
    check_too_short,
    count_words,
    redact_advisory_sentences,
)


class TestWordCount:
    def test_empty(self):
        assert count_words("") == 0

    def test_normal_sentence(self):
        assert count_words("The quick brown fox jumps") == 5

    def test_multiline(self):
        assert count_words("Line one\nLine two\nLine three") == 6

    def test_extra_whitespace(self):
        assert count_words("  too   many   spaces  ") == 3


class TestTooShort:
    def test_empty_string(self):
        assert check_too_short("") is True

    def test_single_word(self):
        assert check_too_short("Deposit") is True

    def test_nine_words(self):
        assert check_too_short("The tenant shall pay rent on the first day") is True

    def test_ten_words_is_not_short(self):
        assert check_too_short("The tenant shall pay rent on the first day monthly") is False

    def test_real_clause(self):
        clause = (
            "Tenant shall deposit with Landlord the sum of two thousand dollars "
            "as a security deposit to be held as security for the faithful performance "
            "of all terms and conditions of this Lease."
        )
        assert check_too_short(clause) is False


class TestTooLong:
    def test_short_clause(self):
        assert check_too_long("Rent is due on the first of each month.") is False

    def test_exactly_350_words(self):
        assert check_too_long(" ".join(["word"] * 350)) is False

    def test_351_words(self):
        assert check_too_long(" ".join(["word"] * 351)) is True

    def test_500_words(self):
        assert check_too_long(" ".join(["word"] * 500)) is True


class TestCrossReferences:
    def test_no_references(self):
        assert check_cross_references("Tenant shall pay rent on the first of each month.") is False

    def test_see_section(self):
        assert check_cross_references("Late fees apply. See Section 4.2 for details.") is True

    def test_as_defined_in(self):
        assert check_cross_references("Damages as defined in Article 7 shall be deducted.") is True

    def test_per_exhibit(self):
        assert check_cross_references("Rent shall be paid per Exhibit B schedule.") is True

    def test_pursuant_to_section(self):
        assert check_cross_references(
            "Pursuant to Section 12.1, disputes shall be resolved by arbitration."
        ) is True

    def test_as_set_forth_in(self):
        assert check_cross_references("Late charges as set forth in Exhibit B shall apply.") is True

    def test_in_accordance_with(self):
        assert check_cross_references(
            "Repairs shall be made in accordance with Article 5."
        ) is True

    def test_subject_to_section(self):
        assert check_cross_references("This clause is subject to Section 9.") is True

    def test_case_insensitive(self):
        assert check_cross_references("SEE SECTION 3 FOR ADDITIONAL TERMS.") is True

    def test_section_as_general_word(self):
        # "section" used as a common noun, not a cross-reference
        assert check_cross_references(
            "The kitchen section of the unit must be kept clean."
        ) is False


class TestAdvisoryLanguage:
    def test_no_advisory(self):
        assert check_advisory_language("You must pay rent by the first of each month.") == []

    def test_you_should(self):
        result = check_advisory_language("You pay rent monthly. You should negotiate a lower rate.")
        assert len(result) == 1
        assert "negotiate" in result[0].lower()

    def test_i_recommend(self):
        result = check_advisory_language("The deposit is $2,000. I recommend reviewing this with a lawyer.")
        assert len(result) == 1

    def test_consider_negotiating(self):
        result = check_advisory_language("This is strict. Consider negotiating the terms before signing.")
        assert len(result) == 1

    def test_you_may_want_to(self):
        result = check_advisory_language("The fee is non-refundable. You may want to reconsider this clause.")
        assert len(result) == 1

    def test_multiple_advisory_sentences(self):
        text = (
            "Rent is $1,500 per month. You should ask for a discount. "
            "I recommend getting renter's insurance. The deposit is refundable."
        )
        assert len(check_advisory_language(text)) == 2

    def test_no_false_positive_landlord_should(self):
        # "should" not preceded by "you" — not advisory toward the reader
        assert check_advisory_language("The landlord should maintain the building.") == []

    def test_it_is_advisable(self):
        result = check_advisory_language("It is advisable to read all sections carefully.")
        assert len(result) == 1

    def test_we_suggest(self):
        result = check_advisory_language("We suggest consulting an attorney before signing.")
        assert len(result) == 1


class TestRedactAdvisorySentences:
    def test_no_advisory_unchanged(self):
        text = "You must pay rent monthly. The deposit is $2,000."
        cleaned, redacted = redact_advisory_sentences(text)
        assert redacted == []
        assert "rent monthly" in cleaned
        assert "deposit" in cleaned

    def test_single_advisory_redacted(self):
        text = "You pay rent monthly. You should negotiate a lower rate. The deposit is $500."
        cleaned, redacted = redact_advisory_sentences(text)
        assert len(redacted) == 1
        assert "negotiate" in redacted[0].lower()
        assert "you should" not in cleaned.lower()
        assert "rent monthly" in cleaned
        assert "deposit" in cleaned

    def test_multiple_advisory_redacted(self):
        text = (
            "Rent is $1,500 per month. "
            "You should ask for a discount. "
            "I recommend getting renter's insurance. "
            "The deposit is refundable."
        )
        cleaned, redacted = redact_advisory_sentences(text)
        assert len(redacted) == 2
        assert "you should" not in cleaned.lower()
        assert "i recommend" not in cleaned.lower()
        assert "refundable" in cleaned

    def test_all_advisory_returns_empty_cleaned(self):
        text = "You should negotiate. I recommend consulting a lawyer."
        cleaned, redacted = redact_advisory_sentences(text)
        assert len(redacted) == 2
        assert cleaned.strip() == ""

    def test_cleaned_text_ends_with_period(self):
        text = "Rent is due monthly. You should ask about discounts. The landlord maintains the roof."
        cleaned, _ = redact_advisory_sentences(text)
        assert cleaned.endswith(".")

    def test_preserves_non_advisory_content_exactly(self):
        text = "The deposit is two thousand dollars. Consider negotiating this amount. It is held for 30 days."
        cleaned, redacted = redact_advisory_sentences(text)
        assert "two thousand dollars" in cleaned
        assert "30 days" in cleaned
        assert "Consider negotiating" not in cleaned
