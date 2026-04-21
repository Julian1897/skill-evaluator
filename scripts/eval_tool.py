"""
Skill Evaluator — Deterministic Check Engine
=============================================
Provides functions for automated, reproducible evaluation of Claude Code skills.
All checks are deterministic: same input always yields same output.
"""

import os
import ast
import re
import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# ── Configuration ──────────────────────────────────────────────────────────

SKILLS_BASE_DIR = os.path.join(".claude", "skills")


def _skill_dir(skill_name: str) -> str:
    """Return the path to a skill directory."""
    return os.path.join(SKILLS_BASE_DIR, skill_name)


def _skill_md_path(skill_name: str) -> str:
    """Return the path to a skill's SKILL.md."""
    return os.path.join(_skill_dir(skill_name), "SKILL.md")


def _get_script_path(skill_name: str) -> str | None:
    """Return a helper script path for a skill, or None for instruction-only skills."""
    skill_dir = _skill_dir(skill_name)
    preferred = ['scripts/call_tool.py', 'scripts/geo_tool.py', 'scripts/eval_tool.py']
    for script_name in preferred:
        script_path = os.path.join(skill_dir, script_name)
        if os.path.isfile(script_path):
            return script_path
    scripts_dir = os.path.join(skill_dir, 'scripts')
    if os.path.isdir(scripts_dir):
        for entry in sorted(os.listdir(scripts_dir)):
            if entry.endswith('.py'):
                return os.path.join(scripts_dir, entry)
    return None


def _read_skill_md(skill_name: str) -> str:
    """Read a skill's SKILL.md or return empty string if missing."""
    md_path = _skill_md_path(skill_name)
    if not os.path.isfile(md_path):
        return ""
    with open(md_path, 'r', encoding='utf-8') as f:
        return f.read()


def _skill_requires_script(skill_name: str, md_text: str | None = None) -> bool:
    """Infer whether a skill expects a helper script."""
    if md_text is None:
        md_text = _read_skill_md(skill_name)
    scripts_dir = os.path.join(_skill_dir(skill_name), 'scripts')
    if os.path.isdir(scripts_dir):
        for entry in os.listdir(scripts_dir):
            if entry.endswith('.py'):
                return True
    markers = [
        'scripts/call_tool.py',
        'scripts/geo_tool.py',
        'scripts/eval_tool.py',
        'exec(open("scripts/',
        "exec(open('scripts/"
    ]
    return any(marker in md_text for marker in markers)


# ── YAML Front Matter Parsing ─────────────────────────────────────────────

def parse_frontmatter(md_text: str) -> Dict[str, str]:
    """Extract YAML front matter from a Markdown file. Returns a dict of key-value pairs."""
    match = re.match(r'^---\s*\n(.*?)\n---\s*\n', md_text, re.DOTALL)
    if not match:
        return {}
    fm_text = match.group(1)
    result = {}
    for line in fm_text.split('\n'):
        line = line.strip()
        if ':' in line:
            key, _, value = line.partition(':')
            result[key.strip()] = value.strip()
    return result


def parse_body_sections(md_text: str) -> Dict[str, str]:
    """Parse Markdown body into sections keyed by heading."""
    # Remove front matter
    body = re.sub(r'^---\s*\n.*?\n---\s*\n', '', md_text, count=1, flags=re.DOTALL)
    sections = {}
    current_heading = "__preamble__"
    current_lines = []
    for line in body.split('\n'):
        heading_match = re.match(r'^#+\s+(.+)', line)
        if heading_match:
            sections[current_heading] = '\n'.join(current_lines)
            current_heading = heading_match.group(1).strip().lower()
            current_lines = []
        else:
            current_lines.append(line)
    sections[current_heading] = '\n'.join(current_lines)
    return sections


# ── Individual Checks ─────────────────────────────────────────────────────

def check_frontmatter_name(md_text: str) -> Dict:
    """Verify YAML front matter has a non-empty 'name' field."""
    fm = parse_frontmatter(md_text)
    name = fm.get('name', '')
    if name and len(name.strip()) > 0:
        return {"check_id": "frontmatter-name", "pass": True, "details": f"name = '{name}'"}
    return {"check_id": "frontmatter-name", "pass": False, "details": "Missing or empty 'name' in front matter"}


def check_frontmatter_desc(md_text: str) -> Dict:
    """Verify YAML front matter has a substantial 'description' field (>= 20 chars)."""
    fm = parse_frontmatter(md_text)
    desc = fm.get('description', '')
    if len(desc.strip()) >= 20:
        return {"check_id": "frontmatter-desc", "pass": True,
                "details": f"description length = {len(desc)} chars"}
    return {"check_id": "frontmatter-desc", "pass": False,
            "details": f"Description too short ({len(desc)} chars, need >= 20)"}


def check_desc_keywords(md_text: str) -> Dict:
    """Verify description includes trigger keywords for the skill's domain."""
    fm = parse_frontmatter(md_text)
    desc = fm.get('description', '').lower()
    # Check for common trigger patterns
    has_use_when = 'use when' in desc
    has_trigger = any(kw in desc for kw in [
        'keyword', 'trigger', 'perform', 'generate', 'analyze', 'create',
        'extract', 'process', 'detect', 'classify', 'interpolate', 'model',
        'simulate', 'monitor', 'assess', 'map', 'estimate', 'forecast'
    ])
    score = (1 if has_use_when else 0) + (1 if has_trigger else 0)
    if score >= 1:
        return {"check_id": "desc-keywords", "pass": True,
                "details": f"Has trigger keywords (use_when={has_use_when}, action_words={has_trigger})"}
    return {"check_id": "desc-keywords", "pass": False,
            "details": "Description lacks trigger keywords or 'Use when' pattern"}


def check_has_section(md_text: str, section_pattern: str, check_id: str) -> Dict:
    """Check if the body contains a section matching the pattern."""
    sections = parse_body_sections(md_text)
    for heading in sections:
        if section_pattern.lower() in heading:
            content = sections[heading].strip()
            return {"check_id": check_id, "pass": True,
                    "details": f"Found section '{heading}' ({len(content)} chars)"}
    return {"check_id": check_id, "pass": False,
            "details": f"No section matching '{section_pattern}' found"}


def check_step_numbering(md_text: str) -> Dict:
    """Verify top-level step headings are numbered and sequential."""
    step_pattern = re.compile(r'^###\s+Step\s+(\d+)\b', re.IGNORECASE | re.MULTILINE)
    steps = [int(num) for num in step_pattern.findall(md_text)]
    if not steps:
        return {"check_id": "step-numbering", "pass": False,
                "details": "No numbered step headings found"}
    expected = list(range(1, len(steps) + 1))
    is_sequential = steps == expected
    return {"check_id": "step-numbering", "pass": is_sequential,
            "details": f"Step headings found: {steps} — {'sequential' if is_sequential else 'not sequential'}"}


def check_parameter_table(md_text: str) -> Dict:
    """Check if parameters are documented in a table format."""
    # Look for Markdown tables with parameter-like headers
    table_pattern = re.compile(r'\|.*parameter.*\|.*type.*\|', re.IGNORECASE)
    if table_pattern.search(md_text):
        return {"check_id": "parameter-table", "pass": True,
                "details": "Found parameter table with type documentation"}
    # Also check for inline parameter docs
    param_pattern = re.compile(r'`[a-z_]+`\s*[:(]')
    if param_pattern.search(md_text):
        return {"check_id": "parameter-table", "pass": True,
                "details": "Found inline parameter documentation"}
    return {"check_id": "parameter-table", "pass": False,
            "details": "No parameter table or inline parameter docs found"}


# ── Script Checks ─────────────────────────────────────────────────────────

def check_script_exists(skill_name: str) -> Dict:
    """Verify the skill has a script file when the skill design requires one."""
    script_path = _get_script_path(skill_name)
    if script_path:
        rel_path = script_path.replace(_skill_dir(skill_name) + os.sep, '')
        return {"check_id": "script-exists", "pass": True,
                "details": f"Found {rel_path}"}
    if _skill_requires_script(skill_name):
        return {"check_id": "script-exists", "pass": False,
                "details": "Skill appears to require a helper script but none was found"}
    return {"check_id": "script-exists", "pass": True,
            "details": "Instruction-only skill; no helper script required"}


def check_script_valid_python(skill_name: str) -> Dict:
    """Verify the script file parses as valid Python when present."""
    script_path = _get_script_path(skill_name)
    if not script_path:
        if _skill_requires_script(skill_name):
            return {"check_id": "script-valid-python", "pass": False,
                    "details": "Required helper script is missing, so Python validity cannot be checked"}
        return {"check_id": "script-valid-python", "pass": True,
                "details": "No helper script present; nothing to validate"}
    rel_path = script_path.replace(_skill_dir(skill_name) + os.sep, '')
    try:
        with open(script_path, 'r', encoding='utf-8') as f:
            source = f.read()
        ast.parse(source)
        return {"check_id": "script-valid-python", "pass": True,
                "details": f"{rel_path} parses as valid Python"}
    except SyntaxError as e:
        return {"check_id": "script-valid-python", "pass": False,
                "details": f"Syntax error in {rel_path}: {e}"}


def check_script_has_invoke(skill_name: str) -> Dict:
    """Verify the script defines the _invoke_tool_http function when a helper script is present."""
    script_path = _get_script_path(skill_name)
    if not script_path:
        return {"check_id": "script-has-invoke", "pass": True,
                "details": "No helper script present; invoke check not applicable"}
    rel_path = script_path.replace(_skill_dir(skill_name) + os.sep, '')
    with open(script_path, 'r', encoding='utf-8') as f:
        source = f.read()
    if '_invoke_tool_http' in source:
        return {"check_id": "script-has-invoke", "pass": True,
                "details": f"_invoke_tool_http defined in {rel_path}"}
    return {"check_id": "script-has-invoke", "pass": False,
            "details": f"_invoke_tool_http not found in {rel_path}"}



# ── Reference Checks ──────────────────────────────────────────────────────

def check_reference_exists(skill_name: str, md_text: str | None = None) -> Dict:
    """Check if references/reference.md exists when SKILL.md links to that specific file."""
    if md_text is None:
        md_text = _read_skill_md(skill_name)
    mentions_reference = bool(re.search(r'\]\(references/reference\.md\)', md_text))
    ref_path = os.path.join(_skill_dir(skill_name), 'references', 'reference.md')
    ref_exists = os.path.isfile(ref_path)

    if mentions_reference:
        if ref_exists:
            return {"check_id": "reference-exists", "pass": True,
                    "details": "references/reference.md exists as referenced in SKILL.md"}
        return {"check_id": "reference-exists", "pass": False,
                "details": "SKILL.md links to references/reference.md but file does not exist"}

    return {"check_id": "reference-exists", "pass": True,
            "details": "No references/reference.md link found (optional)"}


def check_reference_nonempty(skill_name: str) -> Dict:
    """Check that reference.md is non-empty."""
    ref_path = os.path.join(_skill_dir(skill_name), 'references', 'reference.md')
    if os.path.isfile(ref_path):
        with open(ref_path, 'r', encoding='utf-8') as f:
            content = f.read().strip()
        if len(content) > 0:
            return {"check_id": "reference-nonempty", "pass": True,
                    "details": f"reference.md has {len(content)} chars"}
        return {"check_id": "reference-nonempty", "pass": False,
                "details": "reference.md is empty"}
    return {"check_id": "reference-nonempty", "pass": True,
            "details": "No reference.md (optional)"}


def check_tool_names_valid(skill_name: str, md_text: str | None = None) -> Dict:
    """Check whether tool names extracted from SKILL.md look syntactically valid."""
    if md_text is None:
        md_text = _read_skill_md(skill_name)
    tool_names = extract_tool_names(md_text)
    if not tool_names:
        return {"check_id": "tool-names-valid", "pass": True,
                "details": "No explicit tool invocation names found to validate"}
    invalid = [name for name in tool_names if not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', name)]
    if invalid:
        return {"check_id": "tool-names-valid", "pass": False,
                "details": f"Invalid tool names: {invalid}"}
    return {"check_id": "tool-names-valid", "pass": True,
            "details": f"Extracted valid tool names: {', '.join(sorted(tool_names))}"}


# ── Tool Name Extraction ──────────────────────────────────────────────────

def extract_tool_names(md_text: str) -> List[str]:
    """Extract tool function names from _invoke_tool_http calls in the SKILL.md."""
    pattern = re.compile(r'_invoke_tool_http\(\s*["\'](\w+)["\']', re.MULTILINE)
    return list(set(pattern.findall(md_text)))


# ── Master Runner ─────────────────────────────────────────────────────────

def run_all_deterministic_checks(skill_name: str) -> Dict:
    """
    Run all deterministic checks for a given skill.
    Returns a structured result with individual check results and summary stats.
    """
    results = {
        "skill_name": skill_name,
        "checks": [],
        "summary": {
            "total": 0,
            "passed": 0,
            "failed": 0,
            "pass_rate": 0.0
        }
    }

    # Read SKILL.md
    md_path = _skill_md_path(skill_name)
    if not os.path.isfile(md_path):
        results["checks"].append({
            "check_id": "skill-md-exists", "pass": False,
            "details": f"SKILL.md not found at {md_path}"
        })
        results["summary"]["total"] = 1
        results["summary"]["failed"] = 1
        results["summary"]["pass_rate"] = 0.0
        return results

    with open(md_path, 'r', encoding='utf-8') as f:
        md_text = f.read()

    # ── SKILL.md Structure Checks ──
    results["checks"].append(check_frontmatter_name(md_text))
    results["checks"].append(check_frontmatter_desc(md_text))
    results["checks"].append(check_desc_keywords(md_text))
    results["checks"].append(check_has_section(md_text, "when to use", "has-when-to-use"))
    results["checks"].append(check_has_section(md_text, "instruction", "has-instructions"))
    results["checks"].append(check_has_section(md_text, "example", "has-examples"))
    results["checks"].append(check_has_section(md_text, "troubleshoot", "has-troubleshooting"))
    results["checks"].append(check_step_numbering(md_text))
    results["checks"].append(check_parameter_table(md_text))

    # ── Script Checks ──
    results["checks"].append(check_script_exists(skill_name))
    results["checks"].append(check_script_valid_python(skill_name))
    results["checks"].append(check_script_has_invoke(skill_name))

    # ── Reference Checks ──
    results["checks"].append(check_reference_exists(skill_name, md_text))
    results["checks"].append(check_reference_nonempty(skill_name))

    # ── Tool Name Checks ──
    results["checks"].append(check_tool_names_valid(skill_name, md_text))

    # ── Summary ──
    total = len(results["checks"])
    passed = sum(1 for c in results["checks"] if c["pass"])
    results["summary"]["total"] = total
    results["summary"]["passed"] = passed
    results["summary"]["failed"] = total - passed
    results["summary"]["pass_rate"] = round(passed / total * 100, 1) if total > 0 else 0.0

    # ── Extracted info ──
    results["tool_names"] = extract_tool_names(md_text)
    results["frontmatter"] = parse_frontmatter(md_text)

    return results


def run_batch_deterministic_checks() -> List[Dict]:
    """Run deterministic checks on all skills in the skills directory."""
    results = []
    if not os.path.isdir(SKILLS_BASE_DIR):
        return results
    for entry in sorted(os.listdir(SKILLS_BASE_DIR)):
        skill_path = os.path.join(SKILLS_BASE_DIR, entry)
        if os.path.isdir(skill_path) and os.path.isfile(os.path.join(skill_path, "SKILL.md")):
            result = run_all_deterministic_checks(entry)
            results.append(result)
    return results


# ── Eval Prompt Generation ────────────────────────────────────────────────

def generate_eval_prompts(skill_name: str, md_text: str = None) -> List[Dict]:
    """
    Generate a set of eval prompts for a skill based on its SKILL.md content.
    Returns a list of dicts with id, should_trigger, category, prompt, expected_behavior.
    """
    if md_text is None:
        md_path = _skill_md_path(skill_name)
        if os.path.isfile(md_path):
            with open(md_path, 'r', encoding='utf-8') as f:
                md_text = f.read()
        else:
            return []

    fm = parse_frontmatter(md_text)
    name = fm.get('name', skill_name)
    desc = fm.get('description', '')
    tool_names = extract_tool_names(md_text)
    tool_name = tool_names[0] if tool_names else name

    when_to_use_match = re.search(r'##\s+When to Use\s*(.*?)(?:\n##\s+|\Z)', md_text, re.DOTALL | re.IGNORECASE)
    when_to_use_text = when_to_use_match.group(1).strip() if when_to_use_match else ''
    domain_hint = desc.replace('Use when', '').strip().rstrip('.') if desc else f'use {name}'
    short_domain_hint = domain_hint[:120] + '...' if len(domain_hint) > 120 else domain_hint

    prompts = []

    prompts.append({
        "id": f"{skill_name}-01",
        "should_trigger": True,
        "category": "explicit",
        "prompt": f"Use the ${name} skill to perform its documented task",
        "expected_behavior": f"Should invoke {name} and follow its documented steps"
    })
    prompts.append({
        "id": f"{skill_name}-02",
        "should_trigger": True,
        "category": "explicit",
        "prompt": f"Run ${name} with standard parameters",
        "expected_behavior": f"Should invoke {name}, ask for missing required parameters"
    })

    action_words = re.findall(r'\b(perform|generate|analyze|create|extract|process|detect|classify|interpolate|model|simulate|monitor|assess|map|estimate|forecast|calculate|evaluate|convert|visualize|load|retrieve)\b', desc.lower())
    if action_words:
        action = action_words[0]
        prompts.append({
            "id": f"{skill_name}-03",
            "should_trigger": True,
            "category": "implicit",
            "prompt": f"I need help to {action} data for this task",
            "expected_behavior": f"Should trigger {name} based on task description matching"
        })
    prompts.append({
        "id": f"{skill_name}-04",
        "should_trigger": True,
        "category": "implicit",
        "prompt": short_domain_hint,
        "expected_behavior": f"Should trigger {name} since the prompt matches its description"
    })

    contextual_prompt = when_to_use_text.split('\n')[0].strip('- ').strip() if when_to_use_text else domain_hint
    prompts.append({
        "id": f"{skill_name}-05",
        "should_trigger": True,
        "category": "contextual",
        "prompt": f"I'm working on a real project and need help with this: {contextual_prompt}",
        "expected_behavior": f"Should trigger {name} in a realistic project context"
    })

    prompts.append({
        "id": f"{skill_name}-06",
        "should_trigger": False,
        "category": "negative",
        "prompt": "I only need a high-level explanation, not a specialized workflow or tool invocation",
        "expected_behavior": "Should NOT trigger because this request stays at a generic explanation level"
    })
    prompts.append({
        "id": f"{skill_name}-07",
        "should_trigger": False,
        "category": "negative",
        "prompt": "Help me set up my development environment",
        "expected_behavior": "Should NOT trigger because this is environment setup, not the target task"
    })

    prompts.append({
        "id": f"{skill_name}-08",
        "should_trigger": True,
        "category": "edge-case",
        "prompt": f"Use ${name} but I don't yet have all required inputs",
        "expected_behavior": f"Should trigger {name} and ask for missing parameters instead of fabricating them"
    })

    return prompts


def save_prompts_csv(prompts: List[Dict], output_path: str):
    """Save generated prompts to a CSV file."""
    import csv
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=['id', 'should_trigger', 'category', 'prompt', 'expected_behavior'])
        writer.writeheader()
        for prompt in prompts:
            writer.writerow(prompt)


# ── Report Generation ─────────────────────────────────────────────────────

def compute_score(deterministic_results: Dict, rubric_results: Dict = None) -> Dict:
    """
    Compute the final evaluation score.
    deterministic_results: output of run_all_deterministic_checks()
    rubric_results: dict with 'checks' list containing {id, pass, score, notes}
    """
    det_summary = deterministic_results.get("summary", {})
    det_total = det_summary.get("total", 1)
    det_passed = det_summary.get("passed", 0)
    det_percent = (det_passed / det_total) * 100 if det_total > 0 else 0
    det_score = (det_passed / det_total) * 50 if det_total > 0 else 0

    rubric_score = 0.0
    rubric_avg = None
    rubric_used = bool(rubric_results and rubric_results.get("checks"))
    if rubric_used:
        scores = [c.get("score", 0) for c in rubric_results["checks"]]
        rubric_avg = sum(scores) / len(scores) if scores else 0
        rubric_score = (rubric_avg / 5) * 50
        total_score = round(det_score + rubric_score, 1)
    else:
        total_score = round(det_percent, 1)

    if total_score >= 90:
        grade = "A"
    elif total_score >= 80:
        grade = "B"
    elif total_score >= 70:
        grade = "C"
    elif total_score >= 60:
        grade = "D"
    else:
        grade = "F"

    critical_issues = [c for c in deterministic_results.get("checks", [])
                       if not c["pass"] and c["check_id"] in [
                           "frontmatter-name", "frontmatter-desc", "skill-md-exists"
                       ]]
    if total_score >= 70 and len(critical_issues) == 0:
        verdict = "PASS"
    elif total_score >= 60 and len(critical_issues) == 0:
        verdict = "CONDITIONAL PASS"
    else:
        verdict = "FAIL"

    return {
        "deterministic_score": round(det_score, 1),
        "deterministic_percent": round(det_percent, 1),
        "rubric_used": rubric_used,
        "rubric_score": round(rubric_score, 1),
        "rubric_average": round(rubric_avg, 2) if rubric_avg is not None else None,
        "total_score": total_score,
        "grade": grade,
        "verdict": verdict,
        "critical_issues": [c["check_id"] for c in critical_issues]
    }


def generate_report(skill_name: str, deterministic_results: Dict,
                    rubric_results: Dict = None, score: Dict = None) -> str:
    """Generate a Markdown evaluation report."""
    from datetime import datetime

    score = score or compute_score(deterministic_results, rubric_results)

    lines = [
        f"# Skill Evaluation Report: {skill_name}",
        "",
        f"**Date:** {datetime.now().isoformat()}",
        "**Evaluator:** skill-evaluator (automated)",
        f"**Target:** `.claude/skills/{skill_name}/`",
        "",
        "## Summary",
        "",
        "| Dimension | Score | Weight | Contribution |",
        "|-----------|-------|--------|-------------|",
        f"| Deterministic Checks | {deterministic_results['summary']['passed']}/{deterministic_results['summary']['total']} passed ({deterministic_results['summary']['pass_rate']}%) | {'50%' if score.get('rubric_used') else '100%'} | {score['deterministic_score']}/50{' → ' + str(score['deterministic_percent']) + '/100' if not score.get('rubric_used') else ''} |",
        f"| Rubric Grading | {(str(score.get('rubric_average')) + '/5 avg') if score.get('rubric_used') else 'Not run'} | {'50%' if score.get('rubric_used') else '—'} | {str(score['rubric_score']) + '/50' if score.get('rubric_used') else '—'} |",
        f"| **Total** | | | **{score['total_score']}/100** |",
        "",
        f"**Grade:** {score['grade']} | **Verdict:** {score['verdict']}",
        "",
        "## Deterministic Checks",
        "",
        "| Check | Status | Details |",
        "|-------|--------|---------|",
    ]

    for check in deterministic_results.get("checks", []):
        status = "PASS" if check["pass"] else "FAIL"
        lines.append(f"| {check['check_id']} | {status} | {check['details']} |")

    det_pass = deterministic_results["summary"]["passed"]
    det_total = deterministic_results["summary"]["total"]
    lines.append(f"")
    lines.append(f"**Deterministic pass rate:** {det_pass}/{det_total} ({deterministic_results['summary']['pass_rate']}%)")

    if rubric_results:
        lines.extend([
            "",
            "## Rubric Grading",
            "",
            "| Check | Score | Pass | Notes |",
            "|-------|-------|------|-------|",
        ])
        for check in rubric_results.get("checks", []):
            lines.append(f"| {check['id']} | {check.get('score', 'N/A')}/5 | {'PASS' if check['pass'] else 'FAIL'} | {check.get('notes', '')} |")

    # Tool names
    if deterministic_results.get("tool_names"):
        lines.extend([
            "",
            "## Detected Tool Names",
            "",
        ])
        for tn in deterministic_results["tool_names"]:
            lines.append(f"- `{tn}`")

    # Findings
    lines.extend([
        "",
        "## Findings",
        "",
    ])

    failed = [c for c in deterministic_results.get("checks", []) if not c["pass"]]
    if failed:
        lines.append("### Critical Issues")
        for c in failed:
            if c["check_id"] in ["frontmatter-name", "frontmatter-desc", "skill-md-exists"]:
                lines.append(f"- **{c['check_id']}**: {c['details']}")
        lines.append("")
        lines.append("### Warnings")
        for c in failed:
            if c["check_id"] not in ["frontmatter-name", "frontmatter-desc", "skill-md-exists"]:
                lines.append(f"- **{c['check_id']}**: {c['details']}")
    else:
        lines.append("All deterministic checks passed. No issues found.")

    lines.extend(["", "---", f"*Generated by skill-evaluator on {datetime.now().isoformat()}*"])

    return "\n".join(lines)


# ── Convenience Functions (for interactive use) ───────────────────────────

def evaluate_skill(skill_name: str, output_dir: str = "evals/artifacts") -> Dict:
    """
    Run a complete evaluation of a single skill.
    Returns the full results and writes report to disk.
    """
    os.makedirs(output_dir, exist_ok=True)

    # Step 1: Run deterministic checks
    det_results = run_all_deterministic_checks(skill_name)

    # Step 2: Generate eval prompts
    prompts = generate_eval_prompts(skill_name)
    if prompts:
        prompts_path = os.path.join(output_dir, f"{skill_name}.prompts.csv")
        save_prompts_csv(prompts, prompts_path)

    # Step 3: Compute score (without rubric — that requires human/AI judgment)
    score = compute_score(det_results)

    # Step 4: Generate and save report
    report = generate_report(skill_name, det_results, score=score)
    report_path = os.path.join(output_dir, f"{skill_name}-eval-report.md")
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(report)

    return {
        "skill_name": skill_name,
        "deterministic": det_results,
        "prompts": prompts,
        "score": score,
        "report_path": report_path
    }


def evaluate_all_skills(output_dir: str = "evals/artifacts") -> List[Dict]:
    """Evaluate all skills in the skills directory."""
    results = []
    if not os.path.isdir(SKILLS_BASE_DIR):
        print(f"Skills directory not found: {SKILLS_BASE_DIR}")
        return results

    for entry in sorted(os.listdir(SKILLS_BASE_DIR)):
        skill_path = os.path.join(SKILLS_BASE_DIR, entry)
        if os.path.isdir(skill_path) and os.path.isfile(os.path.join(skill_path, "SKILL.md")):
            print(f"Evaluating: {entry}...")
            result = evaluate_skill(entry, output_dir)
            results.append(result)
            print(f"  Score: {result['score']['total_score']}/100 ({result['score']['grade']}) — {result['score']['verdict']}")

    # Generate batch summary
    if results:
        _generate_batch_summary(results, output_dir)

    return results


def _generate_batch_summary(results: List[Dict], output_dir: str):
    """Generate a batch evaluation summary report."""
    from datetime import datetime

    scores = [r["score"]["total_score"] for r in results]
    avg_score = round(sum(scores) / len(scores), 1) if scores else 0

    grade_counts = {"A": [], "B": [], "C": [], "D": [], "F": []}
    for r in results:
        grade_counts[r["score"]["grade"]].append(r["skill_name"])

    lines = [
        "# Batch Evaluation Summary",
        "",
        f"**Date:** {datetime.now().isoformat()}",
        f"**Skills evaluated:** {len(results)}",
        f"**Average score:** {avg_score}/100",
        "",
        "## Score Distribution",
        "",
        "| Grade | Count | Skills |",
        "|-------|-------|--------|",
    ]
    for grade, skills in grade_counts.items():
        if skills:
            lines.append(f"| {grade} | {len(skills)} | {', '.join(skills[:5])}{'...' if len(skills) > 5 else ''} |")
        else:
            lines.append(f"| {grade} | 0 | — |")

    lines.extend(["", "## Common Issues", ""])

    # Aggregate failed checks
    issue_counts = {}
    for r in results:
        for c in r["deterministic"].get("checks", []):
            if not c["pass"]:
                cid = c["check_id"]
                if cid not in issue_counts:
                    issue_counts[cid] = []
                issue_counts[cid].append(r["skill_name"])

    if issue_counts:
        lines.append("| Issue | Affected Skills | Count |")
        lines.append("|-------|----------------|-------|")
        for issue, skills in sorted(issue_counts.items(), key=lambda x: -len(x[1])):
            lines.append(f"| {issue} | {', '.join(skills[:3])}{'...' if len(skills) > 3 else ''} | {len(skills)} |")
    else:
        lines.append("No common issues found.")

    lines.extend([
        "",
        "## Top Skills (score >= 90)",
        "",
    ])
    top = [r for r in results if r["score"]["total_score"] >= 90]
    if top:
        for r in sorted(top, key=lambda x: -x["score"]["total_score"]):
            lines.append(f"- **{r['skill_name']}** — {r['score']['total_score']}/100")
    else:
        lines.append("No skills scored 90 or above.")

    lines.extend([
        "",
        "## Skills Needing Attention (score < 70)",
        "",
    ])
    low = [r for r in results if r["score"]["total_score"] < 70]
    if low:
        for r in sorted(low, key=lambda x: x["score"]["total_score"]):
            lines.append(f"- **{r['skill_name']}** — {r['score']['total_score']}/100 ({r['score']['grade']})")
    else:
        lines.append("All skills scored 70 or above.")

    lines.extend(["", "---", f"*Generated by skill-evaluator on {datetime.now().isoformat()}*"])

    summary_path = os.path.join(output_dir, "batch-eval-summary.md")
    with open(summary_path, 'w', encoding='utf-8') as f:
        f.write("\n".join(lines))

    print(f"\nBatch summary written to: {summary_path}")


# ── Quick stats ───────────────────────────────────────────────────────────

def quick_stats(results: List[Dict]):
    """Print a quick summary table of batch evaluation results."""
    print(f"\n{'Skill':<35} {'Score':>6} {'Grade':>6} {'Verdict':<20}")
    print("─" * 70)
    for r in sorted(results, key=lambda x: -x["score"]["total_score"]):
        s = r["score"]
        print(f"{r['skill_name']:<35} {s['total_score']:>5.1f} {s['grade']:>6} {s['verdict']:<20}")


# ═══════════════════════════════════════════════════════════════════════════
# V2 UPGRADE: Rubric Auto-Scoring, Bilingual Prompts, Comparison Mode,
#             Enhanced Batch Summary
# ═══════════════════════════════════════════════════════════════════════════


# ── Rubric Auto-Scoring Engine ───────────────────────────────────────────

def _count_code_blocks(md_text: str) -> int:
    """Count fenced code blocks in markdown."""
    return len(re.findall(r'```', md_text)) // 2


def _count_examples(md_text: str) -> int:
    """Count 'Example' sections and example-like blocks."""
    sections = parse_body_sections(md_text)
    count = 0
    for heading in sections:
        if 'example' in heading:
            count += 1
    # Also count code blocks after "Example" markers
    count += len(re.findall(r'\*\*Example', md_text, re.IGNORECASE))
    return max(count, 1)


def _count_troubleshooting_items(md_text: str) -> int:
    """Count rows in troubleshooting table or bullet items."""
    sections = parse_body_sections(md_text)
    for heading in sections:
        if 'troubleshoot' in heading:
            content = sections[heading]
            table_rows = len(re.findall(r'\|.*\|.*\|', content)) - 1
            bullet_items = len(re.findall(r'^\s*-\s+', content, re.MULTILINE))
            return max(table_rows, bullet_items)
    return 0


def _count_parameters_documented(md_text: str) -> int:
    """Count documented parameters from tables or inline param docs."""
    table_rows = re.findall(r'\|.*`([a-z_]+)`.*\|', md_text, re.IGNORECASE)
    inline_params = re.findall(r'`([a-z_]+)`\s*[:(]', md_text)
    return len(set(table_rows + inline_params))


def _estimate_tool_param_count(md_text: str) -> int:
    """Estimate how many parameters a tool likely has based on invocation patterns."""
    invoke_calls = re.findall(r'_invoke_tool_http\([^)]+\)', md_text)
    if not invoke_calls:
        return 0
    params = set()
    for call in invoke_calls:
        params.update(re.findall(r'["\'](\w+)["\']', call))
    return len(params)


def _check_redundancy(md_text: str) -> Tuple[float, List[str]]:
    """Detect redundant content. Returns (redundancy_ratio, list_of_issues)."""
    issues = []
    lines = [l.strip() for l in md_text.split('\n') if l.strip() and not l.strip().startswith('#') and not l.strip().startswith('|') and not l.strip().startswith('```')]
    if len(lines) < 2:
        return (0.0, [])

    seen = {}
    duplicates = 0
    for line in lines:
        normalized = re.sub(r'\s+', ' ', line.lower().strip())
        if len(normalized) < 20:
            continue
        if normalized in seen:
            duplicates += 1
            if duplicates <= 3:
                issues.append(f"Duplicate line: '{line[:60]}...'")
        else:
            seen[normalized] = True

    ratio = duplicates / max(len(lines), 1)
    return (round(ratio, 3), issues[:5])


def _has_cjk(text: str) -> bool:
    """Check if text contains CJK characters."""
    return bool(re.search(r'[\u4e00-\u9fff\u3400-\u4dbf]', text))


def _score_trigger_clarity(md_text: str) -> Dict:
    """Score r-trigger-clarity: Is the skill's name + description specific enough?"""
    fm = parse_frontmatter(md_text)
    name = fm.get('name', '')
    desc = fm.get('description', '')
    score = 3
    notes = []

    if not name:
        return {"id": "r-trigger-clarity", "pass": False, "score": 1,
                "notes": "Missing skill name in front matter"}

    # Check description specificity
    if len(desc) >= 100:
        score += 1
        notes.append("Rich description (>100 chars)")
    elif len(desc) >= 50:
        notes.append("Adequate description length")
    else:
        score -= 1
        notes.append("Short description (<50 chars)")

    # Check for "Use when" pattern
    if re.search(r'use when|trigger|TRIGGER', desc, re.IGNORECASE):
        score += 1
        notes.append("Has explicit trigger pattern")

    # Check for domain-specific keywords
    domain_kw_count = len(re.findall(
        r'\b(kriging|interpolat|classif|detect|extract|segment|monitor|simulat|model|predict|'
        r'assess|analyz|process|generat|convert|visualiz|forecast|delineat|estimat)\b',
        desc, re.IGNORECASE))
    if domain_kw_count >= 2:
        score += 1
        notes.append(f"Multiple domain keywords ({domain_kw_count})")

    # Chinese keyword coverage
    if _has_cjk(desc):
        notes.append("Has Chinese keyword coverage")
        score += 0.5

    # Penalize overly generic names
    generic_names = ['skill', 'tool', 'helper', 'utility', 'test', 'demo']
    if name.lower() in generic_names:
        score -= 2
        notes.append("Overly generic skill name")

    score = max(1, min(5, round(score)))
    return {"id": "r-trigger-clarity", "pass": score >= 3, "score": score,
            "notes": "; ".join(notes) if notes else "Basic trigger clarity"}


def _score_instruction_completeness(md_text: str) -> Dict:
    """Score r-instruction-completeness: Are steps complete and well-ordered?"""
    score = 3
    notes = []

    step_pattern = re.compile(r'^###\s+Step\s+\d+', re.MULTILINE)
    steps = step_pattern.findall(md_text)
    step_count = len(steps)

    if step_count >= 5:
        score += 1
        notes.append(f"Comprehensive steps ({step_count} steps)")
    elif step_count >= 3:
        notes.append(f"Adequate steps ({step_count})")
    elif step_count >= 1:
        notes.append(f"Minimal steps ({step_count})")
    else:
        score -= 1
        notes.append("No numbered step headings")

    # Check for code blocks in instructions
    code_blocks = _count_code_blocks(md_text)
    if code_blocks >= 3:
        score += 1
        notes.append(f"Rich code examples ({code_blocks} code blocks)")
    elif code_blocks >= 1:
        notes.append(f"Has code examples ({code_blocks})")

    # Check for parameter documentation
    if check_parameter_table(md_text)["pass"]:
        notes.append("Parameters documented")

    # Check for "before you begin" / prerequisites
    if re.search(r'prerequisite|before you begin|requirement|前提|前置', md_text, re.IGNORECASE):
        score += 0.5
        notes.append("Has prerequisites")

    score = max(1, min(5, round(score)))
    return {"id": "r-instruction-completeness", "pass": score >= 3, "score": score,
            "notes": "; ".join(notes) if notes else "Basic instruction completeness"}


def _score_example_quality(md_text: str) -> Dict:
    """Score r-example-quality: Are examples realistic and runnable?"""
    score = 2
    notes = []

    example_sections = _count_examples(md_text)
    code_blocks = _count_code_blocks(md_text)

    if example_sections >= 2 and code_blocks >= 2:
        score = 4
        notes.append(f"Multiple examples ({example_sections}) with code ({code_blocks} blocks)")
    elif example_sections >= 1 and code_blocks >= 1:
        score = 3
        notes.append(f"Has examples ({example_sections}) with code ({code_blocks})")
    elif code_blocks >= 2:
        score = 3
        notes.append(f"Code blocks present ({code_blocks}) but no explicit Example section")

    # Check if examples contain realistic parameters
    if re.search(r'["\'][\w/]+\.(tif|csv|shp|nc|json|geojson)["\']', md_text):
        score += 0.5
        notes.append("Examples use realistic file paths")

    # Check for "Example" labeled sections
    if re.search(r'^##\s+Example', md_text, re.MULTILINE):
        score += 0.5
        notes.append("Has dedicated Example section")

    score = max(1, min(5, round(score)))
    return {"id": "r-example-quality", "pass": score >= 3, "score": score,
            "notes": "; ".join(notes) if notes else "Basic examples"}


def _score_error_handling(md_text: str) -> Dict:
    """Score r-error-handling: Does Troubleshooting cover common failures?"""
    score = 2
    notes = []

    ts_items = _count_troubleshooting_items(md_text)

    if ts_items >= 5:
        score = 5
        notes.append(f"Comprehensive troubleshooting ({ts_items} items)")
    elif ts_items >= 3:
        score = 4
        notes.append(f"Good troubleshooting coverage ({ts_items} items)")
    elif ts_items >= 1:
        score = 3
        notes.append(f"Basic troubleshooting ({ts_items} items)")
    else:
        notes.append("No troubleshooting section found")
        score = 1

    # Check for error/exception handling in code
    if re.search(r'try\s*:|except\s|raise\s|error|Error|exception', md_text):
        score = min(5, score + 1)
        notes.append("Mentions error handling")

    # Check for "if...not" / validation patterns
    if re.search(r'if not|if missing|validate|check.*exist', md_text, re.IGNORECASE):
        notes.append("Has input validation guidance")

    score = max(1, min(5, score))
    return {"id": "r-error-handling", "pass": score >= 3, "score": score,
            "notes": "; ".join(notes) if notes else "Basic error handling"}


def _score_style_consistency(md_text: str) -> Dict:
    """Score r-style-consistency: Does the skill follow conventions?"""
    score = 3
    notes = []

    # Check heading hierarchy
    h2_count = len(re.findall(r'^## ', md_text, re.MULTILINE))
    h3_count = len(re.findall(r'^### ', md_text, re.MULTILINE))
    if h2_count >= 3 and h3_count >= 2:
        score += 1
        notes.append(f"Good heading hierarchy (H2:{h2_count}, H3:{h3_count})")
    elif h2_count >= 2:
        notes.append(f"Basic heading structure (H2:{h2_count})")

    # Check for consistent formatting
    table_count = len(re.findall(r'^\|.*\|.*\|$', md_text, re.MULTILINE))
    if table_count >= 3:
        score += 0.5
        notes.append(f"Uses tables ({table_count} rows)")

    # Check for YAML front matter
    if re.match(r'^---\s*\n', md_text):
        notes.append("Has proper YAML front matter")
    else:
        score -= 1
        notes.append("Missing YAML front matter")

    # Check for standard sections
    standard = ['when to use', 'instruction', 'example', 'troubleshoot']
    found = sum(1 for s in standard
                if any(s in h for h in parse_body_sections(md_text)))
    if found >= 3:
        score += 0.5
        notes.append(f"Has {found}/4 standard sections")

    score = max(1, min(5, round(score)))
    return {"id": "r-style-consistency", "pass": score >= 3, "score": score,
            "notes": "; ".join(notes) if notes else "Basic style"}


def _score_scientific_accuracy(md_text: str) -> Dict:
    """Score r-scientific-accuracy: Are geoscience terms and methods correct?"""
    score = 3
    notes = []

    # Check for domain terminology
    geo_terms = re.findall(
        r'\b(DEM|DTM|DSM|LiDAR|SAR|NDVI|kriging|interpolat|spatial|'
        r'raster|vector|GeoTIFF|shapefile|coordinate|projection|'
        r'CRS|EPSG|WGS\s*84|UTM|geoid|ellipsoid|datum|'
        r'slope|aspect|hillshade|curvature|watershed|'
        r'geology|geophysic|seismic|magnetic|gravity|'
        r'remote\s+sensing|classification|segmentation|'
        r'GeoJSON|NetCDF|EPSG)\b',
        md_text, re.IGNORECASE)
    unique_terms = set(t.lower() for t in geo_terms)

    if len(unique_terms) >= 8:
        score = 5
        notes.append(f"Rich domain terminology ({len(unique_terms)} unique terms)")
    elif len(unique_terms) >= 4:
        score = 4
        notes.append(f"Good domain vocabulary ({len(unique_terms)} terms)")
    elif len(unique_terms) >= 2:
        notes.append(f"Some domain terms ({len(unique_terms)})")

    # Check for caveats/limitations
    if re.search(r'caveat|limitation|assumption|note\s+that|caveats|注意|限制|假设', md_text, re.IGNORECASE):
        score = min(5, score + 0.5)
        notes.append("Mentions caveats/limitations")

    # Check for references to methods/algorithms
    if re.search(r'algorithm|method|approach|model|formula|算法|方法|模型', md_text, re.IGNORECASE):
        notes.append("References methods/algorithms")

    score = max(1, min(5, round(score)))
    return {"id": "r-scientific-accuracy", "pass": score >= 3, "score": score,
            "notes": "; ".join(notes) if notes else "Basic scientific accuracy"}


def _score_parameter_coverage(md_text: str) -> Dict:
    """Score r-parameter-coverage: Are all tool parameters documented?"""
    score = 3
    notes = []

    param_count = _count_parameters_documented(md_text)
    tool_param_est = _estimate_tool_param_count(md_text)

    if param_count >= 5:
        score = 5
        notes.append(f"Comprehensive parameter docs ({param_count} params)")
    elif param_count >= 3:
        score = 4
        notes.append(f"Good parameter coverage ({param_count} params)")
    elif param_count >= 1:
        notes.append(f"Some parameters documented ({param_count})")
    else:
        score = 2
        notes.append("No explicit parameter documentation")

    # Check for type annotations
    type_hints = re.findall(r'\|\s*\w+\s*\|\s*(string|integer|float|boolean|str|int|bool|list|dict|array|number|path|file)', md_text, re.IGNORECASE)
    if type_hints:
        notes.append(f"Has type annotations ({len(type_hints)})")
        score = min(5, score + 0.5)

    # Check for required/optional markers
    req_markers = re.findall(r'required|optional|必填|选填|必需', md_text, re.IGNORECASE)
    if req_markers:
        notes.append(f"Documents required/optional ({len(req_markers)} refs)")
        score = min(5, score + 0.5)

    score = max(1, min(5, round(score)))
    return {"id": "r-parameter-coverage", "pass": score >= 3, "score": score,
            "notes": "; ".join(notes) if notes else "Basic parameter coverage"}


def _score_no_redundancy(md_text: str) -> Dict:
    """Score r-no-redundancy: No duplicated content or unnecessary sections?"""
    redundancy_ratio, issues = _check_redundancy(md_text)
    score = 5
    notes = []

    if redundancy_ratio > 0.15:
        score = 2
        notes.append(f"High redundancy ({redundancy_ratio:.0%})")
    elif redundancy_ratio > 0.08:
        score = 3
        notes.append(f"Moderate redundancy ({redundancy_ratio:.0%})")
    elif redundancy_ratio > 0.03:
        score = 4
        notes.append(f"Low redundancy ({redundancy_ratio:.0%})")
    else:
        notes.append(f"Minimal redundancy ({redundancy_ratio:.0%})")

    if issues:
        notes.append(f"Top issue: {issues[0][:80]}")

    # Check total length — overly verbose skills lose points
    total_len = len(md_text)
    if total_len > 8000:
        notes.append(f"Very long SKILL.md ({total_len} chars) — may contain bloat")
        score = max(1, score - 1)

    score = max(1, min(5, round(score)))
    return {"id": "r-no-redundancy", "pass": score >= 3, "score": score,
            "notes": "; ".join(notes) if notes else "No redundancy issues"}


# ── Master Rubric Auto-Scorer ─────────────────────────────────────────────

_RUBRIC_SCORERS = [
    _score_trigger_clarity,
    _score_instruction_completeness,
    _score_example_quality,
    _score_error_handling,
    _score_style_consistency,
    _score_scientific_accuracy,
    _score_parameter_coverage,
    _score_no_redundancy,
]

_RUBRIC_DIMENSIONS = {
    "r-trigger-clarity": "Outcome",
    "r-instruction-completeness": "Process",
    "r-example-quality": "Process",
    "r-error-handling": "Process",
    "r-style-consistency": "Style",
    "r-scientific-accuracy": "Style",
    "r-parameter-coverage": "Efficiency",
    "r-no-redundancy": "Efficiency",
}


def auto_score_rubric(skill_name: str) -> Dict:
    """
    Automatically score all rubric items for a skill using heuristic analysis.
    Returns a rubric result dict compatible with compute_score() and generate_report().
    """
    md_text = _read_skill_md(skill_name)
    if not md_text:
        return {
            "overall_pass": False,
            "score": 0,
            "checks": [{"id": "skill-md-missing", "pass": False, "score": 1,
                         "notes": f"SKILL.md not found for {skill_name}"}]
        }

    checks = []
    for scorer in _RUBRIC_SCORERS:
        checks.append(scorer(md_text))

    scores = [c["score"] for c in checks]
    avg = sum(scores) / len(scores) if scores else 0
    all_pass = all(c["pass"] for c in checks)

    # Compute a raw score (rubric is 50% of total)
    rubric_pct = (avg / 5) * 50
    det_results = run_all_deterministic_checks(skill_name)
    det_pct = (det_results["summary"]["passed"] / max(det_results["summary"]["total"], 1)) * 50
    total = round(det_pct + rubric_pct, 1)

    return {
        "overall_pass": all_pass and total >= 70,
        "score": int(total),
        "checks": checks,
        "rubric_average": round(avg, 2),
        "dimension_breakdown": _compute_dimension_breakdown(checks)
    }


def _compute_dimension_breakdown(checks: List[Dict]) -> Dict:
    """Compute per-dimension rubric breakdown."""
    dimensions = {}
    for c in checks:
        dim = _RUBRIC_DIMENSIONS.get(c["id"], "Unknown")
        if dim not in dimensions:
            dimensions[dim] = {"scores": [], "checks": []}
        dimensions[dim]["scores"].append(c["score"])
        dimensions[dim]["checks"].append(c["id"])

    breakdown = {}
    for dim, data in dimensions.items():
        avg = sum(data["scores"]) / len(data["scores"]) if data["scores"] else 0
        breakdown[dim] = {
            "average": round(avg, 2),
            "checks": data["checks"],
            "status": "Strong" if avg >= 4 else ("Adequate" if avg >= 3 else "Weak")
        }
    return breakdown


def run_rubric_auto_grading(skill_name: str) -> Dict:
    """
    Full rubric auto-grading entry point.
    Runs deterministic checks + auto rubric scoring, returns combined results.
    """
    det_results = run_all_deterministic_checks(skill_name)
    rubric = auto_score_rubric(skill_name)
    score = compute_score(det_results, rubric)

    return {
        "skill_name": skill_name,
        "deterministic": det_results,
        "rubric": rubric,
        "score": score,
        "dimension_breakdown": rubric.get("dimension_breakdown", {})
    }


# ── Bilingual Prompt Generation ──────────────────────────────────────────

_GEOSCIENCE_DOMAINS = {
    "terrain": {"en": ["DEM", "slope", "aspect", "hillshade", "terrain analysis", "elevation"],
                "cn": ["DEM", "坡度", "坡向", "山体阴影", "地形分析", "高程"]},
    "kriging": {"en": ["kriging", "interpolation", "spatial interpolation", "variogram", "semivariogram"],
                "cn": ["克里金", "插值", "空间插值", "变异函数", "半变异函数"]},
    "remote_sensing": {"en": ["remote sensing", "classification", "NDVI", "satellite", " Landsat", "Sentinel"],
                       "cn": ["遥感", "分类", "归一化植被指数", "卫星", "哨兵"]},
    "geology": {"en": ["geological", "stratigraphy", "fault", "fold", "structure"],
                "cn": ["地质", "地层", "断层", "褶皱", "构造"]},
    "geophysics": {"en": ["seismic", "gravity", "magnetic", "resistivity", "geophysical"],
                   "cn": ["地震", "重力", "磁法", "电阻率", "地球物理"]},
    "hydrology": {"en": ["watershed", "runoff", "flood", "hydrology", "drainage"],
                  "cn": ["流域", "径流", "洪水", "水文", "排水"]},
    "geochemistry": {"en": ["geochemistry", "anomaly", "element", "geochemical", "mineral"],
                     "cn": ["地球化学", "异常", "元素", "地球化学", "矿物"]},
    "general_geo": {"en": ["GIS", "spatial", "geospatial", "coordinate", "projection", "raster", "vector"],
                    "cn": ["GIS", "空间", "地理空间", "坐标", "投影", "栅格", "矢量"]},
}

_PROMPT_TEMPLATES_EN = {
    "explicit": [
        "Use the ${name} skill to ${action}",
        "Run ${name} with the standard workflow",
        "Apply ${name} to process ${data_type} data",
    ],
    "implicit": [
        "I need to ${action} for my geoscience project",
        "Can you help me ${action}? I have ${data_type} data ready",
        "Please ${action} using the best available method",
    ],
    "contextual": [
        "I'm doing a ${domain} study and need to ${action}. My data is in ${data_type} format.",
        "For my research on ${domain}, I want to compare different approaches to ${action}.",
        "I'm preparing a report on ${domain} and need ${action} as part of the analysis pipeline.",
    ],
    "negative": [
        "I just want to read about ${domain} theory, not run any tools",
        "Help me format my bibliography for a ${domain} paper",
        "What's the history of ${domain} as a scientific discipline?",
    ],
    "edge-case": [
        "Use ${name} but my input file might have missing values",
        "I want to run ${name} but I'm not sure about the coordinate system of my data",
        "Can ${name} handle very large datasets (>10GB)?",
    ],
}

_PROMPT_TEMPLATES_CN = {
    "explicit": [
        "使用 ${name} 技能来完成 ${action_cn}",
        "运行 ${name} 标准工作流",
        "调用 ${name} 处理 ${data_type_cn} 数据",
    ],
    "implicit": [
        "我需要对地学项目数据进行 ${action_cn}",
        "帮我 ${action_cn}，数据已经准备好了",
        "请用最合适的方法完成 ${action_cn}",
    ],
    "contextual": [
        "我在做 ${domain_cn} 研究，需要进行 ${action_cn}，数据格式是 ${data_type_cn}。",
        "关于 ${domain_cn} 的研究，我想对比不同 ${action_cn} 方法的优缺点。",
        "我正在准备 ${domain_cn} 报告，${action_cn} 是分析流程的一部分。",
    ],
    "negative": [
        "我只想了解 ${domain_cn} 的理论知识，不需要运行任何工具",
        "帮我整理 ${domain_cn} 论文的参考文献格式",
        "${domain_cn} 作为学科的发展历史是什么？",
    ],
    "edge-case": [
        "使用 ${name} 但我的输入数据可能有缺失值",
        "我想运行 ${name} 但不确定数据的坐标系",
        "${name} 能处理超大数据集（>10GB）吗？",
    ],
}


def _detect_domain(md_text: str) -> str:
    """Detect the geoscience domain from skill content."""
    domain_scores = {}
    desc = md_text[:2000].lower()
    for domain, vocab in _GEOSCIENCE_DOMAINS.items():
        score = sum(1 for term in vocab["en"] if term.lower() in desc)
        score += sum(1 for term in vocab["cn"] if term in desc)
        domain_scores[domain] = score
    best = max(domain_scores, key=domain_scores.get)
    return best if domain_scores[best] > 0 else "general_geo"


def _extract_action_words(md_text: str) -> Tuple[str, str]:
    """Extract action words from skill description. Returns (en_action, cn_action)."""
    fm = parse_frontmatter(md_text)
    desc = fm.get('description', '').lower()

    en_action_map = {
        'analyze': 'analyze', 'analyse': 'analyze', '分析': 'analyze',
        'interpolate': 'interpolate', '插值': 'interpolate',
        'classify': 'classify', '分类': 'classify',
        'detect': 'detect', '检测': 'detect',
        'extract': 'extract', '提取': 'extract',
        'monitor': 'monitor', '监测': 'monitor',
        'simulate': 'simulate', '模拟': 'simulate',
        'assess': 'assess', '评估': 'assess',
        'process': 'process', '处理': 'process',
        'generate': 'generate', '生成': 'generate',
        'convert': 'convert', '转换': 'convert',
        'visualize': 'visualize', '可视化': 'visualize',
        'model': 'model', '建模': 'model',
        'estimate': 'estimate', '估算': 'estimate',
        'forecast': 'forecast', '预测': 'forecast',
        'calculate': 'calculate', '计算': 'calculate',
        'load': 'load', '加载': 'load',
    }

    cn_action_map = {
        'analyze': '分析', 'interpolate': '插值', 'classify': '分类',
        'detect': '检测', 'extract': '提取', 'monitor': '监测',
        'simulate': '模拟', 'assess': '评估', 'process': '处理',
        'generate': '生成', 'convert': '转换', 'visualize': '可视化',
        'model': '建模', 'estimate': '估算', 'forecast': '预测',
    }

    for en_word, action in en_action_map.items():
        if en_word in desc:
            return (action, cn_action_map.get(action, action))

    return ("process", "处理")


def _extract_data_types(md_text: str) -> Tuple[str, str]:
    """Extract data type references. Returns (en_type, cn_type)."""
    types_en = {
        'GeoTIFF': '栅格 GeoTIFF', 'geotiff': '栅格 GeoTIFF',
        'shapefile': '矢量 Shapefile', 'shp': '矢量 Shapefile',
        'NetCDF': 'NetCDF 格点', 'netcdf': 'NetCDF 格点',
        'CSV': 'CSV 表格', 'csv': 'CSV 表格',
        'GeoJSON': 'GeoJSON 矢量', 'geojson': 'GeoJSON 矢量',
        'raster': '栅格', 'vector': '矢量',
        'point': '点数据', 'DEM': 'DEM 高程',
    }
    for ext, cn in types_en.items():
        if ext.lower() in md_text[:3000].lower():
            return (ext, cn)
    return ("geospatial", "地理空间")


def generate_bilingual_prompts(skill_name: str, md_text: str = None) -> List[Dict]:
    """
    Generate bilingual (EN/CN) eval prompts for a skill.
    Auto-detects language preference and generates prompts in both languages.
    Returns list of prompt dicts with a 'language' field.
    """
    if md_text is None:
        md_text = _read_skill_md(skill_name)
    if not md_text:
        return []

    fm = parse_frontmatter(md_text)
    name = fm.get('name', skill_name)
    has_cn = _has_cjk(md_text)
    domain = _detect_domain(md_text)
    en_action, cn_action = _extract_action_words(md_text)
    en_data, cn_data = _extract_data_types(md_text)

    domain_vocab = _GEOSCIENCE_DOMAINS.get(domain, _GEOSCIENCE_DOMAINS["general_geo"])
    domain_en = domain_vocab["en"][0] if domain_vocab["en"] else "geoscience"
    domain_cn = domain_vocab["cn"][0] if domain_vocab["cn"] else "地学"

    prompts = []
    prompt_id = 0

    # Determine which languages to generate
    languages = ["en", "cn"] if has_cn else ["en"]

    for lang in languages:
        templates = _PROMPT_TEMPLATES_EN if lang == "en" else _PROMPT_TEMPLATES_CN

        # Explicit (2)
        for tmpl in templates["explicit"][:2]:
            prompt_id += 1
            text = tmpl.replace("${name}", name) \
                       .replace("${action}", en_action if lang == "en" else cn_action) \
                       .replace("${action_cn}", cn_action) \
                       .replace("${data_type}", en_data if lang == "en" else cn_data) \
                       .replace("${data_type_cn}", cn_data)
            prompts.append({
                "id": f"{skill_name}-{prompt_id:02d}",
                "should_trigger": True,
                "category": "explicit",
                "language": lang,
                "prompt": text,
                "expected_behavior": f"Should invoke {name} and follow documented steps ({lang.upper()})"
            })

        # Implicit (2)
        for tmpl in templates["implicit"][:2]:
            prompt_id += 1
            text = tmpl.replace("${action}", en_action if lang == "en" else cn_action) \
                       .replace("${action_cn}", cn_action) \
                       .replace("${data_type}", en_data if lang == "en" else cn_data) \
                       .replace("${data_type_cn}", cn_data) \
                       .replace("${domain}", domain_en) \
                       .replace("${domain_cn}", domain_cn)
            prompts.append({
                "id": f"{skill_name}-{prompt_id:02d}",
                "should_trigger": True,
                "category": "implicit",
                "language": lang,
                "prompt": text,
                "expected_behavior": f"Should trigger {name} from implicit description ({lang.upper()})"
            })

        # Contextual (1)
        prompt_id += 1
        tmpl = templates["contextual"][0]
        text = tmpl.replace("${domain}", domain_en if lang == "en" else domain_cn) \
                   .replace("${domain_cn}", domain_cn) \
                   .replace("${action}", en_action if lang == "en" else cn_action) \
                   .replace("${action_cn}", cn_action) \
                   .replace("${data_type}", en_data if lang == "en" else cn_data) \
                   .replace("${data_type_cn}", cn_data)
        prompts.append({
            "id": f"{skill_name}-{prompt_id:02d}",
            "should_trigger": True,
            "category": "contextual",
            "language": lang,
            "prompt": text,
            "expected_behavior": f"Should trigger {name} in realistic project context ({lang.upper()})"
        })

        # Negative (2)
        for tmpl in templates["negative"][:2]:
            prompt_id += 1
            text = tmpl.replace("${domain}", domain_en if lang == "en" else domain_cn) \
                       .replace("${domain_cn}", domain_cn) \
                       .replace("${name}", name)
            prompts.append({
                "id": f"{skill_name}-{prompt_id:02d}",
                "should_trigger": False,
                "category": "negative",
                "language": lang,
                "prompt": text,
                "expected_behavior": f"Should NOT trigger {name} ({lang.upper()})"
            })

        # Edge-case (1)
        prompt_id += 1
        tmpl = templates["edge-case"][0]
        text = tmpl.replace("${name}", name) \
                   .replace("${action}", en_action if lang == "en" else cn_action) \
                   .replace("${action_cn}", cn_action)
        prompts.append({
            "id": f"{skill_name}-{prompt_id:02d}",
            "should_trigger": True,
            "category": "edge-case",
            "language": lang,
            "prompt": text,
            "expected_behavior": f"Should trigger {name} and handle edge case gracefully ({lang.upper()})"
        })

    return prompts


def save_bilingual_prompts_csv(prompts: List[Dict], output_path: str):
    """Save bilingual prompts to CSV with language column."""
    import csv
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        fieldnames = ['id', 'should_trigger', 'category', 'language', 'prompt', 'expected_behavior']
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for prompt in prompts:
            writer.writerow(prompt)


# ── Skill Comparison Mode ─────────────────────────────────────────────────

def _parse_eval_report(report_path: str) -> Optional[Dict]:
    """Parse an evaluation report Markdown file into a structured dict."""
    if not os.path.isfile(report_path):
        return None
    with open(report_path, 'r', encoding='utf-8') as f:
        content = f.read()

    result = {
        "file": report_path,
        "skill_name": "",
        "total_score": None,
        "grade": None,
        "verdict": None,
        "deterministic_checks": {},
        "rubric_checks": {},
        "tool_names": [],
        "findings": {"critical": [], "warnings": []},
    }

    # Extract skill name from title
    title_match = re.search(r'# Skill Evaluation Report:\s*(.+)', content)
    if title_match:
        result["skill_name"] = title_match.group(1).strip()

    # Extract total score
    score_match = re.search(r'\*\*(\d+(?:\.\d+)?)/100\*\*', content)
    if score_match:
        result["total_score"] = float(score_match.group(1))

    # Extract grade and verdict
    grade_match = re.search(r'\*\*Grade:\*\*\s*([A-F])\s*\|\s*\*\*Verdict:\*\*\s*(.+)', content)
    if grade_match:
        result["grade"] = grade_match.group(1)
        result["verdict"] = grade_match.group(2).strip()

    # Parse deterministic check table
    det_section = re.search(
        r'## Deterministic Checks\s*\n.*?\n\|\s*Check\s*\|.*?\n.*?\n([\s\S]*?)(?=\n\*\*Deterministic|\n##)',
        content, re.MULTILINE)
    if det_section:
        for line in det_section.group(1).strip().split('\n'):
            row = re.findall(r'\|\s*([^|]+)\s*\|', line)
            if len(row) >= 3:
                check_id = row[0].strip()
                status = row[1].strip()
                details = row[2].strip()
                result["deterministic_checks"][check_id] = {
                    "pass": status == "PASS",
                    "details": details
                }

    # Parse rubric table
    rubric_section = re.search(
        r'## Rubric Grading\s*\n.*?\n\|\s*Check\s*\|.*?\n.*?\n([\s\S]*?)(?=\n##|\n---)',
        content, re.MULTILINE)
    if rubric_section:
        for line in rubric_section.group(1).strip().split('\n'):
            row = re.findall(r'\|\s*([^|]+)\s*\|', line)
            if len(row) >= 3:
                check_id = row[0].strip()
                score_match_r = re.search(r'(\d+)/5', row[1])
                result["rubric_checks"][check_id] = {
                    "score": int(score_match_r.group(1)) if score_match_r else None,
                    "pass": row[2].strip() == "PASS"
                }

    # Parse findings
    critical_section = re.search(r'### Critical Issues\s*\n([\s\S]*?)(?=\n###|\n##|\n---)', content)
    if critical_section:
        result["findings"]["critical"] = re.findall(r'-\s*\*\*(.+?)\*\*', critical_section.group(1))

    warning_section = re.search(r'### Warnings\s*\n([\s\S]*?)(?=\n###|\n##|\n---)', content)
    if warning_section:
        result["findings"]["warnings"] = re.findall(r'-\s*\*\*(.+?)\*\*', warning_section.group(1))

    # Parse tool names
    tool_section = re.search(r'## Detected Tool Names\s*\n([\s\S]*?)(?=\n##|\n---)', content)
    if tool_section:
        result["tool_names"] = re.findall(r'-\s*`(.+?)`', tool_section.group(1))

    return result


def compare_evaluations(before_path: str, after_path: str,
                        output_dir: str = "evals/artifacts") -> Dict:
    """
    Compare two evaluation reports (before/after) and generate a comparison report.

    Parameters:
        before_path: Path to the 'before' evaluation report
        after_path: Path to the 'after' evaluation report
        output_dir: Directory to save the comparison report

    Returns:
        Dict with comparison results and report_path
    """
    from datetime import datetime

    before = _parse_eval_report(before_path)
    after = _parse_eval_report(after_path)

    if not before:
        return {"error": f"Could not parse 'before' report: {before_path}"}
    if not after:
        return {"error": f"Could not parse 'after' report: {after_path}"}

    skill_name = after.get("skill_name") or before.get("skill_name") or "unknown"

    # Score comparison
    score_delta = None
    if before["total_score"] is not None and after["total_score"] is not None:
        score_delta = round(after["total_score"] - before["total_score"], 1)

    # Grade comparison
    grade_delta = None
    grade_order = {"A": 5, "B": 4, "C": 3, "D": 2, "F": 1}
    if before["grade"] and after["grade"]:
        grade_delta = grade_order.get(after["grade"], 0) - grade_order.get(before["grade"], 0)

    # Check-level comparison
    all_check_ids = set(before["deterministic_checks"].keys()) | set(after["deterministic_checks"].keys())
    new_passes = []
    new_failures = []
    unchanged_pass = []
    unchanged_fail = []

    for cid in sorted(all_check_ids):
        b = before["deterministic_checks"].get(cid, {})
        a = after["deterministic_checks"].get(cid, {})
        b_pass = b.get("pass", False)
        a_pass = a.get("pass", False)

        if a_pass and not b_pass:
            new_passes.append(cid)
        elif not a_pass and b_pass:
            new_failures.append(cid)
        elif a_pass and b_pass:
            unchanged_pass.append(cid)
        else:
            unchanged_fail.append(cid)

    # Rubric comparison
    rubric_improvements = []
    rubric_regressions = []
    rubric_unchanged = []
    all_rubric_ids = set(before["rubric_checks"].keys()) | set(after["rubric_checks"].keys())
    for rid in sorted(all_rubric_ids):
        b_score = before["rubric_checks"].get(rid, {}).get("score") or 0
        a_score = after["rubric_checks"].get(rid, {}).get("score") or 0
        delta = a_score - b_score
        if delta > 0:
            rubric_improvements.append((rid, b_score, a_score, delta))
        elif delta < 0:
            rubric_regressions.append((rid, b_score, a_score, delta))
        else:
            rubric_unchanged.append((rid, a_score))

    # Verdict
    has_regression = len(new_failures) > 0 or len(rubric_regressions) > 0
    has_improvement = len(new_passes) > 0 or len(rubric_improvements) > 0
    overall_verdict = "IMPROVED" if (score_delta or 0) > 0 else (
        "REGRESSED" if (score_delta or 0) < 0 else "UNCHANGED")

    # Build comparison result
    comparison = {
        "skill_name": skill_name,
        "before": {"file": before_path, "score": before["total_score"], "grade": before["grade"],
                    "verdict": before["verdict"]},
        "after": {"file": after_path, "score": after["total_score"], "grade": after["grade"],
                   "verdict": after["verdict"]},
        "score_delta": score_delta,
        "grade_delta": grade_delta,
        "deterministic": {
            "new_passes": new_passes,
            "new_failures": new_failures,
            "unchanged_pass": unchanged_pass,
            "unchanged_fail": unchanged_fail,
        },
        "rubric": {
            "improvements": rubric_improvements,
            "regressions": rubric_regressions,
            "unchanged": rubric_unchanged,
        },
        "overall_verdict": overall_verdict,
        "has_regression": has_regression,
        "has_improvement": has_improvement,
    }

    # Generate report
    lines = [
        f"# Skill Comparison Report: {skill_name}",
        "",
        f"**Date:** {datetime.now().isoformat()}",
        f"**Before:** {before_path}",
        f"**After:** {after_path}",
        "",
        "## Score Comparison",
        "",
        "| Metric | Before | After | Delta |",
        "|--------|--------|-------|-------|",
        f"| Total Score | {before['total_score'] or 'N/A'} | {after['total_score'] or 'N/A'} | {(f'{score_delta:+.1f}') if score_delta is not None else 'N/A'} |",
        f"| Grade | {before['grade'] or 'N/A'} | {after['grade'] or 'N/A'} | {'↑' if (grade_delta or 0) > 0 else '↓' if (grade_delta or 0) < 0 else '→'} |",
        f"| Verdict | {before['verdict'] or 'N/A'} | {after['verdict'] or 'N/A'} | |",
        "",
        f"**Overall: {overall_verdict}**",
        "",
        "## Deterministic Check Changes",
        "",
    ]

    if new_passes:
        lines.append("### Fixed Issues (now PASS)")
        for cid in new_passes:
            lines.append(f"- **{cid}**: FAIL → PASS ✓")
        lines.append("")

    if new_failures:
        lines.append("### Regressions (now FAIL)")
        for cid in new_failures:
            lines.append(f"- **{cid}**: PASS → FAIL ✗")
        lines.append("")

    if unchanged_pass:
        lines.append(f"### Still Passing ({len(unchanged_pass)} checks)")
        lines.append(", ".join(unchanged_pass[:10]))
        lines.append("")

    if unchanged_fail:
        lines.append(f"### Still Failing ({len(unchanged_fail)} checks)")
        for cid in unchanged_fail:
            lines.append(f"- {cid}")
        lines.append("")

    if rubric_improvements or rubric_regressions:
        lines.append("## Rubric Score Changes")
        lines.append("")
        lines.append("| Rubric Item | Before | After | Delta |")
        lines.append("|-------------|--------|-------|-------|")
        for rid, b_s, a_s, d in rubric_improvements + rubric_regressions:
            lines.append(f"| {rid} | {b_s}/5 | {a_s}/5 | {d:+d} |")
        for rid, s in rubric_unchanged:
            lines.append(f"| {rid} | {s}/5 | {s}/5 | 0 |")
        lines.append("")

    # Summary
    lines.extend([
        "## Summary",
        "",
        f"- **Score change:** {score_delta:+.1f}" if score_delta is not None else "- Score: N/A",
        f"- **Fixed issues:** {len(new_passes)}",
        f"- **New regressions:** {len(new_failures)}",
        f"- **Rubric improvements:** {len(rubric_improvements)}",
        f"- **Rubric regressions:** {len(rubric_regressions)}",
    ])

    if new_failures:
        lines.extend(["", "## Action Required"])
        for cid in new_failures:
            lines.append(f"- [ ] Investigate regression: **{cid}**")

    lines.extend(["", "---", f"*Generated by skill-evaluator v2 on {datetime.now().isoformat()}*"])

    # Save
    os.makedirs(output_dir, exist_ok=True)
    report_path = os.path.join(output_dir, f"{skill_name}-comparison-report.md")
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write("\n".join(lines))

    comparison["report_path"] = report_path
    return comparison


# ── Enhanced Batch Summary v2 ─────────────────────────────────────────────

def _score_histogram(scores: List[float]) -> str:
    """Generate a text-based score distribution histogram."""
    bins = [(0, 20, "0-19"), (20, 40, "20-39"), (40, 60, "40-59"),
            (60, 70, "60-69"), (70, 80, "70-79"), (80, 90, "80-89"), (90, 101, "90-100")]
    lines = []
    for low, high, label in bins:
        count = sum(1 for s in scores if low <= s < high)
        bar = "█" * count + "░" * max(0, 10 - count)
        lines.append(f"  {label:>6} │{bar}│ {count}")
    return "\n".join(lines)


def _categorize_skill(skill_name: str) -> str:
    """Categorize a skill into a geoscience domain."""
    name_lower = skill_name.lower()
    categories = {
        "Remote Sensing": ["rs-", "remote-sensing", "satellite", "ndvi", "classification", "segmentation",
                           "super-resolution", "cloud-removal", "object-detection", "scene-classification",
                           "ship-detection", "wildfire-detection", "image-restoration", "building-extraction",
                           "road-extraction", "water-segmentation", "crop-", "forest-change",
                           "landslide-mining", "wildfire-monitoring"],
        "Geology & Structure": ["geological", "structural", "fold", "fault", "stereonet",
                                "cross-section", "geological-map", "3d-modeling",
                                "implicit-3d"],
        "Geophysics": ["geophysic", "seismic", "gravity", "magnetic", "resistivity",
                       "forward-modeling", "inversion", "beachball", "focal-mechanism",
                       "interpretation"],
        "Geochemistry": ["geochem", "anomaly", "ree-pattern", "mineral-prospectivity",
                         "multivariate-statistics", "geochemical"],
        "Hydrology & Climate": ["hydrology", "flood", "watershed", "rainfall", "runoff",
                                "drought", "evapotranspiration", "water-resource",
                                "ctd-oceanographic", "sea-surface", "groundwater"],
        "Terrain & Spatial": ["terrain", "kriging", "interpolation", "spatial-autocorrelation",
                              "buffer", "distance", "geocoding", "spatial-query",
                              "geospatial-data-quality", "geospatial-format"],
        "Environmental": ["ecological", "carbon-cycle", "vegetation", "soil-contamination",
                          "land-use", "land-surface-temperature", "urban-heat",
                          "multi-factor-environmental", "multi-hazard-risk",
                          "landslide-susceptibility", "air-quality"],
        "Resource & Mining": ["resource-estimation", "exploration-target", "borehole",
                              "block-model", "grade-interpolation", "drill-sample",
                              "well-log", "rock-classification", "thermobarometry",
                              "load-remote-sensing"],
        "Data & Tools": ["stac-data", "geovisualization", "thematic-map", "cartography",
                         "model-uncertainty"],
    }
    for category, keywords in categories.items():
        if any(kw in name_lower for kw in keywords):
            return category
    return "Other"


def generate_enhanced_batch_summary(results: List[Dict], output_dir: str = "evals/artifacts"):
    """
    Generate an enhanced batch evaluation summary with detailed statistics,
    dimension breakdown, histogram, category grouping, and actionable recommendations.
    """
    from datetime import datetime

    if not results:
        print("No results to summarize.")
        return

    os.makedirs(output_dir, exist_ok=True)
    scores = [r["score"]["total_score"] for r in results]
    avg_score = round(sum(scores) / len(scores), 1) if scores else 0
    median_score = round(sorted(scores)[len(scores) // 2], 1) if scores else 0
    min_score = round(min(scores), 1) if scores else 0
    max_score = round(max(scores), 1) if scores else 0
    std_score = round((sum((s - avg_score) ** 2 for s in scores) / max(len(scores), 1)) ** 0.5, 1)

    lines = [
        "# Enhanced Batch Evaluation Summary (v2)",
        "",
        f"**Date:** {datetime.now().isoformat()}",
        f"**Skills evaluated:** {len(results)}",
        f"**Evaluator:** skill-evaluator v2",
        "",
        "## Overall Statistics",
        "",
        "| Metric | Value |",
        "|--------|-------|",
        f"| Mean Score | {avg_score}/100 |",
        f"| Median Score | {median_score}/100 |",
        f"| Std Deviation | {std_score} |",
        f"| Min Score | {min_score}/100 |",
        f"| Max Score | {max_score}/100 |",
        f"| Pass Rate (>=70) | {sum(1 for s in scores if s >= 70)}/{len(scores)} ({sum(1 for s in scores if s >= 70)/max(len(scores),1)*100:.0f}%) |",
        f"| Fail Rate (<60) | {sum(1 for s in scores if s < 60)}/{len(scores)} ({sum(1 for s in scores if s < 60)/max(len(scores),1)*100:.0f}%) |",
        "",
        "## Score Distribution",
        "",
        _score_histogram(scores),
        "",
        "## Grade Distribution",
        "",
        "| Grade | Count | Percentage | Skills |",
        "|-------|-------|------------|--------|",
    ]

    grade_counts = {"A": [], "B": [], "C": [], "D": [], "F": []}
    for r in results:
        grade_counts[r["score"]["grade"]].append(r)

    for grade in ["A", "B", "C", "D", "F"]:
        skills = grade_counts[grade]
        pct = round(len(skills) / max(len(results), 1) * 100, 1)
        skill_names = ", ".join(s["skill_name"] for s in skills[:5])
        if len(skills) > 5:
            skill_names += f" (+{len(skills)-5} more)"
        lines.append(f"| {grade} | {len(skills)} | {pct}% | {skill_names or '—'} |")

    # Dimension breakdown (if rubric was used)
    has_rubric = any(r.get("rubric") or r.get("dimension_breakdown") for r in results)
    if has_rubric:
        lines.extend(["", "## Dimension Breakdown", "",
                       "| Dimension | Avg Score | Status | Typical Weakness |",
                       "|-----------|-----------|--------|------------------|"])
        dim_scores = {"Outcome": [], "Process": [], "Style": [], "Efficiency": []}
        for r in results:
            if "dimension_breakdown" in r:
                for dim, data in r["dimension_breakdown"].items():
                    if dim in dim_scores:
                        dim_scores[dim].append(data["average"])

        dim_status_map = {}
        for dim, vals in dim_scores.items():
            if vals:
                avg = round(sum(vals) / len(vals), 2)
                status = "Strong" if avg >= 4 else ("Adequate" if avg >= 3 else "Weak")
                dim_status_map[dim] = (avg, status)

        for dim in ["Outcome", "Process", "Style", "Efficiency"]:
            if dim in dim_status_map:
                avg, status = dim_status_map[dim]
                weakness = "" if status == "Strong" else f"Score {avg}/5"
                lines.append(f"| {dim} | {avg}/5 | {status} | {weakness} |")

    # Category grouping
    lines.extend(["", "## Category Analysis", "",
                   "| Category | Count | Avg Score | Pass Rate |",
                   "|----------|-------|-----------|-----------|"])
    cat_groups = {}
    for r in results:
        cat = _categorize_skill(r["skill_name"])
        if cat not in cat_groups:
            cat_groups[cat] = []
        cat_groups[cat].append(r)

    for cat in sorted(cat_groups.keys(), key=lambda c: -sum(r["score"]["total_score"] for r in cat_groups[c]) / max(len(cat_groups[c]), 1)):
        skills = cat_groups[cat]
        cat_avg = round(sum(r["score"]["total_score"] for r in skills) / len(skills), 1)
        cat_pass = sum(1 for r in skills if r["score"]["total_score"] >= 70)
        lines.append(f"| {cat} | {len(skills)} | {cat_avg}/100 | {cat_pass}/{len(skills)} |")

    # Common issues with severity
    lines.extend(["", "## Common Issues (Severity-Weighted)", ""])

    issue_severity = {
        "frontmatter-name": "CRITICAL", "frontmatter-desc": "CRITICAL", "skill-md-exists": "CRITICAL",
        "script-valid-python": "HIGH", "script-has-invoke": "HIGH",
        "has-instructions": "MEDIUM", "has-when-to-use": "MEDIUM", "step-numbering": "MEDIUM",
        "parameter-table": "MEDIUM", "has-examples": "LOW", "has-troubleshooting": "LOW",
        "desc-keywords": "LOW", "reference-exists": "LOW", "reference-nonempty": "LOW",
        "tool-names-valid": "MEDIUM",
    }

    issue_counts = {}
    for r in results:
        for c in r["deterministic"].get("checks", []):
            if not c["pass"]:
                cid = c["check_id"]
                if cid not in issue_counts:
                    issue_counts[cid] = {"count": 0, "skills": [], "severity": issue_severity.get(cid, "MEDIUM")}
                issue_counts[cid]["count"] += 1
                issue_counts[cid]["skills"].append(r["skill_name"])

    if issue_counts:
        lines.append("| Issue | Severity | Count | Affected Skills |")
        lines.append("|-------|----------|-------|-----------------|")
        severity_order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3, "INFO": 4}
        for cid, data in sorted(issue_counts.items(),
                                 key=lambda x: (severity_order.get(x[1]["severity"], 3), -x[1]["count"])):
            skills_str = ", ".join(data["skills"][:3])
            if len(data["skills"]) > 3:
                skills_str += f" (+{len(data['skills'])-3})"
            lines.append(f"| {cid} | {data['severity']} | {data['count']} | {skills_str} |")
    else:
        lines.append("No issues found across any skills.")

    # Improvement priority ranking
    lines.extend(["", "## Improvement Priority Ranking", ""])
    low_skills = sorted([r for r in results if r["score"]["total_score"] < 80],
                         key=lambda x: x["score"]["total_score"])
    if low_skills:
        lines.append("Skills sorted by urgency (lowest score first):")
        lines.append("")
        lines.append("| Priority | Skill | Score | Key Issues |")
        lines.append("|----------|-------|-------|------------|")
        for i, r in enumerate(low_skills[:20], 1):
            failed = [c["check_id"] for c in r["deterministic"].get("checks", []) if not c["pass"]]
            key_issues = ", ".join(failed[:3])
            if len(failed) > 3:
                key_issues += f" (+{len(failed)-3})"
            lines.append(f"| {i} | {r['skill_name']} | {r['score']['total_score']}/100 | {key_issues or 'All checks passed'} |")
    else:
        lines.append("All skills scored 80 or above. No urgent improvements needed.")

    # Top skills
    lines.extend(["", "## Top Performing Skills (score >= 90)", ""])
    top = sorted([r for r in results if r["score"]["total_score"] >= 90],
                  key=lambda x: -x["score"]["total_score"])
    if top:
        for r in top:
            lines.append(f"- **{r['skill_name']}** — {r['score']['total_score']}/100 ({r['score']['grade']})")
    else:
        lines.append("No skills scored 90 or above.")

    # Actionable recommendations
    lines.extend(["", "## Actionable Recommendations", ""])
    recs = []

    # Check for widespread issues
    critical_issues = {cid: data for cid, data in issue_counts.items() if data["severity"] == "CRITICAL"}
    if critical_issues:
        recs.append(f"1. **Fix {len(critical_issues)} critical issue(s)** affecting core skill structure")

    high_issues = {cid: data for cid, data in issue_counts.items() if data["severity"] == "HIGH"}
    if high_issues:
        total_affected = sum(data["count"] for data in high_issues.values())
        recs.append(f"2. **Address {len(high_issues)} high-severity issue(s)** across {total_affected} skill evaluations")

    missing_ts = [r["skill_name"] for r in results
                  if not any(c["pass"] for c in r["deterministic"].get("checks", [])
                             if c["check_id"] == "has-troubleshooting")]
    if missing_ts:
        recs.append(f"3. **Add Troubleshooting sections** to {len(missing_ts)} skills: {', '.join(missing_ts[:5])}")

    missing_examples = [r["skill_name"] for r in results
                        if not any(c["pass"] for c in r["deterministic"].get("checks", [])
                                   if c["check_id"] == "has-examples")]
    if missing_examples:
        recs.append(f"4. **Add Example sections** to {len(missing_examples)} skills: {', '.join(missing_examples[:5])}")

    if recs:
        lines.extend(recs)
    else:
        lines.append("All skills meet quality standards. Consider adding more edge-case testing.")

    lines.extend(["", "---", f"*Generated by skill-evaluator v2 on {datetime.now().isoformat()}*"])

    # Write
    summary_path = os.path.join(output_dir, "batch-eval-summary-v2.md")
    with open(summary_path, 'w', encoding='utf-8') as f:
        f.write("\n".join(lines))

    print(f"\nEnhanced batch summary written to: {summary_path}")
    return summary_path


# ── Upgraded Convenience Functions ────────────────────────────────────────

def evaluate_skill_v2(skill_name: str, output_dir: str = "evals/artifacts",
                      enable_rubric: bool = True,
                      bilingual: bool = True) -> Dict:
    """
    V2 full evaluation: deterministic checks + auto rubric scoring + bilingual prompts.
    Returns the full results and writes report + prompts to disk.
    """
    os.makedirs(output_dir, exist_ok=True)

    # Step 1: Deterministic checks
    det_results = run_all_deterministic_checks(skill_name)

    # Step 2: Auto rubric scoring (if enabled)
    rubric = None
    if enable_rubric:
        rubric = auto_score_rubric(skill_name)

    # Step 3: Compute combined score
    score = compute_score(det_results, rubric)

    # Step 4: Generate bilingual prompts (if enabled)
    prompts = []
    if bilingual:
        prompts = generate_bilingual_prompts(skill_name)
        if prompts:
            prompts_path = os.path.join(output_dir, f"{skill_name}-bilingual.prompts.csv")
            save_bilingual_prompts_csv(prompts, prompts_path)
    else:
        prompts = generate_eval_prompts(skill_name)
        if prompts:
            prompts_path = os.path.join(output_dir, f"{skill_name}.prompts.csv")
            save_prompts_csv(prompts, prompts_path)

    # Step 5: Generate report
    report = generate_report(skill_name, det_results, rubric, score)
    report_path = os.path.join(output_dir, f"{skill_name}-eval-report.md")
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(report)

    return {
        "skill_name": skill_name,
        "deterministic": det_results,
        "rubric": rubric,
        "prompts": prompts,
        "score": score,
        "dimension_breakdown": rubric.get("dimension_breakdown", {}) if rubric else {},
        "report_path": report_path
    }


def evaluate_all_skills_v2(output_dir: str = "evals/artifacts",
                           enable_rubric: bool = True,
                           bilingual: bool = True) -> List[Dict]:
    """
    V2 batch evaluation of all skills with enhanced summary.
    """
    results = []
    if not os.path.isdir(SKILLS_BASE_DIR):
        print(f"Skills directory not found: {SKILLS_BASE_DIR}")
        return results

    for entry in sorted(os.listdir(SKILLS_BASE_DIR)):
        skill_path = os.path.join(SKILLS_BASE_DIR, entry)
        if os.path.isdir(skill_path) and os.path.isfile(os.path.join(skill_path, "SKILL.md")):
            print(f"Evaluating: {entry}...")
            result = evaluate_skill_v2(entry, output_dir, enable_rubric, bilingual)
            results.append(result)
            s = result["score"]
            print(f"  Score: {s['total_score']}/100 ({s['grade']}) — {s['verdict']}"
                  + (f" | Rubric: {result.get('rubric', {}).get('rubric_average', 'N/A')}/5" if enable_rubric else ""))

    # Generate enhanced batch summary
    if results:
        generate_enhanced_batch_summary(results, output_dir)

    return results


def quick_stats_v2(results: List[Dict]):
    """Print an enhanced quick summary table for v2 batch results."""
    print(f"\n{'Skill':<35} {'Score':>6} {'Grade':>6} {'Det%':>5} {'Rubric':>7} {'Verdict':<18}")
    print("─" * 82)
    for r in sorted(results, key=lambda x: -x["score"]["total_score"]):
        s = r["score"]
        det_pct = s.get("deterministic_percent", 0)
        rub = f"{r['rubric']['rubric_average']}/5" if r.get("rubric") and r["rubric"].get("rubric_average") else "N/A"
        print(f"{r['skill_name']:<35} {s['total_score']:>5.1f} {s['grade']:>6} {det_pct:>4.0f}% {rub:>7} {s['verdict']:<18}")

    scores = [r["score"]["total_score"] for r in results]
    print("─" * 82)
    print(f"{'MEAN':<35} {sum(scores)/max(len(scores),1):>5.1f} {'':<6} {'':<5} {'':<7} Pass: {sum(1 for s in scores if s >= 70)}/{len(scores)}")


print("Skill Evaluator v2 loaded.")
print("  evaluate_skill_v2('<name>')  — full eval with auto-rubric + bilingual prompts")
print("  evaluate_all_skills_v2()     — batch eval with enhanced summary")
print("  compare_evaluations(before, after) — before/after comparison")
print("  auto_score_rubric('<name>')  — rubric auto-scoring only")
print("  generate_bilingual_prompts('<name>') — bilingual prompt generation")
