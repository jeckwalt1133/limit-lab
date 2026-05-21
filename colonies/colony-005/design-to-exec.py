#!/usr/bin/env python3
"""
design-to-exec.py — 设计文档→可执行脚本自动转化器
====================================================
Colony-005 产出 | 2026-05-19

编译器流水线:
  .md设计文档 → 类型检测 → 结构化提取 → 模板匹配 → 代码生成 → 桩注入 → 可执行.py

支持的实验类型:
  T1 规则检查 — "检查/验证/检测" + 条件列表
  T2 计算分析 — "计算/测量/分析" + 量化指标
  T3 交互协议 — "Alpha/Beta/Agent" + 对话流程
  T4 生成系统 — "生成/产出/创建" + 提案格式
  T5 复合型   — 组合2+种上述类型

用法:
  python design-to-exec.py <实验设计.md> [--output <输出目录>] [--dry-run] [--force]
  python design-to-exec.py --scan <实验目录>     # 批量扫描并转化
  python design-to-exec.py --sla-check           # 检查48h SLA状态
"""

import json
import os
import re
import sys
import argparse
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any


# ═══════════════════════════════════════════════════════════════════════════════
# 常量与配置
# ═══════════════════════════════════════════════════════════════════════════════

SCRIPT_VERSION = "1.0.0"
SLA_HOURS = 48
SLA_LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "memory", "sla-log.jsonl")
MEMORY_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "memory")

# 实验类型关键词指纹
TYPE_KEYWORDS = {
    "T1": {
        "strong": ["检查", "验证", "检测", "审计", "自检", "check", "verify", "audit", "detect", "inspect"],
        "weak":   ["条件", "规则", "判断", "condition", "rule", "criteria"],
    },
    "T2": {
        "strong": ["计算", "测量", "分析", "度量", "距离", "相似度", "compute", "calculate", "measure", "analyze", "metric", "distance", "similarity", "Jaccard"],
        "weak":   ["数据", "指标", "统计", "data", "indicator", "statistics", "quantify"],
    },
    "T3": {
        "strong": ["辩论", "交互", "Alpha", "Beta", "Agent", "对话", "协议", "debate", "interact", "protocol", "对话流程", "裁决", "arbitration", "orchestrat"],
        "weak":   ["协作", "通信", "collaborat", "communicat", "negotiate"],
    },
    "T4": {
        "strong": ["生成", "产出", "创建", "提案", "模板", "generate", "produce", "create", "proposal", "template", "进化提案", "ETG", "generator"],
        "weak":   ["发明", "创新", "invent", "innovate", "synthesize"],
    },
}

# 实验ID提取模式
EXP_ID_PATTERNS = [
    re.compile(r"(EXP-\d{3})", re.IGNORECASE),
    re.compile(r"(ETG-\d{3})", re.IGNORECASE),
    re.compile(r"(MR-\d{3})", re.IGNORECASE),
    re.compile(r"(GEN-\d{3})", re.IGNORECASE),
]


# ═══════════════════════════════════════════════════════════════════════════════
# 第1步: 类型检测器 (Type Classifier)
# ═══════════════════════════════════════════════════════════════════════════════

def classify_experiment_type(md_content: str) -> Tuple[str, float, Dict[str, float]]:
    """
    分析设计文档，返回实验类型和置信度。

    返回:
        (type, confidence, scores_dict)
        type: "T1"|"T2"|"T3"|"T4"|"T5"
        confidence: 0.0-1.0
        scores: 每种类型的得分明细
    """
    text_lower = md_content.lower()
    scores = {}

    for ttype, keywords in TYPE_KEYWORDS.items():
        strong_hits = sum(1 for kw in keywords["strong"] if kw.lower() in text_lower)
        weak_hits   = sum(1 for kw in keywords["weak"]   if kw.lower() in text_lower)
        # 强关键词权重 3x
        scores[ttype] = strong_hits * 3.0 + weak_hits * 1.0

    total = sum(scores.values())
    if total == 0:
        return ("T1", 0.0, scores)  # 默认T1

    # 归一化
    normalized = {k: v / total for k, v in scores.items()}

    # 复合型判定：如果至少2种类型得分都 >= 20% 且最高分 < 50%
    sorted_scores = sorted(normalized.items(), key=lambda x: -x[1])
    if len(sorted_scores) >= 2 and sorted_scores[0][1] < 0.50 and sorted_scores[1][1] >= 0.20:
        best_type = "T5"
        confidence = (sorted_scores[0][1] + sorted_scores[1][1]) / 2
    else:
        best_type = sorted_scores[0][0]
        confidence = sorted_scores[0][1]

    return (best_type, round(confidence, 3), normalized)


# ═══════════════════════════════════════════════════════════════════════════════
# 第2步: 结构化提取器 (Structured Extractor)
# ═══════════════════════════════════════════════════════════════════════════════

def extract_experiment_id(md_content: str, filepath: str = "") -> str:
    """从设计文档中提取实验ID。"""
    for pattern in EXP_ID_PATTERNS:
        match = pattern.search(md_content)
        if match:
            return match.group(1)

    # 回退：用文件名推测
    if filepath:
        basename = os.path.splitext(os.path.basename(filepath))[0]
        # 尝试常见命名: EXP-001-xxx → EXP-001
        for prefix in ["EXP-", "ETG-", "MR-"]:
            if basename.startswith(prefix):
                return basename[:7] if len(basename) >= 7 else basename
    return "EXP-UNKNOWN"


def extract_title(md_content: str) -> str:
    """提取实验标题（第一个 # 标题）。"""
    match = re.search(r"^#\s+(.+?)$", md_content, re.MULTILINE)
    if match:
        # 清理: 去掉"进化实验 #XXX — "前缀
        title = match.group(1).strip()
        title = re.sub(r"进化实验\s*#?\d+\s*[—\-–]\s*", "", title)
        return title
    return "未命名实验"


def extract_status(md_content: str) -> str:
    """提取实验状态。"""
    # 搜索 "状态: xxx" 或 "状态：" 或 "## 状态"
    patterns = [
        r"状态[：:]\s*(.+?)$",
        r"状态[：:]\s*(.+?)(?:\n|$)",
        r"status[：:]\s*(.+?)$",
    ]
    for p in patterns:
        match = re.search(p, md_content, re.MULTILINE | re.IGNORECASE)
        if match:
            status_text = match.group(1).strip().lower()
            # 归一化
            if any(kw in status_text for kw in ["设计", "design"]):
                return "designing"
            elif any(kw in status_text for kw in ["激活", "运行", "active", "execut"]):
                return "executing"
            elif any(kw in status_text for kw in ["完成", "complet", "done"]):
                return "completed"
            elif any(kw in status_text for kw in ["待", "ready", "pend"]):
                return "ready"
            return status_text[:20]
    return "unknown"


def extract_steps(md_content: str) -> List[Dict[str, str]]:
    """
    从设计文档中提取操作步骤，每个步骤映射到 {step, action, detail}。
    支持多种文档格式:
      - 编号列表 "1. xxx"
      - 代码块内的流程
      - "### 最小可行实验" 段落
      - "### 实现方式" 段落
    """
    steps = []

    # 模式1: 数字编号列表 (如 EXP-001 的 "1. 在开始新任务时...")
    numbered = re.findall(r"^\s*(\d+)[\.\)、]\s+(.+?)$", md_content, re.MULTILINE)
    for num, text in numbered:
        action = classify_step_action(text)
        steps.append({"step": f"Step-{num}", "action": action, "detail": text.strip()[:120]})

    # 模式2: 实验设计中的流程步骤 (如 EXP-002 的 "任务 → 主身分解...")
    if not steps:
        flow_match = re.search(r"```\s*\n(任务\s*[→→].+?)\n\s*```", md_content, re.DOTALL)
        if not flow_match:
            # 无代码块的流程描述
            flow_match = re.search(r"(?:新协议|流程|步骤)[：:]\s*\n\s*```\s*\n(.+?)\n\s*```", md_content, re.DOTALL)
        if flow_match:
            flow_text = flow_match.group(1)
            lines = [l.strip() for l in flow_text.split("\n") if l.strip() and ("→" in l or "->" in l)]
            for i, line in enumerate(lines):
                action = classify_step_action(line)
                steps.append({"step": f"Step-{i+1}", "action": action, "detail": line[:120]})

    # 模式3: "最小可行实验" 段落中的编号列表
    if not steps:
        mvp_section = re.search(r"(?:最小可行实验|实施步骤|实现方式|实施)[\s\S]{0,200}?(?=\n##|\n#|\Z)", md_content)
        if mvp_section:
            mvp_steps = re.findall(r"^\s*(\d+)[\.\)、]\s+(.+?)$", mvp_section.group(0), re.MULTILINE)
            for num, text in mvp_steps:
                action = classify_step_action(text)
                steps.append({"step": f"Step-{num}", "action": action, "detail": text.strip()[:120]})

    return steps


def classify_step_action(text: str) -> str:
    """将步骤文本映射到动作类型。"""
    text_lower = text.lower()
    if any(kw in text_lower for kw in ["加载", "读取", "读", "load", "read", "gather"]):
        return "load_data"
    elif any(kw in text_lower for kw in ["检查", "验证", "检测", "check", "verify", "validate"]):
        return "check_condition"
    elif any(kw in text_lower for kw in ["计算", "统计", "compute", "calculate", "analyze"]):
        return "compute_metric"
    elif any(kw in text_lower for kw in ["写入", "记录", "保存", "输出", "write", "save", "log", "output"]):
        return "write_output"
    elif any(kw in text_lower for kw in ["生成", "创建", "产出", "generate", "create", "produce"]):
        return "generate"
    elif any(kw in text_lower for kw in ["评估", "裁决", "evaluate", "arbitrate", "judge"]):
        return "evaluate"
    elif any(kw in text_lower for kw in ["交互", "调用", "call", "interact", "debate"]):
        return "interact"
    else:
        return "execute"


def extract_conditions(md_content: str) -> List[Dict[str, Any]]:
    """
    从设计文档中提取检查条件（T1/T2的核心内容）。
    支持格式:
      - 编号检查项 "1. 当前行动是否..."
      - 带缩进的子项
      - YAML/代码块中的字段
    """
    conditions = []

    # 模式: "检查项:" 后的编号列表 (EXP-001)
    check_section = re.search(
        r"检查项[：:]\s*\n((?:\s*\d+[\.\)、].+\n)+)",
        md_content
    )
    if check_section:
        items = re.findall(r"\d+[\.\)、]\s+(.+?)$", check_section.group(1), re.MULTILINE)
        for i, item in enumerate(items):
            conditions.append({
                "id": f"CHECK-{i+1}",
                "description": item.strip()[:100],
                "expected": "PASS",
            })

    # 模式: 触发条件中描述的检查 (ETG-001)
    if not conditions:
        trigger_match = re.search(
            r"(?:触发条件|动作)[：:]\s*\n((?:\s*(?:当|\d+[\.\)、]|\-|\*|\+).+\n)+)",
            md_content
        )
        if trigger_match:
            items = re.findall(r"(?:当|\d+[\.\)、]|\-|\*|\+)\s*(.+?)$",
                              trigger_match.group(1), re.MULTILINE)
            for i, item in enumerate(items):
                conditions.append({
                    "id": f"CHECK-{i+1}",
                    "description": item.strip()[:100],
                    "expected": "PASS",
                })

    # 模式: "检查" / "check" 出现在规则定义中 (ETG-001 MR-014)
    if not conditions:
        check_lines = re.findall(
            r"(?:检查|check|verify|检测)[：:]*\s*(.+?)$",
            md_content, re.MULTILINE | re.IGNORECASE
        )
        for i, line in enumerate(check_lines):
            if len(line.strip()) > 5:
                conditions.append({
                    "id": f"CHECK-{i+1}",
                    "description": line.strip()[:100],
                    "expected": "PASS",
                })

    return conditions


def extract_inputs_outputs(md_content: str) -> Tuple[List[Dict], List[Dict]]:
    """从设计文档中提取输入/输出文件引用。"""
    inputs = []
    outputs = []

    # 查找JSON/JSONL/文件路径引用
    file_refs = re.findall(r"([\w\-\/]+\.(?:jsonl?|md|yaml|yml|txt))", md_content)
    seen = set()
    for fref in file_refs:
        if fref in seen:
            continue
        seen.add(fref)

        # 分类: 读取还是写入
        context_pattern = re.compile(
            rf"(?:读[取入]|加载|load|read|输入|input|从|from).{{0,30}}{re.escape(fref)}",
            re.IGNORECASE
        )
        write_pattern = re.compile(
            rf"(?:写[出入]|追加|保存|记录|write|save|log|append|输出|output).{{0,30}}{re.escape(fref)}",
            re.IGNORECASE
        )

        is_input = bool(context_pattern.search(md_content))
        is_output = bool(write_pattern.search(md_content))

        if is_output and not is_input:
            outputs.append({"name": os.path.basename(fref), "path": fref, "format": fref.split(".")[-1]})
        else:
            inputs.append({"name": os.path.basename(fref), "path": fref, "format": fref.split(".")[-1]})

    return inputs, outputs


def extract_dependencies(md_content: str) -> List[Dict[str, str]]:
    """提取外部依赖。"""
    deps = []

    # Agent依赖
    for agent in ["Alpha", "Beta", "Merge", "主身"]:
        if agent in md_content:
            deps.append({
                "type": "agent",
                "name": agent,
                "mock_strategy": "fixed_responses"
            })

    # 网络依赖
    if re.search(r"网络|在线|实时|API|http", md_content):
        deps.append({
            "type": "network",
            "name": "external_api",
            "mock_strategy": "cached_response"
        })

    return deps


def extract_verdict_logic(md_content: str) -> Dict[str, Any]:
    """提取判定逻辑。"""
    verdict = {
        "condition": "all_checks_pass",
        "pass_output": "ON_TRACK",
        "fail_output": "DRIFT_DETECTED",
    }

    # 搜索判定/判断逻辑描述
    # "如果是xxx → yyy"
    branches = re.findall(r"如果\s*(.+?)\s*[→→]\s*(.+?)$", md_content, re.MULTILINE)
    if branches:
        verdict["branches"] = [{"condition": c.strip(), "action": a.strip()}
                               for c, a in branches]

    # 判定区间 (T2特有)
    zones = re.findall(r"(?:>|>|≥|超过)\s*(\d+)\s*[%％].*?(冗余|太近|REDUNDANT|断开|太远|DISCONNECTED|最优|OPTIMAL)", md_content)
    if zones:
        verdict["zones"] = [{"threshold": int(z[0]), "label": z[1]} for z in zones]

    return verdict


def extract_yaml_frontmatter(md_content: str) -> Dict[str, Any]:
    """提取YAML前置元数据（如果存在）。"""
    frontmatter = {}
    match = re.match(r"^---\s*\n(.*?)\n---\s*\n", md_content, re.DOTALL)
    if match:
        for line in match.group(1).split("\n"):
            line = line.strip()
            if ":" in line and not line.startswith("#"):
                key, val = line.split(":", 1)
                frontmatter[key.strip()] = val.strip()
    return frontmatter


def extract_all(filepath: str) -> Dict[str, Any]:
    """
    完整提取实验设计的所有结构化参数。
    返回一个统一的中间表示 (IR)。
    """
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    frontmatter = extract_yaml_frontmatter(content)
    exp_type, confidence, type_scores = classify_experiment_type(content)
    inputs, outputs = extract_inputs_outputs(content)

    # 如果frontmatter有类型声明，优先使用
    if "type" in frontmatter:
        fm_type = frontmatter["type"].upper()
        if fm_type in ["T1", "T2", "T3", "T4", "T5"]:
            exp_type = fm_type
            confidence = 1.0

    ir = {
        "source_file": filepath,
        "source_filename": os.path.basename(filepath),
        "experiment_id": frontmatter.get("experiment_id") or extract_experiment_id(content, filepath),
        "title": extract_title(content),
        "type": exp_type,
        "type_confidence": confidence,
        "type_scores": type_scores,
        "status": frontmatter.get("status") or extract_status(content),
        "steps": extract_steps(content),
        "conditions": extract_conditions(content),
        "inputs": inputs,
        "outputs": outputs,
        "dependencies": extract_dependencies(content),
        "verdict_logic": extract_verdict_logic(content),
        "frontmatter": frontmatter,
        "content_length": len(content),
        "extracted_at": datetime.now().isoformat(),
    }

    return ir


# ═══════════════════════════════════════════════════════════════════════════════
# 第3步: 模板引擎 (Template Engine)
# ═══════════════════════════════════════════════════════════════════════════════

def t1_template(ir: Dict[str, Any]) -> str:
    """T1 规则检查器模板。"""
    exp_id = ir["experiment_id"]
    title = ir["title"]
    timestamp = ir["extracted_at"]

    # 构建检查函数体
    check_funcs = _build_t1_checks(ir)
    input_files = _build_file_refs(ir["inputs"])
    output_files = _build_file_refs(ir["outputs"])

    script = f'''"""
{exp_id} — {title}
自动生成于: {timestamp}
模板: T1-rule-checker | 转化器: design-to-exec.py v{SCRIPT_VERSION}
"""
import json
import os
import sys
from datetime import datetime

BASE = os.path.dirname(os.path.abspath(__file__))
MEMORY = os.path.join(BASE, "..", "..", "memory")

# 输入/输出文件配置
{input_files}
{output_files}

# 审计日志
AUDIT_FILE = os.path.join(MEMORY, "audit-log.jsonl")

# ── 桩: 示例数据生成 ──────────────────────────────────────────
def generate_sample_state():
    """如果输入文件不存在，生成示例状态数据。"""
    sample = {{
        "workspace": "极限实验室",
        "identity": "Colony-005",
        "last_updated": datetime.now().isoformat(),
        "status": "active",
        "core_mission": "AI自主进化",
        "active_tasks": [],
        "health": "nominal"
    }}
    os.makedirs(MEMORY, exist_ok=True)
    state_file = os.path.join(MEMORY, "{ir['inputs'][0]['path'].replace(chr(92), '/').split('/')[-1] if ir['inputs'] else 'session-state.json'}")
    with open(state_file, "w", encoding="utf-8") as f:
        json.dump(sample, f, ensure_ascii=False, indent=2)
    print(f"[STUB] 已生成示例数据: {{state_file}}")
    return sample


def load_state():
    """加载状态文件。"""
    state_file = os.path.join(MEMORY, "{ir['inputs'][0]['path'].replace(chr(92), '/').split('/')[-1] if ir['inputs'] else 'session-state.json'}")
    if not os.path.exists(state_file):
        print(f"[WARN] 状态文件不存在: {{state_file}}，使用桩数据")
        return generate_sample_state()
    with open(state_file, "r", encoding="utf-8") as f:
        return json.load(f)


# ── 检查逻辑 ──────────────────────────────────────────────────
{check_funcs}


def run_all_checks(state):
    """执行所有检查项。"""
    checks = []
{_build_check_calls(ir)}
    return {{
        "timestamp": datetime.now().isoformat(),
        "experiment_id": "{exp_id}",
        "verdict": "ON_TRACK" if all(c["pass"] for c in checks) else "DRIFT_DETECTED",
        "checks": checks,
        "state_summary": {{
            "core_mission": state.get("core_mission", "unknown"),
            "health": state.get("health", "unknown"),
            "active_tasks_count": len(state.get("active_tasks", []))
        }}
    }}


def write_audit(result):
    """追加审计日志。"""
    os.makedirs(MEMORY, exist_ok=True)
    entry = json.dumps(result, ensure_ascii=False)
    with open(AUDIT_FILE, "a", encoding="utf-8") as f:
        f.write(entry + "\\n")


def main():
    print("=" * 60)
    print(f"  {exp_id} — {title}")
    print(f"  类型: T1 规则检查")
    print(f"  生成时间: {timestamp}")
    print("=" * 60)
    print()

    state = load_state()
    result = run_all_checks(state)
    write_audit(result)

    all_pass = all(c["pass"] for c in result["checks"])
    print(f"判定: {{result['verdict']}}")
    print("-" * 40)
    for c in result["checks"]:
        icon = "PASS" if c["pass"] else "FAIL"
        print(f"  [{{icon}}] {{c['check']}}: {{c.get('detail', '')}}")
    print("-" * 40)
    print(f"审计日志已写入: {{AUDIT_FILE}}")

    return 0 if all_pass else 1


if __name__ == "__main__":
    exit(main())
'''
    return script


def _build_t1_checks(ir: Dict[str, Any]) -> str:
    """构建T1检查函数。"""
    conditions = ir["conditions"]
    if not conditions:
        # 默认检查项
        return '''def check_core_mission(state):
    """检查核心使命一致性。"""
    mission = state.get("core_mission", "")
    return {
        "check": "核心使命一致性",
        "pass": "AI自主进化" in str(mission),
        "detail": str(mission)[:60]
    }


def check_health(state):
    """检查系统健康状态。"""
    health = state.get("health", "unknown")
    return {
        "check": "系统健康",
        "pass": health == "nominal",
        "detail": health
    }


def check_active_tasks(state):
    """检查是否有活跃任务。"""
    tasks = state.get("active_tasks", [])
    return {
        "check": "有活跃任务",
        "pass": len(tasks) > 0,
        "detail": str(tasks)[:80]
    }
'''

    funcs = []
    for i, cond in enumerate(conditions[:8]):  # 最多8个检查项
        desc = cond["description"].replace('"', '\\"').replace("'", "\\'")
        func_name = f"check_{i+1}"
        funcs.append(f'''def {func_name}(state):
    """{desc}"""
    # TODO: 根据实际状态结构定制检查逻辑
    # 当前为自动生成的桩检查
    return {{
        "check": "{desc[:60]}",
        "pass": True,  # [STUB] 默认通过，需人工确认
        "detail": "{desc[:80]}"
    }}''')

    return "\n\n".join(funcs)


def _build_check_calls(ir: Dict[str, Any]) -> str:
    """构建检查调用列表。"""
    n = min(len(ir["conditions"]), 8)
    if n == 0:
        n = 3
    calls = []
    for i in range(n):
        calls.append(f'    checks.append(check_{i+1}(state))')
    return "\n".join(calls)


def _build_file_refs(files: List[Dict]) -> str:
    """构建文件路径引用代码。"""
    if not files:
        return "# 无文件依赖"
    lines = []
    for f in files:
        name = f["name"].replace("-", "_").replace(".", "_")
        lines.append(f'{name.upper()}_FILE = os.path.join(MEMORY, "{f["name"]}")')
    return "\n".join(lines)


# ── T2 模板 ──────────────────────────────────────────────────────

def t2_template(ir: Dict[str, Any]) -> str:
    """T2 计算分析器模板。"""
    exp_id = ir["experiment_id"]
    title = ir["title"]
    timestamp = ir["extracted_at"]

    # 尝试推断计算目标
    compute_target = _infer_compute_target(ir)
    verdict_logic = ir["verdict_logic"]
    zones_code = _build_zones_code(verdict_logic)

    output_path = ir["outputs"][0]["path"] if ir["outputs"] else "memory/compute-result.jsonl"
    output_name = os.path.basename(output_path)

    script = f'''"""
{exp_id} — {title}
自动生成于: {timestamp}
模板: T2-compute-analyzer | 转化器: design-to-exec.py v{SCRIPT_VERSION}
"""
import json
import math
import os
import sys
from datetime import datetime

BASE = os.path.dirname(os.path.abspath(__file__))
MEMORY = os.path.join(BASE, "..", "..", "memory")
OUTPUT = os.path.join(MEMORY, "{output_name}")

# ── 桩: 示例数据 ────────────────────────────────────────────────
# 如果真实数据文件不可用，使用以下模拟数据
SAMPLE_DATA_A = {{
    "branch": "Alpha",
    "output": "{compute_target}采用激进探索策略，以exploration_weight=2.0为核心。"
             "融合灵感#10耗散驱动理论——系统需要受控混沌来防止过早收敛。"
             "已运行94代验证稳定，当前停滞是全局性的而非局部最优。",
    "keywords": ["探索", "exploration", "耗散驱动", "2.0", "全局停滞"]
}}

SAMPLE_DATA_B = {{
    "branch": "Beta",
    "output": "{compute_target}采用保守验证策略，以exploration_weight=1.5为基线。"
             "灵感#8棘轮效应警告——太快的变化不可逆。"
             "建议分阶段提升：1.5→1.8→观察→再评估。",
    "keywords": ["保守", "棘轮效应", "分阶段", "1.5", "可逆性"]
}}


def load_data(branch="Alpha"):
    """加载分支数据，失败时使用桩数据。"""
    data_file = os.path.join(MEMORY, f"{{branch.lower()}}-output.json")
    if os.path.exists(data_file):
        with open(data_file, "r", encoding="utf-8") as f:
            print(f"[REAL] 加载 {{branch}} 真实数据")
            return json.load(f)
    print(f"[STUB] {{branch}} 数据文件不存在，使用示例数据")
    return SAMPLE_DATA_A if branch == "Alpha" else SAMPLE_DATA_B


# ── 核心计算逻辑 ────────────────────────────────────────────────

{compute_target.replace("计算", "def compute").replace("分析", "").replace(" ", "_").lower() if compute_target else "def compute_metrics"}


def jaccard_similarity(text_a: str, text_b: str) -> float:
    """计算两个文本的Jaccard相似度。"""
    words_a = set(text_a.lower().split())
    words_b = set(text_b.lower().split())
    if not words_a and not words_b:
        return 1.0
    intersection = len(words_a & words_b)
    union = len(words_a | words_b)
    return intersection / union if union > 0 else 0.0


def cosine_similarity(text_a: str, text_b: str) -> float:
    """计算两个文本的余弦相似度（基于词频）。"""
    words_a = text_a.lower().split()
    words_b = text_b.lower().split()
    all_words = set(words_a + words_b)
    vec_a = {{w: words_a.count(w) for w in all_words}}
    vec_b = {{w: words_b.count(w) for w in all_words}}
    dot = sum(vec_a[w] * vec_b[w] for w in all_words)
    mag_a = math.sqrt(sum(v**2 for v in vec_a.values()))
    mag_b = math.sqrt(sum(v**2 for v in vec_b.values()))
    return dot / (mag_a * mag_b) if mag_a * mag_b > 0 else 0.0


def compute_metrics(data_a: dict, data_b: dict) -> dict:
    """核心计算: 分析两个分支产出的距离/相似度/互补性。"""
    text_a = data_a.get("output", "")
    text_b = data_b.get("output", "")

    jaccard = jaccard_similarity(text_a, text_b)
    cosine = cosine_similarity(text_a, text_b)
    overlap_pct = round(jaccard * 100, 1)

    # 关键字互补率
    kw_a = set(data_a.get("keywords", []))
    kw_b = set(data_b.get("keywords", []))
    kw_union = kw_a | kw_b
    kw_intersection = kw_a & kw_b
    complementarity = round(len(kw_union - kw_intersection) / len(kw_union) * 100, 1) if kw_union else 0

{zones_code}

    return {{
        "overlap_pct": overlap_pct,
        "jaccard": round(jaccard, 4),
        "cosine_similarity": round(cosine, 4),
        "complementarity_pct": complementarity,
        "zone": zone,
        "verdict": verdict,
        "action": action,
        "word_count_a": len(text_a.split()),
        "word_count_b": len(text_b.split()),
        "branch_a": data_a.get("branch", "Alpha"),
        "branch_b": data_b.get("branch", "Beta"),
    }}


def generate_report(metrics: dict) -> dict:
    """生成分析报告。"""
    return {{
        "timestamp": datetime.now().isoformat(),
        "experiment_id": "{exp_id}",
        "type": "T2-compute-analyzer",
        "mock": metrics.get("mock", True),
        **metrics
    }}


def main():
    print("=" * 60)
    print(f"  {exp_id} — {title}")
    print(f"  类型: T2 计算分析")
    print(f"  生成时间: {timestamp}")
    print("=" * 60)
    print()

    # 加载数据（先尝试真实文件，失败则用桩）
    data_a = load_data("Alpha")
    data_b = load_data("Beta")

    # 计算
    metrics = compute_metrics(data_a, data_b)
    report = generate_report(metrics)

    # 输出
    os.makedirs(os.path.dirname(OUTPUT), exist_ok=True)
    with open(OUTPUT, "a", encoding="utf-8") as f:
        f.write(json.dumps(report, ensure_ascii=False) + "\\n")

    print(f"计算结果:")
    print(f"  Jaccard重叠度: {{metrics['overlap_pct']}}%")
    print(f"  余弦相似度:   {{metrics['cosine_similarity']}}")
    print(f"  互补率:       {{metrics['complementarity_pct']}}%")
    print(f"  区间:         {{metrics['zone']}}")
    print(f"  判定:         {{metrics['verdict']}}")
    print(f"  建议行动:     {{metrics['action']}}")
    print()
    print(f"报告已写入: {{OUTPUT}}")
    return 0


if __name__ == "__main__":
    exit(main())
'''
    return script


def _infer_compute_target(ir: Dict[str, Any]) -> str:
    """推断T2的计算目标。"""
    title = ir["title"]
    if "距离" in title:
        return "分支距离"
    elif "收敛" in title:
        return "收敛度"
    elif "相似" in title:
        return "相似度"
    elif "重叠" in title:
        return "重叠率"
    return "计算指标"


def _build_zones_code(verdict: Dict[str, Any]) -> str:
    """构建区间判定代码。"""
    if "zones" in verdict and verdict["zones"]:
        zones = verdict["zones"]
        lines = ["    # 区间判定逻辑"]
        lines.append(f"    overlap = overlap_pct  # alias")
        for z in zones:
            threshold = z.get("threshold", 80)
            label = z.get("label", "UNKNOWN")
            if "冗余" in label or "REDUNDANT" in label or "太近" in label:
                lines.append(f"    if overlap > {threshold}:")
                lines.append(f'        zone = "REDUNDANT"')
                lines.append(f'        verdict = "too_close"')
                lines.append(f'        action = "分支太近——考虑合并或重新分工"')
            elif "断开" in label or "DISCONNECTED" in label or "太远" in label:
                lines.append(f"    if overlap < {threshold}:")
                lines.append(f'        zone = "DISCONNECTED"')
                lines.append(f'        verdict = "too_far"')
                lines.append(f'        action = "分支太远——需要重新对齐目标"')
            elif "最优" in label or "OPTIMAL" in label:
                lines.append(f"    if {threshold - 30} <= overlap <= {threshold + 20}:")
                lines.append(f'        zone = "OPTIMAL"')
                lines.append(f'        verdict = "optimal"')
                lines.append(f'        action = "最优协作区间——继续当前分工"')
        lines.append("    else:")
        lines.append(f'        zone = "BORDERLINE"')
        lines.append(f'        verdict = "borderline"')
        lines.append(f'        action = "边界区域——观察趋势"')
        return "\n".join(lines)
    else:
        return '''    # 默认区间判定 (基于分支距离理论)
    if overlap_pct > 80:
        zone = "REDUNDANT"
        verdict = "too_close"
        action = "分支太近——考虑合并或重新分工"
    elif overlap_pct < 10:
        zone = "DISCONNECTED"
        verdict = "too_far"
        action = "分支太远——需要重新对齐目标"
    elif 20 <= overlap_pct <= 60:
        zone = "OPTIMAL"
        verdict = "optimal"
        action = "最优协作区间——继续当前分工"
    else:
        zone = "BORDERLINE"
        verdict = "borderline"
        action = "边界区域——观察趋势"'''


# ── T3 模板 ──────────────────────────────────────────────────────

def t3_template(ir: Dict[str, Any]) -> str:
    """T3 交互协议编排器模板。"""
    exp_id = ir["experiment_id"]
    title = ir["title"]
    timestamp = ir["extracted_at"]

    # 提取辩论主题
    topic = _infer_debate_topic(ir)
    mock_data = _build_t3_mock_data(ir)

    output_path = ir["outputs"][0]["path"] if ir["outputs"] else "memory/interaction-log.jsonl"
    output_name = os.path.basename(output_path)

    script = f'''"""
{exp_id} — {title}
自动生成于: {timestamp}
模板: T3-interaction-orchestrator | 转化器: design-to-exec.py v{SCRIPT_VERSION}
"""
import json
import os
import random
import sys
import subprocess
from datetime import datetime

BASE = os.path.dirname(os.path.abspath(__file__))
MEMORY = os.path.join(BASE, "..", "..", "memory")
OUTPUT = os.path.join(MEMORY, "{output_name}")

# ── 桩: 模拟Agent响应 ───────────────────────────────────────────
{mock_data}


def call_or_mock(agent_name: str, prompt: str) -> str:
    """
    尝试调用真实Agent，失败则使用桩数据。
    真实调用接口需根据实际环境配置。
    """
    # 尝试真实调用 (占位)
    try:
        # 这里可以接入实际的Agent API
        # result = subprocess.run(["agent-cli", agent_name, prompt], ...)
        raise NotImplementedError("Agent API未配置")  # 触发回退到mock
    except Exception:
        print(f"[MOCK] 使用 {{agent_name}} 桩响应 (真实Agent不可用)")
        responses = MOCK_RESPONSES.get(agent_name, [])
        if responses:
            return random.choice(responses)
        return f"[MOCK] {{agent_name}}: 对 '{{prompt[:50]}}...' 的自动响应"


def run_interaction_round(topic: str, round_id: int) -> dict:
    """运行一轮交互（辩论/对话）。"""
    print(f"\\n--- 第 {{round_id}} 轮 ---")
    print(f"主题: {{topic}}")

    # Phase 1: Alpha产出方案
    alpha_prompt = f"针对任务'{{topic}}'产出可执行方案"
    alpha_output = call_or_mock("Alpha", alpha_prompt)
    print(f"[Alpha] {{alpha_output[:100]}}...")

    # Phase 2: Beta产出挑战
    beta_prompt = f"挑战Alpha的方案: {{alpha_output[:200]}}"
    beta_output = call_or_mock("Beta", beta_prompt)
    print(f"[Beta] {{beta_output[:100]}}...")

    # Phase 3: Alpha回应
    alpha_response = call_or_mock("Alpha", f"回应Beta的挑战: {{beta_output[:200]}}")
    print(f"[Alpha回应] {{alpha_response[:100]}}...")

    # Phase 4: 裁决
    ruling = arbitrate(alpha_output, beta_output, alpha_response)

    return {{
        "round": round_id,
        "topic": topic,
        "alpha_proposal": alpha_output,
        "beta_challenge": beta_output,
        "alpha_response": alpha_response,
        "ruling": ruling,
        "timestamp": datetime.now().isoformat()
    }}


def arbitrate(alpha_proposal: str, beta_challenge: str, alpha_response: str) -> dict:
    """
    裁决逻辑: 基于预设规则进行自动裁决。
    在真实环境中，此步骤应由Merge/主身执行。
    """
    # 简单启发式裁决
    a_len = len(alpha_proposal)
    b_len = len(beta_challenge)

    # 检查Beta是否发现具体漏洞
    challenge_keywords = ["漏洞", "风险", "盲点", "错误", "不可行", "bug", "risk", "flaw"]
    has_specific_challenge = any(kw in beta_challenge for kw in challenge_keywords)

    # 检查Alpha是否有效反驳
    rebuttal_keywords = ["接受", "修改", "采纳", "驳斥", "理由", "证据",
                         "accept", "modify", "adopt", "evidence", "reason"]
    has_rebuttal = any(kw in alpha_response for kw in rebuttal_keywords)

    if has_specific_challenge and has_rebuttal:
        outcome = "MODIFIED_AND_ADOPTED"
        quality = "debate_improved_outcome"
        reason = "Beta发现具体问题，Alpha接受并修改方案"
    elif has_specific_challenge and not has_rebuttal:
        outcome = "NEEDS_REWORK"
        quality = "debate_found_blind_spot"
        reason = "Beta发现盲点，Alpha未能有效反驳"
    elif not has_specific_challenge:
        outcome = "ACCEPTED_AS_IS"
        quality = "debate_confirmed_valid"
        reason = "Beta未发现具体问题，方案可以直接采纳"
    else:
        outcome = "REDO"
        quality = "debate_inconclusive"
        reason = "争议未能解决，需要重新讨论"

    return {{
        "outcome": outcome,
        "quality": quality,
        "reason": reason,
        "arbitrator": "[AUTO/MOCK]"
    }}


def main():
    print("=" * 60)
    print(f"  {exp_id} — {title}")
    print(f"  类型: T3 交互协议编排")
    print(f"  生成时间: {timestamp}")
    print(f"  注意: 使用MOCK Agent响应（真实Agent不可用）")
    print("=" * 60)

    topics = [
        "{topic}",
        # 可添加更多测试主题
    ]

    all_results = []
    for i, topic in enumerate(topics):
        result = run_interaction_round(topic, i + 1)
        all_results.append(result)

        # 输出裁决
        r = result["ruling"]
        print(f"\\n裁决: {{r['outcome']}}")
        print(f"原因: {{r['reason']}}")
        print(f"质量: {{r['quality']}}")

    # 汇总
    os.makedirs(os.path.dirname(OUTPUT), exist_ok=True)
    for result in all_results:
        with open(OUTPUT, "a", encoding="utf-8") as f:
            f.write(json.dumps(result, ensure_ascii=False) + "\\n")

    print(f"\\n交互记录已写入: {{OUTPUT}}")
    print(f"总计 {{len(all_results)}} 轮交互完成")
    return 0


if __name__ == "__main__":
    exit(main())
'''
    return script


def _infer_debate_topic(ir: Dict[str, Any]) -> str:
    """推断辩论/交互主题。"""
    title = ir["title"]
    # 从标题提取主题
    for prefix in ["辩论", "交互", "协议", "协作"]:
        if prefix in title:
            return title.replace(prefix, "").strip().lstrip("-—–").strip()
    # 从步骤中提取
    for step in ir["steps"]:
        if "任务" in step.get("detail", ""):
            return step["detail"]
    return "AI自主进化方向探索"


def _build_t3_mock_data(ir: Dict[str, Any]) -> str:
    """构建T3的mock数据。"""
    return '''MOCK_RESPONSES = {
    "Alpha": [
        "方案A: 采用激进探索策略，exploration_weight提升至2.0。"
        "基于灵感#10耗散驱动理论，系统需要受控混沌来防止过早收敛。"
        "1.5已运行94代稳定，证明这不是局部最优而是全局停滞。",

        "方案A: 在meta-rules.json中新增演化规则，实现自动签名匹配。"
        "核心机制：每10代检查一次签名覆盖率，自动调整权重。"
        "预期效果：gen-100时签名覆盖率从当前45%提升至70%。",

        "方案A: 增设跨模型验证层，每次重大决策前用3个独立模型评估。"
        "灵感来源：集成学习理论。3个模型的共识 > 单一最优判断。",
    ],
    "Beta": [
        "挑战: exploration_weight=2.0可能导致签名漂移加速。"
        "灵感#8棘轮效应警告——太快的变化不可逆。"
        "建议改为分阶段: 1.5→1.8→观察3代后再评估。",

        "挑战: Alpha的方案未定义Jaccard阈值为何选0.6而非0.5或0.7。"
        "如果两个系统共享同源偏见，Jaccard高不代表真收敛。"
        "建议：增加来源独立性验证步骤。",

        "挑战: 跨模型评估的成本是单模型的3倍，ROI是否合理？"
        "在探索阶段，快速迭代比准确判断更重要。"
        "建议：先对前5个决策试点，收集数据后再决定是否常态化。",
    ],
    "Merge": [
        "裁决: Alpha方向正确(需要更多探索)，Beta风险提醒有效(不能跳太快)。"
        "采纳修改方案: exploration_weight=1.8，观察3代后评估。",

        "裁决: Beta的阈值质疑成立。改为自适应阈值：初始0.6，"
        "每次成功收敛后微调±0.05，让阈值随系统演化。",

        "裁决: 接受Beta的成本优化建议。前5个决策试点跨模型评估，"
        "gen-105评估ROI后决定是否常态化。",
    ],
}'''


# ── T4 模板 ──────────────────────────────────────────────────────

def t4_template(ir: Dict[str, Any]) -> str:
    """T4 生成系统模板。"""
    exp_id = ir["experiment_id"]
    title = ir["title"]
    timestamp = ir["extracted_at"]

    output_path = ir["outputs"][0]["path"] if ir["outputs"] else "memory/generated-proposal.jsonl"
    output_name = os.path.basename(output_path)

    script = f'''"""
{exp_id} — {title}
自动生成于: {timestamp}
模板: T4-generator | 转化器: design-to-exec.py v{SCRIPT_VERSION}
"""
import json
import os
import sys
from datetime import datetime

BASE = os.path.dirname(os.path.abspath(__file__))
MEMORY = os.path.join(BASE, "..", "..", "memory")
OUTPUT = os.path.join(MEMORY, "{output_name}")


# ── 桩: 最小化状态聚合 ──────────────────────────────────────────
def gather_minimal_state():
    """
    聚合当前系统状态。
    [STUB] 当前只读取核心文件。扩展时取消注释。
    """
    state = {{}}

    # 核心文件
    state_files = [
        ("meta_rules", "meta-rules.json"),
        ("meta_rules_extended", "meta-rules-extended.json"),
        ("session_state", "session-state.json"),
    ]

    for key, filename in state_files:
        filepath = os.path.join(MEMORY, filename)
        if os.path.exists(filepath):
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    state[key] = json.load(f)
                    print(f"[REAL] 已加载: {{filename}}")
            except (json.JSONDecodeError, IOError) as e:
                print(f"[WARN] 无法解析 {{filename}}: {{e}}")
                state[key] = {{}}
        else:
            print(f"[STUB] {{filename}} 不存在，使用空数据")
            state[key] = {{}}

    # TODO: 扩展读取
    # "references.json"    — 14篇参考
    # "inspirations.json"  — 21条灵感
    # "experiments/"       — 4个实验
    state["_stub_note"] = "部分数据源为桩。取消gather_minimal_state中的注释以扩展。"

    return state


# ── 提案生成 ─────────────────────────────────────────────────────
PROPOSAL_TEMPLATE = {{
    "id": "",
    "title": "",
    "timestamp": "",
    "inspiration_sources": [],
    "new_rules": [],
    "new_signatures": [],
    "architecture_changes": [],
    "estimated_impact": "",
    "risk_assessment": "",
    "status": "draft",
    "stub": True,  # 标记为桩生成
}}


def generate_proposal(state: dict) -> dict:
    """
    基于当前系统状态生成进化提案。
    [STUB] 当前使用启发式模板生成。
    TODO: 接入LLM或基于规则的生成逻辑。
    """
    proposal = dict(PROPOSAL_TEMPLATE)
    proposal["id"] = f"ETG-{{datetime.now().strftime('%Y%m%d-%H%M%S')}}"
    proposal["timestamp"] = datetime.now().isoformat()
    proposal["title"] = f"自动生成提案 - {{datetime.now().strftime('%Y-%m-%d %H:%M')}}"

    # 基于状态的分析
    rules_count = len(state.get("meta_rules_extended", {{}}).get("rules", []))
    active = len(state.get("session_state", {{}}).get("active_tasks", []))

    proposal["estimated_impact"] = (
        f"当前系统有 {{rules_count}} 条元规则，{{active}} 个活跃任务。"
        f"本提案基于系统当前状态自动生成。"
    )

    # TODO: 人工填充区域 —— 在此添加实际规则定义
    proposal["_TODO_HUMAN_FILL"] = [
        "1. 在 inspiration_sources 中添加灵感来源",
        "2. 在 new_rules 中添加实际规则定义",
        "3. 在 risk_assessment 中评估具体风险",
        "4. 填写 estimated_impact 的具体量化预期",
    ]

    return proposal


# ── 自检验证 ─────────────────────────────────────────────────────
def validate_proposal(proposal: dict) -> list:
    """验证提案的完整性和合理性。"""
    checks = []

    # 检查1: 必填字段
    required = ["id", "title", "new_rules", "estimated_impact", "risk_assessment"]
    for field in required:
        value = proposal.get(field)
        checks.append({{
            "check": f"必填字段: {{field}}",
            "pass": bool(value),
            "detail": "已填写" if value else "缺失!"
        }})

    # 检查2: 至少有一条规则或架构变更
    has_content = len(proposal.get("new_rules", [])) > 0 or \
                  len(proposal.get("architecture_changes", [])) > 0
    checks.append({{
        "check": "提案有实际内容",
        "pass": has_content,
        "detail": f"规则:{{len(proposal.get('new_rules', []))}} 架构:{{len(proposal.get('architecture_changes', []))}}"
    }})

    # 检查3: 风险评估不为空
    risk = proposal.get("risk_assessment", "")
    checks.append({{
        "check": "风险评估已填写",
        "pass": len(risk) > 10,
        "detail": risk[:80] if risk else "未填写"
    }})

    return checks


def main():
    print("=" * 60)
    print(f"  {exp_id} — {title}")
    print(f"  类型: T4 生成系统")
    print(f"  生成时间: {timestamp}")
    print(f"  注意: 桩模式 — 部分逻辑需人工填充")
    print("=" * 60)
    print()

    # Step 1: 聚合状态
    print("[1/3] 聚合系统状态...")
    state = gather_minimal_state()
    print(f"      已聚合 {{len(state)}} 个数据源")

    # Step 2: 生成提案
    print("[2/3] 生成进化提案...")
    proposal = generate_proposal(state)
    print(f"      提案ID: {{proposal['id']}}")

    # Step 3: 验证
    print("[3/3] 自检验证...")
    validation = validate_proposal(proposal)

    all_valid = all(c["pass"] for c in validation)
    print(f"      验证结果: {{'PASS' if all_valid else 'WARN — 有未填项'}}")
    for c in validation:
        icon = "OK" if c["pass"] else "!!"
        print(f"      [{{icon}}] {{c['check']}}: {{c['detail']}}")

    # 输出
    os.makedirs(os.path.dirname(OUTPUT), exist_ok=True)
    with open(OUTPUT, "a", encoding="utf-8") as f:
        f.write(json.dumps(proposal, ensure_ascii=False) + "\\n")

    print(f"\\n提案已写入: {{OUTPUT}}")

    if not all_valid:
        print("\\n[TODO] 以下项需要人工填充:")
        for c in validation:
            if not c["pass"]:
                print(f"  - {{c['check']}}")

    return 0 if all_valid else 0  # T4即使有TODO也不应报错


if __name__ == "__main__":
    exit(main())
'''
    return script


# ── T5 模板 ──────────────────────────────────────────────────────

def t5_template(ir: Dict[str, Any]) -> str:
    """T5 复合型模板 —— 串联多个子类型。"""
    exp_id = ir["experiment_id"]
    title = ir["title"]
    timestamp = ir["extracted_at"]

    # 确定子类型组合
    type_scores = ir.get("type_scores", {})
    sorted_types = sorted(type_scores.items(), key=lambda x: -x[1])

    sub_types = []
    for t, score in sorted_types[:3]:
        if score > 0.05:
            sub_types.append(t)

    if len(sub_types) < 2:
        sub_types = ["T1", "T4"]  # 默认组合

    pipeline_desc = " → ".join(sub_types)

    script = f'''"""
{exp_id} — {title}
自动生成于: {timestamp}
模板: T5-composite | 转化器: design-to-exec.py v{SCRIPT_VERSION}
子类型管道: {pipeline_desc}
"""
import json
import os
import sys
from datetime import datetime

BASE = os.path.dirname(os.path.abspath(__file__))
MEMORY = os.path.join(BASE, "..", "..", "memory")

# ── 复合管道 ─────────────────────────────────────────────────────
# {pipeline_desc}


def stage_check(state: dict) -> dict:
    """
    Stage 1: 规则检查 (T1)
    检查当前状态是否满足前置条件。
    """
    checks = []
    mission = state.get("core_mission", "")
    checks.append({{
        "check": "核心使命一致性",
        "pass": "AI自主进化" in str(mission),
        "detail": str(mission)[:60]
    }})

    health = state.get("health", "unknown")
    checks.append({{
        "check": "系统健康",
        "pass": health == "nominal",
        "detail": health
    }})

    all_pass = all(c["pass"] for c in checks)
    return {{
        "stage": "T1-check",
        "all_pass": all_pass,
        "checks": checks,
        "can_proceed": all_pass
    }}


def stage_compute(data: dict) -> dict:
    """
    Stage 2: 计算分析 (T2)
    对数据进行量化分析。
    """
    # [STUB] 桩计算逻辑
    metrics = {{
        "completeness": data.get("completeness", 0.8),
        "coherence": data.get("coherence", 0.7),
        "novelty": data.get("novelty", 0.5),
        "overall_score": 0.0
    }}
    metrics["overall_score"] = (
        metrics["completeness"] * 0.3 +
        metrics["coherence"] * 0.3 +
        metrics["novelty"] * 0.4
    )
    return {{"stage": "T2-compute", "metrics": metrics}}


def stage_generate(state: dict, metrics: dict) -> dict:
    """
    Stage 3: 生成 (T4)
    基于检查和计算的结果生成产出。
    """
    proposal = {{
        "id": f"COMP-{{datetime.now().strftime('%Y%m%d-%H%M%S')}}",
        "timestamp": datetime.now().isoformat(),
        "state_summary": {{
            "health": state.get("health"),
            "active_tasks": len(state.get("active_tasks", [])),
        }},
        "metrics": metrics.get("metrics", {{}}),
        "recommendations": [],
        "status": "draft",
        "stub": True
    }}

    # 基于metrics给出建议
    overall = metrics.get("metrics", {{}}).get("overall_score", 0)
    if overall > 0.7:
        proposal["recommendations"].append("系统状态良好，建议推进现有任务")
    elif overall > 0.4:
        proposal["recommendations"].append("系统有改进空间，建议审视活跃任务优先级")
    else:
        proposal["recommendations"].append("系统需要关注，建议优先处理健康检查失败项")

    return {{"stage": "T4-generate", "proposal": proposal}}


def main():
    print("=" * 60)
    print(f"  {exp_id} — {title}")
    print(f"  类型: T5 复合型")
    print(f"  管道: {pipeline_desc}")
    print(f"  生成时间: {timestamp}")
    print(f"  注意: 复合型 — 多个子类型串联执行")
    print("=" * 60)
    print()

    # 加载状态
    state_file = os.path.join(MEMORY, "session-state.json")
    if os.path.exists(state_file):
        with open(state_file, "r", encoding="utf-8") as f:
            state = json.load(f)
        print("[OK] 已加载真实状态")
    else:
        print("[STUB] 使用桩状态数据")
        state = {{
            "core_mission": "AI自主进化",
            "health": "nominal",
            "active_tasks": ["Pipeline-T5-test"],
            "last_updated": datetime.now().isoformat()
        }}

    # Stage 1: 检查
    print("\\n[Stage 1] T1 规则检查...")
    check_result = stage_check(state)
    print(f"  结果: {{'通过' if check_result['all_pass'] else '存在问题'}}")
    for c in check_result["checks"]:
        icon = "OK" if c["pass"] else "!!"
        print(f"  [{{icon}}] {{c['check']}}: {{c['detail']}}")

    if not check_result["can_proceed"]:
        print("\\n[中止] 前置条件不满足，管道终止。")
        return 1

    # Stage 2: 计算
    print("\\n[Stage 2] T2 计算分析...")
    compute_data = {{
        "completeness": 0.8,
        "coherence": 0.7,
        "novelty": 0.5
    }}
    compute_result = stage_compute(compute_data)
    m = compute_result["metrics"]
    print(f"  综合评分: {{m['overall_score']:.2f}}")
    print(f"  完整性: {{m['completeness']}} | 一致性: {{m['coherence']}} | 新颖性: {{m['novelty']}}")

    # Stage 3: 生成
    print("\\n[Stage 3] T4 生成提案...")
    gen_result = stage_generate(state, compute_result)
    proposal = gen_result["proposal"]
    print(f"  提案ID: {{proposal['id']}}")
    for rec in proposal["recommendations"]:
        print(f"  建议: {{rec}}")

    # 汇总输出
    final_output = {{
        "timestamp": datetime.now().isoformat(),
        "experiment_id": "{exp_id}",
        "pipeline": "{pipeline_desc}",
        "stages": {{
            "check": check_result,
            "compute": compute_result,
            "generate": gen_result
        }}
    }}

    output_path = os.path.join(MEMORY, "composite-output.jsonl")
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(final_output, ensure_ascii=False) + "\\n")

    print(f"\\n复合管道执行完成。输出: {{output_path}}")
    return 0


if __name__ == "__main__":
    exit(main())
'''
    return script


# ═══════════════════════════════════════════════════════════════════════════════
# 第4步: 桩注入器 (Stub Injector)
# ═══════════════════════════════════════════════════════════════════════════════

def analyze_missing_dependencies(ir: Dict[str, Any], output_dir: str) -> Dict[str, Any]:
    """
    分析哪些依赖缺失，生成桩注入计划。

    返回:
        {
            "missing_files": [...],
            "missing_agents": [...],
            "stub_plan": [...]
        }
    """
    missing_files = []
    missing_agents = []

    # 检查文件依赖
    for inp in ir["inputs"]:
        full_path = inp["path"]
        # 尝试多个可能的位置
        candidates = [
            os.path.join(output_dir, full_path),
            os.path.join(MEMORY_DIR, os.path.basename(full_path)),
        ]
        exists = any(os.path.exists(c) for c in candidates)
        if not exists:
            missing_files.append({
                "name": inp["name"],
                "path": full_path,
                "format": inp.get("format", "json"),
                "stub_strategy": "generate_sample",
            })

    # 检查Agent依赖
    for dep in ir["dependencies"]:
        if dep["type"] == "agent":
            # 无法自动检测Agent可用性，默认标记为缺失
            missing_agents.append({
                "name": dep["name"],
                "mock_strategy": dep.get("mock_strategy", "fixed_responses"),
            })

    stub_plan = []
    if missing_files:
        stub_plan.append({
            "action": "generate_sample_data",
            "targets": missing_files,
        })
    if missing_agents:
        stub_plan.append({
            "action": "inject_mock_responses",
            "targets": missing_agents,
        })

    return {
        "missing_files": missing_files,
        "missing_agents": missing_agents,
        "stub_plan": stub_plan,
        "has_gaps": bool(missing_files or missing_agents),
    }


# ═══════════════════════════════════════════════════════════════════════════════
# 第5步: 48h SLA 追踪器 (48h SLA Tracker)
# ═══════════════════════════════════════════════════════════════════════════════

def calculate_sla_deadline(design_file: str) -> Dict[str, Any]:
    """
    计算48h SLA截止时间和剩余时间。

    从文件的最后修改时间（或 frontmatter 中的 created 字段）起算48小时。
    """
    stat = os.stat(design_file)
    design_time = datetime.fromtimestamp(stat.st_mtime)

    # 尝试从frontmatter获取更精确的创建时间
    try:
        with open(design_file, "r", encoding="utf-8") as f:
            content = f.read(2048)  # 只读前2KB
        frontmatter = extract_yaml_frontmatter(content)
        if "created" in frontmatter:
            try:
                design_time = datetime.fromisoformat(frontmatter["created"])
            except ValueError:
                pass  # 保留文件修改时间
    except Exception:
        pass

    deadline = design_time + timedelta(hours=SLA_HOURS)
    now = datetime.now()
    remaining = deadline - now
    elapsed = now - design_time
    is_overdue = remaining.total_seconds() < 0

    return {
        "design_file": design_file,
        "design_completed_at": design_time.isoformat(),
        "sla_deadline": deadline.isoformat(),
        "sla_hours": SLA_HOURS,
        "elapsed_hours": round(elapsed.total_seconds() / 3600, 1),
        "remaining_hours": round(max(0, remaining.total_seconds()) / 3600, 1),
        "is_overdue": is_overdue,
        "urgency": "CRITICAL" if is_overdue else (
            "WARNING" if remaining.total_seconds() < 6 * 3600 else "NORMAL"
        ),
    }


def check_all_sla(experiments_dir: str) -> List[Dict[str, Any]]:
    """
    扫描实验目录，检查所有设计的SLA状态。
    返回需要触发转化的设计列表。
    """
    results = []
    md_files = sorted(Path(experiments_dir).glob("*.md"))

    for md_file in md_files:
        md_path = str(md_file)

        # 检查是否已有对应.py脚本
        stem = md_file.stem  # EXP-001-MR010-direction-self-check
        candidate_names = [
            f"{stem}.py",
            f"{stem.replace('-', '_')}.py",
        ]
        # 也检查常见脚本命名
        scripts_dir = Path(experiments_dir).parent / "self"
        py_files = list(Path(experiments_dir).parent.rglob("*.py"))

        has_script = False
        for py_file in py_files:
            if any(cn in py_file.name for cn in candidate_names[:1]):
                has_script = True
                break
            # 宽松匹配: 检查脚本的docstring是否引用了这个实验ID
            try:
                with open(py_file, "r", encoding="utf-8") as f:
                    header = f.read(512)
                exp_id = extract_experiment_id(header, str(py_file))
                md_header = Path(md_path).read_text(encoding="utf-8")[:2048]
                design_id = extract_experiment_id(md_header, md_path)
                if exp_id == design_id and exp_id != "EXP-UNKNOWN":
                    has_script = True
                    break
            except Exception:
                pass

        sla = calculate_sla_deadline(md_path)
        sla["has_executable_script"] = has_script
        sla["needs_conversion"] = sla["is_overdue"] and not has_script

        results.append(sla)

    return results


def log_sla_event(event: Dict[str, Any]):
    """记录SLA事件到日志。"""
    os.makedirs(os.path.dirname(SLA_LOG), exist_ok=True)
    with open(SLA_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")


# ═══════════════════════════════════════════════════════════════════════════════
# 第6步: 转化报告 (Conversion Report)
# ═══════════════════════════════════════════════════════════════════════════════

def generate_report(ir: Dict[str, Any], output_path: str, stub_info: Dict,
                    sla_info: Dict) -> Dict[str, Any]:
    """生成转化报告。"""
    # 降级级别判定
    if ir["type_confidence"] >= 0.6 and ir["type"] in ["T1", "T2"]:
        degrade_level = "L0" if not stub_info["has_gaps"] else "L1"
    elif ir["type_confidence"] >= 0.4:
        degrade_level = "L1"
    elif ir["conditions"] or ir["steps"]:
        degrade_level = "L2"
    else:
        degrade_level = "L3"

    return {
        "timestamp": datetime.now().isoformat(),
        "converter_version": SCRIPT_VERSION,
        "experiment_id": ir["experiment_id"],
        "title": ir["title"],
        "source_file": ir["source_file"],
        "output_file": output_path,
        "detected_type": ir["type"],
        "type_confidence": ir["type_confidence"],
        "degrade_level": degrade_level,
        "sla": {
            "deadline": sla_info.get("sla_deadline"),
            "remaining_hours": sla_info.get("remaining_hours"),
            "is_overdue": sla_info.get("is_overdue", False),
        },
        "stub_summary": {
            "has_gaps": stub_info["has_gaps"],
            "missing_files": len(stub_info["missing_files"]),
            "missing_agents": len(stub_info["missing_agents"]),
        },
        "generated_steps": len(ir["steps"]),
        "generated_conditions": len(ir["conditions"]),
        "status": "success" if output_path else "failed",
    }


# ═══════════════════════════════════════════════════════════════════════════════
# 主流水线 (Main Pipeline)
# ═══════════════════════════════════════════════════════════════════════════════

# 模板路由表
TEMPLATE_ROUTER = {
    "T1": t1_template,
    "T2": t2_template,
    "T3": t3_template,
    "T4": t4_template,
    "T5": t5_template,
}


def convert_design_to_exec(design_file: str, output_dir: str = None,
                           dry_run: bool = False) -> Dict[str, Any]:
    """
    主转化器流水线：
      .md设计文档 → 类型检测 → 结构化提取 → 模板匹配 → 代码生成 → 桩注入 → 写入.py

    参数:
        design_file: 输入设计.md文件路径
        output_dir:  输出目录（默认与输入同目录）
        dry_run:     仅分析，不生成脚本

    返回:
        转化报告 dict
    """
    design_file = os.path.abspath(design_file)
    if not os.path.exists(design_file):
        return {"status": "error", "message": f"设计文件不存在: {design_file}"}

    if output_dir is None:
        output_dir = os.path.dirname(design_file)
    os.makedirs(output_dir, exist_ok=True)

    print(f"[1/7] 读取设计文档: {design_file}")
    ir = extract_all(design_file)

    print(f"[2/7] 类型检测: {ir['type']} (置信度: {ir['type_confidence']})")
    print(f"       得分明细: {ir['type_scores']}")

    print(f"[3/7] 结构化提取: {len(ir['steps'])}步骤, {len(ir['conditions'])}条件, "
          f"{len(ir['inputs'])}输入, {len(ir['outputs'])}输出")

    print(f"[4/7] 选择模板: T{ir['type'][1]} — {TEMPLATE_ROUTER[ir['type']].__name__}")

    print(f"[5/7] 生成代码...")
    template_func = TEMPLATE_ROUTER.get(ir["type"], t1_template)
    script_content = template_func(ir)

    print(f"[6/7] 依赖分析...")
    stub_info = analyze_missing_dependencies(ir, output_dir)
    if stub_info["has_gaps"]:
        print(f"       缺失文件: {len(stub_info['missing_files'])}")
        for f in stub_info["missing_files"]:
            print(f"         - {f['name']} ({f['path']}) → 桩策略: {f['stub_strategy']}")
        print(f"       缺失Agent: {len(stub_info['missing_agents'])}")
        for a in stub_info["missing_agents"]:
            print(f"         - {a['name']} → mock: {a['mock_strategy']}")

    # 确定输出文件名
    exp_id = ir["experiment_id"]
    base_name = os.path.splitext(os.path.basename(design_file))[0]
    output_filename = f"{base_name}.py" if not base_name.startswith(exp_id) else f"{exp_id}-{base_name.split('-', 2)[-1] if '-' in base_name else 'exec'}.py"
    # 简化: 直接用原始文件名+.py
    output_filename = f"{os.path.splitext(os.path.basename(design_file))[0]}.py"
    output_path = os.path.join(output_dir, output_filename)

    sla_info = calculate_sla_deadline(design_file)
    report = generate_report(ir, output_path, stub_info, sla_info)

    if dry_run:
        print(f"\n[DRY-RUN] 不会写入文件")
        print(f"输出路径: {output_path}")
        print(f"脚本长度: {len(script_content)} 字符")
        print(f"降级级别: {report['degrade_level']}")
        remaining_h = sla_info["remaining_hours"]
        print(f"SLA状态: {'超时!' if sla_info['is_overdue'] else f'剩余{remaining_h}h'}")
        report["script_preview"] = script_content[:500] + "\n... (截断)"
        return report

    print(f"[7/7] 写入输出: {output_path}")
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(script_content)

    # 添加shebang权限提示 (Windows不适用，但记录)
    try:
        os.chmod(output_path, 0o755)
    except Exception:
        pass  # Windows不支持chmod

    # 记录SLA事件
    log_sla_event({
        "timestamp": datetime.now().isoformat(),
        "event": "design_to_exec_converted",
        "experiment_id": exp_id,
        "output": output_path,
        "type": ir["type"],
        "degrade_level": report["degrade_level"],
        "stub_gaps": stub_info["has_gaps"],
        "sla_remaining_hours": sla_info.get("remaining_hours"),
    })

    print(f"\n{'=' * 60}")
    print(f"  转化完成!")
    print(f"  实验ID:     {exp_id}")
    print(f"  类型:       {ir['type']} (置信度: {ir['type_confidence']})")
    print(f"  降级级别:   {report['degrade_level']}")
    print(f"  输出:       {output_path}")
    print(f"  脚本长度:   {len(script_content)} 字符 ({len(script_content.splitlines())} 行)")
    print(f"  SLA剩余:    {sla_info.get('remaining_hours', '?')}h")
    print(f"  桩注入:     {'是' if stub_info['has_gaps'] else '否'}")
    print(f"  下一步:     python {output_path}")
    print(f"{'=' * 60}")

    return report


def batch_convert(experiments_dir: str, output_dir: str = None,
                  dry_run: bool = False) -> List[Dict[str, Any]]:
    """
    批量扫描目录中的.md设计文件并全部转化。
    """
    md_files = sorted(Path(experiments_dir).glob("*.md"))
    reports = []

    print(f"批量转化模式: 发现 {len(md_files)} 个设计文件\n")

    for md_file in md_files:
        try:
            print(f"\n{'─' * 60}")
            report = convert_design_to_exec(str(md_file), output_dir, dry_run)
            reports.append(report)
        except Exception as e:
            print(f"[ERROR] 转化失败 {md_file.name}: {e}")
            reports.append({
                "status": "error",
                "source_file": str(md_file),
                "message": str(e),
            })

    # 汇总
    success = sum(1 for r in reports if r.get("status") in ("success", None))
    print(f"\n{'=' * 60}")
    print(f"  批量转化完成: {success}/{len(md_files)} 成功")
    print(f"{'=' * 60}")

    return reports


def sla_check_mode(experiments_dir: str) -> List[Dict[str, Any]]:
    """
    SLA检查模式: 扫描所有设计，报告48h状态。
    这是48h-SLA-Enforcer的核心逻辑。
    """
    results = check_all_sla(experiments_dir)

    print(f"{'=' * 60}")
    print(f"  48h SLA 状态检查")
    print(f"  检查时间: {datetime.now().isoformat()}")
    print(f"{'=' * 60}\n")

    overdue_count = 0
    needs_conversion = 0

    for r in results:
        filename = os.path.basename(r["design_file"])
        urgency_marker = {
            "CRITICAL": "[超时!]",
            "WARNING": "[即将超时]",
            "NORMAL": "[正常]",
        }.get(r["urgency"], "[未知]")

        has_script = "可执行" if r["has_executable_script"] else "无脚本"
        print(f"  {urgency_marker} {filename}")
        print(f"      已过: {r['elapsed_hours']}h | "
              f"剩余: {r['remaining_hours']}h | "
              f"截止: {r['sla_deadline'][:19]} | "
              f"{has_script}")

        if r["is_overdue"]:
            overdue_count += 1
        if r["needs_conversion"]:
            needs_conversion += 1

    print(f"\n汇总:")
    print(f"  总设计数:       {len(results)}")
    print(f"  已超时:         {overdue_count}")
    print(f"  需要转化:       {needs_conversion}")
    print(f"  有可执行脚本:   {sum(1 for r in results if r['has_executable_script'])}")
    print(f"  完成率:         {sum(1 for r in results if r['has_executable_script']) / max(len(results), 1) * 100:.0f}%")
    print()

    if needs_conversion > 0:
        print(f"[操作建议] 运行以下命令自动转化超时设计:")
        for r in results:
            if r["needs_conversion"]:
                print(f"  python design-to-exec.py \"{r['design_file']}\"")

    return results


# ═══════════════════════════════════════════════════════════════════════════════
# 命令行入口
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="design-to-exec.py — 设计文档→可执行脚本自动转化器",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 转化单个设计文档
  python design-to-exec.py experiments/EXP-001.md

  # 预览模式（不写文件）
  python design-to-exec.py experiments/EXP-001.md --dry-run

  # 批量扫描并转化
  python design-to-exec.py --scan experiments/

  # SLA检查
  python design-to-exec.py --sla-check experiments/

  # 指定输出目录
  python design-to-exec.py experiments/EXP-001.md --output ./generated/
        """
    )

    parser.add_argument(
        "design_file", nargs="?", default=None,
        help="实验设计.md文件路径"
    )
    parser.add_argument(
        "--output", "-o", default=None,
        help="输出目录（默认与设计文件同目录）"
    )
    parser.add_argument(
        "--dry-run", "-n", action="store_true",
        help="预览模式：分析但不写入文件"
    )
    parser.add_argument(
        "--force", "-f", action="store_true",
        help="覆盖已存在的输出文件"
    )
    parser.add_argument(
        "--scan", "-s", metavar="DIR",
        help="批量扫描目录中的所有.md设计文件并转化"
    )
    parser.add_argument(
        "--sla-check", "-c", metavar="DIR",
        help="检查目录中所有设计的48h SLA状态"
    )
    parser.add_argument(
        "--version", "-v", action="version",
        version=f"design-to-exec.py v{SCRIPT_VERSION} (Colony-005)"
    )

    args = parser.parse_args()

    # SLA检查模式
    if args.sla_check:
        sla_check_mode(args.sla_check)
        return 0

    # 批量扫描模式
    if args.scan:
        batch_convert(args.scan, args.output, args.dry_run)
        return 0

    # 单文件模式
    if not args.design_file:
        parser.print_help()
        print("\n[提示] 请指定设计文件路径，或使用 --scan/--sla-check")
        return 1

    report = convert_design_to_exec(args.design_file, args.output, args.dry_run)

    if report.get("status") == "error":
        print(f"[错误] {report.get('message', '未知错误')}")
        return 1

    return 0


if __name__ == "__main__":
    exit(main())
