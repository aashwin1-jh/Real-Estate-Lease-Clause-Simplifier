"""
baseline.py — Baseline comparison for the Lease Clause Simplifier.

Compares the app's simplified output against the baseline of reading the raw
legal clause with no help.

Usage:
    python evaluation/baseline.py [--dry-run] [--skip-judge]

    --dry-run     Skip LLM simplification calls; use synthetic simplified text.
    --skip-judge  Skip the LLM-as-judge rubric scoring step.

Outputs:
    evaluation/baseline_report.md   Full markdown report
    evaluation/fk_comparison.png    Bar chart (original vs. simplified FK by category)
    evaluation/rubric_scores.csv    Per-clause rubric scores
"""

import argparse
import csv
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import matplotlib
matplotlib.use("Agg")  # headless — no display needed
import matplotlib.pyplot as plt
import textstat
from dotenv import load_dotenv

import anthropic
from judge_prompt import JUDGE_SYSTEM_PROMPT, JUDGE_USER_TEMPLATE
from llm import simplify_clause

load_dotenv()

# ── Paths ─────────────────────────────────────────────────────────────────────

DIR = os.path.dirname(os.path.abspath(__file__))
TEST_CLAUSES_PATH = os.path.join(DIR, "test_clauses.json")
REPORT_PATH       = os.path.join(DIR, "baseline_report.md")
CHART_PATH        = os.path.join(DIR, "fk_comparison.png")
RUBRIC_CSV_PATH   = os.path.join(DIR, "rubric_scores.csv")

RUBRIC_DIMS = ["simplicity", "completeness", "accuracy", "clarity"]
JUDGE_MODEL = "claude-sonnet-4-6"

# ── Helpers ───────────────────────────────────────────────────────────────────

def fk(text: str) -> float:
    return round(textstat.flesch_kincaid_grade(text), 1)


def _synthetic_simplify(clause_text: str) -> dict:
    """Deterministic stub for --dry-run mode."""
    return {
        "simplified_text": (
            "You and the landlord have agreed to these terms. "
            "Read each part carefully. "
            "The landlord will follow the rules. "
            "You must follow the rules too."
        ),
        "tenant_obligations": ["follow the rules in this clause"],
        "landlord_obligations": ["maintain the property"],
        "tenant_rights": ["ask questions if anything is unclear"],
        "ambiguity_flag": False,
        "ambiguity_note": None,
    }


def _synthetic_judge(_original: str, _simplified: str) -> dict:
    """Deterministic stub for --dry-run / --skip-judge mode."""
    return {
        "simplicity":    {"score": 4, "justification": "Dry-run stub."},
        "completeness":  {"score": 4, "justification": "Dry-run stub."},
        "accuracy":      {"score": 4, "justification": "Dry-run stub."},
        "clarity":       {"score": 4, "justification": "Dry-run stub."},
    }


def call_judge(client: anthropic.Anthropic, original: str, simplified_output: str) -> dict:
    """Call the LLM judge and return parsed rubric scores."""
    user_msg = JUDGE_USER_TEMPLATE.format(
        original_clause=original,
        simplified_output=simplified_output,
    )
    response = client.messages.create(
        model=JUDGE_MODEL,
        max_tokens=512,
        temperature=0,
        system=JUDGE_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_msg}],
    )
    raw = next((b.text for b in response.content if b.type == "text"), "{}")
    raw = raw.strip()
    if raw.startswith("```"):
        raw = "\n".join(l for l in raw.splitlines() if not l.startswith("```")).strip()
    return json.loads(raw)


# ── Bar chart ─────────────────────────────────────────────────────────────────

def make_bar_chart(category_stats: dict[str, dict]) -> None:
    """
    Save a grouped bar chart of avg original vs. simplified FK scores by category.
    category_stats: {category: {"orig": float, "simp": float}}
    """
    cats = sorted(category_stats)
    orig_vals = [category_stats[c]["orig"] for c in cats]
    simp_vals = [category_stats[c]["simp"] for c in cats]

    x = range(len(cats))
    width = 0.38

    fig, ax = plt.subplots(figsize=(11, 5))
    bars_orig = ax.bar([i - width / 2 for i in x], orig_vals, width,
                       label="Original (baseline)", color="#c0392b", alpha=0.85)
    bars_simp = ax.bar([i + width / 2 for i in x], simp_vals, width,
                       label="Simplified (app)", color="#27ae60", alpha=0.85)

    ax.set_xlabel("Category", fontsize=11)
    ax.set_ylabel("Avg Flesch-Kincaid Grade Level", fontsize=11)
    ax.set_title("Baseline vs. Simplified: Flesch-Kincaid Grade Level by Category", fontsize=12)
    ax.set_xticks(list(x))
    ax.set_xticklabels([c.replace("_", "\n") for c in cats], fontsize=8)
    ax.axhline(y=8, color="#2980b9", linestyle="--", linewidth=1.2, label="Target: Grade 8")
    ax.legend(fontsize=9)
    ax.set_ylim(0, max(orig_vals) * 1.2)

    for bar in bars_orig:
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.2,
                f"{bar.get_height():.1f}", ha="center", va="bottom", fontsize=7)
    for bar in bars_simp:
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.2,
                f"{bar.get_height():.1f}", ha="center", va="bottom", fontsize=7)

    plt.tight_layout()
    plt.savefig(CHART_PATH, dpi=150)
    plt.close()
    print(f"  Chart saved → {CHART_PATH}")


# ── Markdown report ───────────────────────────────────────────────────────────

def _avg(vals: list) -> float:
    return round(sum(vals) / len(vals), 2) if vals else 0.0


def write_report(
    records: list[dict],
    category_stats: dict,
    rubric_rows: list[dict],
    dim_avgs: dict[str, float],
    overall_rubric_avg: float,
    dry_run: bool,
    skip_judge: bool,
) -> None:
    overall_orig = _avg([r["orig_fk"] for r in records])
    overall_simp = _avg([r["simp_fk"] for r in records if r["simp_fk"] is not None])
    overall_delta = round(overall_orig - overall_simp, 2)
    below_8 = sum(1 for r in records if r["simp_fk"] is not None and r["simp_fk"] <= 8.0)
    n = len(records)

    lines = []
    lines.append("# Baseline Comparison Report — Lease Clause Simplifier\n")
    lines.append(
        f"*Generated in {'**DRY-RUN** ' if dry_run else ''}mode. "
        f"{n} clauses evaluated across 10 categories.*\n"
    )
    lines.append("> **Baseline definition:** The renter reads the original legal clause with no help.\n")

    # ── Overall FK table ──────────────────────────────────────────────────────
    lines.append("---\n")
    lines.append("## 1. Flesch-Kincaid Readability: Overall\n")
    lines.append("| Metric | Value |")
    lines.append("|---|---|")
    lines.append(f"| Clauses evaluated | {n} |")
    lines.append(f"| Avg original FK grade (baseline) | {overall_orig} |")
    lines.append(f"| Avg simplified FK grade (app) | {overall_simp} |")
    lines.append(f"| Avg FK reduction | **{overall_delta:+.2f} grade levels** |")
    lines.append(f"| Simplified outputs at/below grade 8 | {below_8} / {n} ({below_8/n*100:.0f}%) |\n")

    # ── Per-clause FK table ───────────────────────────────────────────────────
    lines.append("---\n")
    lines.append("## 2. Per-Clause FK Scores\n")
    lines.append("| ID | Category | Original FK | Simplified FK | Delta | Ambiguity Flagged |")
    lines.append("|---|---|---:|---:|---:|:---:|")
    for r in records:
        simp_str  = f"{r['simp_fk']:.1f}"  if r["simp_fk"]  is not None else "—"
        delta_str = f"{r['delta']:+.1f}"   if r["delta"]    is not None else "—"
        flag      = "✓" if r["ambiguity_flagged"] else ""
        lines.append(f"| {r['id']} | {r['category']} | {r['orig_fk']:.1f} | {simp_str} | {delta_str} | {flag} |")
    lines.append("")

    # ── Category breakdown ────────────────────────────────────────────────────
    lines.append("---\n")
    lines.append("## 3. Flesch-Kincaid by Category\n")
    lines.append("| Category | Clauses | Avg Original FK | Avg Simplified FK | Avg Delta |")
    lines.append("|---|---:|---:|---:|---:|")
    for cat in sorted(category_stats):
        s = category_stats[cat]
        lines.append(
            f"| {cat} | {s['count']} | {s['orig']:.1f} | {s['simp']:.1f} "
            f"| {s['orig'] - s['simp']:+.1f} |"
        )
    lines.append("")

    # ── Chart reference ───────────────────────────────────────────────────────
    lines.append("---\n")
    lines.append("## 4. Bar Chart — FK by Category\n")
    lines.append("![FK Comparison by Category](fk_comparison.png)\n")
    lines.append(
        "The dashed blue line marks the **Grade 8 target**. "
        "Green bars show the app's simplified output; red bars show the baseline "
        "(original legal text).\n"
    )

    # ── Rubric section ────────────────────────────────────────────────────────
    lines.append("---\n")
    lines.append("## 5. Rubric-Based Evaluation (LLM-as-Judge)\n")

    if skip_judge and not dry_run:
        lines.append("*Rubric scoring was skipped (`--skip-judge` flag).*\n")
    else:
        if dry_run:
            lines.append("*Rubric scores below are synthetic placeholders (dry-run mode).*\n")

        lines.append("Each simplified output is scored 1–5 on four dimensions by a separate")
        lines.append(f"LLM judge ({JUDGE_MODEL}). Scores are independent of the simplification call.\n")
        lines.append("### Rubric Dimensions\n")
        lines.append("| Dimension | Description |")
        lines.append("|---|---|")
        lines.append("| **Simplicity** | Is the output readable at an 8th-grade level? No jargon? |")
        lines.append("| **Completeness** | Are all obligations, rights, deadlines, and fees captured? |")
        lines.append("| **Accuracy** | Is the rewrite faithful to the original? No distortions? |")
        lines.append("| **Clarity** | Is ambiguity flagged? Is advice avoided? |\n")

        lines.append("### Average Rubric Scores\n")
        lines.append("| Dimension | Avg Score (out of 5) |")
        lines.append("|---|---:|")
        for dim in RUBRIC_DIMS:
            lines.append(f"| {dim.capitalize()} | {dim_avgs.get(dim, 0):.2f} |")
        lines.append(f"| **Overall average** | **{overall_rubric_avg:.2f}** |\n")

        lines.append("### Per-Clause Rubric Scores\n")
        lines.append(
            "| ID | Category | Simplicity | Completeness | Accuracy | Clarity | Avg |"
        )
        lines.append("|---|---|---:|---:|---:|---:|---:|")
        for row in rubric_rows:
            clause_avg = _avg([row[d] for d in RUBRIC_DIMS if row[d] is not None])
            lines.append(
                f"| {row['id']} | {row['category']} "
                f"| {row['simplicity'] or '—'} "
                f"| {row['completeness'] or '—'} "
                f"| {row['accuracy'] or '—'} "
                f"| {row['clarity'] or '—'} "
                f"| {clause_avg:.1f} |"
            )
        lines.append("")

    # ── Methodology ───────────────────────────────────────────────────────────
    lines.append("---\n")
    lines.append("## 6. Methodology\n")
    lines.append("- **Baseline:** The original lease clause text, unmodified.")
    lines.append("- **FK scoring:** `textstat.flesch_kincaid_grade()` applied to both original and simplified text.")
    lines.append("- **Completeness (eval.py):** Fuzzy string matching (`thefuzz.partial_ratio ≥ 65`) between")
    lines.append("  `key_obligations` and all LLM-extracted obligations + simplified text.")
    lines.append(f"- **Rubric judge:** `{JUDGE_MODEL}` at temperature 0, prompted with the four-dimension")
    lines.append("  rubric defined in `evaluation/rubric.md`. Each judge call is independent of the")
    lines.append("  simplification call.")
    lines.append("- **Dry-run mode:** Synthetic simplified text and rubric scores are used instead of")
    lines.append("  live API calls — useful for testing the pipeline without API costs.\n")

    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(f"  Report saved → {REPORT_PATH}")


# ── Main ──────────────────────────────────────────────────────────────────────

def main(dry_run: bool = False, skip_judge: bool = False) -> None:
    with open(TEST_CLAUSES_PATH, encoding="utf-8") as f:
        test_cases = json.load(f)

    client = anthropic.Anthropic(max_retries=2)

    records: list[dict]     = []
    rubric_rows: list[dict] = []
    category_data: dict     = {}  # {cat: {"orig": [], "simp": []}}

    print(f"\nRunning baseline comparison — {len(test_cases)} clauses "
          f"({'dry-run' if dry_run else 'live'}) …\n")

    for tc in test_cases:
        cid      = tc["id"]
        category = tc["category"]
        clause   = tc["clause_text"]

        orig_fk   = fk(clause)
        simp_fk   = None
        delta     = None
        ambig     = False
        simplified_text = ""
        error_msg = ""

        # ── Simplification ────────────────────────────────────────────────────
        try:
            if dry_run:
                result = _synthetic_simplify(clause)
            else:
                result = simplify_clause(clause)
                time.sleep(0.5)

            simplified_text = result.get("simplified_text", "")
            simp_fk         = fk(simplified_text)
            delta           = round(orig_fk - simp_fk, 1)
            ambig           = bool(result.get("ambiguity_flag", False))

        except Exception as exc:
            error_msg = str(exc)
            print(f"  [SIMPLIFY ERROR] {cid}: {exc}")

        records.append({
            "id": cid, "category": category,
            "orig_fk": orig_fk, "simp_fk": simp_fk,
            "delta": delta, "ambiguity_flagged": ambig, "error": error_msg,
        })

        if category not in category_data:
            category_data[category] = {"orig": [], "simp": []}
        category_data[category]["orig"].append(orig_fk)
        if simp_fk is not None:
            category_data[category]["simp"].append(simp_fk)

        # ── LLM-as-judge ──────────────────────────────────────────────────────
        rubric_row = {
            "id": cid, "category": category,
            **{d: None for d in RUBRIC_DIMS},
            "clause_avg": None, "error": "",
        }

        if not skip_judge and simplified_text:
            try:
                if dry_run:
                    scores = _synthetic_judge(clause, simplified_text)
                else:
                    scores = call_judge(client, clause, simplified_text)
                    time.sleep(0.5)

                for dim in RUBRIC_DIMS:
                    rubric_row[dim] = scores.get(dim, {}).get("score")
                valid = [rubric_row[d] for d in RUBRIC_DIMS if rubric_row[d] is not None]
                rubric_row["clause_avg"] = _avg(valid) if valid else None

            except Exception as exc:
                rubric_row["error"] = str(exc)
                print(f"  [JUDGE ERROR] {cid}: {exc}")

        rubric_rows.append(rubric_row)

        simp_str = f"{simp_fk:.1f}" if simp_fk else "—"
        delta_str = f"{delta:+.1f}" if delta else "—"
        rubric_str = f"{rubric_row['clause_avg']:.1f}" if rubric_row['clause_avg'] else "—"
        status = (
            f"orig={orig_fk:.1f}  simp={simp_str:>4}  "
            f"delta={delta_str:>5}  rubric={rubric_str}"
        )
        print(f"  {cid:<28} {status}")

    # ── Category stats ────────────────────────────────────────────────────────
    category_stats = {}
    for cat, vals in category_data.items():
        o = _avg(vals["orig"])
        s = _avg(vals["simp"]) if vals["simp"] else 0.0
        category_stats[cat] = {"orig": o, "simp": s, "count": len(vals["orig"])}

    # ── Rubric aggregates ─────────────────────────────────────────────────────
    dim_avgs: dict[str, float] = {}
    for dim in RUBRIC_DIMS:
        vals = [r[dim] for r in rubric_rows if r[dim] is not None]
        dim_avgs[dim] = _avg(vals) if vals else 0.0

    all_dim_vals = [
        r[d] for r in rubric_rows for d in RUBRIC_DIMS if r[d] is not None
    ]
    overall_rubric_avg = _avg(all_dim_vals) if all_dim_vals else 0.0

    # ── Write rubric CSV ──────────────────────────────────────────────────────
    with open(RUBRIC_CSV_PATH, "w", newline="", encoding="utf-8") as f:
        fieldnames = ["id", "category"] + RUBRIC_DIMS + ["clause_avg", "error"]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rubric_rows)
    print(f"\n  Rubric CSV saved → {RUBRIC_CSV_PATH}")

    # ── Chart ─────────────────────────────────────────────────────────────────
    make_bar_chart(category_stats)

    # ── Markdown report ───────────────────────────────────────────────────────
    write_report(
        records, category_stats, rubric_rows,
        dim_avgs, overall_rubric_avg,
        dry_run=dry_run, skip_judge=skip_judge,
    )

    # ── Console summary ───────────────────────────────────────────────────────
    good = [r for r in records if r["simp_fk"] is not None]
    print("\n" + "=" * 54)
    print("SUMMARY")
    print("=" * 54)
    print(f"  Clauses evaluated : {len(good)} / {len(records)}")
    if good:
        print(f"  Avg original FK   : {_avg([r['orig_fk'] for r in good]):.1f}")
        print(f"  Avg simplified FK : {_avg([r['simp_fk'] for r in good]):.1f}")
        print(f"  Avg FK reduction  : {_avg([r['delta'] for r in good if r['delta']]):+.1f} grade levels")
        below = sum(1 for r in good if r["simp_fk"] <= 8)
        print(f"  At/below grade 8  : {below}/{len(good)} ({below/len(good)*100:.0f}%)")
    if not (skip_judge and not dry_run):
        print(f"  Avg rubric score  : {overall_rubric_avg:.2f} / 5.00")
        for dim in RUBRIC_DIMS:
            print(f"    {dim.capitalize():<14}: {dim_avgs[dim]:.2f}")
    print("=" * 54)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run",    action="store_true",
                        help="Use synthetic LLM output — no API calls.")
    parser.add_argument("--skip-judge", action="store_true",
                        help="Skip the LLM-as-judge rubric scoring step.")
    args = parser.parse_args()
    main(dry_run=args.dry_run, skip_judge=args.skip_judge)
