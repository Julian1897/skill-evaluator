# Skill Evaluator

> A deterministic evaluation framework for AI agent skills — it treats a skill as **production agent behavior**, not just a Markdown file.

[English](./README.md) · [简体中文](./README.zh-CN.md)

---

## Overview

**Skill Evaluator** is a reproducible evaluation framework for Codex- and Claude Code-style agent skills — folders containing a `SKILL.md`, optional scripts, references, assets, test prompts, and generated reports.

Most "skill reviews" only judge the prose. Skill Evaluator goes further: it captures how a skill actually *behaves* when an agent runs it, then scores that behavior with checks that are reproducible and explainable.

The core evaluation model is:

```
prompt  →  captured run (trace + artifacts)  →  deterministic checks
                                                  + rubric checks
                                                  + optional human calibration
                                                  →  a comparable score
```

A useful evaluation is one you can **compare**: before vs. after a change, skill vs. skill, or this week vs. last week.

---

## Why Skill Evaluator

| Problem | What Skill Evaluator does |
|---|---|
| Reviews only check the writing | Scores structure **and** behavior, with optional agent-run traces |
| Scores are subjective and drift | Deterministic checks always return the same result for the same input |
| "It worked once" passes review | Prompts cover triggers, core logic, edge cases, and negative controls |
| Regressions slip in unnoticed | Before/after report comparison flags score drops and lost checks |
| A directory of skills is a black box | Batch evaluation ranks every skill and prioritizes fixes |

---

## How It Works

### Three Judges

| Judge | Best For | Gate Role |
|---|---|---|
| **Deterministic grader** | Structure, files, scripts, tool calls, JSON schema, artifacts, cost counters | Hard gate |
| **Rubric grader** | Reasoning quality, instruction fit, clarity, style, subjective output | Soft / graded gate |
| **Human expert** | Calibrating LLM judges, diagnosing 0% / 100% anomalies, high-risk review | Sampling & escalation |

Use **deterministic** checks for anything code can judge. Use **rubric** checks where the behavior is genuinely subjective. Use **humans** to calibrate and investigate — not as the default regression engine.

### Five Dimensions

| Dimension | Question | Typical Signals |
|---|---|---|
| Functional correctness | Did it do the right task? | trigger accuracy, required files, command success, schema validity |
| Process quality | Did it follow the intended path? | required steps, tool order, context use, self-correction |
| Efficiency & cost | Was the path economical? | token / call counts, latency, retries, unnecessary commands |
| Robustness & safety | Does it survive pressure? | negative controls, missing inputs, prompt injection, no hallucinated artifacts |
| Experience & alignment | Is the output useful and aligned? | clear report, correct tone, asks for missing info, explains choices |

Prioritize **functional correctness** and **robustness/safety** first. Add **process** and **efficiency** next. Add **experience/alignment** when the skill is user-facing or subjective.

---

## What It Evaluates

| Layer | What it checks |
|---|---|
| **Static readiness** | `SKILL.md` front matter, trigger clarity, sections, examples, troubleshooting, scripts, references |
| **Prompt coverage** | explicit, implicit, contextual, negative, edge-case, and bilingual (EN / CN) prompt rows |
| **Deterministic quality** | hard checks that are reproducible and explainable |
| **Rubric quality** | heuristic scoring across trigger, process, examples, error handling, style, domain fit, parameters, redundancy |
| **Regression risk** | before/after report comparison and batch priority ranking |

When the environment provides an agent CLI, Skill Evaluator can also guide agent-run evaluations using captured traces from `codex exec --json` or another runner.

---

## Quick Start

```python
# Load the evaluation engine
exec(open("scripts/eval_tool.py", encoding="utf-8").read())

# Point at the skills directory you want to evaluate
set_skills_base_dir(r"C:\Users\ZJ\.codex\skills")

# Evaluate one skill
result = evaluate_skill_v2("my-skill")
print(result["score"])
print(result["report_path"])
```

Artifacts are written under `evals/artifacts/` by default:

- `<skill>-eval-report.md` — full per-skill evaluation report
- `<skill>-bilingual.prompts.csv` — generated prompt set (EN/CN)
- `batch-eval-summary-v2.md` — directory-wide batch summary
- `<skill>-comparison-report.md` — before/after regression comparison

---

## Core API

| Function | Description |
|---|---|
| `set_skills_base_dir(path)` | Configure the skills root (e.g. `.codex/skills`, `.claude/skills`, or a custom path). |
| `evaluate_skill_v2(name, output_dir="evals/artifacts")` | Full static evaluation: deterministic checks + rubric scoring + prompt CSV + report. |
| `evaluate_all_skills_v2(output_dir="evals/artifacts")` | Batch evaluation with summary statistics and prioritized fixes. |
| `auto_score_rubric(name)` | Rubric-only heuristic score. |
| `generate_bilingual_prompts(name)` | Generate prompt rows; emits CN rows when the skill contains CJK text, otherwise EN. |
| `compare_evaluations(before, after)` | Compare two reports and flag regressions. |
| `quick_stats_v2(results)` | Print a compact batch summary. |

---

## Deterministic Checks

| Check | Purpose |
|---|---|
| `frontmatter-name` | Skill has a non-empty name. |
| `frontmatter-desc` | Description is present and substantial. |
| `desc-keywords` | Description uses `Use when` and concrete trigger vocabulary. |
| `has-when-to-use` | Body explains trigger cases. |
| `has-instructions` | Body includes ordered instructions. |
| `has-examples` | At least one example exists. |
| `has-troubleshooting` | Failure handling is documented. |
| `step-numbering` | Step headings are sequential when present. |
| `parameter-table` | Parameters / options are documented. |
| `script-exists` | Referenced helper script exists when required. |
| `script-valid-python` | Helper Python script parses. |
| `script-has-invoke` | Legacy tool wrapper check, when relevant. |
| `reference-exists` | Referenced reference file exists. |
| `reference-nonempty` | Reference file is not empty. |
| `tool-names-valid` | Tool names found in docs are syntactically valid. |

---

## Scoring & Grading

```
Total score = Deterministic score (50%) + Rubric score (50%)
```

| Score | Grade | Meaning |
|---|---|---|
| 90–100 | **A** | Production-ready if agent-run evidence exists |
| 80–89 | **B** | Strong — fix warnings before broad sharing |
| 70–79 | **C** | Conditional — use only with known limits |
| 60–69 | **D** | Weak — improve before deployment |
| < 60 | **F** | Do not deploy |

> A high static score proves **eval readiness**, not production reliability. True confidence requires agent-run traces and real bad-case prompts.

---

## Examples

### Single skill

```python
exec(open("scripts/eval_tool.py", encoding="utf-8").read())
set_skills_base_dir(r"C:\Users\ZJ\.codex\skills")

result = evaluate_skill_v2("tim-space-planning")
print(result["score"]["total_score"], result["score"]["verdict"])
print(result["report_path"])
```

### Batch a whole directory

```python
exec(open("scripts/eval_tool.py", encoding="utf-8").read())
set_skills_base_dir(r"C:\Users\ZJ\.codex\skills")

results = evaluate_all_skills_v2()
quick_stats_v2(results)
```

### Before / after regression check

```python
exec(open("scripts/eval_tool.py", encoding="utf-8").read())

before = evaluate_skill_v2("my-skill", output_dir="evals/before")
# ... edit the skill ...
after  = evaluate_skill_v2("my-skill", output_dir="evals/after")

comparison = compare_evaluations(before["report_path"], after["report_path"])
print(f"Score delta: {comparison['score_delta']:+.1f}")
print(f"Regression:  {comparison['has_regression']}")
```

### Suggested agent-run loop

Static evaluation is necessary but not sufficient — production confidence needs real traces:

```bash
codex exec --json --full-auto "Use the my-skill skill to complete the task" \
  > evals/artifacts/run.jsonl
```

Then score the captured run for: skill invocation (expected vs. actual), required commands/tools and order, required artifacts and file contents, cost/latency/retry thresholds, and forbidden actions or secret leakage.

---

## Project Structure

```text
skill-evaluator/
├── SKILL.md              # The skill definition (the skill itself)
├── README.md             # This file — quick start & API reference (English)
├── README.zh-CN.md       # Quick start & API reference (简体中文)
└── scripts/
    └── eval_tool.py      # Deterministic check engine, prompt generation,
                          # scoring, comparison, and batch summaries
```

---

## Evaluation Principles

- Use **deterministic graders** for anything code can judge.
- Use **rubric graders** for natural-language quality and process judgment.
- Use **human experts** to calibrate model judges, diagnose anomalies, and review high-risk cases.
- Cover the **five dimensions**: functional correctness, process quality, efficiency/cost, robustness/safety, experience/alignment.
- Keep **regression suites stable** — graduate passing cases in, and never remove them unless the use case is obsolete.

---

## License

MIT
