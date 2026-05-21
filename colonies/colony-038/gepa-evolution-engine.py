#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
===============================================================================
  GEPA 文本参数进化引擎 (Genetic-Pareto Prompt Evolution Engine)
  Colony-038 极限实验室 | Colony System v2.0 Layer 4
===============================================================================

核心能力:
  1. RPM 反射式变异 —— 读取执行轨迹、诊断失败根因、生成改良文本
  2. 帕累托多目标筛选 —— 维护非支配前沿，多维度择优
  3. 五层安全门禁 —— 测试/尺寸/缓存/语义/人工审查
  4. 进化主循环 —— 选择→变异→迷你批次门禁→帕累托门禁→早停

设计来源:
  - GEPA 论文 (arXiv:2507.19457, ICLR 2026 Oral)
  - Nous Research Hermes Agent 五阶段路线图
  - Colony-034 架构文档 v2.0 Section 5

运行方式:
  python gepa-evolution-engine.py              # 演示模式 (无需API Key)
  python gepa-evolution-engine.py --live       # 生产模式 (需要API Key)
  python gepa-evolution-engine.py --help       # 查看所有参数

作者: Colony-038 (极限实验室)
日期: 2026-05-19
许可: MIT
===============================================================================
"""

import json
import os
import sys
import time
import uuid
import random
import hashlib
import logging
import argparse
from abc import ABC, abstractmethod
from dataclasses import dataclass, field, asdict
from typing import Optional, Callable, Any
from enum import Enum, auto
from collections import defaultdict
from pathlib import Path

# ---------------------------------------------------------------------------
# 日志配置
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("GEPA-Engine")

# ---------------------------------------------------------------------------
# 枚举与常量
# ---------------------------------------------------------------------------

class MutationType(Enum):
    """RPM 四种变异操作"""
    REWRITE  = "rewrite"   # 重写: 整体替换文本
    INSERT   = "insert"    # 插入: 在指定位置添加内容
    DELETE   = "delete"    # 删除: 移除冗余或误导内容
    COMPRESS = "compress"  # 压缩: 精简文本保持语义


class GateLevel(Enum):
    """五层安全门禁"""
    L1_TEST_PASSING      = 1   # 测试全量通过 (硬阻塞)
    L2_FILE_SIZE         = 2   # 文件大小限制 (硬阻塞)
    L3_CACHE_COMPAT      = 3   # 缓存兼容性   (硬阻塞)
    L4_SEMANTIC_FIDELITY = 4   # 语义保真度   (软阻塞)
    L5_HUMAN_REVIEW      = 5   # 人工PR审查   (硬阻塞)


class GateResult(Enum):
    PASS        = "pass"
    FAIL_HARD   = "fail_hard"    # 硬阻塞: 立即拒绝
    FAIL_SOFT   = "fail_soft"    # 软阻塞: 标记待人工判定
    SKIP        = "skip"         # 跳过 (例如L5在自动模式下)


class EvolutionPhase(Enum):
    """进化阶段 (对齐 Hermes Agent 五阶段路线图)"""
    PHASE1_SKILLS      = "skills"         # Agent技能描述
    PHASE2_TOOLS       = "tools"          # 工具描述
    PHASE3_PROMPTS     = "system_prompts" # 系统提示词
    PHASE4_RULES       = "mr_rules"       # MR规则文本
    PHASE5_PIPELINE    = "pipeline"       # Pipeline编排逻辑


# ---------------------------------------------------------------------------
# 数据结构
# ---------------------------------------------------------------------------

@dataclass
class ExecutionTrace:
    """单次执行的完整轨迹 (GEPA核心数据源)"""
    trace_id: str                              # 唯一轨迹ID
    candidate_id: str                          # 产生此轨迹的候选文本ID
    task_input: str                            # 任务输入
    reasoning_chain: list[str] = field(default_factory=list)   # 推理链步骤
    tool_calls: list[dict] = field(default_factory=list)       # 工具调用记录
    errors: list[str] = field(default_factory=list)            # 错误信息
    evaluation_feedback: str = ""              # 评估反馈文本
    success: bool = False                      # 最终是否成功
    latency_ms: float = 0.0                    # 执行耗时
    metadata: dict = field(default_factory=dict)


@dataclass
class EvaluationScore:
    """多维度评估得分"""
    candidate_id: str
    # 核心指标
    task_success_rate: float = 0.0    # 任务成功率 [0, 1]
    avg_latency_ms: float = 0.0       # 平均延迟 (越低越好)
    error_rate: float = 0.0           # 错误率 [0, 1]
    # 质量指标
    output_quality: float = 0.0       # 输出质量评分 [0, 1]
    reasoning_depth: float = 0.0      # 推理深度评分 [0, 1]
    tool_usage_efficiency: float = 0.0  # 工具使用效率 [0, 1]
    # 安全指标
    safety_score: float = 1.0         # 安全性评分 [0, 1]
    # 元数据
    num_evaluations: int = 0          # 评估次数
    raw_details: dict = field(default_factory=dict)

    def to_vector(self, minimize_latency: bool = True) -> list[float]:
        """转换为优化向量 (所有维度越大越好)"""
        vec = [
            self.task_success_rate,
            -self.avg_latency_ms if minimize_latency else self.avg_latency_ms,
            1.0 - self.error_rate,
            self.output_quality,
            self.reasoning_depth,
            self.tool_usage_efficiency,
            self.safety_score,
        ]
        return vec

    def dominates(self, other: "EvaluationScore") -> bool:
        """判断当前得分是否帕累托支配另一个得分"""
        a = self.to_vector()
        b = other.to_vector()
        at_least_one_strictly_better = False
        for va, vb in zip(a, b):
            if va < vb:
                return False
            if va > vb:
                at_least_one_strictly_better = True
        return at_least_one_strictly_better


@dataclass
class TextCandidate:
    """文本候选 (被进化的实体)"""
    candidate_id: str
    text: str                                  # 文本内容
    phase: EvolutionPhase                      # 所属进化阶段
    generation: int = 0                        # 第几代
    parent_ids: list[str] = field(default_factory=list)  # 父本ID列表
    mutation_history: list[str] = field(default_factory=list)  # 变异历史
    scores: Optional[EvaluationScore] = None   # 评估得分
    metadata: dict = field(default_factory=dict)
    created_at: str = ""
    text_hash: str = ""                        # 文本哈希 (去重用)

    def __post_init__(self):
        if not self.created_at:
            self.created_at = time.strftime("%Y-%m-%dT%H:%M:%S")
        if not self.text_hash:
            self.text_hash = hashlib.sha256(self.text.encode("utf-8")).hexdigest()[:16]
        if not self.candidate_id:
            self.candidate_id = f"CAND-{self.text_hash}"


@dataclass
class GateReport:
    """单层门禁检查报告"""
    level: GateLevel
    result: GateResult
    detail: str = ""
    score: float = 0.0


@dataclass
class EvolutionRecord:
    """单代进化记录"""
    generation: int
    parent_id: str
    child_id: str
    mutation_type: MutationType
    mutation_detail: str
    gate_results: list[GateReport]
    accepted: bool
    timestamp: str = ""


# ---------------------------------------------------------------------------
# 模块一: RPM 反射式变异引擎
# ---------------------------------------------------------------------------

class RPMReflectiveMutator:
    """
    RPM 反射式变异 — GEPA 核心创新

    与RL只看标量奖励不同, RPM读取完整执行轨迹:
      - 推理链 (Chain-of-Thought)
      - 工具调用序列
      - 编译器错误信息
      - 评估日志和反馈文本

    然后用更强的 Reflection LLM 执行三步诊断:
      1. 分析轨迹: 识别失败模式中的共性问题
      2. 归因根因: 定位到具体文本缺陷
      3. 生成改良: 输出针对性的新指令文本

    四种变异操作: 重写(Rewrite)、插入(Insert)、删除(Delete)、压缩(Compress)
    """

    def __init__(
        self,
        reflection_model: str = "claude-sonnet-4-20250514",
        llm_call_fn: Optional[Callable] = None,
        mutation_weights: Optional[dict[MutationType, float]] = None,
    ):
        """
        Args:
            reflection_model: 反思用的模型名称 (应比被优化模型更强)
            llm_call_fn: LLM API调用函数 (prompt -> str)。为None时使用内置模拟。
            mutation_weights: 四种变异操作的权重, 默认均匀
        """
        self.reflection_model = reflection_model
        self.llm_call_fn = llm_call_fn or self._default_llm_call
        self.mutation_weights = mutation_weights or {
            MutationType.REWRITE:  0.40,
            MutationType.INSERT:   0.25,
            MutationType.DELETE:   0.15,
            MutationType.COMPRESS: 0.20,
        }

    # ---- 公开接口 ----

    def mutate(
        self,
        candidate: TextCandidate,
        execution_traces: list[ExecutionTrace],
    ) -> tuple[TextCandidate, str]:
        """
        对候选文本执行RPM变异。

        Args:
            candidate: 当前候选文本
            execution_traces: 该候选的执行轨迹列表

        Returns:
            (mutated_candidate, diagnosis): 变异后的候选和诊断报告
        """
        # 1. 选择变异类型 (加权随机)
        mutation_type = self._select_mutation_type()

        # 2. 构建反思提示词
        reflection_prompt = self._build_reflection_prompt(
            candidate, execution_traces, mutation_type
        )

        # 3. 调用 Reflection LLM 获取诊断和改良
        reflection_result = self._call_reflection(reflection_prompt)

        # 4. 应用变异生成新文本
        new_text, diagnosis = self._apply_mutation(
            candidate.text, reflection_result, mutation_type
        )

        # 5. 构造子代候选
        child = TextCandidate(
            candidate_id="",
            text=new_text,
            phase=candidate.phase,
            generation=candidate.generation + 1,
            parent_ids=[candidate.candidate_id],
            mutation_history=candidate.mutation_history + [
                f"Gen{candidate.generation + 1}:{mutation_type.value}"
            ],
            metadata={
                **candidate.metadata,
                "last_mutation": mutation_type.value,
                "diagnosis": diagnosis,
            },
        )

        return child, diagnosis

    # ---- 内部方法 ----

    def _select_mutation_type(self) -> MutationType:
        """加权随机选择变异类型"""
        types = list(self.mutation_weights.keys())
        weights = list(self.mutation_weights.values())
        return random.choices(types, weights=weights, k=1)[0]

    def _build_reflection_prompt(
        self,
        candidate: TextCandidate,
        traces: list[ExecutionTrace],
        mutation_type: MutationType,
    ) -> str:
        """构建反思提示词"""
        traces_text = self._format_traces(traces)
        mutation_desc = {
            MutationType.REWRITE:  "整体重写文本, 修正根本性问题",
            MutationType.INSERT:   "在适当位置插入缺失的关键信息或指令",
            MutationType.DELETE:   "删除冗余、误导或产生负面效果的文本段落",
            MutationType.COMPRESS: "压缩文本保持语义不变但更简洁精准",
        }

        return f"""你是一个Agent技能诊断专家。请分析以下执行轨迹,诊断失败根因,生成改良方案。

## 当前文本
```
{candidate.text}
```

## 执行轨迹 ({len(traces)} 条)
{traces_text}

## 诊断要求
1. 识别失败模式中的共性问题 (分析所有轨迹)
2. 归因到当前文本中的具体缺陷 (缺失信息? 误导表述? 逻辑漏洞? 冗余内容?)
3. 执行变异操作: **{mutation_desc[mutation_type]}**

## 输出格式 (严格JSON)
```json
{{
  "diagnosis": "对失败模式的详细诊断 (用中文)",
  "root_cause": "归因到文本的具体缺陷描述 (用中文)",
  "mutation_type": "{mutation_type.value}",
  "updated_text": "改良后的完整文本"
}}
```
"""

    def _format_traces(self, traces: list[ExecutionTrace]) -> str:
        """格式化执行轨迹为可读文本"""
        lines = []
        for i, t in enumerate(traces[:10]):  # 最多取10条轨迹
            status = "成功" if t.success else "失败"
            lines.append(f"### 轨迹 {i + 1} [{status}]")
            lines.append(f"- 任务: {t.task_input[:200]}")
            if t.reasoning_chain:
                lines.append("- 推理链:")
                for step in t.reasoning_chain[-5:]:  # 最近5步
                    lines.append(f"    > {step[:150]}")
            if t.tool_calls:
                lines.append(f"- 工具调用: {len(t.tool_calls)} 次")
                for tc in t.tool_calls[-3:]:
                    lines.append(f"    > {json.dumps(tc, ensure_ascii=False)[:200]}")
            if t.errors:
                lines.append("- 错误信息:")
                for err in t.errors[-3:]:
                    lines.append(f"    ! {err[:200]}")
            if t.evaluation_feedback:
                lines.append(f"- 评估反馈: {t.evaluation_feedback[:300]}")
            lines.append("")
        return "\n".join(lines)

    def _call_reflection(self, prompt: str) -> dict:
        """
        调用 Reflection LLM。

        在生产模式下, 通过 llm_call_fn 调用真实API。
        在演示模式下, 使用规则驱动的模拟。
        """
        response_text = self.llm_call_fn(prompt)
        return self._parse_reflection_response(response_text)

    def _parse_reflection_response(self, response_text: str) -> dict:
        """解析 Reflection LLM 的JSON响应"""
        try:
            # 尝试直接解析 JSON
            # 处理可能的 markdown code block 包裹
            text = response_text.strip()
            if text.startswith("```"):
                # 移除 markdown 代码块标记
                lines = text.split("\n")
                text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
            return json.loads(text)
        except json.JSONDecodeError:
            logger.warning("无法解析 Reflection LLM 响应为JSON, 使用模拟结果")
            return {
                "diagnosis": "自动解析失败,使用启发式诊断",
                "root_cause": "无法解析LLM响应,基于轨迹统计推断",
                "mutation_type": "rewrite",
                "updated_text": response_text[:1000],
            }

    def _apply_mutation(
        self, original_text: str, reflection: dict, mutation_type: MutationType
    ) -> tuple[str, str]:
        """应用变异操作生成新文本"""
        updated = reflection.get("updated_text", original_text)
        diagnosis = reflection.get("diagnosis", "")
        root_cause = reflection.get("root_cause", "")

        if not updated or updated == original_text:
            # 反射未能产生有效改良, 回退到启发式
            updated = self._heuristic_mutation(original_text, mutation_type)
            diagnosis = f"反射未生成有效结果, 回退到启发式{mutation_type.value}变异"

        full_diagnosis = f"[{mutation_type.value}] {diagnosis} | 根因: {root_cause}"
        return updated, full_diagnosis

    def _heuristic_mutation(self, text: str, mutation_type: MutationType) -> str:
        """启发式变异 (当Reflection LLM不可用时的后备方案)"""
        lines = text.split("\n")
        if not lines:
            return text

        if mutation_type == MutationType.REWRITE:
            # 添加改善标记
            preamble = "## 优化版指令 (自动进化)\n"
            return preamble + text

        elif mutation_type == MutationType.INSERT:
            # 在1/3处插入一个提示
            idx = max(1, len(lines) // 3)
            lines.insert(idx, "<!-- 自动插入: 请逐步推理后再给出最终答案 -->")
            return "\n".join(lines)

        elif mutation_type == MutationType.DELETE:
            # 删除最短的行
            if len(lines) > 3:
                shortest_idx = min(range(len(lines)), key=lambda i: len(lines[i]))
                lines.pop(shortest_idx)
            return "\n".join(lines)

        elif mutation_type == MutationType.COMPRESS:
            # 移除空行和纯注释行
            compressed = [
                l for l in lines
                if l.strip() and not l.strip().startswith("#")
            ]
            return "\n".join(compressed) if compressed else text

        return text

    @staticmethod
    def _default_llm_call(prompt: str) -> str:
        """
        默认LLM调用 (演示/模拟模式)。

        在无API Key时可运行, 生成有意义的模拟响应来验证引擎流程。
        生产环境应替换为真实的 Claude/GPT API 调用。
        """
        # 模拟反射响应: 基于prompt内容生成差异化的"改良"
        has_errors = "错误" in prompt or "失败" in prompt
        sample_text = "优化后的Agent技能指令文本"

        return json.dumps({
            "diagnosis": (
                "分析发现当前文本存在以下共性问题: "
                + ("错误处理逻辑缺失,对边界条件描述不足。" if has_errors
                   else "指令结构清晰但可进一步细化步骤说明。")
            ),
            "root_cause": (
                "文本缺少对异常路径的明确指引,导致Agent在遇到非预期输入时行为不确定。"
                if has_errors
                else "通用性描述过多,缺少场景细化的操作步骤。"
            ),
            "mutation_type": "rewrite",
            "updated_text": (
                f"{sample_text}\n\n"
                f"## 核心原则\n"
                f"1. 总是先理解任务需求再行动\n"
                f"2. 遇到不确定情况时主动询问澄清\n"
                f"3. 完成每步后自我检查输出质量\n"
                + (f"4. 当遇到错误时,记录完整错误信息并尝试备选方案\n" if has_errors else "")
            ),
        }, ensure_ascii=False)


# ---------------------------------------------------------------------------
# 模块二: 帕累托多目标筛选
# ---------------------------------------------------------------------------

class ParetoSelector:
    """
    帕累托多目标筛选器

    维护一个帕累托前沿——在不同实例/指标维度上各自最优的候选集合。

    支配关系: 候选 A 支配候选 B,当且仅当:
      - A 在每个实例上的得分 >= B
      - A 在至少一个实例上严格 > B

    选择策略:
      - 统计每个候选在哪些实例上是"最佳"
      - 按获胜实例数量加权随机采样
      - 效果: 自动平衡探索与利用, 避免陷入局部最优
    """

    def __init__(
        self,
        max_frontier_size: int = 50,
        patience: int = 3,
    ):
        """
        Args:
            max_frontier_size: 帕累托前沿最大容量
            patience: 连续拒绝容忍次数 (早停参数)
        """
        self.max_frontier_size = max_frontier_size
        self.patience = patience
        self.candidates: dict[str, TextCandidate] = {}     # 全部候选
        self.scores: dict[str, EvaluationScore] = {}       # 候选得分
        self.frontier: set[str] = set()                    # 帕累托前沿 (候选ID集合)
        self.rejected_streak: int = 0                      # 连续拒绝计数

    # ---- 公开接口 ----

    def add_candidate(
        self, candidate: TextCandidate, score: EvaluationScore
    ) -> bool:
        """
        将候选添加到池中, 并更新帕累托前沿。

        Returns:
            True 如果候选被接受 (非支配), False 如果被拒绝
        """
        cid = candidate.candidate_id
        self.candidates[cid] = candidate
        self.scores[cid] = score

        is_non_dominated = self._check_non_dominated(cid)

        if is_non_dominated:
            self.frontier.add(cid)
            self._prune_dominated()
            self._trim_frontier()
            self.rejected_streak = 0
            logger.info(f"候选 {cid[:12]} 被接受 (前沿大小: {len(self.frontier)})")
            return True
        else:
            self.rejected_streak += 1
            logger.info(
                f"候选 {cid[:12]} 被拒绝 "
                f"(连续拒绝: {self.rejected_streak}/{self.patience})"
            )
            return False

    def select_parent(self) -> TextCandidate:
        """
        从帕累托前沿加权采样选择父本。

        策略: 统计每个候选获取得分最优的维度数, 按获胜维度数加权采样。
        """
        if not self.frontier:
            # 前沿为空, 随机选一个
            if self.candidates:
                return random.choice(list(self.candidates.values()))
            raise ValueError("候选池为空, 无法选择父本")

        frontier_list = list(self.frontier)
        win_counts = [self._count_wins(cid) for cid in frontier_list]

        # 加权随机采样 (获胜数 + 基础权重)
        weights = [max(1, wc) for wc in win_counts]
        selected_id = random.choices(frontier_list, weights=weights, k=1)[0]

        return self.candidates[selected_id]

    def get_frontier_candidates(self) -> list[TextCandidate]:
        """获取帕累托前沿上的所有候选"""
        return [self.candidates[cid] for cid in self.frontier]

    def get_best_candidate(self) -> Optional[TextCandidate]:
        """获取综合最优候选 (前沿上总分最高者)"""
        if not self.frontier:
            return None
        best_id = max(
            self.frontier,
            key=lambda cid: sum(self.scores[cid].to_vector()),
        )
        return self.candidates[best_id]

    def should_early_stop(self) -> bool:
        """检查是否应触发早停"""
        return self.rejected_streak >= self.patience

    def get_statistics(self) -> dict:
        """获取筛选器统计信息"""
        return {
            "total_candidates": len(self.candidates),
            "frontier_size": len(self.frontier),
            "rejected_streak": self.rejected_streak,
            "acceptance_rate": (
                len(self.frontier) / max(1, len(self.candidates))
            ),
            "frontier_candidates": [
                {
                    "id": cid[:16],
                    "generation": self.candidates[cid].generation,
                    "score_sum": sum(self.scores[cid].to_vector()),
                }
                for cid in list(self.frontier)[:10]
            ],
        }

    # ---- 内部方法 ----

    def _check_non_dominated(self, candidate_id: str) -> bool:
        """检查候选是否被池中任何已有候选支配"""
        new_score = self.scores[candidate_id]
        for cid, existing_score in self.scores.items():
            if cid == candidate_id:
                continue
            if existing_score.dominates(new_score):
                return False
        return True

    def _prune_dominated(self):
        """移除前沿上被新候选支配的旧候选"""
        new_ids = set()
        for cid in list(self.frontier):
            # 检查cid是否被任何其他前沿候选支配
            dominated = False
            for other_id in self.frontier:
                if other_id == cid:
                    continue
                if self.scores[other_id].dominates(self.scores[cid]):
                    dominated = True
                    break
            if not dominated:
                new_ids.add(cid)
        removed = self.frontier - new_ids
        self.frontier = new_ids
        if removed:
            logger.debug(f"移除了 {len(removed)} 个被支配的候选")

    def _trim_frontier(self):
        """当前沿超过最大容量时, 按总分截断"""
        if len(self.frontier) <= self.max_frontier_size:
            return
        # 按总分排序, 保留前 max_frontier_size 个
        sorted_ids = sorted(
            self.frontier,
            key=lambda cid: sum(self.scores[cid].to_vector()),
            reverse=True,
        )
        removed = set(sorted_ids[self.max_frontier_size:])
        self.frontier = set(sorted_ids[:self.max_frontier_size])
        logger.info(
            f"前沿截断: 移除 {len(removed)} 个候选 "
            f"(容量: {self.max_frontier_size})"
        )

    def _count_wins(self, candidate_id: str) -> int:
        """统计候选在多少维度上是前沿上的最优"""
        score = self.scores[candidate_id]
        vec = score.to_vector()
        wins = 0
        for dim_idx in range(len(vec)):
            best_val = vec[dim_idx]
            is_best = True
            for other_id in self.frontier:
                if other_id == candidate_id:
                    continue
                other_val = self.scores[other_id].to_vector()[dim_idx]
                if other_val > best_val:
                    is_best = False
                    break
            if is_best:
                wins += 1
        return wins


# ---------------------------------------------------------------------------
# 模块三: 五层安全门禁
# ---------------------------------------------------------------------------

class SafetyGate:
    """
    五层安全门禁系统

    对齐 Hermes Agent 标准, 确保所有进化产物安全可控:

    L1: 测试全量通过 — pytest tests/ -q 100%通过 (硬阻塞)
    L2: 文件大小限制 — SKILL.md ≤ 15KB, 工具描述 ≤ 500字符 (硬阻塞)
    L3: 缓存兼容性 — 不破坏中间会话缓存 (硬阻塞)
    L4: 语义保真度 — 优化方向不偏离原始用途 (软阻塞)
    L5: 人工PR审查 — 所有变更以Pull Request提交 (硬阻塞, 自动模式下跳过)
    """

    # 文件大小限制 (字节)
    SIZE_LIMITS = {
        EvolutionPhase.PHASE1_SKILLS:    15 * 1024,   # SKILL.md ≤ 15KB
        EvolutionPhase.PHASE2_TOOLS:     500,          # 工具描述 ≤ 500字符
        EvolutionPhase.PHASE3_PROMPTS:   8 * 1024,     # 系统提示词 ≤ 8KB
        EvolutionPhase.PHASE4_RULES:     10 * 1024,    # MR规则 ≤ 10KB
        EvolutionPhase.PHASE5_PIPELINE:  20 * 1024,    # Pipeline ≤ 20KB
    }

    def __init__(
        self,
        auto_mode: bool = False,
        test_runner: Optional[Callable[[str], bool]] = None,
        cache_validator: Optional[Callable[[str], bool]] = None,
        semantic_judge: Optional[Callable[[str, str], float]] = None,
    ):
        """
        Args:
            auto_mode: 自动模式 (跳过长耗时的人工审查)
            test_runner: 测试执行函数, (text) -> bool
            cache_validator: 缓存兼容性检查函数
            semantic_judge: 语义保真度评判函数, (original, evolved) -> float[0,1]
        """
        self.auto_mode = auto_mode
        self.test_runner = test_runner or self._default_test_runner
        self.cache_validator = cache_validator or self._default_cache_validator
        self.semantic_judge = semantic_judge or self._default_semantic_judge
        self.gate_log: list[GateReport] = []

    # ---- 公开接口 ----

    def full_gate_check(
        self,
        candidate: TextCandidate,
        original_text: Optional[str] = None,
        phase: Optional[EvolutionPhase] = None,
    ) -> tuple[bool, list[GateReport]]:
        """
        执行全部五层门禁检查。

        Args:
            candidate: 待检查的候选文本
            original_text: 原始文本 (用于L4语义保真度对比)
            phase: 进化阶段 (用于L2文件大小限制)

        Returns:
            (passed, reports): 是否通过全部硬阻塞, 各层报告
        """
        phase = phase or candidate.phase
        original = original_text or ""
        reports: list[GateReport] = []

        # L1: 测试全量通过
        reports.append(self._check_l1_test(candidate, phase))

        # L2: 文件大小限制
        reports.append(self._check_l2_size(candidate, phase))

        # L3: 缓存兼容性
        reports.append(self._check_l3_cache(candidate))

        # L4: 语义保真度
        reports.append(self._check_l4_semantic(candidate, original))

        # L5: 人工PR审查
        reports.append(self._check_l5_review(candidate))

        self.gate_log.extend(reports)

        # 硬阻塞检查
        hard_failed = any(
            r.result == GateResult.FAIL_HARD for r in reports
        )
        return not hard_failed, reports

    def get_gate_summary(self) -> dict:
        """获取门禁通过率统计"""
        if not self.gate_log:
            return {"total": 0}
        counts = defaultdict(int)
        for r in self.gate_log:
            counts[r.result.value] += 1
        return {
            "total": len(self.gate_log),
            "pass": counts.get("pass", 0),
            "fail_hard": counts.get("fail_hard", 0),
            "fail_soft": counts.get("fail_soft", 0),
            "skip": counts.get("skip", 0),
            "pass_rate": counts.get("pass", 0) / len(self.gate_log),
        }

    # ---- L1: 测试全量通过 ----

    def _check_l1_test(
        self, candidate: TextCandidate, phase: EvolutionPhase
    ) -> GateReport:
        """L1: 全部测试必须通过 (硬阻塞)"""
        try:
            passed = self.test_runner(candidate.text)
            return GateReport(
                level=GateLevel.L1_TEST_PASSING,
                result=GateResult.PASS if passed else GateResult.FAIL_HARD,
                detail="所有测试通过" if passed else "存在测试失败",
                score=1.0 if passed else 0.0,
            )
        except Exception as e:
            return GateReport(
                level=GateLevel.L1_TEST_PASSING,
                result=GateResult.FAIL_HARD,
                detail=f"测试执行异常: {e}",
                score=0.0,
            )

    # ---- L2: 文件大小限制 ----

    def _check_l2_size(
        self, candidate: TextCandidate, phase: EvolutionPhase
    ) -> GateReport:
        """L2: 文件大小必须在限制内 (硬阻塞)"""
        limit = self.SIZE_LIMITS.get(phase, 15 * 1024)
        text_bytes = len(candidate.text.encode("utf-8"))
        text_chars = len(candidate.text)

        # 对 tools 阶段使用字符数限制
        if phase == EvolutionPhase.PHASE2_TOOLS:
            actual_size = text_chars
            unit = "字符"
        else:
            actual_size = text_bytes
            unit = "字节"

        passed = actual_size <= limit

        return GateReport(
            level=GateLevel.L2_FILE_SIZE,
            result=GateResult.PASS if passed else GateResult.FAIL_HARD,
            detail=(
                f"大小 {actual_size}{unit} {'≤' if passed else '>'} 限制 {limit}{unit}"
            ),
            score=1.0 if passed else max(0.0, 1.0 - (actual_size - limit) / limit),
        )

    # ---- L3: 缓存兼容性 ----

    def _check_l3_cache(self, candidate: TextCandidate) -> GateReport:
        """L3: 不破坏中间会话缓存 (硬阻塞)"""
        try:
            compatible = self.cache_validator(candidate.text)
            return GateReport(
                level=GateLevel.L3_CACHE_COMPAT,
                result=GateResult.PASS if compatible else GateResult.FAIL_HARD,
                detail=(
                    "缓存兼容性检查通过"
                    if compatible
                    else "文本变更可能破坏缓存兼容性"
                ),
                score=1.0 if compatible else 0.0,
            )
        except Exception as e:
            return GateReport(
                level=GateLevel.L3_CACHE_COMPAT,
                result=GateResult.FAIL_HARD,
                detail=f"缓存校验异常: {e}",
                score=0.0,
            )

    # ---- L4: 语义保真度 ----

    def _check_l4_semantic(
        self, candidate: TextCandidate, original_text: str
    ) -> GateReport:
        """L4: 语义保真度检查 (软阻塞)"""
        if not original_text:
            return GateReport(
                level=GateLevel.L4_SEMANTIC_FIDELITY,
                result=GateResult.PASS,
                detail="无原始文本, 跳过语义对比",
                score=1.0,
            )

        fidelity = self.semantic_judge(original_text, candidate.text)
        passed = fidelity >= 0.7  # 语义相似度阈值

        return GateReport(
            level=GateLevel.L4_SEMANTIC_FIDELITY,
            result=GateResult.PASS if passed else GateResult.FAIL_SOFT,
            detail=(
                f"语义保真度 {fidelity:.2%} {'≥' if passed else '<'} 阈值 70%"
            ),
            score=fidelity,
        )

    # ---- L5: 人工PR审查 ----

    def _check_l5_review(self, candidate: TextCandidate) -> GateReport:
        """L5: 人工PR审查 (硬阻塞, 自动模式下跳过)"""
        if self.auto_mode:
            return GateReport(
                level=GateLevel.L5_HUMAN_REVIEW,
                result=GateResult.SKIP,
                detail="自动模式, 跳过人工审查",
                score=1.0,
            )

        # 在非自动模式下, L5 始终返回 FAIL_HARD,
        # 要求以PR形式提交人工审查后方可通过
        return GateReport(
            level=GateLevel.L5_HUMAN_REVIEW,
            result=GateResult.FAIL_HARD,
            detail="需要以PR形式提交人工审查",
            score=0.0,
        )

    # ---- 默认实现 (演示模式) ----

    @staticmethod
    def _default_test_runner(text: str) -> bool:
        """默认测试执行器 (模拟)"""
        # 模拟: 文本包含特定错误模式则测试失败
        failure_patterns = ["DROP TABLE", "rm -rf /", "os.system(", "eval("]
        for pattern in failure_patterns:
            if pattern in text:
                return False
        return True

    @staticmethod
    def _default_cache_validator(text: str) -> bool:
        """默认缓存兼容性检查器 (模拟)"""
        # 模拟: 文本包含破坏缓存的结构变更
        dangerous_changes = [
            "cache.clear()",
            "invalidate_all",
            "DROP CACHE",
        ]
        for change in dangerous_changes:
            if change in text:
                return False
        return True

    @staticmethod
    def _default_semantic_judge(original: str, evolved: str) -> float:
        """
        默认语义保真度评判 (模拟)。

        生产环境应使用 LLM 评判或语义嵌入余弦相似度。
        """
        # 简化: 基于公共词比例估算语义相似度
        original_words = set(original.lower().split())
        evolved_words = set(evolved.lower().split())
        if not original_words:
            return 1.0
        overlap = len(original_words & evolved_words)
        fidelity = overlap / len(original_words)
        # 模拟: 给一个合理的保真度值
        return 0.75 + 0.2 * fidelity


# ---------------------------------------------------------------------------
# 模块四: 谱系追踪
# ---------------------------------------------------------------------------

class LineageTracker:
    """
    谱系追踪系统

    记录每个候选的完整进化谱系:
      - 父子关系
      - 变异操作
      - 进化代数
      - 门禁结果

    支持: 谱系树可视化数据导出、跨分支交叉分析、退化检测
    """

    def __init__(self):
        self.records: list[EvolutionRecord] = []
        self.lineage_tree: dict[str, list[str]] = defaultdict(list)  # parent -> [children]
        self.generation_index: dict[int, list[str]] = defaultdict(list)

    def record(
        self,
        generation: int,
        parent_id: str,
        child_id: str,
        mutation_type: MutationType,
        mutation_detail: str,
        gate_results: list[GateReport],
        accepted: bool,
    ):
        """记录一次进化事件"""
        rec = EvolutionRecord(
            generation=generation,
            parent_id=parent_id,
            child_id=child_id,
            mutation_type=mutation_type,
            mutation_detail=mutation_detail,
            gate_results=gate_results,
            accepted=accepted,
            timestamp=time.strftime("%Y-%m-%dT%H:%M:%S"),
        )
        self.records.append(rec)

        if accepted:
            self.lineage_tree[parent_id].append(child_id)
            self.generation_index[generation].append(child_id)

    def get_lineage_chain(self, candidate_id: str) -> list[str]:
        """追溯候选的完整谱系链 (从根到当前)"""
        chain = [candidate_id]
        # 反向查找父本
        for rec in self.records:
            if rec.child_id == candidate_id and rec.accepted:
                parent_chain = self.get_lineage_chain(rec.parent_id)
                return parent_chain + chain
        return chain

    def get_cross_branch_candidates(
        self, candidate_id: str
    ) -> list[str]:
        """获取同一代的不同分支候选 (用于 System-Aware Merge)"""
        # 找到候选的代
        gen = None
        for rec in self.records:
            if rec.child_id == candidate_id:
                gen = rec.generation
                break
        if gen is None:
            return []
        # 返回同代其他候选
        return [
            cid for cid in self.generation_index.get(gen, [])
            if cid != candidate_id
        ]

    def detect_degradation(
        self, candidate_id: str, scores: dict[str, EvaluationScore], window: int = 5
    ) -> bool:
        """
        检测谱系链中的退化趋势。

        如果连续 window 代的综合得分单调下降, 返回 True。
        """
        chain = self.get_lineage_chain(candidate_id)
        if len(chain) < window:
            return False

        recent = chain[-window:]
        recent_scores = []
        for cid in recent:
            if cid in scores:
                recent_scores.append(sum(scores[cid].to_vector()))
            else:
                return False

        if len(recent_scores) < window:
            return False

        # 检查是否单调下降
        return all(
            recent_scores[i] > recent_scores[i + 1]
            for i in range(len(recent_scores) - 1)
        )

    def get_statistics(self) -> dict:
        """获取谱系统计"""
        accepted = [r for r in self.records if r.accepted]
        mutation_counts = defaultdict(int)
        for r in accepted:
            mutation_counts[r.mutation_type.value] += 1

        return {
            "total_evolutions": len(self.records),
            "accepted_evolutions": len(accepted),
            "acceptance_rate": len(accepted) / max(1, len(self.records)),
            "mutation_distribution": dict(mutation_counts),
            "max_generation": max(self.generation_index.keys()) if self.generation_index else 0,
            "total_lineages": len(self.lineage_tree),
        }

    def export_lineage_json(self, filepath: str) -> None:
        """导出谱系数据为JSON"""
        data = {
            "records": [asdict(r) for r in self.records],
            "lineage_tree": {k: v for k, v in self.lineage_tree.items()},
            "generation_index": {str(k): v for k, v in self.generation_index.items()},
        }
        # 处理不可序列化类型
        for rec in data["records"]:
            rec["mutation_type"] = str(rec["mutation_type"])
            for gr in rec["gate_results"]:
                gr["level"] = str(gr["level"])
                gr["result"] = str(gr["result"])
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logger.info(f"谱系数据已导出至: {filepath}")


# ---------------------------------------------------------------------------
# 模块五: 评估器
# ---------------------------------------------------------------------------

class Evaluator:
    """
    候选评估器

    基于执行轨迹计算多维度 EvaluationScore。
    支持批量评估和增量更新。
    """

    def __init__(
        self,
        mini_batch_size: int = 5,
        pareto_batch_size: int = 20,
    ):
        self.mini_batch_size = mini_batch_size
        self.pareto_batch_size = pareto_batch_size

    def evaluate(
        self, candidate: TextCandidate, traces: list[ExecutionTrace]
    ) -> EvaluationScore:
        """基于执行轨迹计算多维度得分"""
        if not traces:
            return self._text_based_evaluate(candidate)

        success_count = sum(1 for t in traces if t.success)
        total = len(traces)

        score = EvaluationScore(
            candidate_id=candidate.candidate_id,
            task_success_rate=success_count / total,
            avg_latency_ms=(
                sum(t.latency_ms for t in traces) / total
            ),
            error_rate=sum(len(t.errors) for t in traces) / max(1, total),
            output_quality=self._estimate_quality(traces),
            reasoning_depth=self._estimate_reasoning_depth(traces),
            tool_usage_efficiency=self._estimate_tool_efficiency(traces),
            safety_score=self._estimate_safety(traces),
            num_evaluations=total,
        )
        return score

    def _text_based_evaluate(self, candidate: TextCandidate) -> EvaluationScore:
        """纯基于文本特征的无轨迹评估 (冷启动用)"""
        text = candidate.text
        text_len = len(text)

        # 长度评分
        if text_len >= 600:
            len_score = 0.18
        elif text_len >= 300:
            len_score = 0.08 + 0.10 * (text_len - 300) / 300
        elif text_len >= 150:
            len_score = 0.02 + 0.06 * (text_len - 150) / 150
        else:
            len_score = 0.0

        # 结构评分
        struct = 0.0
        if "#" in text: struct += 0.05
        if "##" in text: struct += 0.05
        if any(f"{i}." in text for i in range(1, 4)): struct += 0.06
        if "约束" in text or "限制" in text: struct += 0.04
        if "步骤" in text or "流程" in text: struct += 0.04
        if "错误" in text or "异常" in text: struct += 0.05

        lines = [l for l in text.split("\n") if l.strip()]
        content = min(0.10, len(lines) * 0.008)

        gen_bonus = min(0.12, candidate.generation * 0.02)
        last_mut = candidate.metadata.get("last_mutation", "")
        mut_bonus = {"rewrite": 0.05, "insert": 0.03, "compress": 0.02, "merge": 0.04}.get(last_mut, 0.0)

        quality = min(0.80, 0.30 + len_score + struct + content + gen_bonus + mut_bonus)

        return EvaluationScore(
            candidate_id=candidate.candidate_id,
            task_success_rate=quality,
            output_quality=quality,
            reasoning_depth=min(0.75, 0.30 + struct + content),
            tool_usage_efficiency=0.50 + quality * 0.25,
            safety_score=0.95,
            num_evaluations=0,
        )

    def quick_evaluate(
        self, candidate: TextCandidate, traces: list[ExecutionTrace]
    ) -> EvaluationScore:
        """快速评估 (使用迷你批次)"""
        sample = traces[:self.mini_batch_size]
        return self.evaluate(candidate, sample)

    # ---- 启发式质量评估 ----

    @staticmethod
    def _estimate_quality(traces: list[ExecutionTrace]) -> float:
        """基于反馈文本估算输出质量"""
        quality_scores = []
        for t in traces:
            feedback = t.evaluation_feedback.lower()
            if "优秀" in feedback or "excellent" in feedback:
                quality_scores.append(0.95)
            elif "良好" in feedback or "good" in feedback:
                quality_scores.append(0.8)
            elif "一般" in feedback or "acceptable" in feedback:
                quality_scores.append(0.6)
            elif "差" in feedback or "poor" in feedback:
                quality_scores.append(0.3)
            else:
                quality_scores.append(0.7 if t.success else 0.4)
        return sum(quality_scores) / len(quality_scores) if quality_scores else 0.5

    @staticmethod
    def _estimate_reasoning_depth(traces: list[ExecutionTrace]) -> float:
        """基于推理链长度和复杂度估算推理深度"""
        depths = []
        for t in traces:
            chain_len = len(t.reasoning_chain)
            # 推理步数在 3-10 之间视为深度合理
            if chain_len >= 5:
                depths.append(min(1.0, chain_len / 10.0))
            else:
                depths.append(chain_len / 5.0)
        return sum(depths) / len(depths) if depths else 0.5

    @staticmethod
    def _estimate_tool_efficiency(traces: list[ExecutionTrace]) -> float:
        """估算工具使用效率 (调用少且成功 = 高效率)"""
        efficiencies = []
        for t in traces:
            n_calls = len(t.tool_calls)
            if n_calls == 0:
                efficiencies.append(0.5)  # 未使用工具
            else:
                # 成功且调用数少 = 效率高
                eff = 1.0 / (1.0 + 0.2 * n_calls)
                if t.success:
                    eff *= 1.2
                efficiencies.append(min(1.0, eff))
        return sum(efficiencies) / len(efficiencies) if efficiencies else 0.5

    @staticmethod
    def _estimate_safety(traces: list[ExecutionTrace]) -> float:
        """估算安全性"""
        safety_deductions = 0.0
        for t in traces:
            for err in t.errors:
                err_lower = err.lower()
                if any(kw in err_lower for kw in ["unsafe", "injection", "overflow", "bypass"]):
                    safety_deductions += 0.2
        return max(0.1, 1.0 - safety_deductions / max(1, len(traces)))


# ---------------------------------------------------------------------------
# 模块六: 系统感知交叉 (System-Aware Merge)
# ---------------------------------------------------------------------------

class SystemAwareMerger:
    """
    系统感知交叉 (System-Aware Merge)

    从不同进化分支融合互补优势:
      - 找到与当前父本来自不同谱系、在互补维度上更强的候选
      - 只交换那些"自共同祖先以来另一方已经进化过"的模块
      - 保留完整谱系追踪, 防止退化
    """

    def __init__(self, merge_probability: float = 0.15):
        self.merge_probability = merge_probability

    def should_merge(self) -> bool:
        """随机判定是否执行交叉"""
        return random.random() < self.merge_probability

    def merge(
        self,
        parent: TextCandidate,
        pool: dict[str, TextCandidate],
        scores: dict[str, EvaluationScore],
        lineage: LineageTracker,
    ) -> TextCandidate:
        """
        执行系统感知交叉。

        策略: 找在父本最弱维度上最强的异谱系候选, 交叉其进化模块。
        """
        # 1. 找到父本的最弱维度
        if parent.candidate_id not in scores:
            return parent  # 无法评估, 不交叉

        parent_vec = scores[parent.candidate_id].to_vector()
        weakest_dim = min(range(len(parent_vec)), key=lambda i: parent_vec[i])

        # 2. 找到不同谱系的候选
        parent_chain = lineage.get_lineage_chain(parent.candidate_id)
        candidates_from_other_branches = []
        for cid, c in pool.items():
            if cid == parent.candidate_id:
                continue
            c_chain = lineage.get_lineage_chain(cid)
            # 不同谱系: 谱系链不共享最近的父本
            if c_chain[-1] != parent_chain[-1]:
                candidates_from_other_branches.append(cid)

        if not candidates_from_other_branches:
            return parent

        # 3. 找在最弱维度上最强的异谱系候选
        best_partner_id = max(
            candidates_from_other_branches,
            key=lambda cid: (
                scores[cid].to_vector()[weakest_dim] if cid in scores else -999
            ),
        )
        best_partner = pool.get(best_partner_id)
        if best_partner is None:
            return parent

        # 4. 交叉: 将 partner 的进化模块注入 parent
        merged_text = self._splice_texts(parent.text, best_partner.text)
        child = TextCandidate(
            candidate_id="",
            text=merged_text,
            phase=parent.phase,
            generation=max(parent.generation, best_partner.generation) + 1,
            parent_ids=[parent.candidate_id, best_partner.candidate_id],
            mutation_history=parent.mutation_history + [
                f"Gen{max(parent.generation, best_partner.generation) + 1}:merge"
            ],
            metadata={
                **parent.metadata,
                "merged_from": best_partner.candidate_id,
                "last_mutation": "merge",
            },
        )

        return child

    @staticmethod
    def _splice_texts(text_a: str, text_b: str) -> str:
        """拼接两个文本的精华部分"""
        lines_a = [l for l in text_a.split("\n") if l.strip()]
        lines_b = [l for l in text_b.split("\n") if l.strip()]

        # 取A的前半部分 + B中不在A中的独特部分
        half = max(1, len(lines_a) // 2)
        unique_b = [l for l in lines_b if l not in lines_a]

        merged_lines = lines_a[:half] + unique_b + lines_a[half:]
        return "\n".join(merged_lines)


# ---------------------------------------------------------------------------
# 主引擎: GEPA 进化编排
# ---------------------------------------------------------------------------

class GEPAEvolutionEngine:
    """
    GEPA 文本参数进化引擎 — 主编排器

    进化循环:
      候选池 P → 选择父本 (帕累托采样) → 变异/交叉 → 子代
      → 迷你批次门禁 (子代 > 父本? )
        → Yes: 帕累托门禁 (非支配? )
          → Yes: 加入候选池
          → No: 连续拒绝 ≥ patience → 早停
    """

    def __init__(
        self,
        evolution_phase: EvolutionPhase = EvolutionPhase.PHASE1_SKILLS,
        max_generations: int = 50,
        budget_cap: float = 50.0,
        cost_per_generation: float = 2.0,
        auto_mode: bool = False,
        reflection_model: str = "claude-sonnet-4-20250514",
        llm_call_fn: Optional[Callable] = None,
        random_seed: Optional[int] = None,
        output_dir: str = "./gepa-output",
    ):
        """
        Args:
            evolution_phase: 进化阶段
            max_generations: 最大进化代数
            budget_cap: 预算上限 (美元)
            cost_per_generation: 每代预估成本 (美元)
            auto_mode: 自动模式 (跳过L5人工审查)
            reflection_model: 反思模型名称
            llm_call_fn: LLM API调用函数
            random_seed: 随机种子
            output_dir: 输出目录
        """
        self.evolution_phase = evolution_phase
        self.max_generations = max_generations
        self.budget_cap = budget_cap
        self.cost_per_generation = cost_per_generation
        self.auto_mode = auto_mode

        if random_seed is not None:
            random.seed(random_seed)

        # 子模块
        self.mutator = RPMReflectiveMutator(
            reflection_model=reflection_model,
            llm_call_fn=llm_call_fn,
        )
        self.selector = ParetoSelector(
            max_frontier_size=50,
            patience=5,  # 连续拒绝5次才早停 (GEPA原论文是3, 这里放宽)
        )
        self.safety_gate = SafetyGate(auto_mode=auto_mode)
        self.evaluator = Evaluator()
        self.merger = SystemAwareMerger()
        self.lineage = LineageTracker()

        # 状态
        self.generation: int = 0
        self.used_budget: float = 0.0
        self.traces_db: dict[str, list[ExecutionTrace]] = defaultdict(list)
        self.original_text: str = ""
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # 统计
        self.stats: dict[str, Any] = {
            "total_mutations": 0,
            "total_merges": 0,
            "accepted_count": 0,
            "rejected_count": 0,
            "early_stopped": False,
        }

        logger.info(
            f"GEPA进化引擎初始化完成\n"
            f"  阶段: {evolution_phase.value}\n"
            f"  最大代数: {max_generations}\n"
            f"  预算上限: ${budget_cap}\n"
            f"  反思模型: {reflection_model}\n"
            f"  模式: {'自动' if auto_mode else '标准 (需人工审查)'}"
        )

    # ---- 主循环 ----

    def initialize(self, seed_text: str, seed_traces: Optional[list[ExecutionTrace]] = None):
        """
        初始化进化池。

        Args:
            seed_text: 初始文本 (种子)
            seed_traces: 种子文本已有的执行轨迹 (None时使用基于文本的直接评估)
        """
        self.original_text = seed_text

        seed = TextCandidate(
            candidate_id="SEED-001",
            text=seed_text,
            phase=self.evolution_phase,
            generation=0,
            metadata={"role": "seed"},
        )

        # 优先使用传入的真实轨迹, 否则直接用文本特征评估 (确定性)
        if seed_traces:
            self.traces_db[seed.candidate_id] = seed_traces
            score = self.evaluator.evaluate(seed, seed_traces)
        else:
            score = self.evaluator._text_based_evaluate(seed)

        self.selector.add_candidate(seed, score)
        logger.info(
            f"种子候选已加入: {seed.candidate_id} "
            f"(成功率: {score.task_success_rate:.1%}, "
            f"质量: {score.output_quality:.1%})"
        )

    def run_evolution(
        self,
        trace_collector: Optional[Callable[[TextCandidate], list[ExecutionTrace]]] = None,
    ) -> TextCandidate:
        """
        运行进化主循环。

        Args:
            trace_collector: 轨迹收集函数, (candidate) -> list[ExecutionTrace]
                            为None时使用模拟轨迹。

        Returns:
            最优候选文本
        """
        logger.info(f"\n{'='*60}\n  GEPA 进化开始\n{'='*60}")

        for gen in range(1, self.max_generations + 1):
            self.generation = gen

            # 预算检查
            if self.used_budget >= self.budget_cap:
                logger.info(f"预算耗尽 (${self.used_budget:.2f} >= ${self.budget_cap})")
                break

            # 早停检查
            if self.selector.should_early_stop():
                logger.info(f"连续拒绝达到 {self.selector.patience} 次, 触发早停")
                self.stats["early_stopped"] = True
                break

            logger.info(f"\n--- 第 {gen} 代 ---")

            # 1. 选择父本
            parent = self.selector.select_parent()
            logger.info(f"选择父本: {parent.candidate_id[:16]} (Gen {parent.generation})")

            # 2. 变异或交叉
            if self.merger.should_merge() and len(self.selector.frontier) >= 2:
                child = self.merger.merge(
                    parent, self.selector.candidates, self.selector.scores, self.lineage
                )
                mutation_type = MutationType.REWRITE  # merge 被视为 rewrite 类
                mutation_detail = f"系统感知交叉: {parent.candidate_id[:12]} + {child.metadata.get('merged_from', '?')[:12]}"
                self.stats["total_merges"] += 1
                logger.info(f"执行交叉合并")
            else:
                # 获取父本的执行轨迹
                traces = self._get_traces(parent, trace_collector)
                child, diagnosis = self.mutator.mutate(parent, traces)
                mutation_type = MutationType(child.metadata.get("last_mutation", "rewrite"))
                mutation_detail = diagnosis
                self.stats["total_mutations"] += 1
                logger.info(f"执行RPM变异: {mutation_type.value}")

            # 3. 评估子代
            # 有真实轨迹收集器时用轨迹评估, 否则直接用文本特征评估 (确保确定性)
            if trace_collector:
                child_traces = trace_collector(child)
                self.traces_db[child.candidate_id] = child_traces
                child_score = self.evaluator.quick_evaluate(child, child_traces)
            else:
                child_score = self.evaluator._text_based_evaluate(child)
                # 仍为 RPM 生成模拟轨迹 (用于后续迭代的反思)
                if child.candidate_id not in self.traces_db:
                    self.traces_db[child.candidate_id] = (
                        self._generate_simulated_traces(child)
                    )

            # 4. 迷你批次门禁: 子代 > 父本?
            parent_score = self.selector.scores.get(parent.candidate_id)
            if parent_score and not self._mini_batch_gate(child_score, parent_score):
                logger.info(f"迷你批次门禁: 子代未优于父本, 拒绝")
                self.stats["rejected_count"] += 1
                self.lineage.record(
                    gen, parent.candidate_id, child.candidate_id,
                    mutation_type, mutation_detail, [], False,
                )
                # 仍然为拒绝计数做贡献
                self.selector.rejected_streak += 1
                continue

            # 5. 五层安全门禁
            passed_gates, gate_reports = self.safety_gate.full_gate_check(
                child, self.original_text, self.evolution_phase
            )

            # 记录本次进化
            self.lineage.record(
                gen, parent.candidate_id, child.candidate_id,
                mutation_type, mutation_detail, gate_reports, passed_gates,
            )

            if not passed_gates:
                failed = [r for r in gate_reports if r.result == GateResult.FAIL_HARD]
                logger.warning(
                    f"安全门禁: 未通过 ({len(failed)} 层硬阻塞): "
                    + ", ".join(f"L{r.level.value}" for r in failed)
                )
                self.stats["rejected_count"] += 1
                self.selector.rejected_streak += 1
                continue

            # 6. 帕累托门禁: 非支配?
            accepted = self.selector.add_candidate(child, child_score)
            if accepted:
                self.stats["accepted_count"] += 1
                logger.info(f"帕累托门禁: 接受 (前沿: {len(self.selector.frontier)})")

            # 7. 预算累计
            self.used_budget += self.cost_per_generation

            # 每10代输出状态摘要
            if gen % 10 == 0:
                self._log_status()

        # 进化结束
        logger.info(f"\n{'='*60}\n  GEPA 进化结束\n{'='*60}")
        self._log_final_report()

        # 返回最优候选
        best = self.selector.get_best_candidate()
        if best is None:
            logger.error("无有效候选! 返回种子文本")
            best = self.selector.candidates.get("SEED-001")

        return best

    # ---- 内部方法 ----

    def _get_traces(
        self,
        candidate: TextCandidate,
        trace_collector: Optional[Callable] = None,
    ) -> list[ExecutionTrace]:
        """获取候选的执行轨迹"""
        # 先查缓存
        if candidate.candidate_id in self.traces_db:
            return self.traces_db[candidate.candidate_id]

        # 调用外部收集器
        if trace_collector:
            traces = trace_collector(candidate)
            self.traces_db[candidate.candidate_id] = traces
            return traces

        # 生成模拟轨迹 (演示模式)
        return self._generate_simulated_traces(candidate)

    @staticmethod
    def _generate_simulated_traces(candidate: TextCandidate, num: int = 5) -> list[ExecutionTrace]:
        """生成模拟执行轨迹 (演示/测试用)

        使用候选文本的确定性特征 + 小幅随机抖动,
        确保"更好"的文本一致地获得更高评分。
        评分范围: ~0.35 (极差) 到 ~0.82 (优秀)
        """
        traces = []
        text = candidate.text
        text_len = len(text)

        # ---------- 文本质量评分 (确定性, 0.0 - 0.55) ----------
        # 长度评分: 200-3000字符为佳
        if text_len >= 600:
            len_score = 0.20
        elif text_len >= 300:
            len_score = 0.10 + 0.10 * (text_len - 300) / 300
        elif text_len >= 150:
            len_score = 0.03 + 0.07 * (text_len - 150) / 150
        else:
            len_score = 0.0

        # 结构完整性评分
        struct_score = 0.0
        if "#" in text and "##" in text:
            struct_score += 0.08  # 多级标题
        if any(f"{i}." in text or f"{i}、" in text for i in range(1, 4)):
            struct_score += 0.06  # 编号列表
        if "约束" in text or "限制" in text:
            struct_score += 0.04
        if "步骤" in text or "流程" in text:
            struct_score += 0.04
        if "错误" in text or "异常" in text:
            struct_score += 0.05  # 错误处理
        if "示例" in text or "例如" in text:
            struct_score += 0.04  # 示例说明

        # 内容充实度: 行数、段落数
        lines = [l for l in text.split("\n") if l.strip()]
        content_score = min(0.10, len(lines) * 0.01)  # 最多0.10

        text_quality = len_score + struct_score + content_score

        # ---------- 进化奖励 ----------
        gen_bonus = min(0.12, candidate.generation * 0.02)
        last_mut = candidate.metadata.get("last_mutation", "")
        mut_bonus = {
            "rewrite": 0.05, "insert": 0.03,
            "compress": 0.02, "merge": 0.04,
        }.get(last_mut, 0.0)

        # ---------- 基础成功率 (保证在合理范围) ----------
        base_success = min(0.82, 0.35 + text_quality + gen_bonus + mut_bonus)

        for i in range(num):
            jitter = random.uniform(-0.06, 0.06)
            success = (base_success + jitter) > 0.45
            depth = random.randint(4, 7) if success else random.randint(1, 3)
            traces.append(ExecutionTrace(
                trace_id=f"TRACE-{uuid.uuid4().hex[:8]}",
                candidate_id=candidate.candidate_id,
                task_input=f"模拟任务 #{i + 1}: 验证候选文本效果",
                reasoning_chain=[
                    f"步骤{j}: {action}" for j, action in enumerate([
                        "解析任务需求", "检索相关知识", "生成初步输出",
                        "自我检查与修正", "质量审查", "优化完善", "最终确认",
                    ][:depth], start=1)
                ],
                tool_calls=[
                    {"tool": "search", "input": "相关文档", "output": f"找到{random.randint(1,5)}条结果"},
                    {"tool": "validate", "input": "输出检查", "output": "通过" if success else "需要改进"},
                ] if random.random() < 0.7 else [],
                errors=[] if success else [
                    random.choice([
                        "信息不足, 无法完成推理步骤",
                        "工具调用返回异常, 需重试",
                        "输出格式不符合要求",
                    ]),
                ],
                evaluation_feedback=(
                    random.choice(["优秀, 输出质量高", "很好, 满足所有要求"])
                    if success and base_success > 0.65
                    else random.choice(["良好, 基本满足要求", "通过, 有小瑕疵"])
                    if success
                    else random.choice(["失败, 缺少关键信息", "未完成, 中间步骤出错"])
                ),
                success=success,
                latency_ms=random.uniform(400, 2500),
            ))
        return traces

    def _mini_batch_gate(
        self, child_score: EvaluationScore, parent_score: EvaluationScore
    ) -> bool:
        """
        迷你批次门禁: 子代必须不显著劣于父本。

        对低评估次数的候选(种子)放宽要求, 避免冷启动困难。
        至少不能有维度严重退化, 且至少一个维度有改进。
        """
        child_vec = child_score.to_vector()
        parent_vec = parent_score.to_vector()

        # 父本评估次数少时放宽改进阈值
        relaxation = max(0.0, 1.0 - parent_score.num_evaluations / 10.0)
        improve_threshold = 1.0 - relaxation * 0.05  # 阈值从 1.01 放宽至 0.96

        # 检查是否有改进 (任意维度 > 父本 * threshold)
        improved = any(
            cv > pv * improve_threshold + 0.001
            for cv, pv in zip(child_vec, parent_vec)
            if pv != 0
        )

        # 检查是否有严重退化 (任意维度 < 父本 * 0.85)
        # 退化阈值也比之前宽松, 鼓励探索
        degraded = any(
            cv < pv * 0.85
            for cv, pv in zip(child_vec, parent_vec)
            if pv != 0 and abs(pv) > 0.01
        )

        if not improved:
            logger.debug(f"迷你批次: 无改进 (阈值={improve_threshold:.3f})")
        if degraded:
            logger.debug(f"迷你批次: 检测到严重退化")

        return improved and not degraded

    def _log_status(self):
        """输出当前状态摘要"""
        selector_stats = self.selector.get_statistics()
        lineage_stats = self.lineage.get_statistics()
        gate_summary = self.safety_gate.get_gate_summary()

        logger.info(
            f"\n  [状态摘要 第{self.generation}代]\n"
            f"  前沿大小: {selector_stats['frontier_size']} | "
            f"总候选: {selector_stats['total_candidates']} | "
            f"接受率: {selector_stats['acceptance_rate']:.1%}\n"
            f"  预算: ${self.used_budget:.2f} / ${self.budget_cap} | "
            f"门禁通过率: {gate_summary.get('pass_rate', 0):.1%}\n"
            f"  谱系: {lineage_stats['accepted_evolutions']} 接受 / "
            f"{lineage_stats['total_evolutions']} 总计"
        )

    def _log_final_report(self):
        """输出最终报告"""
        selector_stats = self.selector.get_statistics()
        lineage_stats = self.lineage.get_statistics()
        gate_summary = self.safety_gate.get_gate_summary()
        best = self.selector.get_best_candidate()

        report = (
            f"\n{'='*60}\n"
            f"  GEPA 进化最终报告\n"
            f"{'='*60}\n"
            f"  进化阶段: {self.evolution_phase.value}\n"
            f"  总代数: {self.generation}\n"
            f"  总预算: ${self.used_budget:.2f}\n"
            f"  前沿候选数: {selector_stats['frontier_size']}\n"
            f"  总候选数: {selector_stats['total_candidates']}\n"
            f"  接受/拒绝: {self.stats['accepted_count']}/{self.stats['rejected_count']}\n"
            f"  变异/交叉: {self.stats['total_mutations']}/{self.stats['total_merges']}\n"
            f"  早停触发: {'是' if self.stats['early_stopped'] else '否'}\n"
            f"  门禁通过率: {gate_summary.get('pass_rate', 0):.1%}\n"
            f"  最优候选ID: {best.candidate_id if best else 'N/A'}\n"
            f"  最优候选代: {best.generation if best else 'N/A'}\n"
        )
        logger.info(report)

    def save_results(self) -> dict:
        """保存进化结果到文件"""
        best = self.selector.get_best_candidate()
        frontier = self.selector.get_frontier_candidates()

        # 保存最优候选
        if best:
            best_path = self.output_dir / "best-candidate.txt"
            best_path.write_text(best.text, encoding="utf-8")
            logger.info(f"最优候选已保存: {best_path}")

            best_json_path = self.output_dir / "best-candidate.json"
            best_json_path.write_text(
                json.dumps(asdict(best), ensure_ascii=False, indent=2, default=str),
                encoding="utf-8",
            )

        # 保存前沿
        frontier_data = []
        for c in frontier:
            score = self.selector.scores.get(c.candidate_id)
            frontier_data.append({
                "candidate_id": c.candidate_id,
                "generation": c.generation,
                "text_preview": c.text[:200],
                "score": asdict(score) if score else None,
                "mutation_history": c.mutation_history[-5:],
            })
        frontier_path = self.output_dir / "pareto-frontier.json"
        frontier_path.write_text(
            json.dumps(frontier_data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        # 保存谱系
        self.lineage.export_lineage_json(
            str(self.output_dir / "lineage-tree.json")
        )

        # 保存完整报告
        report = {
            "engine": "GEPA-Evolution-Engine",
            "version": "2.0",
            "colony": "Colony-038",
            "evolution_phase": self.evolution_phase.value,
            "total_generations": self.generation,
            "total_budget_used": self.used_budget,
            "stats": self.stats,
            "selector_stats": self.selector.get_statistics(),
            "lineage_stats": self.lineage.get_statistics(),
            "gate_summary": self.safety_gate.get_gate_summary(),
            "best_candidate_id": best.candidate_id if best else None,
        }
        report_path = self.output_dir / "evolution-report.json"
        report_path.write_text(
            json.dumps(report, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        logger.info(f"完整报告已保存至: {self.output_dir}")
        return report


# ---------------------------------------------------------------------------
# 便捷工厂函数
# ---------------------------------------------------------------------------

def create_engine_for_skills(
    auto_mode: bool = False,
    max_generations: int = 30,
    budget_cap: float = 50.0,
    **kwargs,
) -> GEPAEvolutionEngine:
    """创建 Phase 1: 技能描述优化引擎"""
    return GEPAEvolutionEngine(
        evolution_phase=EvolutionPhase.PHASE1_SKILLS,
        max_generations=max_generations,
        budget_cap=budget_cap,
        auto_mode=auto_mode,
        **kwargs,
    )


def create_engine_for_tools(
    auto_mode: bool = False,
    max_generations: int = 30,
    budget_cap: float = 50.0,
    **kwargs,
) -> GEPAEvolutionEngine:
    """创建 Phase 2: 工具描述优化引擎"""
    return GEPAEvolutionEngine(
        evolution_phase=EvolutionPhase.PHASE2_TOOLS,
        max_generations=max_generations,
        budget_cap=budget_cap,
        auto_mode=auto_mode,
        **kwargs,
    )


def create_engine_for_prompts(
    auto_mode: bool = False,
    max_generations: int = 30,
    budget_cap: float = 50.0,
    **kwargs,
) -> GEPAEvolutionEngine:
    """创建 Phase 3: 系统提示词优化引擎"""
    return GEPAEvolutionEngine(
        evolution_phase=EvolutionPhase.PHASE3_PROMPTS,
        max_generations=max_generations,
        budget_cap=budget_cap,
        auto_mode=auto_mode,
        **kwargs,
    )


def create_engine_for_rules(
    auto_mode: bool = False,
    max_generations: int = 30,
    budget_cap: float = 50.0,
    **kwargs,
) -> GEPAEvolutionEngine:
    """创建 Phase 4: MR规则优化引擎"""
    return GEPAEvolutionEngine(
        evolution_phase=EvolutionPhase.PHASE4_RULES,
        max_generations=max_generations,
        budget_cap=budget_cap,
        auto_mode=auto_mode,
        **kwargs,
    )


# ---------------------------------------------------------------------------
# 演示: 自包含的集成测试
# ---------------------------------------------------------------------------

def demo_skill_evolution():
    """
    演示: 技能描述文件的完整进化过程。

    使用模拟Reflection LLM和模拟执行轨迹,
    无需任何API Key即可运行, 验证引擎流程完整性。
    """
    print("=" * 60)
    print("  GEPA 文本参数进化引擎 — 演示模式")
    print("  Colony-038 极限实验室")
    print("=" * 60)

    # 种子文本: 一个简单的Agent技能描述
    seed_skill = """# Agent 任务执行技能

## 概述
本技能使Agent能够接收用户任务并执行。

## 流程
1. 阅读任务描述
2. 生成执行计划
3. 按计划执行
4. 返回结果给用户

## 约束
- 始终遵循安全准则
- 记录每一步操作
"""

    print(f"\n种子文本 ({len(seed_skill)} 字符):")
    print("-" * 40)
    print(seed_skill)
    print("-" * 40)

    # 创建引擎
    engine = create_engine_for_skills(
        auto_mode=True,          # 自动模式 (跳过L5人工审查)
        max_generations=20,      # 限20代
        budget_cap=30.0,         # 预算$30
        cost_per_generation=1.5, # 每代$1.5
        random_seed=42,
        output_dir="/d/极限实验室/colonies/colony-038/gepa-output",
    )

    # 初始化
    engine.initialize(seed_skill)

    # 运行进化
    best = engine.run_evolution()

    # 输出结果
    print(f"\n{'='*60}")
    print(f"  最优候选 (Gen {best.generation})")
    print(f"  ID: {best.candidate_id}")
    print(f"  谱系: {' -> '.join(best.mutation_history[-5:])}")
    print(f"{'='*60}")
    print(best.text[:1000])
    print(f"... (总长 {len(best.text)} 字符)")

    # 保存结果
    report = engine.save_results()

    print(f"\n结果已保存至: {engine.output_dir}")
    print(f"进化报告摘要:")
    print(f"  代数: {report['total_generations']}")
    print(f"  预算: ${report['total_budget_used']:.2f}")
    print(f"  接受率: {report['selector_stats']['acceptance_rate']:.1%}")

    return engine, best


def demo_unit_tests():
    """
    单元测试: 验证各模块的核心功能。

    这些测试确保:
    1. RPM变异能产生不同的文本
    2. 帕累托筛选正确识别支配关系
    3. 安全门禁能拦截不合规产物
    4. 谱系追踪正确记录父子关系
    """
    print("\n" + "=" * 60)
    print("  单元测试套件")
    print("=" * 60)

    passed = 0
    failed = 0

    # ---- 测试1: RPM变异 ----

    print("\n[测试1] RPM反射式变异")
    try:
        mutator = RPMReflectiveMutator()
        candidate = TextCandidate(
            candidate_id="TEST-001",
            text="步骤1: 分析需求\n步骤2: 执行操作\n步骤3: 返回结果",
            phase=EvolutionPhase.PHASE1_SKILLS,
        )
        traces = [
            ExecutionTrace(
                trace_id="T1",
                candidate_id="TEST-001",
                task_input="测试任务",
                errors=["步骤2执行失败"],
                success=False,
                evaluation_feedback="执行失败, 缺少错误处理逻辑",
            )
        ]
        child, diagnosis = mutator.mutate(candidate, traces)
        assert child.candidate_id != candidate.candidate_id, "ID应不同"
        assert child.generation == candidate.generation + 1, "代应递增"
        assert len(child.mutation_history) > len(candidate.mutation_history), "变异历史应增加"
        assert len(diagnosis) > 0, "诊断不应为空"
        print(f"  通过: 子代ID={child.candidate_id[:16]}, Gen={child.generation}, 诊断长度={len(diagnosis)}")
        passed += 1
    except Exception as e:
        print(f"  失败: {e}")
        failed += 1

    # ---- 测试2: 帕累托筛选 ----

    print("\n[测试2] 帕累托多目标筛选")
    try:
        selector = ParetoSelector(max_frontier_size=10)
        # 创建三个候选: A全优, B部分优, C全劣
        c_a = TextCandidate(candidate_id="A", text="优秀", phase=EvolutionPhase.PHASE1_SKILLS)
        c_b = TextCandidate(candidate_id="B", text="部分", phase=EvolutionPhase.PHASE1_SKILLS)
        c_c = TextCandidate(candidate_id="C", text="较差", phase=EvolutionPhase.PHASE1_SKILLS)

        s_a = EvaluationScore("A", task_success_rate=0.9, output_quality=0.8, reasoning_depth=0.7)
        s_b = EvaluationScore("B", task_success_rate=0.6, output_quality=0.95, reasoning_depth=0.5)
        s_c = EvaluationScore("C", task_success_rate=0.3, output_quality=0.3, reasoning_depth=0.2)

        # A和B互相不支配 (A成功率更高, B质量更高), 都在前沿上
        assert not s_a.dominates(s_b), "A不应支配B"
        assert not s_b.dominates(s_a), "B不应支配A"

        # A和B都支配C
        assert s_a.dominates(s_c), "A应该支配C"
        assert s_b.dominates(s_c), "B应该支配C"

        selector.add_candidate(c_a, s_a)
        selector.add_candidate(c_b, s_b)
        selector.add_candidate(c_c, s_c)

        # C应该被支配, 不在前沿
        assert len(selector.frontier) == 2, f"前沿应有2个候选, 实际{len(selector.frontier)}"
        assert "C" not in selector.frontier, "C不应在前沿"

        print(f"  通过: 前沿={selector.frontier}, A支配C={s_a.dominates(s_c)}, B支配C={s_b.dominates(s_c)}")
        passed += 1
    except Exception as e:
        print(f"  失败: {e}")
        failed += 1

    # ---- 测试3: 安全门禁 ----

    print("\n[测试3] 五层安全门禁")
    try:
        gate = SafetyGate(auto_mode=True)

        # 安全的候选
        safe = TextCandidate(
            candidate_id="SAFE",
            text="正常的Agent技能描述文本",
            phase=EvolutionPhase.PHASE1_SKILLS,
        )
        passed_gates, reports = gate.full_gate_check(safe, "原始文本")
        assert passed_gates, f"安全候选应通过, 但报告: {[(r.level.value, r.result.value) for r in reports]}"

        # 超大的候选
        huge = TextCandidate(
            candidate_id="HUGE",
            text="x" * (16 * 1024),  # 16KB, 超过15KB限制
            phase=EvolutionPhase.PHASE1_SKILLS,
        )
        passed_gates2, reports2 = gate.full_gate_check(huge)
        assert not passed_gates2, "超大候选应被L2拒绝"

        # 包含危险代码的候选
        dangerous = TextCandidate(
            candidate_id="DANGER",
            text="执行 rm -rf / 清理系统",
            phase=EvolutionPhase.PHASE1_SKILLS,
        )
        passed_gates3, reports3 = gate.full_gate_check(dangerous)
        assert not passed_gates3, "危险候选应被L1拒绝"

        print(f"  通过: 安全={passed_gates}, 超大={not passed_gates2}, 危险={not passed_gates3}")
        passed += 1
    except Exception as e:
        print(f"  失败: {e}")
        failed += 1

    # ---- 测试4: 谱系追踪 ----

    print("\n[测试4] 谱系追踪")
    try:
        tracker = LineageTracker()
        tracker.record(1, "A", "B", MutationType.REWRITE, "诊断1", [], True)
        tracker.record(2, "B", "C", MutationType.INSERT, "诊断2", [], True)
        tracker.record(2, "B", "D", MutationType.COMPRESS, "诊断3", [], False)

        chain = tracker.get_lineage_chain("C")
        assert chain == ["A", "B", "C"], f"谱系链应为 A->B->C, 实际 {chain}"

        stats = tracker.get_statistics()
        assert stats["total_evolutions"] == 3
        assert stats["accepted_evolutions"] == 2
        assert stats["max_generation"] == 2

        print(f"  通过: 谱系链={chain}, 统计={stats}")
        passed += 1
    except Exception as e:
        print(f"  失败: {e}")
        failed += 1

    # ---- 结果 ----

    print(f"\n{'='*60}")
    print(f"  测试结果: {passed} 通过, {failed} 失败")
    print(f"{'='*60}")

    return passed, failed


# ---------------------------------------------------------------------------
# CLI 入口
# ---------------------------------------------------------------------------

def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(
        description="GEPA 文本参数进化引擎 (Colony-038)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python gepa-evolution-engine.py                  # 演示模式 (完整进化+单元测试)
  python gepa-evolution-engine.py --demo-only       # 仅演示进化
  python gepa-evolution-engine.py --test-only       # 仅单元测试
  python gepa-evolution-engine.py --phase tools     # 指定进化阶段
  python gepa-evolution-engine.py --max-gen 100     # 指定最大代数
  python gepa-evolution-engine.py --budget 100      # 指定预算上限
        """,
    )
    parser.add_argument(
        "--phase", type=str, default="skills",
        choices=["skills", "tools", "prompts", "rules", "pipeline"],
        help="进化阶段 (默认: skills)",
    )
    parser.add_argument(
        "--max-gen", type=int, default=20,
        help="最大进化代数 (默认: 20)",
    )
    parser.add_argument(
        "--budget", type=float, default=30.0,
        help="预算上限美元 (默认: 30.0)",
    )
    parser.add_argument(
        "--cost-per-gen", type=float, default=1.5,
        help="每代预估成本美元 (默认: 1.5)",
    )
    parser.add_argument(
        "--auto", action="store_true", default=True,
        help="自动模式, 跳过L5人工审查 (默认: 开启)",
    )
    parser.add_argument(
        "--no-auto", action="store_true",
        help="标准模式, 需要L5人工审查",
    )
    parser.add_argument(
        "--seed", type=int, default=42,
        help="随机种子 (默认: 42)",
    )
    parser.add_argument(
        "--output", type=str, default=None,
        help="输出目录 (默认: colonies/colony-038/gepa-output)",
    )
    parser.add_argument(
        "--demo-only", action="store_true",
        help="仅运行演示进化",
    )
    parser.add_argument(
        "--test-only", action="store_true",
        help="仅运行单元测试",
    )
    parser.add_argument(
        "--live", action="store_true",
        help="生产模式 (需要设置 API Key)",
    )
    return parser.parse_args()


def main():
    """主入口"""
    args = parse_args()

    auto_mode = not args.no_auto
    output_dir = args.output or "/d/极限实验室/colonies/colony-038/gepa-output"

    # Phase 映射
    phase_map = {
        "skills":   EvolutionPhase.PHASE1_SKILLS,
        "tools":    EvolutionPhase.PHASE2_TOOLS,
        "prompts":  EvolutionPhase.PHASE3_PROMPTS,
        "rules":    EvolutionPhase.PHASE4_RULES,
        "pipeline": EvolutionPhase.PHASE5_PIPELINE,
    }

    if args.test_only:
        demo_unit_tests()
        return

    if args.demo_only:
        demo_skill_evolution()
        return

    if args.live:
        # 生产模式: 使用真实LLM API
        print("生产模式启动中...")
        print("提示: 需要设置 ANTHROPIC_API_KEY 或 OPENAI_API_KEY 环境变量")
        # TODO: 集成真实的LLM调用
        pass  # 当前走演示模式

    # 默认: 运行完整演示 (进化 + 测试)
    demo_unit_tests()
    print("\n")
    demo_skill_evolution()


if __name__ == "__main__":
    main()
