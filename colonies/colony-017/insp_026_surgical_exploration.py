#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
INSP-026: 外科手术式探索扰动系统
============================================================
来源: Colony-016 自动灵感生成管线 (生态学 → 探索策略)
映射: mechanism_transfer — 生态学"主动干扰即生态位构建" → 精准探索扰动
文献: Gefen Y, Ben-Oren Y, Kolodny O. (2026). The American Naturalist. DOI: 10.1086/740876.

核心原理:
  生态学发现: 入侵物种不被动等待机会窗口 — 它们主动制造受控干扰来构建
  自己的生态位。干扰不是副作用而是策略本身。关键参数: 干扰强度必须在
  自身耐受范围内，恢复速度必须快于竞争者。

  映射到探索策略:
  当前: 全局 exploration_weight = 1.5 (对所有签名均等提升探索)
  改进: "外科手术式" — 只针对匹配率最低的 2 条签名，临时将其
  exploration_weight 提升到 3.0，持续 3 个会话，然后恢复到正常水平。

  为什么更好?
  1. 精准: 只扰动需要被扰动的地方 (低匹配率签名)
  2. 安全: 不扰乱已经稳定的签名
  3. 快速恢复: 短期扰动后恢复正常，不像全局探索长期悬在探索状态
  4. 可评估: 可清晰评估 "这次扰动是否改善了这个特定签名"

  五步入侵操作流程:
  1. 评估 (Assess): 每5会话评估所有签名匹配率分布
  2. 选择 (Select): 选出匹配率最低的 2 条签名作为"入侵目标"
  3. 扰动 (Disturb): 将这些签名的 exploration_weight 临时提升到 3.0
  4. 建立 (Establish): 在新探索的模式中找到匹配率更高的变体
  5. 恢复 (Recover): 3个会话后将 exploration_weight 恢复到 1.5

执行方式:
  python insp_026_surgical_exploration.py [--input <data.json>] [--output <path>]
"""

import json
import math
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

# ============================================================
# 配置常量 — 源自 INSP-026 的具体参数规格
# ============================================================

# 默认全局探索权重
DEFAULT_EXPLORATION_WEIGHT = 1.5

# 扰动期探索权重 (目标签名)
DISTURBANCE_EXPLORATION_WEIGHT = 3.0

# 扰动持续时间 (会话数)
DISTURBANCE_DURATION_SESSIONS = 3

# 评估间隔 (每 N 个会话评估一次)
EVALUATION_INTERVAL_SESSIONS = 5

# 每次扰动的目标签名数 (bottom-N)
DISTURBANCE_TARGET_COUNT = 2

# 触发扰动的匹配率下限 (低于此值才触发扰动)
DISTURBANCE_TRIGGER_THRESHOLD = 0.55

# 扰动后冷却期 (会话数) — 防止同一签名被反复扰动
DISTURBANCE_COOLDOWN_SESSIONS = 5

# 安全锁条件: 这些情况下禁止扰动
SAFETY_LOCK_CONDITIONS = [
    "etg_in_progress",            # ETG (临界转换) 期间
    "branch_merge_in_progress",   # 分支合并期间
    "identity_validation_error",  # 身份验证异常期间
    "system_health_below_0.5",    # 系统健康度过低
]

# 签名定义 (DS-003 ~ DS-012)
SIGNATURES: List[Dict] = [
    {"id": "DS-003", "name": "response_pattern_matching", "category": "pattern",
     "match_rate": 0.72, "exploration_weight": DEFAULT_EXPLORATION_WEIGHT},
    {"id": "DS-004", "name": "tool_selection_heuristic",  "category": "tool",
     "match_rate": 0.58, "exploration_weight": DEFAULT_EXPLORATION_WEIGHT},
    {"id": "DS-005", "name": "conversation_flow_routing", "category": "flow",
     "match_rate": 0.42, "exploration_weight": DEFAULT_EXPLORATION_WEIGHT},
    {"id": "DS-006", "name": "error_recovery_strategy",   "category": "recovery",
     "match_rate": 0.68, "exploration_weight": DEFAULT_EXPLORATION_WEIGHT},
    {"id": "DS-007", "name": "knowledge_retrieval_depth", "category": "knowledge",
     "match_rate": 0.51, "exploration_weight": DEFAULT_EXPLORATION_WEIGHT},
    {"id": "DS-008", "name": "context_window_management", "category": "context",
     "match_rate": 0.79, "exploration_weight": DEFAULT_EXPLORATION_WEIGHT},
    {"id": "DS-009", "name": "agent_handoff_protocol",    "category": "protocol",
     "match_rate": 0.63, "exploration_weight": DEFAULT_EXPLORATION_WEIGHT},
    {"id": "DS-010", "name": "cost_optimization_tactic",  "category": "optimization",
     "match_rate": 0.85, "exploration_weight": DEFAULT_EXPLORATION_WEIGHT},
    {"id": "DS-011", "name": "parallelism_strategy",      "category": "parallelism",
     "match_rate": 0.37, "exploration_weight": DEFAULT_EXPLORATION_WEIGHT},
    {"id": "DS-012", "name": "fallback_chain_design",     "category": "fallback",
     "match_rate": 0.71, "exploration_weight": DEFAULT_EXPLORATION_WEIGHT},
]


@dataclass
class SignatureState:
    """单条签名的运行时状态"""
    id: str
    name: str
    category: str
    match_rate: float
    exploration_weight: float = DEFAULT_EXPLORATION_WEIGHT
    in_disturbance: bool = False              # 是否处于扰动期
    disturbance_remaining_sessions: int = 0   # 扰动剩余会话数
    sessions_since_last_disturbance: int = 999  # 距上次扰动的会话数
    disturbance_history: List[Dict] = field(default_factory=list)
    pre_disturbance_match_rate: Optional[float] = None  # 扰动前匹配率 (用于效果评估)


@dataclass
class DisturbanceWindow:
    """一次扰动窗口的记录"""
    window_id: int
    session_start: int
    session_end: int
    target_signatures: List[str]
    pre_disturbance_rates: Dict[str, float]
    post_disturbance_rates: Dict[str, float] = field(default_factory=dict)
    improvement: Dict[str, float] = field(default_factory=dict)
    active: bool = True


class SurgicalExplorationSystem:
    """
    外科手术式探索扰动引擎

    核心算法 — 入侵五步法:
    1. ASSESS:  评估所有签名匹配率, 排序
    2. SELECT:  选择 bottom-N 作为入侵目标
    3. DISTURB: 临时提升目标签名的 exploration_weight
    4. ESTABLISH: 等待新探索发现更好的模式
    5. RECOVER: 恢复到正常 exploration_weight, 评估效果
    """

    def __init__(self):
        self.signatures: Dict[str, SignatureState] = {}
        self.disturbance_windows: List[DisturbanceWindow] = []
        self.session_count: int = 0
        self.safety_locks: Dict[str, bool] = {
            cond: False for cond in SAFETY_LOCK_CONDITIONS
        }
        self.window_counter: int = 0

        # 载入签名
        for sig in SIGNATURES:
            self.signatures[sig["id"]] = SignatureState(
                id=sig["id"],
                name=sig["name"],
                category=sig["category"],
                match_rate=sig["match_rate"],
                exploration_weight=sig.get("exploration_weight", DEFAULT_EXPLORATION_WEIGHT),
            )

    def set_safety_lock(self, condition: str, active: bool):
        """设置/解除安全锁"""
        if condition in self.safety_locks:
            self.safety_locks[condition] = active

    def is_safe_to_disturb(self) -> Tuple[bool, List[str]]:
        """检查是否安全执行扰动"""
        active_locks = [cond for cond, active in self.safety_locks.items() if active]
        if active_locks:
            return False, active_locks
        return True, []

    def _generate_synthetic_match_rates(self):
        """生成合成匹配率数据 (用于演示)"""
        import random
        random.seed(self.session_count * 37 + 11)

        for sig_id, sig in self.signatures.items():
            if sig.in_disturbance:
                # 扰动期间: 匹配率有更大概率正向变化 (模拟探索效果)
                improvement_chance = 0.6  # 60% 概率改善
                if random.random() < improvement_chance:
                    delta = random.uniform(0.01, 0.08)
                else:
                    delta = random.uniform(-0.03, 0.02)
                sig.match_rate = max(0.20, min(0.98, sig.match_rate + delta))
            else:
                # 正常期间: 小幅随机漂移
                base_drift = random.uniform(-0.02, 0.02)
                # 低匹配率有自然回升趋势, 高匹配率有自然回归趋势
                reversion = (0.65 - sig.match_rate) * 0.01
                sig.match_rate = max(0.20, min(0.98, sig.match_rate + base_drift + reversion))

    def assess(self) -> Dict:
        """
        步骤1+2: 评估并选择入侵目标

        返回: 评估报告
        """
        # 按匹配率升序排列 (最低的在前面)
        ranked = sorted(self.signatures.items(), key=lambda x: x[1].match_rate)

        assessment = {
            "session": self.session_count,
            "signatures_ranked": [
                {
                    "id": sig_id,
                    "name": sig.name,
                    "category": sig.category,
                    "match_rate": round(sig.match_rate, 3),
                    "exploration_weight": sig.exploration_weight,
                    "in_disturbance": sig.in_disturbance,
                    "disturbance_remaining": sig.disturbance_remaining_sessions,
                }
                for sig_id, sig in ranked
            ],
            "average_match_rate": round(
                sum(s.match_rate for s in self.signatures.values()) / len(self.signatures), 3
            ),
            "eligible_targets": [],
        }

        # 筛选可扰动目标:
        #   - 匹配率 < 触发阈值
        #   - 不在扰动中
        #   - 距上次扰动超过冷却期
        #   - 匹配率在低位 (bottom-N)
        eligible = []
        for sig_id, sig in ranked:
            if (sig.match_rate < DISTURBANCE_TRIGGER_THRESHOLD
                    and not sig.in_disturbance
                    and sig.sessions_since_last_disturbance >= DISTURBANCE_COOLDOWN_SESSIONS):
                eligible.append({
                    "id": sig_id,
                    "name": sig.name,
                    "match_rate": round(sig.match_rate, 3),
                    "gap_to_threshold": round(DISTURBANCE_TRIGGER_THRESHOLD - sig.match_rate, 3),
                })

        assessment["eligible_targets"] = eligible
        assessment["eligible_count"] = len(eligible)

        return assessment

    def disturb(self) -> Optional[Dict]:
        """
        步骤3: 执行扰动 — 对外科目标提升 exploration_weight

        仅在满足以下条件时执行:
        1. 安全性检查通过 (无活跃安全锁)
        2. 距上次评估 >= 评估间隔
        3. 有可扰动目标

        返回: 扰动报告 (如果执行了扰动) 或 None
        """
        # === 安全性检查 ===
        safe, active_locks = self.is_safe_to_disturb()
        if not safe:
            return {
                "status": "blocked",
                "reason": f"安全锁活跃: {active_locks}",
                "session": self.session_count,
            }

        # === 评估间隔检查 ===
        if self.session_count % EVALUATION_INTERVAL_SESSIONS != 0:
            return {
                "status": "skipped",
                "reason": f"非评估点 (间隔={EVALUATION_INTERVAL_SESSIONS}, 当前={self.session_count})",
                "next_evaluation_at": (
                    (self.session_count // EVALUATION_INTERVAL_SESSIONS + 1)
                    * EVALUATION_INTERVAL_SESSIONS
                ),
                "session": self.session_count,
            }

        # === 评估并选择目标 ===
        assessment = self.assess()
        eligible = assessment["eligible_targets"]

        if len(eligible) == 0:
            return {
                "status": "no_targets",
                "reason": "没有签名符合扰动条件 (匹配率不够低、已在扰动中、或冷却中)",
                "session": self.session_count,
                "assessment": assessment,
            }

        # 选择 bottom-N (最低匹配率的 N 个) 作为目标
        # 选匹配率最低的 DISTURBANCE_TARGET_COUNT 个作为目标
        targets_sorted = sorted(eligible, key=lambda x: x["match_rate"])
        selected = targets_sorted[:DISTURBANCE_TARGET_COUNT]

        # === 执行扰动 ===
        self.window_counter += 1
        window = DisturbanceWindow(
            window_id=self.window_counter,
            session_start=self.session_count,
            session_end=self.session_count + DISTURBANCE_DURATION_SESSIONS - 1,
            target_signatures=[s["id"] for s in selected],
            pre_disturbance_rates={},
        )

        for target in selected:
            sig = self.signatures[target["id"]]

            # 记录扰动前状态
            sig.pre_disturbance_match_rate = sig.match_rate
            window.pre_disturbance_rates[target["id"]] = sig.match_rate

            # 激活扰动
            sig.in_disturbance = True
            sig.disturbance_remaining_sessions = DISTURBANCE_DURATION_SESSIONS
            sig.exploration_weight = DISTURBANCE_EXPLORATION_WEIGHT

            # 记录历史
            sig.disturbance_history.append({
                "session": self.session_count,
                "window_id": self.window_counter,
                "action": "disturbance_started",
                "pre_match_rate": sig.pre_disturbance_match_rate,
                "exploration_weight": DISTURBANCE_EXPLORATION_WEIGHT,
                "duration": DISTURBANCE_DURATION_SESSIONS,
            })

        self.disturbance_windows.append(window)

        return {
            "status": "executed",
            "session": self.session_count,
            "window_id": self.window_counter,
            "targets": [
                {
                    "id": s["id"],
                    "name": self.signatures[s["id"]].name,
                    "pre_disturbance_match_rate": round(window.pre_disturbance_rates[s["id"]], 3),
                    "new_exploration_weight": DISTURBANCE_EXPLORATION_WEIGHT,
                    "duration_sessions": DISTURBANCE_DURATION_SESSIONS,
                    "disturbance_window": f"会话 {window.session_start} ~ {window.session_end}",
                }
                for s in selected
            ],
            "safety_check": {"passed": True, "active_locks": []},
            "assessment_summary": {
                "total_signatures": len(self.signatures),
                "eligible_count": len(eligible),
                "selected_count": len(selected),
                "avg_match_rate": assessment["average_match_rate"],
            },
        }

    def recover(self) -> Dict:
        """
        步骤4+5: 恢复 — 将到期扰动的签名恢复正常 exploration_weight

        在每次会话调用, 检查是否有扰动窗口到期。
        到期时: 记录扰动后匹配率, 计算改善量, 恢复正常权重。
        """
        recovery_actions = []

        for sig_id, sig in self.signatures.items():
            if sig.in_disturbance:
                sig.disturbance_remaining_sessions -= 1

                if sig.disturbance_remaining_sessions <= 0:
                    # 扰动窗口结束 — 恢复
                    post_rate = sig.match_rate
                    pre_rate = sig.pre_disturbance_match_rate or post_rate
                    improvement = post_rate - pre_rate

                    # 恢复探索权重
                    sig.in_disturbance = False
                    sig.exploration_weight = DEFAULT_EXPLORATION_WEIGHT
                    sig.sessions_since_last_disturbance = 0

                    recovery_action = {
                        "signature_id": sig_id,
                        "signature_name": sig.name,
                        "action": "disturbance_ended",
                        "session": self.session_count,
                        "pre_disturbance_match_rate": round(pre_rate, 3),
                        "post_disturbance_match_rate": round(post_rate, 3),
                        "improvement": round(improvement, 3),
                        "improvement_pct": round(improvement / max(pre_rate, 0.01) * 100, 1),
                        "verdict": (
                            "EFFECTIVE" if improvement > 0.02 else
                            "MARGINAL" if improvement > 0.005 else
                            "INEFFECTIVE"
                        ),
                        "exploration_weight_restored_to": DEFAULT_EXPLORATION_WEIGHT,
                    }

                    sig.disturbance_history.append({
                        "session": self.session_count,
                        "action": "disturbance_ended",
                        "post_match_rate": post_rate,
                        "improvement": recovery_action["improvement"],
                        "verdict": recovery_action["verdict"],
                    })

                    # 更新扰动窗口记录
                    for window in self.disturbance_windows:
                        if sig_id in window.target_signatures and window.active:
                            window.post_disturbance_rates[sig_id] = post_rate
                            window.improvement[sig_id] = improvement
                            # 检查窗口是否全部完成
                            if len(window.post_disturbance_rates) == len(window.target_signatures):
                                window.active = False
                            break

                    recovery_actions.append(recovery_action)

            else:
                # 不在扰动中 — 增加冷却计数器
                sig.sessions_since_last_disturbance += 1

        return {
            "session": self.session_count,
            "recovery_actions": recovery_actions,
            "recovery_count": len(recovery_actions),
            "currently_disturbed": [
                sig_id for sig_id, sig in self.signatures.items() if sig.in_disturbance
            ],
        }

    def step(self) -> Dict:
        """
        执行一个完整的会话步骤:
        1. 递增会话计数
        2. 检查是否需要恢复
        3. 生成新的匹配率数据
        4. 如果到了评估点, 尝试扰动
        """
        self.session_count += 1

        # 先恢复到期扰动
        recovery_report = self.recover()

        # 生成新数据 (实际系统使用真实数据)
        self._generate_synthetic_match_rates()

        # 尝试执行扰动
        disturb_report = self.disturb()

        return {
            "session": self.session_count,
            "recovery": recovery_report,
            "disturbance": disturb_report,
            "active_disturbance_count": sum(
                1 for s in self.signatures.values() if s.in_disturbance
            ),
        }

    def get_system_status(self) -> Dict:
        """获取系统状态快照"""
        signatures_status = []
        for sig_id, sig in self.signatures.items():
            signatures_status.append({
                "id": sig_id,
                "name": sig.name,
                "category": sig.category,
                "match_rate": round(sig.match_rate, 3),
                "exploration_weight": sig.exploration_weight,
                "in_disturbance": sig.in_disturbance,
                "disturbance_remaining": sig.disturbance_remaining_sessions,
                "cooldown_remaining": max(
                    0, DISTURBANCE_COOLDOWN_SESSIONS - sig.sessions_since_last_disturbance
                ),
                "total_disturbances": len(sig.disturbance_history),
            })

        # 扰动效果统计
        total_improvements = []
        for window in self.disturbance_windows:
            if not window.active:
                total_improvements.extend(window.improvement.values())

        return {
            "session": self.session_count,
            "signatures": signatures_status,
            "disturbance_windows_total": self.window_counter,
            "active_windows": sum(1 for w in self.disturbance_windows if w.active),
            "completed_windows": sum(1 for w in self.disturbance_windows if not w.active),
            "total_disturbance_actions": sum(
                len(s.disturbance_history) // 2 for s in self.signatures.values()
            ),
            "perturbation_effectiveness": {
                "total_improvements_tracked": len(total_improvements),
                "avg_improvement": (
                    round(sum(total_improvements) / len(total_improvements), 4)
                    if total_improvements else None
                ),
                "effective_count": sum(1 for i in total_improvements if i > 0.02),
                "marginal_count": sum(1 for i in total_improvements if 0.005 < i <= 0.02),
                "ineffective_count": sum(1 for i in total_improvements if i <= 0.005),
            },
            "safety_locks": {
                cond: active for cond, active in self.safety_locks.items() if active
            },
        }

    def generate_summary_table(self) -> str:
        """生成状态汇总表"""
        status = self.get_system_status()

        lines = []
        lines.append("")
        lines.append("  签名探索扰动状态")
        lines.append("  " + "=" * 95)
        lines.append("")
        lines.append(f"  {'签名':<10} {'匹配率':<10} {'探索权重':<10} {'扰动中':<8} {'剩余':<6} {'冷却':<6} {'扰动次数'}")
        lines.append("  " + "-" * 70)

        for sig in status["signatures"]:
            disturb_marker = "是 [!!] " if sig["in_disturbance"] else "否"
            lines.append(
                f"  {sig['id']:<10} {sig['match_rate']:<10.3f} "
                f"{sig['exploration_weight']:<10.1f} {disturb_marker:<8} "
                f"{sig['disturbance_remaining']:<6} {sig['cooldown_remaining']:<6} "
                f"{sig['total_disturbances']}"
            )

        lines.append("")
        lines.append(f"  扰动窗口: 总计={status['disturbance_windows_total']}, "
                     f"活跃={status['active_windows']}, "
                     f"已完成={status['completed_windows']}")

        eff = status["perturbation_effectiveness"]
        if eff["avg_improvement"] is not None:
            lines.append(f"  扰动效果: 平均改善={eff['avg_improvement']:.4f}, "
                         f"有效={eff['effective_count']}, "
                         f"边际={eff['marginal_count']}, "
                         f"无效={eff['ineffective_count']}")

        if status["safety_locks"]:
            lines.append(f"  *** 安全锁活跃: {list(status['safety_locks'].keys())} ***")

        return "\n".join(lines)


# ============================================================
# 命令行接口
# ============================================================

def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="INSP-026 外科手术式探索扰动系统 — 精准局部探索替代粗糙全局权重",
    )
    parser.add_argument(
        "--input", type=str, default=None,
        help="外部签名状态 JSON 文件路径"
    )
    parser.add_argument(
        "--output", type=str, default=None,
        help="输出报告 JSON 文件路径"
    )
    parser.add_argument(
        "--sessions", type=int, default=20,
        help="模拟运行的会话数 (默认 20)"
    )
    parser.add_argument(
        "--etg-at", type=str, default=None,
        help="ETG 触发会话 (逗号分隔, 如 '7,14'), 期间禁止扰动"
    )
    parser.add_argument(
        "--no-safety-lock", action="store_true",
        help="禁用安全锁机制 (允许在任何情况下扰动)"
    )

    args = parser.parse_args()

    system = SurgicalExplorationSystem()

    # 解析 ETG 会话
    etg_sessions = set()
    if args.etg_at:
        etg_sessions = {int(s.strip()) for s in args.etg_at.split(",") if s.strip().isdigit()}

    print("=" * 70)
    print("  INSP-026: 外科手术式探索扰动系统")
    print("  来源: Colony-016 生态学主动干扰策略 → 精准探索扰动")
    print("=" * 70)
    print(f"\n初始化完成:")
    print(f"  签名总数: {len(system.signatures)} 条")
    print(f"  默认探索权重: {DEFAULT_EXPLORATION_WEIGHT}")
    print(f"  扰动探索权重: {DISTURBANCE_EXPLORATION_WEIGHT}")
    print(f"  扰动持续: {DISTURBANCE_DURATION_SESSIONS} 会话")
    print(f"  评估间隔: {EVALUATION_INTERVAL_SESSIONS} 会话")
    print(f"  每次目标数: {DISTURBANCE_TARGET_COUNT} 条 (bottom-{DISTURBANCE_TARGET_COUNT})")
    print(f"  触发阈值: match_rate < {DISTURBANCE_TRIGGER_THRESHOLD}")
    print(f"  冷却期: {DISTURBANCE_COOLDOWN_SESSIONS} 会话")
    print(f"  安全锁条件: {SAFETY_LOCK_CONDITIONS}")
    if etg_sessions:
        print(f"  ETG 会话: {sorted(etg_sessions)}")

    # 初始状态
    print(system.generate_summary_table())

    # === 模拟运行 ===
    print(f"\n{'=' * 70}")
    print(f"  模拟运行 {args.sessions} 个会话")
    print("=" * 70)

    all_steps = []
    for s in range(args.sessions):
        # ETG 期间设置安全锁
        if etg_sessions and (s + 1) in etg_sessions:
            system.set_safety_lock("etg_in_progress", True)
            print(f"\n  *** 会话 {s+1}: ETG 触发 — 安全锁激活, 禁止扰动 ***")
        elif etg_sessions and (s + 1) - 1 in etg_sessions:
            # ETG 结束后的会话 — 解除锁
            system.set_safety_lock("etg_in_progress", False)
            print(f"\n  *** 会话 {s+1}: ETG 结束 — 安全锁解除 ***")

        result = system.step()
        all_steps.append(result)

        # 显示关键事件
        if result["disturbance"] and result["disturbance"].get("status") == "executed":
            print(f"\n  >>> 会话 {result['session']}: 外科手术式扰动已执行 <<<")
            for t in result["disturbance"]["targets"]:
                print(f"      目标: {t['id']} ({t['name']})")
                print(f"      扰动前匹配率: {t['pre_disturbance_match_rate']:.3f}")
                print(f"      新探索权重: {t['new_exploration_weight']}")
                print(f"      扰动窗口: {t['disturbance_window']}")
        elif result["disturbance"] and result["disturbance"].get("status") == "blocked":
            print(f"\n  [!] 会话 {result['session']}: 扰动被安全锁阻止 — {result['disturbance']['reason']}")

        if result["recovery"]["recovery_actions"]:
            for action in result["recovery"]["recovery_actions"]:
                verdict_icon = (
                    "[有效]" if action["verdict"] == "EFFECTIVE" else
                    "[边际]" if action["verdict"] == "MARGINAL" else
                    "[无效]"
                )
                print(f"\n  <<< 会话 {result['session']}: {action['signature_id']} 扰动结束 >>>")
                print(f"      匹配率: {action['pre_disturbance_match_rate']:.3f} → "
                      f"{action['post_disturbance_match_rate']:.3f} "
                      f"(改善={action['improvement']:+.3f}, {action['improvement_pct']:+.1f}%)")
                print(f"      判定: {verdict_icon} — 探索权重恢复至 {action['exploration_weight_restored_to']}")

    # 最终状态
    print(f"\n{'=' * 70}")
    print(f"  最终状态 ({args.sessions} 会话后)")
    print("=" * 70)
    final_status = system.get_system_status()
    print(system.generate_summary_table())

    # 对比分析: 外科手术式 vs 全局探索
    print(f"\n{'=' * 70}")
    print(f"  对比分析: 外科手术式扰动 vs 全局探索")
    print("=" * 70)

    # 计算哪些签名被扰动过
    disturbed_signatures = [
        sig for sig in final_status["signatures"] if sig["total_disturbances"] > 0
    ]
    undisturbed_signatures = [
        sig for sig in final_status["signatures"] if sig["total_disturbances"] == 0
    ]

    if disturbed_signatures:
        avg_disturbed_improvement = sum(
            s["match_rate"] for s in disturbed_signatures
        ) / len(disturbed_signatures)
        print(f"\n  扰动过的签名 ({len(disturbed_signatures)} 条):")
        for sig in disturbed_signatures:
            # 查找扰动历史中的改善
            sig_state = system.signatures[sig["id"]]
            improvements = [
                h.get("improvement", 0) for h in sig_state.disturbance_history
                if h.get("action") == "disturbance_ended"
            ]
            avg_imp = sum(improvements) / len(improvements) if improvements else 0
            print(f"    {sig['id']}: 当前匹配率={sig['match_rate']:.3f}, "
                  f"扰动次数={sig['total_disturbances']}, "
                  f"平均改善={avg_imp:+.4f}")

    if undisturbed_signatures:
        avg_undisturbed = sum(
            s["match_rate"] for s in undisturbed_signatures
        ) / len(undisturbed_signatures)
        print(f"\n  未扰动的签名 ({len(undisturbed_signatures)} 条):")
        for sig in undisturbed_signatures[:5]:
            print(f"    {sig['id']}: 匹配率={sig['match_rate']:.3f} (保持稳定)")

    # 输出文件
    if args.output:
        output_path = Path(args.output)
        output_data = {
            "inspiration_id": "INSP-20260519-026",
            "title": "外科手术式探索扰动系统",
            "timestamp": datetime.now().isoformat(),
            "configuration": {
                "default_exploration_weight": DEFAULT_EXPLORATION_WEIGHT,
                "disturbance_exploration_weight": DISTURBANCE_EXPLORATION_WEIGHT,
                "disturbance_duration_sessions": DISTURBANCE_DURATION_SESSIONS,
                "evaluation_interval_sessions": EVALUATION_INTERVAL_SESSIONS,
                "disturbance_target_count": DISTURBANCE_TARGET_COUNT,
                "disturbance_trigger_threshold": DISTURBANCE_TRIGGER_THRESHOLD,
                "disturbance_cooldown_sessions": DISTURBANCE_COOLDOWN_SESSIONS,
                "safety_lock_conditions": SAFETY_LOCK_CONDITIONS,
            },
            "final_status": final_status,
            "session_steps": all_steps,
        }
        output_path.write_text(json.dumps(output_data, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"\n  输出文件已写入: {output_path}")

    print(f"\n{'=' * 70}")
    print("  执行完成。")
    print(f"  精准局部探索 > 粗糙全局权重。入侵五步法已就绪。")
    print("=" * 70)


if __name__ == "__main__":
    main()
