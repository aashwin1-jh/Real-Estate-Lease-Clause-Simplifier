# Evaluation Rubric — Lease Clause Simplifier

This rubric is used to score each simplified output on four dimensions.
Scores range from 1 (lowest) to 5 (highest).

---

## Dimension 1: Simplicity

Can a person with an 8th-grade reading level understand the output?

| Score | Criteria |
|-------|----------|
| 5 | Simple, everyday language throughout. No legal jargon. Short sentences. A middle-schooler could read and understand it. |
| 4 | Mostly plain language with one or two slightly advanced words that don't block understanding. |
| 3 | Some legal or formal terms remain unexplained. A college student would understand but not everyone. |
| 2 | Multiple legal terms, long sentences, or complex phrasing that requires re-reading. |
| 1 | Barely simpler than the original. Still reads like a legal document. |

**Flesch-Kincaid target:** Simplified output should score at grade level 8 or below.

---

## Dimension 2: Completeness

Did the system capture all key rights, obligations, and conditions?

| Score | Criteria |
|-------|----------|
| 5 | All obligations, rights, deadlines, fees, and conditions from the original are represented. Nothing important is missing. |
| 4 | One minor detail is omitted (e.g., a specific timeframe) but all major obligations are present. |
| 3 | One significant obligation or right is missing. |
| 2 | Multiple obligations or rights are missing. The reader would have an incomplete picture. |
| 1 | Most of the clause's content is missing or the output is too vague to be useful. |

---

## Dimension 3: Accuracy

Is the simplified version faithful to the original clause? Does it avoid misrepresenting anything?

| Score | Criteria |
|-------|----------|
| 5 | Completely faithful. No distortions, no added meaning, no softened or exaggerated terms. |
| 4 | Accurate overall with one minor imprecision that does not change the practical meaning. |
| 3 | One meaningful inaccuracy — e.g., a deadline is wrong, a fee amount is changed, or an obligation is attributed to the wrong party. |
| 2 | Multiple inaccuracies or a single serious misrepresentation that could mislead the reader. |
| 1 | The simplified version contradicts the original or invents obligations/rights not in the clause. |

---

## Dimension 4: Clarity / Ambiguity Handling

Does the output flag ambiguity or contradiction? Does it avoid giving advice?

| Score | Criteria |
|-------|----------|
| 5 | If the clause is clear, the output is clear. If the clause is ambiguous or references other sections, the output explicitly flags it. No advice is given. |
| 4 | Ambiguity handling is mostly correct, with one minor miss. No advice. |
| 3 | Ambiguity in the original is not flagged, or the output includes one mildly advisory statement. |
| 2 | Ambiguity is ignored and the output presents uncertain content as definitive, or includes advice. |
| 1 | The output confidently misinterprets an ambiguous clause or gives direct legal advice. |

---

## How to Use This Rubric

### Manual scoring
For each test clause, read the original and the simplified output side by side.
Score each of the four dimensions independently (1-5).
Record scores in a spreadsheet alongside the clause ID.

### LLM-as-judge scoring
Pass the original clause, the simplified output, and this rubric to a separate LLM call.
Ask it to return a JSON object with scores and brief justifications:

```json
{
  "simplicity": { "score": 4, "justification": "..." },
  "completeness": { "score": 5, "justification": "..." },
  "accuracy": { "score": 5, "justification": "..." },
  "clarity": { "score": 4, "justification": "..." }
}
```

### Aggregation
- Per-clause average across 4 dimensions
- Per-dimension average across all 30 test clauses
- Overall average across all clauses and dimensions
- Breakdown by clause category (security_deposit, maintenance, etc.)
