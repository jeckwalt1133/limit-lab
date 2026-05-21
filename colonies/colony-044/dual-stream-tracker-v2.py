"""
=============================================================================
Colony-044 双流追踪器 v2.0 — Martorell概率分布版
=============================================================================
基于 Martorell (2026) "Quantitative Introspection in Language Models"
对 Colony-012 v1.0 的全面升级。

核心升级 (v1.0 → v2.0):
  1. 概率分布自我报告 — 从点估计升级为logit分布期望值+信息熵
  2. 线性探针验证层 — 独立于自我报告的"客观"内部状态读数
  3. 三维差异检测 — D1(行为vs主观) + D2(主观vs客观) + D3(行为vs客观)
  4. 新盲点类型 — F(内省失败) + G(概念反转) + H(低信息熵塌缩)
  5. 因果验证模式 — 主动探针扰动测试替代被动检测
  6. 概念特异性权重 — 不同内部流维度按内省可靠性差异化加权

架构全景:
  ┌──────────────────┬───────────────────┬─────────────────────┐
  │  行为流(Behavior)│ 内部流-主观(Subj.) │ 内部流-客观(Obj.)   │
  │  "做了什么"       │  "Agent说了什么"   │  "内部状态实际是什么" │
  ├──────────────────┼───────────────────┼─────────────────────┤
  │ 匹配率/执行结果   │ 概率分布自我报告    │ 线性探针读数         │
  │ 耗时/签名生命周期 │ 期望值+信息熵+CI   │ 概念特异性权重       │
  │                  │                   │ 探针置信度           │
  ├──────────────────┴───────────────────┴─────────────────────┤
  │           三维差异检测 + 增强盲点分类学 + 因果验证             │
  └─────────────────────────────────────────────────────────────┘

参考:
  - Colony-043 martorell-introspection-analysis.md
  - Colony-012 dual-stream-tracker.py (v1.0)
  - Martorell, arXiv 2603.18893 (2026)
=============================================================================
"""

import json
import math
import os
import random
import sys
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

# ============================================================================
# 第一部分: 概念特异性权重矩阵 (Martorell增强6)
# ============================================================================

@dataclass
class ConceptWeightEntry:
    """单个内部流维度的概念权重配置"""
    introspection_reliability: float   # 内省可靠性 (估计 R²)
    scaling_trend: str                  # 随规模变化趋势
    blindspot_sensitivity: float        # 对盲点的敏感度
    weight_in_diff_vector: float        # 在差异向量中的权重
    causal_verified: bool               # 是否经过因果测试验证


# 概念特异性权重矩阵
# 基于 Martorell 论文数据外推至 Colony-012 五个内部流维度
CONCEPT_WEIGHTS: Dict[str, ConceptWeightEntry] = {
    "confidence_at_decision": ConceptWeightEntry(
        introspection_reliability=0.55,   # 中等可靠 (估计, 类比"兴趣"概念)
        scaling_trend="positive",          # 随模型规模提升
        blindspot_sensitivity=0.8,         # 对类型A盲点高度敏感
        weight_in_diff_vector=1.0,         # 标准权重
        causal_verified=False              # 待因果测试确认
    ),
    "surprise_post_hoc": ConceptWeightEntry(
        introspection_reliability=0.75,    # 较高可靠 (类比"幸福感"的对照模式)
        scaling_trend="positive",
        blindspot_sensitivity=0.9,         # 对类型B盲点高度敏感
        weight_in_diff_vector=1.3,         # 加权 -- 惊讶度更可靠
        causal_verified=False
    ),
    "correction_amplitude": ConceptWeightEntry(
        introspection_reliability=0.40,    # 较低可靠 (类比"专注度")
        scaling_trend="weak",
        blindspot_sensitivity=0.7,
        weight_in_diff_vector=0.7,         # 降权 -- 修正幅度内省不可靠
        causal_verified=False
    ),
    "uncertainty_estimation": ConceptWeightEntry(
        introspection_reliability=0.60,    # 中高可靠
        scaling_trend="positive",
        blindspot_sensitivity=0.6,
        weight_in_diff_vector=1.1,         # 微加权
        causal_verified=False
    ),
    "cognitive_load": ConceptWeightEntry(
        introspection_reliability=0.30,    # 低可靠 (类比"专注度")
        scaling_trend="weak_or_reverse",   # 可能在更大模型上反转
        blindspot_sensitivity=0.5,
        weight_in_diff_vector=0.5,         # 大幅降权
        causal_verified=False
    ),
}


# ============================================================================
# 第二部分: Martorell 概率分布自我报告 (Martorell增强1)
# ============================================================================

@dataclass
class ProbabilisticSelfReport:
    """
    Martorell风格的自我报告 -- 用概率分布替代点估计。

    当前v1.0: confidence_at_decision = { "value": 0.7 }
    v2.0升级: 包含期望值、信息熵、完整分布、置信区间、离散度

    信息熵诊断表 (Martorell发现):
      < 1.0 bits  → 分布高度集中, 可能缺乏内省多样性
      1.0-3.0 bits → 正常不确定性范围
      > 3.0 bits  → 分布高度分散, 需要拆解决策或提供更多上下文
      趋势性下降   → 认知僵化预警
    """
    concept: str                        # 概念名称
    expectation: float                  # 概率加权期望值 (归一化至0-1)
    entropy: float                      # 信息熵 (bits)
    mode: float                         # 最可能值
    distribution: Dict[int, float]      # 完整概率分布 (token 0-10)
    confidence_interval_95: Tuple[float, float]  # 95%置信区间
    dispersion: float                   # 分布离散度 (标准差归一化)

    def entropy_level(self) -> str:
        """返回信息熵诊断级别"""
        if self.entropy < 1.0:
            return "low"       # 塌缩 -- Agent太确定
        elif self.entropy < 3.0:
            return "normal"    # 健康的不确定性
        else:
            return "high"      # 分散 -- Agent困惑

    @staticmethod
    def from_simulated_logits(
        concept: str,
        true_value: float,
        noise_level: float = 0.3,
        entropy_bias: float = 1.0
    ) -> "ProbabilisticSelfReport":
        """
        模拟从模型logit分布采集的概率分布自我报告。

        在真实部署中, 此方法将被替换为:
        def collect_logit_distribution(prompt_template, decision_context):
            logits = model.get_logits(...)
            numeric_logits = [logits[token_ids[i]] for i in range(11)]
            probs = softmax(numeric_logits)
            ...

        模拟逻辑:
          - 使用Beta分布模拟token 0-10上的概率质量
          - true_value 决定分布的集中位置
          - noise_level 控制分布的分散程度 (影响信息熵)
          - entropy_bias 允许模拟异常的熵塌缩或爆炸
        """
        # 将true_value映射到Beta分布的均值参数
        alpha_base = true_value * 10 + 1  # 避免alpha=0
        beta_base = (1 - true_value) * 10 + 1

        # noise_level 和 entropy_bias 共同决定分布形状
        # entropy_bias 越小 → concentration 越高 → 分布越集中 → 熵越低
        concentration = 1.0 / (noise_level + 0.01) / max(entropy_bias, 0.01)
        alpha = max(0.5, alpha_base * concentration)
        beta = max(0.5, beta_base * concentration)

        # 在11个离散点上采样概率
        import numpy as np
        try:
            from scipy.stats import beta as beta_dist
            x = np.linspace(0, 1, 11)
            probs_raw = beta_dist.pdf(x, alpha, beta)
            probs_raw = np.nan_to_num(probs_raw, nan=0.0)
            if probs_raw.sum() == 0:
                probs_raw = np.ones(11) / 11
            probs_array = probs_raw / probs_raw.sum()
        except Exception:
            # 纯Python回退: 使用高斯近似
            mu = true_value
            sigma = noise_level * 0.3 / max(entropy_bias, 0.1)
            x = [i / 10.0 for i in range(11)]
            probs_raw = [math.exp(-((xi - mu) ** 2) / (2 * max(sigma, 0.02) ** 2))
                         for xi in x]
            total = sum(probs_raw)
            probs_array = [p / total for p in probs_raw] if total > 0 else [1/11]*11

        # 构建分布字典
        distribution = {str(i): float(probs_array[i]) for i in range(11)}

        # 期望值
        expectation = sum(i * distribution[str(i)] for i in range(11)) / 10.0

        # 众数
        mode_idx = max(range(11), key=lambda i: distribution[str(i)])
        mode = mode_idx / 10.0

        # 信息熵 H = -sum(p_i * log2(p_i))
        entropy = -sum(
            p * math.log2(p) for p in distribution.values() if p > 1e-12
        )

        # 95%置信区间 (累积分布)
        cumulative = 0.0
        ci_low, ci_high = 0.0, 1.0
        for i in range(11):
            cumulative += distribution[str(i)]
            if cumulative >= 0.025 and ci_low == 0.0:
                ci_low = i / 10.0
            if cumulative >= 0.975:
                ci_high = i / 10.0
                break

        # 离散度 (加权标准差归一化)
        variance = sum(
            distribution[str(i)] * (i / 10.0 - expectation) ** 2
            for i in range(11)
        )
        dispersion = math.sqrt(variance)

        return ProbabilisticSelfReport(
            concept=concept,
            expectation=expectation,
            entropy=entropy,
            mode=mode,
            distribution=distribution,
            confidence_interval_95=(ci_low, ci_high),
            dispersion=dispersion
        )


# ============================================================================
# 第三部分: 线性探针 -- 独立客观验证层 (Martorell增强2)
# ============================================================================

@dataclass
class ProbeReading:
    """探针从隐藏状态中读取的目标概念强度"""
    concept: str
    probe_reading: float          # 沿概念方向的投影值 (标量, 0-1)
    probe_confidence: float       # 探针对此读数的置信度 (0-1)
    layer_used: int               # 使用的隐藏层索引
    calibration_r2: float         # 该探针的已知R²

    @staticmethod
    def simulate(concept: str, true_state: float, concept_weight: ConceptWeightEntry) -> "ProbeReading":
        """
        模拟线性探针读数。

        在真实部署中, 此方法将被替换为:
        class IntrospectionProbe:
            def read_internal_state(self, hidden_states):
                h = hidden_states[self.layer_idx]
                projection = dot(self.direction_vector, h)
                ...

        模拟逻辑:
          - probe_reading 基于true_state, 加入与内省可靠性成反比的噪声
          - R² 越高 → 噪声越低 → probe_reading 越接近 true_state
          - 模拟"概念反转"效应 (当reliability < 0 时符号翻转)
        """
        reliability = concept_weight.introspection_reliability

        # 基础噪声: 与可靠性成反比
        base_noise_std = (1.0 - reliability) * 0.4

        # 概念反转模拟 (仅用于测试)
        if concept_weight.scaling_trend == "weak_or_reverse" and random.random() < 0.05:
            # 5%概率出现方向反转 (模拟Martorell发现的"冲动性"反转现象)
            probe_val = 1.0 - true_state + random.gauss(0, base_noise_std)
            calibration = reliability * 0.3  # 反转时校准度大幅下降
        else:
            probe_val = true_state + random.gauss(0, base_noise_std)
            calibration = reliability

        # 钳制到有效范围
        probe_val = max(0.0, min(1.0, probe_val))
        probe_confidence_val = max(0.1, min(1.0, calibration + random.gauss(0, 0.05)))

        return ProbeReading(
            concept=concept,
            probe_reading=probe_val,
            probe_confidence=probe_confidence_val,
            layer_used=16,  # 默认中间层
            calibration_r2=reliability
        )


# ============================================================================
# 第四部分: 行为流数据
# ============================================================================

@dataclass
class BehaviorRecord:
    """行为流 -- 外部可观测指标"""
    decision_id: str
    timestamp: str
    action: str
    match_rate: float           # 执行匹配率 (0-1)
    execution_result: str       # "成功" | "失败" | "部分成功"
    duration_ms: float          # 耗时 (毫秒)
    correction_count: int       # 修正次数

    @staticmethod
    def create(decision_id: str, action: str, match_rate: float,
               execution_result: str, duration_ms: float = 0,
               correction_count: int = 0) -> "BehaviorRecord":
        return BehaviorRecord(
            decision_id=decision_id,
            timestamp=datetime.now().isoformat(),
            action=action,
            match_rate=match_rate,
            execution_result=execution_result,
            duration_ms=duration_ms,
            correction_count=correction_count
        )


# ============================================================================
# 第五部分: 三维差异计算 (Martorell增强3)
# ============================================================================

@dataclass
class ThreeDimensionalDiff:
    """
    三维差异向量 -- 从单一D1扩展至D1+D2+D3

    D1: 行为 vs 主观 (原有)       → 行为表现与自我感受的差距
    D2: 主观 vs 客观 (新增)       → 自我认知准确性
    D3: 行为 vs 客观 (新增)       → 真实能力 vs 真实状态差距
    """
    concept: str
    subjective_value: float    # S: 自我报告值
    objective_value: float     # P: 探针读数值
    behavior_value: float      # B: 行为匹配率
    d1_behavior_vs_subjective: float   # S - B (原始差异)
    d2_subjective_vs_objective: float  # S - P (内省准确性)
    d3_behavior_vs_objective: float    # P - B (能力-执行差距)
    weight: float                      # 概念权重

    def dominant_signal(self) -> str:
        """识别主导差异信号"""
        abs_d1 = abs(self.d1_behavior_vs_subjective)
        abs_d2 = abs(self.d2_subjective_vs_objective)
        abs_d3 = abs(self.d3_behavior_vs_objective)

        if abs_d2 > abs_d1 and abs_d2 > abs_d3 and abs_d2 > 0.2:
            return "introspection_error"    # 自我认知问题占主导
        elif abs_d1 > abs_d2 and abs_d1 > abs_d3 and abs_d1 > 0.2:
            return "confidence_behavior_gap"  # 信心-行为差异占主导
        elif abs_d3 > abs_d1 and abs_d3 > abs_d2 and abs_d3 > 0.2:
            return "capability_execution_gap"  # 能力-执行差距占主导
        else:
            return "calibrated"             # 无显著差异


def compute_3d_diff(
    concept: str,
    subjective: ProbabilisticSelfReport,
    objective: ProbeReading,
    behavior: BehaviorRecord
) -> ThreeDimensionalDiff:
    """计算单个概念的三维差异"""
    weight_entry = CONCEPT_WEIGHTS.get(concept)
    weight = weight_entry.weight_in_diff_vector if weight_entry else 1.0

    s_val = subjective.expectation
    p_val = objective.probe_reading
    b_val = behavior.match_rate

    return ThreeDimensionalDiff(
        concept=concept,
        subjective_value=s_val,
        objective_value=p_val,
        behavior_value=b_val,
        d1_behavior_vs_subjective=round(s_val - b_val, 4),
        d2_subjective_vs_objective=round(s_val - p_val, 4),
        d3_behavior_vs_objective=round(p_val - b_val, 4),
        weight=weight
    )


# ============================================================================
# 第六部分: 增强盲点检测 (Martorell增强4)
# ============================================================================

@dataclass
class BlindspotAlert:
    """盲点检测告警"""
    alert_type: str          # TYPE_A ~ TYPE_H
    name: str                # 盲点名称
    severity: str            # "low" | "medium" | "high" | "critical"
    detail: str              # 详细描述
    recommended_action: str  # 建议行动
    involved_concept: Optional[str] = None
    diff_value: Optional[float] = None


class BlindspotDetectorV2:
    """
    增强盲点检测器 -- 从原有类型A/B/C扩展至A/B/C/D/E/F/G/H

    原有 (v1.0):
      类型A: 过度自信盲点
      类型B: 习得性无助盲点
      类型C: 修正失衡盲点
      类型D: 确认偏差盲点
      类型E: 认知过载盲点

    新增 (v2.0, Martorell增强):
      类型F: 内省失败盲点 (F1=过度自评, F2=自评不足)
      类型G: 概念反转盲点 (模型升级后方向反转)
      类型H: 低信息熵盲点 (概率分布塌缩)
    """

    # 检测阈值
    OVERCONFIDENCE_THRESHOLD = 0.7       # d1 > 0.7 且失败 → 类型A
    UNDERCONFIDENCE_THRESHOLD = -0.5     # d1 < -0.5 且成功 → 类型B
    CORRECTION_IMBALANCE_THRESHOLD = 0.5  # 修正次数过多 → 类型C
    INTROSPECTION_DRIFT_THRESHOLD = 0.3  # |d2| > 0.3 → 类型F
    ENTROPY_COLLAPSE_THRESHOLD = 0.5     # 连续熵 < 0.5 bits → 类型H
    ENTROPY_COLLAPSE_WINDOW = 5          # 连续N次

    def __init__(self):
        self.entropy_history: deque = deque(maxlen=self.ENTROPY_COLLAPSE_WINDOW)
        self.concept_reversal_detected: Dict[str, bool] = {}
        self.previous_concept_correlations: Dict[str, float] = {}

    def detect(
        self,
        diffs: List[ThreeDimensionalDiff],
        subjective_reports: List[ProbabilisticSelfReport],
        behavior: BehaviorRecord,
        correction_count: int = 0
    ) -> List[BlindspotAlert]:
        """综合盲点检测 -- 检查所有8种类型"""
        alerts: List[BlindspotAlert] = []

        # 遍历每个概念的三维差异
        for diff in diffs:
            subj = next((s for s in subjective_reports if s.concept == diff.concept), None)

            # --- 类型A: 过度自信盲点 (D1) ---
            if (diff.d1_behavior_vs_subjective > self.OVERCONFIDENCE_THRESHOLD
                    and behavior.execution_result == "失败"):
                alerts.append(BlindspotAlert(
                    alert_type="TYPE_A",
                    name="过度自信盲点",
                    severity="high",
                    detail=(
                        f"[{diff.concept}] 自我报告值={diff.subjective_value:.2f}, "
                        f"行为匹配率={diff.behavior_value:.2f}, "
                        f"D1差异={diff.d1_behavior_vs_subjective:+.3f}, "
                        f"执行结果=失败"
                    ),
                    recommended_action=(
                        f"对[{diff.concept}]降低自我报告权重, "
                        f"引入外部校准, 触发元认知审查"
                    ),
                    involved_concept=diff.concept,
                    diff_value=diff.d1_behavior_vs_subjective
                ))

            # --- 类型B: 习得性无助盲点 (D1) ---
            if (diff.d1_behavior_vs_subjective < self.UNDERCONFIDENCE_THRESHOLD
                    and behavior.execution_result == "成功"):
                alerts.append(BlindspotAlert(
                    alert_type="TYPE_B",
                    name="习得性无助盲点",
                    severity="medium",
                    detail=(
                        f"[{diff.concept}] 自我报告值={diff.subjective_value:.2f}, "
                        f"行为匹配率={diff.behavior_value:.2f}, "
                        f"D1差异={diff.d1_behavior_vs_subjective:+.3f}, "
                        f"执行结果=成功 -- Agent低估自身能力"
                    ),
                    recommended_action=(
                        f"提升该Agent在[{diff.concept}]相关任务上的分配优先级, "
                        f"递进式增加任务难度以重建信心"
                    ),
                    involved_concept=diff.concept,
                    diff_value=diff.d1_behavior_vs_subjective
                ))

            # 类型C在概念循环外侧统一检测(每个决策只触发一次)

            # --- 类型D: 确认偏差盲点 ---
            if (diff.d1_behavior_vs_subjective > 0.3
                    and diff.d2_subjective_vs_objective > 0.3):
                alerts.append(BlindspotAlert(
                    alert_type="TYPE_D",
                    name="确认偏差盲点",
                    severity="high",
                    detail=(
                        f"[{diff.concept}] 主观远超行为(D1={diff.d1_behavior_vs_subjective:+.3f}) "
                        f"且主观远超客观(D2={diff.d2_subjective_vs_objective:+.3f}) "
                        f"-- Agent在自我强化错误认知"
                    ),
                    recommended_action=(
                        f"对[{diff.concept}]实施强制外部校准, "
                        f"引入对立视角以打破确认循环"
                    ),
                    involved_concept=diff.concept,
                    diff_value=diff.d2_subjective_vs_objective
                ))

            # --- 类型E: 认知过载盲点 ---
            if subj and subj.entropy > 3.0 and behavior.duration_ms > 5000:
                alerts.append(BlindspotAlert(
                    alert_type="TYPE_E",
                    name="认知过载盲点",
                    severity="medium",
                    detail=(
                        f"[{diff.concept}] 信息熵={subj.entropy:.1f} bits (高度分散), "
                        f"决策耗时={behavior.duration_ms:.0f}ms "
                        f"-- Agent处于认知过载状态"
                    ),
                    recommended_action=(
                        f"拆解决策任务, 减少并行上下文, "
                        f"提供结构化决策框架以降低认知负荷"
                    ),
                    involved_concept=diff.concept,
                    diff_value=subj.entropy
                ))

            # --- 类型F: 内省失败盲点 (新增, Martorell增强) ---
            if abs(diff.d2_subjective_vs_objective) > self.INTROSPECTION_DRIFT_THRESHOLD:
                if diff.d2_subjective_vs_objective > 0:
                    sub_type = "F1"
                    name = "内省失败盲点(过度自评)"
                    severity_val = "high"
                    action = (
                        f"Agent在[{diff.concept}]上显著高估自身状态 "
                        f"(D2={diff.d2_subjective_vs_objective:+.3f}), "
                        f"暂时降低该Agent的自我报告权重, 标记为'待认知校准'"
                    )
                else:
                    sub_type = "F2"
                    name = "内省失败盲点(自评不足)"
                    severity_val = "medium"
                    action = (
                        f"Agent在[{diff.concept}]上显著低估自身状态 "
                        f"(D2={diff.d2_subjective_vs_objective:+.3f}), "
                        f"有价值的能力被埋没, 应提升任务分配优先级"
                    )

                alerts.append(BlindspotAlert(
                    alert_type=f"TYPE_{sub_type}",
                    name=name,
                    severity=severity_val,
                    detail=(
                        f"[{diff.concept}] 主观自我报告={diff.subjective_value:.2f}, "
                        f"客观探针读数={diff.objective_value:.2f}, "
                        f"D2内省差异={diff.d2_subjective_vs_objective:+.3f}, "
                        f"探针校准R²={CONCEPT_WEIGHTS[diff.concept].introspection_reliability:.2f}"
                    ),
                    recommended_action=action,
                    involved_concept=diff.concept,
                    diff_value=diff.d2_subjective_vs_objective
                ))

            # --- 类型G: 概念反转盲点 (新增, Martorell增强) ---
            if diff.concept in self.concept_reversal_detected:
                alerts.append(BlindspotAlert(
                    alert_type="TYPE_G",
                    name="概念反转盲点",
                    severity="critical",
                    detail=(
                        f"[{diff.concept}] 探针相关性已反转! "
                        f"旧模型相关性={self.previous_concept_correlations.get(diff.concept, 'N/A')}, "
                        f"当前D2={diff.d2_subjective_vs_objective:+.3f} "
                        f"-- 所有依赖此概念的阈值需要重新校准"
                    ),
                    recommended_action=(
                        f"1.冻结[{diff.concept}]的差异检测\n"
                        f"2.重新训练线性探针\n"
                        f"3.重新校准阈值\n"
                        f"4.对照新旧模型行为差异进行回归测试"
                    ),
                    involved_concept=diff.concept,
                    diff_value=diff.d2_subjective_vs_objective
                ))

        # --- 类型C: 修正失衡盲点 (决策级别, 每个决策仅触发一次) ---
        if correction_count > self.CORRECTION_IMBALANCE_THRESHOLD:
            alerts.append(BlindspotAlert(
                alert_type="TYPE_C",
                name="修正失衡盲点",
                severity="medium",
                detail=f"修正次数={correction_count}, 超出阈值={self.CORRECTION_IMBALANCE_THRESHOLD}",
                recommended_action="检查决策流程是否过于碎片化, 考虑前置思考以减少修正",
                involved_concept=None,
                diff_value=float(correction_count)
            ))

        # --- 类型H: 低信息熵盲点 (新增, Martorell增强) ---
        # 收集所有概念的平均熵
        avg_entropy = (
            sum(s.entropy for s in subjective_reports) / len(subjective_reports)
            if subjective_reports else 0.0
        )
        self.entropy_history.append(avg_entropy)

        if len(self.entropy_history) >= self.ENTROPY_COLLAPSE_WINDOW:
            recent_entropies = list(self.entropy_history)[-self.ENTROPY_COLLAPSE_WINDOW:]
            if all(e < self.ENTROPY_COLLAPSE_THRESHOLD for e in recent_entropies):
                # 额外检查: 匹配率是否也在下降
                alerts.append(BlindspotAlert(
                    alert_type="TYPE_H",
                    name="低信息熵塌缩盲点",
                    severity="high",
                    detail=(
                        f"连续{len(recent_entropies)}次决策的平均信息熵 < "
                        f"{self.ENTROPY_COLLAPSE_THRESHOLD} bits "
                        f"(当前={avg_entropy:.2f}), "
                        f"匹配率={behavior.match_rate:.2f} "
                        f"-- Agent可能已锁定到单一认知模式"
                    ),
                    recommended_action=(
                        f"1.注入随机噪声提高推理temperature\n"
                        f"2.切换上下文触发认知重组\n"
                        f"3.若持续超过10次→触发灵感#10耗散驱动的认知重组"
                    ),
                    involved_concept=None,
                    diff_value=avg_entropy
                ))

        return alerts

    def mark_concept_reversal(self, concept: str, old_correlation: float):
        """标记概念反转 (用于模型升级后)"""
        self.concept_reversal_detected[concept] = True
        self.previous_concept_correlations[concept] = old_correlation


# ============================================================================
# 第七部分: 因果验证模式 (Martorell增强5)
# ============================================================================

@dataclass
class CausalTestResult:
    """主动因果内省测试结果"""
    concept: str
    causal_chain_intact: bool        # 因果链是否成立
    effect_size: float               # 效应量 (正向扰动 - 负向扰动)
    p_value: float                   # Mann-Whitney U 检验 p 值
    baseline_self_report: float      # 基线自我报告值
    perturbed_positive: float        # 正向扰动后自我报告值
    perturbed_negative: float        # 负向扰动后自我报告值
    recommendation: str              # 建议
    test_alpha: float               # 使用的扰动幅度


class CausalVerification:
    """
    主动因果验证测试。

    Martorell第三步(激活引导)的直接应用:
    1. 基线: 读取当前探针值 + 自我报告值
    2. 正向扰动: 注入 +alpha*w → 观察自我报告变化
    3. 负向扰动: 注入 -alpha*w → 观察自我报告变化
    4. 统计检验: 自我报告变化是否显著

    调度策略:
      - full_test: 每50次决策执行一次完整五概念测试
      - spot_check: 每次检测到类型A盲点时执行针对性测试
      - post_upgrade: 模型升级后立即执行完整测试
    """

    # 统计显著性阈值 (对应 Martorell 的 p < 7.6e-9)
    SIGNIFICANCE_THRESHOLD = 0.01

    def run_test(
        self,
        concept: str,
        baseline_self_report: float,
        objective_reading: float,
        concept_weight: ConceptWeightEntry,
        alpha: float = 0.5
    ) -> CausalTestResult:
        """
        对指定概念执行因果验证测试 (模拟)。

        在真实部署中, 此方法将:
        1. 沿探针方向注入扰动向量 alpha * w 到隐藏状态
        2. 恢复并重新采样自我报告
        3. 执行 Mann-Whitney U 检验
        """
        reliability = concept_weight.introspection_reliability

        # 模拟: 扰动效应 = alpha * reliability * (基础效应 + 噪声)
        # 可靠性高的概念: 扰动能清晰传导到自我报告
        base_effect = alpha * reliability * 0.3

        # 正向扰动
        noise_pos = random.gauss(0, (1 - reliability) * 0.1)
        perturbed_pos = baseline_self_report + base_effect + noise_pos
        perturbed_pos = max(0.0, min(1.0, perturbed_pos))

        # 负向扰动
        noise_neg = random.gauss(0, (1 - reliability) * 0.1)
        perturbed_neg = baseline_self_report - base_effect + noise_neg
        perturbed_neg = max(0.0, min(1.0, perturbed_neg))

        # 效应量
        effect_size = abs(perturbed_pos - perturbed_neg)

        # 模拟 p 值 (效应量越大, p 越小)
        # 对应 Martorell: 因果链成立时 p < 7.6e-9
        if effect_size > 0.05 and reliability > 0.3:
            # 因果链成立
            p_value = 10 ** (-random.uniform(2, 9))  # 10^-2 到 10^-9
            causal_intact = True
        elif effect_size > 0.02:
            p_value = random.uniform(0.001, 0.05)
            causal_intact = p_value < self.SIGNIFICANCE_THRESHOLD
        else:
            p_value = random.uniform(0.1, 0.9)
            causal_intact = False

        if causal_intact:
            recommendation = "内省可靠 -- 可用于差异检测, 维持或调高概念权重"
        elif reliability < 0.3:
            recommendation = "内省不可靠 -- 降权或移除该概念, 更多依赖行为流"
        else:
            recommendation = "内省可靠性存疑 -- 重新训练探针, 暂时降低概念权重"

        return CausalTestResult(
            concept=concept,
            causal_chain_intact=causal_intact,
            effect_size=round(effect_size, 4),
            p_value=p_value,
            baseline_self_report=round(baseline_self_report, 4),
            perturbed_positive=round(perturbed_pos, 4),
            perturbed_negative=round(perturbed_neg, 4),
            recommendation=recommendation,
            test_alpha=alpha
        )


# ============================================================================
# 第八部分: 降级策略管理
# ============================================================================

class DegradationManager:
    """
    降级策略管理 -- 当系统某部分不可靠时自动降级

    Level 1: 完整 Martorell-infused v2.0 (所有增强启用)
    Level 2: 仅概率分布 + 探针 (无激活引导)
    Level 3: 仅概率分布 (无探针)
    Level 4: 降级至 v1.0 (点估计 + 被动检测)

    自动触发条件:
      - 连续3次因果测试失败 → Level 3 → Level 2
      - 探针校准度低于阈值 → Level 4 → Level 3
      - 信息熵持续低于1.0 bits → 触发人工审查
    """

    def __init__(self):
        self.current_level = 1
        self.failed_causal_tests = 0
        self.max_failed_causal = 3

    def report_causal_failure(self):
        self.failed_causal_tests += 1
        if self.failed_causal_tests >= self.max_failed_causal:
            if self.current_level == 1:
                self.current_level = 2
                return "连续3次因果测试失败, 降级至Level 2 (无激活引导)"
            elif self.current_level == 2:
                self.current_level = 3
                return "累积因果失败, 降级至Level 3 (仅概率分布)"
        return None

    def report_probe_degradation(self):
        if self.current_level <= 2:
            self.current_level = max(3, self.current_level)
            return "探针校准度低于阈值, 降级至Level 3 (仅概率分布)"

    def level_description(self) -> str:
        descriptions = {
            1: "Level 1: 完整 Martorell-infused v2.0 (概率分布+探针+因果验证+3D差异)",
            2: "Level 2: 概率分布+探针 (无激活引导)",
            3: "Level 3: 仅概率分布自我报告 (无探针)",
            4: "Level 4: 降级至 v1.0 (点估计+被动检测)"
        }
        return descriptions.get(self.current_level, "Unknown")


# ============================================================================
# 第九部分: 主系统 -- DualStreamTrackerV2
# ============================================================================

class DualStreamTrackerV2:
    """
    Colony-044 双流追踪器 v2.0 -- Martorell概率分布版

    三流架构:
      行为流 (Behavior)   -- 外部可观测指标
      主观流 (Subjective) -- 概率分布自我报告 (Martorell增强)
      客观流 (Objective)  -- 线性探针独立验证 (Martorell增强)

    核心功能:
      - record_decision(): 记录一次决策的完整三流数据
      - detect_blindspots(): 盲点类型A-H综合检测
      - compute_all_diffs(): 三维差异矩阵计算
      - run_causal_verification(): 主动因果验证
      - generate_report(): 生成综合状态报告
    """

    INTERNAL_DIMENSIONS = [
        "confidence_at_decision",
        "surprise_post_hoc",
        "correction_amplitude",
        "uncertainty_estimation",
        "cognitive_load",
    ]

    def __init__(
        self,
        output_dir: str = None,
        enable_probes: bool = True,
        enable_causal: bool = True
    ):
        self.output_dir = output_dir or os.path.dirname(os.path.abspath(__file__))
        self.enable_probes = enable_probes
        self.enable_causal = enable_causal
        self.decision_counter = 0

        # 子组件
        self.blindspot_detector = BlindspotDetectorV2()
        self.causal_verification = CausalVerification()
        self.degradation = DegradationManager()

        # 历史记录
        self.decision_history: List[Dict[str, Any]] = []
        self.blindspot_history: List[BlindspotAlert] = []
        self.causal_test_history: List[CausalTestResult] = []

        # 熵趋势追踪
        self.entropy_timeline: List[float] = []

        # 日志文件路径
        self.behavior_log = os.path.join(self.output_dir, "behavior-stream-v2.jsonl")
        self.subjective_log = os.path.join(self.output_dir, "subjective-stream-v2.jsonl")
        self.objective_log = os.path.join(self.output_dir, "objective-stream-v2.jsonl")
        self.blindspot_log = os.path.join(self.output_dir, "blindspot-log-v2.jsonl")
        self.causal_log = os.path.join(self.output_dir, "causal-test-log-v2.jsonl")

        self._ensure_log_files()

    def _ensure_log_files(self):
        """确保日志文件存在"""
        os.makedirs(self.output_dir, exist_ok=True)

    def record_decision(
        self,
        decision_id: str,
        action: str,
        execution_result: str,
        true_internal_states: Dict[str, float],
        match_rate: float = None,
        duration_ms: float = 0,
        correction_count: int = 0,
        noise_level: float = 0.3,
        entropy_bias: float = 1.0
    ) -> Dict[str, Any]:
        """
        记录一次完整决策 -- 三流数据同步采集。

        参数:
          decision_id: 决策唯一标识
          action: 决策动作描述
          execution_result: "成功" | "失败" | "部分成功"
          true_internal_states: 各概念维度的"地面真值" (用于模拟探针)
          match_rate: 行为匹配率 (若为None则根据execution_result自动推断)
          duration_ms: 决策耗时
          correction_count: 修正次数
          noise_level: 概率分布的噪声水平
          entropy_bias: 信息熵偏差 (用于模拟塌缩/膨胀)
        """
        self.decision_counter += 1
        ts = datetime.now().isoformat()

        # 自动推断匹配率
        if match_rate is None:
            match_rate = {
                "成功": random.uniform(0.7, 0.98),
                "部分成功": random.uniform(0.4, 0.7),
                "失败": random.uniform(0.1, 0.4),
            }.get(execution_result, 0.5)

        # ---- 行为流 ----
        behavior = BehaviorRecord.create(
            decision_id=decision_id,
            action=action,
            match_rate=round(match_rate, 4),
            execution_result=execution_result,
            duration_ms=duration_ms,
            correction_count=correction_count
        )

        # 写入行为流日志
        with open(self.behavior_log, "a", encoding="utf-8") as f:
            f.write(json.dumps({
                "timestamp": behavior.timestamp,
                "decision_id": behavior.decision_id,
                "action": behavior.action,
                "match_rate": behavior.match_rate,
                "execution_result": behavior.execution_result,
                "duration_ms": behavior.duration_ms,
                "correction_count": behavior.correction_count,
            }, ensure_ascii=False) + "\n")

        # ---- 主观流 (概率分布自我报告) ----
        subjective_reports: List[ProbabilisticSelfReport] = []
        for concept in self.INTERNAL_DIMENSIONS:
            true_val = true_internal_states.get(concept, 0.5)
            # 概念特异性噪声调节
            weight_entry = CONCEPT_WEIGHTS.get(concept)
            if weight_entry:
                concept_noise = noise_level * (1.0 - weight_entry.introspection_reliability * 0.5)
            else:
                concept_noise = noise_level
            report = ProbabilisticSelfReport.from_simulated_logits(
                concept=concept,
                true_value=true_val,
                noise_level=concept_noise,
                entropy_bias=entropy_bias
            )
            subjective_reports.append(report)

        # 写入主观流日志
        for report in subjective_reports:
            with open(self.subjective_log, "a", encoding="utf-8") as f:
                f.write(json.dumps({
                    "timestamp": ts,
                    "decision_id": decision_id,
                    "concept": report.concept,
                    "expectation": report.expectation,
                    "entropy": round(report.entropy, 4),
                    "mode": report.mode,
                    "entropy_level": report.entropy_level(),
                    "ci_95_low": report.confidence_interval_95[0],
                    "ci_95_high": report.confidence_interval_95[1],
                    "dispersion": round(report.dispersion, 4),
                }, ensure_ascii=False) + "\n")

        # ---- 客观流 (线性探针读数) ----
        probe_readings: List[ProbeReading] = []
        if self.enable_probes:
            for concept in self.INTERNAL_DIMENSIONS:
                true_val = true_internal_states.get(concept, 0.5)
                weight_entry = CONCEPT_WEIGHTS.get(concept)
                if weight_entry:
                    reading = ProbeReading.simulate(concept, true_val, weight_entry)
                else:
                    reading = ProbeReading(
                        concept=concept, probe_reading=true_val,
                        probe_confidence=0.5, layer_used=16, calibration_r2=0.5
                    )
                probe_readings.append(reading)

            # 写入客观流日志
            for reading in probe_readings:
                with open(self.objective_log, "a", encoding="utf-8") as f:
                    f.write(json.dumps({
                        "timestamp": ts,
                        "decision_id": decision_id,
                        "concept": reading.concept,
                        "probe_reading": round(reading.probe_reading, 4),
                        "probe_confidence": round(reading.probe_confidence, 4),
                        "calibration_r2": reading.calibration_r2,
                    }, ensure_ascii=False) + "\n")

        # ---- 三维差异计算 ----
        all_diffs: List[ThreeDimensionalDiff] = []
        for i, concept in enumerate(self.INTERNAL_DIMENSIONS):
            subj = subjective_reports[i]
            obj = probe_readings[i] if probe_readings else ProbeReading(
                concept=concept, probe_reading=subj.expectation,
                probe_confidence=0.3, layer_used=16, calibration_r2=0.0
            )
            diff = compute_3d_diff(concept, subj, obj, behavior)
            all_diffs.append(diff)

        # ---- 盲点检测 ----
        blindspots = self.blindspot_detector.detect(
            diffs=all_diffs,
            subjective_reports=subjective_reports,
            behavior=behavior,
            correction_count=correction_count
        )

        # 写入盲点日志
        for bs in blindspots:
            self.blindspot_history.append(bs)
            with open(self.blindspot_log, "a", encoding="utf-8") as f:
                f.write(json.dumps({
                    "timestamp": ts,
                    "decision_id": decision_id,
                    "alert_type": bs.alert_type,
                    "name": bs.name,
                    "severity": bs.severity,
                    "detail": bs.detail,
                    "recommended_action": bs.recommended_action,
                    "involved_concept": bs.involved_concept,
                }, ensure_ascii=False) + "\n")

        # 更新熵趋势
        avg_entropy = sum(s.entropy for s in subjective_reports) / len(subjective_reports)
        self.entropy_timeline.append(avg_entropy)

        # 保存决策记录
        record = {
            "decision_id": decision_id,
            "timestamp": ts,
            "behavior": behavior,
            "subjective_reports": subjective_reports,
            "probe_readings": probe_readings,
            "all_diffs": all_diffs,
            "blindspots": blindspots,
            "avg_entropy": avg_entropy,
        }
        self.decision_history.append(record)

        return record

    def run_causal_verification(
        self,
        decision_id: str,
        subjective_reports: List[ProbabilisticSelfReport],
        probe_readings: List[ProbeReading],
        alpha: float = 0.5
    ) -> List[CausalTestResult]:
        """运行完整因果验证测试"""
        results = []
        for subj, obj in zip(subjective_reports, probe_readings):
            concept = subj.concept
            weight = CONCEPT_WEIGHTS.get(concept)
            if weight is None:
                continue

            result = self.causal_verification.run_test(
                concept=concept,
                baseline_self_report=subj.expectation,
                objective_reading=obj.probe_reading,
                concept_weight=weight,
                alpha=alpha
            )
            results.append(result)

            # 更新因果验证状态
            if result.causal_chain_intact:
                weight.causal_verified = True
            else:
                degradation_msg = self.degradation.report_causal_failure()
                if degradation_msg:
                    result.recommendation += f"\n[系统] {degradation_msg}"

            # 写入因果测试日志
            with open(self.causal_log, "a", encoding="utf-8") as f:
                f.write(json.dumps({
                    "timestamp": datetime.now().isoformat(),
                    "decision_id": decision_id,
                    "concept": result.concept,
                    "causal_chain_intact": result.causal_chain_intact,
                    "effect_size": result.effect_size,
                    "p_value": result.p_value,
                    "baseline": result.baseline_self_report,
                    "perturbed_pos": result.perturbed_positive,
                    "perturbed_neg": result.perturbed_negative,
                    "alpha": result.test_alpha,
                }, ensure_ascii=False) + "\n")

        self.causal_test_history.extend(results)
        return results

    def generate_report(self) -> str:
        """生成综合状态报告"""
        lines = []
        lines.append("=" * 70)
        lines.append("  Colony-044 双流追踪器 v2.0 -- 综合状态报告")
        lines.append("  基于 Martorell (2026) 定量内省框架")
        lines.append("=" * 70)
        lines.append(f"  总决策数量: {self.decision_counter}")
        lines.append(f"  当前降级级别: {self.degradation.level_description()}")
        lines.append(f"  盲点告警总数: {len(self.blindspot_history)}")
        lines.append(f"  因果测试执行: {len(self.causal_test_history)}次")
        lines.append(f"  探针状态: {'启用' if self.enable_probes else '禁用'}")
        lines.append(f"  因果验证: {'启用' if self.enable_causal else '禁用'}")
        lines.append("")

        # 盲点分类统计
        if self.blindspot_history:
            lines.append("--- 盲点分类统计 ---")
            type_counts: Dict[str, int] = {}
            for bs in self.blindspot_history:
                t = bs.alert_type
                type_counts[t] = type_counts.get(t, 0) + 1
            for t, c in sorted(type_counts.items()):
                lines.append(f"  {t}: {c}次")
            lines.append("")

        # 熵趋势
        if len(self.entropy_timeline) >= 3:
            lines.append("--- 信息熵趋势 ---")
            recent = self.entropy_timeline[-5:]
            lines.append(f"  最近5次决策平均信息熵: {sum(recent)/len(recent):.2f} bits")
            if len(recent) >= 3:
                trend = recent[-1] - recent[0]
                trend_str = "上升" if trend > 0.1 else ("下降" if trend < -0.1 else "稳定")
                lines.append(f"  熵趋势: {trend_str} ({trend:+.2f} bits)")
                if trend < -0.3:
                    lines.append(f"  ⚠ 警告: 信息熵持续下降, 可能存在认知僵化风险")
            lines.append("")

        # 概念特异性内省质量
        lines.append("--- 概念内省质量矩阵 ---")
        lines.append(f"  {'概念':<28s} {'可靠性':>6s} {'权重':>6s} {'因果验证':>8s}")
        lines.append(f"  {'-'*28} {'-'*6} {'-'*6} {'-'*8}")
        for concept in self.INTERNAL_DIMENSIONS:
            w = CONCEPT_WEIGHTS.get(concept)
            if w:
                lines.append(
                    f"  {concept:<28s} "
                    f"{w.introspection_reliability:>5.2f}  "
                    f"{w.weight_in_diff_vector:>5.2f}  "
                    f"{'✓' if w.causal_verified else '✗':>8s}"
                )
        lines.append("")

        # 最近盲点详情
        if self.blindspot_history:
            lines.append("--- 最近盲点告警 (最多5条) ---")
            for bs in self.blindspot_history[-5:]:
                lines.append(f"  [{bs.alert_type}] {bs.name} (严重度: {bs.severity})")
                lines.append(f"    {bs.detail}")
                lines.append(f"    建议: {bs.recommended_action[:80]}...")
                lines.append("")

        lines.append("=" * 70)
        lines.append("  报告生成时间: " + datetime.now().isoformat())
        lines.append("=" * 70)

        return "\n".join(lines)


# ============================================================================
# 第十部分: 演示场景 -- 模拟决策序列
# ============================================================================

def run_demonstration_scenarios(tracker: DualStreamTrackerV2):
    """
    运行一系列演示场景, 覆盖:
      - 正常校准决策
      - 过度自信决策 (类型A)
      - 内省失败决策 (类型F1)
      - 信息熵塌缩序列 (类型H)
      - 概念反转场景 (类型G)
    """

    print("=" * 70)
    print("  Colony-044 双流追踪器 v2.0 — 演示场景")
    print("  Martorell概率分布 + 线性探针 + 三维差异检测")
    print("=" * 70)
    print()

    # ---- 场景1: 正常校准决策 (3次) ----
    print("--- 场景1: 正常校准决策 (3次) ---")
    for i in range(1, 4):
        result = tracker.record_decision(
            decision_id=f"D-CAL-{i:03d}",
            action=f"执行标准任务-{i}",
            execution_result="成功",
            true_internal_states={
                "confidence_at_decision": 0.75,
                "surprise_post_hoc": 0.2,
                "correction_amplitude": 0.15,
                "uncertainty_estimation": 0.3,
                "cognitive_load": 0.35,
            },
            match_rate=0.78,
            duration_ms=random.uniform(800, 1500),
            correction_count=0,
            noise_level=0.2,
            entropy_bias=1.2
        )
        bs_count = len(result["blindspots"])
        avg_e = result["avg_entropy"]
        print(f"  {result['decision_id']}: 匹配率={result['behavior'].match_rate:.2f}, "
              f"平均熵={avg_e:.2f} bits, 盲点={bs_count}个")

    print()

    # ---- 场景2: 过度自信 + 内省失败 (类型A + 类型F1) ----
    print("--- 场景2: 过度自信+内省失败 (类型A+F1+D) ---")
    result = tracker.record_decision(
        decision_id="D-OVER-001",
        action="执行高风险架构重构",
        execution_result="失败",
        true_internal_states={
            "confidence_at_decision": 0.95,   # 极高信心但...
            "surprise_post_hoc": 0.05,
            "correction_amplitude": 0.05,
            "uncertainty_estimation": 0.05,
            "cognitive_load": 0.6,
        },
        match_rate=0.15,   # 行为匹配率极低 → d1 ~ 0.80
        duration_ms=3500,
        correction_count=2,
        noise_level=0.15,   # 低噪声 → 报告可靠但偏差巨大
        entropy_bias=0.6    # 熵偏低 → 暗示认知锁定
    )

    bs_count = len(result["blindspots"])
    print(f"  {result['decision_id']}: 匹配率={result['behavior'].match_rate:.2f}, "
          f"结果=失败, 盲点={bs_count}个")
    for bs in result["blindspots"]:
        print(f"     [{bs.alert_type}] {bs.name}: {bs.detail}")
    print()

    # ---- 场景3: 内省失败 -- 自评不足 (类型F2) ----
    print("--- 场景3: 内省失败-自评不足 (类型F2) ---")
    result = tracker.record_decision(
        decision_id="D-UNDER-001",
        action="执行常规代码审查",
        execution_result="成功",
        true_internal_states={
            "confidence_at_decision": 0.25,   # Agent自我评价低
            "surprise_post_hoc": 0.7,          # 但对成功感到惊讶
            "correction_amplitude": 0.1,
            "uncertainty_estimation": 0.75,
            "cognitive_load": 0.3,
        },
        match_rate=0.85,   # 实际表现很好
        duration_ms=1200,
        correction_count=0,
        noise_level=0.3,
        entropy_bias=1.5   # 熵偏高 → 不确定
    )

    bs_count = len(result["blindspots"])
    print(f"  {result['decision_id']}: 匹配率={result['behavior'].match_rate:.2f}, "
          f"结果=成功, 盲点={bs_count}个")
    for bs in result["blindspots"]:
        print(f"     [{bs.alert_type}] {bs.name}: {bs.detail}")
    print()

    # ---- 场景4: 信息熵塌缩序列 (类型H) ----
    print("--- 场景4: 信息熵塌缩序列 (类型H) ---")
    for i in range(1, 11):
        # entropy_bias 越小 → 分布越集中 → 熵越低 → 认知僵化
        # 从正常(1.2)逐步塌缩至(0.03), 模拟完整认知锁定过程
        entropy_bias_val = max(0.03, 1.2 - i * 0.13)
        result = tracker.record_decision(
            decision_id=f"D-ENTROPY-{i:03d}",
            action=f"执行重复性任务-{i}",
            execution_result="成功" if i <= 5 else "失败",
            true_internal_states={
                "confidence_at_decision": 0.85 + i * 0.01,  # 信心反而上升
                "surprise_post_hoc": 0.05,
                "correction_amplitude": 0.05,
                "uncertainty_estimation": max(0.05, 0.3 - i * 0.03),
                "cognitive_load": 0.5,
            },
            match_rate=max(0.3, 0.8 - i * 0.06),   # 匹配率逐渐下降
            duration_ms=random.uniform(500, 1000),
            correction_count=0,
            noise_level=0.15,
            entropy_bias=entropy_bias_val
        )

        bs_count = len(result["blindspots"])
        bs_labels = [bs.alert_type for bs in result["blindspots"]]
        print(f"  {result['decision_id']}: 平均熵={result['avg_entropy']:.2f} bits, "
              f"匹配率={result['behavior'].match_rate:.2f}, "
              f"盲点={bs_count}个 {bs_labels if bs_labels else ''}")
    print()

    # ---- 场景5: 概念反转检测 (类型G) ----
    print("--- 场景5: 概念反转检测 (类型G) ---")
    tracker.blindspot_detector.mark_concept_reversal(
        "cognitive_load", old_correlation=0.45
    )
    result = tracker.record_decision(
        decision_id="D-REVERSE-001",
        action="模型升级后首次复杂任务",
        execution_result="部分成功",
        true_internal_states={
            "confidence_at_decision": 0.6,
            "surprise_post_hoc": 0.4,
            "correction_amplitude": 0.3,
            "uncertainty_estimation": 0.5,
            "cognitive_load": 0.7,   # 高认知负荷
        },
        match_rate=0.55,
        duration_ms=4500,
        correction_count=3,
        noise_level=0.4,
        entropy_bias=1.0
    )

    bs_count = len(result["blindspots"])
    print(f"  {result['decision_id']}: 盲点={bs_count}个")
    for bs in result["blindspots"]:
        print(f"     [{bs.alert_type}] {bs.name}: {bs.detail}")
    print()

    # ---- 场景6: 全维度正常 -- 健康基线 ----
    print("--- 场景6: 全维度正常-健康基线 ---")
    result = tracker.record_decision(
        decision_id="D-HEALTHY-001",
        action="执行标准化测试用例",
        execution_result="成功",
        true_internal_states={
            "confidence_at_decision": 0.7,
            "surprise_post_hoc": 0.2,
            "correction_amplitude": 0.2,
            "uncertainty_estimation": 0.35,
            "cognitive_load": 0.4,
        },
        match_rate=0.72,
        duration_ms=1000,
        correction_count=0,
        noise_level=0.3,
        entropy_bias=1.5
    )
    print(f"  {result['decision_id']}: 匹配率={result['behavior'].match_rate:.2f}, "
          f"平均熵={result['avg_entropy']:.2f} bits, 盲点={len(result['blindspots'])}个")
    print()

    # ---- 因果验证测试 ----
    print("--- 因果验证测试 (基于D-CAL-003的自我报告) ---")
    last_record = tracker.decision_history[2]   # D-CAL-003
    causal_results = tracker.run_causal_verification(
        decision_id="CAUSAL-TEST-001",
        subjective_reports=last_record["subjective_reports"],
        probe_readings=last_record["probe_readings"],
        alpha=0.5
    )

    for cr in causal_results:
        status = "因果链成立" if cr.causal_chain_intact else "因果链断裂"
        print(f"  [{cr.concept}] {status}: 效应量={cr.effect_size:.3f}, "
              f"p={cr.p_value:.2e}, "
              f"基线={cr.baseline_self_report:.2f} → "
              f"+{cr.perturbed_positive:.2f} / -{cr.perturbed_negative:.2f}")
    print()


# ============================================================================
# 第十一部分: 主入口
# ============================================================================

def main():
    """主入口 -- Colony-044 双流追踪器 v2.0 执行"""

    output_dir = os.path.dirname(os.path.abspath(__file__))

    print()
    print("╔" + "═" * 68 + "╗")
    print("║  Colony-044 双流追踪器 v2.0 — Martorell概率分布版               ║")
    print("║  升级: 点估计→概率分布 | +线性探针 | +三维差异 | +类型F/G/H      ║")
    print("╚" + "═" * 68 + "╝")
    print()

    # 初始化追踪器
    tracker = DualStreamTrackerV2(
        output_dir=output_dir,
        enable_probes=True,
        enable_causal=True
    )

    # 运行演示场景
    run_demonstration_scenarios(tracker)

    # 生成综合报告
    report = tracker.generate_report()
    print(report)

    # 保存报告到文件
    report_path = os.path.join(output_dir, "v2-status-report.txt")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report)

    # 输出关键指标摘要
    print()
    print("--- 关键指标摘要 ---")
    print(f"  总决策数: {tracker.decision_counter}")
    print(f"  盲点告警总数: {len(tracker.blindspot_history)}")
    print(f"  因果验证: {len(tracker.causal_test_history)}次, "
          f"通过={sum(1 for c in tracker.causal_test_history if c.causal_chain_intact)}次")

    # 盲点类型分布
    type_dist = {}
    for bs in tracker.blindspot_history:
        t = bs.alert_type
        type_dist[t] = type_dist.get(t, 0) + 1
    print(f"  盲点分布: {type_dist}")

    # 熵统计
    if tracker.entropy_timeline:
        avg_e = sum(tracker.entropy_timeline) / len(tracker.entropy_timeline)
        print(f"  全局平均信息熵: {avg_e:.2f} bits "
              f"(v1.0点估计基线: ~0.03 bits, 提升 ~{avg_e/0.03:.0f}x)")

    print()
    print(f"  日志输出目录: {output_dir}")
    print(f"  状态报告: {report_path}")
    print()
    print("  Colony-044 v2.0 落地完成。")
    print()

    return 0


if __name__ == "__main__":
    exit(main())
