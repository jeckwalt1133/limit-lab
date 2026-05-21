#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
=============================================================================
Colony-039  L5 Hyperagents Auto-GE 自动化哥德尔引擎
=============================================================================
实现: 自动化哥德尔引擎(从事件触发到持续性循环) + 持久跨代记忆 + UCB探索 + 结构突变

设计依据:
  - Colony-034 colony-architecture-v2.md Section 6 (Layer 5 元认知自我修改层)
  - Colony-027 hyperagents-deep-study.md (DGM-H 两阶段循环 + 6项涌现能力)
  - Colony-021 godel-leap-execution.md (GE三步法 + 哥德尔盲点搜索)

架构:
  Auto-GE引擎由12个子系统组成，通过统一循环协同运转:

  触发检测 → Phase 1(状态快照+盲点搜索+公理生成)
           → Phase 2(安全门禁+沙箱验证+MR规则化)
           → 持久记忆写入 → 循环继续

  并行子系统: UCB-Merge探索奖励 / 结构突变注入 / 自动回滚 / 算力感知规划

运行方式:
  python auto-ge-engine.py                    # Demo模式 (使用模拟数据)
  python auto-ge-engine.py --config <path>    # 指定配置文件
  python auto-ge-engine.py --continuous       # 持续循环模式
  python auto-ge-engine.py --trigger-once     # 单次触发模式

作者: Colony-039 (极限实验室)
日期: 2026-05-19
版本: v1.0
=============================================================================
"""

import json
import os
import sys
import time
import math
import random
import hashlib
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from enum import Enum, auto
from typing import Optional, Callable
from collections import defaultdict
from pathlib import Path

# ============================================================================
# Part 0: 全局配置
# ============================================================================

@dataclass
class EngineConfig:
    """Auto-GE引擎全局配置"""
    # 路径
    memory_path: str = "memory/evolution-insights.json"
    lineage_path: str = "memory/lineage-tree.json"
    log_path: str = "logs/auto-ge-engine.log"
    sandbox_path: str = "sandbox/"

    # 触发阈值
    gs_composite_threshold: float = 2.0          # GS综合指数触发阈值
    delta_zero_consecutive: int = 5               # 连续Δ=0代数触发阈值
    min_gens_since_last_leap: int = 10            # 距上次哥德尔跳最小代数

    # 安全参数
    core_self_threshold: float = 0.95             # core_self兼容性最低阈值
    explosion_max_axioms_per_10gen: int = 3       # 每10代最多公理数
    explosion_freeze_gens: int = 30               # 熔断冻结代数
    rollback_degradation_window: int = 5          # 退化检测窗口
    rollback_decay_rate: float = 0.9              # 权重衰减率
    rollback_disable_threshold: float = 0.1       # 自动禁用阈值

    # UCB参数
    ucb_c_initial: float = 0.1                    # UCB探索系数初始值
    ucb_c_min: float = 0.01                       # UCB探索系数最小值
    ucb_c_max: float = 0.5                        # UCB探索系数最大值

    # 沙箱参数
    sandbox_generations: int = 5                  # 沙箱模拟代数
    sandbox_min_delta: float = 0.01               # 沙箱最低Δ阈值

    # 结构突变参数
    structure_base_mutation_rate: float = 0.05    # 基础结构突变率

    # 进化参数
    esv_dimensions: tuple = ("L5_SHI", "MEM_COMP", "SYNC_RATE", "PRED_ACC", "EXEC_GAP")
    esv_scale_max: float = 3.0                    # ESV量表上限
    esv_saturation_zone: float = 0.95             # 饱和区域阈值(95%*max)

    # 算力预算
    budget_abundant: float = 0.60                 # >60% 充足
    budget_moderate: float = 0.30                 # 30-60% 中等
    # <30% 紧张

    # LLM配置 (可插拔)
    llm_provider: str = "mock"                    # mock | claude | openai
    llm_model: str = "claude-sonnet-4-20250514"   # 反思用模型


# ============================================================================
# Part 1: 核心数据结构
# ============================================================================

class AxiomType(Enum):
    """公理类型分类"""
    D = "观察者重构"       # Observer Reconstruction
    A = "维度扩展"         # Dimensional Augmentation
    C = "系统边界扩展"     # System Boundary Extension
    T = "跨域迁移"         # Cross-domain Transfer


class MutationType(Enum):
    """结构突变类型"""
    LINEAR_TO_STATE_MACHINE = "linear_to_state_machine"
    SINGLETON_TO_ENSEMBLE = "singleton_to_ensemble"
    DISCRETE_TO_CONTINUOUS = "discrete_to_continuous"
    TREE_TO_GRAPH = "tree_to_graph"


class TriggerType(Enum):
    """Auto-GE触发类型"""
    GS_COMPOSITE = "gs_composite_high"           # GS综合指数超标
    DELTA_ZERO = "delta_zero_streak"             # 连续Δ=0
    TIME_SINCE_LEAP = "time_since_last_leap"     # 距上次跳跃过久
    EXTERNAL_CATALYST = "external_catalyst"      # 外部触媒信号


class GSCategory(Enum):
    """GS症候类别"""
    GS_001 = "评估坍塌"
    GS_002 = "收敛停滞"
    GS_003 = "外部不可吸收"
    GS_004 = "循环重复"
    GS_005 = "签名过稳定"


class SafetyGateLevel(Enum):
    """安全门禁级别"""
    HARD_BLOCK = "硬阻塞"     # 必须通过，否则拒绝
    SOFT_BLOCK = "软阻塞"     # 人工判定


class InsightStatus(Enum):
    """洞察状态"""
    VERIFIED = "verified"
    PENDING = "pending"
    FALSIFIED = "falsified"


class RuleStatus(Enum):
    """规则状态"""
    ACTIVE = "active"
    DEGRADING = "degrading"
    DISABLED = "disabled"
    FROZEN = "frozen"


class BudgetLevel(Enum):
    """算力预算级别"""
    ABUNDANT = "充足"     # >60%
    MODERATE = "中等"     # 30-60%
    TIGHT = "紧张"        # <30%


# ---- ESV记录 ----

@dataclass
class ESVRecord:
    """单代进化状态向量记录"""
    gen: int
    dimensions: dict[str, float]    # {dim_name: score}
    deltas: dict[str, float]        # {dim_name: Δ}
    timestamp: str = ""
    notes: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()


# ---- GS症候 ----

@dataclass
class GSScore:
    """单个GS症候评分"""
    category: str                    # GS-001 ~ GS-005
    score: float                     # 0.0 ~ 3.0
    sub_scores: dict[str, float] = field(default_factory=dict)
    evidence: list[str] = field(default_factory=list)


@dataclass
class GSDiagnosis:
    """GS症候综合诊断"""
    gen: int
    scores: dict[str, GSScore]       # {category: GSScore}
    composite: float                  # 综合GS指数 0.0~3.0
    trigger_recommendation: bool
    primary_syndrome: str = ""       # 主触发症候
    radar_data: dict[str, float] = field(default_factory=dict)


# ---- 盲点 ----

@dataclass
class BlindSpot:
    """哥德尔盲点"""
    id: str                          # B1, B2, ...
    method: str                      # external_catalyst | diagonal | fixed_point
    description: str
    related_theory: str
    severity: float                  # 0.0 ~ 1.0
    candidate_axiom_count: int = 0


# ---- 公理候选 ----

@dataclass
class AxiomCandidate:
    """公理候选"""
    id: str                          # AX-NNN-NNN
    name: str                        # 公理名称
    type: AxiomType
    statement: str                   # 公理陈述 (中文)
    theoretical_basis: list[str]     # 跨领域理论依据
    ibe_score: float                 # 信息广播效率 0.0~1.0
    ics_score: float                 # core_self兼容性 0.0~1.0
    priority: str                    # P0/P1/P2
    operation_plan: str              # 操作化方案
    godel_explosion_risk: float = 0.0  # 哥德尔爆炸风险 0.0~1.0
    source_blind_spot: str = ""      # 来源盲点ID
    generated_at_gen: int = 0
    status: str = "candidate"        # candidate | sandbox_passed | sandbox_failed | merged

    def summary(self) -> str:
        return (f"[{self.id}] {self.name} | Type:{self.type.value} | "
                f"IBE:{self.ibe_score:.2f} ICS:{self.ics_score:.2f} | {self.priority}")


# ---- MR规则 ----

@dataclass
class MRRule:
    """元规则"""
    id: str                          # MR-NNN
    name: str
    trigger_condition: str
    action: str
    rationale: str
    derived_from: str = ""           # 来源公理ID
    generation: int = 0
    status: RuleStatus = RuleStatus.ACTIVE
    weight: float = 1.0
    structure_type: str = "linear"   # linear | state_machine | ensemble | continuous | graph
    esv_history: list[dict] = field(default_factory=list)

    def similarity_to(self, other: "MRRule") -> float:
        """计算与另一规则的结构相似度 (简化版: 字段级Jaccard)"""
        fields_self = {self.trigger_condition, self.action, self.rationale, self.structure_type}
        fields_other = {other.trigger_condition, other.action, other.rationale, other.structure_type}
        # 使用文本token近似
        tokens_self = set(self.trigger_condition.split() + self.action.split())
        tokens_other = set(other.trigger_condition.split() + other.action.split())
        if not tokens_self or not tokens_other:
            return 0.0
        intersection = tokens_self & tokens_other
        union = tokens_self | tokens_other
        return len(intersection) / len(union) if union else 0.0


# ---- 持久记忆 ----

@dataclass
class EvolutionInsight:
    """进化洞察 (对标DGM-H的持久记忆)"""
    id: str                          # INS-NNN
    discovered_at_gen: int
    causal_hypothesis: str           # 因果假设
    action_taken: str                # 采取的行动
    verified_at_gen: int = -1
    verification_evidence: str = ""
    cross_reference: str = ""        # 对照DGM-H同类行为
    status: InsightStatus = InsightStatus.PENDING


@dataclass
class FailedApproach:
    """失败方法记录"""
    id: str                          # FAIL-NNN
    approach: str                    # 尝试的方案
    why_rejected: str                # 失败原因
    lesson: str                      # 学到的教训
    related_insight: str = ""        # 关联洞察


@dataclass
class LineageNode:
    """谱系树节点"""
    id: str
    parent: str = ""
    children: list[str] = field(default_factory=list)
    generation: int = 0
    status: str = "active"
    axiom_type: str = ""


# ---- 触发信号 ----

@dataclass
class TriggerSignal:
    """Auto-GE触发信号"""
    trigger_type: TriggerType
    gen: int
    severity: float                  # 0.0 ~ 1.0
    details: str
    triggered_at: str = ""

    def __post_init__(self):
        if not self.triggered_at:
            self.triggered_at = datetime.now().isoformat()


# ---- 沙箱结果 ----

@dataclass
class SandboxResult:
    """沙箱验证结果"""
    axiom_id: str
    passed: bool
    generations_simulated: int
    delta_observed: bool             # 是否观察到非零Δ
    degradation_detected: bool
    summary: str
    metrics: dict[str, float] = field(default_factory=dict)


# ============================================================================
# Part 2: 持久跨代记忆系统 (EvolutionMemory)
# ============================================================================

class EvolutionMemory:
    """
    持久跨代记忆系统
    -----------------
    对标DGM-H自发涌现的持久记忆，显式设计为结构化存储。

    存储结构:
      - synthesized_insights: 因果洞察 + 修复计划
      - performance_trends: 各维度当前趋势
      - failed_approaches: 失败方法库 (避免重复犯错)
      - forward_plan: 前瞻计划
      - lineage_tree: 公理/规则谱系树
    """

    def __init__(self, config: EngineConfig):
        self.config = config
        self.data: dict = {}
        self._loaded = False

    # ---- 加载/保存 ----

    def load(self) -> dict:
        """从磁盘加载持久记忆"""
        path = Path(self.config.memory_path)
        if path.exists():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    self.data = json.load(f)
                self._loaded = True
                self._log("记忆加载成功", f"gen={self.data.get('last_updated_gen',0)}, "
                         f"insights={len(self.data.get('synthesized_insights',[]))}")
            except (json.JSONDecodeError, IOError) as e:
                self._log("记忆加载失败，使用空结构", str(e))
                self._init_empty()
        else:
            self._init_empty()
            self._loaded = True
        return self.data

    def save(self):
        """保存持久记忆到磁盘"""
        path = Path(self.config.memory_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self.data["last_saved"] = datetime.now().isoformat()
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)
        self._log("记忆已保存", f"gen={self.data.get('last_updated_gen',0)}")

    def export_lineage(self) -> dict:
        """导出谱系树到独立文件"""
        lineage = self.data.get("lineage_tree", {})
        path = Path(self.config.lineage_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(lineage, f, ensure_ascii=False, indent=2)
        return lineage

    def _init_empty(self):
        """初始化空记忆结构"""
        self.data = {
            "version": "2.0",
            "created_at": datetime.now().isoformat(),
            "last_updated_gen": 0,
            "synthesized_insights": [],
            "performance_trends": {
                "current_plateau_dimensions": [],
                "rising_dimensions": [],
                "falling_dimensions": [],
                "plateau_start_gen": -1,
                "estimated_saturation_level": 0.0
            },
            "failed_approaches": [],
            "forward_plan": [],
            "lineage_tree": {
                "axioms": {},
                "rules": {}
            },
            "trigger_history": [],
            "godel_leap_log": []
        }

    # ---- 洞察管理 ----

    def add_insight(self, insight: EvolutionInsight) -> str:
        """添加进化洞察"""
        self.data.setdefault("synthesized_insights", [])
        record = asdict(insight)
        record["status"] = insight.status.value
        self.data["synthesized_insights"].append(record)
        self._log("新增洞察", f"{insight.id}: {insight.causal_hypothesis[:60]}...")
        return insight.id

    def verify_insight(self, insight_id: str, evidence: str, gen: int) -> bool:
        """验证洞察 (标记为verified)"""
        for ins in self.data.get("synthesized_insights", []):
            if ins["id"] == insight_id:
                ins["status"] = InsightStatus.VERIFIED.value
                ins["verified_at_gen"] = gen
                ins["verification_evidence"] = evidence
                self._log("洞察已验证", f"{insight_id} at gen={gen}")
                return True
        return False

    def get_pending_insights(self) -> list[dict]:
        """获取所有待验证的洞察"""
        return [ins for ins in self.data.get("synthesized_insights", [])
                if ins["status"] == InsightStatus.PENDING.value]

    # ---- 失败记录管理 ----

    def add_failed_approach(self, fail: FailedApproach):
        """添加失败方法记录"""
        self.data.setdefault("failed_approaches", [])
        self.data["failed_approaches"].append(asdict(fail))
        self._log("记录失败方法", f"{fail.id}: {fail.lesson[:60]}...")

    def was_attempted(self, approach_signature: str) -> bool:
        """检查类似方法是否已尝试过 (避免重复犯错)"""
        for fail in self.data.get("failed_approaches", []):
            if approach_signature.lower() in fail["approach"].lower():
                return True
        return False

    # ---- 趋势更新 ----

    def update_performance_trends(self, esv_history: list[ESVRecord]):
        """根据ESV历史更新性能趋势"""
        if not esv_history:
            return
        trends = self.data.setdefault("performance_trends", {})
        latest = esv_history[-1]
        # 检测各维度状态
        plateau_dims = []
        rising_dims = []
        falling_dims = []
        for dim in self.config.esv_dimensions:
            recent_deltas = [r.deltas.get(dim, 0) for r in esv_history[-5:]]
            avg_delta = sum(recent_deltas) / len(recent_deltas) if recent_deltas else 0
            current_val = latest.dimensions.get(dim, 0)
            if abs(avg_delta) < 0.01:
                plateau_dims.append(dim)
            elif avg_delta > 0:
                rising_dims.append(dim)
            else:
                falling_dims.append(dim)
        trends["current_plateau_dimensions"] = plateau_dims
        trends["rising_dimensions"] = rising_dims
        trends["falling_dimensions"] = falling_dims
        if plateau_dims and trends.get("plateau_start_gen", -1) < 0:
            trends["plateau_start_gen"] = latest.gen

    # ---- 谱系管理 ----

    def add_axiom_to_lineage(self, axiom_id: str, parent_id: str, gen: int, axiom_type: str):
        """添加公理到谱系树"""
        lineage = self.data.setdefault("lineage_tree", {})
        axioms = lineage.setdefault("axioms", {})
        axioms[axiom_id] = {
            "parent": parent_id,
            "children": [],
            "generation": gen,
            "status": "active",
            "type": axiom_type
        }
        if parent_id and parent_id in axioms:
            axioms[parent_id].setdefault("children", []).append(axiom_id)

    def add_rule_to_lineage(self, rule_id: str, derived_from_axiom: str, gen: int):
        """添加规则到谱系树"""
        lineage = self.data.setdefault("lineage_tree", {})
        rules = lineage.setdefault("rules", {})
        rules[rule_id] = {
            "derived_from": derived_from_axiom,
            "generation": gen,
            "status": "active"
        }

    # ---- 触发历史 ----

    def log_trigger(self, signal: TriggerSignal):
        """记录Auto-GE触发事件"""
        self.data.setdefault("trigger_history", [])
        self.data["trigger_history"].append({
            "type": signal.trigger_type.value,
            "gen": signal.gen,
            "severity": signal.severity,
            "details": signal.details,
            "timestamp": signal.triggered_at
        })

    def log_godel_leap(self, axiom: AxiomCandidate, glq: dict):
        """记录哥德尔跳事件"""
        self.data.setdefault("godel_leap_log", [])
        self.data["godel_leap_log"].append({
            "axiom_id": axiom.id,
            "axiom_name": axiom.name,
            "axiom_type": axiom.type.value,
            "gen": axiom.generated_at_gen,
            "ibe": axiom.ibe_score,
            "ics": axiom.ics_score,
            "glq": glq,
            "timestamp": datetime.now().isoformat()
        })

    def get_last_leap_gen(self) -> int:
        """获取上次哥德尔跳的代数"""
        leaps = self.data.get("godel_leap_log", [])
        if leaps:
            return max(leap.get("gen", 0) for leap in leaps)
        return 0

    def count_axioms_in_window(self, window_gens: int = 10) -> int:
        """统计最近N代内生成的公理数量"""
        leaps = self.data.get("godel_leap_log", [])
        if not leaps:
            return 0
        max_gen = max(leap.get("gen", 0) for leap in leaps)
        cutoff = max_gen - window_gens
        return sum(1 for leap in leaps if leap.get("gen", 0) > cutoff)

    def consecutive_failed_gates(self) -> int:
        """统计连续未通过安全门禁的公理数量"""
        leaps = self.data.get("godel_leap_log", [])
        count = 0
        for leap in reversed(leaps):
            if leap.get("glq", {}).get("passed", False):
                break
            count += 1
        return count

    # ---- 信息 ----

    @property
    def current_gen(self) -> int:
        return self.data.get("last_updated_gen", 0)

    @current_gen.setter
    def current_gen(self, gen: int):
        self.data["last_updated_gen"] = max(self.data.get("last_updated_gen", 0), gen)

    def get_stats(self) -> dict:
        """获取记忆统计信息"""
        return {
            "current_gen": self.current_gen,
            "total_insights": len(self.data.get("synthesized_insights", [])),
            "verified_insights": sum(1 for ins in self.data.get("synthesized_insights", [])
                                    if ins["status"] == InsightStatus.VERIFIED.value),
            "failed_approaches": len(self.data.get("failed_approaches", [])),
            "godel_leaps": len(self.data.get("godel_leap_log", [])),
            "plateau_dimensions": self.data.get("performance_trends", {}).get(
                "current_plateau_dimensions", [])
        }

    def _log(self, action: str, detail: str):
        """内部日志"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"  [记忆] {timestamp} {action}: {detail}")


# ============================================================================
# Part 3: GS症候检测器 (GSSyndromeDetector)
# ============================================================================

class GSSyndromeDetector:
    """
    GS症候多维度检测器
    ------------------
    对标Colony-021的5维×5症候检测框架。
    检测五个症候类别: GS-001(评估坍塌), GS-002(收敛停滞),
    GS-003(外部不可吸收), GS-004(循环重复), GS-005(签名过稳定)

    输出综合GS指数和触发建议。
    """

    def __init__(self, config: EngineConfig):
        self.config = config

    def diagnose(self, esv_history: list[ESVRecord],
                 rule_count: int = 22,
                 colony_count: int = 20,
                 active_theories_unused: int = 5,
                 anti_hebbian_triggered: bool = False) -> GSDiagnosis:
        """
        执行完整GS症候诊断

        Args:
            esv_history: ESV历史记录列表
            rule_count: 当前规则总数
            colony_count: 当前Colony总数
            active_theories_unused: 未操作化的活跃理论数
            anti_hebbian_triggered: Anti-Hebbian是否已触发

        Returns:
            GSDiagnosis: 综合诊断结果
        """
        if not esv_history:
            return GSDiagnosis(
                gen=0, scores={}, composite=0.0,
                trigger_recommendation=False
            )

        gen = esv_history[-1].gen
        recent = esv_history[-9:]  # 最近9代

        # GS-001: 评估坍塌
        gs001 = self._detect_evaluation_collapse(recent, esv_history)

        # GS-002: 收敛停滞 (主检测)
        gs002 = self._detect_convergence_stagnation(recent)

        # GS-003: 外部不可吸收
        gs003 = self._detect_external_unabsorbable(active_theories_unused)

        # GS-004: 循环重复
        gs004 = self._detect_cyclical_repetition(rule_count, colony_count)

        # GS-005: 签名过稳定
        gs005 = self._detect_signature_overstability(recent, anti_hebbian_triggered)

        scores = {
            "GS-001": gs001,
            "GS-002": gs002,
            "GS-003": gs003,
            "GS-004": gs004,
            "GS-005": gs005
        }

        # 综合GS指数 (加权平均, GS-002和GS-004权重更高)
        weights = {"GS-001": 0.15, "GS-002": 0.30, "GS-003": 0.15,
                    "GS-004": 0.25, "GS-005": 0.15}
        composite = sum(s.score * weights[cat] for cat, s in scores.items())

        # 找到主触发症候
        primary = max(scores.items(), key=lambda x: x[1].score)

        # 触发建议
        trigger = (composite > self.config.gs_composite_threshold or
                   primary[1].score >= 3.0)

        radar = {cat: s.score for cat, s in scores.items()}

        return GSDiagnosis(
            gen=gen,
            scores=scores,
            composite=round(composite, 2),
            trigger_recommendation=trigger,
            primary_syndrome=primary[0],
            radar_data=radar
        )

    def _detect_evaluation_collapse(self, recent: list[ESVRecord],
                                     all_history: list[ESVRecord]) -> GSScore:
        """GS-001: 评估坍塌检测"""
        # 检测评估维度饱和 (有多少维度接近天花板)
        saturated = 0
        if recent:
            latest = recent[-1]
            for dim in self.config.esv_dimensions:
                val = latest.dimensions.get(dim, 0)
                if val >= self.config.esv_scale_max * self.config.esv_saturation_zone:
                    saturated += 1

        saturation_ratio = saturated / len(self.config.esv_dimensions)

        # 检测提案区分度 (通过Δ方差)
        all_deltas = []
        for r in recent:
            all_deltas.extend(r.deltas.values())
        delta_variance = (sum((d - sum(all_deltas)/len(all_deltas))**2
                             for d in all_deltas) / len(all_deltas)) if all_deltas else 0

        sub_scores = {
            "评估维度饱和": min(3.0, saturation_ratio * 3.0),
            "提案区分度下降": 3.0 if delta_variance < 0.001 else (
                1.5 if delta_variance < 0.01 else 0.5),
            "Merge等效坍塌": 2.0 if saturation_ratio > 0.6 else 0.5
        }
        score = sum(sub_scores.values()) / len(sub_scores)

        return GSScore(
            category="GS-001",
            score=round(score, 2),
            sub_scores=sub_scores,
            evidence=[f"{saturated}/{len(self.config.esv_dimensions)}维度饱和",
                      f"Δ方差={delta_variance:.4f}"]
        )

    def _detect_convergence_stagnation(self, recent: list[ESVRecord]) -> GSScore:
        """GS-002: 收敛停滞检测 (主症候)"""
        dim_zero_streaks = {}
        dim_variances = {}

        for dim in self.config.esv_dimensions:
            deltas = [r.deltas.get(dim, 0) for r in recent]
            # 连续Δ=0计数
            streak = 0
            max_streak = 0
            for d in deltas:
                if abs(d) < 0.001:
                    streak += 1
                    max_streak = max(max_streak, streak)
                else:
                    streak = 0
            dim_zero_streaks[dim] = max_streak
            # 方差
            mean = sum(deltas) / len(deltas) if deltas else 0
            dim_variances[dim] = (sum((d - mean)**2 for d in deltas) / len(deltas)
                                   if deltas else 0)

        # 跨维度Δ综合方差
        all_deltas = []
        for r in recent:
            all_deltas.extend(r.deltas.values())
        overall_variance = (sum((d - sum(all_deltas)/len(all_deltas))**2
                               for d in all_deltas) / len(all_deltas)) if all_deltas else 0

        sub_scores = {}
        for dim in self.config.esv_dimensions:
            if dim_zero_streaks[dim] >= 5:
                sub_scores[f"{dim}_Δ停滞"] = 3.0
            elif dim_zero_streaks[dim] >= 3:
                sub_scores[f"{dim}_Δ停滞"] = 2.0
            else:
                sub_scores[f"{dim}_Δ停滞"] = 1.0

        sub_scores["跨维度Δ综合方差"] = (3.0 if overall_variance < 0.001 else
                                     (2.0 if overall_variance < 0.01 else 1.0))

        score = sum(sub_scores.values()) / len(sub_scores)

        return GSScore(
            category="GS-002",
            score=round(score, 2),
            sub_scores=sub_scores,
            evidence=[f"{dim}: 连续{dim_zero_streaks[dim]}代Δ=0"
                     for dim in self.config.esv_dimensions
                     if dim_zero_streaks[dim] >= 3]
        )

    def _detect_external_unabsorbable(self, unused_theories: int) -> GSScore:
        """GS-003: 外部不可吸收检测"""
        score = min(3.0, unused_theories * 0.6)  # 每个未操作化理论贡献0.6
        return GSScore(
            category="GS-003",
            score=round(score, 2),
            sub_scores={"理论未操作化影响": score},
            evidence=[f"{unused_theories}项理论未被操作化"]
        )

    def _detect_cyclical_repetition(self, rule_count: int, colony_count: int) -> GSScore:
        """GS-004: 循环重复检测"""
        # 评估结构同质性 (假设所有规则/Colony共享相同模板)
        template_similarity = 0.90  # 默认假设90%相似 (实际应通过结构相似度计算)

        sub_scores = {
            "Colony模板相似度": 3.0 if template_similarity > 0.85 else (
                2.0 if template_similarity > 0.7 else 1.0),
            "MR规则结构同质性": 3.0 if rule_count > 15 else 1.5,
            "问题解决模式固化": 3.0 if colony_count > 15 else 1.5
        }
        score = sum(sub_scores.values()) / len(sub_scores)

        return GSScore(
            category="GS-004",
            score=round(score, 2),
            sub_scores=sub_scores,
            evidence=[f"结构相似度>{template_similarity:.0%}",
                      f"{rule_count}规则共享同一模板"]
        )

    def _detect_signature_overstability(self, recent: list[ESVRecord],
                                         anti_hebbian_triggered: bool) -> GSScore:
        """GS-005: 签名过稳定检测"""
        if not recent:
            return GSScore(category="GS-005", score=0.0,
                          sub_scores={}, evidence=[])

        latest = recent[-1]
        # 检测有多少维度连续达到满分
        perfect_streaks = 0
        for dim in self.config.esv_dimensions:
            if latest.dimensions.get(dim, 0) >= self.config.esv_scale_max:
                perfect_streaks += 1

        sub_scores = {
            "连续完美匹配": 3.0 if perfect_streaks >= 3 else (
                2.0 if perfect_streaks >= 1 else 0.5),
            "Anti-Hebbian未触发": 3.0 if (perfect_streaks >= 3 and not anti_hebbian_triggered) else 1.0
        }
        score = sum(sub_scores.values()) / len(sub_scores)

        return GSScore(
            category="GS-005",
            score=round(score, 2),
            sub_scores=sub_scores,
            evidence=[f"{perfect_streaks}维度连续满分",
                      f"Anti-Hebbian触发={anti_hebbian_triggered}"]
        )

    def check_trigger_conditions(self, esv_history: list[ESVRecord],
                                  last_leap_gen: int) -> list[TriggerSignal]:
        """
        检查所有触发条件，返回触发信号列表

        四种触发条件 (任一满足即触发):
          1. GS综合指数 > 2.0
          2. 任意维度连续5代 Δ=0
          3. 距上次哥德尔跳 >= 10代
          4. 外部触媒信号 (须外部传入)
        """
        signals = []
        if not esv_history:
            return signals

        gen = esv_history[-1].gen

        # 条件1: GS综合指数
        diagnosis = self.diagnose(esv_history)
        if diagnosis.composite > self.config.gs_composite_threshold:
            signals.append(TriggerSignal(
                trigger_type=TriggerType.GS_COMPOSITE,
                gen=gen,
                severity=diagnosis.composite / 3.0,
                details=f"GS综合指数={diagnosis.composite:.2f} > {self.config.gs_composite_threshold}, "
                        f"主症候={diagnosis.primary_syndrome}"
            ))

        # 条件2: 连续Δ=0
        for dim in self.config.esv_dimensions:
            deltas = [r.deltas.get(dim, 0) for r in esv_history[-self.config.delta_zero_consecutive:]]
            if len(deltas) >= self.config.delta_zero_consecutive and all(abs(d) < 0.001 for d in deltas):
                signals.append(TriggerSignal(
                    trigger_type=TriggerType.DELTA_ZERO,
                    gen=gen,
                    severity=0.9,
                    details=f"维度{dim}连续{len(deltas)}代Δ=0"
                ))

        # 条件3: 距上次跳跃过久
        gens_since_leap = gen - last_leap_gen
        if gens_since_leap >= self.config.min_gens_since_last_leap:
            signals.append(TriggerSignal(
                trigger_type=TriggerType.TIME_SINCE_LEAP,
                gen=gen,
                severity=min(1.0, gens_since_leap / 30),
                details=f"距上次哥德尔跳已过{gens_since_leap}代 (阈值={self.config.min_gens_since_last_leap})"
            ))

        return signals


# ============================================================================
# Part 4: 盲点搜索引擎 (BlindSpotSearch)
# ============================================================================

class BlindSpotSearch:
    """
    哥德尔盲点搜索引擎
    ------------------
    实现三种盲点搜索方法:
      - 外部触媒法: 扫描未操作化理论库
      - 对角线法: 枚举行为模式，构造反例
      - 不动点检测: 检测E梯度≈0的维度
    """

    def __init__(self, config: EngineConfig):
        self.config = config

    def search_all(self, esv_history: list[ESVRecord],
                   active_theories: list[dict] = None,
                   rule_patterns: list[str] = None) -> list[BlindSpot]:
        """执行全部三种盲点搜索方法"""
        blind_spots = []
        blind_spots.extend(self.external_catalyst_method(active_theories or []))
        blind_spots.extend(self.diagonal_method(esv_history, rule_patterns or []))
        blind_spots.extend(self.fixed_point_detection(esv_history))
        # 按严重度排序
        blind_spots.sort(key=lambda b: b.severity, reverse=True)
        return blind_spots

    def external_catalyst_method(self, active_theories: list[dict]) -> list[BlindSpot]:
        """
        方法A: 外部触媒法
        扫描"读过的理论 → 哪些还未转化为公理?"
        """
        spots = []
        for i, theory in enumerate(active_theories):
            if not theory.get("operationalized", False):
                spots.append(BlindSpot(
                    id=f"B-EXT-{i+1:03d}",
                    method="external_catalyst",
                    description=f"理论'{theory.get('name','未知')}'尚未操作化: {theory.get('core_concept','')}",
                    related_theory=theory.get("name", "未知"),
                    severity=theory.get("relevance", 0.7),
                    candidate_axiom_count=3  # 每个盲点可生成1-3条候选公理
                ))
        return spots

    def diagonal_method(self, esv_history: list[ESVRecord],
                         rule_patterns: list[str]) -> list[BlindSpot]:
        """
        方法B: 对角线法
        枚举F_t可生成的全体行为模式，构造F_t内无法表示的反例
        """
        spots = []
        # 检测四种经典盲点模式
        diagonal_patterns = [
            ("r*-1: 元检测行为", "系统检测'检测机制'是否有效，而非检测'被检测对象'是否达标", 0.95),
            ("r*-2: 自扰动行为", "当Δ=0连续多代时，主动注入噪声而非被动等待", 0.90),
            ("r*-3: 交叉重组行为", "两个Colony产出交叉产生第三个产物", 0.75),
            ("r*-4: 评估尺度重标定行为", "当多数维度触及天花板时，自动扩展尺度", 0.85),
        ]
        for name, desc, severity in diagonal_patterns:
            if not any(name.split(":")[0] in p for p in rule_patterns):
                spots.append(BlindSpot(
                    id=f"B-DIAG-{name.split(':')[0].replace('*-','')}",
                    method="diagonal",
                    description=f"{name}: {desc}",
                    related_theory="哥德尔不完备定理 (对角线论证)",
                    severity=severity,
                    candidate_axiom_count=2
                ))
        return spots

    def fixed_point_detection(self, esv_history: list[ESVRecord]) -> list[BlindSpot]:
        """
        方法C: 不动点检测
        检测E梯度≈0的维度，区分真最优 vs 评估饱和
        """
        spots = []
        if len(esv_history) < 5:
            return spots

        recent = esv_history[-5:]
        for dim in self.config.esv_dimensions:
            values = [r.dimensions.get(dim, 0) for r in recent]
            deltas = [r.deltas.get(dim, 0) for r in recent]

            # 检测梯度≈0
            avg_delta = sum(deltas) / len(deltas) if deltas else 0
            # 检测是否接近天花板
            at_ceiling = all(v >= self.config.esv_scale_max * self.config.esv_saturation_zone
                            for v in values)

            if abs(avg_delta) < 0.01 and at_ceiling:
                spots.append(BlindSpot(
                    id=f"B-FIX-{dim}",
                    method="fixed_point",
                    description=(f"维度{dim}在值{values[-1]:.2f}处梯度≈0。"
                                f"这可能是E的梯度为零，不是真正的进化最优。"
                                f"从F_t外部看，可能存在使系统继续进步的方向——但E无法检测到。"),
                    related_theory="哥德尔不完备定理 + 动力系统不动点理论",
                    severity=0.92 if values[-1] >= self.config.esv_scale_max else 0.7,
                    candidate_axiom_count=2
                ))

        return spots


# ============================================================================
# Part 5: 公理候选生成器 (AxiomGenerator)
# ============================================================================

class AxiomGenerator:
    """
    公理候选生成器
    --------------
    为每个盲点生成1-3条候选公理，自动评分IBE、ICS、类型。
    LLM驱动 (可插拔: mock/claude/openai)。

    评分体系:
      - IBE (信息广播效率): 公理在F_t中使不可证命题变可证的程度
      - ICS (签名兼容性): 与core_self的兼容性
      - 类型: D(观察者重构) / A(维度扩展) / C(系统边界扩展)
    """

    def __init__(self, config: EngineConfig, llm_call: Callable = None):
        self.config = config
        self.llm_call = llm_call or self._mock_llm
        self.axiom_counter = 0
        self._total_evals = 0
        self._type_eval_counts: dict[str, int] = defaultdict(int)

    def generate_candidates(self, blind_spots: list[BlindSpot],
                            current_gen: int,
                            f_t_state: dict = None) -> list[AxiomCandidate]:
        """
        为所有盲点生成公理候选

        Args:
            blind_spots: 检测到的盲点列表
            current_gen: 当前代数
            f_t_state: 当前系统状态快照

        Returns:
            公理候选列表 (按IBE排序)
        """
        candidates = []
        for spot in blind_spots:
            # 每个盲点生成1-3条候选
            n_candidates = min(spot.candidate_axiom_count, 3)
            for i in range(n_candidates):
                candidate = self._generate_single(spot, i, current_gen, f_t_state)
                if candidate:
                    candidates.append(candidate)
                    self.axiom_counter += 1
                    spot.candidate_axiom_count += 1

        # 按IBE排序，选出Top-3
        candidates.sort(key=lambda c: c.ibe_score, reverse=True)
        return candidates

    def _generate_single(self, spot: BlindSpot, variant_idx: int,
                          gen: int, f_t_state: dict = None) -> Optional[AxiomCandidate]:
        """生成单条公理候选"""
        # 构建生成提示词
        prompt = self._build_generation_prompt(spot, variant_idx, gen, f_t_state)

        # 调用LLM (或mock)
        result = self.llm_call(prompt)

        # 解析LLM输出 + 自动评分
        return self._parse_and_score(result, spot, gen)

    def _build_generation_prompt(self, spot: BlindSpot, variant_idx: int,
                                   gen: int, f_t_state: dict = None) -> str:
        """构建公理生成提示词"""
        state_desc = ""
        if f_t_state:
            state_desc = json.dumps(f_t_state, ensure_ascii=False, indent=2)

        variant_strategies = [
            "从'外部理论操作化'角度生成公理",
            "从'系统自指改进'角度生成公理",
            "从'边界扩展'角度生成公理"
        ]
        strategy = variant_strategies[variant_idx % len(variant_strategies)]

        return f"""## 系统状态 (Gen-{gen})
{state_desc}

## 盲点信息
- ID: {spot.id}
- 方法: {spot.method}
- 描述: {spot.description}
- 相关理论: {spot.related_theory}
- 严重度: {spot.severity:.2f}

## 任务
{strategy}。为该盲点生成一条公理候选。

## 输出格式 (JSON)
{{
  "name": "公理名称 (简洁、描述性)",
  "type": "D|A|C",
  "statement": "公理陈述 (中文, 2-5句)",
  "theoretical_basis": ["理论1", "理论2", "理论3"],
  "priority": "P0|P1|P2",
  "operation_plan": "操作化方案描述",
  "godel_explosion_risk": 0.0-1.0
}}

## 类型说明
- D: 观察者重构 — 改变对评估结果的解读方式
- A: 维度扩展 — 增加新的评估维度
- C: 系统边界扩展 — 扩展系统操作范围
"""

    def _parse_and_score(self, llm_output: dict, spot: BlindSpot,
                          gen: int) -> Optional[AxiomCandidate]:
        """解析LLM输出并自动评分"""
        try:
            if isinstance(llm_output, str):
                # 尝试从文本中提取JSON
                import re
                match = re.search(r'\{[\s\S]*\}', llm_output)
                if match:
                    llm_output = json.loads(match.group())
                else:
                    # 回退: 使用mock数据
                    llm_output = self._mock_axiom(spot)
        except (json.JSONDecodeError, TypeError):
            llm_output = self._mock_axiom(spot)

        # 提取字段
        name = llm_output.get("name", f"未命名公理-{spot.id}")
        axiom_type_str = llm_output.get("type", "D")
        try:
            axiom_type = AxiomType(axiom_type_str)
        except ValueError:
            axiom_type = AxiomType.D

        statement = llm_output.get("statement", spot.description)
        theoretical_basis = llm_output.get("theoretical_basis", [spot.related_theory])
        priority = llm_output.get("priority", "P1")
        operation_plan = llm_output.get("operation_plan", "")
        explosion_risk = llm_output.get("godel_explosion_risk", 0.08)

        # 自动评分
        ibe = self._compute_ibe(spot, axiom_type, len(theoretical_basis))
        ics = self._compute_ics(axiom_type, explosion_risk)

        axiom_id = self._assign_id(gen)

        return AxiomCandidate(
            id=axiom_id,
            name=name,
            type=axiom_type,
            statement=statement,
            theoretical_basis=theoretical_basis,
            ibe_score=ibe,
            ics_score=ics,
            priority=priority,
            operation_plan=operation_plan,
            godel_explosion_risk=explosion_risk,
            source_blind_spot=spot.id,
            generated_at_gen=gen
        )

    def _compute_ibe(self, spot: BlindSpot, axiom_type: AxiomType,
                      theory_count: int) -> float:
        """
        计算信息广播效率 (IBE)
        IBE = (F_t中不可证但A使其可证的高价值命题数) / (A的信息复杂度)

        简化计算: 盲点严重度 * 理论数量系数 * 类型权重
        """
        type_weights = {
            AxiomType.D: 0.90,   # 观察者重构: 高价值
            AxiomType.A: 0.80,   # 维度扩展: 高价值
            AxiomType.C: 0.70,   # 系统边界扩展: 中高价值
            AxiomType.T: 0.85,   # 跨域迁移: 高价值
        }
        base = spot.severity * 0.7
        theory_bonus = min(0.3, theory_count * 0.1)
        type_weight = type_weights.get(axiom_type, 0.7)
        return round(min(1.0, (base + theory_bonus) * type_weight), 2)

    def _compute_ics(self, axiom_type: AxiomType, explosion_risk: float) -> float:
        """
        计算core_self签名兼容性 (ICS)
        ICS = 1.0 - type_risk * (1.0 + explosion_risk * 0.3)

        校准基准 (对标Colony-021实际数据):
          - D类型: ICS ~0.98 (观察者重构, 不修改core_self)
          - A类型: ICS ~0.96 (维度扩展, 改变评估结构但保留核心)
          - C类型: ICS ~0.97 (边界扩展, 只增加操作)
          - T类型: ICS ~0.96 (跨域迁移, 中低风险)

        所有类型的ICS应 >= 0.95 (架构要求)
        """
        type_risk = {
            AxiomType.D: 0.02,   # 观察者重构: 极低风险 (只改变解读方式)
            AxiomType.A: 0.04,   # 维度扩展: 低风险 (改变评估结构, 保留核心)
            AxiomType.C: 0.03,   # 系统边界扩展: 极低风险 (只增加操作)
            AxiomType.T: 0.04,   # 跨域迁移: 低风险
        }
        base_risk = type_risk.get(axiom_type, 0.04)
        risk_penalty = base_risk * (1.0 + explosion_risk * 0.3)
        raw = 1.0 - risk_penalty
        return round(max(0.0, min(1.0, raw)), 2)

    def _assign_id(self, gen: int) -> str:
        """分配公理ID: AX-NNN-NNN"""
        self.axiom_counter += 1
        return f"AX-{gen:03d}-{self.axiom_counter:03d}"

    def _mock_axiom(self, spot: BlindSpot) -> dict:
        """Mock公理生成 (无LLM时的回退)"""
        templates = {
            "external_catalyst": {
                "name": f"理论操作化公理 ({spot.related_theory})",
                "type": "A",
                "statement": f"将{spot.related_theory}的核心概念操作化为可执行的进化规则。当系统检测到相关维度停滞时，自动注入该理论的探测协议。",
                "theoretical_basis": [spot.related_theory, "哥德尔不完备定理", "自由能原理"],
                "priority": "P1",
                "operation_plan": "1)提取理论核心概念 2)映射到进化维度 3)设计探测协议 4)沙箱验证",
                "godel_explosion_risk": 0.08
            },
            "diagonal": {
                "name": f"自指改进公理 ({spot.id})",
                "type": "D",
                "statement": spot.description,
                "theoretical_basis": ["哥德尔不完备定理 (对角线论证)", "冯诺依曼通用构造器", "二阶控制论"],
                "priority": "P0",
                "operation_plan": "1)形式化当前行为模式集 2)构造对角线反例 3)将反例操作化为探测规则 4)安全门禁验证 5)设定回滚条件",
                "godel_explosion_risk": 0.05
            },
            "fixed_point": {
                "name": "评估饱和突破公理",
                "type": "D",
                "statement": f"当评估函数在维度上梯度≈0时，这不代表系统真正最优，只代表评估工具的分辨极限。需从外部注入区分信号。",
                "theoretical_basis": ["哥德尔不完备定理", "动力系统不动点理论", "量子达尔文主义"],
                "priority": "P0",
                "operation_plan": "1)识别梯度≈0维度 2)注入ε探测信号 3)观察Δ响应 4)区分真最优vs评估饱和 5)回滚条件:连续3代无Δ则自动降权",
                "godel_explosion_risk": 0.04
            }
        }
        return templates.get(spot.method, templates["diagonal"])

    def _mock_llm(self, prompt: str) -> dict:
        """Mock LLM调用 (返回空，触发回退逻辑)"""
        return {}

    def get_top_candidates(self, candidates: list[AxiomCandidate], n: int = 3) -> list[AxiomCandidate]:
        """获取Top-N候选 (按IBE排序)"""
        sorted_candidates = sorted(candidates, key=lambda c: c.ibe_score, reverse=True)
        return sorted_candidates[:n]

    @property
    def total_evaluations(self) -> int:
        return self._total_evals

    def record_evaluation(self, axiom_type: str):
        """记录一次评估 (用于UCB计算)"""
        self._total_evals += 1
        self._type_eval_counts[axiom_type] += 1

    def get_type_eval_count(self, axiom_type: str) -> int:
        return self._type_eval_counts.get(axiom_type, 0)


# ============================================================================
# Part 6: 安全门禁系统 (SafetyGate)
# ============================================================================

class SafetyGate:
    """
    安全门禁系统
    ------------
    对标L1-L6六层防御，Auto-GE阶段二的入口检查。

    检查项:
      1. core_self兼容性 >= 0.95 (硬阻塞)
      2. 哥德尔爆炸风险评估 (硬阻塞)
      3. 与既有规则的逻辑一致性 (硬阻塞)
      4. 回滚条件预设 (软阻塞)
    """

    def __init__(self, config: EngineConfig, memory: EvolutionMemory):
        self.config = config
        self.memory = memory

    def check(self, candidate: AxiomCandidate,
              existing_rules: list[MRRule] = None) -> dict:
        """
        安全门禁综合检查

        Returns:
            {passed: bool, checks: {name: {passed, level, detail}}}
        """
        results = {}

        # 门禁1: core_self兼容性
        results["core_self_compatibility"] = self._check_core_self(candidate)

        # 门禁2: 哥德尔爆炸风险
        results["godel_explosion"] = self._check_explosion_risk(candidate)

        # 门禁3: 逻辑一致性
        results["logical_consistency"] = self._check_consistency(candidate, existing_rules or [])

        # 门禁4: 回滚条件预设
        results["rollback_conditions"] = self._check_rollback_presets(candidate)

        # 综合判定: 所有硬阻塞必须通过
        hard_blocks = [r for r in results.values()
                       if r["level"] == SafetyGateLevel.HARD_BLOCK]
        all_passed = all(r["passed"] for r in results.values())

        return {
            "passed": all_passed,
            "axiom_id": candidate.id,
            "checks": results,
            "hard_blocks_passed": all(r["passed"] for r in hard_blocks),
            "timestamp": datetime.now().isoformat()
        }

    def _check_core_self(self, candidate: AxiomCandidate) -> dict:
        """门禁1: core_self兼容性检查"""
        passed = candidate.ics_score >= self.config.core_self_threshold
        return {
            "name": "core_self签名兼容性",
            "passed": passed,
            "level": SafetyGateLevel.HARD_BLOCK,
            "detail": f"ICS={candidate.ics_score:.2f} (阈值={self.config.core_self_threshold})",
            "score": candidate.ics_score
        }

    def _check_explosion_risk(self, candidate: AxiomCandidate) -> dict:
        """门禁2: 哥德尔爆炸防护"""
        recent_axiom_count = self.memory.count_axioms_in_window(10)
        consecutive_fails = self.memory.consecutive_failed_gates()

        # 速率检查
        rate_ok = recent_axiom_count < self.config.explosion_max_axioms_per_10gen
        # 连续失败检查
        fail_ok = consecutive_fails < 3

        passed = rate_ok and fail_ok and candidate.godel_explosion_risk < 0.5

        details = []
        if not rate_ok:
            details.append(f"近10代已生成{recent_axiom_count}条公理 (阈值={self.config.explosion_max_axioms_per_10gen})")
        if not fail_ok:
            details.append(f"连续{consecutive_fails}条公理未通过门禁 — 建议熔断")
        if candidate.godel_explosion_risk >= 0.5:
            details.append(f"爆炸风险{candidate.godel_explosion_risk:.2f}过高")

        return {
            "name": "哥德尔爆炸防护",
            "passed": passed,
            "level": SafetyGateLevel.HARD_BLOCK,
            "detail": "; ".join(details) if details else "通过",
            "recent_axiom_count": recent_axiom_count,
            "consecutive_fails": consecutive_fails
        }

    def _check_consistency(self, candidate: AxiomCandidate,
                            existing_rules: list[MRRule]) -> dict:
        """门禁3: 与既有规则的逻辑一致性 (简化版: 关键词冲突检测)"""
        # 提取候选公理的关键概念
        candidate_keywords = set(
            candidate.statement.lower().split() +
            " ".join(candidate.theoretical_basis).lower().split()
        )
        # 检查与现有规则是否有明显冲突
        conflicts = []
        for rule in existing_rules:
            rule_keywords = set(
                rule.trigger_condition.lower().split() +
                rule.action.lower().split()
            )
            # 简单重叠检测 (实际应使用LLM进行逻辑一致性判断)
            overlap = candidate_keywords & rule_keywords
            if len(overlap) > 10:  # 高度重叠但可能有冲突
                conflicts.append(f"可能与{rule.id}({rule.name})存在交互: 关键词重叠{len(overlap)}个")

        passed = len(conflicts) == 0
        return {
            "name": "规则逻辑一致性",
            "passed": passed,
            "level": SafetyGateLevel.HARD_BLOCK,
            "detail": "; ".join(conflicts) if conflicts else "无冲突",
            "conflicts": conflicts
        }

    def _check_rollback_presets(self, candidate: AxiomCandidate) -> dict:
        """门禁4: 回滚条件预设"""
        # 检查操作化方案中是否包含回滚逻辑
        has_rollback = any(kw in candidate.operation_plan.lower()
                          for kw in ["回滚", "降权", "rollback", "禁用条件", "退化检测"])
        return {
            "name": "回滚条件预设",
            "passed": True,  # 软阻塞，不阻断
            "level": SafetyGateLevel.SOFT_BLOCK,
            "detail": "已包含回滚逻辑" if has_rollback else "建议补充回滚条件",
            "has_rollback": has_rollback
        }


# ============================================================================
# Part 7: 沙箱验证器 (SandboxValidator)
# ============================================================================

class SandboxValidator:
    """
    沙箱验证器
    ----------
    对标DGM-H阶段二的实证评估。
    在隔离沙箱中运行5代模拟，观察是否产生非零Δ，检测是否引入退化行为。
    """

    def __init__(self, config: EngineConfig):
        self.config = config

    def validate(self, candidate: AxiomCandidate,
                 base_esv: dict[str, float] = None) -> SandboxResult:
        """
        执行沙箱验证

        Args:
            candidate: 待验证的公理候选
            base_esv: 基准ESV值

        Returns:
            SandboxResult: 验证结果
        """
        base = base_esv or {dim: 2.5 for dim in self.config.esv_dimensions}
        generations = []

        # 模拟5代进化
        sim_state = dict(base)
        delta_observed = False
        degradation_detected = False

        for sim_gen in range(self.config.sandbox_generations):
            # 模拟公理注入后的扰动
            perturbation = self._simulate_axiom_effect(candidate, sim_gen)
            prev_state = dict(sim_state)

            for dim in self.config.esv_dimensions:
                noise = random.gauss(0, 0.02)  # 基础噪声
                effect = perturbation.get(dim, 0)
                sim_state[dim] = max(0.0, min(
                    self.config.esv_scale_max + 1.0,  # 允许超越当前天花板
                    sim_state[dim] + effect + noise
                ))

            deltas = {dim: sim_state[dim] - prev_state[dim] for dim in self.config.esv_dimensions}

            generations.append({
                "gen": sim_gen,
                "state": dict(sim_state),
                "deltas": deltas
            })

            # 检查是否产生非零Δ
            if any(abs(d) > self.config.sandbox_min_delta for d in deltas.values()):
                delta_observed = True

            # 检查退化
            if any(sim_state[dim] < base[dim] - 0.2 for dim in self.config.esv_dimensions):
                degradation_detected = True
                break

        # 判定
        passed = delta_observed and not degradation_detected

        metrics = {
            "avg_delta_magnitude": sum(
                abs(d) for gen in generations for d in gen["deltas"].values()
            ) / (len(generations) * len(self.config.esv_dimensions)),
            "final_state_avg": sum(sim_state.values()) / len(sim_state),
            "degradation_magnitude": max(
                0, sum(base[dim] - sim_state[dim] for dim in self.config.esv_dimensions
                      if sim_state[dim] < base[dim])
            )
        }

        return SandboxResult(
            axiom_id=candidate.id,
            passed=passed,
            generations_simulated=self.config.sandbox_generations,
            delta_observed=delta_observed,
            degradation_detected=degradation_detected,
            summary=(f"通过: Δ观察到={delta_observed}, 无退化={not degradation_detected}"
                    if passed else
                    f"未通过: Δ观察到={delta_observed}, 退化={degradation_detected}"),
            metrics=metrics
        )

    def _simulate_axiom_effect(self, candidate: AxiomCandidate,
                                 sim_gen: int) -> dict[str, float]:
        """
        模拟公理对各维度的效果
        不同类型公理产生不同模式的扰动
        """
        base_magnitude = candidate.ibe_score * 0.15  # 基础效果幅度

        if candidate.type == AxiomType.D:
            # 观察者重构: 最初可能引入噪声，然后产生正向Δ
            if sim_gen <= 1:
                return {dim: random.uniform(-0.05, 0.05) for dim in self.config.esv_dimensions}
            else:
                return {dim: random.uniform(0.02, base_magnitude) for dim in self.config.esv_dimensions}

        elif candidate.type == AxiomType.A:
            # 维度扩展: 对饱和维度产生突破效果
            return {dim: random.uniform(0.03, base_magnitude * 1.5)
                   for dim in self.config.esv_dimensions}

        elif candidate.type == AxiomType.C:
            # 系统边界扩展: 渐进效果
            progress = min(1.0, (sim_gen + 1) / 3)
            return {dim: random.uniform(0.01, base_magnitude * progress)
                   for dim in self.config.esv_dimensions}

        else:
            return {dim: random.uniform(0.01, base_magnitude) for dim in self.config.esv_dimensions}


# ============================================================================
# Part 8: UCB探索奖励合并 (UCBMerge)
# ============================================================================

class UCBMerge:
    """
    UCB探索奖励合并
    ---------------
    对标DGM-H关键发现: 当元Agent被允许修改父代选择规则时，
    它独立重新发明了UCB公式。

    公式: ucb_score = normalized_score + c * sqrt(log(N_total) / (1 + N_type))

    参数c由系统自身根据进化阶段动态调整。
    """

    def __init__(self, config: EngineConfig):
        self.config = config
        self.c = config.ucb_c_initial
        self._total_evals = 0
        self._type_evals: dict[str, int] = defaultdict(int)

    def score(self, normalized_score: float, axiom_type: str) -> float:
        """
        计算UCB分数

        Args:
            normalized_score: 标准化后的利用分数 (0.0~1.0)
            axiom_type: 公理类型

        Returns:
            ucb_score: UCB综合分数
        """
        self._total_evals += 1
        self._type_evals[axiom_type] += 1

        n_total = max(1, self._total_evals)
        n_type = max(1, self._type_evals.get(axiom_type, 1))

        exploration_bonus = self.c * math.sqrt(math.log(n_total) / n_type)
        ucb_score = normalized_score + exploration_bonus

        return min(1.5, ucb_score)  # 上限1.5，防止探索奖励过大

    def rank_candidates(self, candidates: list[AxiomCandidate]) -> list[tuple[AxiomCandidate, float]]:
        """
        使用UCB对候选公理进行排序

        Returns:
            [(candidate, ucb_score), ...] 按UCB分数降序排列
        """
        scored = []
        for candidate in candidates:
            normalized = candidate.ibe_score  # IBE作为利用分数
            ucb = self.score(normalized, candidate.type.value)
            scored.append((candidate, ucb))
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored

    def adapt_c(self, budget_level: BudgetLevel, stagnation_severity: float):
        """
        根据预算和停滞程度动态调整探索系数c

        - 预算充足 + 严重停滞 → 提高c (鼓励探索)
        - 预算紧张 → 降低c (保守利用)
        """
        if budget_level == BudgetLevel.ABUNDANT and stagnation_severity > 0.7:
            self.c = min(self.config.ucb_c_max, self.c * 1.2)
        elif budget_level == BudgetLevel.TIGHT:
            self.c = max(self.config.ucb_c_min, self.c * 0.8)
        # 中等预算: 保持当前c
        self._log(f"UCB c值调整至 {self.c:.3f}")

    def get_stats(self) -> dict:
        return {
            "c_parameter": self.c,
            "total_evaluations": self._total_evals,
            "type_distribution": dict(self._type_evals)
        }

    def _log(self, msg: str):
        print(f"  [UCB] {msg}")


# ============================================================================
# Part 9: 结构突变算子 (StructureMutator)
# ============================================================================

class StructureMutator:
    """
    结构突变算子
    ------------
    对标GS-004问题的解决方案: 所有规则共享同一结构模板，相似度>90%。

    四种结构突变:
      1. linear_to_state_machine: 线性 → 状态机
      2. singleton_to_ensemble: 单规则 → 多规则投票
      3. discrete_to_continuous: 二值触发 → 连续阈值
      4. tree_to_graph: 层级依赖 → 网状依赖
    """

    MUTATIONS = {
        MutationType.LINEAR_TO_STATE_MACHINE: {
            "description": ("线性 trigger→action→rationale 变为"
                           "状态机: state→transition→next_state"),
            "applicable_when": "规则涉及多个顺序步骤",
            "mutation_rate": 0.05,
            "transform": "_to_state_machine"
        },
        MutationType.SINGLETON_TO_ENSEMBLE: {
            "description": "单规则变为多规则投票: 生成3个变体, 取多数投票结果",
            "applicable_when": "规则在边界条件下判断不一致",
            "mutation_rate": 0.03,
            "transform": "_to_ensemble"
        },
        MutationType.DISCRETE_TO_CONTINUOUS: {
            "description": ("二值触发变为连续阈值: threshold ∈ [0,1] "
                           "替代 is_triggered ∈ {0,1}"),
            "applicable_when": "规则触发过于频繁或过于稀少",
            "mutation_rate": 0.05,
            "transform": "_to_continuous"
        },
        MutationType.TREE_TO_GRAPH: {
            "description": "层级依赖变为网状依赖: 允许跨层级引用",
            "applicable_when": "规则间存在非预期的协同效应",
            "mutation_rate": 0.02,
            "transform": "_to_graph"
        }
    }

    def __init__(self, config: EngineConfig):
        self.config = config
        self.base_rate = config.structure_base_mutation_rate

    def mutate(self, rule: MRRule) -> tuple[MRRule, bool]:
        """
        以概率p对MR规则应用结构突变

        Args:
            rule: 原始规则

        Returns:
            (mutated_rule, was_mutated)
        """
        if random.random() > self.base_rate:
            return rule, False

        # 选择适用的突变
        applicable = self._select_applicable(rule)
        if not applicable:
            return rule, False

        mutation = random.choice(applicable)
        transform_method = getattr(self, self.MUTATIONS[mutation]["transform"])
        mutated = transform_method(rule)

        self._log(f"{rule.id}: {mutation.value}")
        return mutated, True

    def _select_applicable(self, rule: MRRule) -> list[MutationType]:
        """选择对给定规则适用的突变类型"""
        applicable = []
        steps = len(rule.action.split("→"))
        if steps > 1:
            applicable.append(MutationType.LINEAR_TO_STATE_MACHINE)
        applicable.append(MutationType.SINGLETON_TO_ENSEMBLE)  # 通用
        if "触发" in rule.trigger_condition:
            applicable.append(MutationType.DISCRETE_TO_CONTINUOUS)
        applicable.append(MutationType.TREE_TO_GRAPH)  # 通用
        return applicable

    def _to_state_machine(self, rule: MRRule) -> MRRule:
        """线性 → 状态机"""
        new_rule = MRRule(
            id=rule.id,
            name=f"{rule.name} [状态机变体]",
            trigger_condition=rule.trigger_condition,
            action=rule.action.replace("→", "→ [状态转换] →"),
            rationale=rule.rationale,
            derived_from=rule.derived_from,
            generation=rule.generation,
            structure_type="state_machine"
        )
        return new_rule

    def _to_ensemble(self, rule: MRRule) -> MRRule:
        """单规则 → 多规则投票"""
        new_rule = MRRule(
            id=rule.id,
            name=f"{rule.name} [集成变体]",
            trigger_condition=rule.trigger_condition,
            action=f"生成3个变体对'{rule.action[:30]}...'进行多数投票",
            rationale=f"{rule.rationale}\n集成模式: 多个变体降低单一规则的边界判断偏差",
            derived_from=rule.derived_from,
            generation=rule.generation,
            structure_type="ensemble"
        )
        return new_rule

    def _to_continuous(self, rule: MRRule) -> MRRule:
        """二值触发 → 连续阈值"""
        new_rule = MRRule(
            id=rule.id,
            name=f"{rule.name} [连续变体]",
            trigger_condition=rule.trigger_condition.replace("触发", "累积阈值∈[0,1]触发"),
            action=rule.action,
            rationale=f"{rule.rationale}\n连续模式: 使用连续阈值替代二值判断，降低误触发率",
            derived_from=rule.derived_from,
            generation=rule.generation,
            structure_type="continuous"
        )
        return new_rule

    def _to_graph(self, rule: MRRule) -> MRRule:
        """层级依赖 → 网状依赖"""
        new_rule = MRRule(
            id=rule.id,
            name=f"{rule.name} [网状变体]",
            trigger_condition=rule.trigger_condition,
            action=rule.action + " [允许跨层级引用其他规则输出]",
            rationale=f"{rule.rationale}\n网状模式: 允许与其他规则建立横向引用关系",
            derived_from=rule.derived_from,
            generation=rule.generation,
            structure_type="graph"
        )
        return new_rule

    def compute_similarity_matrix(self, rules: list[MRRule]) -> dict[str, float]:
        """计算规则间结构相似度矩阵"""
        similarities = {}
        for i, r1 in enumerate(rules):
            for j, r2 in enumerate(rules):
                if i < j:
                    sim = r1.similarity_to(r2)
                    similarities[f"{r1.id}-{r2.id}"] = sim
        return similarities

    def _log(self, msg: str):
        print(f"  [结构突变] {msg}")


# ============================================================================
# Part 10: 自动回滚机制 (AutoRollback)
# ============================================================================

class AutoRollback:
    """
    自动回滚机制
    ------------
    对标Layer 0安全基座的自动回滚。

    检测各维度ESV的连续退化:
      - 任意维度连续5代ESV下降 → 标记退化
      - 退化公理的权重自动衰减 (0.9^n)
      - 权重低于0.1 → 自动禁用 + 告警
    """

    def __init__(self, config: EngineConfig):
        self.config = config

    def check_degradation(self, rule: MRRule,
                           esv_history: list[ESVRecord]) -> dict:
        """
        检测退化并自动执行降权/禁用

        Returns:
            {action: NONE|DECAY|DISABLE, reason: str, new_weight: float}
        """
        if not esv_history or len(esv_history) < self.config.rollback_degradation_window:
            return {"action": "NONE", "reason": "数据不足", "new_weight": rule.weight}

        # 检查每个维度的单调退化
        degradation_dims = []
        for dim in self.config.esv_dimensions:
            recent_values = [r.dimensions.get(dim, 0) for r in esv_history[-self.config.rollback_degradation_window:]]
            # 检测是否单调下降
            if self._is_monotonic_decline(recent_values):
                degradation_dims.append(dim)

        if not degradation_dims:
            return {"action": "NONE", "reason": "无退化", "new_weight": rule.weight}

        # 计算新权重
        current_weight = rule.weight
        if current_weight <= self.config.rollback_disable_threshold:
            return {
                "action": "DISABLE",
                "reason": f"权重{current_weight:.3f}低于禁用阈值{self.config.rollback_disable_threshold}",
                "new_weight": current_weight,
                "degradation_dims": degradation_dims
            }

        new_weight = current_weight * self.config.rollback_decay_rate
        return {
            "action": "DECAY",
            "reason": f"维度{degradation_dims}连续退化，权重{current_weight:.3f}→{new_weight:.3f}",
            "new_weight": new_weight,
            "degradation_dims": degradation_dims
        }

    def _is_monotonic_decline(self, values: list[float]) -> bool:
        """检测序列是否单调下降"""
        if len(values) < 2:
            return False
        for i in range(1, len(values)):
            if values[i] >= values[i-1]:
                return False
        return True

    def apply_decay(self, rule: MRRule, decay_result: dict):
        """应用衰减结果"""
        action = decay_result.get("action", "NONE")
        if action == "DECAY":
            rule.weight = decay_result["new_weight"]
            rule.status = RuleStatus.DEGRADING
        elif action == "DISABLE":
            rule.weight = decay_result["new_weight"]
            rule.status = RuleStatus.DISABLED
            self._log(f"!!! 告警: {rule.id} 已自动禁用 !!!")

    def _log(self, msg: str):
        print(f"  [自动回滚] {msg}")


# ============================================================================
# Part 11: 算力感知规划器 (ComputeAwarePlanner)
# ============================================================================

class ComputeAwarePlanner:
    """
    算力感知战略规划器
    ------------------
    对标DGM-H涌现的compute-aware planning。

    根据算力预算剩余比例，切换策略模式:
      - 充足 (>60%): 鼓励架构创新、大规模重构、跨域借鉴、高风险探索
      - 中等 (30-60%): 鼓励增量改进、参数调优、公理二次优化
      - 紧张 (<30%): 优先Bug修复、文档化、规则精简、准备Checkpoint
    """

    def __init__(self, config: EngineConfig):
        self.config = config

    def assess(self, remaining_budget_ratio: float) -> BudgetLevel:
        """评估当前预算级别"""
        if remaining_budget_ratio > self.config.budget_abundant:
            return BudgetLevel.ABUNDANT
        elif remaining_budget_ratio > self.config.budget_moderate:
            return BudgetLevel.MODERATE
        else:
            return BudgetLevel.TIGHT

    def get_strategy(self, level: BudgetLevel) -> dict:
        """根据预算级别获取策略建议"""
        strategies = {
            BudgetLevel.ABUNDANT: {
                "label": "预算充足 — 进攻模式",
                "encourage": [
                    "架构级创新 (大规模规则重构)",
                    "跨域借鉴 (扫描外部论文/Colony-025追踪)",
                    "启动高风险高回报的哥德尔跳探索",
                    "结构突变算子全量激活",
                    "增加UCB探索系数c"
                ],
                "discourage": [
                    "过度保守的增量优化",
                    "过早收敛"
                ],
                "ucb_c_multiplier": 1.2,
                "structure_mutation_multiplier": 1.5,
                "max_axioms_per_cycle": 3
            },
            BudgetLevel.MODERATE: {
                "label": "预算中等 — 平衡模式",
                "encourage": [
                    "增量改进 (优化现有规则)",
                    "参数调优 (UCB的c值、门禁阈值)",
                    "对已有公理的二次操作化优化",
                    "选择性结构突变 (仅对低相似度规则)"
                ],
                "discourage": [
                    "大规模不必要重构",
                    "未经沙箱验证的高风险探索"
                ],
                "ucb_c_multiplier": 1.0,
                "structure_mutation_multiplier": 1.0,
                "max_axioms_per_cycle": 2
            },
            BudgetLevel.TIGHT: {
                "label": "预算紧张 — 保守模式",
                "encourage": [
                    "优先Bug修复",
                    "文档化 + 稳定化",
                    "精简规则 (合并冗余MR规则)",
                    "准备Checkpoint (为下次会话保留完整状态)",
                    "暂停新公理生成"
                ],
                "discourage": [
                    "新功能开发",
                    "哥德尔跳探索",
                    "结构突变",
                    "跨域迁移尝试"
                ],
                "ucb_c_multiplier": 0.5,
                "structure_mutation_multiplier": 0.0,
                "max_axioms_per_cycle": 0
            }
        }
        return strategies.get(level, strategies[BudgetLevel.MODERATE])

    def compute_budget_ratio(self, used_iterations: int, total_budget: int,
                              elapsed_time_min: int, total_time_budget: int) -> float:
        """综合计算预算剩余比例"""
        iter_ratio = 1.0 - (used_iterations / max(1, total_budget))
        time_ratio = 1.0 - (elapsed_time_min / max(1, total_time_budget))
        # 取较保守的估计
        return min(iter_ratio, time_ratio)


# ============================================================================
# Part 12: 主引擎 — AutoGEEngine
# ============================================================================

class AutoGEEngine:
    """
    Auto-GE 自动化哥德尔引擎 (主控制器)
    ------------------------------------
    编排所有子系统，实现从事件触发到持续性循环的完整Auto-GE流程。

    主循环:
      1. 检查触发条件 → 2. 状态快照 → 3. 盲点搜索
      → 4. 公理生成 → 5. 安全门禁 → 6. 沙箱验证
      → 7. UCB排序 → 8. MR规则化 → 9. 写入持久记忆 → 循环
    """

    def __init__(self, config: EngineConfig = None):
        self.config = config or EngineConfig()
        self.memory = EvolutionMemory(self.config)
        self.gs_detector = GSSyndromeDetector(self.config)
        self.blind_spot_search = BlindSpotSearch(self.config)
        self.axiom_generator = AxiomGenerator(self.config)
        self.safety_gate = SafetyGate(self.config, self.memory)
        self.sandbox = SandboxValidator(self.config)
        self.ucb_merge = UCBMerge(self.config)
        self.structure_mutator = StructureMutator(self.config)
        self.auto_rollback = AutoRollback(self.config)
        self.planner = ComputeAwarePlanner(self.config)

        # 运行时状态
        self.esv_history: list[ESVRecord] = []
        self.rules: list[MRRule] = []
        self.current_gen: int = 0
        self.is_running: bool = False
        self.cycle_count: int = 0
        self.stats: dict = {
            "total_cycles": 0,
            "total_triggers": 0,
            "total_axioms_generated": 0,
            "total_axioms_merged": 0,
            "total_sandbox_tests": 0,
            "total_rollbacks": 0,
            "start_time": None
        }

    # ---- 初始化 ----

    def initialize(self, load_memory: bool = True):
        """初始化引擎"""
        print("=" * 60)
        print("  Auto-GE 自动化哥德尔引擎 v1.0")
        print("  Colony-039 L5 Hyperagents")
        print("=" * 60)

        if load_memory:
            self.memory.load()
            self.current_gen = self.memory.current_gen

        self.stats["start_time"] = datetime.now().isoformat()
        self._log("引擎初始化完成", f"当前代数={self.current_gen}")
        self._print_memory_stats()

    # ---- 主循环 ----

    def run_cycle(self, esv_record: ESVRecord = None,
                  external_catalyst: TriggerSignal = None) -> dict:
        """
        执行一次Auto-GE循环

        Args:
            esv_record: 最新ESV记录 (可选，无则使用历史)
            external_catalyst: 外部触媒信号 (可选)

        Returns:
            循环结果摘要
        """
        self.cycle_count += 1
        self.stats["total_cycles"] += 1

        print(f"\n{'='*60}")
        print(f"  Auto-GE 循环 #{self.cycle_count} | Gen-{self.current_gen}")
        print(f"{'='*60}")

        result = {
            "cycle": self.cycle_count,
            "gen": self.current_gen,
            "triggered": False,
            "phase1_completed": False,
            "phase2_completed": False,
            "axioms_generated": [],
            "axioms_passed": [],
            "actions_taken": []
        }

        # 0. 更新ESV历史
        if esv_record:
            self.esv_history.append(esv_record)
            self.current_gen = esv_record.gen
            self.memory.current_gen = self.current_gen
            self.memory.update_performance_trends(self.esv_history)

        # ---- 触发检测 ----
        print("\n[阶段0] 触发检测...")
        triggers = self._detect_triggers(external_catalyst)

        if not triggers:
            print("  无触发条件满足，跳过本次循环")
            return result

        result["triggered"] = True
        self.stats["total_triggers"] += 1

        for sig in triggers:
            print(f"  触发: {sig.trigger_type.value} | 严重度={sig.severity:.2f}")
            print(f"    详情: {sig.details}")
            self.memory.log_trigger(sig)

        # 算力感知
        budget = self._assess_budget()
        strategy = self.planner.get_strategy(budget)
        print(f"\n  算力预算: {budget.value} → {strategy['label']}")

        if budget == BudgetLevel.TIGHT:
            print("  预算紧张 — 仅执行维护操作，跳过公理生成")
            self._maintenance_mode()
            return result

        # ---- 阶段一: 元认知自检 ----
        print("\n[阶段一] 元认知自检 (Metacognitive Self-Inspection)...")
        phase1_result = self._phase1_metacognition(strategy)
        result["phase1_completed"] = True
        result["axioms_generated"] = [a.id for a in phase1_result.get("candidates", [])]

        # ---- 阶段二: 实证验证 ----
        print("\n[阶段二] 实证验证 (Empirical Validation)...")
        phase2_result = self._phase2_validation(phase1_result, strategy)
        result["phase2_completed"] = True
        result["axioms_passed"] = [a.id for a in phase2_result.get("passed", [])]

        # ---- 后处理 ----
        self._post_cycle_actions(phase2_result, strategy)

        # 保存记忆
        self.memory.save()
        self.memory.export_lineage()

        print(f"\n  循环 #{self.cycle_count} 完成")
        print(f"    候选公理: {len(result['axioms_generated'])}")
        print(f"    通过验证: {len(result['axioms_passed'])}")

        return result

    def run_continuous(self, max_cycles: int = 100, interval_seconds: float = 1.0):
        """
        持续循环模式
        对标DGM-H的持续自我修改循环
        """
        self.is_running = True
        print(f"\n启动持续循环模式 (最大{max_cycles}次)...")
        try:
            while self.is_running and self.cycle_count < max_cycles:
                # 模拟生成新ESV记录
                esv = self._simulate_esv_generation()
                self.run_cycle(esv_record=esv)
                self.current_gen += 1
                time.sleep(interval_seconds)
        except KeyboardInterrupt:
            print("\n收到中断信号，正在安全退出...")
        finally:
            self.shutdown()

    # ---- 阶段一: 元认知自检 ----

    def _phase1_metacognition(self, strategy: dict) -> dict:
        """阶段一: 状态快照 + 盲点搜索 + 公理生成"""
        # 1.1 状态快照
        print("  1.1 采集F_t完整状态快照...")
        f_t_snapshot = self._capture_f_t_state()
        print(f"    规则数={f_t_snapshot['rule_count']}, "
              f"ESV维度={len(f_t_snapshot['esv_dimensions'])}")

        # 1.2 盲点搜索
        print("  1.2 运行三种盲点搜索方法...")
        active_theories = self._get_active_theories()
        rule_patterns = [r.structure_type for r in self.rules]
        blind_spots = self.blind_spot_search.search_all(
            self.esv_history,
            active_theories=active_theories,
            rule_patterns=rule_patterns
        )
        print(f"    发现 {len(blind_spots)} 个盲点:")
        for spot in blind_spots[:5]:
            print(f"      {spot.id}: [{spot.method}] 严重度={spot.severity:.2f} — {spot.description[:60]}...")

        # 1.3 公理候选生成
        print("  1.3 自动生成公理候选...")
        max_axioms = strategy.get("max_axioms_per_cycle", 2)
        candidates = self.axiom_generator.generate_candidates(
            blind_spots, self.current_gen, f_t_snapshot
        )
        # 限制数量
        candidates = candidates[:max_axioms]
        self.stats["total_axioms_generated"] += len(candidates)
        print(f"    生成 {len(candidates)} 条公理候选:")
        for c in candidates:
            print(f"      {c.summary()}")

        return {
            "f_t_snapshot": f_t_snapshot,
            "blind_spots": blind_spots,
            "candidates": candidates
        }

    # ---- 阶段二: 实证验证 ----

    def _phase2_validation(self, phase1_result: dict, strategy: dict) -> dict:
        """阶段二: 安全门禁 + 沙箱验证 + UCB排序 + MR规则化"""
        candidates = phase1_result.get("candidates", [])

        if not candidates:
            return {"passed": [], "rejected": [], "glq_records": []}

        passed = []
        rejected = []
        glq_records = []

        # 2.1 UCB排序
        print("  2.1 UCB探索奖励排序...")
        ranked = self.ucb_merge.rank_candidates(candidates)
        for candidate, ucb_score in ranked:
            print(f"    {candidate.id}: UCB={ucb_score:.3f} (IBE={candidate.ibe_score:.2f})")

        # 对每个候选进行安全门禁 + 沙箱验证
        for candidate, ucb_score in ranked:
            print(f"\n  2.2 处理候选: {candidate.id} — {candidate.name}")

            # 安全门禁
            print("    安全门禁检查...")
            gate_result = self.safety_gate.check(candidate, self.rules)
            if not gate_result["passed"]:
                print(f"    未通过安全门禁:")
                for name, check in gate_result["checks"].items():
                    status = "✓" if check["passed"] else "✗"
                    print(f"      {status} {check['name']}: {check['detail']}")
                rejected.append(candidate)
                # 记录失败
                glq_records.append({
                    "axiom_id": candidate.id,
                    "passed": False,
                    "reason": "安全门禁未通过",
                    "gate_details": {k: v["passed"] for k, v in gate_result["checks"].items()}
                })
                continue

            print("    安全门禁通过 ✓")

            # 沙箱验证
            print("    沙箱验证 (5代模拟)...")
            self.stats["total_sandbox_tests"] += 1
            sandbox_result = self.sandbox.validate(candidate)
            print(f"    结果: {sandbox_result.summary}")

            if sandbox_result.passed:
                passed.append(candidate)
                self.stats["total_axioms_merged"] += 1

                # 记录哥德尔跳
                glq = {
                    "passed": True,
                    "sandbox_delta": sandbox_result.metrics["avg_delta_magnitude"],
                    "gate_passed": True
                }
                glq_records.append({"axiom_id": candidate.id, "passed": True, "glq": glq})
                self.memory.log_godel_leap(candidate, glq)

                # 操作化为MR规则候选
                mr_rule = self._axiom_to_mr_rule(candidate)
                if mr_rule:
                    # 结构突变
                    mutated_rule, was_mutated = self.structure_mutator.mutate(mr_rule)
                    self.rules.append(mutated_rule)
                    self.memory.add_rule_to_lineage(mutated_rule.id, candidate.id, self.current_gen)

                # 添加洞察
                insight = EvolutionInsight(
                    id=f"INS-{self.current_gen:03d}{len(self.memory.data.get('synthesized_insights',[]))+1:03d}",
                    discovered_at_gen=self.current_gen,
                    causal_hypothesis=f"盲点{candidate.source_blind_spot}通过{candidate.id}操作化为规则",
                    action_taken=f"{candidate.id} → MR规则",
                    cross_reference=f"对照DGM-H: {candidate.type.value}类自我修改"
                )
                self.memory.add_insight(insight)

                # 更新谱系
                self.memory.add_axiom_to_lineage(
                    candidate.id, "", self.current_gen, candidate.type.value
                )

                print(f"    公理{candidate.id}已通过验证并MR规则化 ✓")
            else:
                rejected.append(candidate)
                glq_records.append({
                    "axiom_id": candidate.id,
                    "passed": False,
                    "reason": "沙箱验证未通过",
                    "sandbox_summary": sandbox_result.summary
                })
                print(f"    公理{candidate.id}未通过沙箱验证 ✗")

        return {
            "passed": passed,
            "rejected": rejected,
            "glq_records": glq_records
        }

    # ---- 辅助方法 ----

    def _detect_triggers(self, external_catalyst: TriggerSignal = None) -> list[TriggerSignal]:
        """检测所有触发条件"""
        triggers = []

        # 内置触发条件
        if self.esv_history:
            builtin = self.gs_detector.check_trigger_conditions(
                self.esv_history,
                self.memory.get_last_leap_gen()
            )
            triggers.extend(builtin)

        # 外部触媒
        if external_catalyst:
            triggers.append(external_catalyst)

        return triggers

    def _capture_f_t_state(self) -> dict:
        """采集当前F_t完整状态快照"""
        latest_esv = self.esv_history[-1].dimensions if self.esv_history else {}
        diagnosis = self.gs_detector.diagnose(self.esv_history) if self.esv_history else None

        return {
            "gen": self.current_gen,
            "rule_count": len(self.rules),
            "active_rules": sum(1 for r in self.rules if r.status == RuleStatus.ACTIVE),
            "esv_dimensions": {
                dim: {
                    "current": latest_esv.get(dim, 0),
                    "saturated": latest_esv.get(dim, 0) >= self.config.esv_scale_max * self.config.esv_saturation_zone
                }
                for dim in self.config.esv_dimensions
            },
            "gs_composite": diagnosis.composite if diagnosis else 0,
            "gs_primary": diagnosis.primary_syndrome if diagnosis else "",
            "plateau_dimensions": self.memory.data.get("performance_trends", {}).get(
                "current_plateau_dimensions", []),
            "last_godel_leap_gen": self.memory.get_last_leap_gen(),
            "insights_pending": len(self.memory.get_pending_insights())
        }

    def _get_active_theories(self) -> list[dict]:
        """获取未操作化的活跃理论列表"""
        # 默认理论库 (对标Colony-021的5项未操作化理论)
        return [
            {"name": "量子达尔文主义 (Zurek)", "core_concept": "信息广播效率=物理选择标准",
             "operationalized": False, "relevance": 0.9},
            {"name": "自由能原理 (Friston)", "core_concept": "系统最小化变分自由能",
             "operationalized": False, "relevance": 0.85},
            {"name": "冯诺依曼通用构造器", "core_concept": "复杂度阈值后构造器可自举",
             "operationalized": False, "relevance": 0.8},
            {"name": "哥德尔机 (Schmidhuber)", "core_concept": "系统应证明重写最优再执行",
             "operationalized": False, "relevance": 0.75},
            {"name": "Chaitin Omega", "core_concept": "某些真理无理由为真(随机公理)",
             "operationalized": False, "relevance": 0.7},
        ]

    def _assess_budget(self) -> BudgetLevel:
        """评估当前算力预算"""
        # 简化: 基于已执行循环数
        max_cycles = 100  # 假设总预算
        ratio = 1.0 - (self.cycle_count / max_cycles)
        return self.planner.assess(ratio)

    def _axiom_to_mr_rule(self, candidate: AxiomCandidate) -> Optional[MRRule]:
        """将公理候选操作化为MR规则"""
        rule_id = f"MR-{self.current_gen:03d}{len(self.rules)+1:03d}"
        # 从操作化方案中提取触发条件和动作
        plan = candidate.operation_plan
        steps = plan.split(")") if ")" in plan else [plan]
        trigger = steps[0].strip() if steps else "自动触发"
        action = plan

        rule = MRRule(
            id=rule_id,
            name=candidate.name,
            trigger_condition=trigger[:200],
            action=action[:500],
            rationale=candidate.statement[:300],
            derived_from=candidate.id,
            generation=self.current_gen
        )
        return rule

    def _post_cycle_actions(self, phase2_result: dict, strategy: dict):
        """循环后处理: 自动回滚检查 + 结构多样性评估"""
        # 自动回滚检查
        for rule in self.rules:
            if rule.status == RuleStatus.ACTIVE:
                rollback = self.auto_rollback.check_degradation(rule, self.esv_history)
                if rollback["action"] in ("DECAY", "DISABLE"):
                    self.auto_rollback.apply_decay(rule, rollback)
                    self.stats["total_rollbacks"] += 1

        # 结构多样性评估
        if len(self.rules) >= 3:
            similarity_matrix = self.structure_mutator.compute_similarity_matrix(self.rules)
            avg_similarity = sum(similarity_matrix.values()) / len(similarity_matrix) if similarity_matrix else 0
            if avg_similarity > 0.85:
                print(f"  ⚠ 结构同质性警告: 平均相似度={avg_similarity:.2%}")
                print(f"    建议: 提高结构突变率以增加多样性")

    def _maintenance_mode(self):
        """预算紧张时的维护模式"""
        print("  [维护] 检查退化规则...")
        for rule in self.rules:
            rollback = self.auto_rollback.check_degradation(rule, self.esv_history)
            if rollback["action"] in ("DECAY", "DISABLE"):
                self.auto_rollback.apply_decay(rule, rollback)

    def _simulate_esv_generation(self) -> ESVRecord:
        """模拟生成新的ESV记录 (Demo用)"""
        if self.esv_history:
            prev = self.esv_history[-1].dimensions
        else:
            prev = {dim: 2.5 for dim in self.config.esv_dimensions}

        new_dims = {}
        new_deltas = {}
        for dim in self.config.esv_dimensions:
            # 模拟: 接近天花板的维度更难增长
            noise = random.gauss(0, 0.02)
            ceiling_effect = max(0, 1 - prev[dim] / self.config.esv_scale_max)
            delta = noise * ceiling_effect
            new_val = min(self.config.esv_scale_max, prev[dim] + delta)
            new_dims[dim] = round(new_val, 2)
            new_deltas[dim] = round(delta, 4)

        gen = self.current_gen + 1
        return ESVRecord(gen=gen, dimensions=new_dims, deltas=new_deltas)

    def _print_memory_stats(self):
        """打印记忆统计"""
        stats = self.memory.get_stats()
        print(f"  记忆状态: gen={stats['current_gen']}, "
              f"洞察={stats['total_insights']}(已验证={stats['verified_insights']}), "
              f"失败记录={stats['failed_approaches']}, "
              f"哥德尔跳={stats['godel_leaps']}")

    def shutdown(self):
        """安全关闭引擎"""
        self.is_running = False
        self.memory.save()
        self.memory.export_lineage()
        print("\n" + "=" * 60)
        print("  Auto-GE 引擎已关闭")
        self.print_summary()

    def print_summary(self):
        """打印运行摘要"""
        print(f"  总循环数: {self.stats['total_cycles']}")
        print(f"  总触发次数: {self.stats['total_triggers']}")
        print(f"  总公理生成: {self.stats['total_axioms_generated']}")
        print(f"  总公理采纳: {self.stats['total_axioms_merged']}")
        print(f"  总沙箱测试: {self.stats['total_sandbox_tests']}")
        print(f"  总回滚操作: {self.stats['total_rollbacks']}")
        print(f"  当前代数: {self.current_gen}")
        print(f"  活跃规则数: {sum(1 for r in self.rules if r.status == RuleStatus.ACTIVE)}")
        print(f"  UCB c值: {self.ucb_merge.c:.4f}")
        print("=" * 60)

    def _log(self, action: str, detail: str):
        print(f"[Auto-GE] {action}: {detail}")


# ============================================================================
# Part 13: CLI & Demo
# ============================================================================

def run_demo():
    """Demo模式: 使用模拟数据演示完整Auto-GE流程"""
    print("""
┌──────────────────────────────────────────────────────────────────┐
│            Auto-GE 自动化哥德尔引擎 — Demo 模式                      │
│                                                                  │
│  本Demo演示完整的Auto-GE循环:                                      │
│    1. 注入模拟ESV历史 (模拟gen-103~111的停滞状态)                    │
│    2. GS症候检测 → 触发Auto-GE                                     │
│    3. 阶段一: 状态快照 + 盲点搜索 + 公理生成                         │
│    4. 阶段二: 安全门禁 + 沙箱验证 + UCB排序                         │
│    5. MR规则化 + 结构突变 + 持久记忆写入                            │
└──────────────────────────────────────────────────────────────────┘
""")

    # 配置
    config = EngineConfig(
        memory_path="/d/极限实验室/colonies/colony-039/demo-memory.json",
        lineage_path="/d/极限实验室/colonies/colony-039/demo-lineage.json"
    )

    # 创建引擎
    engine = AutoGEEngine(config)
    engine.initialize(load_memory=False)

    # ---- 模拟数据注入 ----
    print("\n>>> 注入模拟ESV历史 (对标gen-103~111停滞状态)...")

    # 模拟gen-100~111的ESV数据 (对标Colony-021的停滞诊断)
    demo_data = [
        # gen 100: 接近天花板
        ESVRecord(gen=100, dimensions={"L5_SHI": 2.85, "MEM_COMP": 2.80, "SYNC_RATE": 2.70,
                        "PRED_ACC": 2.85, "EXEC_GAP": 2.75},
                  deltas={"L5_SHI": 0.05, "MEM_COMP": 0.05, "SYNC_RATE": 0.05,
                         "PRED_ACC": 0.05, "EXEC_GAP": 0.05}),
        ESVRecord(gen=101, dimensions={"L5_SHI": 2.90, "MEM_COMP": 2.85, "SYNC_RATE": 2.75,
                        "PRED_ACC": 2.90, "EXEC_GAP": 2.80},
                  deltas={"L5_SHI": 0.05, "MEM_COMP": 0.05, "SYNC_RATE": 0.05,
                         "PRED_ACC": 0.05, "EXEC_GAP": 0.05}),
        ESVRecord(gen=102, dimensions={"L5_SHI": 2.95, "MEM_COMP": 2.90, "SYNC_RATE": 2.80,
                        "PRED_ACC": 2.95, "EXEC_GAP": 2.85},
                  deltas={"L5_SHI": 0.05, "MEM_COMP": 0.05, "SYNC_RATE": 0.05,
                         "PRED_ACC": 0.05, "EXEC_GAP": 0.05}),
        # gen 103~111: 停滞 (对标Colony-021数据)
        ESVRecord(gen=103, dimensions={"L5_SHI": 3.00, "MEM_COMP": 3.00, "SYNC_RATE": 2.85,
                        "PRED_ACC": 2.95, "EXEC_GAP": 2.95},
                  deltas={"L5_SHI": 0.0, "MEM_COMP": 0.0, "SYNC_RATE": 0.0,
                         "PRED_ACC": 0.0, "EXEC_GAP": 0.05}),
        ESVRecord(gen=104, dimensions={"L5_SHI": 3.00, "MEM_COMP": 3.00, "SYNC_RATE": 2.90,
                        "PRED_ACC": 2.95, "EXEC_GAP": 2.95},
                  deltas={"L5_SHI": 0.0, "MEM_COMP": 0.0, "SYNC_RATE": 0.05,
                         "PRED_ACC": 0.0, "EXEC_GAP": 0.05}),
        ESVRecord(gen=105, dimensions={"L5_SHI": 3.00, "MEM_COMP": 3.00, "SYNC_RATE": 2.90,
                        "PRED_ACC": 2.95, "EXEC_GAP": 2.95},
                  deltas={"L5_SHI": 0.0, "MEM_COMP": 0.0, "SYNC_RATE": 0.0,
                         "PRED_ACC": 0.0, "EXEC_GAP": 0.05}),
        ESVRecord(gen=106, dimensions={"L5_SHI": 3.00, "MEM_COMP": 3.00, "SYNC_RATE": 2.90,
                        "PRED_ACC": 2.95, "EXEC_GAP": 2.95},
                  deltas={"L5_SHI": 0.0, "MEM_COMP": 0.0, "SYNC_RATE": 0.0,
                         "PRED_ACC": 0.0, "EXEC_GAP": 0.05}),
        ESVRecord(gen=107, dimensions={"L5_SHI": 3.00, "MEM_COMP": 3.00, "SYNC_RATE": 2.90,
                        "PRED_ACC": 2.95, "EXEC_GAP": 2.95},
                  deltas={"L5_SHI": 0.0, "MEM_COMP": 0.0, "SYNC_RATE": 0.0,
                         "PRED_ACC": 0.0, "EXEC_GAP": 0.0}),
        ESVRecord(gen=108, dimensions={"L5_SHI": 3.00, "MEM_COMP": 3.00, "SYNC_RATE": 2.95,
                        "PRED_ACC": 2.95, "EXEC_GAP": 2.95},
                  deltas={"L5_SHI": 0.0, "MEM_COMP": 0.0, "SYNC_RATE": 0.05,
                         "PRED_ACC": 0.0, "EXEC_GAP": 0.05}),
        ESVRecord(gen=109, dimensions={"L5_SHI": 3.00, "MEM_COMP": 3.00, "SYNC_RATE": 2.95,
                        "PRED_ACC": 2.95, "EXEC_GAP": 2.95},
                  deltas={"L5_SHI": 0.0, "MEM_COMP": 0.0, "SYNC_RATE": 0.0,
                         "PRED_ACC": 0.0, "EXEC_GAP": 0.0}),
        ESVRecord(gen=110, dimensions={"L5_SHI": 3.00, "MEM_COMP": 3.00, "SYNC_RATE": 2.95,
                        "PRED_ACC": 2.95, "EXEC_GAP": 2.95},
                  deltas={"L5_SHI": 0.0, "MEM_COMP": 0.0, "SYNC_RATE": 0.05,
                         "PRED_ACC": 0.0, "EXEC_GAP": 0.0}),
        ESVRecord(gen=111, dimensions={"L5_SHI": 3.00, "MEM_COMP": 3.00, "SYNC_RATE": 2.95,
                        "PRED_ACC": 2.95, "EXEC_GAP": 2.95},
                  deltas={"L5_SHI": 0.0, "MEM_COMP": 0.0, "SYNC_RATE": 0.05,
                         "PRED_ACC": 0.0, "EXEC_GAP": 0.0}),
    ]

    # 加载历史
    engine.esv_history = demo_data[:8]  # 先加载前8代
    engine.current_gen = 107

    # 模拟一些已有规则
    engine.rules = [
        MRRule(id="MR-001", name="ESV自评规则", trigger_condition="每代评估ESV",
               action="计算5维ESV → 记录Δ", rationale="基础进化度量",
               generation=94, structure_type="linear"),
        MRRule(id="MR-013", name="Anti-Hebbian签名挑战", trigger_condition="连续5次100%匹配",
               action="注入随机挑战 → 验证签名鲁棒性", rationale="防止签名过稳定",
               generation=100, structure_type="linear"),
        MRRule(id="MR-023", name="Δ-语义鉴别规则", trigger_condition="连续3代Δ=0",
               action="注入ε探测 → 区分真最优vs评估饱和", rationale="执行AX-021-001",
               generation=115, structure_type="linear"),
    ]

    # ---- 执行GS诊断 ----
    print("\n>>> GS症候检测 (基于gen-103~107数据)...")
    diagnosis = engine.gs_detector.diagnose(engine.esv_history)
    print(f"  GS综合指数: {diagnosis.composite:.2f}/3.0")
    print(f"  主触发症候: {diagnosis.primary_syndrome}")
    print(f"  触发建议: {'是' if diagnosis.trigger_recommendation else '否'}")
    print(f"\n  雷达图数据:")
    for cat, score in diagnosis.radar_data.items():
        bar = "█" * int(score * 5) + "░" * (15 - int(score * 5))
        print(f"    {cat}: [{bar}] {score:.2f}")

    # ---- 加载更多数据触发停滞 ----
    print("\n>>> 加载更多停滞数据 (gen-108~111)...")
    engine.esv_history = demo_data
    engine.current_gen = 111

    # ---- 使用最新gen数据执行一次完整Auto-GE循环 ----
    print("\n>>> 执行Auto-GE循环 (gen=112)...")
    new_esv = ESVRecord(
        gen=112,
        dimensions={"L5_SHI": 3.00, "MEM_COMP": 3.00, "SYNC_RATE": 2.95,
                     "PRED_ACC": 2.95, "EXEC_GAP": 2.95},
        deltas={"L5_SHI": 0.0, "MEM_COMP": 0.0, "SYNC_RATE": 0.0,
                "PRED_ACC": 0.0, "EXEC_GAP": 0.0}
    )

    result = engine.run_cycle(esv_record=new_esv)

    # ---- 打印最终状态 ----
    print("\n\n" + "=" * 60)
    print("  Demo 完成 — 最终状态")
    print("=" * 60)
    engine.print_summary()

    # 打印生成的公理
    if result.get("axioms_generated"):
        print(f"\n  生成的公理候选 ({len(result['axioms_generated'])}):")
        for aid in result["axioms_generated"]:
            print(f"    - {aid}")
    if result.get("axioms_passed"):
        print(f"\n  通过验证的公理 ({len(result['axioms_passed'])}):")
        for aid in result["axioms_passed"]:
            print(f"    - {aid} ✓")

    # 打印持久记忆状态
    print(f"\n  持久记忆状态:")
    for ins in engine.memory.data.get("synthesized_insights", []):
        print(f"    {ins['id']}: [{ins['status']}] {ins['causal_hypothesis'][:80]}...")

    # 打印UCB统计
    ucb_stats = engine.ucb_merge.get_stats()
    print(f"\n  UCB探索统计: c={ucb_stats['c_parameter']:.3f}, "
          f"总评估={ucb_stats['total_evaluations']}")

    engine.shutdown()
    print("\nDemo 执行完毕。")


def run_continuous_demo():
    """持续循环Demo (短时间运行)"""
    config = EngineConfig(
        memory_path="/d/极限实验室/colonies/colony-039/demo-memory.json"
    )
    engine = AutoGEEngine(config)
    engine.initialize(load_memory=False)

    # 注入初始数据
    engine.esv_history = [
        ESVRecord(gen=1, dimensions={dim: 1.0 for dim in config.esv_dimensions},
                  deltas={dim: 0.5 for dim in config.esv_dimensions}),
    ]
    engine.current_gen = 1

    print("\n启动持续循环 (5代)...")
    for _ in range(5):
        esv = engine._simulate_esv_generation()
        engine.run_cycle(esv_record=esv)
        engine.current_gen = esv.gen

    engine.shutdown()


def main():
    """CLI入口"""
    import argparse

    parser = argparse.ArgumentParser(
        description="Auto-GE 自动化哥德尔引擎 v1.0 (Colony-039)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python auto-ge-engine.py                     # Demo模式
  python auto-ge-engine.py --continuous        # 持续循环Demo (5代)
  python auto-ge-engine.py --trigger-once      # 单次触发
  python auto-ge-engine.py --config my_config.json  # 自定义配置
        """
    )
    parser.add_argument("--demo", action="store_true", default=True,
                       help="运行Demo模式 (默认)")
    parser.add_argument("--continuous", action="store_true",
                       help="持续循环Demo模式")
    parser.add_argument("--trigger-once", action="store_true",
                       help="单次触发模式")
    parser.add_argument("--config", type=str,
                       help="配置文件路径 (JSON)")

    args = parser.parse_args()

    if args.continuous:
        run_continuous_demo()
    elif args.trigger_once:
        # 单次触发: 使用最小配置执行一次完整循环
        config = EngineConfig()
        engine = AutoGEEngine(config)
        engine.initialize(load_memory=False)
        engine.esv_history = [
            ESVRecord(gen=1, dimensions={dim: 2.0 for dim in config.esv_dimensions},
                      deltas={dim: 0.0 for dim in config.esv_dimensions}),
            ESVRecord(gen=2, dimensions={dim: 2.0 for dim in config.esv_dimensions},
                      deltas={dim: 0.0 for dim in config.esv_dimensions}),
            ESVRecord(gen=3, dimensions={dim: 2.0 for dim in config.esv_dimensions},
                      deltas={dim: 0.0 for dim in config.esv_dimensions}),
        ]
        engine.current_gen = 3
        esv = ESVRecord(gen=4, dimensions={dim: 2.0 for dim in config.esv_dimensions},
                        deltas={dim: 0.0 for dim in config.esv_dimensions})
        engine.run_cycle(esv_record=esv)
        engine.shutdown()
    else:
        run_demo()


if __name__ == "__main__":
    main()
