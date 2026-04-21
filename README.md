# Skill Evaluator

A systematic evaluation framework for Claude Code skills, featuring rubric auto-scoring, bilingual prompt generation, deterministic structural checks, and before/after comparison.

**Score: 92.5/100 (Grade A)** — self-evaluated with full transparency.

## Overview

Skill Evaluator adapts the eval methodology from [Testing Agent Skills Systematically with Evals](https://platform.openai.com/docs/guides/evaluation-best-practices) into a 5-step automated pipeline:

```
analyze → generate prompts → run deterministic checks → auto-score rubric → produce scored report
```

Every skill is evaluated across **four weighted dimensions**:

| Dimension | What it checks | Weight |
|-----------|---------------|--------|
| **Outcome** | Does the skill produce the intended result? | 30% |
| **Process** | Does it follow documented steps and tool-calling patterns? | 25% |
| **Style** | Does the output follow conventions (formatting, naming, structure)? | 20% |
| **Efficiency** | Is it well-structured without unnecessary complexity? | 25% |

## Features

- **Deterministic Checks** — 17 reproducible checks covering SKILL.md structure, script validity, API connectivity, and reference integrity
- **Rubric Auto-Scoring** — 8 heuristic-based rubric items scored 1-5, no human judgment needed for a baseline
- **Bilingual Prompt Generation** — Auto-detects Chinese/English content and generates 8-16 test prompts across 5 categories
- **Batch Evaluation** — Evaluate all skills in a directory with statistics (mean, median, histogram, grade distribution)
- **Before/After Comparison** — Compare two evaluation results to detect regressions and improvements
- **Graded Reports** — Scores mapped to A-F grades with PASS / CONDITIONAL PASS / FAIL verdicts

## Repository Structure

```
skill-evaluator/
├── SKILL.md                              # Skill definition (5-step eval pipeline)
├── scripts/
│   └── eval_tool.py                      # Core engine: checks, rubric, prompts, reports
└── evals/
    ├── rubric.schema.json                # JSON Schema for rubric output validation
    ├── template.prompts.csv              # Prompt category template (8 rows)
    └── artifacts/
        ├── skill-evaluator.prompts.csv   # Self-evaluation: English prompts
        ├── skill-evaluator-bilingual.prompts.csv  # Self-evaluation: bilingual prompts
        └── skill-evaluator-eval-report.md         # Self-evaluation: scored report
```

## Quick Start

### Prerequisites

- Claude Code CLI with skills support
- Python 3.8+ (for `eval_tool.py`)
- A skill to evaluate located under `.claude/skills/<skill-name>/`

### Single Skill Evaluation

```python
exec(open("scripts/eval_tool.py").read())

# Full V2 evaluation: deterministic + rubric + bilingual prompts
result = evaluate_skill_v2("kriging-interpolation")
print(f"Score: {result['score']['total_score']}/100")
print(f"Grade: {result['score']['grade']}")
print(f"Verdict: {result['score']['verdict']}")
```

### Batch Evaluation

```python
exec(open("scripts/eval_tool.py").read())

results = evaluate_all_skills_v2(output_dir="evals/artifacts")
quick_stats_v2(results)
```

### Bilingual Prompt Generation

```python
exec(open("scripts/eval_tool.py").read())

# Auto-detects language from SKILL.md content
prompts = generate_bilingual_prompts("seismic-interpretation")
save_bilingual_prompts_csv(prompts, "evals/artifacts/seismic-interpretation-bilingual.prompts.csv")
```

### Before/After Comparison

```python
exec(open("scripts/eval_tool.py").read())

comparison = compare_evaluations(
    "evals/artifacts/my-skill-eval-before.md",
    "evals/artifacts/my-skill-eval-after.md"
)
print(f"Score delta: {comparison['score_delta']:+.1f}")
print(f"Regressions: {comparison['deterministic']['new_failures']}")
```

## Evaluation Pipeline

### Step 1 — Deterministic Checks (50% of total score)

17 automated checks across 4 categories:

**SKILL.md Structure (9 checks):**
`frontmatter-name`, `frontmatter-desc`, `desc-keywords`, `has-when-to-use`, `has-instructions`, `has-examples`, `has-troubleshooting`, `step-numbering`, `parameter-table`

**Script Validation (4 checks):**
`script-exists`, `script-valid-python`, `script-has-invoke`, `script-api-url`

**Reference Checks (2 checks):**
`reference-exists`, `reference-nonempty`

**Connectivity (2 checks):**
`api-reachable`, `tool-names-valid`

### Step 2 — Rubric Auto-Scoring (50% of total score)

8 heuristic-scored items mapped to dimensions:

| Check | Dimension | Key Heuristic |
|-------|-----------|--------------|
| trigger-clarity | Outcome | Description length, "Use when" pattern, domain keywords |
| instruction-completeness | Process | Step count, code blocks, parameter table |
| example-quality | Process | Example sections, realistic file paths |
| error-handling | Process | Troubleshooting items, input validation |
| style-consistency | Style | Heading hierarchy, tables, YAML front matter |
| scientific-accuracy | Style | Domain terminology, caveats, method references |
| parameter-coverage | Efficiency | Documented params, type annotations |
| no-redundancy | Efficiency | Duplicate ratio, excessive length penalty |

### Grade Scale

| Score Range | Grade | Verdict |
|-------------|-------|---------|
| 90-100 | A | PASS |
| 80-89 | B | PASS |
| 70-79 | C | PASS |
| 60-69 | D | CONDITIONAL PASS |
| 0-59 | F | FAIL |

## Prompt Categories

Generated test prompts cover 5 categories per language:

| Category | Count | Purpose |
|----------|-------|---------|
| Explicit invocation | 2 | Prompts that name the skill directly |
| Implicit invocation | 2 | Prompts that describe the task without naming |
| Contextual invocation | 1 | Prompts with realistic project context |
| Negative control | 2 | Requests that should NOT trigger the skill |
| Edge cases | 1 | Missing parameters, invalid inputs |

**Bilingual behavior:** If SKILL.md contains CJK characters, generates 16 prompts (8 EN + 8 CN); otherwise 8 EN prompts.

## Self-Evaluation Results

This skill evaluated itself, scoring **92.5/100 (Grade A, PASS)**:

| Dimension | Result |
|-----------|--------|
| Deterministic Checks | 17/17 passed (100%) |
| Rubric Grading | 4.25/5 average |

See the full report at [`evals/artifacts/skill-evaluator-eval-report.md`](evals/artifacts/skill-evaluator-eval-report.md).

## API Reference

### Core Functions

| Function | Description |
|----------|-------------|
| `evaluate_skill_v2(name)` | Full V2 evaluation pipeline |
| `evaluate_all_skills_v2()` | Batch evaluate all skills |
| `run_all_deterministic_checks(name)` | Run 17 structural checks |
| `auto_score_rubric(name)` | Heuristic rubric scoring |
| `run_rubric_auto_grading(name)` | Combined deterministic + rubric |
| `generate_bilingual_prompts(name)` | Generate CN/EN test prompts |
| `compare_evaluations(before, after)` | Compare two evaluation reports |
| `quick_stats_v2(results)` | Print batch statistics summary |

### Output Functions

| Function | Description |
|----------|-------------|
| `save_prompts_csv(prompts, path)` | Save English prompts to CSV |
| `save_bilingual_prompts_csv(prompts, path)` | Save bilingual prompts to CSV |

## V1 Compatibility

| V1 Function | V2 Replacement |
|-------------|---------------|
| `evaluate_skill()` | `evaluate_skill_v2()` |
| `evaluate_all_skills()` | `evaluate_all_skills_v2()` |
| `quick_stats()` | `quick_stats_v2()` |
| `generate_eval_prompts()` | `generate_bilingual_prompts()` |

## Troubleshooting

| Problem | Solution |
|---------|----------|
| Target skill directory not found | Verify skill name matches a directory under `.claude/skills/` |
| API unreachable for connectivity check | Check is skipped and noted in the report |
| Script has syntax errors | Error details reported, `script-valid-python` marked FAIL |
| No YAML front matter | All frontmatter checks marked FAIL — critical issue |
| Bilingual prompts not generated | Check if SKILL.md has CJK characters; use `generate_eval_prompts()` for EN-only |

## License

MIT
