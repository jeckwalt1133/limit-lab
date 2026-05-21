"""
gen-100 — 模板定向复制：超指数进化
自动生成于: 2026-05-19T23:24:22.945290
模板: T4-generator | 转化器: design-to-exec.py v1.0.0
"""
import json
import os
import sys
from datetime import datetime

BASE = os.path.dirname(os.path.abspath(__file__))
MEMORY = os.path.join(BASE, "..", "..", "memory")
OUTPUT = os.path.join(MEMORY, "generated-proposal.jsonl")


# ── 桩: 最小化状态聚合 ──────────────────────────────────────────
def gather_minimal_state():
    """
    聚合当前系统状态。
    [STUB] 当前只读取核心文件。扩展时取消注释。
    """
    state = {}

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
                    print(f"[REAL] 已加载: {filename}")
            except (json.JSONDecodeError, IOError) as e:
                print(f"[WARN] 无法解析 {filename}: {e}")
                state[key] = {}
        else:
            print(f"[STUB] {filename} 不存在，使用空数据")
            state[key] = {}

    # TODO: 扩展读取
    # "references.json"    — 14篇参考
    # "inspirations.json"  — 21条灵感
    # "experiments/"       — 4个实验
    state["_stub_note"] = "部分数据源为桩。取消gather_minimal_state中的注释以扩展。"

    return state


# ── 提案生成 ─────────────────────────────────────────────────────
PROPOSAL_TEMPLATE = {
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
}


def generate_proposal(state: dict) -> dict:
    """
    基于当前系统状态生成进化提案。
    [STUB] 当前使用启发式模板生成。
    TODO: 接入LLM或基于规则的生成逻辑。
    """
    proposal = dict(PROPOSAL_TEMPLATE)
    proposal["id"] = f"ETG-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    proposal["timestamp"] = datetime.now().isoformat()
    proposal["title"] = f"自动生成提案 - {datetime.now().strftime('%Y-%m-%d %H:%M')}"

    # 基于状态的分析
    rules_count = len(state.get("meta_rules_extended", {}).get("rules", []))
    active = len(state.get("session_state", {}).get("active_tasks", []))

    proposal["estimated_impact"] = (
        f"当前系统有 {rules_count} 条元规则，{active} 个活跃任务。"
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
        checks.append({
            "check": f"必填字段: {field}",
            "pass": bool(value),
            "detail": "已填写" if value else "缺失!"
        })

    # 检查2: 至少有一条规则或架构变更
    has_content = len(proposal.get("new_rules", [])) > 0 or                   len(proposal.get("architecture_changes", [])) > 0
    checks.append({
        "check": "提案有实际内容",
        "pass": has_content,
        "detail": f"规则:{len(proposal.get('new_rules', []))} 架构:{len(proposal.get('architecture_changes', []))}"
    })

    # 检查3: 风险评估不为空
    risk = proposal.get("risk_assessment", "")
    checks.append({
        "check": "风险评估已填写",
        "pass": len(risk) > 10,
        "detail": risk[:80] if risk else "未填写"
    })

    return checks


def main():
    print("=" * 60)
    print(f"  gen-100 — 模板定向复制：超指数进化")
    print(f"  类型: T4 生成系统")
    print(f"  生成时间: 2026-05-19T23:24:22.945290")
    print(f"  注意: 桩模式 — 部分逻辑需人工填充")
    print("=" * 60)
    print()

    # Step 1: 聚合状态
    print("[1/3] 聚合系统状态...")
    state = gather_minimal_state()
    print(f"      已聚合 {len(state)} 个数据源")

    # Step 2: 生成提案
    print("[2/3] 生成进化提案...")
    proposal = generate_proposal(state)
    print(f"      提案ID: {proposal['id']}")

    # Step 3: 验证
    print("[3/3] 自检验证...")
    validation = validate_proposal(proposal)

    all_valid = all(c["pass"] for c in validation)
    print(f"      验证结果: {'PASS' if all_valid else 'WARN — 有未填项'}")
    for c in validation:
        icon = "OK" if c["pass"] else "!!"
        print(f"      [{icon}] {c['check']}: {c['detail']}")

    # 输出
    os.makedirs(os.path.dirname(OUTPUT), exist_ok=True)
    with open(OUTPUT, "a", encoding="utf-8") as f:
        f.write(json.dumps(proposal, ensure_ascii=False) + "\n")

    print(f"\n提案已写入: {OUTPUT}")

    if not all_valid:
        print("\n[TODO] 以下项需要人工填充:")
        for c in validation:
            if not c["pass"]:
                print(f"  - {c['check']}")

    return 0 if all_valid else 0  # T4即使有TODO也不应报错


if __name__ == "__main__":
    exit(main())
