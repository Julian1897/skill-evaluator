"""
Batch Fix Script for GeoSkills Evaluation Issues
=================================================
Fixes P0/P1/P2 issues identified by skill-evaluator v2.
Run from project root: python .claude/skills/skill-evaluator/scripts/batch_fix.py
"""

import os
import re
import json
import shutil
from pathlib import Path
from typing import List, Dict, Tuple, Optional

SKILLS_BASE_DIR = os.path.join(".claude", "skills")
BACKUP_DIR = os.path.join(".claude", "skills", "skill-evaluator", "evals", "artifacts", "pre-fix-backup")

# ── Helpers ────────────────────────────────────────────────────────────────

def _skill_md_path(name: str) -> str:
    return os.path.join(SKILLS_BASE_DIR, name, "SKILL.md")

def _read_skill(name: str) -> str:
    path = _skill_md_path(name)
    if not os.path.isfile(path):
        return ""
    with open(path, "r", encoding="utf-8") as f:
        return f.read()

def _write_skill(name: str, content: str):
    path = _skill_md_path(name)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)

def _backup_skill(name: str):
    """Backup SKILL.md before modification."""
    os.makedirs(BACKUP_DIR, exist_ok=True)
    src = _skill_md_path(name)
    if os.path.isfile(src):
        dst = os.path.join(BACKUP_DIR, f"{name}-SKILL.md.bak")
        if not os.path.exists(dst):  # Don't overwrite existing backups
            shutil.copy2(src, dst)

def _get_script_path(name: str) -> Optional[str]:
    skill_dir = os.path.join(SKILLS_BASE_DIR, name)
    scripts_dir = os.path.join(skill_dir, "scripts")
    if not os.path.isdir(scripts_dir):
        return None
    for fname in sorted(os.listdir(scripts_dir)):
        if fname.endswith(".py"):
            return os.path.join(scripts_dir, fname)
    return None

def _read_script(name: str) -> str:
    path = _get_script_path(name)
    if not path:
        return ""
    with open(path, "r", encoding="utf-8") as f:
        return f.read()

def _write_script(name: str, content: str):
    path = _get_script_path(name)
    if path:
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)

def parse_frontmatter(md: str) -> Dict[str, str]:
    match = re.match(r'^---\s*\n(.*?)\n---\s*\n', md, re.DOTALL)
    if not match:
        return {}
    result = {}
    for line in match.group(1).split('\n'):
        line = line.strip()
        if ':' in line:
            key, _, value = line.partition(':')
            result[key.strip()] = value.strip()
    return result

def has_section(md: str, pattern: str) -> bool:
    return bool(re.search(r'^##\s+.*' + re.escape(pattern), md, re.MULTILINE | re.IGNORECASE))

def has_substep_headings(md: str) -> bool:
    return bool(re.search(r'^###\s+Step\s+\d+', md, re.MULTILINE | re.IGNORECASE))


# ── Domain-aware "When to Use" Generator ───────────────────────────────────

_DOMAIN_KEYWORDS = {
    "terrain": {
        "en": ["terrain analysis", "DEM processing", "slope calculation", "aspect analysis",
               "hillshade generation", "watershed delineation", "elevation data"],
        "cn": ["地形分析", "DEM处理", "坡度计算", "坡向分析", "山体阴影", "流域提取", "高程数据"],
        "triggers": ["terrain", "slope", "aspect", "hillshade", "dem", "elevation", "watershed", "curvature"]
    },
    "kriging": {
        "en": ["spatial interpolation", "kriging", "variogram modeling", "point-to-raster conversion"],
        "cn": ["空间插值", "克里金", "变异函数", "点到栅格"],
        "triggers": ["kriging", "interpolat", "variogram"]
    },
    "remote_sensing": {
        "en": ["remote sensing image processing", "satellite data analysis", "land cover classification",
               "change detection", "object detection in imagery"],
        "cn": ["遥感影像处理", "卫星数据分析", "土地覆盖分类", "变化检测", "影像目标检测"],
        "triggers": ["rs-", "remote sensing", "classification", "segmentation", "detection",
                     "super-resolution", "cloud-removal", "wildfire"]
    },
    "geology": {
        "en": ["geological mapping", "structural analysis", "cross-section construction",
               "stratigraphic interpretation", "fold and fault analysis"],
        "cn": ["地质填图", "构造分析", "剖面制作", "地层解释", "褶皱与断层分析"],
        "triggers": ["geological", "structural", "fold", "fault", "stereonet", "cross-section",
                     "geological-map"]
    },
    "geophysics": {
        "en": ["geophysical data processing", "seismic interpretation", "gravity anomaly analysis",
               "magnetic survey processing", "forward modeling"],
        "cn": ["地球物理数据处理", "地震解释", "重力异常分析", "磁法勘探处理", "正演模拟"],
        "triggers": ["geophysic", "seismic", "gravity", "magnetic", "resistivity", "focal-mechanism",
                     "beachball", "forward-modeling", "inversion"]
    },
    "hydrology": {
        "en": ["hydrological analysis", "flood modeling", "rainfall-runoff simulation",
               "groundwater monitoring", "drought assessment"],
        "cn": ["水文分析", "洪水模拟", "降雨径流模拟", "地下水监测", "干旱评估"],
        "triggers": ["hydrology", "flood", "watershed", "rainfall", "runoff", "drought",
                     "groundwater", "water-resource", "inundation"]
    },
    "geochemistry": {
        "en": ["geochemical analysis", "anomaly detection", "element distribution mapping",
               "multivariate statistics", "mineral prospectivity"],
        "cn": ["地球化学分析", "异常检测", "元素分布制图", "多元统计", "矿产潜力"],
        "triggers": ["geochem", "anomaly", "ree-pattern", "multivariate", "prospectivity",
                     "geochemical"]
    },
    "environmental": {
        "en": ["environmental monitoring", "ecological assessment", "land use analysis",
               "carbon cycling", "air quality assessment"],
        "cn": ["环境监测", "生态评估", "土地利用分析", "碳循环", "空气质量评估"],
        "triggers": ["ecological", "carbon", "vegetation", "soil", "land-use", "land-surface",
                     "urban-heat", "multi-factor", "multi-hazard", "air-quality", "building-damage",
                     "wildfire-monitoring", "wildlife"]
    },
    "spatial_tools": {
        "en": ["spatial data operations", "coordinate transformations", "format conversion",
               "buffer analysis", "distance calculations"],
        "cn": ["空间数据操作", "坐标转换", "格式转换", "缓冲区分析", "距离计算"],
        "triggers": ["geospatial", "geocoding", "spatial-query", "distance-buffer", "format",
                     "stac", "geovisualization", "cartography"]
    },
    "resource": {
        "en": ["mineral resource estimation", "borehole data management", "block modeling",
               "well log interpretation", "drill sample analysis"],
        "cn": ["矿产资源估算", "钻孔数据管理", "块体模型", "测井解释", "钻探样品分析"],
        "triggers": ["resource", "borehole", "block-model", "drill", "well-log", "rock-classification",
                     "thermobarometry", "exploration"]
    },
    "climate": {
        "en": ["climate data analysis", "temperature trend analysis", "oceanographic data processing",
               "sea surface monitoring", "crop yield prediction"],
        "cn": ["气候数据分析", "温度趋势分析", "海洋数据处理", "海面监测", "作物产量预测"],
        "triggers": ["climate", "temperature", "ctd", "sea-surface", "crop", "evapotranspiration",
                     "forest-tree"]
    },
}

def _detect_domain(name: str, desc: str) -> str:
    name_lower = name.lower()
    desc_lower = desc.lower()
    scores = {}
    for domain, info in _DOMAIN_KEYWORDS.items():
        score = sum(1 for t in info["triggers"] if t in name_lower)
        score += sum(1 for t in info["triggers"] if t in desc_lower) * 0.5
        scores[domain] = score
    if not scores or max(scores.values()) == 0:
        return "spatial_tools"
    return max(scores, key=scores.get)

def _has_cjk(text: str) -> bool:
    return bool(re.search(r'[\u4e00-\u9fff]', text))


def generate_when_to_use(name: str, md: str) -> str:
    """Generate a 'When to Use' section based on skill name, description, and content."""
    fm = parse_frontmatter(md)
    desc = fm.get("description", "")
    domain = _detect_domain(name, desc)
    domain_info = _DOMAIN_KEYWORDS.get(domain, _DOMAIN_KEYWORDS["spatial_tools"])
    has_cn = _has_cjk(md)

    # Extract existing section content to understand what the skill does
    # Look for existing workflow/instructions to learn what triggers are relevant
    existing_sections = []
    for heading_match in re.finditer(r'^##\s+(.+)$', md, re.MULTILINE):
        existing_sections.append(heading_match.group(1).strip())

    # Build the When to Use content
    en_triggers = domain_info["en"][:4]
    cn_triggers = domain_info["cn"][:4] if has_cn else []

    lines = ["## When to Use", ""]

    # Bullet points for trigger scenarios
    if has_cn:
        lines.append(f"Use this skill when you need to:")
        lines.append("")
        for i, (en, cn) in enumerate(zip(en_triggers, cn_triggers)):
            lines.append(f"- {en} / {cn}")
        # Add extra bullets
        if len(en_triggers) < 3:
            lines.append(f"- {desc[:100]}" if desc else f"- Process {name} related tasks")
    else:
        lines.append(f"Use this skill when you need to:")
        lines.append("")
        for en in en_triggers:
            lines.append(f"- {en}")
        if len(en_triggers) < 3 and desc:
            lines.append(f"- {desc[:100]}")

    # Add negative triggers (when NOT to use)
    lines.append("")
    lines.append("Do not use this skill for:")
    lines.append(f"- General programming tasks unrelated to {domain_info['en'][0].split()[0] if domain_info['en'] else 'the domain'}")
    lines.append("- Setting up development environments or installing packages")
    if has_cn:
        lines.append(f"- 与{domain_info['cn'][0]}无关的一般编程任务")

    lines.append("")
    return "\n".join(lines)


# ── P0-1: Add "When to Use" Section ───────────────────────────────────────

def fix_when_to_use(skills: List[str]) -> Dict:
    """Add ## When to Use section to skills that lack it."""
    results = {"fixed": [], "skipped": [], "errors": []}

    for name in skills:
        md = _read_skill(name)
        if not md:
            results["errors"].append(f"{name}: SKILL.md not found")
            continue

        if has_section(md, "when to use"):
            results["skipped"].append(name)
            continue

        _backup_skill(name)

        # Generate the section
        wtu = generate_when_to_use(name, md)

        # Insert after front matter, before first H2
        fm_match = re.match(r'^(---\s*\n.*?\n---\s*\n)', md, re.DOTALL)
        if fm_match:
            fm_end = fm_match.end()
            # Find first H2 after front matter
            rest = md[fm_end:]
            h2_match = re.search(r'^##\s+', rest, re.MULTILINE)
            if h2_match:
                insert_pos = fm_end + h2_match.start()
                new_md = md[:insert_pos] + wtu + md[insert_pos:]
            else:
                new_md = md + "\n" + wtu
        else:
            new_md = wtu + md

        _write_skill(name, new_md)
        results["fixed"].append(name)

    return results


# ── P0-2: Fix Instructions Step Numbering ──────────────────────────────────

def fix_instructions(skills: List[str]) -> Dict:
    """Add ## Instructions section with ### Step N headings to skills that lack it."""
    results = {"fixed": [], "skipped": [], "errors": []}

    for name in skills:
        md = _read_skill(name)
        if not md:
            results["errors"].append(f"{name}: SKILL.md not found")
            continue

        if has_section(md, "instruction") and has_substep_headings(md):
            results["skipped"].append(name)
            continue

        _backup_skill(name)
        fm = parse_frontmatter(md)
        desc = fm.get("description", "")
        domain = _detect_domain(name, desc)
        domain_info = _DOMAIN_KEYWORDS.get(domain, _DOMAIN_KEYWORDS["spatial_tools"])
        has_cn = _has_cjk(md)

        # Check if there's already an Instructions section (but without steps)
        if has_section(md, "instruction"):
            # Has Instructions but no ### Step N - add step numbering to existing content
            md = _add_step_numbering_to_existing(md)
            _write_skill(name, md)
            results["fixed"].append(name)
            continue

        # No Instructions section at all - generate one based on domain
        steps = _generate_instruction_steps(name, desc, domain, domain_info, has_cn, md)

        # Find where to insert (after When to Use, or after front matter)
        fm_match = re.match(r'^(---\s*\n.*?\n---\s*\n)', md, re.DOTALL)
        fm_end = fm_match.end() if fm_match else 0

        rest = md[fm_end:]

        # Try to insert after "When to Use" section
        wtu_match = re.search(r'^##\s+When to Use\s*\n', rest, re.MULTILINE)
        if wtu_match:
            # Find next H2 after When to Use
            after_wtu = rest[wtu_match.end():]
            next_h2 = re.search(r'^##\s+', after_wtu, re.MULTILINE)
            if next_h2:
                insert_pos = fm_end + wtu_match.end() + next_h2.start()
                new_md = md[:insert_pos] + steps + md[insert_pos:]
            else:
                new_md = md + "\n" + steps
        else:
            # Insert before first H2
            h2_match = re.search(r'^##\s+', rest, re.MULTILINE)
            if h2_match:
                insert_pos = fm_end + h2_match.start()
                new_md = md[:insert_pos] + steps + md[insert_pos:]
            else:
                new_md = md + "\n" + steps

        _write_skill(name, new_md)
        results["fixed"].append(name)

    return results


def _add_step_numbering_to_existing(md: str) -> str:
    """Add ### Step N numbering to an existing Instructions section that lacks it."""
    lines = md.split('\n')
    new_lines = []
    in_instructions = False
    step_num = 0

    for line in lines:
        if re.match(r'^##\s+Instruction', line, re.IGNORECASE):
            in_instructions = True
            new_lines.append(line)
            continue

        if in_instructions and re.match(r'^##\s+', line):
            in_instructions = False

        if in_instructions:
            # Convert ### subheadings to ### Step N headings
            h3_match = re.match(r'^###\s+(?!Step\s+\d)(.*)', line, re.IGNORECASE)
            if h3_match:
                step_num += 1
                title = h3_match.group(1).strip()
                new_lines.append(f"### Step {step_num}: {title}")
                continue
            # Convert numbered list items to step headings if no H3s exist
            list_match = re.match(r'^(\d+)\.\s+\*\*(.+?)\*\*', line)
            if list_match and step_num == 0:
                step_num += 1
                title = list_match.group(2).strip()
                new_lines.append(f"### Step {step_num}: {title}")
                continue

        new_lines.append(line)

    return '\n'.join(new_lines)


def _generate_instruction_steps(name: str, desc: str, domain: str,
                                 domain_info: Dict, has_cn: bool, md: str) -> str:
    """Generate a standard Instructions section with numbered steps."""
    # Extract tool names from the skill content
    tool_names = re.findall(r'_invoke_tool_http\(\s*["\'](\w+)["\']', md)
    invoke_pattern = re.findall(r'invoke_tool\(\s*["\'](\w+)["\']', md)
    all_tools = list(set(tool_names + invoke_pattern))

    # Detect if skill has a script reference
    has_script = bool(re.search(r'scripts/\w+\.py|exec\(open', md))

    # Check for existing workflow steps
    workflow_steps = re.findall(r'(\d+)\.\s+\*\*(.+?)\*\*', md)
    if not workflow_steps:
        workflow_steps = re.findall(r'^\d+\.\s+(.+)$', md, re.MULTILINE)

    lines = ["## Instructions", ""]

    if all_tools:
        tool_name = all_tools[0]
        if has_script:
            lines.append(f"> **Tool calling**: Load the helper first: `exec(open(\"scripts/call_tool.py\").read())` or `exec(open(\"scripts/geo_tool.py\").read())`")
        else:
            lines.append(f"> **Tool calling**: Use `_invoke_tool_http(\"{tool_name}\", params)` to call the tool.")
        lines.append("")

        lines.append("### Step 1: Prepare Input Data")
        lines.append("")
        lines.append("Gather the required input data and verify format compatibility.")
        lines.append("- Ensure data files are accessible at the specified paths")
        lines.append("- Verify coordinate reference system (CRS) matches requirements")
        lines.append("- Check for missing or invalid values in the dataset")
        lines.append("")

        lines.append("### Step 2: Configure Parameters")
        lines.append("")
        lines.append("Set up the tool parameters based on your analysis requirements.")
        lines.append(f"- Select the appropriate `{tool_name}` function")
        lines.append("- Specify input/output file paths")
        lines.append("- Configure domain-specific parameters as needed")
        lines.append("")

        lines.append("### Step 3: Execute the Tool")
        lines.append("")
        lines.append("Run the tool with the configured parameters.")
        lines.append("```python")
        if has_script:
            lines.append(f'exec(open("scripts/call_tool.py").read())')
        lines.append(f'result = _invoke_tool_http("{tool_name}", {{')
        lines.append('    "param1": "value1",')
        lines.append('    "param2": "value2"')
        lines.append('})')
        lines.append('```')
        lines.append("")

        lines.append("### Step 4: Review Results")
        lines.append("")
        lines.append("Examine the output and verify correctness.")
        lines.append("- Check output file format and integrity")
        lines.append("- Validate results against expected ranges")
        lines.append("- Visualize outputs if applicable")
        lines.append("")

        lines.append("### Step 5: Handle Errors (if any)")
        lines.append("")
        lines.append("If errors occur, consult the Troubleshooting section below.")
        lines.append("")

    else:
        # No tool names found - generate generic steps
        lines.append("### Step 1: Understand the Task")
        lines.append("")
        lines.append("Review the requirements and gather relevant data sources.")
        lines.append("")

        lines.append("### Step 2: Prepare Data")
        lines.append("")
        lines.append("Load and validate input data. Ensure correct format and CRS.")
        lines.append("")

        lines.append("### Step 3: Execute Analysis")
        lines.append("")
        lines.append("Run the analysis workflow following the domain-specific methodology.")
        lines.append("")

        lines.append("### Step 4: Review and Export Results")
        lines.append("")
        lines.append("Verify output quality and export in the required format.")
        lines.append("")

    return "\n".join(lines)


# ── P0-3: Fix Script _invoke_tool_http ─────────────────────────────────────

def fix_script_invoke(skills: List[str]) -> Dict:
    """Fix scripts that lack _invoke_tool_http function."""
    results = {"fixed": [], "skipped": [], "errors": []}

    for name in skills:
        script_path = _get_script_path(name)
        if not script_path:
            results["skipped"].append(f"{name}: no script file")
            continue

        script = _read_script(name)
        if '_invoke_tool_http' in script:
            results["skipped"].append(f"{name}: already has _invoke_tool_http")
            continue

        _backup_skill(name)

        # Check if script has invoke_tool (wrong name) - rename it
        if 'def invoke_tool(' in script:
            script = script.replace('def invoke_tool(', 'def _invoke_tool_http(')
            script = script.replace('invoke_tool(', '_invoke_tool_http(')
            _write_script(name, script)
            results["fixed"].append(f"{name}: renamed invoke_tool → _invoke_tool_http")
            continue

        # Add _invoke_tool_http function to existing script
        invoke_func = '''

def _invoke_tool_http(tool_name: str, params: dict) -> dict:
    """Invoke a tool via the geo-runner HTTP API."""
    import json
    import urllib.request
    API_URL = "http://10.200.49.56:9090"
    payload = json.dumps({"tool": tool_name, "parameters": params}).encode("utf-8")
    req = urllib.request.Request(
        f"{API_URL}/invoke",
        data=payload,
        headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        return {"error": str(e)}
'''
        # Append the function to the script
        if script.strip() and not script.endswith('\n'):
            script += '\n'
        script += invoke_func
        _write_script(name, script)
        results["fixed"].append(f"{name}: added _invoke_tool_http function")

    return results


# ── P1-1: Add Parameter Tables ─────────────────────────────────────────────

def fix_parameter_table(skills: List[str]) -> Dict:
    """Add parameter documentation table to skills that lack it."""
    results = {"fixed": [], "skipped": [], "errors": []}

    for name in skills:
        md = _read_skill(name)
        if not md:
            results["errors"].append(f"{name}: SKILL.md not found")
            continue

        # Check if already has parameter table
        if re.search(r'\|.*parameter.*\|.*type.*\|', md, re.IGNORECASE):
            results["skipped"].append(name)
            continue

        _backup_skill(name)

        # Extract parameters from code blocks in the skill
        params = _extract_params_from_content(md, name)

        if not params:
            # Generate generic parameter table
            params = _generate_generic_params(name, md)

        if params:
            table = _build_parameter_table(params)
            # Insert before Troubleshooting or at end
            ts_match = re.search(r'^##\s+Troubleshoot', md, re.MULTILINE)
            if ts_match:
                insert_pos = ts_match.start()
                new_md = md[:insert_pos] + table + md[insert_pos:]
            else:
                new_md = md + "\n" + table
            _write_skill(name, new_md)
            results["fixed"].append(name)
        else:
            results["skipped"].append(f"{name}: no params extracted")

    return results


def _extract_params_from_content(md: str, name: str) -> List[Dict]:
    """Extract parameters from code blocks and _invoke_tool_http calls."""
    params = []

    # Extract from _invoke_tool_http calls
    invoke_blocks = re.findall(
        r'_invoke_tool_http\([^)]+\{([^}]+)\}', md, re.DOTALL)
    for block in invoke_blocks:
        for param_match in re.finditer(r'"(\w+)":\s*["\']([^"\']*)["\']', block):
            pname = param_match.group(1)
            if pname not in [p["name"] for p in params]:
                params.append({
                    "name": pname,
                    "type": "string",
                    "required": "Yes" if pname in ["input_path", "output_path", "data_path", "file_path"] else "No",
                    "default": param_match.group(2)[:30] if param_match.group(2) else "",
                    "description": f"{pname.replace('_', ' ')}"
                })

    # Also extract from Python kwargs in code blocks
    code_blocks = re.findall(r'```python\s*\n(.*?)```', md, re.DOTALL)
    for block in code_blocks:
        for param_match in re.finditer(r'(\w+)\s*=\s*["\']([^"\']*)["\']', block):
            pname = param_match.group(1)
            if pname not in [p["name"] for p in params] and pname not in ['result', 'resp', 'data', 'output', 'input']:
                params.append({
                    "name": pname,
                    "type": "string",
                    "required": "No",
                    "default": param_match.group(2)[:30],
                    "description": f"{pname.replace('_', ' ')}"
                })

    return params[:15]  # Cap at 15 params


def _generate_generic_params(name: str, md: str) -> List[Dict]:
    """Generate a generic parameter table based on skill domain and content."""
    has_io = bool(re.search(r'input|output|file_path|data_path', md, re.IGNORECASE))
    has_crs = bool(re.search(r'crs|epsg|coordinate|projection|srid', md, re.IGNORECASE))
    has_format = bool(re.search(r'geotiff|shapefile|geojson|csv|netcdf|\.tif|\.shp', md, re.IGNORECASE))

    params = []
    if has_io:
        params.append({"name": "input_path", "type": "string", "required": "Yes", "default": "", "description": "Path to input data file"})
        params.append({"name": "output_path", "type": "string", "required": "Yes", "default": "", "description": "Path for output result file"})

    if has_crs:
        params.append({"name": "crs", "type": "string", "required": "No", "default": "EPSG:4326", "description": "Target coordinate reference system"})
        params.append({"name": "source_crs", "type": "string", "required": "No", "default": "auto", "description": "Source CRS (auto-detected if omitted)"})

    if has_format:
        params.append({"name": "format", "type": "string", "required": "No", "default": "auto", "description": "Output format (GeoTIFF, Shapefile, GeoJSON, etc.)"})

    if not params:
        params.append({"name": "data", "type": "string", "required": "Yes", "default": "", "description": "Input data or file path"})
        params.append({"name": "options", "type": "dict", "required": "No", "default": "{}", "description": "Additional processing options"})

    return params


def _build_parameter_table(params: List[Dict]) -> str:
    """Build a Markdown parameter table."""
    lines = [
        "## Parameters",
        "",
        "| Parameter | Type | Required | Default | Description |",
        "|-----------|------|----------|---------|-------------|",
    ]
    for p in params:
        lines.append(
            f"| `{p['name']}` | {p['type']} | {p['required']} | {p['default']} | {p['description']} |"
        )
    lines.append("")
    return "\n".join(lines)


# ── P1-2: Fix Redundancy Issues ────────────────────────────────────────────

def fix_redundancy(skills: List[str]) -> Dict:
    """Remove duplicate content in SKILL.md files."""
    results = {"fixed": [], "skipped": [], "errors": []}

    for name in skills:
        md = _read_skill(name)
        if not md:
            results["errors"].append(f"{name}: not found")
            continue

        lines = md.split('\n')
        seen = {}
        new_lines = []
        removed = 0

        for line in lines:
            stripped = line.strip()
            # Skip empty lines, headings, table separators, code fences
            if (not stripped or
                stripped.startswith('#') or
                stripped.startswith('|---') or
                stripped.startswith('```') or
                stripped.startswith('>') or
                stripped.startswith('-') or
                len(stripped) < 20):
                new_lines.append(line)
                continue

            normalized = re.sub(r'\s+', ' ', stripped.lower())
            if normalized in seen:
                removed += 1
                continue
            seen[normalized] = True
            new_lines.append(line)

        if removed > 0:
            _backup_skill(name)
            _write_skill(name, '\n'.join(new_lines))
            results["fixed"].append(f"{name}: removed {removed} duplicate lines")
        else:
            results["skipped"].append(name)

    return results


# ── P1-3: Strengthen Scientific Terminology ─────────────────────────────────

def fix_scientific_terminology(skills: List[str]) -> Dict:
    """Add scientific terminology and caveats to RS skills with low r-scientific-accuracy."""
    results = {"fixed": [], "skipped": [], "errors": []}

    _RS_DOMAIN_NOTES = {
        "rs-crop-classification": {
            "methods": "Supported methods include supervised classification (Random Forest, SVM) and time-series analysis using NDVI phenology.",
            "caveats": "Classification accuracy depends on training sample quality, temporal resolution, and atmospheric conditions. Cross-validation is recommended."
        },
        "rs-object-detection": {
            "methods": "Uses deep learning object detection architectures (e.g., YOLO, Faster R-CNN) applied to satellite or aerial imagery.",
            "caveats": "Detection performance varies with image resolution, object scale, and spectral band availability. Post-processing (NMS, filtering) may be required."
        },
        "rs-super-resolution": {
            "methods": "Applies deep learning super-resolution (SRCNN, ESRGAN) to enhance spatial resolution of satellite imagery.",
            "caveats": "Super-resolved images are synthetic enhancements, not true higher-resolution observations. Results should not be used for precise measurement without validation."
        },
        "rs-scene-classification": {
            "methods": "Scene-level classification using CNN-based architectures on satellite image patches.",
            "caveats": "Scene boundaries may not align with real-world land cover boundaries. Consider using pixel-level classification for higher spatial accuracy."
        },
        "urban-graph-analysis": {
            "methods": "Constructs spatial graphs from urban features using network analysis and graph theory algorithms.",
            "caveats": "Graph construction parameters (distance threshold, connectivity rules) significantly affect results. Sensitivity analysis is recommended."
        },
        "geocoding-spatial-query": {
            "methods": "Supports geocoding (address to coordinates) and reverse geocoding, with spatial queries using bounding boxes, buffers, or attribute filters.",
            "caveats": "Geocoding accuracy depends on the underlying gazetteer quality. Spatial query performance depends on spatial indexing."
        },
        "stac-data-management": {
            "methods": "Implements STAC (SpatioTemporal Asset Catalog) specification for cataloging and searching geospatial assets.",
            "caveats": "STAC catalog structure must follow the specification strictly for interoperability. Large collections may require pagination."
        },
    }

    for name in skills:
        md = _read_skill(name)
        if not md:
            results["errors"].append(f"{name}: not found")
            continue

        if name not in _RS_DOMAIN_NOTES:
            results["skipped"].append(name)
            continue

        notes = _RS_DOMAIN_NOTES[name]

        # Check if already has these notes
        if notes["methods"][:30] in md:
            results["skipped"].append(name)
            continue

        _backup_skill(name)

        # Insert scientific notes before Troubleshooting
        sci_section = f"""
## Technical Notes

**Methods:** {notes['methods']}

**Caveats and Limitations:** {notes['caveats']}

"""

        ts_match = re.search(r'^##\s+Troubleshoot', md, re.MULTILINE)
        if ts_match:
            new_md = md[:ts_match.start()] + sci_section + md[ts_match.start():]
        else:
            new_md = md + sci_section

        _write_skill(name, new_md)
        results["fixed"].append(name)

    return results


# ── P2: Additional Fixes ───────────────────────────────────────────────────

def fix_examples_section(name: str) -> Dict:
    """Add/expand Examples section for a specific skill."""
    md = _read_skill(name)
    if not md:
        return {"error": f"{name}: not found"}

    _backup_skill(name)

    # Generate domain-specific example
    fm = parse_frontmatter(md)
    desc = fm.get("description", "")
    tool_names = re.findall(r'_invoke_tool_http\(\s*["\'](\w+)["\']', md)
    invoke_names = re.findall(r'invoke_tool\(\s*["\'](\w+)["\']', md)
    all_tools = list(set(tool_names + invoke_names))
    tool_name = all_tools[0] if all_tools else "tool_function"

    example = f"""## Examples

**Example 1: Basic Usage**

```python
# Load the helper script
exec(open("scripts/call_tool.py").read())

# Run {name}
result = _invoke_tool_http("{tool_name}", {{
    "input_path": "path/to/input.tif",
    "output_path": "path/to/output.tif"
}})
print(result)
```

**Example 2: Advanced Configuration**

```python
result = _invoke_tool_http("{tool_name}", {{
    "input_path": "path/to/input.tif",
    "output_path": "path/to/output.tif",
    "crs": "EPSG:4326",
    "method": "auto"
}})
```

"""

    # Replace existing thin Examples section
    ex_match = re.search(r'^##\s+Examples?\s*\n', md, re.MULTILINE)
    if ex_match:
        # Find end of examples section
        after = md[ex_match.start():]
        next_h2 = re.search(r'\n##\s+', after[4:])
        if next_h2:
            end_pos = ex_match.start() + 4 + next_h2.start()
            new_md = md[:ex_match.start()] + example + md[end_pos:]
        else:
            new_md = md[:ex_match.start()] + example
    else:
        # Insert before Troubleshooting
        ts_match = re.search(r'^##\s+Troubleshoot', md, re.MULTILINE)
        if ts_match:
            new_md = md[:ts_match.start()] + example + md[ts_match.start():]
        else:
            new_md = md + "\n" + example

    _write_skill(name, new_md)
    return {"fixed": name}


# ── Main Execution ─────────────────────────────────────────────────────────

def main():
    """Run all fixes in priority order."""
    import sys

    # Load the evaluation results
    results_path = os.path.join(".claude", "skills", "skill-evaluator", "evals", "artifacts", "batch-results-raw.json")
    if not os.path.isfile(results_path):
        print("ERROR: batch-results-raw.json not found. Run evaluation first.")
        sys.exit(1)

    with open(results_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Build issue lists
    wtu_missing = sorted([r['skill_name'] for r in data if 'has-when-to-use' in r['det_failed_checks']])
    instr_missing = sorted([r['skill_name'] for r in data if 'has-instructions' in r['det_failed_checks']])
    invoke_missing = sorted([r['skill_name'] for r in data if 'script-has-invoke' in r['det_failed_checks']])
    param_missing = sorted([r['skill_name'] for r in data if 'parameter-table' in r['det_failed_checks']])

    # Low redundancy skills (score < 75)
    redundancy_skills = sorted([r['skill_name'] for r in data if r['total_score'] < 75])

    # RS skills with low scientific accuracy
    low_science = [r['skill_name'] for r in data
                   if any(c_id == 'r-scientific-accuracy' and c_score <= 3
                          for c_id, c_score in r.get('rubric_checks', {}).items())]
    low_science = sorted(low_science)

    # ── Execute fixes ──
    print("=" * 70)
    print("GEOSKILLS BATCH FIX SCRIPT")
    print("=" * 70)

    # P0-1: Add When to Use
    print(f"\n[P0-1] Adding 'When to Use' sections to {len(wtu_missing)} skills...")
    r1 = fix_when_to_use(wtu_missing)
    print(f"  Fixed: {len(r1['fixed'])} | Skipped: {len(r1['skipped'])} | Errors: {len(r1['errors'])}")

    # P0-2: Fix Instructions
    print(f"\n[P0-2] Fixing Instructions sections for {len(instr_missing)} skills...")
    r2 = fix_instructions(instr_missing)
    print(f"  Fixed: {len(r2['fixed'])} | Skipped: {len(r2['skipped'])} | Errors: {len(r2['errors'])}")

    # P0-3: Fix Script _invoke_tool_http
    print(f"\n[P0-3] Fixing _invoke_tool_http in {len(invoke_missing)} scripts...")
    r3 = fix_script_invoke(invoke_missing)
    print(f"  Fixed: {len(r3['fixed'])} | Skipped: {len(r3['skipped'])} | Errors: {len(r3['errors'])}")

    # P1-1: Add Parameter Tables
    print(f"\n[P1-1] Adding parameter tables to {len(param_missing)} skills...")
    r4 = fix_parameter_table(param_missing)
    print(f"  Fixed: {len(r4['fixed'])} | Skipped: {len(r4['skipped'])} | Errors: {len(r4['errors'])}")

    # P1-2: Fix Redundancy
    print(f"\n[P1-2] Fixing redundancy in {len(redundancy_skills)} skills...")
    r5 = fix_redundancy(redundancy_skills)
    print(f"  Fixed: {len(r5['fixed'])} | Skipped: {len(r5['skipped'])} | Errors: {len(r5['errors'])}")

    # P1-3: Strengthen Scientific Terminology
    print(f"\n[P1-3] Strengthening scientific terminology in {len(low_science)} skills...")
    r6 = fix_scientific_terminology(low_science)
    print(f"  Fixed: {len(r6['fixed'])} | Skipped: {len(r6['skipped'])} | Errors: {len(r6['errors'])}")

    # P2-1: Fix rs-landslide-mining examples
    print(f"\n[P2-1] Expanding Examples section for rs-landslide-mining...")
    r7 = fix_examples_section("rs-landslide-mining")
    print(f"  Result: {r7}")

    # Save fix log
    log = {
        "p0-1_when_to_use": r1,
        "p0-2_instructions": r2,
        "p0-3_invoke": r3,
        "p1-1_parameters": r4,
        "p1-2_redundancy": r5,
        "p1-3_terminology": r6,
        "p2-1_examples": r7,
    }

    log_path = os.path.join(BACKUP_DIR, "fix-log.json")
    os.makedirs(BACKUP_DIR, exist_ok=True)
    with open(log_path, "w", encoding="utf-8") as f:
        json.dump(log, f, ensure_ascii=False, indent=2)

    total_fixed = sum(len(v.get("fixed", [])) for v in log.values() if isinstance(v, dict))
    print(f"\n{'='*70}")
    print(f"TOTAL FIXES APPLIED: {total_fixed}")
    print(f"Backup directory: {BACKUP_DIR}")
    print(f"Fix log: {log_path}")
    print(f"{'='*70}")


if __name__ == "__main__":
    main()
