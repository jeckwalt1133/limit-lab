#!/usr/bin/env python3
"""
Colony-026 哥德尔跳质量量化指标计算器
==============================================
将 GODEL_LEAP 从二值计数 (0/1) 升级为四项连续量化指标:
  1. 跳跃幅度 M_G   (Leap Magnitude)
  2. 盲点发现率 BDR  (Blindspot Discovery Rate)
  3. 公理存活率 ASR  (Axiom Survival Rate)
  4. 维度扩展效率 DEE (Dimension Expansion Efficiency)

综合输出: GLQ (Godel Leap Quality Index)

用法:
  python godel-leap-metrics.py --input <leap-data.json>
  python godel-leap-metrics.py --demo          # 用 Colony-021 基线数据演示
  python godel-leap-metrics.py --input <json> --output <result.json>
"""

import argparse
import json
import math
import os
import sys
from datetime import datetime
from typing import Dict, List, Optional, Tuple

# ── 常量: 权重 ─────────────────────────────────────────────────────
# 均在 colony-026/godel-leap-metrics.md 中定义并校准

# M_G 子指标权重
W_GS = 0.25       # GS 症候严重度
W_BLIND = 0.20    # 盲点深度
W_AXIOM_Q = 0.30  # 公理生成质量
W_DIM = 0.25      # 维度扩展比

# GS 症候权重
GS_WEIGHTS = {
    "GS-001": 1.0,   # 评估坍塌 (轻度)
    "GS-002": 2.0,   # 收敛停滞 (重度，主触发)
    "GS-003": 1.5,   # 外部不可吸收 (中度)
    "GS-004": 1.5,   # 循环重复 (中度)
    "GS-005": 1.5,   # 签名过稳定 (中重度)
}
GS_MAX_RAW = 4.5  # 归一化分母: Σ(w_i)·3 / 5 = 7.5·3/5 = 4.5

# ASR 权重
BETA_SUSTAIN = 0.5   # 存活权重折扣
GAMMA_THRIVE = 0.3   # 繁荣权重折扣

# GLQ 综合权重
W_MG = 0.30     # 跳跃幅度
W_BDR = 0.20    # 盲点发现率
W_ASR = 0.25    # 公理存活率
W_DEE = 0.25    # 维度扩展效率

# 盲点深度评分 (按发现方法)
DEPTH_BY_METHOD = {
    "external_catalyst": 0.6,   # 外部触媒法 — 需要外部理论映射
    "diagonalization": 0.8,     # 对角线法 — 需要构造反例
    "fixed_point": 1.0,         # 不动点检测 — 需要元层次分析
}

# 公理类型评分
TYPE_SCORE = {
    "D": 1.00,  # 观察者重构 — 最高价值
    "A": 0.85,  # 维度扩展
    "C": 0.70,  # 系统边界扩展
}

# IBE_proxy 权重
W_THEORY = 0.4
W_TYPE = 0.35
W_COMPAT = 0.25

# 参考点 (用于 tanh 归一化)
BDR_REF = 0.3     # BDR 参考点
ASR_REF = 2.0     # ASR 参考点
DIM_PER_AX_REF = 3.0  # 每条公理期望维度数
CANDIDATE_PER_METHOD_REF = 3.0  # 每种方法期望候选数


# ── 辅助函数 ─────────────────────────────────────────────────────

def safe_div(a: float, b: float, default: float = 0.0) -> float:
    """安全除法，b=0 时返回默认值。"""
    return a / b if b != 0 else default


def grade(value: float, thresholds: List[Tuple[float, float, str]]) -> str:
    """根据阈值区间返回等级标签。"""
    for lo, hi, label in thresholds:
        if lo <= value < hi or (hi == float("inf") and value >= lo):
            return label
    return "UNKNOWN"


# ── 1. 跳跃幅度 M_G ──────────────────────────────────────────────

def compute_gs_severity(gs_scores: Dict[str, float]) -> float:
    """
    计算 GS 症候严重度 S_GS ∈ [0, 1]。

    S_GS = min(1.0, raw / GS_MAX_RAW)
    raw = (1/5) · Σ w_i · score_i
    """
    raw = sum(GS_WEIGHTS.get(k, 1.0) * v for k, v in gs_scores.items()) / 5.0
    return min(1.0, raw / GS_MAX_RAW)


def compute_blindspot_depth(blindspots: List[Dict]) -> float:
    """
    计算盲点深度 D_blind ∈ [0, 1]。

    每个盲点的深度由其发现方法决定。
    若同一盲点被多种方法发现，取最大 depth。
    """
    if not blindspots:
        return 0.0
    depths = []
    for bs in blindspots:
        method = bs.get("method", "external_catalyst")
        depth = DEPTH_BY_METHOD.get(method, 0.6)
        depths.append(depth)
    return sum(depths) / len(depths)


def compute_axiom_quality(axioms: List[Dict]) -> float:
    """
    计算公理生成质量 Q_axiom ∈ [0, 1]。

    优先使用实际 IBE 值；若无，使用 IBE_proxy 估算。
    """
    if not axioms:
        return 0.0
    q_values = []
    for ax in axioms:
        ibe = ax.get("ibe")
        if ibe is not None and ibe > 0:
            q_values.append(ibe)
        else:
            # IBE_proxy 估算
            theory_refs = ax.get("theory_refs", 0)
            ax_type = ax.get("type", "C")
            ics = ax.get("ics", 0.95)

            c_theory = min(1.0, theory_refs / 3.0)
            s_type = TYPE_SCORE.get(ax_type, 0.70)
            ibe_proxy = W_THEORY * c_theory + W_TYPE * s_type + W_COMPAT * ics
            q_values.append(ibe_proxy)
    return sum(q_values) / len(q_values)


def compute_dim_expansion_ratio(dim_before: int, dim_after: float) -> float:
    """
    计算维度扩展比 E_dim。
    E_dim = (|DS_new| - |DS_old|) / |DS_old|
    """
    if dim_before <= 0:
        return 0.0
    return (dim_after - dim_before) / dim_before


def compute_leap_magnitude(
    gs_scores: Dict[str, float],
    blindspots: List[Dict],
    axioms: List[Dict],
    dim_before: int,
    dim_after: float,
) -> Dict:
    """
    计算跳跃幅度 M_G ∈ [0, 1] (实际可超过 1.0 对于极端跳跃)。

    返回详细分解。
    """
    s_gs = compute_gs_severity(gs_scores)
    d_blind = compute_blindspot_depth(blindspots)
    q_axiom = compute_axiom_quality(axioms)
    e_dim = compute_dim_expansion_ratio(dim_before, dim_after)
    e_dim_norm = math.tanh(e_dim)

    m_g = W_GS * s_gs + W_BLIND * d_blind + W_AXIOM_Q * q_axiom + W_DIM * e_dim_norm

    grade_thresholds = [
        (0.0, 0.15, "微跳"),
        (0.15, 0.35, "小跳"),
        (0.35, 0.60, "中跳"),
        (0.60, 0.85, "大跳"),
        (0.85, float("inf"), "巨跳"),
    ]

    return {
        "M_G": round(m_g, 4),
        "grade": grade(m_g, grade_thresholds),
        "components": {
            "S_GS": round(s_gs, 4),
            "D_blind": round(d_blind, 4),
            "Q_axiom": round(q_axiom, 4),
            "E_dim": round(e_dim, 4),
            "E_dim_norm": round(e_dim_norm, 4),
        },
        "weights": {"alpha1": W_GS, "alpha2": W_BLIND, "alpha3": W_AXIOM_Q, "alpha4": W_DIM},
    }


# ── 2. 盲点发现率 BDR ─────────────────────────────────────────────

def compute_bdr(
    blindspots: List[Dict],
    methods_used: List[str],
    axioms: List[Dict],
    theories_scanned: int,
    theories_available: int,
) -> Dict:
    """
    计算盲点发现率 BDR。

    BDR = C_method · D_candidate_norm · R_convert · C_theory
    """
    n_methods = len(methods_used)
    n_blindspots = len(blindspots)
    n_axioms = len(axioms)

    c_method = n_methods / 3.0 if n_methods > 0 else 0.0
    d_candidate = safe_div(n_blindspots, n_methods)
    d_candidate_norm = math.tanh(d_candidate / CANDIDATE_PER_METHOD_REF)
    r_convert = safe_div(n_axioms, n_blindspots) if n_blindspots > 0 else 0.0
    c_theory = safe_div(theories_scanned, theories_available) if theories_available > 0 else 0.0

    bdr = c_method * d_candidate_norm * r_convert * c_theory

    grade_thresholds = [
        (0.0, 0.10, "低效"),
        (0.10, 0.30, "正常"),
        (0.30, 0.50, "高效"),
        (0.50, float("inf"), "超高"),
    ]

    return {
        "BDR": round(bdr, 4),
        "grade": grade(bdr, grade_thresholds),
        "components": {
            "C_method": round(c_method, 4),
            "D_candidate": round(d_candidate, 2),
            "D_candidate_norm": round(d_candidate_norm, 4),
            "R_convert": round(r_convert, 4),
            "C_theory": round(c_theory, 4),
        },
    }


# ── 3. 公理存活率 ASR ─────────────────────────────────────────────

def compute_asr(axioms: List[Dict]) -> Dict:
    """
    计算公理存活率 ASR。

    ASR = R_adopt · (1 + β · R_sustain) · (1 + γ · R_thrive)

    根据 axioms 中每条公理的 status 字段判断所处阶段。
    """
    if not axioms:
        return {"ASR": 0.0, "grade": "N/A", "components": {}, "note": "无公理数据"}

    n_generated = len(axioms)
    n_adopted = sum(1 for ax in axioms if ax.get("adopted_as"))
    n_survived = sum(1 for ax in axioms if ax.get("status") in ("active", "thriving"))
    n_thriving = sum(1 for ax in axioms if ax.get("status") == "thriving")

    r_adopt = safe_div(n_adopted, n_generated)
    r_sustain = safe_div(n_survived, n_adopted) if n_adopted > 0 else 0.0
    r_thrive = safe_div(n_thriving, n_survived) if n_survived > 0 else 0.0

    asr = r_adopt * (1.0 + BETA_SUSTAIN * r_sustain) * (1.0 + GAMMA_THRIVE * r_thrive)

    # 估算衰减常数 λ (如果提供了 gen 信息)
    lambda_est = None
    survival_halflife = None
    if n_adopted > 0 and n_survived < n_adopted:
        # 假设 N_stable = 30
        if r_sustain > 0:
            lambda_est = -math.log(max(r_sustain, 0.01)) / 30.0
            survival_halflife = math.log(2) / lambda_est if lambda_est > 0 else float("inf")

    grade_thresholds = [
        (0.0, 0.5, "低存活"),
        (0.5, 1.0, "正常"),
        (1.0, 1.5, "高存活"),
        (1.5, float("inf"), "超高"),
    ]

    result = {
        "ASR": round(asr, 4),
        "grade": grade(asr, grade_thresholds),
        "components": {
            "N_generated": n_generated,
            "N_adopted": n_adopted,
            "N_survived": n_survived,
            "N_thriving": n_thriving,
            "R_adopt": round(r_adopt, 4),
            "R_sustain": round(r_sustain, 4),
            "R_thrive": round(r_thrive, 4),
        },
    }

    if lambda_est is not None:
        result["decay"] = {
            "lambda": round(lambda_est, 6),
            "halflife_generations": round(survival_halflife, 1) if survival_halflife else None,
        }

    # 逐公理详情
    result["axiom_details"] = []
    for ax in axioms:
        detail = {
            "id": ax.get("id", "?"),
            "adopted_as": ax.get("adopted_as"),
            "status": ax.get("status", "unknown"),
            "type": ax.get("type", "?"),
        }
        result["axiom_details"].append(detail)

    return result


# ── 4. 维度扩展效率 DEE ───────────────────────────────────────────

def compute_dee(
    axioms: List[Dict],
    dim_before: int,
    dim_after: float,
    saturated_dims: List[str],
) -> Dict:
    """
    计算维度扩展效率 DEE。

    DEE = R_exp_norm · Q_dim · (1 + P_sat) · E_per_ax_norm
    """
    # R_exp
    r_exp = safe_div(dim_after - dim_before, dim_before) if dim_before > 0 else 0.0

    # 实际有效维度增量 (排除二阶衍生维度的折扣)
    total_dim_impact = dim_after - dim_before

    # P_sat
    n_saturated = len(saturated_dims)
    p_sat = safe_div(n_saturated, dim_before) if dim_before > 0 else 0.0

    # Q_dim: 导致维度扩展的公理 IBE 均值
    expansion_axioms = [ax for ax in axioms if ax.get("dimension_impact", 0) > 0]
    if expansion_axioms:
        q_dim = sum(ax.get("ibe", compute_axiom_quality([ax])) for ax in expansion_axioms) / len(expansion_axioms)
    else:
        q_dim = 0.0

    # E_per_ax
    e_per_ax = safe_div(total_dim_impact, len(axioms)) if axioms else 0.0
    e_per_ax_norm = math.tanh(e_per_ax / DIM_PER_AX_REF)

    r_exp_norm = math.tanh(r_exp)

    dee = r_exp_norm * q_dim * (1.0 + p_sat) * e_per_ax_norm

    grade_thresholds = [
        (0.0, 0.10, "低效"),
        (0.10, 0.25, "正常"),
        (0.25, 0.50, "高效"),
        (0.50, float("inf"), "超高"),
    ]

    return {
        "DEE": round(dee, 4),
        "grade": grade(dee, grade_thresholds),
        "components": {
            "R_exp": round(r_exp, 4),
            "R_exp_norm": round(r_exp_norm, 4),
            "P_sat": round(p_sat, 4),
            "Saturated_count": n_saturated,
            "Q_dim": round(q_dim, 4),
            "E_per_ax": round(e_per_ax, 4),
            "E_per_ax_norm": round(e_per_ax_norm, 4),
            "Total_dim_impact": round(total_dim_impact, 2),
            "Expansion_axioms": [ax.get("id") for ax in expansion_axioms],
        },
    }


# ── 5. 综合 GLQ ───────────────────────────────────────────────────

def compute_glq(m_g_result: Dict, bdr_result: Dict, asr_result: Dict, dee_result: Dict) -> Dict:
    """
    计算哥德尔跳质量指数 GLQ。

    GLQ = w1·M_G + w2·BDR_norm + w3·ASR_norm + w4·DEE
    """
    m_g = m_g_result["M_G"]
    bdr = bdr_result["BDR"]
    asr = asr_result["ASR"]
    dee = dee_result["DEE"]

    bdr_norm = math.tanh(bdr / BDR_REF)
    asr_norm = math.tanh(asr / ASR_REF)

    glq = W_MG * m_g + W_BDR * bdr_norm + W_ASR * asr_norm + W_DEE * dee

    grade_thresholds = [
        (0.0, 0.20, "微跳"),
        (0.20, 0.40, "小跳"),
        (0.40, 0.60, "中跳"),
        (0.60, 0.80, "大跳"),
        (0.80, float("inf"), "巨跳"),
    ]

    return {
        "GLQ": round(glq, 4),
        "grade": grade(glq, grade_thresholds),
        "components": {
            "M_G": round(m_g, 4),
            "BDR": round(bdr, 4),
            "BDR_norm": round(bdr_norm, 4),
            "ASR": round(asr, 4),
            "ASR_norm": round(asr_norm, 4),
            "DEE": round(dee, 4),
        },
        "weights": {"w1_M_G": W_MG, "w2_BDR": W_BDR, "w3_ASR": W_ASR, "w4_DEE": W_DEE},
    }


# ── 主计算入口 ─────────────────────────────────────────────────────

def compute_all_metrics(data: Dict) -> Dict:
    """
    从结构化数据计算全部四项指标 + 综合 GLQ。

    输入格式参见 godel-leap-metrics.md 第 6 节。
    """
    leap_id = data.get("leap_id", "GL-???")
    gen = data.get("gen", 0)
    colony = data.get("trigger_colony", "?")
    timestamp = data.get("timestamp", datetime.now().isoformat())

    gs_scores = data.get("gs_scores", {})
    blindspots_data = data.get("blindspots", {})
    axioms = data.get("axioms", [])
    dim_info = data.get("dimensions", {})

    methods_used = blindspots_data.get("methods_used", [])
    candidates = blindspots_data.get("candidates", [])
    theories_scanned = blindspots_data.get("theories_scanned", 0)
    theories_available = blindspots_data.get("theories_available", 0)

    dim_before = dim_info.get("before", 0)
    dim_after = dim_info.get("after", 0)
    saturated_before = dim_info.get("saturated_before", [])

    # 计算四项指标
    m_g = compute_leap_magnitude(gs_scores, candidates, axioms, dim_before, dim_after)
    bdr = compute_bdr(candidates, methods_used, axioms, theories_scanned, theories_available)
    asr = compute_asr(axioms)
    dee = compute_dee(axioms, dim_before, dim_after, saturated_before)

    # 综合
    glq = compute_glq(m_g, bdr, asr, dee)

    return {
        "meta": {
            "leap_id": leap_id,
            "gen": gen,
            "trigger_colony": colony,
            "timestamp": timestamp,
            "calculator_version": "1.0.0",
            "colony": "Colony-026",
        },
        "metrics": {
            "leap_magnitude": m_g,
            "blindspot_discovery_rate": bdr,
            "axiom_survival_rate": asr,
            "dimension_expansion_efficiency": dee,
        },
        "composite": glq,
    }


# ── 输出格式化 ─────────────────────────────────────────────────────

def format_report(result: Dict) -> str:
    """生成可读文本报告。"""
    meta = result["meta"]
    m = result["metrics"]
    c = result["composite"]

    lines = []
    lines.append("=" * 60)
    lines.append(f"  哥德尔跳质量报告: {meta['leap_id']}")
    lines.append(f"  Colony: {meta['trigger_colony']} | Gen: {meta['gen']}")
    lines.append(f"  时间: {meta['timestamp'][:19]}")
    lines.append("=" * 60)
    lines.append("")

    # M_G
    mg = m["leap_magnitude"]
    lines.append(f"  1. 跳跃幅度 M_G:     {mg['M_G']:.4f}  [{mg['grade']}]")
    lines.append(f"     ├ S_GS (GS严重度):    {mg['components']['S_GS']:.4f}")
    lines.append(f"     ├ D_blind (盲点深度):  {mg['components']['D_blind']:.4f}")
    lines.append(f"     ├ Q_axiom (公理质量):  {mg['components']['Q_axiom']:.4f}")
    lines.append(f"     └ E_dim (维度扩展比):  {mg['components']['E_dim']:.4f}")
    lines.append("")

    # BDR
    bdr = m["blindspot_discovery_rate"]
    lines.append(f"  2. 盲点发现率 BDR:   {bdr['BDR']:.4f}  [{bdr['grade']}]")
    lines.append(f"     ├ C_method (方法覆盖): {bdr['components']['C_method']:.4f}")
    lines.append(f"     ├ D_candidate (候选密度): {bdr['components']['D_candidate']:.2f}")
    lines.append(f"     ├ R_convert (转化率):  {bdr['components']['R_convert']:.4f}")
    lines.append(f"     └ C_theory (理论覆盖): {bdr['components']['C_theory']:.4f}")
    lines.append("")

    # ASR
    asr = m["axiom_survival_rate"]
    lines.append(f"  3. 公理存活率 ASR:   {asr['ASR']:.4f}  [{asr['grade']}]")
    comp = asr["components"]
    lines.append(f"     ├ 生成: {comp['N_generated']} → 采纳: {comp['N_adopted']} → 存活: {comp['N_survived']} → 繁荣: {comp['N_thriving']}")
    lines.append(f"     ├ R_adopt (采纳率):   {comp['R_adopt']:.4f}")
    lines.append(f"     ├ R_sustain (存活率):  {comp['R_sustain']:.4f}")
    lines.append(f"     └ R_thrive (繁荣率):   {comp['R_thrive']:.4f}")
    if "decay" in asr:
        d = asr["decay"]
        lines.append(f"     └ 衰减 λ={d['lambda']:.6f}, 半衰期={d.get('halflife_generations', '?')} 代")
    lines.append("")

    # DEE
    dee = m["dimension_expansion_efficiency"]
    lines.append(f"  4. 维度扩展效率 DEE: {dee['DEE']:.4f}  [{dee['grade']}]")
    dc = dee["components"]
    lines.append(f"     ├ R_exp (扩展比):      {dc['R_exp']:.4f}")
    lines.append(f"     ├ P_sat (饱和压力):    {dc['P_sat']:.4f} ({dc['Saturated_count']}/{dim_before_or_0(dc)} 维触及天花板)")
    lines.append(f"     ├ Q_dim (新维信息密度): {dc['Q_dim']:.4f}")
    lines.append(f"     └ E_per_ax (单位效率): {dc['E_per_ax']:.4f}")
    lines.append("")

    # GLQ
    lines.append("  " + "-" * 56)
    lines.append(f"  综合 GLQ:           {c['GLQ']:.4f}  [{c['grade']}]")
    lines.append(f"     M_G={c['components']['M_G']:.4f}  BDR_n={c['components']['BDR_norm']:.4f}  ASR_n={c['components']['ASR_norm']:.4f}  DEE={c['components']['DEE']:.4f}")
    lines.append("  " + "-" * 56)

    return "\n".join(lines)


def dim_before_or_0(components: Dict) -> int:
    """从 DEE components 推算原始维度数 (辅助显示)。"""
    # 反推: n_sat = P_sat * dim_before
    p_sat = components.get("P_sat", 0)
    n_sat = components.get("Saturated_count", 0)
    if p_sat > 0:
        return int(n_sat / p_sat)
    return 0


# ── 基线数据 ───────────────────────────────────────────────────────

def get_colony021_baseline() -> Dict:
    """返回 Colony-021 首次自主哥德尔跳的完整结构化数据。"""
    return {
        "leap_id": "GL-001",
        "gen": 115,
        "trigger_colony": "Colony-021",
        "timestamp": "2026-05-19T00:00:00",
        "gs_scores": {
            "GS-001": 1.5,
            "GS-002": 3.0,
            "GS-003": 2.0,
            "GS-004": 3.0,
            "GS-005": 2.5,
        },
        "blindspots": {
            "methods_used": ["external_catalyst", "diagonalization", "fixed_point"],
            "candidates": [
                {"id": "B1", "method": "external_catalyst", "theory": "quantum_darwinism"},
                {"id": "B2", "method": "external_catalyst", "theory": "free_energy_principle"},
                {"id": "B3", "method": "external_catalyst", "theory": "von_neumann_constructor"},
                {"id": "B4", "method": "external_catalyst", "theory": "godel_machine"},
                {"id": "B5", "method": "external_catalyst", "theory": "chaitin_omega"},
            ],
            "theories_available": 5,
            "theories_scanned": 5,
        },
        "axioms": [
            {
                "id": "AX-021-001",
                "type": "D",
                "ibe": 0.87,
                "theory_refs": 3,
                "ics": 0.98,
                "adopted_as": "MR-023",
                "dimension_impact": 1.0,
                "status": "active",
            },
            {
                "id": "AX-021-002",
                "type": "A",
                "ibe": 0.72,
                "theory_refs": 3,
                "ics": 0.96,
                "adopted_as": "MR-024",
                "dimension_impact": 2.5,
                "status": "active",
            },
            {
                "id": "AX-021-003",
                "type": "C",
                "ibe": 0.65,
                "theory_refs": 3,
                "ics": 0.97,
                "adopted_as": "MR-025",
                "dimension_impact": 1.0,
                "status": "active",
            },
        ],
        "dimensions": {
            "before": 5,
            "after": 9.5,
            "saturated_before": ["L5_SHI", "MEM_COMP"],
        },
    }


# ── CLI ────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Colony-026 哥德尔跳质量量化指标计算器",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python godel-leap-metrics.py --demo
  python godel-leap-metrics.py --input leap-data.json
  python godel-leap-metrics.py --input leap-data.json --output result.json
        """,
    )
    parser.add_argument("--input", "-i", help="输入 JSON 数据文件路径")
    parser.add_argument("--output", "-o", help="输出 JSON 结果文件路径 (可选)")
    parser.add_argument("--demo", action="store_true", help="使用 Colony-021 基线数据演示计算")
    parser.add_argument("--quiet", "-q", action="store_true", help="仅输出 JSON，不打印报告")
    args = parser.parse_args()

    # 加载数据
    if args.demo:
        data = get_colony021_baseline()
    elif args.input:
        with open(args.input, "r", encoding="utf-8") as f:
            data = json.load(f)
    else:
        # 尝试从 stdin 读取
        if not sys.stdin.isatty():
            data = json.load(sys.stdin)
        else:
            parser.print_help()
            print("\n请指定 --input, --demo, 或通过管道传入 JSON。")
            return 1

    # 计算
    result = compute_all_metrics(data)

    # 输出
    if not args.quiet:
        print(format_report(result))

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        if not args.quiet:
            print(f"\n结果已写入: {args.output}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
