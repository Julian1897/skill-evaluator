---
name: skill-evaluator
description: Systematically evaluate skills with rubric auto-scoring, bilingual prompts, and batch statistics; when users need to evaluate, benchmark, audit, compare, or regression-test skills
---

# Skill Evaluator v2

Systematically evaluate any GeoSkill (or general Claude Code skill) using a structured eval methodology adapted from ["Testing Agent Skills Systematically with Evals"](https://platform.openai.com/docs/guides/evaluation-best-practices).

The eval loop is: **analyze → generate prompts → run deterministic checks → auto-score rubric → produce scored report**.

## When to Use

- Evaluating a single skill's quality and correctness
- Comparing two versions of a skill (before/after a change)
- Batch-evaluating all skills in a directory with detailed statistics
- Auditing skill completeness before deployment
- Running regression checks after modifying a skill
- Generating bilingual (CN/EN) test prompt sets
- User says "evaluate skill X", "test skill X", "audit skill X", "benchmark skill X", "compare skill X before/after"

## Evaluation Framework

Every eval operates across four dimensions:

| Dimension       | What it checks                                              | Weight |
|-----------------|-------------------------------------------------------------|--------|
| **Outcome**     | Does the skill produce the intended result?                  | 30%    |
| **Process**     | Does it follow the documented steps and tool-calling pattern? | 25%    |
| **Style**       | Does the output follow conventions (formatting, naming, structure)? | 20%    |
| **Efficiency**  | Is it well-structured with no unnecessary complexity or missing coverage? | 25%    |

## Instructions

> **Output directory**: All generated artifacts (reports, prompt CSVs, batch summaries) are written to `evals/artifacts/` in the **consumer's workspace** (the working directory where the evaluation is invoked), not inside the skill-evaluator's own directory.

> **Tool calling**: The evaluation helper is in `scripts/eval_tool.py`. Before running checks, execute `exec(open("scripts/eval_tool.py").read())` to make all functions available.

### Step 1: Analyze the Target Skill

Read the target skill's `SKILL.md` and extract key information. If evaluating multiple skills, repeat for each.

```python
skill_path = ".claude/skills/<target-skill-name>/SKILL.md"
```

Parse and record:
- YAML front matter: `name` and `description` fields
- Markdown body: section headings, instruction steps, examples, troubleshooting
- Declared tools: function names from `_invoke_tool_http` calls
- Documented parameters, outputs, error cases

### Step 2: Generate Eval Prompt Set

**V2 supports bilingual (EN/CN) prompt generation.** Prompts are auto-generated based on the skill's domain, detected language, and content analysis.

```python
# Generate bilingual prompts (auto-detects CN/EN)
prompts = generate_bilingual_prompts("<skill-name>")
save_bilingual_prompts_csv(prompts, "evals/artifacts/<skill-name>-bilingual.prompts.csv")

# Or generate English-only prompts (legacy)
prompts = generate_eval_prompts("<skill-name>")
save_prompts_csv(prompts, "evals/artifacts/<skill-name>.prompts.csv")
```

**Prompt categories (per language):**

| Category | Count | Purpose |
|----------|-------|---------|
| **Explicit invocation** | 2 | Prompts that name the skill directly |
| **Implicit invocation** | 2 | Prompts that describe the task without naming the skill |
| **Contextual invocation** | 1 | Prompts with realistic project context |
| **Negative control** | 2 | Requests that should NOT trigger the skill |
| **Edge cases** | 1 | Missing parameters, invalid inputs, ambiguous requests |

**Bilingual behavior:**
- If the skill's SKILL.md contains Chinese characters → generates prompts in both English and Chinese (16 total)
- If English-only → generates 8 English prompts
- Domain vocabulary is auto-detected (terrain, remote sensing, geophysics, etc.)
- Action words are extracted from the skill description and adapted to both languages

### Step 3: Run Deterministic Checks

Run automated checks against the skill's files and structure. These checks are **deterministic, reproducible, and debuggable**.

```python
results = run_all_deterministic_checks("<skill-name>")
```

**3.1 SKILL.md Structure Checks:**

| Check ID | What it verifies |
|----------|-----------------|
| `frontmatter-name` | YAML front matter has a non-empty `name` field |
| `frontmatter-desc` | YAML front matter has a non-empty `description` field (min 20 chars) |
| `desc-keywords` | Description includes trigger keywords for the skill's domain |
| `has-when-to-use` | Body contains a "When to Use" section |
| `has-instructions` | Body contains step-by-step instructions |
| `has-examples` | Body contains at least one usage example |
| `has-troubleshooting` | Body contains a Troubleshooting section |
| `step-numbering` | Steps are numbered and sequential |
| `parameter-table` | Parameters are documented in a table with type and required status |

**3.2 Script Checks:**

| Check ID | What it verifies |
|----------|-----------------|
| `script-exists` | `scripts/call_tool.py` or `scripts/geo_tool.py` exists |
| `script-valid-python` | Script parses as valid Python (no syntax errors) |
| `script-has-invoke` | Script defines `_invoke_tool_http` function |

**3.3 Reference Checks (if applicable):**

| Check ID | What it verifies |
|----------|-----------------|
| `reference-exists` | `references/reference.md` exists (if mentioned in SKILL.md) |
| `reference-nonempty` | Reference file is non-empty |

**3.4 Tool Name Checks:**

| Check ID | What it verifies |
|----------|-----------------|
| `tool-names-valid` | Tool function names found in SKILL.md are syntactically valid |

### Step 4: Auto-Score Rubric (V2 NEW)

**V2 adds heuristic-based automatic rubric scoring.** No human judgment needed for a baseline — the engine analyzes SKILL.md content and scores each rubric item 1-5.

```python
# Auto-score rubric for a single skill
rubric = auto_score_rubric("<skill-name>")
print(rubric["rubric_average"])  # e.g., 3.75/5
print(rubric["dimension_breakdown"])  # per-dimension breakdown

# Or run full rubric grading with combined deterministic + rubric
result = run_rubric_auto_grading("<skill-name>")
print(result["score"]["total_score"])  # e.g., 82.5/100
```

**4.1 Rubric items and their heuristic scoring criteria:**

| Check ID | Dimension | Scoring Heuristic |
|----------|-----------|-------------------|
| `r-trigger-clarity` | Outcome | Description length (>=100 chars +1), "Use when" pattern (+1), domain keywords count (+1), CJK coverage (+0.5), generic name penalty (-2) |
| `r-instruction-completeness` | Process | Step count (>=5 +1), code blocks (>=3 +1), parameter table presence, prerequisites mention (+0.5) |
| `r-example-quality` | Process | Example sections (>=2 +2), code blocks, realistic file paths (+0.5), dedicated Example heading (+0.5) |
| `r-error-handling` | Process | Troubleshooting items (>=5 → score 5, 3→4, 1→3, 0→1), error handling mentions (+1), input validation (+0.5) |
| `r-style-consistency` | Style | Heading hierarchy (H2>=3, H3>=2 +1), tables (>=3 rows +0.5), YAML front matter (-1 if missing), standard sections (>=3/4 +0.5) |
| `r-scientific-accuracy` | Style | Domain terminology count (>=8 → 5, >=4 → 4, >=2 → 3), caveats/limitations mention (+0.5), method references |
| `r-parameter-coverage` | Efficiency | Documented params (>=5 → 5, >=3 → 4, >=1 → 3), type annotations (+0.5), required/optional markers (+0.5) |
| `r-no-redundancy` | Efficiency | Duplicate line ratio (>15% → 2, >8% → 3, >3% → 4, else → 5), excessive length penalty (-1 if >8000 chars) |

**4.2 Grade scale:**

| Score | Meaning |
|-------|---------|
| 5 | Excellent — exceeds expectations |
| 4 | Good — meets all criteria |
| 3 | Adequate — meets basic criteria with minor gaps |
| 2 | Below standard — notable gaps or issues |
| 1 | Failing — critical missing or incorrect content |

**4.3 Dimension breakdown:**

Each rubric check maps to a dimension. The auto-scorer computes per-dimension averages:

```
Outcome  = avg(r-trigger-clarity)
Process  = avg(r-instruction-completeness, r-example-quality, r-error-handling)
Style    = avg(r-style-consistency, r-scientific-accuracy)
Efficiency = avg(r-parameter-coverage, r-no-redundancy)
```

### Step 5: Generate Evaluation Report

**V2 uses `evaluate_skill_v2()` for the complete pipeline:**

```python
# Full V2 evaluation: deterministic + rubric + bilingual prompts
result = evaluate_skill_v2("<skill-name>")
print(result["score"]["total_score"])
```

**Report structure:**

```markdown
# Skill Evaluation Report: <skill-name>

**Date:** <ISO date>
**Evaluator:** skill-evaluator v2

## Summary
| Dimension | Score | Weight | Contribution |
|-----------|-------|--------|-------------|
| Deterministic Checks | X/Y passed | 50% | Z/50 |
| Rubric Grading | N/5 avg | 50% | M/50 |
| **Total** | | | **T/100** |

**Grade:** A/B/C/D/F | **Verdict:** PASS / CONDITIONAL PASS / FAIL

## Deterministic Checks
(table of all checks with PASS/FAIL status)

## Rubric Grading
(table of all rubric items with scores and notes)

## Detected Tool Names
## Findings
### Critical Issues / Warnings / Suggestions
## Recommendations
```

**Scoring calculation:**

```
Deterministic score = (passed_checks / total_checks) * 50
Rubric score = (average_rubric_score / 5) * 50
Total score = Deterministic score + Rubric score
```

**Grade thresholds:** A (90-100), B (80-89), C (70-79), D (60-69), F (0-59)

**Verdict rules:**
- **PASS**: Score >= 70 AND zero critical issues
- **CONDITIONAL PASS**: Score >= 60 OR has warnings but no critical issues
- **FAIL**: Score < 60 OR has critical issues

## V2 Features

### Feature 1: Rubric Auto-Scoring

Run heuristic-based rubric evaluation without human input.

```python
exec(open("scripts/eval_tool.py").read())

# Auto-score rubric only
rubric = auto_score_rubric("kriging-interpolation")
for check in rubric["checks"]:
    print(f"  {check['id']}: {check['score']}/5 — {check['notes']}")

# Full rubric grading with deterministic checks combined
result = run_rubric_auto_grading("kriging-interpolation")
print(f"Score: {result['score']['total_score']}/100 ({result['score']['grade']})")
print(f"Dimension breakdown: {result['dimension_breakdown']}")
```

### Feature 2: Enhanced Batch Summary

V2 generates `batch-eval-summary-v2.md` with:

| Section | Content |
|---------|---------|
| Overall Statistics | Mean, median, std deviation, min/max, pass/fail rates |
| Score Distribution | Text-based histogram (0-19, 20-39, ..., 90-100) |
| Grade Distribution | Count, percentage, and skill list per grade |
| Dimension Breakdown | Per-dimension average, status (Strong/Adequate/Weak) |
| Category Analysis | Skills grouped by geoscience domain with avg scores |
| Common Issues | Severity-weighted issue table (CRITICAL → INFO) |
| Improvement Priority | Urgency-ranked list of skills needing attention |
| Top Performers | Skills scoring >= 90 |
| Actionable Recommendations | Auto-generated fix suggestions |

```python
exec(open("scripts/eval_tool.py").read())
results = evaluate_all_skills_v2(output_dir="evals/artifacts")
quick_stats_v2(results)
```

### Feature 3: Bilingual Prompt Generation

Auto-generate test prompts in both Chinese and English.

```python
exec(open("scripts/eval_tool.py").read())

# Generate bilingual prompts (auto-detects language from skill content)
prompts = generate_bilingual_prompts("kriging-interpolation")
for p in prompts:
    print(f"[{p['language'].upper()}] {p['prompt']}")

# Save to CSV
save_bilingual_prompts_csv(prompts, "evals/artifacts/kriging-interpolation-bilingual.prompts.csv")

# Language detection:
# - Skill SKILL.md contains CJK chars → EN + CN prompts (16 total)
# - English-only SKILL.md → EN prompts only (8 total)
```

**Domain auto-detection** supports: terrain, kriging, remote sensing, geology, geophysics, hydrology, geochemistry, and general geospatial.

### Feature 4: Skill Comparison Mode

Compare evaluation results before and after skill modifications.

```python
exec(open("scripts/eval_tool.py").read())

# Step 1: Evaluate before version (save report)
result_before = evaluate_skill_v2("my-skill", output_dir="evals/artifacts")
# Rename report
import shutil
shutil.move("evals/artifacts/my-skill-eval-report.md", "evals/artifacts/my-skill-eval-before.md")

# Step 2: Make changes to the skill...

# Step 3: Evaluate after version
result_after = evaluate_skill_v2("my-skill", output_dir="evals/artifacts")
shutil.move("evals/artifacts/my-skill-eval-report.md", "evals/artifacts/my-skill-eval-after.md")

# Step 4: Compare
comparison = compare_evaluations(
    "evals/artifacts/my-skill-eval-before.md",
    "evals/artifacts/my-skill-eval-after.md"
)
print(f"Score delta: {comparison['score_delta']:+.1f}")
print(f"New passes: {comparison['deterministic']['new_passes']}")
print(f"Regressions: {comparison['deterministic']['new_failures']}")
print(f"Report: {comparison['report_path']}")
```

**Comparison report includes:**
- Score comparison table (before/after/delta)
- Grade change indicator (↑ ↓ →)
- Fixed issues (FAIL → PASS)
- Regressions (PASS → FAIL) — **highlighted for action**
- Rubric score changes table
- Summary with actionable checklist

## Examples

**Example 1: Quick single-skill evaluation (V2)**

```python
exec(open("scripts/eval_tool.py").read())
result = evaluate_skill_v2("kriging-interpolation")
print(f"Score: {result['score']['total_score']}/100")
print(f"Rubric avg: {result['rubric']['rubric_average']}/5")
print(f"Prompts generated: {len(result['prompts'])}")
```

**Example 2: Batch evaluation with enhanced summary**

```python
exec(open("scripts/eval_tool.py").read())
results = evaluate_all_skills_v2()
quick_stats_v2(results)
```

**Example 3: Rubric auto-scoring only**

```python
exec(open("scripts/eval_tool.py").read())
rubric = auto_score_rubric("terrain-analysis")
for dim, data in rubric["dimension_breakdown"].items():
    print(f"  {dim}: {data['average']}/5 ({data['status']})")
```

**Example 4: Bilingual prompt generation**

```python
exec(open("scripts/eval_tool.py").read())
prompts = generate_bilingual_prompts("seismic-interpretation")
cn_prompts = [p for p in prompts if p["language"] == "cn"]
en_prompts = [p for p in prompts if p["language"] == "en"]
print(f"Chinese prompts: {len(cn_prompts)}, English prompts: {len(en_prompts)}")
```

**Example 5: Before/after comparison**

```python
exec(open("scripts/eval_tool.py").read())
comparison = compare_evaluations(
    "evals/artifacts/my-skill-eval-before.md",
    "evals/artifacts/my-skill-eval-after.md"
)
if comparison["has_regression"]:
    print("WARNING: Regressions detected!")
    for cid in comparison["deterministic"]["new_failures"]:
        print(f"  REGRESSED: {cid}")
```

## V1 Compatibility

All V1 functions remain available:

| V1 Function | V2 Equivalent | Notes |
|-------------|---------------|-------|
| `evaluate_skill()` | `evaluate_skill_v2()` | V2 adds rubric + bilingual |
| `evaluate_all_skills()` | `evaluate_all_skills_v2()` | V2 adds enhanced summary |
| `quick_stats()` | `quick_stats_v2()` | V2 adds rubric column |
| `generate_eval_prompts()` | `generate_bilingual_prompts()` | V2 adds CN/EN auto-detection |

## Troubleshooting

| Problem | Solution |
|---------|----------|
| Target skill directory not found | Verify the skill name matches a directory under `.claude/skills/` |
| Script has syntax errors | Report the error details and mark `script-valid-python` as FAIL |
| SKILL.md has no YAML front matter | Mark all frontmatter checks as FAIL; this is a critical issue |
| Rubric scores seem off | Review the heuristic criteria in Step 4.1; adjust scoring thresholds if needed |
| Bilingual prompts not generated | Check if SKILL.md contains CJK characters; use `generate_eval_prompts()` for English-only |
| Comparison report shows no changes | Ensure both report files are valid and contain different results |
| `auto_score_rubric` returns low scores | Check individual rubric check notes — low scores indicate specific improvement areas |

## Resource Index

| File | Purpose |
|------|---------|
| `scripts/eval_tool.py` | Core evaluation engine — deterministic checks, rubric auto-scoring, bilingual prompt generation, report generation, skill comparison, and enhanced batch summary |
| `scripts/batch_fix.py` | Batch remediation script — auto-fixes common skill issues (When to Use, instructions, script invoke, parameter table, redundancy, scientific terminology, examples) |
