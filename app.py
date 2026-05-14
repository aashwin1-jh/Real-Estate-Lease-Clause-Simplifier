"""
app.py — Streamlit UI for the Lease Clause Simplifier.

Run with: streamlit run app.py
"""

import streamlit as st

from guardrails import (
    check_cross_references,
    check_too_long,
    check_too_short,
    count_words,
    redact_advisory_sentences,
)
from llm import simplify_clause

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Plain-English Real Estate Lease Clause Simplifier",
    page_icon="🏠",
    layout="centered",
)

# ── Header ────────────────────────────────────────────────────────────────────
st.title("Plain-English Real Estate Lease Clause Simplifier")
st.markdown(
    "Paste a single clause from your residential lease and get a plain-English "
    "breakdown of what it means — including your obligations, the landlord's "
    "obligations, and your rights. **This is an educational tool, not legal advice.**"
)

st.divider()

# ── Input ─────────────────────────────────────────────────────────────────────
clause_input = st.text_area(
    label="Paste your lease clause here (50–350 words)",
    placeholder=(
        "Example: Upon execution of this Lease, Tenant shall deposit with Landlord "
        "the sum of two thousand dollars ($2,000) as a security deposit..."
    ),
    height=200,
)

simplify_clicked = st.button("Simplify", type="primary", use_container_width=True)

# ── Guardrails + Results ──────────────────────────────────────────────────────
if simplify_clicked:
    text = clause_input.strip()

    # --- Input guardrail 1: too short ---
    if not text or check_too_short(text):
        st.error(
            "This doesn't look like a full clause — please paste at least one complete sentence."
        )

    # --- Input guardrail 2: too long ---
    elif check_too_long(text):
        word_count = count_words(text)
        st.warning(
            f"Your clause is {word_count} words, which is over the 350-word limit. "
            "Long clauses are best split into smaller sections for accurate results. "
            "Please paste one clause (or one sub-section) at a time."
        )

    else:
        # --- Input guardrail 3: cross-references ---
        if check_cross_references(text):
            st.info(
                "ℹ️ **This clause references other sections.** The simplification is based "
                "only on the text you pasted and may be incomplete. For a full picture, "
                "review the referenced sections alongside this summary."
            )

        try:
            with st.spinner("Simplifying your clause…"):
                result = simplify_clause(text)

            # --- Output guardrail: advisory language ---
            simplified = result.get("simplified_text", "")
            simplified, redacted = redact_advisory_sentences(simplified)
            result["simplified_text"] = simplified

            if redacted:
                st.warning(
                    "⚠️ **Note:** One or more sentences in the simplification contained "
                    "advisory language (e.g. recommendations or suggestions) and were "
                    "removed. This tool provides plain-English explanations only — "
                    "not legal advice."
                )

            # Side-by-side: original | simplified
            col_left, col_right = st.columns(2)
            with col_left:
                st.subheader("Original Clause")
                st.markdown(
                    f'<div style="background:#f8f8f8;padding:1rem;border-radius:6px;'
                    f'font-size:0.9rem;line-height:1.5;">{text}</div>',
                    unsafe_allow_html=True,
                )
            with col_right:
                st.subheader("Simplified Version")
                st.markdown(
                    f'<div style="background:#eef6ee;padding:1rem;border-radius:6px;'
                    f'font-size:0.9rem;line-height:1.5;">{result["simplified_text"]}</div>',
                    unsafe_allow_html=True,
                )

            st.divider()

            # Ambiguity warning from LLM
            if result.get("ambiguity_flag"):
                st.warning(
                    f"⚠️ **This clause may be ambiguous or incomplete.** "
                    f"{result.get('ambiguity_note', '')}"
                )

            # Expandable obligation / rights sections
            def bullet_list(items: list[str]) -> str:
                if not items:
                    return "_None identified in this clause._"
                return "\n".join(f"- {item}" for item in items)

            with st.expander("📋 Your Obligations as Tenant", expanded=True):
                st.markdown(bullet_list(result.get("tenant_obligations", [])))

            with st.expander("🔧 Landlord's Obligations", expanded=True):
                st.markdown(bullet_list(result.get("landlord_obligations", [])))

            with st.expander("✅ Your Rights", expanded=True):
                st.markdown(bullet_list(result.get("tenant_rights", [])))

        except ValueError as exc:
            st.error(str(exc))
        except Exception as exc:
            st.error(
                f"Something went wrong while contacting the AI service. "
                f"Please try again in a moment. ({exc})"
            )

# ── Persistent disclaimer ─────────────────────────────────────────────────────
st.divider()
st.caption(
    "⚖️ **Disclaimer:** This tool simplifies lease language for understanding only. "
    "It is not legal advice. Consult a licensed attorney for legal decisions."
)
