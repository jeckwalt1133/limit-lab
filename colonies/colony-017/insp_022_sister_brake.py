#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
INSP-022: 姊妹制动规则系统
============================================================
来源: Colony-016 自动灵感生成管线 (生态学 → 元规则系统)
映射: mechanism_transfer — 生态学"自调节悖论" → 元规则制动机制
文献: Yang Y, Barabas G, Saavedra S, Li A. (2026). PNAS, 123(2).

核心原理:
  生态学发现强自调节在临界点附近从稳定力逆转为破坏力。
  映射到元规则系统: 每条规则的strength参数存在倒U特性 —
  过高的strength在系统临界点(ETG)时反而破坏稳定性。

  解决方案: 每条增强规则配备一条"姊妹制动规则" —
  当自身强度超过阈值时自动降权, 低于恢复阈值时自动释放。

执行方式:
  python insp_022_sister_brake.py [--rules-config <path>] [--output <path>]
"""

import json
import math
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# ============================================================
# 配置常量 — 源自 INSP-022 的具体参数规格
# ============================================================

# 制动触发阈值: strength > 0.85 时激活制动
BRAKE_ACTIVATION_THRESHOLD = 0.85

# 制动释放阈值: strength < 0.30 时释放制动
BRAKE_RELEASE_THRESHOLD = 0.30

# 每次制动动作的降权幅度
BRAKE_STEP_DOWN = 0.05

# 每次释放动作的升权幅度 (缓慢恢复)
BRAKE_STEP_UP = 0.02

# 制动后冷却时间(会话数) — 防止频繁制动/释放振荡
BRAKE_COOLDOWN_SESSIONS = 3

# 元规则定义 (MR-001 ~ MR-013)
# 每条规则包含: 名称, 类别, 初始强度, 是否已有制动机制
META_RULES_DEFINITION: List[Dict] = [
    {"id": "MR-001", "name": "identity_validation",      "category": "core_security", "initial_strength": 0.95, "has_brake": False},
    {"id": "MR-002", "name": "decay_rate",               "category": "stability",     "initial_strength": 0.60, "has_brake": False},
    {"id": "MR-003", "name": "hebbian_reinforcement",    "category": "learning",      "initial_strength": 0.70, "has_brake": True},   # MR-013 是其姊妹制动
    {"id": "MR-004", "name": "generation_tracking",       "category": "core_security", "initial_strength": 0.90, "has_brake": False},
    {"id": "MR-005", "name": "exploration_exploitation",  "category": "learning",      "initial_strength": 0.65, "has_brake": False},
    {"id": "MR-006", "name": "convergence_boost",         "category": "optimization",  "initial_strength": 0.55, "has_brake": False},
    {"id": "MR-007", "name": "divergence_penalty",        "category": "stability",     "initial_strength": 0.50, "has_brake": False},
    {"id": "MR-008", "name": "convergence_detection",     "category": "monitoring",    "initial_strength": 0.75, "has_brake": False},
    {"id": "MR-009", "name": "signature_decay_control",   "category": "stability",     "initial_strength": 0.45, "has_brake": False},
    {"id": "MR-010", "name": "branch_health_monitor",     "category": "monitoring",    "initial_strength": 0.60, "has_brake": False},
    {"id": "MR-011", "name": "novelty_bonus",             "category": "learning",      "initial_strength": 0.40, "has_brake": False},
    {"id": "MR-012", "name": "conflict_resolution",       "category": "stability",     "initial_strength": 0.55, "has_brake": False},
    {"id": "MR-013", "name": "anti_overfitting",          "category": "learning",      "initial_strength": 0.50, "has_brake": False},  # 它本身是 MR-003 的姊妹制动
]


@dataclass
class BrakePair:
    """姊妹制动对 — 记录增强规则与其制动规则的关系"""
    primary_rule_id: str       # 被制动的主规则
    brake_rule_id: str         # 制动规则 (可能是新建的姊妹规则)
    activation_threshold: float = BRAKE_ACTIVATION_THRESHOLD
    release_threshold: float = BRAKE_RELEASE_THRESHOLD
    brake_active: bool = False
    sessions_since_last_brake: int = 999  # 初始设为高值, 允许立即制动
    sessions_since_last_release: int = 999
    brake_history: List[Dict] = field(default_factory=list)


@dataclass
class RuleState:
    """单条规则的运行时状态"""
    rule_id: str
    name: str
    category: str
    strength: float
    has_brake: bool
    brake_pair_id: Optional[str] = None   # 对应的制动规则 ID


class SisterBrakeSystem:
    """
    姊妹制动系统 — 实现 INSP-022 的核心逻辑

    工作流程:
    1. 载入所有元规则定义
    2. 为每条缺少制动的规则自动创建姊妹制动规则
    3. 每个评估周期检查所有规则强度
    4. 对超过阈值的规则触发制动, 对低于恢复阈值的释放制动
    5. 生成制动覆盖度热图
    """

    def __init__(self, rules_config: Optional[List[Dict]] = None):
        self.rules: Dict[str, RuleState] = {}
        self.brake_pairs: Dict[str, BrakePair] = {}  # key = primary_rule_id
        self.session_count: int = 0
        self.etg_in_progress: bool = False

        # 载入规则
        config = rules_config or META_RULES_DEFINITION
        for r in config:
            self.rules[r["id"]] = RuleState(
                rule_id=r["id"],
                name=r["name"],
                category=r["category"],
                strength=r.get("initial_strength", 0.50),
                has_brake=r.get("has_brake", False),
            )

        # 建立姊妹制动对
        self._establish_brake_pairs()

    def _establish_brake_pairs(self):
        """为每条缺少制动机制的规则自动创建姊妹制动规则并配对"""
        brake_counter = 14  # 新制动规则从 MR-014 开始编号

        for rule_id, rule in list(self.rules.items()):
            if rule.has_brake:
                # 已有制动 — 查找其姊妹 (如 MR-003 → MR-013)
                # 简化: 约定制动规则 ID 为原规则 ID + 10
                # 实际系统中应由配置指定
                partner_id = f"MR-{int(rule_id.split('-')[1]) + 10:03d}"
                if partner_id in self.rules:
                    rule.brake_pair_id = partner_id
                    self.brake_pairs[rule_id] = BrakePair(
                        primary_rule_id=rule_id,
                        brake_rule_id=partner_id,
                    )
                continue

            # 无制动 — 创建姊妹制动规则
            brake_id = f"MR-{brake_counter:03d}"
            brake_counter += 1

            brake_name = f"{rule.name}_brake"
            brake_rule = RuleState(
                rule_id=brake_id,
                name=brake_name,
                category="brake",
                strength=0.50,  # 制动规则初始强度居中
                has_brake=False,
            )
            self.rules[brake_id] = brake_rule

            # 建立双向关联
            rule.has_brake = True
            rule.brake_pair_id = brake_id

            self.brake_pairs[rule_id] = BrakePair(
                primary_rule_id=rule_id,
                brake_rule_id=brake_id,
            )

    def evaluate(self, current_strengths: Optional[Dict[str, float]] = None,
                 etg_active: bool = False) -> Dict:
        """
        执行一个评估周期

        参数:
          current_strengths: 当前各规则的 strength 值 (可选, 用于外部数据注入)
          etg_active: 是否处于 ETG (临界转换) 期间

        返回:
          评估报告 dict
        """
        self.session_count += 1
        self.etg_in_progress = etg_active

        # 更新规则强度 (如果提供了外部数据)
        if current_strengths:
            for rid, strength in current_strengths.items():
                if rid in self.rules:
                    self.rules[rid].strength = strength

        actions_taken: List[Dict] = []
        brake_status: Dict[str, str] = {}

        for primary_id, pair in self.brake_pairs.items():
            primary_rule = self.rules.get(primary_id)
            if not primary_rule:
                continue

            # 增加冷却计数器
            pair.sessions_since_last_brake += 1
            pair.sessions_since_last_release += 1

            strength = primary_rule.strength
            previous_status = "braked" if pair.brake_active else "normal"

            # === ETG 期间调整阈值 ===
            # 临界点附近, 制动阈值降低 — 更敏感地检测自调节悖论
            active_threshold = BRAKE_ACTIVATION_THRESHOLD - 0.05 if etg_active else BRAKE_ACTIVATION_THRESHOLD
            release_threshold = BRAKE_RELEASE_THRESHOLD + 0.05 if etg_active else BRAKE_RELEASE_THRESHOLD

            # === 制动激活逻辑 ===
            if (strength > active_threshold
                    and not pair.brake_active
                    and pair.sessions_since_last_brake >= BRAKE_COOLDOWN_SESSIONS):

                pair.brake_active = True
                pair.sessions_since_last_brake = 0

                # 执行制动: 降权
                new_strength = max(strength - BRAKE_STEP_DOWN, active_threshold - 0.01)
                primary_rule.strength = new_strength

                action_record = {
                    "action": "brake_activated",
                    "rule_id": primary_id,
                    "brake_rule_id": pair.brake_rule_id,
                    "old_strength": strength,
                    "new_strength": new_strength,
                    "session": self.session_count,
                    "etg_active": etg_active,
                    "reason": (
                        f"强度 {strength:.2f} 超过制动阈值 {active_threshold:.2f}"
                        f"{' (ETG期间阈值下调)' if etg_active else ''}"
                    ),
                }
                pair.brake_history.append(action_record)
                actions_taken.append(action_record)

            # === 制动释放逻辑 ===
            elif (strength < release_threshold
                  and pair.brake_active
                  and pair.sessions_since_last_release >= BRAKE_COOLDOWN_SESSIONS):

                pair.brake_active = False
                pair.sessions_since_last_release = 0

                # 执行释放: 缓慢升权
                new_strength = min(strength + BRAKE_STEP_UP, release_threshold + 0.01)
                primary_rule.strength = new_strength

                action_record = {
                    "action": "brake_released",
                    "rule_id": primary_id,
                    "brake_rule_id": pair.brake_rule_id,
                    "old_strength": strength,
                    "new_strength": new_strength,
                    "session": self.session_count,
                    "reason": (
                        f"强度 {strength:.2f} 低于释放阈值 {release_threshold:.2f}"
                        f"{' (ETG期间阈值上调)' if etg_active else ''}"
                    ),
                }
                pair.brake_history.append(action_record)
                actions_taken.append(action_record)

            # 记录状态
            current_status = "braked" if pair.brake_active else "normal"
            if current_status != previous_status:
                brake_status[primary_id] = f"{previous_status} → {current_status}"
            else:
                brake_status[primary_id] = current_status

        return {
            "session": self.session_count,
            "etg_active": etg_active,
            "total_rules": len(self.rules),
            "total_brake_pairs": len(self.brake_pairs),
            "actions_taken": actions_taken,
            "brake_status": brake_status,
            "active_brakes": sum(1 for p in self.brake_pairs.values() if p.brake_active),
        }

    def generate_brake_coverage_heatmap(self) -> Dict:
        """
        生成制动覆盖度热图

        对每条元规则评估:
        - 是否有制动机制 (has_brake)
        - 当前是否被制动 (is_braked)
        - 制动覆盖度评分: 0.0 (无制动) ~ 1.0 (有制动且正常)
        - 关键种风险: 高strength + 无制动 = 高风险
        """
        heatmap = []
        for rule_id, rule in self.rules.items():
            if rule.category == "brake":
                continue  # 制动规则本身不纳入热图

            has_brake = rule.has_brake
            is_braked = False
            brake_pair = self.brake_pairs.get(rule_id)

            if brake_pair:
                is_braked = brake_pair.brake_active

            # 制动覆盖度: 有制动=基础0.6, 未被制动=+0.2, 强度适中=+0.2
            coverage_score = 0.0
            if has_brake:
                coverage_score += 0.6
            if not is_braked:
                coverage_score += 0.2
            if 0.35 <= rule.strength <= 0.80:
                coverage_score += 0.2

            # 关键种风险指数 (0-1, 越高越危险)
            # 风险 = 高强度 × (1 - 覆盖度)
            keystone_risk = rule.strength * (1.0 - coverage_score)

            heatmap.append({
                "rule_id": rule_id,
                "name": rule.name,
                "category": rule.category,
                "strength": round(rule.strength, 2),
                "has_brake": has_brake,
                "is_braked": is_braked,
                "brake_coverage": round(coverage_score, 2),
                "keystone_risk": round(keystone_risk, 2),
                "risk_level": (
                    "CRITICAL" if keystone_risk > 0.5 else
                    "HIGH" if keystone_risk > 0.3 else
                    "MEDIUM" if keystone_risk > 0.15 else
                    "LOW"
                ),
            })

        # 按关键种风险降序排列
        heatmap.sort(key=lambda x: x["keystone_risk"], reverse=True)

        return {
            "timestamp": datetime.now().isoformat(),
            "session": self.session_count,
            "total_rules_evaluated": len(heatmap),
            "rules": heatmap,
            "summary": {
                "critical_count": sum(1 for h in heatmap if h["risk_level"] == "CRITICAL"),
                "high_count": sum(1 for h in heatmap if h["risk_level"] == "HIGH"),
                "medium_count": sum(1 for h in heatmap if h["risk_level"] == "MEDIUM"),
                "low_count": sum(1 for h in heatmap if h["risk_level"] == "LOW"),
                "avg_brake_coverage": round(
                    sum(h["brake_coverage"] for h in heatmap) / len(heatmap), 2
                ),
            },
        }

    def get_brake_pair_analysis(self) -> List[Dict]:
        """获取所有制动对的详细分析"""
        analysis = []
        for primary_id, pair in self.brake_pairs.items():
            primary = self.rules.get(primary_id)
            brake = self.rules.get(pair.brake_rule_id)
            if not primary:
                continue

            analysis.append({
                "primary_rule_id": primary_id,
                "primary_name": primary.name,
                "primary_strength": round(primary.strength, 2),
                "brake_rule_id": pair.brake_rule_id,
                "brake_name": brake.name if brake else "N/A",
                "brake_active": pair.brake_active,
                "sessions_since_last_action": min(
                    pair.sessions_since_last_brake,
                    pair.sessions_since_last_release,
                ),
                "history_actions": len(pair.brake_history),
                "last_action": pair.brake_history[-1]["action"] if pair.brake_history else "none",
            })

        return analysis


# ============================================================
# 命令行接口
# ============================================================

def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="INSP-022 姊妹制动规则系统 — 为每条增强规则配备自动制动机制",
    )
    parser.add_argument(
        "--rules-config", type=str, default=None,
        help="外部规则配置 JSON 文件路径"
    )
    parser.add_argument(
        "--output", type=str, default=None,
        help="输出报告 JSON 文件路径"
    )
    parser.add_argument(
        "--simulate-sessions", type=int, default=10,
        help="模拟的会话周期数 (默认 10)"
    )
    parser.add_argument(
        "--etg-sessions", type=str, default="4,8",
        help="以逗号分隔的 ETG 触发会话编号 (如: '4,8')"
    )

    args = parser.parse_args()

    # 载入外部配置
    rules_config = None
    if args.rules_config:
        config_path = Path(args.rules_config)
        if config_path.exists():
            rules_config = json.loads(config_path.read_text(encoding="utf-8"))

    # 解析 ETG 会话
    etg_sessions = set()
    if args.etg_sessions:
        etg_sessions = {int(s.strip()) for s in args.etg_sessions.split(",") if s.strip().isdigit()}

    # 初始化系统
    system = SisterBrakeSystem(rules_config)

    print("=" * 70)
    print("  INSP-022: 姊妹制动规则系统")
    print("  来源: Colony-016 生态学自调节悖论 → 元规则制动机制")
    print("=" * 70)
    print(f"\n初始化完成:")
    print(f"  元规则总数: {len(system.rules)}")
    print(f"  制动对数量: {len(system.brake_pairs)}")
    print(f"  制动激活阈值: {BRAKE_ACTIVATION_THRESHOLD}")
    print(f"  制动释放阈值: {BRAKE_RELEASE_THRESHOLD}")
    print(f"  制动冷却期: {BRAKE_COOLDOWN_SESSIONS} 会话")

    # 输出初始制动覆盖度热图
    print(f"\n{'=' * 70}")
    print("  初始制动覆盖度热图 (模拟前)")
    print("=" * 70)
    initial_heatmap = system.generate_brake_coverage_heatmap()
    print(f"\n{'规则ID':<10} {'名称':<28} {'强度':<8} {'有制动':<8} {'覆盖度':<8} {'关键种风险':<12} {'风险等级'}")
    print("-" * 90)
    for rule in initial_heatmap["rules"]:
        print(
            f"{rule['rule_id']:<10} {rule['name']:<28} {rule['strength']:<8.2f} "
            f"{'是' if rule['has_brake'] else '否':<8} {rule['brake_coverage']:<8.2f} "
            f"{rule['keystone_risk']:<12.2f} {rule['risk_level']}"
        )
    print(f"\n汇总: CRITICAL={initial_heatmap['summary']['critical_count']}, "
          f"HIGH={initial_heatmap['summary']['high_count']}, "
          f"MEDIUM={initial_heatmap['summary']['medium_count']}, "
          f"LOW={initial_heatmap['summary']['low_count']}")

    # 模拟运行多个会话周期
    print(f"\n{'=' * 70}")
    print(f"  模拟运行 {args.simulate_sessions} 个会话周期")
    print("=" * 70)

    all_reports = []
    for session in range(1, args.simulate_sessions + 1):
        is_etg = session in etg_sessions

        # 模拟强度变化: 部分规则强度逐渐上升 (模拟过拟合)
        simulated_strengths = {}
        for rid, rule in system.rules.items():
            # 添加一些随机漂移
            drift = (hash(f"{rid}_{session}") % 100) / 500.0 - 0.1  # -0.1 ~ 0.1
            new_s = max(0.1, min(1.0, rule.strength + drift))
            simulated_strengths[rid] = new_s

        report = system.evaluate(simulated_strengths, etg_active=is_etg)
        all_reports.append(report)

        etg_marker = " [ETG!]" if is_etg else ""
        if report["actions_taken"]:
            for action in report["actions_taken"]:
                print(f"\n  会话 {session:02d}{etg_marker}: "
                      f"{action['rule_id']} {action['action']} "
                      f"({action['old_strength']:.2f}→{action['new_strength']:.2f})")
                print(f"    原因: {action['reason']}")

    # 最终热图
    print(f"\n{'=' * 70}")
    print("  最终制动覆盖度热图 (模拟后)")
    print("=" * 70)
    final_heatmap = system.generate_brake_coverage_heatmap()
    print(f"\n{'规则ID':<10} {'名称':<28} {'强度':<8} {'有制动':<8} {'覆盖度':<8} {'关键种风险':<12} {'风险等级'}")
    print("-" * 90)
    for rule in final_heatmap["rules"]:
        print(
            f"{rule['rule_id']:<10} {rule['name']:<28} {rule['strength']:<8.2f} "
            f"{'是' if rule['has_brake'] else '否':<8} {rule['brake_coverage']:<8.2f} "
            f"{rule['keystone_risk']:<12.2f} {rule['risk_level']}"
        )

    # 制动对分析
    print(f"\n{'=' * 70}")
    print("  制动对分析")
    print("=" * 70)
    pair_analysis = system.get_brake_pair_analysis()
    print(f"\n{'主规则':<10} {'主规则名':<28} {'强度':<8} {'制动规则':<10} {'制动激活':<10} {'历史动作数'}")
    print("-" * 80)
    for pa in pair_analysis:
        print(
            f"{pa['primary_rule_id']:<10} {pa['primary_name']:<28} "
            f"{pa['primary_strength']:<8.2f} {pa['brake_rule_id']:<10} "
            f"{'是' if pa['brake_active'] else '否':<10} {pa['history_actions']}"
        )

    # 汇总
    total_brake_actions = sum(len(r["actions_taken"]) for r in all_reports)
    print(f"\n{'=' * 70}")
    print(f"  模拟摘要")
    print(f"=" * 70)
    print(f"  总模拟会话: {args.simulate_sessions}")
    print(f"  ETG 触发会话: {sorted(etg_sessions)}")
    print(f"  总制动动作: {total_brake_actions}")
    print(f"  当前活跃制动数: {sum(1 for p in system.brake_pairs.values() if p.brake_active)}")

    # 输出文件
    if args.output:
        output_path = Path(args.output)
        output_data = {
            "inspiration_id": "INSP-20260519-022",
            "title": "姊妹制动规则系统",
            "timestamp": datetime.now().isoformat(),
            "configuration": {
                "brake_activation_threshold": BRAKE_ACTIVATION_THRESHOLD,
                "brake_release_threshold": BRAKE_RELEASE_THRESHOLD,
                "brake_step_down": BRAKE_STEP_DOWN,
                "brake_step_up": BRAKE_STEP_UP,
                "brake_cooldown_sessions": BRAKE_COOLDOWN_SESSIONS,
            },
            "initial_heatmap": initial_heatmap,
            "final_heatmap": final_heatmap,
            "pair_analysis": pair_analysis,
            "session_reports": all_reports,
        }
        output_path.write_text(json.dumps(output_data, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"\n  输出文件已写入: {output_path}")

    print(f"\n{'=' * 70}")
    print("  执行完成。")
    print("=" * 70)


if __name__ == "__main__":
    main()
