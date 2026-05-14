"""
evaluation/eval.py — Automated evaluation harness for the Lease Clause Simplifier.

Usage:
    python evaluation/eval.py [--dry-run]

    --dry-run   Skip LLM calls; generate synthetic simplified text for testing
                the scoring pipeline without spending API tokens.

Outputs:
    evaluation/results.csv   Per-clause metrics
    Summary table to stdout
"""

import argparse
import csv
import json
import os
import sys
import time

# Allow running from the project root or from evaluation/
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import textstat
from thefuzz import fuzz

from llm import simplify_clause

# ── Constants ─────────────────────────────────────────────────────────────────

TEST_CLAUSES_PATH = os.path.join(os.path.dirname(__file__), "test_clauses.json")
RESULTS_PATH = os.path.join(os.path.dirname(__file__), "results.csv")

# Fuzzy-match threshold: an extracted obligation is considered a hit if its
# best partial-ratio match against any key obligation reaches this score.
FUZZY_THRESHOLD = 65

CSV_FIELDS = [
    "id",
    "category",
    "original_fk_score",
    "simplified_fk_score",
    "fk_delta",
    "completeness_pct",
    "ambiguity_flagged",
    "obligations_found",
    "obligations_total",
    "error",
]


# ── Scoring helpers ───────────────────────────────────────────────────────────

def flesch_kincaid_grade(text: str) -> float:
    """Return the Flesch-Kincaid grade level for *text*, rounded to 1 decimal."""
    score = textstat.flesch_kincaid_grade(text)
    return round(score, 1)


def _obligation_matched(obligation: str, candidates: list[str]) -> bool:
    """
    Return True if *obligation* fuzzy-matches any string in *candidates*
    above FUZZY_THRESHOLD using partial_ratio (substring-aware).
    """
    ob_lower = obligation.lower()
    for candidate in candidates:
        if fuzz.partial_ratio(ob_lower, candidate.lower()) >= FUZZY_THRESHOLD:
            return True
    return False


def completeness_score(key_obligations: list[str], extracted: list[str]) -> tuple[float, int, int]:
    """
    Compute what fraction of key_obligations appear in extracted.

    Returns:
        (pct_float_0_to_100, matched_count, total_count)
    """
    if not key_obligations:
        return 100.0, 0, 0
    matched = sum(1 for ob in key_obligations if _obligation_matched(ob, extracted))
    pct = round(matched / len(key_obligations) * 100, 1)
    return pct, matched, len(key_obligations)


def _all_extracted_obligations(result: dict) -> list[str]:
    """Flatten all obligation/rights lists from the LLM result into one list."""
    out = []
    for key in ("tenant_obligations", "landlord_obligations", "tenant_rights"):
        out.extend(result.get(key, []))
    # Also include the simplified_text itself as a candidate (catches paraphrases)
    simplified = result.get("simplified_text", "")
    if simplified:
        out.append(simplified)
    return out


# ── Dry-run stub ──────────────────────────────────────────────────────────────

def _synthetic_simplify(clause_text: str) -> dict:
    """
    Return a plausible but deterministic fake result for --dry-run mode.
    Produces readable text so FK scoring is meaningful.
    """
    words = clause_text.split()[:30]
    simplified = (
        "You and the landlord have agreed to these terms. "
        "Read each part carefully. "
        "The landlord will follow the rules. "
        "You must follow the rules too. "
        "Ask questions if anything is unclear."
    )
    return {
        "simplified_text": simplified,
        "tenant_obligations": ["follow the rules in this clause"],
        "landlord_obligations": ["follow the rules in this clause"],
        "tenant_rights": ["ask questions if unclear"],
        "ambiguity_flag": False,
        "ambiguity_note": None,
    }


# ── Main evaluation loop ──────────────────────────────────────────────────────

def run_evaluation(dry_run: bool = False) -> list[dict]:
    with open(TEST_CLAUSES_PATH, encoding="utf-8") as f:
        test_cases = json.load(f)

    rows = []
    col_widths = {"id": 20, "category": 16, "orig_fk": 7, "simp_fk": 7,
                  "delta": 7, "complete": 10, "flagged": 8}

    header = (
        f"{'ID':<{col_widths['id']}} {'CATEGORY':<{col_widths['category']}} "
        f"{'ORIG_FK':>{col_widths['orig_fk']}} {'SIMP_FK':>{col_widths['simp_fk']}} "
        f"{'DELTA':>{col_widths['delta']}} {'COMPLETE%':>{col_widths['complete']}} "
        f"{'AMBIG?':>{col_widths['flagged']}}"
    )
    separator = "-" * len(header)

    print(f"\n{'LEASE CLAUSE SIMPLIFIER — EVALUATION RUN':^{len(header)}}")
    print(f"{'Mode: DRY-RUN (no API calls)' if dry_run else 'Mode: LIVE (calling API)':^{len(header)}}")
    print(separator)
    print(header)
    print(separator)

    for tc in test_cases:
        clause_id = tc["id"]
        category = tc["category"]
        clause_text = tc["clause_text"]
        key_obligations = tc.get("key_obligations", [])

        original_fk = flesch_kincaid_grade(clause_text)
        error_msg = ""
        simplified_fk = None
        completeness_pct = None
        ambiguity_flagged = False
        obligations_found = 0
        obligations_total = len(key_obligations)

        try:
            if dry_run:
                result = _synthetic_simplify(clause_text)
            else:
                result = simplify_clause(clause_text)
                time.sleep(0.5)  # gentle rate-limit buffer between calls

            simplified_text = result.get("simplified_text", "")
            simplified_fk = flesch_kincaid_grade(simplified_text)
            ambiguity_flagged = bool(result.get("ambiguity_flag", False))

            extracted = _all_extracted_obligations(result)
            completeness_pct, obligations_found, obligations_total = completeness_score(
                key_obligations, extracted
            )

        except ValueError as exc:
            error_msg = f"ValueError: {exc}"
        except Exception as exc:
            error_msg = f"Error: {exc}"

        fk_delta = (
            round(original_fk - simplified_fk, 1)
            if simplified_fk is not None
            else None
        )

        row = {
            "id": clause_id,
            "category": category,
            "original_fk_score": original_fk,
            "simplified_fk_score": simplified_fk if simplified_fk is not None else "",
            "fk_delta": fk_delta if fk_delta is not None else "",
            "completeness_pct": completeness_pct if completeness_pct is not None else "",
            "ambiguity_flagged": ambiguity_flagged,
            "obligations_found": obligations_found,
            "obligations_total": obligations_total,
            "error": error_msg,
        }
        rows.append(row)

        # Print progress row
        simp_fk_str = f"{simplified_fk:.1f}" if simplified_fk is not None else "ERR"
        delta_str = f"{fk_delta:+.1f}" if fk_delta is not None else "ERR"
        complete_str = f"{completeness_pct:.1f}%" if completeness_pct is not None else "ERR"
        flagged_str = "YES" if ambiguity_flagged else "no"

        print(
            f"{clause_id:<{col_widths['id']}} {category:<{col_widths['category']}} "
            f"{original_fk:>{col_widths['orig_fk']}.1f} {simp_fk_str:>{col_widths['simp_fk']}} "
            f"{delta_str:>{col_widths['delta']}} {complete_str:>{col_widths['complete']}} "
            f"{flagged_str:>{col_widths['flagged']}}"
        )

    print(separator)

    # Write CSV
    with open(RESULTS_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(rows)

    return rows


# ── Summary table ─────────────────────────────────────────────────────────────

def print_summary(rows: list[dict]) -> None:
    successful = [r for r in rows if r["simplified_fk_score"] != ""]

    if not successful:
        print("\nNo successful evaluations to summarize.")
        return

    orig_fk_vals = [r["original_fk_score"] for r in successful]
    simp_fk_vals = [float(r["simplified_fk_score"]) for r in successful]
    delta_vals = [float(r["fk_delta"]) for r in successful]
    complete_vals = [float(r["completeness_pct"]) for r in successful if r["completeness_pct"] != ""]
    ambig_count = sum(1 for r in successful if r["ambiguity_flagged"])

    below_grade_8 = sum(1 for v in simp_fk_vals if v <= 8.0)

    categories = {}
    for r in successful:
        cat = r["category"]
        if cat not in categories:
            categories[cat] = {"orig": [], "simp": [], "complete": []}
        categories[cat]["orig"].append(r["original_fk_score"])
        categories[cat]["simp"].append(float(r["simplified_fk_score"]))
        if r["completeness_pct"] != "":
            categories[cat]["complete"].append(float(r["completeness_pct"]))

    print("\n" + "=" * 62)
    print("SUMMARY")
    print("=" * 62)
    print(f"  Clauses evaluated :  {len(successful)} / {len(rows)}")
    print(f"  Avg original FK   :  {sum(orig_fk_vals)/len(orig_fk_vals):.1f}")
    print(f"  Avg simplified FK :  {sum(simp_fk_vals)/len(simp_fk_vals):.1f}")
    print(f"  Avg FK reduction  :  {sum(delta_vals)/len(delta_vals):+.1f} grade levels")
    print(f"  At/below grade 8  :  {below_grade_8} / {len(successful)} "
          f"({below_grade_8/len(successful)*100:.0f}%)")
    print(f"  Avg completeness  :  {sum(complete_vals)/len(complete_vals):.1f}%" if complete_vals else "  Avg completeness  :  N/A")
    print(f"  Ambiguity flagged :  {ambig_count} clause(s)")
    print(f"  Results saved to  :  {RESULTS_PATH}")

    print("\n  Per-category averages:")
    print(f"  {'Category':<18} {'Orig FK':>7} {'Simp FK':>7} {'Complete%':>9}")
    print("  " + "-" * 44)
    for cat in sorted(categories):
        d = categories[cat]
        orig_avg = sum(d["orig"]) / len(d["orig"])
        simp_avg = sum(d["simp"]) / len(d["simp"])
        comp_avg = (sum(d["complete"]) / len(d["complete"])) if d["complete"] else 0
        print(f"  {cat:<18} {orig_avg:>7.1f} {simp_avg:>7.1f} {comp_avg:>8.1f}%")

    print("=" * 62)


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Evaluate the Lease Clause Simplifier.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Skip API calls and use synthetic output (tests the scoring pipeline).",
    )
    args = parser.parse_args()

    rows = run_evaluation(dry_run=args.dry_run)
    print_summary(rows)
