#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Colony v2.0 — L1 固定编排框架: 四阶段Pipeline编排器
=====================================================
Colony-035 极限实验室 | 2026-05-19

设计来源: Colony-029 内生性悖论核心发现 ——
  固定编排+自主角色(Sequential) = 最优 (+44% vs Shared协议)

四阶段Pipeline:
  输入(任务) → Stage 1 情境感知 → Stage 2 方案生成 → Stage 3 执行实现 → Stage 4 质量验证 → 输出(产物)

关键约束:
  - 传递完整输出 (非摘要!) — 自愿弃权机制依赖信息完整性
  - Stage数量固定为4 (短期基线, 中期通过NeuroMAS优化为3-6)
  - 验证失败 → 仅回溯Stage 3 (不回溯Stage 1/2)
"""

import json
import sys
import time
import uuid
import logging
import hashlib
import argparse
from abc import ABC, abstractmethod
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Optional, Callable

# ──────────────────────────────────────────────────────────────────────
# 常量
# ──────────────────────────────────────────────────────────────────────

VERSION = "2.0.0"
COLONY_ID = "Colony-035"
DEFAULT_MAX_RETRY_STAGE3 = 3  # Stage 4 失败后 Stage 3 最大重试次数
DEFAULT_ABSTENTION_ALERT_THRESHOLD = 0.5  # 弃权比例 ≥ 50% 触发缺口告警
OUTPUT_ENCODING = "utf-8"

# ──────────────────────────────────────────────────────────────────────
# 日志
# ──────────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("Colony.Pipeline")


# ══════════════════════════════════════════════════════════════════════
# Section 1: 核心数据结构
# ══════════════════════════════════════════════════════════════════════


class StageID(Enum):
    """四阶段标识"""
    CONTEXT_INGESTION = 1     # 情境感知
    STRATEGY_FORMULATION = 2  # 方案生成
    EXECUTION = 3             # 执行实现
    QUALITY_VERIFICATION = 4   # 质量验证

    @property
    def label_cn(self) -> str:
        labels = {
            1: "情境感知",
            2: "方案生成",
            3: "执行实现",
            4: "质量验证",
        }
        return labels.get(self.value, f"Stage-{self.value}")


class Verdict(Enum):
    """验证结论"""
    PASS = "pass"
    FAIL = "fail"
    PASS_WITH_WARNINGS = "pass_with_warnings"
    INCONCLUSIVE = "inconclusive"


# ──────────────────────────────────────────────────────────────
# Agent 角色相关
# ──────────────────────────────────────────────────────────────


@dataclass
class RoleProposal:
    """Agent自声明的角色提案 (内生性悖论 机制A)"""
    agent_id: str
    stage_id: int
    role_name: str                         # Agent自主命名的角色, 如 "数据库迁移风险评估师"
    role_category: str = ""                # 系统自动聚类标签
    rationale: str = ""                    # 基于前置输出的角色选择理由
    contribution_plan: str = ""            # 具体可验证的产出计划
    confidence: float = 0.5               # 0.0-1.0
    abstain: bool = False                 # 是否弃权
    abstention_reason: str = ""            # 弃权理由
    dependencies: list[str] = field(default_factory=list)  # 依赖的其他Agent产出
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def __post_init__(self):
        if self.confidence < 0.0 or self.confidence > 1.0:
            raise ValueError(f"置信度必须在 [0.0, 1.0] 范围内, 当前值: {self.confidence}")


@dataclass
class AbstentionRecord:
    """弃权记录 (内生性悖论 机制B)"""
    agent_id: str
    stage_id: int
    reason: str                            # 弃权理由 (缺口信息)
    domain: str = ""                       # 弃权的任务域
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class GapAlert:
    """缺口告警: 某个任务域 ≥ 50% Agent弃权时触发"""
    stage_id: int
    domain: str                            # 缺口域
    abstention_count: int
    total_agents: int
    abstention_ratio: float
    severity: str = "warning"             # info / warning / critical
    recommendation: str = ""              # 建议: 外部干预 / 简化任务 / 调用额外资源
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


# ──────────────────────────────────────────────────────────────
# Stage 元数据与传输
# ──────────────────────────────────────────────────────────────


@dataclass
class StageMetadata:
    """Stage执行元数据"""
    stage_id: int
    started_at: str = ""
    completed_at: str = ""
    duration_ms: float = 0.0
    model_version: str = ""
    agent_count: int = 0
    abstention_count: int = 0
    token_usage: dict[str, int] = field(default_factory=dict)  # {agent_id: token_count}
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class StageOutput:
    """单个Agent在某个Stage的完整输出"""
    agent_id: str
    stage_id: int
    content: str                           # 完整输出文本 (非摘要!)
    content_hash: str = ""                 # SHA256, 用于完整性校验
    content_length: int = 0
    role: Optional[RoleProposal] = None    # 本Stage承担的角色
    format: str = "text"                   # text / json / code
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def __post_init__(self):
        if not self.content_hash:
            self.content_hash = hashlib.sha256(self.content.encode(OUTPUT_ENCODING)).hexdigest()[:16]
        if not self.content_length:
            self.content_length = len(self.content)


@dataclass
class StageTransfer:
    """
    Stage间传递的标准数据结构

    约束: 传递完整输出, 不做摘要。
    理由 (来自内生性悖论实验): 机制B(自愿弃权)依赖Agent看到的是实际产出而非意图。
    如果摘要, 信息不对称(意图vs实际产出)被抹去, Agent无法做出准确的弃权判断。
    """
    stage_id: int
    stage_label: str = ""
    stage_outputs: dict[str, StageOutput] = field(default_factory=dict)   # {agent_id: StageOutput}
    role_assignments: list[RoleProposal] = field(default_factory=list)
    abstentions: list[AbstentionRecord] = field(default_factory=list)
    gap_alerts: list[GapAlert] = field(default_factory=list)
    metadata: StageMetadata = field(default_factory=lambda: StageMetadata(stage_id=0))
    # 前驱StageTransfer引用 (流水线追踪)
    predecessor: Optional["StageTransfer"] = None

    def get_all_content(self) -> str:
        """聚合本Stage所有Agent的完整输出"""
        parts = []
        for agent_id, output in self.stage_outputs.items():
            role_info = f" [角色: {output.role.role_name}]" if output.role else ""
            parts.append(f"=== Agent: {agent_id}{role_info} ===\n{output.content}")
        return "\n\n".join(parts)

    def get_active_agents(self) -> list[str]:
        """返回未弃权的Agent列表"""
        abstained = {a.agent_id for a in self.abstentions}
        return [aid for aid in self.stage_outputs if aid not in abstained]


# ──────────────────────────────────────────────────────────────
# 任务上下文
# ──────────────────────────────────────────────────────────────


@dataclass
class TaskContext:
    """完整的任务上下文, 作为Pipeline入口"""
    task_id: str
    original_task: str                    # 用户原始任务描述
    history_context: str = ""             # 历史上下文
    environment_state: dict = field(default_factory=dict)  # 环境状态快照
    mr_rules_snapshot: list[str] = field(default_factory=list)  # 相关MR规则快照
    constraints: list[str] = field(default_factory=list)  # 约束条件
    priority: str = "normal"             # low / normal / high / critical
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    extra: dict[str, Any] = field(default_factory=dict)


# ──────────────────────────────────────────────────────────────
# Pipeline 配置与指标
# ──────────────────────────────────────────────────────────────


@dataclass
class PipelineConfig:
    """Pipeline可配置参数"""
    max_retry_stage3: int = DEFAULT_MAX_RETRY_STAGE3
    abstention_alert_threshold: float = DEFAULT_ABSTENTION_ALERT_THRESHOLD
    agent_pool: list[str] = field(default_factory=lambda: ["Agent-Alpha", "Agent-Beta", "Agent-Gamma"])
    enable_role_election: bool = True       # 启用动态角色选举
    enable_abstention: bool = True          # 启用自愿弃权
    enable_gap_detection: bool = True       # 启用缺口检测
    stage_timeout_seconds: int = 600         # 单Stage超时 (秒)
    log_level: str = "INFO"
    output_dir: str = ""                    # 产物输出目录
    agent_callable: Optional[Callable] = None  # 外部Agent调用函数 (仿真模式下为None)


@dataclass
class PipelineMetrics:
    """Pipeline执行指标"""
    pipeline_run_id: str = ""
    task_id: str = ""
    total_duration_ms: float = 0.0
    stage_durations: dict[int, float] = field(default_factory=dict)  # {stage_id: ms}
    stage3_retry_count: int = 0
    total_agent_participations: int = 0
    total_abstentions: int = 0
    total_gap_alerts: int = 0
    final_verdict: str = ""
    started_at: str = ""
    completed_at: str = ""
    success: bool = False


# ══════════════════════════════════════════════════════════════════════
# Section 2: Agent 抽象基类
# ══════════════════════════════════════════════════════════════════════


class BaseAgent(ABC):
    """
    Agent抽象基类

    每个Agent:
      1. 接收任务 + 前置Stage完整输出
      2. 自主声明角色 (RoleProposal) 或弃权
      3. 产出完整文本内容 (非摘要!)
    """

    def __init__(self, agent_id: str, capabilities: Optional[list[str]] = None):
        self.agent_id = agent_id
        self.capabilities = capabilities or []
        self.execution_history: list[dict] = []

    @abstractmethod
    def process(self, stage_id: int, task_context: TaskContext,
                prior_transfer: Optional[StageTransfer] = None) -> tuple[StageOutput, RoleProposal]:
        """
        处理当前Stage

        Returns:
            (StageOutput, RoleProposal) — 产出 + 角色声明
            若弃权, RoleProposal.abstain = True
        """
        ...

    def can_contribute(self, domain: str) -> bool:
        """检查Agent是否能贡献到指定域"""
        if not self.capabilities:
            return True  # 未声明能力时默认可以
        return any(c.lower() in domain.lower() for c in self.capabilities)

    def record_execution(self, record: dict) -> None:
        """记录执行历史"""
        self.execution_history.append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            **record,
        })


# ══════════════════════════════════════════════════════════════════════
# Section 3: 仿真Agent (演示用)
# ══════════════════════════════════════════════════════════════════════


class SimulatedAgent(BaseAgent):
    """
    仿真Agent — 用于 Pipeline 独立测试

    在真实部署中, 替换为调用 Claude API / 开源模型的 Agent 实现。
    """

    STAGE_TEMPLATES = {
        1: {
            "prefix": "## 情境感知分析\n\n### 任务理解\n对任务「{task}」的初步理解:\n- 核心目标: 识别并分析...\n- 涉及领域: {domains}\n- 复杂度评估: 中等\n\n",
            "suffix": "\n\n### 风险预警\n- 信息不对称风险: 低\n- 能力匹配度: {confidence}\n- 建议关注: 需求边界确认",
        },
        2: {
            "prefix": "## 方案生成\n\n### 基于前置情境分析的方案\n阅读了前置Stage输出的情境分析后, 提出以下方案:\n\n#### 方案概述\n- 技术路径: ...\n- 关键决策点: ...\n",
            "suffix": "\n\n### 方案对比\n| 维度 | 方案A | 方案B |\n|------|-------|-------|\n| 实现复杂度 | 中 | 低 |\n| 扩展性 | 高 | 中 |\n\n### 推荐\n方案A, 理由: ...",
        },
        3: {
            "prefix": "## 执行实现\n\n### 基于选定方案的实现\n前置方案已明确技术路径, 开始执行:\n\n```\n### 实现产物\n",
            "suffix": "\n```\n\n### 执行日志\n- 步骤1: 完成\n- 步骤2: 完成\n- 步骤3: 完成",
        },
        4: {
            "prefix": "## 质量验证报告\n\n### 验证维度\n参照原始任务「{task}」进行验证:\n\n#### 1. 功能完整性\n",
            "suffix": "\n\n#### 2. 边界条件\n- 正常输入: PASS\n- 异常输入: PASS\n- 边界值: PASS\n\n#### 3. 综合结论\n最终判定: {verdict}",
        },
    }

    def process(self, stage_id: int, task_context: TaskContext,
                prior_transfer: Optional[StageTransfer] = None) -> tuple[StageOutput, RoleProposal]:

        template = self.STAGE_TEMPLATES.get(stage_id, self.STAGE_TEMPLATES[1])
        domains = ", ".join(self.capabilities) if self.capabilities else "通用领域"

        # 生成角色
        role = self._generate_role(stage_id, task_context, prior_transfer)

        if role.abstain:
            content = f"[弃权] Agent {self.agent_id} 在本Stage弃权。理由: {role.abstention_reason}"
        else:
            content = (
                f"{template['prefix'].format(task=task_context.original_task, domains=domains)}"
                f"### Agent [{self.agent_id}] 角色: {role.role_name}\n"
                f"### 前置Stage分析\n"
                f"{self._summarize_prior(prior_transfer)}\n"
                f"{template['suffix'].format(confidence=role.confidence, verdict='PASS')}"
            )

        output = StageOutput(
            agent_id=self.agent_id,
            stage_id=stage_id,
            content=content,
        )
        output.role = role

        self.record_execution({
            "stage_id": stage_id,
            "role_name": role.role_name,
            "abstained": role.abstain,
        })

        return output, role

    def _generate_role(self, stage_id: int, task_context: TaskContext,
                       prior_transfer: Optional[StageTransfer]) -> RoleProposal:
        """生成角色提案"""
        role_templates = {
            1: ["需求分析师", "领域专家", "风险预判师", "信息收集者"],
            2: ["方案架构师", "成本估算师", "质疑者", "方案比较分析师"],
            3: ["代码实现者", "配置工程师", "测试用例编写者", "文档编写者"],
            4: ["端到端测试员", "安全审计员", "体验评审员", "回归测试员"],
        }
        import random
        templates = role_templates.get(stage_id, role_templates[1])
        idx = hash(self.agent_id + str(stage_id)) % len(templates)
        role_name = templates[idx]

        # 检查是否应弃权
        abstain = False
        abstention_reason = ""
        if stage_id == 3 and prior_transfer:
            # 仿真: 如果前置方案为空, 弃权
            if not prior_transfer.stage_outputs:
                abstain = True
                abstention_reason = f"前置Stage (Stage {prior_transfer.stage_id}) 无可用产出"

        return RoleProposal(
            agent_id=self.agent_id,
            stage_id=stage_id,
            role_name=role_name,
            rationale=f"基于任务「{task_context.original_task[:50]}...」及前置Stage输出, 选择角色 {role_name}",
            contribution_plan=f"产出 {role_name} 对应的完整分析/实现/验证",
            confidence=random.uniform(0.6, 0.95),
            abstain=abstain,
            abstention_reason=abstention_reason,
        )

    def _summarize_prior(self, prior_transfer: Optional[StageTransfer]) -> str:
        """生成前置输出的引用摘要"""
        if prior_transfer is None:
            return "(无前置Stage — 这是Pipeline初始Stage)"
        active = prior_transfer.get_active_agents()
        if not active:
            return "(前置Stage无活跃Agent产出)"
        return f"前置Stage (Stage {prior_transfer.stage_id}) 有 {len(active)} 个Agent产出, "
        f"涵盖角色: {', '.join([(prior_transfer.stage_outputs[a].role.role_name if prior_transfer.stage_outputs[a].role else '未声明') for a in active])}"


# ══════════════════════════════════════════════════════════════════════
# Section 4: Stage 抽象基类与具体实现
# ══════════════════════════════════════════════════════════════════════


class BaseStage(ABC):
    """Stage抽象基类"""

    def __init__(self, stage_id: StageID):
        self.stage_id = stage_id

    @abstractmethod
    def execute(self, agents: list[BaseAgent], task_context: TaskContext,
                prior_transfer: Optional[StageTransfer] = None,
                config: Optional[PipelineConfig] = None) -> StageTransfer:
        """执行本Stage, 返回StageTransfer"""
        ...


class ContextIngestionStage(BaseStage):
    """
    Stage 1: 情境感知 (Context Ingestion)

    输入: 用户原始任务 + 历史上下文 + 环境状态 + 相关MR规则快照
    Agent行为: 每个Agent独立阅读全部输入, 自主声明关注点和能力匹配
    输出: 多维情境分析矩阵 + 缺口标记 + 风险预警 + 角色声明集
    弃权: 允许 — 不匹配的Agent声明弃权并说明缺口
    传递格式: 完整分析文本 (非结构化摘要)
    """

    def __init__(self):
        super().__init__(StageID.CONTEXT_INGESTION)

    def execute(self, agents: list[BaseAgent], task_context: TaskContext,
                prior_transfer: Optional[StageTransfer] = None,
                config: Optional[PipelineConfig] = None) -> StageTransfer:

        logger.info(f"[Stage 1/4] 情境感知 — 任务: {task_context.original_task[:80]}...")
        cfg = config or PipelineConfig()

        metadata = StageMetadata(stage_id=self.stage_id.value)
        metadata.started_at = datetime.now(timezone.utc).isoformat()
        metadata.agent_count = len(agents)
        t_start = time.perf_counter()

        stage_outputs: dict[str, StageOutput] = {}
        role_assignments: list[RoleProposal] = []
        abstentions: list[AbstentionRecord] = []

        for agent in agents:
            output, role = agent.process(self.stage_id.value, task_context, prior_transfer)

            stage_outputs[agent.agent_id] = output
            role_assignments.append(role)

            if role.abstain:
                abstentions.append(AbstentionRecord(
                    agent_id=agent.agent_id,
                    stage_id=self.stage_id.value,
                    reason=role.abstention_reason,
                    domain=role.role_category or "通用",
                ))
                logger.info(f"  Agent [{agent.agent_id}] 弃权: {role.abstention_reason}")

        metadata.abstention_count = len(abstentions)
        metadata.completed_at = datetime.now(timezone.utc).isoformat()
        metadata.duration_ms = (time.perf_counter() - t_start) * 1000

        # 缺口检测
        gap_alerts = self._detect_gaps(abstentions, agents, cfg, self.stage_id.value)

        transfer = StageTransfer(
            stage_id=self.stage_id.value,
            stage_label=self.stage_id.label_cn,
            stage_outputs=stage_outputs,
            role_assignments=role_assignments,
            abstentions=abstentions,
            gap_alerts=gap_alerts,
            metadata=metadata,
            predecessor=prior_transfer,
        )

        logger.info(f"  Stage 1 完成: {len(stage_outputs)} Agent, "
                     f"{len(abstentions)} 弃权, {len(gap_alerts)} 缺口告警, "
                     f"耗时 {metadata.duration_ms:.0f}ms")

        return transfer

    def _detect_gaps(self, abstentions: list[AbstentionRecord],
                     agents: list[BaseAgent], config: PipelineConfig,
                     stage_id: int) -> list[GapAlert]:
        """检测缺口: 某域弃权比例 ≥ 阈值时触发告警"""
        if not config.enable_gap_detection or not abstentions:
            return []

        domain_counts: dict[str, int] = {}
        for a in abstentions:
            domain = a.domain or "未分类"
            domain_counts[domain] = domain_counts.get(domain, 0) + 1

        alerts = []
        for domain, count in domain_counts.items():
            ratio = count / len(agents)
            if ratio >= config.abstention_alert_threshold:
                alerts.append(GapAlert(
                    stage_id=stage_id,
                    domain=domain,
                    abstention_count=count,
                    total_agents=len(agents),
                    abstention_ratio=ratio,
                    severity="critical" if ratio >= 0.75 else "warning",
                    recommendation=f"域 '{domain}' 弃权率 {ratio:.0%}, 建议外部干预或补充专业Agent",
                ))
        return alerts


class StrategyFormulationStage(BaseStage):
    """
    Stage 2: 方案生成 (Strategy Formulation)

    输入: Stage 1完整输出 (所有Agent的情境分析、缺口标记、风险预警)
    Agent行为: 基于前置输出自主选择: 方案提出者/风险分析师/成本估算师/质疑者等
    输出: 多角色方案集 + 方案间对比矩阵 + 推荐排序 + 角色变迁记录
    弃权: 允许 — Agent可以声明"此方案空间超出我的能力"
    关键约束: 角色可以重置 — Agent在Stage 1是"领域专家", 在Stage 2可以变成"质疑者"
    """

    def __init__(self):
        super().__init__(StageID.STRATEGY_FORMULATION)

    def execute(self, agents: list[BaseAgent], task_context: TaskContext,
                prior_transfer: Optional[StageTransfer] = None,
                config: Optional[PipelineConfig] = None) -> StageTransfer:

        logger.info(f"[Stage 2/4] 方案生成 — 基于Stage 1情境分析")
        cfg = config or PipelineConfig()

        metadata = StageMetadata(stage_id=self.stage_id.value)
        metadata.started_at = datetime.now(timezone.utc).isoformat()
        metadata.agent_count = len(agents)
        t_start = time.perf_counter()

        stage_outputs: dict[str, StageOutput] = {}
        role_assignments: list[RoleProposal] = []
        abstentions: list[AbstentionRecord] = []

        for agent in agents:
            # 传递完整前置输出 (关键约束!)
            output, role = agent.process(self.stage_id.value, task_context, prior_transfer)

            stage_outputs[agent.agent_id] = output
            role_assignments.append(role)

            if role.abstain:
                abstentions.append(AbstentionRecord(
                    agent_id=agent.agent_id,
                    stage_id=self.stage_id.value,
                    reason=role.abstention_reason,
                    domain=role.role_category or "方案域",
                ))
                logger.info(f"  Agent [{agent.agent_id}] 弃权: {role.abstention_reason}")

        # 角色变迁追踪
        role_transitions = self._track_role_transitions(prior_transfer, role_assignments)

        metadata.abstention_count = len(abstentions)
        metadata.extra["role_transitions"] = role_transitions
        metadata.completed_at = datetime.now(timezone.utc).isoformat()
        metadata.duration_ms = (time.perf_counter() - t_start) * 1000

        gap_alerts = ContextIngestionStage()._detect_gaps(abstentions, agents, cfg, self.stage_id.value)

        transfer = StageTransfer(
            stage_id=self.stage_id.value,
            stage_label=self.stage_id.label_cn,
            stage_outputs=stage_outputs,
            role_assignments=role_assignments,
            abstentions=abstentions,
            gap_alerts=gap_alerts,
            metadata=metadata,
            predecessor=prior_transfer,
        )

        logger.info(f"  Stage 2 完成: {len(stage_outputs)} Agent, "
                     f"{len(abstentions)} 弃权, {len(role_transitions)} 次角色变迁, "
                     f"耗时 {metadata.duration_ms:.0f}ms")

        return transfer

    def _track_role_transitions(self, prior_transfer: Optional[StageTransfer],
                                current_roles: list[RoleProposal]) -> list[dict]:
        """追踪角色变迁: Agent在Stage 1的角色 vs Stage 2的角色"""
        if prior_transfer is None:
            return []

        prior_roles = {rp.agent_id: rp.role_name for rp in prior_transfer.role_assignments}
        transitions = []
        for rp in current_roles:
            prior_role = prior_roles.get(rp.agent_id)
            if prior_role and prior_role != rp.role_name:
                transitions.append({
                    "agent_id": rp.agent_id,
                    "from_role": prior_role,
                    "to_role": rp.role_name,
                })
                logger.info(f"  角色变迁: [{rp.agent_id}] {prior_role} → {rp.role_name}")
        return transitions


class ExecutionStage(BaseStage):
    """
    Stage 3: 执行实现 (Execution)

    输入: Stage 2完整输出 (所有方案文本, 含对比和推荐)
    Agent行为: 根据方案具体内容自主选择执行角色; 允许多Agent并行执行不同子任务
    输出: 实际产物 (代码/文档/配置) + 执行者角色 + 执行日志
    传递: 前置Agent的已完成产出对后续Agent可见 (不是产出计划!)
    关键约束: 内生性悖论最关键发现 — Agent必须看到"已完成的工作"而不是"工作的计划"
    """

    def __init__(self):
        super().__init__(StageID.EXECUTION)

    def execute(self, agents: list[BaseAgent], task_context: TaskContext,
                prior_transfer: Optional[StageTransfer] = None,
                config: Optional[PipelineConfig] = None) -> StageTransfer:

        logger.info(f"[Stage 3/4] 执行实现 — 基于Stage 2方案")
        cfg = config or PipelineConfig()

        metadata = StageMetadata(stage_id=self.stage_id.value)
        metadata.started_at = datetime.now(timezone.utc).isoformat()
        metadata.agent_count = len(agents)
        t_start = time.perf_counter()

        stage_outputs: dict[str, StageOutput] = {}
        role_assignments: list[RoleProposal] = []
        abstentions: list[AbstentionRecord] = []

        for agent in agents:
            output, role = agent.process(self.stage_id.value, task_context, prior_transfer)

            stage_outputs[agent.agent_id] = output
            role_assignments.append(role)

            if role.abstain:
                abstentions.append(AbstentionRecord(
                    agent_id=agent.agent_id,
                    stage_id=self.stage_id.value,
                    reason=role.abstention_reason,
                    domain=role.role_category or "执行域",
                ))
                logger.info(f"  Agent [{agent.agent_id}] 弃权: {role.abstention_reason}")

        metadata.abstention_count = len(abstentions)
        metadata.completed_at = datetime.now(timezone.utc).isoformat()
        metadata.duration_ms = (time.perf_counter() - t_start) * 1000

        gap_alerts = ContextIngestionStage()._detect_gaps(abstentions, agents, cfg, self.stage_id.value)

        transfer = StageTransfer(
            stage_id=self.stage_id.value,
            stage_label=self.stage_id.label_cn,
            stage_outputs=stage_outputs,
            role_assignments=role_assignments,
            abstentions=abstentions,
            gap_alerts=gap_alerts,
            metadata=metadata,
            predecessor=prior_transfer,
        )

        logger.info(f"  Stage 3 完成: {len(stage_outputs)} Agent, "
                     f"耗时 {metadata.duration_ms:.0f}ms")

        return transfer


class QualityVerificationStage(BaseStage):
    """
    Stage 4: 质量验证 (Quality Verification)

    输入: Stage 3完整输出 + Stage 1原始任务定义
    Agent行为: 自主选择验证角色: 端到端测试者/边界条件检查者/安全审计员/体验评审员
    输出: 多维质量报告 + 各Agent独立验证结论 + 通过/不通过判定
    失败处理: 验证失败 → 触发Stage 3局部重新执行 (不回溯到Stage 1/2)
    """

    def __init__(self):
        super().__init__(StageID.QUALITY_VERIFICATION)

    def execute(self, agents: list[BaseAgent], task_context: TaskContext,
                prior_transfer: Optional[StageTransfer] = None,
                config: Optional[PipelineConfig] = None) -> StageTransfer:

        logger.info(f"[Stage 4/4] 质量验证 — 对照Stage 1原始任务定义")
        cfg = config or PipelineConfig()

        metadata = StageMetadata(stage_id=self.stage_id.value)
        metadata.started_at = datetime.now(timezone.utc).isoformat()
        metadata.agent_count = len(agents)
        t_start = time.perf_counter()

        stage_outputs: dict[str, StageOutput] = {}
        role_assignments: list[RoleProposal] = []
        abstentions: list[AbstentionRecord] = []
        verdicts: list[Verdict] = []

        for agent in agents:
            output, role = agent.process(self.stage_id.value, task_context, prior_transfer)

            stage_outputs[agent.agent_id] = output
            role_assignments.append(role)

            if role.abstain:
                abstentions.append(AbstentionRecord(
                    agent_id=agent.agent_id,
                    stage_id=self.stage_id.value,
                    reason=role.abstention_reason,
                    domain=role.role_category or "验证域",
                ))

            # 解析验证结论
            verdict = self._parse_verdict(output.content)
            verdicts.append(verdict)
            metadata.extra[f"{agent.agent_id}_verdict"] = verdict.value

        metadata.abstention_count = len(abstentions)
        metadata.completed_at = datetime.now(timezone.utc).isoformat()
        metadata.duration_ms = (time.perf_counter() - t_start) * 1000

        # 聚合结论
        overall_verdict = self._aggregate_verdicts(verdicts)
        metadata.extra["overall_verdict"] = str(overall_verdict)

        gap_alerts = ContextIngestionStage()._detect_gaps(abstentions, agents, cfg, self.stage_id.value)

        transfer = StageTransfer(
            stage_id=self.stage_id.value,
            stage_label=self.stage_id.label_cn,
            stage_outputs=stage_outputs,
            role_assignments=role_assignments,
            abstentions=abstentions,
            gap_alerts=gap_alerts,
            metadata=metadata,
            predecessor=prior_transfer,
        )

        logger.info(f"  Stage 4 完成: 综合结论 {overall_verdict}, "
                     f"各Agent结论: {[v.value for v in verdicts]}, "
                     f"耗时 {metadata.duration_ms:.0f}ms")

        return transfer

    def _parse_verdict(self, content: str) -> Verdict:
        """从Agent输出中解析验证结论"""
        content_lower = content.lower()
        if "pass_with_warnings" in content_lower or "有条件通过" in content:
            return Verdict.PASS_WITH_WARNINGS
        if "fail" in content_lower or "不通过" in content:
            return Verdict.FAIL
        if "inconclusive" in content_lower or "无法判定" in content:
            return Verdict.INCONCLUSIVE
        return Verdict.PASS

    def _aggregate_verdicts(self, verdicts: list[Verdict]) -> str:
        """聚合多个Agent的验证结论"""
        if not verdicts:
            return "inconclusive"
        if all(v == Verdict.PASS for v in verdicts):
            return "pass"
        if any(v == Verdict.FAIL for v in verdicts):
            return "fail"
        if any(v == Verdict.PASS_WITH_WARNINGS for v in verdicts):
            return "pass_with_warnings"
        return "inconclusive"


# ══════════════════════════════════════════════════════════════════════
# Section 5: Pipeline 编排器
# ══════════════════════════════════════════════════════════════════════


class PipelineOrchestrator:
    """
    Colony v2.0 四阶段Pipeline编排器

    职责:
      1. 按序执行 Stage 1→2→3→4
      2. Stage间传递完整StageTransfer (非摘要)
      3. Stage 4 失败 → 重新执行 Stage 3 (最多 N 次)
      4. 记录全链路度量 (PipelineMetrics)
      5. 可选: 将产物持久化到 output_dir
    """

    def __init__(self, config: Optional[PipelineConfig] = None):
        self.config = config or PipelineConfig()
        self.agents: list[BaseAgent] = []
        self.stages: dict[StageID, BaseStage] = {
            StageID.CONTEXT_INGESTION: ContextIngestionStage(),
            StageID.STRATEGY_FORMULATION: StrategyFormulationStage(),
            StageID.EXECUTION: ExecutionStage(),
            StageID.QUALITY_VERIFICATION: QualityVerificationStage(),
        }
        self.metrics: Optional[PipelineMetrics] = None
        self._run_id: str = ""

    # ── Agent 管理 ──────────────────────────────────────────────

    def add_agent(self, agent: BaseAgent) -> None:
        """添加Agent到池中"""
        self.agents.append(agent)
        self.config.agent_pool = [a.agent_id for a in self.agents]

    def add_agents(self, agents: list[BaseAgent]) -> None:
        """批量添加Agent"""
        for agent in agents:
            self.add_agent(agent)

    # ── 主执行入口 ──────────────────────────────────────────────

    def run(self, task_context: TaskContext) -> tuple[list[StageTransfer], PipelineMetrics]:
        """
        执行完整四阶段Pipeline

        Args:
            task_context: 任务上下文

        Returns:
            (stage_transfers, metrics) — 全部Stage的传递记录 + 执行指标

        Raises:
            RuntimeError: Stage 3重试耗尽后仍验证失败
        """
        self._run_id = uuid.uuid4().hex[:12]
        logger.info(f"=== Pipeline Run [{self._run_id}] 开始 ===")
        logger.info(f"任务ID: {task_context.task_id}")
        logger.info(f"任务内容: {task_context.original_task[:100]}...")
        logger.info(f"Agent池: {[a.agent_id for a in self.agents]}")

        t_pipeline_start = time.perf_counter()

        metrics = PipelineMetrics(
            pipeline_run_id=self._run_id,
            task_id=task_context.task_id,
            started_at=datetime.now(timezone.utc).isoformat(),
        )

        transfers: list[StageTransfer] = []

        # ── Stage 1: 情境感知 ──
        t1 = self.stages[StageID.CONTEXT_INGESTION]
        transfer_s1 = t1.execute(self.agents, task_context, prior_transfer=None, config=self.config)
        transfers.append(transfer_s1)
        metrics.stage_durations[1] = transfer_s1.metadata.duration_ms
        if transfer_s1.gap_alerts:
            logger.warning(f"  ⚠ Stage 1 缺口告警: {len(transfer_s1.gap_alerts)} 个")

        # ── Stage 2: 方案生成 ──
        t2 = self.stages[StageID.STRATEGY_FORMULATION]
        transfer_s2 = t2.execute(self.agents, task_context, prior_transfer=transfer_s1, config=self.config)
        transfers.append(transfer_s2)
        metrics.stage_durations[2] = transfer_s2.metadata.duration_ms
        if transfer_s2.gap_alerts:
            logger.warning(f"  ⚠ Stage 2 缺口告警: {len(transfer_s2.gap_alerts)} 个")

        # ── Stage 3→4 循环 (含失败重试) ──
        transfer_s3, transfer_s4 = self._execute_stage3_4_loop(
            task_context, transfer_s2, transfer_s1, metrics
        )
        transfers.append(transfer_s3)
        transfers.append(transfer_s4)

        # ── 汇总指标 ──
        total_ms = (time.perf_counter() - t_pipeline_start) * 1000
        metrics.total_duration_ms = total_ms
        metrics.completed_at = datetime.now(timezone.utc).isoformat()
        metrics.total_agent_participations = sum(
            len(t.stage_outputs) for t in transfers
        )
        metrics.total_abstentions = sum(
            len(t.abstentions) for t in transfers
        )
        metrics.total_gap_alerts = sum(
            len(t.gap_alerts) for t in transfers
        )

        overall = transfer_s4.metadata.extra.get("overall_verdict", "inconclusive")
        metrics.final_verdict = overall
        metrics.success = overall == "pass"

        self.metrics = metrics

        logger.info(f"=== Pipeline Run [{self._run_id}] 完成 ===")
        logger.info(f"总耗时: {total_ms:.0f}ms, 综合结论: {overall}, "
                     f"重试次数: {metrics.stage3_retry_count}")
        logger.info(f"各Stage耗时: " +
                     " | ".join(f"S{sid}: {ms:.0f}ms" for sid, ms in metrics.stage_durations.items()))

        return transfers, metrics

    def _execute_stage3_4_loop(self, task_context: TaskContext,
                                transfer_s2: StageTransfer,
                                transfer_s1: StageTransfer,
                                metrics: PipelineMetrics) -> tuple[StageTransfer, StageTransfer]:
        """
        执行 Stage 3 → Stage 4 循环
        验证失败时仅回溯 Stage 3 (不回溯 Stage 1/2)

        这是内生性悖论实验的关键约束:
        - Stage 1/2 的分析和方案是稳定的上下文, 不需要因执行问题而重新分析
        - 执行问题的根因在 Stage 3, 只需重新执行即可

        Returns:
            (transfer_s3, transfer_s4) — 最后一次执行的Stage 3和Stage 4传递
        """
        max_retries = self.config.max_retry_stage3
        retry_count = 0

        while retry_count <= max_retries:
            if retry_count > 0:
                logger.info(f"  ⚠ Stage 3 重试 {retry_count}/{max_retries}")

            # Stage 3: 执行实现
            transfer_s3 = self.stages[StageID.EXECUTION].execute(
                self.agents, task_context, prior_transfer=transfer_s2, config=self.config
            )
            if retry_count == 0:
                metrics.stage_durations[3] = transfer_s3.metadata.duration_ms
            else:
                metrics.stage_durations[3] = metrics.stage_durations.get(3, 0) + transfer_s3.metadata.duration_ms

            # Stage 4: 质量验证 (输入包含 Stage 1 任务定义 + Stage 3 产物)
            transfer_s4 = self.stages[StageID.QUALITY_VERIFICATION].execute(
                self.agents,
                task_context,
                prior_transfer=transfer_s3,  # 传递 Stage 3 完整产出
                config=self.config,
            )
            if retry_count == 0:
                metrics.stage_durations[4] = transfer_s4.metadata.duration_ms
            else:
                metrics.stage_durations[4] = metrics.stage_durations.get(4, 0) + transfer_s4.metadata.duration_ms

            overall = transfer_s4.metadata.extra.get("overall_verdict", "inconclusive")

            if overall == "pass":
                metrics.stage3_retry_count = retry_count
                return transfer_s3, transfer_s4

            if overall == "pass_with_warnings":
                logger.warning(f"  Stage 4 有条件通过 ({retry_count} 次重试), 接受结果")
                metrics.stage3_retry_count = retry_count
                return transfer_s3, transfer_s4

            # fail 或 inconclusive → 重试
            logger.warning(f"  Stage 4 结论: {overall}, 将重试 Stage 3 ({retry_count + 1}/{max_retries})")
            retry_count += 1

        # 耗尽重试次数
        metrics.stage3_retry_count = retry_count - 1
        raise RuntimeError(
            f"Stage 3 重试耗尽 ({max_retries} 次), "
            f"Stage 4 最终结论仍为不通过。请人工检查任务: {task_context.task_id}"
        )

    # ── 导出 ────────────────────────────────────────────────────

    def export_report(self, transfers: list[StageTransfer],
                      metrics: PipelineMetrics,
                      output_path: str) -> None:
        """导出完整执行报告为JSON"""
        report = {
            "colony": COLONY_ID,
            "version": VERSION,
            "pipeline_run_id": metrics.pipeline_run_id,
            "metrics": asdict(metrics),
            "stages": [],
        }

        for transfer in transfers:
            stage_report = {
                "stage_id": transfer.stage_id,
                "stage_label": transfer.stage_label,
                "metadata": asdict(transfer.metadata),
                "agent_outputs": {
                    aid: {
                        "content_hash": out.content_hash,
                        "content_length": out.content_length,
                        "role": out.role.role_name if out.role else None,
                        "content_preview": out.content[:200] + "..." if len(out.content) > 200 else out.content,
                    }
                    for aid, out in transfer.stage_outputs.items()
                },
                "role_assignments": [
                    {
                        "agent_id": rp.agent_id,
                        "role_name": rp.role_name,
                        "abstain": rp.abstain,
                        "confidence": rp.confidence,
                    }
                    for rp in transfer.role_assignments
                ],
                "abstentions": [asdict(a) for a in transfer.abstentions],
                "gap_alerts": [asdict(g) for g in transfer.gap_alerts],
            }
            report["stages"].append(stage_report)

        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding=OUTPUT_ENCODING)
        logger.info(f"执行报告已导出: {path}")


# ══════════════════════════════════════════════════════════════════════
# Section 6: CLI 与演示
# ══════════════════════════════════════════════════════════════════════


def create_demo_pipeline() -> PipelineOrchestrator:
    """创建演示用Pipeline"""
    config = PipelineConfig(
        max_retry_stage3=3,
        abstention_alert_threshold=0.5,
        agent_pool=["Agent-Alpha", "Agent-Beta", "Agent-Gamma", "Agent-Delta"],
        enable_role_election=True,
        enable_abstention=True,
        enable_gap_detection=True,
        output_dir="./pipeline-output",
    )

    orchestrator = PipelineOrchestrator(config)

    # 注册仿真Agent (不同能力画像)
    agents = [
        SimulatedAgent("Agent-Alpha", capabilities=["需求分析", "架构设计", "代码实现"]),
        SimulatedAgent("Agent-Beta", capabilities=["测试验证", "安全审计", "文档编写"]),
        SimulatedAgent("Agent-Gamma", capabilities=["数据分析", "性能优化", "代码实现"]),
        SimulatedAgent("Agent-Delta", capabilities=["用户体验", "项目管理", "需求分析"]),
    ]
    orchestrator.add_agents(agents)

    return orchestrator


def run_demo(export_report: bool = True) -> None:
    """运行演示Pipeline"""
    print("=" * 70)
    print(f"  Colony v2.0 — L1 四阶段Pipeline编排器 v{VERSION}")
    print(f"  极限实验室 {COLONY_ID} | 2026-05-19")
    print("=" * 70)
    print()

    # 创建任务
    task = TaskContext(
        task_id=f"TASK-{uuid.uuid4().hex[:8]}",
        original_task="实现一个用户认证模块: 支持邮箱/密码注册登录, "
                       "JWT令牌认证, 密码加密存储(bcrypt), "
                       "登录限流(5次/分钟/IP), 会话管理",
        history_context="前期已完成数据库Schema设计和API接口规范定义",
        environment_state={"stack": "Python 3.12 + FastAPI + PostgreSQL"},
        mr_rules_snapshot=[
            "MR-001: 所有代码变更前必须通过安全门禁L1-L3",
            "MR-021: 新增API端点必须包含速率限制",
        ],
        constraints=["密码强度: 最少8位, 含大小写+数字", "JWT过期时间: 24小时"],
        priority="high",
    )

    # 创建Pipeline
    orchestrator = create_demo_pipeline()

    # 执行
    print(f"任务: {task.original_task}")
    print(f"Agent池: {orchestrator.config.agent_pool}")
    print(f"Stage 3 最大重试: {orchestrator.config.max_retry_stage3}")
    print()

    transfers, metrics = orchestrator.run(task)

    print()
    print("─" * 70)
    print("  执行结果")
    print("─" * 70)
    print(f"  综合结论: {metrics.final_verdict}")
    print(f"  成功: {'是' if metrics.success else '否'}")
    print(f"  总耗时: {metrics.total_duration_ms:.0f}ms")
    print(f"  Stage 3 重试次数: {metrics.stage3_retry_count}")
    print(f"  各Stage耗时:")
    for sid, ms in metrics.stage_durations.items():
        label = StageID(sid).label_cn
        print(f"    Stage {sid} ({label}): {ms:.0f}ms")
    print(f"  Agent参与总次数: {metrics.total_agent_participations}")
    print(f"  总弃权次数: {metrics.total_abstentions}")
    print(f"  总缺口告警: {metrics.total_gap_alerts}")
    print()

    # 打印各Stage角色分配
    for transfer in transfers:
        print(f"  Stage {transfer.stage_id} ({transfer.stage_label}):")
        for rp in transfer.role_assignments:
            status = f"弃权 ({rp.abstention_reason[:40]}...)" if rp.abstain else f"置信度 {rp.confidence:.2f}"
            print(f"    [{rp.agent_id}] → {rp.role_name} ({status})")
        if transfer.gap_alerts:
            for ga in transfer.gap_alerts:
                print(f"    ⚠ 缺口告警: {ga.domain} (弃权率 {ga.abstention_ratio:.0%}, 严重性: {ga.severity})")
        print()

    # 导出报告
    if export_report:
        output_path = Path(orchestrator.config.output_dir or "./pipeline-output") / f"report-{metrics.pipeline_run_id}.json"
        orchestrator.export_report(transfers, metrics, str(output_path))
        print(f"详细报告已导出: {output_path}")

    print("─" * 70)
    print("  Pipeline执行完成。")
    print("=" * 70)


def main():
    parser = argparse.ArgumentParser(
        description="Colony v2.0 L1 四阶段Pipeline编排器",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python pipeline-orchestrator.py                    # 运行演示
  python pipeline-orchestrator.py --task "任务描述"   # 指定任务
  python pipeline-orchestrator.py --config config.json  # 使用配置文件
  python pipeline-orchestrator.py --no-export         # 不导出报告
        """,
    )
    parser.add_argument("--task", "-t", type=str, help="任务描述")
    parser.add_argument("--config", "-c", type=str, help="Pipeline配置文件 (JSON)")
    parser.add_argument("--no-export", action="store_true", help="不导出JSON报告")
    parser.add_argument("--output-dir", "-o", type=str, default="./pipeline-output", help="报告输出目录")
    parser.add_argument("--agents", "-a", type=int, default=4, help="仿真Agent数量 (默认4)")
    parser.add_argument("--max-retry", "-r", type=int, default=3, help="Stage 3最大重试次数 (默认3)")
    parser.add_argument("--version", "-v", action="version", version=f"Colony Pipeline v{VERSION} ({COLONY_ID})")
    parser.add_argument("--verbose", action="store_true", help="详细日志 (DEBUG级别)")

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    if args.task:
        # 用户自定义任务
        task = TaskContext(
            task_id=f"TASK-{uuid.uuid4().hex[:8]}",
            original_task=args.task,
        )
        config = PipelineConfig(
            max_retry_stage3=args.max_retry,
            output_dir=args.output_dir,
            agent_pool=[f"Agent-{i+1}" for i in range(args.agents)],
        )
        orchestrator = PipelineOrchestrator(config)
        agents = [SimulatedAgent(f"Agent-{i+1}", capabilities=["通用"]) for i in range(args.agents)]
        orchestrator.add_agents(agents)

        transfers, metrics = orchestrator.run(task)

        print(f"\n结论: {metrics.final_verdict} | 耗时: {metrics.total_duration_ms:.0f}ms | 重试: {metrics.stage3_retry_count}")

        if not args.no_export:
            orchestrator.export_report(transfers, metrics,
                                       str(Path(args.output_dir) / f"report-{metrics.pipeline_run_id}.json"))
    else:
        # 运行内置演示
        run_demo(export_report=not args.no_export)


if __name__ == "__main__":
    main()
