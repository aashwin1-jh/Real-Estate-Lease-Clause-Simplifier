# Plain-English Rewriter for Residential Lease Clauses

A Streamlit app that takes dense legal language from U.S. residential lease agreements and rewrites it in plain English at an 8th-grade or below reading level, along with a structured breakdown of tenant obligations, landlord obligations, and tenant rights.

> **Disclaimer:** This tool simplifies lease language for understanding only. It is not legal advice. Consult a licensed attorney for legal decisions.

---

## Project Write-up

### 1. Target User, Workflow, and Business Value

**Target user:** U.S. residential renters, particularly first-time renters, non-native English speakers, and anyone who lacks access to a lawyer — who need to understand what they are agreeing to before signing a lease.

**Workflow:** A renter receives a lease agreement. Instead of reading every clause as-is (most are written at a college reading level or higher), they paste individual clauses into this tool and get a plain-English breakdown in seconds. The breakdown tells them exactly what they must do, what the landlord must do, and what rights they have, without the renters needing legal training.

**Business value:** Reduces information asymmetry between tenants and landlords. A renter who understands what they're signing is less likely to be surprised by penalties, or violate their lease unknowingly, and they will be better positioned to negotiate lease terms. The tool replaces a task that would otherwise require either a lawyer consultation (~$200–$500/hour) or time-consuming self-research with uncertain quality.

---

### 2. Problem Statement and GenAI Fit

**Problem:** Residential lease clauses are written in dense legal language that most tenants cannot easily understand. The average U.S. lease is written at a college-grade reading level. Tenants routinely sign agreements they don't fully understand, leading to disputes, unexpected fees, and forfeited rights.

**Why GenAI fits:** This is a document-understanding and language-transformation task.  Large language models do these tasks well. The transformation is deterministic in structure where it produces the same output schema every time but requires language understanding to paraphrase accurately without changing the legal meaning. Rule-based approaches like find-and-replace, or readability filters cannot do this as well as a trained LLM can. The task is also well-scoped in a way that it can process one clause at a time with no external tool calls required, to give an output in structured JSON.

**Why not a simpler approach:** A Flesch-Kincaid optimizer or word-synonym-swapper would reduce reading level mechanically but would not identify *which party* bears each obligation, would not flag ambiguity, and would not preserve legal accuracy. a Gen AI model can do all three simultaneously.

---

### 3. System Design and Baseline

**Architecture:**

```
User (Streamlit UI)
  → input guardrails (word count, cross-reference detection)
  → LLM call (Claude, structured JSON output)
  → output guardrails (advisory language redaction)
  → structured display (simplified text + obligation lists + ambiguity flag)
```

**Model:** `claude-sonnet-4-20250514` at temperature 0.2. Sonnet was chosen over Haiku for accuracy on nuanced legal language, and over Opus for cost-efficiency given that this is a single-call, single-clause workflow with no tool use or multi-step reasoning required.

**Prompt design:**
- The prompts instruct the model to rewrite at 8th-grade level, return strict JSON, never give legal advice, and flag ambiguity
- 5 few-shot examples (security deposit, maintenance, pets, subletting, cross-reference) were given to demonstrate the expected transformation and JSON schema which is needed to produce structured outputs. 
- Temperature was set to low as it is adequate for consistent structured output, non-zero to allow natural paraphrase variation

**Baseline:** "Original clause as-is" — the renter reads the raw legal text with no assistance. The baseline Flesch-Kincaid grade for the 30-clause test set averages ~13.4 (roughly 1st-year college level). The app targets grade ≤ 8.

---

### 4. Evaluation Plan

**Test set:** 30 clauses across 10 categories (security deposit, maintenance, termination, liability, pets, late fees, noise/conduct, subletting, insurance, utilities), each 50–300 words. 
Includes edge cases: cross-reference clauses, an ambiguous clause, a contradictory clause, and a dual-fee clause.

**Automated metrics:**
- **Flesch-Kincaid grade level** on simplified output (target ≤ 8)
- **Completeness** — fuzzy string match (partial ratio ≥ 65) of extracted obligations against ground-truth `key_obligations` per clause
- **Ambiguity flagging rate** — whether the model correctly raises the flag on tricky clauses

**Rubric (1–5 scale, scored by LLM-as-judge):**
| Dimension | Description |
|-----------|-------------|
| Simplicity | Is the output comprehensible to an 8th grader? |
| Completeness | Are all key obligations and rights captured? |
| Accuracy | Is the rewrite faithful — no distortions or omissions of legal meaning? |
| Clarity | Are ambiguities or contradictions flagged rather than silently resolved? |

**Judge model:** `claude-sonnet-4-6` at temperature 0, called separately from the simplification model to avoid self-evaluation bias. The judge is used only in the evaluation scripts (`baseline.py`) since the app itself makes a single model call per clause.

**Baseline comparison:** `evaluation/baseline.py` computes original Flesch-Kincaid vs. simplified Flesch-Kincaid per clause and per category, generates a grouped bar chart, and writes a full markdown report.

---

### 5. Example Inputs and Failure Cases

**Example input (security deposit clause):**
> "Upon execution of this Lease, Tenant shall deposit with Landlord the sum of two thousand dollars ($2,000) as a security deposit, to be held as security for the faithful performance of all terms, covenants, and conditions of this Lease. Said deposit shall not be applied to the last month's rent..."

**Expected output:** Simplified text at grade ≤ 8, tenant obligation ("pay $2,000 security deposit at signing"), landlord obligation ("hold deposit in trust"), tenant right ("receive deposit back within 21 days of move-out, minus lawful deductions"), no ambiguity flag.

**Known failure modes:**

| Failure mode | Example | Current behavior |
|---|---|---|
| Cross-reference clauses | "Damages as defined in Article 7..." | Warns user; simplifies text as-is, may miss referenced terms |
| Ambiguous clauses | "Landlord may enter at reasonable times" — no notice period specified | Ambiguity flag raised and model notes the gap |
| Very short input | Single phrase, no full clause | Rejected by input guardrail |
| Advisory language in output | Model occasionally adds "you should consult a lawyer" | Redacted by output guardrail |
| State-specific law | Clause about security deposit return timing | Model does not know the state; cannot flag deviations from local law |
| Contradictory terms | "No pets allowed" + "Pet deposit: $500" | Model identifies the contradiction and flags ambiguity |

---

### 6. Risks and Governance

**Trust and accuracy risk:** The model may paraphrase a clause in a way that subtly misrepresents the legal meaning. Mitigations: (1) temperature set to 0.2 to reduce hallucination; (2) few-shot examples anchor the expected style; (3) persistent disclaimer on every session; (4) rubric Accuracy dimension scored in evaluation.

**Advisory language risk:** The model may generate sentences that sound like legal advice ("you should negotiate this clause"). Mitigation: output guardrail scans for advisory phrases and redacts them before display, with a visible notice to the user.

**Scope creep risk:** Users may try to paste entire leases or ask for legal strategy. Mitigations: (1) 350-word input cap; (2) system prompt explicitly prohibits legal advice; (3) cross-reference warning discourages pasting incomplete fragments.

**Deployment boundary:** This tool is designed as a comprehension aid, not a legal instrument. It should not be used to make binding decisions, assert tenant rights in a dispute, or replace attorney review. These boundaries are stated prominently in the UI and in every response.

**No data retention:** Clause text is not logged or stored. The tool makes one stateless API call per clause and discards the text when the session ends.

---

### 7. Course Concepts Integrated

**1. Anatomy of an LLM call (Week 2–3)**
- System prompt specifies role, output format (JSON schema), reading level target, tone constraints, and refusal rules
- Temperature 0.2 balances consistency with natural paraphrase variation
- `max_tokens=1024` caps output to prevent runaway generation
- SDK-native retry (`max_retries=2`) handles transient 429/5xx errors with exponential backoff

**2. Context engineering — few-shot examples (Week 3)**
- 5 examples in `few_shot_examples.json` demonstrate the transformation pattern
- Examples cover: straightforward clause, maintenance, pet restriction, subletting, and a cross-reference ambiguity case (the only one with `ambiguity_flag: true`)
- Examples are injected as alternating user/assistant turns to match the model's expected conversation format

**3. Evaluation design (Week 6)**
- 31-clause test set with ground-truth `key_obligations` per clause
- Automated FK scoring via `textstat`
- Completeness scoring via fuzzy string matching (`thefuzz`, threshold 65)
- LLM-as-judge with 4-dimension rubric (`judge_prompt.py`), separate model call
- Baseline comparison with grouped bar chart (`baseline.py`)
- Results exported to CSV; full markdown report auto-generated

**4. Red-teaming and refusal design (Week 6)**
- Input guardrails: too-short rejection, too-long warning, cross-reference detection
- Output guardrail: advisory language detection and redaction (regex + sentence-level scan)
- Unit tests for all guardrails (`tests/test_guardrails.py`, 38 tests)
- Ambiguity flag in structured output surfaces model uncertainty to the user

**5. Governance and deployment controls (Week 6)**
- Persistent disclaimer on every page load
- System prompt instructs model to never give legal advice
- Advisory redaction removes model-generated advice even when it slips through the prompt
- No data logging; stateless API calls

---

## Quick Start

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Set your API key

```bash
cp .env.example .env
# Edit .env and add your Anthropic API key
```

Get a key at [console.anthropic.com](https://console.anthropic.com) → API Keys. New accounts receive free credits.

### 3. Run the app

```bash
streamlit run app.py
```

The app will open at `http://localhost:8501`.

---

## How It Works

1. Paste a lease clause (50–350 words) into the text box
2. Click **Simplify**
3. See a side-by-side comparison of the original and simplified version
4. Review the structured list of your obligations, landlord obligations, and your rights
5. If the clause is ambiguous or references other sections, a warning is displayed

---

## Project Structure

```
lease-clause-simplifier/
├── app.py                    # Streamlit UI
├── llm.py                    # LLM call logic (API interaction)
├── prompts.py                # System prompt + message builder
├── few_shot_examples.json    # 5 few-shot input/output pairs
├── guardrails.py             # Input/output guardrail functions
├── requirements.txt          # Python dependencies
├── .env.example              # API key template
├── .streamlit/
│   └── config.toml           # Streamlit theme config
├── evaluation/
│   ├── test_clauses.json     # 31-clause test set (10 categories)
│   ├── judge_prompt.py       # LLM-as-judge prompt template
│   ├── eval.py               # Evaluation harness (FK + completeness)
│   └── baseline.py           # Baseline comparison + rubric scoring
├── tests/
│   └── test_guardrails.py    # Unit tests for guardrails (38 tests)
└── README.md
```

---

## Running the Evaluation

```bash
# Dry run (no API calls, tests the scoring pipeline)
python evaluation/eval.py --dry-run
python evaluation/baseline.py --dry-run

# Live run (calls the API for all 31 clauses)
python evaluation/eval.py
python evaluation/baseline.py
```

Outputs:
- `evaluation/results.csv` — per-clause FK and completeness scores
- `evaluation/baseline_report.md` — full markdown report
- `evaluation/fk_comparison.png` — bar chart (original vs. simplified FK by category)
- `evaluation/rubric_scores.csv` — per-clause LLM-as-judge scores

---

## Guardrails

| Guardrail | Behavior |
|-----------|----------|
| Input too short (<10 words) | Error: "Please paste at least one complete sentence." |
| Input too long (>350 words) | Warning: asks user to split the clause |
| Cross-references detected | Info banner: "This clause references other sections..." |
| Advisory language in output | Flagged sentences are redacted with a visible notice |
| Persistent disclaimer | Footer on every page: "This is not legal advice." |

---

## Known Limitations

- **Cross-references:** The app simplifies only the pasted text. If a clause says "See Section 4.2," the app cannot look up that section.
- **State-specific law:** The app does not know which state the lease is from and cannot flag state-specific legal issues (e.g., California's 21-day deposit return rule).
- **Not legal advice:** The app may miss nuances. It is a comprehension aid, not a substitute for an attorney.
- **Clause length:** Very long clauses (>350 words) should be split for best results.
- **Implicit terms:** Obligations implied by local law or context (rather than stated in the clause) may not be captured.

---

## Privacy

- No clause text is stored after the session ends
- No data is logged or sent anywhere beyond the single API call to Anthropic
- Use synthetic or public data for testing; do not commit real lease data containing PII
