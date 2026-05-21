"""
050 盲点验证器 — 独立于Merge的规则系统检查
048形式化 → 049分类 → 050验证
"""
import json, os, itertools

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RULE_FILE = os.path.join(BASE, "colonies", "colony-048", "rule-formalization.json")


def load_rules():
    if not os.path.exists(RULE_FILE):
        print("规则文件不存在。跳过。")
        return None
    with open(RULE_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def check_missing_links(rules):
    """S1: 检查跨规则缺失连接"""
    holes = []
    # MR-019(跨模型) 应该反馈到 MR-015(引擎) 但没有
    if "MR-019" in rules and "MR-015" in rules:
        deps_015 = rules["MR-015"]["dependencies"]
        if "MR-019" not in deps_015:
            holes.append("MR-019→MR-015: 跨模型验证结果不反馈到签名进化")
    return holes


def check_coverage_gaps(rules):
    """S2: 检查覆盖缺口"""
    types = set(r["type"] for r in rules.values())
    expected = {"self_check", "execution", "routing", "anti_overfit", "convergence",
                 "engine", "metrics", "defense", "identity", "noise", "debate",
                 "acceleration", "godel_axiom", "collaboration"}
    missing = expected - types
    return [f"缺失规则类型: {m}" for m in missing]


def check_circular_deps(rules):
    """S3: 检查循环依赖"""
    holes = []
    for a_id, a in rules.items():
        for b_id, b in rules.items():
            if a_id == b_id:
                continue
            if b_id in a.get("dependencies", []) and a_id in b.get("dependencies", []):
                holes.append(f"循环依赖: {a_id}↔{b_id}")
    return holes


def check_dead_rules(rules):
    """S4: 检查死规则"""
    holes = []
    for rid, r in rules.items():
        deps = r.get("dependencies", [])
        trigger = r.get("triggers", "")
        if "OVERRIDE" in rid and rid.replace("-OVERRIDE", "") not in rules:
            holes.append(f"死规则: {rid}——父规则不存在")
    return holes


def check_one_way_locks(rules):
    """S5: 检查单向锁"""
    holes = []
    if "MR-013" in rules:
        modifies = rules["MR-013"]["modifies"]
        if "signature_strength" in modifies:
            # MR-013只减强度，需要MR-003增强度——检查是否连通
            if "MR-003" not in rules["MR-013"].get("dependencies", []):
                holes.append("MR-013单向锁: 只减不增，与MR-003未建立依赖")
    return holes


def main():
    rules_data = load_rules()
    if not rules_data:
        return 0

    rules = rules_data.get("formalized_rules", {})
    if not rules:
        print("无规则数据")
        return 0

    all_holes = []
    all_holes.extend(check_missing_links(rules))
    all_holes.extend(check_coverage_gaps(rules))
    all_holes.extend(check_circular_deps(rules))
    all_holes.extend(check_dead_rules(rules))
    all_holes.extend(check_one_way_locks(rules))

    print(f"050盲点验证器: 发现{len(all_holes)}个结构空洞")
    for h in all_holes:
        print(f"  ⚠️ {h}")

    if not all_holes:
        print("  规则系统结构完整。无空洞。")
    else:
        print(f"  其中可自动修复: {sum(1 for h in all_holes if 'OVERRIDE' not in h)}")

    return len(all_holes)


if __name__ == "__main__":
    exit(main())
