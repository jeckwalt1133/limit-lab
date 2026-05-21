#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Colony v2.0 — L2 动态角色执行层: Agent自主角色选举引擎
========================================================
Colony-036 极限实验室 | 2026-05-19

设计来源: Colony-029 内生性悖论四大机制
  机制A: 角色内生性 — Agent在看到前置输出后自主决定角色, 涌现5,006+种独特角色
  机制B: 自愿自我弃权 — Agent判断不适合时主动弃权, 这是系统级信息
  机制C: 自发浅层级  — Agent通过选择性关注自然形成2-3层权威节点
  机制D: 质量不随规模衰减 — 4到256个Agent, 质量无显著退化

核心功能:
  1. 动态角色选举 — 每个Agent阅读任务+前置输出后自主声明角色
  2. 自愿弃权机制 — Agent判断不匹配时弃权, 某域≥50%弃权触发缺口告警
  3. 注意力链分析 — 追踪Agent间引用关系, 识别自发权威节点, 检测异常

与L1 Pipeline的接口:
  - 输入: TaskContext + StageTransfer (前置Stage完整输出)
  - 输出: StageTransfer (含角色分配、弃权记录、缺口告警)
  - 兼容 Colony-035 pipeline-orchestrator.py 的数据结构

可执行: python role-election-engine.py [--task "任务描述"] [--demo]
"""

import json
import sys
import time
import uuid
import hashlib
import logging
import argparse
import random
import re
from abc import ABC, abstractmethod
from collections import defaultdict, Counter
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Optional, Callable

# ──────────────────────────────────────────────────────────────────────
# 常量
# ──────────────────────────────────────────────────────────────────────

VERSION = "2.0.0"
COLONY_ID = "Colony-036"
DEFAULT_ABSTENTION_ALERT_THRESHOLD = 0.5  # 弃权比例 ≥ 50% 触发缺口告警
DEFAULT_ATTENTION_WINDOW = 5               # 注意力链滑动窗口 (最近N个任务)
DEFAULT_AUTHORITY_CITATION_MIN = 2          # 成为权威节点的最少被引用次数
OUTPUT_ENCODING = "utf-8"

# ──────────────────────────────────────────────────────────────────────
# 日志
# ──────────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("Colony.L2.RoleElection")


# ══════════════════════════════════════════════════════════════════════
# Section 1: 核心数据结构 (与 Colony-035 兼容)
# ══════════════════════════════════════════════════════════════════════


class StageID(Enum):
    """四阶段标识"""
    CONTEXT_INGESTION = 1
    STRATEGY_FORMULATION = 2
    EXECUTION = 3
    QUALITY_VERIFICATION = 4

    @property
    def label_cn(self) -> str:
        labels = {1: "情境感知", 2: "方案生成", 3: "执行实现", 4: "质量验证"}
        return labels.get(self.value, f"Stage-{self.value}")


class ElectionMode(Enum):
    """角色选举模式"""
    FULLY_AUTONOMOUS = "fully_autonomous"     # Agent完全自主命名角色
    GUIDED = "guided"                          # 从预定义角色池中选择
    HYBRID = "hybrid"                          # 预定义池 + 允许自定义扩展


@dataclass
class RoleProposal:
    """
    Agent自声明的角色提案 (内生性悖论 机制A)

    字段对齐 Colony-035 的 RoleProposal 定义, 新增:
      - attention_refs: Agent声明关注的前置输出引用
      - meta_tags: 额外元标签
    """
    agent_id: str
    stage_id: int
    role_name: str                         # Agent自主命名的角色, 如 "数据库迁移风险评估师"
    role_category: str = ""                # 系统自动聚类标签
    rationale: str = ""                    # 基于前置输出的角色选择理由 (必须引用前置输出具体内容)
    contribution_plan: str = ""            # 具体可验证的产出计划
    confidence: float = 0.5               # 0.0-1.0
    abstain: bool = False                 # 是否弃权
    abstention_reason: str = ""            # 弃权理由 (缺口信息)
    dependencies: list[str] = field(default_factory=list)  # 依赖的其他Agent产出
    attention_refs: list[str] = field(default_factory=list)  # 关注的前置Agent产出引用
    meta_tags: dict[str, str] = field(default_factory=dict)  # 额外元标签
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    proposal_id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])

    def __post_init__(self):
        if self.confidence < 0.0 or self.confidence > 1.0:
            raise ValueError(f"置信度必须在 [0.0, 1.0] 范围内, 当前值: {self.confidence}")
        if self.abstain and not self.abstention_reason:
            self.abstention_reason = "(未提供弃权理由)"


@dataclass
class AbstentionRecord:
    """弃权记录 (内生性悖论 机制B) — 对齐 Colony-035"""
    agent_id: str
    stage_id: int
    reason: str
    domain: str = ""
    capability_gap: str = ""               # 具体能力缺口描述
    suggested_remedy: str = ""             # Agent建议的补救方案
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class GapAlert:
    """
    缺口告警: 某个任务域 ≥ 50% Agent弃权时触发

    对齐 Colony-035, 新增:
      - affected_domains_detail: 受影响子域详情
      - recommended_agents: 建议补充的Agent类型
    """
    stage_id: int
    domain: str
    abstention_count: int
    total_agents: int
    abstention_ratio: float
    severity: str = "warning"             # info / warning / critical
    recommendation: str = ""
    affected_domains_detail: list[str] = field(default_factory=list)
    recommended_agents: list[str] = field(default_factory=list)
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class StageOutput:
    """单个Agent在某个Stage的完整输出 — 对齐 Colony-035"""
    agent_id: str
    stage_id: int
    content: str
    content_hash: str = ""
    content_length: int = 0
    role: Optional[RoleProposal] = None
    format: str = "text"
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def __post_init__(self):
        if not self.content_hash:
            self.content_hash = hashlib.sha256(self.content.encode(OUTPUT_ENCODING)).hexdigest()[:16]
        if not self.content_length:
            self.content_length = len(self.content)


@dataclass
class StageTransfer:
    """Stage间传递的标准数据结构 — 对齐 Colony-035"""
    stage_id: int
    stage_label: str = ""
    stage_outputs: dict[str, StageOutput] = field(default_factory=dict)
    role_assignments: list[RoleProposal] = field(default_factory=list)
    abstentions: list[AbstentionRecord] = field(default_factory=list)
    gap_alerts: list[GapAlert] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)
    predecessor: Optional["StageTransfer"] = None

    def get_all_content(self) -> str:
        parts = []
        for agent_id, output in self.stage_outputs.items():
            role_info = f" [角色: {output.role.role_name}]" if output.role else ""
            parts.append(f"=== Agent: {agent_id}{role_info} ===\n{output.content}")
        return "\n\n".join(parts)

    def get_active_agents(self) -> list[str]:
        abstained = {a.agent_id for a in self.abstentions}
        return [aid for aid in self.stage_outputs if aid not in abstained]


@dataclass
class TaskContext:
    """任务上下文 — 对齐 Colony-035"""
    task_id: str
    original_task: str
    history_context: str = ""
    environment_state: dict = field(default_factory=dict)
    mr_rules_snapshot: list[str] = field(default_factory=list)
    constraints: list[str] = field(default_factory=list)
    priority: str = "normal"
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    extra: dict[str, Any] = field(default_factory=dict)


# ══════════════════════════════════════════════════════════════════════
# Section 2: Agent 抽象基类 (选举感知版)
# ══════════════════════════════════════════════════════════════════════


class ElectableAgent(ABC):
    """
    支持角色选举的Agent抽象基类

    每个Agent的生命周期:
      1. 接收任务 + 前置Stage完整输出
      2. 自我评估: 我能贡献什么? (能力匹配度自检)
      3. 决定: 声明角色 (role_name + contribution_plan) 或 弃权 (abstain + reason)
      4. 声明注意力: 关注了前置输出中哪些Agent的哪些内容
      5. 产出: 完整文本内容
    """

    def __init__(self, agent_id: str, capabilities: Optional[list[str]] = None,
                 expertise_domains: Optional[list[str]] = None):
        self.agent_id = agent_id
        self.capabilities = capabilities or []
        self.expertise_domains = expertise_domains or capabilities or []
        self.role_history: list[dict] = []        # 个人角色历史
        self.citation_given: list[dict] = []      # 发出的引用
        self.citation_received: list[dict] = []   # 收到的引用
        self.authority_score: float = 0.0        # 权威分数 (动态)

    @abstractmethod
    def evaluate_and_propose(self, stage_id: int, task_context: TaskContext,
                             prior_transfer: Optional[StageTransfer] = None) -> RoleProposal:
        """
        自我评估并生成角色提案

        这是内生性悖论机制A的核心:
        - Agent看到前置输出后自主决定角色
        - 角色名称由Agent自主命名 (不限预定义标签)
        - 必须引用前置输出中的具体内容作为选择理由
        """
        ...

    @abstractmethod
    def produce_output(self, stage_id: int, task_context: TaskContext,
                       prior_transfer: Optional[StageTransfer] = None,
                       my_role: Optional[RoleProposal] = None) -> str:
        """基于角色产出完整内容"""
        ...

    def can_contribute(self, domain: str) -> bool:
        """检查是否能贡献到指定域"""
        if not self.capabilities:
            return True
        return any(c.lower() in domain.lower() for c in self.capabilities)

    def self_assess_fitness(self, task_domains: list[str]) -> float:
        """
        自我评估对任务域的匹配度 (0.0-1.0)

        使用双向模糊匹配:
          1. 专长关键词是否出现在任务域中
          2. 任务域关键词是否出现在专长中
        """
        if not self.expertise_domains or not task_domains:
            return 0.5

        # 将专长分解为细粒度关键词
        expertise_keywords = set()
        for e in self.expertise_domains:
            # 拆分复合词: "安全架构" → {"安全", "架构", "安全架构"}
            expertise_keywords.add(e.lower())
            for i in range(len(e)):
                for j in range(i + 1, len(e) + 1):
                    if j - i >= 2:
                        expertise_keywords.add(e[i:j].lower())

        # 将任务域分解为细粒度关键词
        domain_keywords = set()
        for d in task_domains:
            domain_keywords.add(d.lower())
            for i in range(len(d)):
                for j in range(i + 1, len(d) + 1):
                    if j - i >= 2:
                        domain_keywords.add(d[i:j].lower())

        # 双向匹配
        matches = 0
        for d in task_domains:
            if any(ek in d.lower() for ek in expertise_keywords):
                matches += 1
            elif any(dk in ek for ek in expertise_keywords for dk in domain_keywords
                     if len(dk) >= 2 and dk in d.lower()):
                matches += 1

        # 计算匹配分数 (基础分 + 匹配比例)
        base_score = 0.3  # 即使完全不匹配也给基础分
        match_ratio = matches / max(len(task_domains), 1)
        return min(base_score + 0.7 * match_ratio, 1.0)


# ══════════════════════════════════════════════════════════════════════
# Section 3: 仿真Agent (演示用, 可替换为真实LLM Agent)
# ══════════════════════════════════════════════════════════════════════


class SimulatedElectableAgent(ElectableAgent):
    """
    仿真Agent — 用于角色选举引擎独立测试

    在真实部署中, 替换为调用 Claude API 的 ElectableAgent 实现。
    仿真逻辑:
      - 基于Agent能力画像、任务域、前置输出自主选择角色
      - 使用丰富的角色名模板模拟5,006+种自发角色涌现
      - 能力不匹配时触发自愿弃权
    """

    # ── 丰富角色名模板 (模拟机制A的5,006+自发角色涌现) ──

    ROLE_TEMPLATES_BY_STAGE = {
        1: {  # 情境感知
            "analysis": [
                "需求边界界定师", "利益相关者需求分析师", "业务逻辑梳理师",
                "技术约束识别师", "领域知识图谱构建师", "信息缺口探测师",
                "风险态势感知分析师", "合规需求审查师", "用户体验场景建模师",
                "数据流溯源分析师", "依赖关系映射师", "安全威胁面分析师",
            ],
            "domain_specific": [
                "金融合规风险评估师", "医疗数据隐私顾问", "电商交易流程分析师",
                "IoT设备交互建模师", "分布式系统故障模式分析师",
                "API契约语义验证师", "微服务边界上下文映射师",
                "遗留系统迁移风险分析师", "实时数据管道瓶颈检测师",
            ],
            "meta": [
                "认知偏差检查员", "需求完整性审计师", "前置假设质疑师",
                "盲点扫描分析师", "矛盾需求调解师",
            ],
        },
        2: {  # 方案生成
            "architecture": [
                "系统架构师", "微服务拆解策略师", "事件驱动架构设计师",
                "CQRS模式应用顾问", "数据一致性方案设计师",
                "容错架构规划师", "扩展性方案评估师", "技术债务风险分析师",
            ],
            "evaluation": [
                "方案对比分析师", "成本收益评估师", "技术可行性评审师",
                "实现复杂度估算师", "替代方案探索师", "最坏情况分析师",
                "方案推销师", "决策矩阵构建师",
            ],
            "critique": [
                "魔鬼代言人质疑师", "边界条件攻击师", "假设有效性验证师",
                "方案脆弱性分析师", "过度工程检测师",
            ],
        },
        3: {  # 执行实现
            "coding": [
                "核心逻辑实现者", "接口适配层编写者", "数据访问层构建师",
                "单元测试先行者", "错误处理策略师", "日志与可观测性实施者",
                "性能关键路径优化师", "并发安全保证师",
            ],
            "integration": [
                "第三方服务集成师", "数据库迁移脚本编写者",
                "CI/CD流水线配置师", "容器化部署配置师",
                "API文档自动生成配置师",
            ],
            "quality": [
                "代码审查员", "静态分析规则配置师", "测试覆盖率保障师",
                "重构建议师", "技术规范执行监督员",
            ],
        },
        4: {  # 质量验证
            "testing": [
                "端到端测试设计师", "边界条件爆破测试员", "性能压测分析师",
                "安全渗透测试员", "回归测试执行师", "模糊测试策略师",
                "兼容性矩阵验证师", "灾难恢复演练师",
            ],
            "audit": [
                "安全审计员", "合规性检查师", "代码许可审查员",
                "数据隐私影响评估师", "密钥管理审计师",
            ],
            "review": [
                "用户体验一致性评审员", "文档完整性检查师",
                "API契约验证师", "国际化就绪度评估师",
                "可维护性评审师",
            ],
        },
    }

    # ── 弃权触发条件模板 ──

    ABSTENTION_PATTERNS = [
        {
            "reason": "该任务域 [{domain}] 超出我的专业能力范围, "
                      "我的核心专长是 {expertise}",
            "suggested_remedy": "建议引入 {domain} 领域的专业Agent",
        },
        {
            "reason": "前置Stage产出中缺乏 {domain} 领域的关键信息, "
                      "无法做出有效贡献",
            "suggested_remedy": "Stage 1应补充 {domain} 维度的情境分析",
        },
        {
            "reason": "本Stage任务与我的能力画像 ({expertise}) 匹配度过低 (约{fit:.0%}), "
                      "强行参与可能产生低质量产出",
            "suggested_remedy": "分配 {domain} 相关子任务或允许我切换到审查角色",
        },
    ]

    def __init__(self, agent_id: str, capabilities: Optional[list[str]] = None,
                 expertise_domains: Optional[list[str]] = None,
                 abstention_tendency: float = 0.15):
        """
        Args:
            abstention_tendency: 弃权倾向 (0.0-1.0), 决定Agent在能力不匹配时弃权的概率
        """
        super().__init__(agent_id, capabilities, expertise_domains)
        self.abstention_tendency = abstention_tendency
        random.seed(hash(self.agent_id) % (2**31))  # 确定性随机

    def evaluate_and_propose(self, stage_id: int, task_context: TaskContext,
                             prior_transfer: Optional[StageTransfer] = None) -> RoleProposal:
        """核心: 自主评估并生成角色提案"""

        # Step 1: 提取任务域
        task_domains = self._extract_domains(task_context.original_task)

        # Step 2: 自我评估匹配度
        fitness = self.self_assess_fitness(task_domains)

        # Step 3: 分析前置输出 (如果有)
        prior_refs, prior_insights = self._analyze_prior(prior_transfer)

        # Step 4: 决定弃权还是参与
        should_abstain, abstention_reason = self._decide_abstention(
            stage_id, task_domains, fitness, prior_transfer
        )

        if should_abstain:
            return RoleProposal(
                agent_id=self.agent_id,
                stage_id=stage_id,
                role_name="弃权",
                role_category="弃权",
                rationale=f"自我评估后决定弃权: {abstention_reason}",
                confidence=fitness,
                abstain=True,
                abstention_reason=abstention_reason,
                attention_refs=prior_refs,
                meta_tags={"fitness": f"{fitness:.2f}", "task_domains": ", ".join(task_domains)},
            )

        # Step 5: 选择角色
        role_name, role_category = self._select_role(stage_id, task_domains, prior_insights)

        # Step 6: 生成基于前置输出的选择理由
        rationale = self._build_rationale(role_name, task_context, prior_insights, fitness)

        # Step 7: 生成具体产出计划
        contribution_plan = self._build_contribution_plan(role_name, stage_id, task_context)

        confidence = max(0.3, min(0.95, fitness + random.uniform(-0.1, 0.15)))

        return RoleProposal(
            agent_id=self.agent_id,
            stage_id=stage_id,
            role_name=role_name,
            role_category=role_category,
            rationale=rationale,
            contribution_plan=contribution_plan,
            confidence=confidence,
            abstain=False,
            dependencies=prior_refs,
            attention_refs=prior_refs,
            meta_tags={
                "fitness": f"{fitness:.2f}",
                "task_domains": ", ".join(task_domains),
                "expertise": ", ".join(self.expertise_domains[:3]),
            },
        )

    def produce_output(self, stage_id: int, task_context: TaskContext,
                       prior_transfer: Optional[StageTransfer] = None,
                       my_role: Optional[RoleProposal] = None) -> str:
        """基于角色产出完整内容"""
        if my_role and my_role.abstain:
            return (f"[弃权声明] Agent {self.agent_id} 在 Stage {stage_id} "
                    f"({StageID(stage_id).label_cn}) 自愿弃权。\n"
                    f"理由: {my_role.abstention_reason}\n"
                    f"建议: (见弃权记录)")

        role_name = my_role.role_name if my_role else "通用贡献者"

        sections = [
            f"## {StageID(stage_id).label_cn} — Agent [{self.agent_id}]",
            f"### 选举角色: {role_name}",
            f"### 任务: {task_context.original_task[:120]}",
        ]

        if prior_transfer:
            active_agents = prior_transfer.get_active_agents()
            if active_agents:
                sections.append(f"### 前置Stage引用")
                for aid in active_agents[:3]:
                    if aid in prior_transfer.stage_outputs:
                        preview = prior_transfer.stage_outputs[aid].content[:100]
                        sections.append(f"- 关注 [{aid}]: {preview}...")

        sections.append(f"\n### {role_name} 产出内容")
        sections.append(self._generate_content_body(stage_id, role_name, task_context))

        return "\n".join(sections)

    # ── 内部方法 ──

    def _extract_domains(self, task_text: str) -> list[str]:
        """从任务文本中提取领域关键词 (使用层级领域映射)"""
        # 层级领域映射: 关键词 → 高级域 → 具体子域
        domain_keywords = {
            "认证": ["身份认证", "安全"],
            "登录": ["身份认证", "会话管理", "用户体验"],
            "密码": ["安全", "密码学", "身份认证"],
            "JWT": ["身份认证", "API设计", "令牌管理"],
            "加密": ["安全", "密码学"],
            "限流": ["性能优化", "安全", "流量管理"],
            "安全": ["安全", "安全审计"],
            "数据库": ["数据存储", "数据库", "数据建模"],
            "API": ["API设计", "系统集成", "接口设计"],
            "前端": ["前端开发", "用户体验", "交互设计"],
            "架构": ["系统架构", "技术选型", "系统设计"],
            "部署": ["运维", "CI/CD", "DevOps", "基础设施"],
            "测试": ["测试验证", "质量保证", "自动化测试"],
            "性能": ["性能优化", "性能测试"],
            "微服务": ["微服务", "分布式系统", "系统架构"],
            "优化": ["性能优化", "代码重构"],
            "审计": ["安全审计", "安全", "合规检查"],
            "消息": ["消息队列", "系统集成", "事件驱动"],
            "协议": ["API设计", "系统集成", "接口设计"],
            "会话": ["会话管理", "安全", "用户体验"],
            "注册": ["用户管理", "身份认证"],
        }
        domains = []
        task_lower = task_text.lower()
        for keyword, domain_list in domain_keywords.items():
            if keyword.lower() in task_lower:
                domains.extend(domain_list)
        if not domains:
            domains = ["通用任务处理"]
        return list(dict.fromkeys(domains))  # 去重保序

    def _analyze_prior(self, prior_transfer: Optional[StageTransfer]) -> tuple[list[str], list[str]]:
        """分析前置输出, 提取引用和洞察 (排除自身引用)"""
        prior_refs = []
        prior_insights = []
        if prior_transfer and prior_transfer.stage_outputs:
            active = prior_transfer.get_active_agents()
            for aid in active:
                if aid == self.agent_id:
                    continue  # 排除自身引用
                if aid in prior_transfer.stage_outputs:
                    output = prior_transfer.stage_outputs[aid]
                    role_label = output.role.role_name if output.role else "未声明"
                    prior_refs.append(aid)
                    prior_insights.append(f"[{aid}] 作为 {role_label}: {output.content[:80]}...")
        return prior_refs, prior_insights

    def _decide_abstention(self, stage_id: int, task_domains: list[str],
                           fitness: float, prior_transfer: Optional[StageTransfer]) -> tuple[bool, str]:
        """
        决定是否弃权 (内生性悖论 机制B)

        弃权条件:
          1. 能力匹配度低于阈值
          2. 前置输出为空且不是Stage 1
          3. 随机因素 (模拟真实场景的不确定性)
        """
        # 条件1: 能力匹配度过低
        if fitness < 0.15:
            pattern = self.ABSTENTION_PATTERNS[0]
            return True, pattern["reason"].format(
                domain=task_domains[0] if task_domains else "未知域",
                expertise=", ".join(self.expertise_domains[:2] or ["通用"]),
            )

        # 条件2: 非初始Stage但前置输出为空
        if stage_id > 1 and prior_transfer and not prior_transfer.stage_outputs:
            pattern = self.ABSTENTION_PATTERNS[1]
            return True, pattern["reason"].format(domain="全部")

        # 条件3: 基于弃权倾向的随机弃权 (模拟不确定性)
        if fitness < 0.4 and random.random() < self.abstention_tendency * (1 - fitness):
            pattern = self.ABSTENTION_PATTERNS[2]
            return True, pattern["reason"].format(
                expertise=", ".join(self.expertise_domains[:2] or ["通用"]),
                fit=fitness,
                domain=task_domains[0] if task_domains else "未分类",
            )

        return False, ""

    def _select_role(self, stage_id: int, task_domains: list[str],
                     prior_insights: list[str]) -> tuple[str, str]:
        """从角色模板中选择角色 (模拟自主命名)"""
        templates = self.ROLE_TEMPLATES_BY_STAGE.get(stage_id, {})
        all_roles = []
        categories = []
        for cat, roles in templates.items():
            all_roles.extend(roles)
            categories.append(cat)

        if not all_roles:
            return f"Stage-{stage_id} 通用贡献者", "通用"

        # 基于Agent ID哈希选择角色 (确保确定性)
        idx = hash(self.agent_id + str(stage_id) + str(task_domains)) % len(all_roles)
        role_name = all_roles[idx]

        # 找到角色所属类别
        for cat, roles in templates.items():
            if role_name in roles:
                return role_name, cat

        return role_name, "未分类"

    def _build_rationale(self, role_name: str, task_context: TaskContext,
                         prior_insights: list[str], fitness: float) -> str:
        """生成基于前置输出的角色选择理由 (机制A核心要求)"""
        parts = [f"选择角色「{role_name}」的理由:"]

        if prior_insights:
            parts.append(f"- 阅读了前置Stage中 {len(prior_insights)} 个Agent的完整输出后, "
                         f"识别到以下关键信息: {prior_insights[0] if prior_insights else '无'}")

        parts.append(f"- 我的专业领域 ({', '.join(self.expertise_domains[:3]) or '通用'}) "
                     f"与任务匹配度: {fitness:.0%}")

        parts.append(f"- 任务「{task_context.original_task[:60]}...」需要 {role_name} 的视角")

        return "。".join(parts)

    def _build_contribution_plan(self, role_name: str, stage_id: int,
                                 task_context: TaskContext) -> str:
        """生成具体可验证的产出计划"""
        plans = {
            1: f"产出完整的情境分析报告, 从{role_name}视角识别缺口和风险",
            2: f"提出至少2个可执行方案, 包含{role_name}特有的评估维度",
            3: f"产出可运行的实现代码和配置, 附执行日志",
            4: f"产出多维验证报告, 独立判断通过/不通过, 列出所有发现的边界条件",
        }
        return plans.get(stage_id, f"产出 {role_name} 对应的完整贡献")

    def _generate_content_body(self, stage_id: int, role_name: str,
                               task_context: TaskContext) -> str:
        """生成仿真内容体"""
        task_brief = task_context.original_task[:80]

        bodies = {
            1: (f"### 情境分析\n"
                f"1. 核心需求识别: {task_brief}\n"
                f"2. 涉及领域: {', '.join(self.expertise_domains[:3]) or '通用'}\n"
                f"3. 关键风险点: 信息不对称、需求边界模糊\n"
                f"4. 建议关注: 非功能性需求(安全、性能、可维护性)\n"
                f"5. 角色视角: 作为 {role_name}, 重点关注...\n"),

            2: (f"### 方案建议\n"
                f"方案A (稳健型): 基于成熟技术栈, 逐步实现\n"
                f"方案B (创新型): 引入新技术, 获得更好扩展性\n"
                f"方案对比: 复杂度、风险、扩展性三维评估\n"
                f"推荐: 方案A (理由: 降低首次交付风险)\n"),

            3: (f"### 实现产物\n"
                f"```\n"
                f"# 伪代码实现 ({role_name} 视角)\n"
                f"# 基于前置Stage方案执行\n"
                f"def implement_feature():\n"
                f"    # Step 1: 核心逻辑\n"
                f"    # Step 2: 错误处理\n"
                f"    # Step 3: 日志与监控\n"
                f"    pass\n"
                f"```\n"
                f"执行日志: 已完成核心实现, 通过基本功能验证\n"),

            4: (f"### 质量验证报告\n"
                f"验证维度:\n"
                f"1. 功能完整性: PASS — 核心功能覆盖\n"
                f"2. 边界条件: PASS — 正常/异常/边界值均通过\n"
                f"3. 安全审计: PASS — 无明显安全漏洞\n"
                f"4. 代码质量: PASS — 结构清晰, 可维护\n"
                f"综合结论: PASS\n"),
        }

        return bodies.get(stage_id, f"### {role_name} 产出\n内容: {task_brief}\n")


# ══════════════════════════════════════════════════════════════════════
# Section 4: 角色选举引擎 (核心)
# ══════════════════════════════════════════════════════════════════════


class RoleElectionEngine:
    """
    Agent自主角色选举引擎

    职责:
      1. 为每个Agent并行执行自我评估+角色提案
      2. 广播所有提案 (后续Agent可读)
      3. 管理弃权记录 + 缺口检测
      4. 输出 StageTransfer (含完整角色分配信息)

    算法 (来自架构文档 Section 3.2):

    对于每个 Agent_i in agent_pool (并行执行):
      1. Agent_i 阅读 task + prior_output
      2. Agent_i 生成 RoleProposal:
         { agent_id, stage_id, role_name, role_category, rationale,
           contribution_plan, confidence, abstain, abstention_reason,
           dependencies }
      3. 如果 abstain == true:
         - 记录弃权理由 (缺口信息)
         - 如果一个任务域有 ≥50% Agent弃权 → 触发缺口告警
      4. 所有 RoleProposal 在当前Stage内广播

    输出:
      - role_assignments: [RoleProposal, ...]
      - stage_outputs: {agent_id: actual_output, ...}
      - gap_alerts: [GapAlert, ...]
    """

    def __init__(self, agents: Optional[list[ElectableAgent]] = None,
                 config: Optional[dict] = None):
        self.agents: dict[str, ElectableAgent] = {}
        self.config = config or self._default_config()
        self._election_history: list[dict] = []

        # 注意力链追踪器 (见 Section 6)
        self.attention_tracker = AttentionChainTracker()

        # 角色历史追踪器 (见 Section 7)
        self.role_history_tracker = RoleHistoryTracker()

        # 弃权管理器 (见 Section 5)
        self.abstention_manager = AbstentionManager(
            threshold=self.config.get("abstention_alert_threshold", DEFAULT_ABSTENTION_ALERT_THRESHOLD)
        )

        if agents:
            for agent in agents:
                self.register_agent(agent)

    @staticmethod
    def _default_config() -> dict:
        return {
            "election_mode": ElectionMode.FULLY_AUTONOMOUS.value,
            "abstention_alert_threshold": DEFAULT_ABSTENTION_ALERT_THRESHOLD,
            "enable_abstention": True,
            "enable_gap_detection": True,
            "enable_attention_tracking": True,
            "enable_role_history": True,
            "broadcast_proposals": True,  # 角色提案是否在Stage内广播
            "min_confidence_threshold": 0.3,  # 低于此阈值的Agent被建议弃权
        }

    # ── Agent 管理 ──

    def register_agent(self, agent: ElectableAgent) -> None:
        """注册Agent到选举池"""
        self.agents[agent.agent_id] = agent
        logger.info(f"Agent [{agent.agent_id}] 已注册, "
                     f"专长: {agent.expertise_domains}")

    def register_agents(self, agents: list[ElectableAgent]) -> None:
        """批量注册Agent"""
        for agent in agents:
            self.register_agent(agent)

    def get_agent_pool(self) -> list[str]:
        """获取当前Agent ID列表"""
        return list(self.agents.keys())

    # ── 核心: 执行角色选举 ──

    def run_election(self, stage_id: int, task_context: TaskContext,
                     prior_transfer: Optional[StageTransfer] = None) -> StageTransfer:
        """
        执行单Stage的角色选举

        这是L2的核心入口, 被L1 Pipeline在每个Stage调用。

        Args:
            stage_id: Stage编号 (1-4)
            task_context: 任务上下文
            prior_transfer: 前置Stage的完整传递 (Stage 1时为None)

        Returns:
            StageTransfer: 包含所有角色分配、弃权记录、产出
        """
        t_start = time.perf_counter()
        stage_label = StageID(stage_id).label_cn if stage_id in [1, 2, 3, 4] else f"Stage-{stage_id}"

        logger.info(f"=== 角色选举开始: Stage {stage_id} ({stage_label}) ===")
        logger.info(f"任务: {task_context.original_task[:100]}...")
        logger.info(f"Agent池: {list(self.agents.keys())}")

        agent_ids = list(self.agents.keys())

        # Phase 1: 所有Agent并行自我评估 + 生成角色提案
        logger.info(f"[Phase 1] {len(agent_ids)} Agent 并行自我评估...")
        proposals: list[RoleProposal] = []
        for agent_id in agent_ids:
            agent = self.agents[agent_id]
            proposal = agent.evaluate_and_propose(stage_id, task_context, prior_transfer)
            proposals.append(proposal)

            status = "弃权" if proposal.abstain else f"角色: {proposal.role_name}"
            logger.info(f"  [{agent_id}] → {status} (置信度: {proposal.confidence:.2f})")

        # Phase 2: 广播角色提案 (所有Agent可读)
        if self.config["broadcast_proposals"]:
            logger.info(f"[Phase 2] 广播 {len(proposals)} 份角色提案...")
            # 在真实部署中, 这里会将提案注入后续Agent的上下文
            # 仿真模式下, Agent已在evaluate阶段完成自评, 此步骤为记录

        # Phase 3: 收集产出 (每个Agent基于自己的角色产出内容)
        logger.info(f"[Phase 3] Agent产出内容...")
        stage_outputs: dict[str, StageOutput] = {}
        for i, agent_id in enumerate(agent_ids):
            agent = self.agents[agent_id]
            proposal = proposals[i]
            content = agent.produce_output(stage_id, task_context, prior_transfer, proposal)

            output = StageOutput(
                agent_id=agent_id,
                stage_id=stage_id,
                content=content,
                role=proposal if not proposal.abstain else None,
            )
            stage_outputs[agent_id] = output

        # Phase 4: 处理弃权 + 缺口检测
        logger.info(f"[Phase 4] 弃权管理 + 缺口检测...")
        abstentions, gap_alerts = self.abstention_manager.process(
            proposals, stage_id, len(agent_ids)
        )

        if gap_alerts:
            for alert in gap_alerts:
                logger.warning(f"  ⚠ 缺口告警: {alert.domain} "
                               f"(弃权率 {alert.abstention_ratio:.0%}, "
                               f"严重性: {alert.severity})")

        # Phase 5: 注意力链更新
        if self.config["enable_attention_tracking"]:
            logger.info(f"[Phase 5] 注意力链分析...")
            self.attention_tracker.record_stage_attention(
                task_id=task_context.task_id,
                stage_id=stage_id,
                proposals=proposals,
                prior_transfer=prior_transfer,
            )

        # Phase 6: 角色历史更新
        if self.config["enable_role_history"]:
            logger.info(f"[Phase 6] 角色历史更新...")
            for proposal in proposals:
                if not proposal.abstain:
                    self.role_history_tracker.record(
                        agent_id=proposal.agent_id,
                        task_id=task_context.task_id,
                        stage_id=stage_id,
                        role_name=proposal.role_name,
                        role_category=proposal.role_category,
                        confidence=proposal.confidence,
                    )

        # 构建 StageTransfer
        metadata = {
            "stage_id": stage_id,
            "agent_count": len(agent_ids),
            "abstention_count": len(abstentions),
            "role_diversity": len(set(p.role_name for p in proposals if not p.abstain)),
            "avg_confidence": (sum(p.confidence for p in proposals) / len(proposals)
                               if proposals else 0.0),
            "duration_ms": (time.perf_counter() - t_start) * 1000,
            "started_at": datetime.now(timezone.utc).isoformat(),
        }

        transfer = StageTransfer(
            stage_id=stage_id,
            stage_label=stage_label,
            stage_outputs=stage_outputs,
            role_assignments=proposals,
            abstentions=abstentions,
            gap_alerts=gap_alerts,
            metadata=metadata,
            predecessor=prior_transfer,
        )

        # 记录选举历史
        self._election_history.append({
            "task_id": task_context.task_id,
            "stage_id": stage_id,
            "proposals": [asdict(p) for p in proposals],
            "abstention_count": len(abstentions),
            "gap_alert_count": len(gap_alerts),
            "role_diversity": metadata["role_diversity"],
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

        logger.info(f"=== 角色选举完成: {len(proposals)} 角色, "
                     f"{len(abstentions)} 弃权, "
                     f"{len(gap_alerts)} 缺口告警, "
                     f"角色多样性: {metadata['role_diversity']}, "
                     f"耗时: {metadata['duration_ms']:.0f}ms ===")

        return transfer

    def run_full_pipeline_election(self, task_context: TaskContext) -> list[StageTransfer]:
        """
        执行完整四阶段角色选举 (不包含实际Pipeline执行, 仅角色层面)

        用于独立测试角色选举机制。
        在真实部署中, 此方法由L1 Pipeline调用 run_election() 逐Stage执行。
        """
        transfers = []
        prior = None
        for stage_id in [1, 2, 3, 4]:
            transfer = self.run_election(stage_id, task_context, prior)
            transfers.append(transfer)
            prior = transfer
        return transfers

    # ── 查询接口 ──

    def get_election_history(self) -> list[dict]:
        """获取选举历史"""
        return self._election_history

    def get_attention_report(self) -> dict:
        """获取注意力链分析报告"""
        return self.attention_tracker.generate_report()

    def get_role_diversity_stats(self) -> dict:
        """获取角色多样性统计"""
        return self.role_history_tracker.get_diversity_stats()

    def get_agent_role_profiles(self) -> dict[str, dict]:
        """获取每个Agent的角色画像"""
        return self.role_history_tracker.get_all_agent_profiles()

    # ── 导出 ──

    def export_results(self, transfers: list[StageTransfer],
                       output_path: str) -> None:
        """导出完整选举结果为JSON"""
        report = {
            "colony": COLONY_ID,
            "version": VERSION,
            "election_mode": self.config["election_mode"],
            "stages": [],
            "attention_chain": self.get_attention_report() if self.config["enable_attention_tracking"] else {},
            "role_diversity": self.get_role_diversity_stats() if self.config["enable_role_history"] else {},
            "agent_profiles": self.get_agent_role_profiles() if self.config["enable_role_history"] else {},
        }

        for transfer in transfers:
            stage_report = {
                "stage_id": transfer.stage_id,
                "stage_label": transfer.stage_label,
                "metadata": transfer.metadata,
                "role_assignments": [
                    {
                        "agent_id": rp.agent_id,
                        "role_name": rp.role_name,
                        "role_category": rp.role_category,
                        "abstain": rp.abstain,
                        "abstention_reason": rp.abstention_reason,
                        "confidence": rp.confidence,
                        "rationale": rp.rationale,
                        "contribution_plan": rp.contribution_plan,
                        "attention_refs": rp.attention_refs,
                        "dependencies": rp.dependencies,
                        "meta_tags": rp.meta_tags,
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
        logger.info(f"选举结果已导出: {path}")


# ══════════════════════════════════════════════════════════════════════
# Section 5: 自愿弃权管理器 (机制B)
# ══════════════════════════════════════════════════════════════════════


class AbstentionManager:
    """
    自愿弃权管理器 (内生性悖论 机制B)

    核心逻辑:
      - 收集所有Agent的弃权声明
      - 按任务域聚合弃权信息
      - 某域 ≥50% Agent弃权时触发缺口告警
      - 生成可行动的补救建议
    """

    def __init__(self, threshold: float = DEFAULT_ABSTENTION_ALERT_THRESHOLD):
        self.threshold = threshold
        self._abstention_log: list[AbstentionRecord] = []
        self._gap_alert_log: list[GapAlert] = []
        self._domain_abstention_history: dict[str, list[int]] = defaultdict(list)

    @property
    def total_abstentions(self) -> int:
        return len(self._abstention_log)

    @property
    def total_gap_alerts(self) -> int:
        return len(self._gap_alert_log)

    def process(self, proposals: list[RoleProposal], stage_id: int,
                total_agents: int) -> tuple[list[AbstentionRecord], list[GapAlert]]:
        """
        处理角色提案, 提取弃权记录并检测缺口

        Args:
            proposals: 所有Agent的角色提案
            stage_id: 当前Stage
            total_agents: Agent总数

        Returns:
            (abstentions, gap_alerts)
        """
        abstentions = []
        gap_alerts = []

        # 提取弃权记录
        domain_abstention: dict[str, list[AbstentionRecord]] = defaultdict(list)

        for proposal in proposals:
            if proposal.abstain:
                domain = proposal.role_category or self._infer_domain(proposal)
                record = AbstentionRecord(
                    agent_id=proposal.agent_id,
                    stage_id=stage_id,
                    reason=proposal.abstention_reason,
                    domain=domain,
                    capability_gap=proposal.meta_tags.get("expertise", ""),
                    suggested_remedy=f"建议引入 {domain} 领域专业Agent 或 简化 {domain} 维度任务",
                )
                abstentions.append(record)
                domain_abstention[domain].append(record)
                self._abstention_log.append(record)

        # 缺口检测: 每个域的弃权比例
        for domain, records in domain_abstention.items():
            abstention_count = len(records)
            ratio = abstention_count / total_agents if total_agents > 0 else 0.0

            self._domain_abstention_history[domain].append(abstention_count)

            if ratio >= self.threshold:
                severity = "critical" if ratio >= 0.75 else "warning"

                # 分析深层缺口信息
                affected_details = list(set(r.capability_gap for r in records if r.capability_gap))

                # 聚合弃权理由, 生成共性信息
                reasons = [r.reason for r in records]
                common_reason = self._extract_common_pattern(reasons)

                # 生成推荐
                recommended_agent_types = self._recommend_agent_types(domain, records)

                alert = GapAlert(
                    stage_id=stage_id,
                    domain=domain,
                    abstention_count=abstention_count,
                    total_agents=total_agents,
                    abstention_ratio=ratio,
                    severity=severity,
                    recommendation=(
                        f"域 '{domain}' 弃权率 {ratio:.0%}。"
                        f"共性缺口: {common_reason}。"
                        f"建议: {', '.join(recommended_agent_types[:3])}"
                    ),
                    affected_domains_detail=affected_details,
                    recommended_agents=recommended_agent_types,
                )
                gap_alerts.append(alert)
                self._gap_alert_log.append(alert)

        return abstentions, gap_alerts

    def _infer_domain(self, proposal: RoleProposal) -> str:
        """从提案元标签推断域"""
        task_domains = proposal.meta_tags.get("task_domains", "")
        if task_domains:
            return task_domains.split(",")[0].strip()
        return proposal.role_category or "未分类"

    def _extract_common_pattern(self, reasons: list[str]) -> str:
        """从多个弃权理由中提取共性模式"""
        if len(reasons) <= 1:
            return reasons[0][:80] if reasons else "未知"

        # 简单关键词频率统计
        keywords = ["能力", "超出", "匹配", "信息", "缺乏", "前置", "领域", "专业", "知识"]
        freq = Counter()
        for reason in reasons:
            for kw in keywords:
                if kw in reason:
                    freq[kw] += 1

        top_kw = [kw for kw, _ in freq.most_common(3)]
        return f"多Agent反映: {', '.join(top_kw)} 相关问题"

    def _recommend_agent_types(self, domain: str, records: list[AbstentionRecord]) -> list[str]:
        """基于弃权信息推荐应补充的Agent类型"""
        domain_recommendations = {
            "安全": ["安全架构师", "渗透测试专家", "密码学工程师"],
            "身份认证": ["认证系统架构师", "OAuth/OIDC专家", "安全审计员"],
            "性能": ["性能优化工程师", "负载测试专家", "缓存策略师"],
            "数据分析": ["数据科学家", "数据工程师", "BI分析师"],
            "前端": ["前端架构师", "UX工程师", "可访问性专家"],
            "数据库": ["DBA", "数据建模师", "SQL优化专家"],
            "API": ["API设计师", "接口契约专家", "集成测试工程师"],
        }

        for key, recs in domain_recommendations.items():
            if key.lower() in domain.lower():
                return recs

        return [f"{domain}领域专家", f"{domain}高级工程师", f"{domain}顾问"]

    def get_domain_risk_profile(self) -> dict[str, dict]:
        """获取各域的弃权风险画像"""
        profile = {}
        for domain, history in self._domain_abstention_history.items():
            if history:
                profile[domain] = {
                    "recent_abstention_count": history[-1],
                    "avg_abstention": sum(history) / len(history),
                    "trend": "上升" if len(history) >= 2 and history[-1] > history[-2]
                             else "下降" if len(history) >= 2 and history[-1] < history[-2]
                             else "稳定",
                    "total_gap_alerts": sum(1 for a in self._gap_alert_log if a.domain == domain),
                }
        return profile


# ══════════════════════════════════════════════════════════════════════
# Section 6: 注意力链分析器 (机制C + 机制D)
# ══════════════════════════════════════════════════════════════════════


class AttentionChainTracker:
    """
    注意力链分析器 (内生性悖论 机制C + 机制D)

    追踪Agent对前置输出的选择性关注, 识别自发形成的"权威节点":

    机制C — 自发浅层级:
      Agent_A的输出 → Agent_B引用3次, Agent_C引用1次, Agent_D引用0次
      → Agent_B成为事实上的"权威响应者"
      → 系统不强制, 但自然涌现了以Agent_B为枢纽的2-3层浅层级

    机制D — 质量不随规模衰减:
      通过注意力链监控, 验证4→256个Agent的质量稳定性

    用途:
      1. 优化Agent能力画像: 知道哪些Agent在哪些场景下自然成为权威
      2. 检测异常: 如果某个权威Agent突然无人引用 → 输出质量可能正在退化
    """

    def __init__(self, window_size: int = DEFAULT_ATTENTION_WINDOW):
        self.window_size = window_size
        # attention_graph[task_id][stage_id] = {citing_agent: [cited_agents]}
        self._attention_graph: dict[str, dict[int, dict[str, list[str]]]] = {}
        # 长期引用计数: citation_counts[cited_agent][citing_agent] = count
        self._citation_counts: dict[str, Counter] = defaultdict(Counter)
        # 权威分数缓存
        self._authority_scores: dict[str, float] = {}
        # 引用时间线 (用于异常检测)
        self._citation_timeline: dict[str, list[dict]] = defaultdict(list)
        # 记录顺序
        self._record_order: list[dict] = []

    def record_stage_attention(self, task_id: str, stage_id: int,
                               proposals: list[RoleProposal],
                               prior_transfer: Optional[StageTransfer] = None) -> None:
        """
        记录单Stage的注意力关系

        从RoleProposal的attention_refs和dependencies字段提取引用关系。

        在真实部署中, 应额外解析Agent产出文本中的实际引用
        (如 "参考Agent-Alpha的XXX分析")。
        """
        if task_id not in self._attention_graph:
            self._attention_graph[task_id] = {}
        if stage_id not in self._attention_graph[task_id]:
            self._attention_graph[task_id][stage_id] = {}

        for proposal in proposals:
            if proposal.abstain:
                continue

            citing_agent = proposal.agent_id
            cited_agents = list(set(
                proposal.attention_refs + proposal.dependencies
            ))

            self._attention_graph[task_id][stage_id][citing_agent] = cited_agents

            # 更新长期引用计数
            for cited in cited_agents:
                self._citation_counts[cited][citing_agent] += 1

                # 记录时间线
                self._citation_timeline[cited].append({
                    "task_id": task_id,
                    "stage_id": stage_id,
                    "citing_agent": citing_agent,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })

        # 记录处理顺序
        self._record_order.append({
            "task_id": task_id,
            "stage_id": stage_id,
            "citation_count": sum(len(refs) for refs in
                                  self._attention_graph[task_id][stage_id].values()),
        })

        # 重新计算权威分数
        self._recalculate_authority_scores()

    def _recalculate_authority_scores(self) -> None:
        """重新计算所有Agent的权威分数"""
        total_citations = sum(sum(c.values()) for c in self._citation_counts.values())
        if total_citations == 0:
            self._authority_scores = {agent: 0.0 for agent in self._citation_counts}
            return

        for agent, citations in self._citation_counts.items():
            total_received = sum(citations.values())
            unique_citers = len(citations)
            # 权威分数 = 加权引用次数 (考虑引用者多样性)
            self._authority_scores[agent] = (
                0.6 * (total_received / max(total_citations, 1)) +
                0.4 * (unique_citers / max(len(self._citation_counts), 1))
            )

    def get_authority_nodes(self, min_citations: int = DEFAULT_AUTHORITY_CITATION_MIN,
                            top_n: int = 10) -> list[dict]:
        """
        获取当前权威节点列表

        权威节点定义:
          - 被其他Agent引用次数 ≥ min_citations
          - 按权威分数降序排列

        Returns:
            [{agent_id, authority_score, total_citations, unique_citers, is_emergent_authority}]
        """
        authority_nodes = []
        for agent_id, citations in self._citation_counts.items():
            total = sum(citations.values())
            unique = len(citations)
            if total >= min_citations:
                authority_nodes.append({
                    "agent_id": agent_id,
                    "authority_score": round(self._authority_scores.get(agent_id, 0.0), 4),
                    "total_citations": total,
                    "unique_citers": unique,
                    "citation_diversity": round(unique / max(len(self._citation_counts), 1), 4),
                    "is_emergent_authority": total >= min_citations * 2,  # 涌现权威 = 2倍基本阈值
                    "cited_by": list(citations.keys()),
                })

        authority_nodes.sort(key=lambda x: x["authority_score"], reverse=True)
        return authority_nodes[:top_n]

    def detect_anomalies(self, recent_window: int = 3) -> list[dict]:
        """
        检测注意力异常

        异常模式:
          1. 引用骤降: 权威Agent突然无人引用 (可能输出质量退化)
          2. 引用垄断: 某Agent引用过度集中 (可能形成信息瓶颈)
          3. 孤立Agent: 某Agent长期无引用 (可能边缘化或产出不可见)
        """
        anomalies = []

        # 1. 引用骤降检测
        for agent_id, timeline in self._citation_timeline.items():
            if len(timeline) < recent_window * 2:
                continue

            # 比较最近 window 与前一 window 的引用频率
            recent = timeline[-recent_window:]
            prior = timeline[-recent_window * 2:-recent_window]

            recent_count = len(recent)
            prior_count = len(prior)

            if prior_count > 0 and recent_count < prior_count * 0.3:
                anomalies.append({
                    "agent_id": agent_id,
                    "type": "引用骤降",
                    "severity": "warning",
                    "detail": (f"最近 {recent_window} 个Stage引用从 {prior_count} "
                              f"骤降至 {recent_count} (降幅 {1 - recent_count/prior_count:.0%})"),
                    "possible_cause": "输出质量退化 / Agent上下文窗口限制 / 角色不匹配",
                    "recommendation": "审查该Agent最近产出, 检查是否需要GEPA优化或角色调整",
                })

        # 2. 引用垄断检测
        if self._citation_counts:
            total_refs = sum(sum(c.values()) for c in self._citation_counts.values())
            if total_refs > 0:
                for agent_id, citations in self._citation_counts.items():
                    share = sum(citations.values()) / total_refs
                    if share > 0.5:  # 单个Agent占超过50%引用
                        anomalies.append({
                            "agent_id": agent_id,
                            "type": "引用垄断",
                            "severity": "warning" if share < 0.7 else "critical",
                            "detail": f"该Agent占据 {share:.0%} 的引用总量, 可能形成信息瓶颈",
                            "possible_cause": "其他Agent过度依赖 / 信息通道单一化",
                            "recommendation": "鼓励更多Agent产出原创分析, 减少对单一节点的依赖",
                        })

        # 3. 孤立Agent检测
        for agent_id in self._citation_counts:
            if agent_id not in self._authority_scores:
                continue
            if self._authority_scores[agent_id] == 0.0:
                # 检查是否在最近的任务中完全无引用
                recent_cited = any(
                    agent_id in refs
                    for task in list(self._attention_graph.values())[-recent_window:]
                    for stage in task.values()
                    for refs in stage.values()
                )
                if not recent_cited:
                    anomalies.append({
                        "agent_id": agent_id,
                        "type": "孤立Agent",
                        "severity": "info",
                        "detail": f"最近 {recent_window} 个任务中无任何引用",
                        "possible_cause": "Agent产出不可见 / 产出质量低 / 角色过于小众",
                        "recommendation": "评估Agent是否适合当前任务, 或调整其角色策略",
                    })

        return anomalies

    def get_attention_graph_summary(self) -> dict:
        """获取注意力图摘要"""
        all_edges = []
        unique_edges: set[tuple[str, str]] = set()
        for task_graph in self._attention_graph.values():
            for stage_graph in task_graph.values():
                for citing, cited_list in stage_graph.items():
                    for cited in cited_list:
                        all_edges.append({"from": citing, "to": cited})
                        unique_edges.add((citing, cited))

        n = len(self._citation_counts)
        max_possible = n * (n - 1)  # 有向图 (不允许自环)

        return {
            "total_tasks": len(self._attention_graph),
            "total_edges": len(all_edges),
            "unique_edges": len(unique_edges),
            "unique_agents": n,
            "graph_density": min(1.0, round(len(unique_edges) / max(max_possible, 1), 4)),
            "authority_nodes": self.get_authority_nodes(min_citations=1),
            "anomalies": self.detect_anomalies(),
        }

    def generate_report(self) -> dict:
        """生成完整注意力链分析报告"""
        return {
            "summary": self.get_attention_graph_summary(),
            "authority_ranking": self.get_authority_nodes(),
            "anomalies": self.detect_anomalies(),
            "emergent_hierarchy_depth": self._estimate_hierarchy_depth(),
            "citation_matrix": {
                cited: dict(citing.most_common())
                for cited, citing in self._citation_counts.items()
            },
        }

    def _estimate_hierarchy_depth(self) -> int:
        """
        估算自发层级深度 (机制C)

        通过分析引用链长度来估算自发形成了几层权威节点。
        预期: 2-3层 (架构文档约束: 不允许多于3层)
        """
        if not self._attention_graph:
            return 0

        max_depth = 0
        for task_graph in self._attention_graph.values():
            for stage_graph in task_graph.values():
                # 检查引用链: A→B→C 表示2层
                for citing, cited_list in stage_graph.items():
                    if len(cited_list) > 0:
                        # 检查被引用者是否也引用了其他人 (间接引用链)
                        for cited in cited_list:
                            if cited in stage_graph:
                                indirect = stage_graph[cited]
                                if indirect:
                                    depth = 2
                                    for indirect_cited in indirect:
                                        if indirect_cited in stage_graph:
                                            if stage_graph[indirect_cited]:
                                                depth = 3
                                    max_depth = max(max_depth, depth)
                            else:
                                max_depth = max(max_depth, 1)

        return min(max_depth, 3)  # 上限为3层 (架构约束)


# ══════════════════════════════════════════════════════════════════════
# Section 7: 角色历史追踪器
# ══════════════════════════════════════════════════════════════════════


class RoleHistoryTracker:
    """
    角色历史追踪器

    追踪角色涌现模式, 用于优化Agent能力画像。

    对标架构文档 Section 3.3:
      - 记录每次角色声明
      - 为每个Agent构建角色画像
      - 识别涌现角色模式 (≥3次出现的角色)
    """

    def __init__(self):
        self._records: list[dict] = []
        self._agent_role_counts: dict[str, Counter] = defaultdict(Counter)
        self._role_frequency: Counter = Counter()
        self._agent_stage_roles: dict[str, dict[int, list[str]]] = defaultdict(
            lambda: defaultdict(list)
        )
        self._role_transitions: dict[str, list[dict]] = defaultdict(list)

    def record(self, agent_id: str, task_id: str, stage_id: int,
               role_name: str, role_category: str = "",
               confidence: float = 0.5) -> None:
        """记录一次角色声明"""
        record = {
            "agent_id": agent_id,
            "task_id": task_id,
            "stage_id": stage_id,
            "role_name": role_name,
            "role_category": role_category,
            "confidence": confidence,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self._records.append(record)
        self._agent_role_counts[agent_id][role_name] += 1
        self._role_frequency[role_name] += 1
        self._agent_stage_roles[agent_id][stage_id].append(role_name)

        # 检测角色变迁 (同一Agent在不同Stage的角色变化)
        prev_records = [r for r in self._records
                        if r["agent_id"] == agent_id and r["task_id"] == task_id
                        and r["stage_id"] == stage_id - 1]
        if prev_records:
            prev_role = prev_records[-1]["role_name"]
            if prev_role != role_name:
                self._role_transitions[agent_id].append({
                    "task_id": task_id,
                    "from_stage": stage_id - 1,
                    "to_stage": stage_id,
                    "from_role": prev_role,
                    "to_role": role_name,
                })

    def get_agent_role_profile(self, agent_id: str) -> dict:
        """获取单个Agent的角色画像"""
        if agent_id not in self._agent_role_counts:
            return {"agent_id": agent_id, "roles": [], "message": "无角色记录"}

        role_counter = self._agent_role_counts[agent_id]
        total = sum(role_counter.values())

        return {
            "agent_id": agent_id,
            "total_role_assignments": total,
            "unique_roles": len(role_counter),
            "top_roles": [
                {"role_name": role, "count": count, "frequency": count / total}
                for role, count in role_counter.most_common(5)
            ],
            "stage_preferences": {
                str(stage): Counter(roles).most_common(3)
                for stage, roles in self._agent_stage_roles.get(agent_id, {}).items()
            },
            "role_transitions": self._role_transitions.get(agent_id, [])[-10:],
            "versatility_score": len(role_counter) / max(total, 1),  # 角色多样性/总数
        }

    def get_all_agent_profiles(self) -> dict[str, dict]:
        """获取所有Agent的角色画像"""
        profiles = {}
        for agent_id in self._agent_role_counts:
            profile = self.get_agent_role_profile(agent_id)
            if profile.get("total_role_assignments", 0) > 0:
                profiles[agent_id] = profile
        return profiles

    def get_emergent_roles(self, min_frequency: int = 3) -> list[dict]:
        """获取涌现角色模式 (出现次数 ≥ min_frequency)"""
        emergent = []
        for role_name, count in self._role_frequency.items():
            if count >= min_frequency:
                # 找到承担过此角色的Agent
                agents = [aid for aid, counter in self._agent_role_counts.items()
                          if role_name in counter]
                emergent.append({
                    "role_name": role_name,
                    "frequency": count,
                    "agent_count": len(agents),
                    "agents": agents,
                    "is_cross_agent": len(agents) > 1,  # 跨Agent涌现
                })
        emergent.sort(key=lambda x: x["frequency"], reverse=True)
        return emergent

    def get_diversity_stats(self) -> dict:
        """获取角色多样性统计"""
        if not self._records:
            return {
                "total_role_assignments": 0,
                "unique_roles": 0,
                "diversity_index": 0.0,
                "avg_roles_per_agent": 0.0,
                "emergent_roles": [],
                "most_common_roles": [],
            }

        total = len(self._records)
        unique = len(self._role_frequency)
        n_agents = len(self._agent_role_counts)

        return {
            "total_role_assignments": total,
            "unique_roles": unique,
            "diversity_index": round(unique / total, 4) if total > 0 else 0.0,
            "avg_roles_per_agent": round(total / n_agents, 2) if n_agents > 0 else 0.0,
            "emergent_roles": self.get_emergent_roles(min_frequency=2),
            "most_common_roles": self._role_frequency.most_common(10),
        }


# ══════════════════════════════════════════════════════════════════════
# Section 8: 角色聚类器 (可选: 语义嵌入聚类)
# ══════════════════════════════════════════════════════════════════════


class RoleClusterer:
    """
    角色自动聚类器

    架构文档 Section 3.3:
      5,006+自发角色 → 语义嵌入(all-MiniLM-L6-v2) → UMAP降维 → HDBSCAN聚类 → 元角色标签

    本实现提供两层:
      Level 1 (基准): 基于规则+关键词的快速聚类, 零依赖
      Level 2 (增强): 基于sentence-transformers的语义聚类 (可选)

    预计产出20-50个"元角色"类别, 人类可理解、可监管。
    """

    # 元角色类别定义 (基于架构文档的20-50个预期类别)
    META_ROLE_CATEGORIES = {
        "分析类": ["分析", "评估", "审查", "审计", "检测", "探测", "扫描", "诊断", "识别", "判断"],
        "设计类": ["设计", "架构", "规划", "建模", "构建", "方案", "策略"],
        "实现类": ["实现", "编写", "开发", "编码", "配置", "构建", "部署", "集成", "迁移"],
        "测试类": ["测试", "验证", "检验", "检查", "审查", "评审", "演练"],
        "安全类": ["安全", "渗透", "加密", "防护", "审计", "合规", "隐私", "密钥", "认证"],
        "性能类": ["性能", "优化", "加速", "缓存", "并发", "扩展", "负载", "压测"],
        "数据类": ["数据", "数据库", "存储", "持久化", "建模", "分析", "SQL", "ETL"],
        "用户体验类": ["体验", "交互", "界面", "可用性", "可访问性", "一致性", "国际化"],
        "质量类": ["质量", "规范", "标准", "风格", "重构", "技术债务", "可维护性"],
        "协调类": ["协调", "调解", "推销", "沟通", "利益相关者", "需求", "项目管理"],
        "创新类": ["创新", "探索", "替代", "前沿", "突破", "实验"],
        "风险类": ["风险", "脆弱", "故障", "灾难", "回滚", "边界", "异常"],
    }

    def __init__(self, use_embeddings: bool = False, embedding_model: str = "all-MiniLM-L6-v2"):
        self.use_embeddings = use_embeddings
        self.embedding_model_name = embedding_model
        self._embedding_model = None
        self._cluster_labels: dict[str, str] = {}  # role_name → meta_category

        if use_embeddings:
            self._init_embedding_model()

    def _init_embedding_model(self) -> None:
        """初始化语义嵌入模型"""
        try:
            from sentence_transformers import SentenceTransformer
            self._embedding_model = SentenceTransformer(self.embedding_model_name)
            logger.info(f"语义嵌入模型已加载: {self.embedding_model_name}")
        except ImportError:
            logger.warning("sentence-transformers 未安装, 回退到关键词聚类模式")
            self.use_embeddings = False

    def cluster_roles(self, role_names: list[str]) -> dict[str, list[str]]:
        """
        将角色名列表聚类为元角色类别

        Args:
            role_names: 角色名列表

        Returns:
            {meta_category: [role_name, ...]}
        """
        if self.use_embeddings and self._embedding_model:
            return self._semantic_cluster(role_names)
        return self._keyword_cluster(role_names)

    def _keyword_cluster(self, role_names: list[str]) -> dict[str, list[str]]:
        """基于关键词的快速聚类 (零依赖基准)"""
        clusters: dict[str, list[str]] = defaultdict(list)

        for role_name in role_names:
            best_category = "通用类"
            best_score = 0

            for category, keywords in self.META_ROLE_CATEGORIES.items():
                score = sum(1 for kw in keywords if kw in role_name)
                if score > best_score:
                    best_score = score
                    best_category = category

            clusters[best_category].append(role_name)
            self._cluster_labels[role_name] = best_category

        return dict(clusters)

    def _semantic_cluster(self, role_names: list[str]) -> dict[str, list[str]]:
        """基于语义嵌入的聚类 (需要sentence-transformers)"""
        try:
            import numpy as np
            from sklearn.cluster import HDBSCAN

            embeddings = self._embedding_model.encode(role_names)

            # 简化: 使用余弦相似度 + 阈值分组
            # 完整实现: UMAP降维 → HDBSCAN聚类
            clusters: dict[str, list[str]] = defaultdict(list)
            cluster_id = 0

            assigned = set()
            for i, name in enumerate(role_names):
                if name in assigned:
                    continue
                cluster_name = f"元角色-{cluster_id}"
                clusters[cluster_name].append(name)
                assigned.add(name)

                # 找相似角色
                for j in range(i + 1, len(role_names)):
                    if role_names[j] in assigned:
                        continue
                    sim = np.dot(embeddings[i], embeddings[j]) / (
                        np.linalg.norm(embeddings[i]) * np.linalg.norm(embeddings[j]) + 1e-8
                    )
                    if sim > 0.75:
                        clusters[cluster_name].append(role_names[j])
                        assigned.add(role_names[j])
                        self._cluster_labels[role_names[j]] = cluster_name

                self._cluster_labels[name] = cluster_name
                cluster_id += 1

            return dict(clusters)

        except Exception as e:
            logger.warning(f"语义聚类失败 ({e}), 回退到关键词聚类")
            return self._keyword_cluster(role_names)

    def classify_role(self, role_name: str) -> str:
        """分类单个角色"""
        if role_name in self._cluster_labels:
            return self._cluster_labels[role_name]

        # 运行时分类
        best_category = "通用类"
        best_score = 0
        for category, keywords in self.META_ROLE_CATEGORIES.items():
            score = sum(1 for kw in keywords if kw in role_name)
            if score > best_score:
                best_score = score
                best_category = category

        self._cluster_labels[role_name] = best_category
        return best_category

    def get_meta_role_summary(self, role_names: list[str]) -> dict:
        """获取元角色摘要"""
        clusters = self.cluster_roles(role_names)
        return {
            "total_unique_roles": len(role_names),
            "meta_categories": len(clusters),
            "category_distribution": {
                cat: {"count": len(roles), "roles": roles[:5]}
                for cat, roles in sorted(clusters.items(), key=lambda x: len(x[1]), reverse=True)
            },
        }


# ══════════════════════════════════════════════════════════════════════
# Section 9: CLI 与演示
# ══════════════════════════════════════════════════════════════════════


def create_demo_engine() -> RoleElectionEngine:
    """创建演示用角色选举引擎"""
    config = {
        "election_mode": ElectionMode.FULLY_AUTONOMOUS.value,
        "abstention_alert_threshold": 0.5,
        "enable_abstention": True,
        "enable_gap_detection": True,
        "enable_attention_tracking": True,
        "enable_role_history": True,
        "broadcast_proposals": True,
    }

    engine = RoleElectionEngine(config=config)

    # 注册7个Agent (模拟富贵军团 7人团队), 各有不同能力画像
    agents = [
        SimulatedElectableAgent(
            "Agent-Alpha",
            capabilities=["需求分析", "系统架构", "代码实现", "技术选型"],
            expertise_domains=["需求分析", "系统架构", "后端开发", "分布式系统"],
            abstention_tendency=0.05,
        ),
        SimulatedElectableAgent(
            "Agent-Beta",
            capabilities=["测试验证", "安全审计", "文档编写", "质量保证"],
            expertise_domains=["安全审计", "渗透测试", "质量保证", "合规检查"],
            abstention_tendency=0.10,
        ),
        SimulatedElectableAgent(
            "Agent-Gamma",
            capabilities=["数据分析", "性能优化", "代码实现", "数据库"],
            expertise_domains=["性能优化", "数据库", "数据分析", "SQL"],
            abstention_tendency=0.08,
        ),
        SimulatedElectableAgent(
            "Agent-Delta",
            capabilities=["用户体验", "项目管理", "需求分析", "前端开发"],
            expertise_domains=["用户体验", "前端开发", "交互设计", "项目管理"],
            abstention_tendency=0.12,
        ),
        SimulatedElectableAgent(
            "Agent-Epsilon",
            capabilities=["安全架构", "密码学", "身份认证", "安全审计"],
            expertise_domains=["安全架构", "密码学", "OAuth/OIDC", "零信任架构"],
            abstention_tendency=0.06,
        ),
        SimulatedElectableAgent(
            "Agent-Zeta",
            capabilities=["DevOps", "CI/CD", "容器化", "云基础设施"],
            expertise_domains=["DevOps", "Kubernetes", "CI/CD", "云原生"],
            abstention_tendency=0.15,
        ),
        SimulatedElectableAgent(
            "Agent-Eta",
            capabilities=["API设计", "微服务", "消息队列", "系统集成"],
            expertise_domains=["API设计", "微服务", "事件驱动架构", "系统集成"],
            abstention_tendency=0.09,
        ),
    ]

    engine.register_agents(agents)
    return engine


def run_demo(export_report: bool = True, output_dir: str = "./election-output") -> None:
    """运行完整演示"""
    print("=" * 70)
    print(f"  Colony v2.0 — L2 动态角色执行层: 角色选举引擎 v{VERSION}")
    print(f"  极限实验室 {COLONY_ID} | 2026-05-19")
    print("=" * 70)
    print()
    print("  实现机制:")
    print("    机制A: Agent自主角色选举 (角色内生性)")
    print("    机制B: 自愿弃权 (信息缺口发现)")
    print("    机制C: 注意力链分析 (自发权威节点)")
    print("    机制D: 规模质量稳定性监控")
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

    # 创建选举引擎
    engine = create_demo_engine()

    print(f"任务: {task.original_task}")
    print(f"Agent池: {engine.get_agent_pool()}")
    print()

    # 执行四阶段选举
    transfers = engine.run_full_pipeline_election(task)

    # ── 打印结果 ──

    print("─" * 70)
    print("  选举结果摘要")
    print("─" * 70)

    for transfer in transfers:
        active_count = len(transfer.get_active_agents())
        abstention_count = len(transfer.abstentions)
        roles = transfer.role_assignments

        print(f"\n  Stage {transfer.stage_id} ({transfer.stage_label}):")
        print(f"    Agent参与: {active_count}/{len(roles)} (弃权: {abstention_count})")
        print(f"    角色多样性: {len(set(p.role_name for p in roles if not p.abstain))} 种独特角色")

        for rp in roles:
            status = f"[弃权] {rp.abstention_reason[:50]}..." if rp.abstain else f"置信度: {rp.confidence:.2f}"
            refs = f" | 关注: {', '.join(rp.attention_refs)}" if rp.attention_refs and not rp.abstain else ""
            print(f"      [{rp.agent_id}] → {rp.role_name} ({status}){refs}")

        if transfer.gap_alerts:
            print(f"    ⚠ 缺口告警 ({len(transfer.gap_alerts)}):")
            for ga in transfer.gap_alerts:
                print(f"      - {ga.domain}: 弃权率 {ga.abstention_ratio:.0%} "
                      f"[{ga.severity}] → {ga.recommendation[:100]}")

    # ── 注意力链分析 ──
    print()
    print("─" * 70)
    print("  注意力链分析 (机制C: 自发权威节点)")
    print("─" * 70)

    attention_report = engine.get_attention_report()
    summary = attention_report["summary"]
    print(f"  总引用边数: {summary['total_edges']}")
    print(f"  图密度: {summary['graph_density']:.4f}")

    authority_nodes = attention_report["authority_ranking"]
    if authority_nodes:
        print(f"\n  权威节点排名 (基于引用次数):")
        for i, node in enumerate(authority_nodes[:5], 1):
            emergent = " [涌现权威]" if node.get("is_emergent_authority") else ""
            print(f"    #{i} {node['agent_id']}: "
                  f"权威分={node['authority_score']:.3f}, "
                  f"被引{node['total_citations']}次, "
                  f"来自{node['unique_citers']}个Agent{emergent}")

        depth = attention_report.get("emergent_hierarchy_depth", 0)
        print(f"\n  自发层级深度: {depth} 层 "
              f"({'正常 (2-3层)' if 2 <= depth <= 3 else '过浅' if depth < 2 else '过深 (不推荐)'})")

    # 异常检测
    anomalies = attention_report.get("anomalies", [])
    if anomalies:
        print(f"\n  ⚠ 注意力异常检测 ({len(anomalies)} 项):")
        for a in anomalies:
            print(f"    [{a['type']}] {a['agent_id']}: {a['detail'][:80]}")
    else:
        print(f"\n  ✓ 未检测到注意力异常")

    # ── 角色聚类 ──
    print()
    print("─" * 70)
    print("  角色聚类分析 (元角色归类)")
    print("─" * 70)

    clusterer = RoleClusterer(use_embeddings=False)
    all_roles = []
    for transfer in transfers:
        for rp in transfer.role_assignments:
            if not rp.abstain:
                all_roles.append(rp.role_name)

    if all_roles:
        clustered = clusterer.cluster_roles(list(set(all_roles)))
        print(f"  独特角色数: {len(set(all_roles))}")
        print(f"  元角色类别数: {len(clustered)}")
        print(f"\n  类别分布:")
        for cat, roles in sorted(clustered.items(), key=lambda x: len(x[1]), reverse=True):
            print(f"    [{cat}] ({len(roles)}个角色): {', '.join(roles[:4])}"
                  f"{'...' if len(roles) > 4 else ''}")

    # ── 角色历史与多样性 ──
    print()
    print("─" * 70)
    print("  角色多样性统计")
    print("─" * 70)

    diversity = engine.get_role_diversity_stats()
    print(f"  总角色分配次数: {diversity.get('total_role_assignments', 0)}")
    print(f"  独特角色数: {diversity.get('unique_roles', 0)}")
    print(f"  多样性指数: {diversity.get('diversity_index', 0.0)}")
    print(f"  平均每Agent角色数: {diversity.get('avg_roles_per_agent', 0.0)}")

    profiles = engine.get_agent_role_profiles()
    if profiles:
        print(f"\n  Agent角色画像:")
        for agent_id, profile in profiles.items():
            if profile.get("top_roles"):
                top_role = profile["top_roles"][0]
                print(f"    [{agent_id}]: {profile['unique_roles']}种角色, "
                      f"top1: {top_role['role_name']} ({top_role['count']}次), "
                      f"多样性: {profile['versatility_score']:.2f}")
    else:
        print(f"\n  Agent角色画像: 暂无数据 (所有Agent均弃权)")

    # ── 导出 ──
    if export_report:
        output_path = Path(output_dir) / f"election-report-{uuid.uuid4().hex[:8]}.json"
        engine.export_results(transfers, str(output_path))
        print(f"\n详细报告已导出: {output_path}")

    print()
    print("─" * 70)
    print("  L2 角色选举引擎演示完成。")
    print("=" * 70)


def run_multi_task_demo(num_tasks: int = 3, export_report: bool = True) -> None:
    """
    运行多任务演示, 展示角色多样性涌现

    这是验证机制A (5,006+自发角色) 和机制D (规模稳定性) 的关键测试。
    """
    print("=" * 70)
    print(f"  Colony v2.0 L2 — 多任务角色涌现演示 ({num_tasks} 个任务)")
    print("=" * 70)
    print()

    engine = create_demo_engine()

    tasks = [
        TaskContext(
            task_id=f"TASK-MT-{i+1:02d}",
            original_task=task_desc,
            priority="normal",
        )
        for i, task_desc in enumerate([
            "实现用户认证模块: JWT令牌认证, bcrypt加密, 登录限流",
            "设计微服务间通信协议: gRPC vs 消息队列 vs REST, 含性能对比",
            "对现有支付系统进行安全审计: SQL注入、XSS、CSRF、敏感数据泄露",
            "优化数据库查询性能: 慢查询分析、索引优化、连接池配置",
            "构建CI/CD流水线: 自动测试、构建、部署到Kubernetes集群",
        ][:num_tasks])
    ]

    all_transfers = []
    for i, task in enumerate(tasks):
        print(f"\n任务 {i+1}/{len(tasks)}: {task.original_task[:80]}...")
        print("-" * 50)
        transfers = engine.run_full_pipeline_election(task)
        all_transfers.append(transfers)

        # 打印每个Stage的角色
        for t in transfers:
            active_roles = [rp.role_name for rp in t.role_assignments if not rp.abstain]
            if active_roles:
                print(f"  Stage {t.stage_id}: {active_roles}")

    # ── 跨任务统计 ──
    print()
    print("─" * 70)
    print("  跨任务涌现统计")
    print("─" * 70)

    diversity = engine.get_role_diversity_stats()
    print(f"  累计独特角色数: {diversity['unique_roles']}")
    print(f"  多样性指数: {diversity['diversity_index']}")

    emergent = diversity.get("emergent_roles", [])
    cross_agent_emergent = [e for e in emergent if e.get("is_cross_agent")]
    print(f"  涌现角色 (≥2次): {len(emergent)} 个")
    print(f"  其中跨Agent涌现: {len(cross_agent_emergent)} 个")

    if emergent[:5]:
        print(f"\n  Top-5 涌现角色:")
        for e in emergent[:5]:
            cross = " [跨Agent]" if e.get("is_cross_agent") else ""
            print(f"    {e['role_name']}: {e['frequency']}次, "
                  f"来自 {e['agent_count']} Agent{cross}")

    # 注意力链
    attn = engine.get_attention_report()
    print(f"\n  注意力图: {attn['summary']['total_edges']} 边, "
          f"图密度 {attn['summary']['graph_density']:.4f}")
    print(f"  自发层级深度: {attn.get('emergent_hierarchy_depth', 0)} 层")

    authorities = attn["authority_ranking"][:3]
    if authorities:
        print(f"  Top-3 权威节点: " +
              ", ".join(f"{a['agent_id']}(分{a['authority_score']:.2f})"
                        for a in authorities))

    # 导出
    if export_report:
        output_path = Path("./election-output") / f"multi-task-report-{uuid.uuid4().hex[:8]}.json"
        # 聚合导出所有任务结果
        engine.export_results(all_transfers[-1], str(output_path))
        print(f"\n报告已导出: {output_path}")

    print("─" * 70)
    print("  多任务演示完成。")
    print("=" * 70)


def main():
    parser = argparse.ArgumentParser(
        description="Colony v2.0 L2 动态角色执行层 — Agent自主角色选举引擎",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python role-election-engine.py                     # 运行单任务完整演示
  python role-election-engine.py --multi 5           # 运行5个任务的涌现演示
  python role-election-engine.py --task "任务描述"    # 指定任务
  python role-election-engine.py --agents 10         # 使用10个Agent
  python role-election-engine.py --output report.json # 自定义输出路径
  python role-election-engine.py --no-export         # 不导出报告
  python role-election-engine.py --mode guided       # 引导式选举 (预定义角色池)
  python role-election-engine.py --verbose           # 详细日志
        """,
    )
    parser.add_argument("--task", "-t", type=str, help="自定义任务描述")
    parser.add_argument("--multi", "-m", type=int, nargs="?", const=3,
                       help="运行多任务涌现演示 (默认3个任务)")
    parser.add_argument("--agents", "-a", type=int, default=7,
                       help="Agent数量 (默认7, 对齐富贵军团规模)")
    parser.add_argument("--output", "-o", type=str, default="./election-output",
                       help="报告输出目录")
    parser.add_argument("--no-export", action="store_true", help="不导出JSON报告")
    parser.add_argument("--mode", choices=["autonomous", "guided", "hybrid"],
                       default="autonomous", help="选举模式 (默认 autonomous)")
    parser.add_argument("--abstention-threshold", type=float, default=0.5,
                       help="弃权告警阈值 (默认0.5)")
    parser.add_argument("--verbose", "-v", action="store_true", help="详细日志 (DEBUG级别)")
    parser.add_argument("--version", action="version",
                       version=f"Colony L2 Role Election Engine v{VERSION} ({COLONY_ID})")

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    if args.multi is not None:
        run_multi_task_demo(
            num_tasks=args.multi,
            export_report=not args.no_export,
        )
    elif args.task:
        # 自定义单任务
        task = TaskContext(
            task_id=f"TASK-{uuid.uuid4().hex[:8]}",
            original_task=args.task,
        )

        config = {
            "election_mode": args.mode,
            "abstention_alert_threshold": args.abstention_threshold,
            "enable_abstention": True,
            "enable_gap_detection": True,
            "enable_attention_tracking": True,
            "enable_role_history": True,
            "broadcast_proposals": True,
        }

        engine = RoleElectionEngine(config=config)

        # 创建Agent
        agent_capabilities = [
            (["需求分析", "架构设计", "代码实现"], ["需求分析", "系统架构", "后端开发"]),
            (["测试验证", "安全审计", "文档编写"], ["安全审计", "测试", "文档"]),
            (["数据分析", "性能优化", "代码实现"], ["性能优化", "数据库", "数据分析"]),
            (["用户体验", "项目管理", "需求分析"], ["UX", "前端", "项目管理"]),
            (["安全架构", "密码学", "身份认证"], ["安全", "密码学", "认证"]),
            (["DevOps", "CI/CD", "容器化"], ["DevOps", "K8s", "CI/CD"]),
            (["API设计", "微服务", "系统集成"], ["API", "微服务", "集成"]),
        ]

        for i in range(args.agents):
            idx = i % len(agent_capabilities)
            caps, expertise = agent_capabilities[idx]
            agent = SimulatedElectableAgent(
                f"Agent-{i+1}",
                capabilities=caps,
                expertise_domains=expertise,
                abstention_tendency=0.1 + random.uniform(-0.05, 0.1),
            )
            engine.register_agent(agent)

        transfers = engine.run_full_pipeline_election(task)

        for t in transfers:
            print(f"\nStage {t.stage_id}: {len(t.role_assignments)}角色, "
                  f"{len(t.abstentions)}弃权, {len(t.gap_alerts)}告警")

        if not args.no_export:
            engine.export_results(transfers, str(Path(args.output) / f"report-{task.task_id}.json"))
    else:
        run_demo(export_report=not args.no_export, output_dir=args.output)


if __name__ == "__main__":
    main()
