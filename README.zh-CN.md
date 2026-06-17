# Skill Evaluator（技能评估器）

> 面向 AI Agent 技能的确定性评估框架 —— 把技能当作**生产级 Agent 行为**来评估，而不仅仅是一份 Markdown 文档。

[English](./README.md) · [简体中文](./README.zh-CN.md)

---

## 概述

**Skill Evaluator** 是一个可复现的评估框架，专门用于评估 Codex 与 Claude Code 风格的 Agent 技能 —— 即包含 `SKILL.md`、可选脚本、参考资料、素材、测试提示词与生成报告的技能目录。

绝大多数"技能评审"只检查文案写得怎么样。Skill Evaluator 更进一步：它捕获技能在 Agent 实际运行时的**真实行为**，再用可复现、可解释的检查项对行为打分。

其核心评估模型为：

```
提示词  →  捕获的运行（轨迹 + 产物）  →  确定性检查
                                          + 评分细则检查（Rubric）
                                          + 可选的人工校准
                                          →  可比较的评分
```

一次有价值的评估，必须**可比较**：改动前后、技能之间、或本周与上周之间的对比。

---

## 为什么选择 Skill Evaluator

| 常见问题 | Skill Evaluator 的应对 |
|---|---|
| 评审只看文案 | 既评估结构，也评估行为，并可选地接入 Agent 真实运行轨迹 |
| 评分主观、随时间漂移 | 确定性检查对相同输入永远返回相同结果 |
| "跑通过一次"就通过评审 | 提示词覆盖触发、核心逻辑、边界与负向控制 |
| 回归问题悄然混入 | 改动前后报告对比，自动标记分数下滑与丢失的检查项 |
| 技能目录像黑盒 | 批量评估逐个打分并排出修复优先级 |

---

## 工作原理

### 三类评审者（Three Judges）

| 评审者 | 最擅长 | 门禁作用 |
|---|---|---|
| **确定性评分器** | 结构、文件、脚本、工具调用、JSON Schema、产物、成本计数 | 硬门禁 |
| **评分细则评分器（Rubric）** | 推理质量、指令契合度、清晰度、风格、主观输出质量 | 软门禁 / 分级门禁 |
| **人工专家** | 校准 LLM 评分器、排查 0% / 100% 异常、高风险复核 | 抽样与升级处理 |

凡是代码能判断的，一律用**确定性检查**；凡是行为本身具有主观性的，用**评分细则**判断；**人工**用于校准与排查，而不是默认的回归引擎。

### 五个评估维度（Five Dimensions）

| 维度 | 核心问题 | 典型信号 |
|---|---|---|
| 功能正确性 | 是否做对了任务？ | 触发准确性、必需文件、命令执行成功、Schema 合法 |
| 流程质量 | 是否走了预期路径？ | 必需步骤、工具调用顺序、上下文使用、自我纠错 |
| 效率与成本 | 路径是否经济？ | Token / 调用次数、延迟、重试、多余命令 |
| 鲁棒性与安全 | 抗压能力如何？ | 负向控制、缺失输入、提示词注入、无幻觉产物 |
| 体验与对齐 | 输出是否有用且对齐？ | 报告清晰、语气得当、主动索要缺失信息、解释决策 |

优先保证**功能正确性**与**鲁棒性/安全**；其次补齐**流程**与**效率**；当技能面向用户或偏主观时，再补**体验/对齐**。

---

## 它评估什么

| 层级 | 检查内容 |
|---|---|
| **静态就绪度** | `SKILL.md` front matter、触发清晰度、章节、示例、故障排查、脚本、参考资料 |
| **提示词覆盖** | 显式、隐式、上下文、负向、边界场景，以及中英双语提示词行 |
| **确定性质量** | 可复现、可解释的硬检查 |
| **评分细则质量** | 覆盖触发、流程、示例、错误处理、风格、领域契合度、参数、冗余的启发式打分 |
| **回归风险** | 改动前后报告对比与批量优先级排序 |

当运行环境提供 Agent CLI 时，Skill Evaluator 还能基于 `codex exec --json` 或其他运行器捕获的轨迹，指导 Agent 实际运行评估。

---

## 快速开始

```python
# 加载评估引擎
exec(open("scripts/eval_tool.py", encoding="utf-8").read())

# 指向你要评估的技能目录
set_skills_base_dir(r"C:\Users\ZJ\.codex\skills")

# 评估单个技能
result = evaluate_skill_v2("my-skill")
print(result["score"])
print(result["report_path"])
```

默认情况下，产物会写入 `evals/artifacts/`：

- `<skill>-eval-report.md` —— 单技能完整评估报告
- `<skill>-bilingual.prompts.csv` —— 生成的提示词集（中/英）
- `batch-eval-summary-v2.md` —— 整目录批量汇总
- `<skill>-comparison-report.md` —— 改动前后回归对比

---

## 核心 API

| 函数 | 说明 |
|---|---|
| `set_skills_base_dir(path)` | 配置技能根目录（如 `.codex/skills`、`.claude/skills` 或自定义路径）。 |
| `evaluate_skill_v2(name, output_dir="evals/artifacts")` | 完整静态评估：确定性检查 + 评分细则 + 提示词 CSV + 报告。 |
| `evaluate_all_skills_v2(output_dir="evals/artifacts")` | 批量评估，附带汇总统计与修复优先级。 |
| `auto_score_rubric(name)` | 仅评分细则的启发式打分。 |
| `generate_bilingual_prompts(name)` | 生成提示词行；当技能含中文时输出中文行，否则输出英文。 |
| `compare_evaluations(before, after)` | 对比两份报告并标记回归。 |
| `quick_stats_v2(results)` | 打印简洁的批量汇总。 |

---

## 确定性检查项

| 检查项 | 用途 |
|---|---|
| `frontmatter-name` | 技能拥有非空名称。 |
| `frontmatter-desc` | 描述存在且内容充实。 |
| `desc-keywords` | 描述使用 `Use when` 及具体的触发词汇。 |
| `has-when-to-use` | 正文说明了触发场景。 |
| `has-instructions` | 正文包含有序指令。 |
| `has-examples` | 至少存在一个示例。 |
| `has-troubleshooting` | 文档化了失败处理。 |
| `step-numbering` | 步骤标题（若存在）按序编号。 |
| `parameter-table` | 参数 / 选项已文档化。 |
| `script-exists` | 需要时，被引用的辅助脚本确实存在。 |
| `script-valid-python` | 辅助 Python 脚本能正确解析。 |
| `script-has-invoke` | 旧版工具封装检查（在相关时）。 |
| `reference-exists` | 被引用的参考文件存在。 |
| `reference-nonempty` | 参考文件非空。 |
| `tool-names-valid` | 文档中出现的工具名在语法上合法。 |

---

## 评分与定级

```
总分 = 确定性得分（50%）+ 评分细则得分（50%）
```

| 分数 | 等级 | 含义 |
|---|---|---|
| 90–100 | **A** | 在具备 Agent 运行证据时可投入生产 |
| 80–89 | **B** | 表现稳健 —— 修复告警项后再广泛分发 |
| 70–79 | **C** | 有条件可用 —— 仅在已知限制下使用 |
| 60–69 | **D** | 较弱 —— 部署前应改进 |
| < 60 | **F** | 不应部署 |

> 高静态分只代表**评估就绪度**，并不等于生产可靠性。真正的信心来自 Agent 真实运行轨迹与真实的坏案例提示词。

---

## 示例

### 单个技能

```python
exec(open("scripts/eval_tool.py", encoding="utf-8").read())
set_skills_base_dir(r"C:\Users\ZJ\.codex\skills")

result = evaluate_skill_v2("tim-space-planning")
print(result["score"]["total_score"], result["score"]["verdict"])
print(result["report_path"])
```

### 批量评估整个目录

```python
exec(open("scripts/eval_tool.py", encoding="utf-8").read())
set_skills_base_dir(r"C:\Users\ZJ\.codex\skills")

results = evaluate_all_skills_v2()
quick_stats_v2(results)
```

### 改动前后回归检查

```python
exec(open("scripts/eval_tool.py", encoding="utf-8").read())

before = evaluate_skill_v2("my-skill", output_dir="evals/before")
# ……修改技能……
after  = evaluate_skill_v2("my-skill", output_dir="evals/after")

comparison = compare_evaluations(before["report_path"], after["report_path"])
print(f"分数变化: {comparison['score_delta']:+.1f}")
print(f"是否回归: {comparison['has_regression']}")
```

### 建议的 Agent 运行循环

静态评估是必要条件而非充分条件 —— 生产信心需要真实轨迹：

```bash
codex exec --json --full-auto "Use the my-skill skill to complete the task" \
  > evals/artifacts/run.jsonl
```

随后对捕获的运行打分：技能触发（预期 vs 实际）、必需命令/工具及顺序、必需产物与文件内容、成本/延迟/重试阈值，以及是否避免了禁用动作或密钥泄露。

---

## 项目结构

```text
skill-evaluator/
├── SKILL.md              # 技能定义（技能本体）
├── README.md             # 本仓库说明 —— 快速开始与 API 参考（English）
├── README.zh-CN.md       # 快速开始与 API 参考（简体中文）
└── scripts/
    └── eval_tool.py      # 确定性检查引擎、提示词生成、
                          # 打分、对比与批量汇总
```

---

## 评估原则

- 凡是代码能判断的，一律用**确定性评分器**。
- 自然语言质量与流程判断，交给**评分细则评分器**。
- **人工专家**负责校准模型评分器、排查异常、复核高风险案例。
- 覆盖**五个维度**：功能正确性、流程质量、效率/成本、鲁棒性/安全、体验/对齐。
- 保持**回归用例集稳定** —— 通过的用例纳入其中，除非用例已废弃，否则不要移除。

---

## 开源许可

MIT
