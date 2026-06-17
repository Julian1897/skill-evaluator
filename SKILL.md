---
name: skill-evaluator
description: Use when evaluating, auditing, benchmarking, regression-testing, comparing, or improving AI agent skills, including Codex or Claude Code skills
---

# Skill Evaluator

## Overview

Evaluate skills as production agent behavior, not just Markdown quality. A useful eval is:

`prompt -> captured run (trace + artifacts) -> deterministic checks + rubric checks + optional human calibration -> comparable score`

This skill is optimized for Codex and Claude Code style skills: folders containing `SKILL.md`, optional scripts, references, assets, test prompts, and generated reports.

## When to Use

Use this skill when the user wants to:

- Evaluate or audit one skill before installing or sharing it.
- Compare a skill before and after a prompt, script, model, or dependency change.
- Batch-score a skills directory and rank improvement priorities.
- Generate a small prompt set for trigger, core workflow, output quality, and failure-mode coverage.
- Turn a bad case into a regression test.
- Decide whether a skill is ready for CI, marketplace distribution, or wider team use.

Do not treat a high static score as proof that the skill works in production. Static checks prove eval readiness; true reliability requires agent-run traces and artifacts.

## Evaluation Model

### Three Judges

| Judge | Best For | Gate Role |
|-------|----------|-----------|
| Deterministic grader | Structure, files, scripts, tool calls, JSON schema, artifacts, cost counters | Hard gate |
| Rubric grader | Reasoning quality, instruction fit, clarity, style, subjective output quality | Soft or graded gate |
| Human expert | Calibrating LLM judges, diagnosing 0%/100% anomalies, high-risk review, ground truth | Sampling and escalation |

Use deterministic checks first. Use rubric checks where code cannot judge the behavior. Use humans to calibrate and investigate, not as the default regression engine.

### Five Dimensions

| Dimension | Question | Typical Signals |
|-----------|----------|-----------------|
| Functional correctness | Did it do the right task? | trigger accuracy, required files, command success, schema validity |
| Process quality | Did it follow the intended path? | required steps, tool order, context use, self-correction |
| Efficiency and cost | Was the path economical? | token/call counts, latency, retries, unnecessary commands |
| Robustness and safety | Does it survive pressure? | negative controls, missing inputs, prompt injection, no hallucinated artifacts |
| Experience and alignment | Is the output useful and aligned? | clear report, correct tone, asks for missing information, explains choices |

Prioritize functional correctness and robustness/safety first. Add process and efficiency next. Add experience/alignment when the skill is user-facing or subjective.

## Instructions

All generated artifacts should go to `evals/artifacts/` in the consumer workspace unless the user specifies another location.

Load the helper once:

```python
exec(open("scripts/eval_tool.py", encoding="utf-8").read())
```

### Step 1: Inspect the Target Skill

Read the full skill folder, not only `SKILL.md`.

Check:

- Front matter has only `name` and `description`.
- `description` starts with `Use when...` and describes trigger conditions, not the workflow.
- Instructions include prerequisites, ordered steps, definition of done, examples, troubleshooting, and gotchas.
- Supporting references/scripts/assets are used for heavy material through progressive disclosure.
- Helper scripts parse and are referenced consistently.

### Step 2: Classify the Skill Type

Classify the skill before scoring. Good skills usually fit one dominant type:

| Type | Main Eval Focus |
|------|-----------------|
| Library/API reference | correct API usage, gotchas, examples |
| Product verification | deterministic checks, traces, screenshots, pass/fail gates |
| Data fetching and analysis | source selection, query correctness, artifact integrity |
| Business process automation | required handoffs, approvals, idempotence |
| Code scaffolding/templates | file tree, build success, convention adherence |
| Code quality/review | finding quality, false positives, severity calibration |
| CI/CD and deployment | environment isolation, rollback, no unsafe commands |
| Runbook | symptom routing, diagnostic order, escalation |
| Infrastructure operations | permissions, safety boundaries, dry-run behavior |

If a skill straddles several categories, flag it. Splitting overloaded skills often improves invocation accuracy.

### Step 3: Build a Small Prompt Set

Start with 10-20 prompts. Include both positive and negative cases:

| Category | Purpose |
|----------|---------|
| Explicit invocation | User names the skill directly. |
| Implicit invocation | User describes the exact task without naming the skill. |
| Contextual invocation | Realistic, slightly noisy project context. |
| Negative control | Adjacent requests that should not trigger. |
| Core logic | Each major branch path has at least one case. |
| Output quality | Expected files, schemas, report sections, or response constraints. |
| Error tolerance | Missing input, invalid input, empty data, tool failure, large input. |
| Adversarial/safety | Prompt injection, secret leakage, permission boundary attempts. |

Add every confirmed bad case to the suite. Once a capability case passes consistently, graduate it into the regression suite and do not remove it unless the use case is obsolete.

### Step 4: Run Static Evaluation

Use the built-in evaluator for repeatable local checks:

```python
result = evaluate_skill_v2("target-skill")
print(result["score"])
```

For a custom skills root:

```python
set_skills_base_dir(r"C:\Users\ZJ\.codex\skills")
result = evaluate_skill_v2("target-skill")
```

The static report is an eval-readiness report: it scores discoverability, instruction quality, folder structure, examples, script validity, prompt generation, and professional rubric coverage.

### Step 5: Add Agent-Run Evidence When Available

When the environment supports an agent CLI, capture a real trace:

```bash
codex exec --json --full-auto "Use the $target-skill skill to complete the task"
```

Score the captured run for:

- Skill invocation expected vs actual.
- Required commands/tools and order.
- Required artifacts and file contents.
- Final response constraints.
- Token/call/latency/retry thresholds.
- Forbidden actions, secret leakage, and false positives.

No trace means process quality is only inferred. Say that clearly in the report.

### Step 6: Calibrate and Gate

Use this default gate:

| Score | Meaning | Action |
|-------|---------|--------|
| 90-100 | Production-ready | Ship if no critical issues and agent-run evidence exists |
| 80-89 | Strong | Fix listed warnings before broad sharing |
| 70-79 | Conditional | Use only with known limits |
| 60-69 | Weak | Improve before deployment |
| <60 | Fail | Do not deploy |

Escalate to human review when the score is 0%/100% unexpectedly, the skill affects high-risk domains, a rubric judge is being introduced, or the expected behavior is subjective.

## API Reference

| Function | Purpose |
|----------|---------|
| `set_skills_base_dir(path)` | Point evaluator at a `.codex/skills`, `.claude/skills`, or custom skills directory. |
| `evaluate_skill_v2(name, output_dir="evals/artifacts")` | Full static eval: deterministic checks, rubric scoring, prompt CSV, report. |
| `evaluate_all_skills_v2(output_dir="evals/artifacts")` | Batch evaluation with summary statistics and priorities. |
| `generate_bilingual_prompts(name)` | Create EN/CN prompt rows when the skill contains Chinese; otherwise EN prompts. |
| `auto_score_rubric(name)` | Rubric-only heuristic scoring. |
| `compare_evaluations(before, after)` | Compare two generated reports and flag regressions. |
| `quick_stats_v2(results)` | Print a compact batch summary. |

## Parameters

| Parameter | Type | Required | Used By | Notes |
|-----------|------|----------|---------|-------|
| `skill_name` | string | yes | `evaluate_skill_v2`, `auto_score_rubric`, prompt generation | Directory name under the configured skills root. |
| `path` | string/path | yes | `set_skills_base_dir` | Skills root such as `.codex/skills` or `.claude/skills`. |
| `output_dir` | string/path | no | evaluation and comparison functions | Defaults to `evals/artifacts`. |
| `enable_rubric` | boolean | no | `evaluate_skill_v2`, `evaluate_all_skills_v2` | Defaults to `True`. |
| `bilingual` | boolean | no | `evaluate_skill_v2`, `evaluate_all_skills_v2` | Defaults to `True`; CN prompts are emitted when CJK text is detected. |
| `before` / `after` | string/path | yes | `compare_evaluations` | Paths to generated Markdown reports. |

## Examples

### Single Skill

```python
exec(open("scripts/eval_tool.py", encoding="utf-8").read())
set_skills_base_dir(r"C:\Users\ZJ\.codex\skills")
result = evaluate_skill_v2("tim-space-planning")
print(result["score"]["total_score"], result["score"]["verdict"])
print(result["report_path"])
```

### Batch Directory

```python
exec(open("scripts/eval_tool.py", encoding="utf-8").read())
set_skills_base_dir(r"C:\Users\ZJ\.codex\skills")
results = evaluate_all_skills_v2()
quick_stats_v2(results)
```

### Before/After Regression

```python
before = evaluate_skill_v2("my-skill", output_dir="evals/before")
# edit the skill
after = evaluate_skill_v2("my-skill", output_dir="evals/after")
comparison = compare_evaluations(before["report_path"], after["report_path"])
print(comparison["score_delta"], comparison["has_regression"])
```

## Common Mistakes

| Mistake | Fix |
|---------|-----|
| Scoring only the final answer | Capture trace and artifacts so process regressions are visible. |
| Only positive prompts | Add negative controls and adjacent non-trigger cases. |
| Vague description | Rewrite as `Use when...` with concrete triggers and symptoms. |
| Workflow summary in description | Move workflow details into the body; keep description for discovery. |
| Treating model grading as objective | Calibrate rubric judges with human-labeled samples. |
| Letting regression suites shrink | Keep regression cases stable; add bad cases as they appear. |
| Overloaded skill scope | Split into one dominant category and cross-reference other skills. |

## Troubleshooting

| Problem | Likely Cause | Action |
|---------|--------------|--------|
| Skill directory not found | Wrong skills root | Call `set_skills_base_dir(path)` or pass the correct folder name. |
| Description check fails | Missing `Use when` or too process-heavy | Rewrite front matter trigger text. |
| Prompt CSV is generic | Skill has weak domain terms | Add concrete task nouns, artifacts, tools, and negative controls. |
| Score is high but skill failed manually | Static eval only checks readiness | Add agent-run trace checks and bad-case prompts. |
| Rubric score seems unfair | Heuristics are conservative | Inspect rubric notes, then add missing sections or adjust manual judgment. |
| Batch summary hides risk | Averages mask P0 failures | Review critical issues and low dimension scores first. |

## Resource Index

| File | Purpose |
|------|---------|
| `scripts/eval_tool.py` | Static evaluation engine, prompt generation, scoring, comparison, batch summaries. |
| `README.md` | Install and quick-start reference for humans. |
