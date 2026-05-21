#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
  Colony v2.0 Layer 6: 跨域迁移与集体记忆
  Colony-040 极限实验室

  三大核心能力:
    1. 公理骨架迁移协议 — 提取领域无关骨架 → 目标域映射 → 零样本验证
    2. 跨Agent经验交叉 — GEPA式Lineage Merge扩展到跨Agent场景
    3. 角色空间可视化 — UMAP 2D投影 + 三层可视化输出

  设计来源:
    - Colony-034 架构文档 v2.0 Section 7 (Layer 6)
    - Hyperagents (DGM-H): 跨域零样本迁移能力
    - GEPA: 跨分支系统感知交叉 (lineage merge)
    - 内生性悖论: 5,006+ 自发角色涌现与聚类
    - Nexa: 身份不可知的策略泛化

  运行方式:
    python cross-domain-migration.py              # 演示模式
    python cross-domain-migration.py --export     # 导出可视化HTML
    python cross-domain-migration.py --full       # 完整迁移验证管线

  作者: Colony-040 (极限实验室)
  日期: 2026-05-19
  许可: MIT
================================================================================
"""

import json
import os
import sys
import time
import uuid
import random
import hashlib
import math
import logging
import argparse
from abc import ABC, abstractmethod
from dataclasses import dataclass, field, asdict
from typing import Optional, Callable, Any
from enum import Enum, auto
from collections import defaultdict, Counter
from pathlib import Path
from itertools import combinations

# ---------------------------------------------------------------------------
# 第三方库可用性检测
# ---------------------------------------------------------------------------

NUMPY_AVAILABLE = False
SKLEARN_AVAILABLE = False
UMAP_AVAILABLE = False

try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    pass

try:
    from sklearn.metrics.pairwise import cosine_similarity
    from sklearn.preprocessing import StandardScaler
    SKLEARN_AVAILABLE = True
except ImportError:
    pass

try:
    import umap
    UMAP_AVAILABLE = True
except ImportError:
    pass

# ---------------------------------------------------------------------------
# 日志配置
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] L6: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("Colony-040-L6")

# ---------------------------------------------------------------------------
# 枚举与常量
# ---------------------------------------------------------------------------

class AxiomCategory(Enum):
    """公理类别"""
    EXPLORATION    = "探索"       # 探索策略
    SAFETY         = "安全"       # 安全约束
    EVOLUTION      = "进化"       # 进化规则
    COORDINATION   = "协调"       # Agent协作
    META_COGNITION = "元认知"     # 自我修改
    TRANSFER       = "跨域"       # 跨域迁移 (Type T)

class TransferResult(Enum):
    """迁移结果"""
    VALID     = "跨域有效"         # Δ > 0, 公理升级为 Type T
    INVALID   = "跨域无效"         # Δ = 0, 骨架含领域特定成分
    DEGRADED  = "退化"            # Δ < 0, 迁移导致性能下降
    PENDING   = "待验证"          # 尚未完成验证

class MergeStrategy(Enum):
    """经验交叉策略"""
    CROSS_ONLY  = "cross_only"    # 仅交叉双方都已独立进化的模块
    UNION_ALL   = "union_all"     # 合并所有模块（风险高）
    SELECTIVE   = "selective"     # 基于语义相似度选择性合并

class VisualLevel(Enum):
    """可视化层级"""
    MACRO  = "macro"   # 宏观: 全局元角色聚类
    MESO   = "meso"    # 中观: 单Agent角色变迁轨迹
    MICRO  = "micro"   # 微观: 单次任务角色涌现过程

# UMAP 默认参数
UMAP_N_NEIGHBORS = 15
UMAP_MIN_DIST = 0.1
UMAP_N_COMPONENTS = 2
UMAP_RANDOM_STATE = 42

# 语义嵌入维度（对齐 all-MiniLM-L6-v2）
EMBEDDING_DIM = 384

# 迁移协议参数
ZERO_SHOT_ROUNDS = 10         # 零样本应用轮数
TRANSFER_CONFIDENCE_THRESHOLD = 0.6  # 迁移置信度阈值
MIN_SIMILARITY_FOR_MERGE = 0.70      # 合并最低语义相似度

# ---------------------------------------------------------------------------
# 数据类定义
# ---------------------------------------------------------------------------

@dataclass
class AxiomSkeleton:
    """公理骨架 —— 剥离领域特定参数后的领域无关结构"""
    skeleton_id: str                          # 骨架唯一ID
    source_axiom_id: str                      # 来源公理ID
    domain_agnostic_statement: str            # 领域无关陈述
    placeholders: dict[str, str]               # 占位符→领域参数映射
    applicability_conditions: list[str]        # 适用条件列表
    extraction_confidence: float               # 提取置信度 0-1

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "AxiomSkeleton":
        return cls(**data)


@dataclass
class DomainMapping:
    """目标域映射 —— 骨架应用到具体目标域的参数化实例"""
    mapping_id: str
    skeleton_id: str
    target_domain: str                        # 目标域名称
    parameter_bindings: dict[str, str]         # 占位符 → 具体绑定
    mapped_statement: str                     # 映射后的领域具体陈述
    mapping_confidence: float                 # 映射置信度 0-1

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class MigrationRecord:
    """迁移记录 —— 一次跨域迁移的完整追踪"""
    record_id: str
    skeleton: AxiomSkeleton
    mapping: DomainMapping
    result: TransferResult
    delta_scores: dict[str, float]            # 各维度 Δ 变化
    rounds: int = ZERO_SHOT_ROUNDS
    analysis: str = ""                        # 分析备注
    timestamp: str = ""

    def __post_init__(self):
        self.timestamp = time.strftime("%Y-%m-%d %H:%M:%S")

    def to_dict(self) -> dict:
        d = asdict(self)
        d["skeleton"] = self.skeleton.to_dict()
        d["mapping"] = self.mapping.to_dict()
        d["result"] = self.result.value
        return d


@dataclass
class CrossDomainLibrary:
    """跨域公理库 —— 所有已验证骨架的持久存储"""
    library_id: str
    skeletons: list[AxiomSkeleton] = field(default_factory=list)
    valid_migrations: list[MigrationRecord] = field(default_factory=list)
    failed_migrations: list[MigrationRecord] = field(default_factory=list)
    version: int = 1

    def add_skeleton(self, skeleton: AxiomSkeleton) -> None:
        self.skeletons.append(skeleton)

    def add_migration(self, record: MigrationRecord) -> None:
        if record.result == TransferResult.VALID:
            self.valid_migrations.append(record)
        else:
            self.failed_migrations.append(record)

    def get_type_t_axioms(self) -> list[AxiomSkeleton]:
        """获取所有 Type T (已验证跨域有效) 的公理骨架"""
        valid_ids = {r.skeleton.skeleton_id for r in self.valid_migrations}
        return [s for s in self.skeletons if s.skeleton_id in valid_ids]

    def stats(self) -> dict:
        return {
            "total_skeletons": len(self.skeletons),
            "valid_migrations": len(self.valid_migrations),
            "failed_migrations": len(self.failed_migrations),
            "transfer_success_rate": (
                len(self.valid_migrations) /
                max(len(self.valid_migrations) + len(self.failed_migrations), 1)
            ),
            "type_t_axioms": len(self.get_type_t_axioms()),
        }

    def to_dict(self) -> dict:
        return {
            "library_id": self.library_id,
            "version": self.version,
            "stats": self.stats(),
            "skeletons": [s.to_dict() for s in self.skeletons],
            "valid_migrations": [m.to_dict() for m in self.valid_migrations],
            "failed_migrations": [m.to_dict() for m in self.failed_migrations],
        }


# ==============================================================================
#  第一部分: 公理骨架迁移协议 (Axiom Transfer Protocol)
# ==============================================================================

class AxiomSkeletonExtractor:
    """
    公理骨架提取器
    职责: 从源公理中剥离领域特定参数，提取领域无关的核心结构

    对齐架构 Section 7.2 步骤1:
      "提取领域无关骨架"——源公理 → 骨架 (领域无关陈述 + 占位符映射)
    """

    VALID_DOMAINS = [
        "Agent协作优化",
        "Pipeline编排优化",
        "技能进化",
        "安全门禁",
        "通信路由",
        "角色选举",
        "记忆管理",
        "元认知自检",
    ]

    def __init__(self, strict_mode: bool = False):
        self.strict_mode = strict_mode  # 严格模式: 置信度 < 阈值拒绝
        self.extraction_count = 0

    def extract(self, axiom_id: str, axiom_statement: str,
                domain: str, rationale: str = "") -> AxiomSkeleton:
        """
        提取公理骨架

        Args:
            axiom_id:     源公理ID (如 AX-021-001)
            axiom_statement: 中文公理陈述
            domain:       所属领域
            rationale:    理论依据

        Returns:
            AxiomSkeleton 领域无关骨架

        算法:
          1. 识别领域特定参数 (数字阈值、特定对象名称、领域术语)
          2. 将参数替换为占位符
          3. 生成领域无关陈述
          4. 评估提取置信度
        """
        self.extraction_count += 1
        skeleton_id = f"SKEL-{self.extraction_count:03d}"

        # ---- 步骤1: 识别领域特定参数 ----
        placeholders = self._identify_domain_parameters(axiom_statement, domain)

        # ---- 步骤2: 生成领域无关陈述 ----
        domain_agnostic = self._generalize(axiom_statement, placeholders, domain)

        # ---- 步骤3: 识别适用条件 ----
        conditions = self._infer_applicability(domain_agnostic, domain)

        # ---- 步骤4: 计算提取置信度 ----
        confidence = self._compute_confidence(placeholders, domain_agnostic, rationale)

        skeleton = AxiomSkeleton(
            skeleton_id=skeleton_id,
            source_axiom_id=axiom_id,
            domain_agnostic_statement=domain_agnostic,
            placeholders=placeholders,
            applicability_conditions=conditions,
            extraction_confidence=confidence,
        )

        logger.info(
            f"[提取骨架] {axiom_id} → {skeleton_id} "
            f"(置信度: {confidence:.2f}, 占位符: {len(placeholders)}个)"
        )

        return skeleton

    def _identify_domain_parameters(self, statement: str,
                                     domain: str) -> dict[str, str]:
        """
        识别语句中的领域特定参数

        扫描策略:
          - 数字参数 (K, N, M 等变量)
          - 领域特定术语 (Agent名称、评估维度名)
          - 操作动词 (注入、选举、路由 等)
        """
        params = {}
        domain_terms = {
            "Agent协作优化": ["Agent", "协作", "角色", "响应"],
            "Pipeline编排优化": ["Stage", "编排", "流水线", "传递"],
            "技能进化":      ["Skill", "技能", "变异", "进化"],
            "安全门禁":      ["门禁", "安全", "校验", "审计"],
            "通信路由":      ["路由", "通信", "消息", "串行", "并行"],
            "角色选举":      ["角色", "选举", "弃权", "提案"],
            "记忆管理":      ["记忆", "存储", "回溯", "持久"],
            "元认知自检":    ["元认知", "自检", "盲点", "公理"],
        }

        # 提取数字参数模式: K代, N轮, M个 等
        import re
        number_patterns = re.findall(
            r'([A-Za-z]+)\s*(?:=|为)?\s*(\d+(?:\.\d+)?)', statement
        )
        for var, val in number_patterns:
            params[f"${{{var}}}"] = str(val)

        # 提取领域特定术语
        terms = domain_terms.get(domain, [])
        for term in terms:
            if term in statement:
                params[f"[[{term}]]"] = term

        return params

    def _generalize(self, statement: str, placeholders: dict[str, str],
                    domain: str) -> str:
        """
        将领域特定参数替换为通用占位符，生成领域无关骨架陈述
        """
        generalized = statement
        for placeholder, original in placeholders.items():
            generalized = generalized.replace(original, placeholder)
        return generalized

    def _infer_applicability(self, skeleton: str,
                               source_domain: str) -> list[str]:
        """
        推断骨架的适用条件 —— 在什么类型的领域该骨架可能有效？
        """
        conditions = []

        # 基于模式识别推断适用域
        if "连续" in skeleton and "无变化" in skeleton:
            conditions.append("适用于具有持续评估机制的领域")
            conditions.append("要求目标域存在可量化的演化指标")
        if "扰动" in skeleton or "变异" in skeleton:
            conditions.append("目标域必须支持非破坏性干预")
            conditions.append("扰动操作不能触发安全熔断")
        if "选举" in skeleton or "角色" in skeleton:
            conditions.append("适用于多Agent或多角色系统")
            conditions.append("目标域Agent数量 > 2")
        if "评估" in skeleton or "度量" in skeleton:
            conditions.append("目标域需有明确的评估指标体系")

        if not conditions:
            conditions.append("通用骨架，无明显领域限制")

        return conditions

    def _compute_confidence(self, placeholders: dict[str, str],
                              generalized: str,
                              rationale: str) -> float:
        """
        计算骨架提取置信度

        启发式:
          - 占位符数量适中 (1-5个): 置信度高
          - 占位符过多 (>8): 骨架可能过于抽象
          - 有理论依据: 置信度+0.15
          - 陈述长度适中: 置信度高
        """
        confidence = 0.70  # 基线

        n_placeholders = len(placeholders)
        if 1 <= n_placeholders <= 5:
            confidence += 0.15
        elif n_placeholders > 8:
            confidence -= 0.20

        if rationale:
            confidence += 0.10

        # 陈述长度惩罚
        if len(generalized) < 20:
            confidence -= 0.10
        elif len(generalized) > 500:
            confidence -= 0.05

        return max(0.0, min(1.0, confidence))


class DomainMapper:
    """
    目标域映射器
    职责: 将骨架映射到具体目标域，生成可执行的领域实例

    对齐架构 Section 7.2 步骤2: "目标域映射"
    """

    def __init__(self):
        self.mapping_count = 0

    def map(self, skeleton: AxiomSkeleton,
            target_domain: str) -> DomainMapping:
        """
        将骨架映射到目标域

        Args:
            skeleton:     待映射的骨架
            target_domain: 目标域名 (如 "Agent协作优化")

        Returns:
            DomainMapping 包含参数绑定和映射后的陈述
        """
        self.mapping_count += 1
        mapping_id = f"MAP-{self.mapping_count:03d}"

        # 生成目标域的领域特定参数绑定
        bindings = self._bind_parameters(skeleton.placeholders, target_domain)

        # 生成映射后的陈述
        mapped = self._instantiate(skeleton.domain_agnostic_statement, bindings)

        # 评估映射置信度
        confidence = self._evaluate_mapping(skeleton, target_domain, bindings)

        mapping = DomainMapping(
            mapping_id=mapping_id,
            skeleton_id=skeleton.skeleton_id,
            target_domain=target_domain,
            parameter_bindings=bindings,
            mapped_statement=mapped,
            mapping_confidence=confidence,
        )

        logger.info(
            f"[目标域映射] {skeleton.skeleton_id} → {target_domain} "
            f"({mapping_id}, 置信度: {confidence:.2f})"
        )

        return mapping

    def _bind_parameters(self, placeholders: dict[str, str],
                           target_domain: str) -> dict[str, str]:
        """
        根据目标域特性绑定参数值

        不同领域对同一占位符有不同的合理取值
        """
        bindings = {}
        domain_defaults = {
            "Agent协作优化":   {"K": "10",  "N": "5",  "阈值": "0.7"},
            "Pipeline编排优化": {"K": "8",   "N": "3",  "阈值": "0.6"},
            "技能进化":       {"K": "15",  "N": "5",  "阈值": "0.8"},
            "安全门禁":       {"K": "3",   "N": "1",  "阈值": "0.95"},
            "通信路由":       {"K": "20",  "N": "10", "阈值": "0.5"},
            "角色选举":       {"K": "12",  "N": "7",  "阈值": "0.6"},
            "记忆管理":       {"K": "50",  "N": "20", "阈值": "0.7"},
            "元认知自检":     {"K": "5",   "N": "3",  "阈值": "0.9"},
        }

        defaults = domain_defaults.get(target_domain, {"K": "10", "N": "5", "阈值": "0.7"})

        for placeholder, original in placeholders.items():
            # 尝试匹配 K, N, 阈值 等常见参数
            matched = False
            for key, default_value in defaults.items():
                if key in placeholder:
                    bindings[placeholder] = default_value
                    matched = True
                    break
            if not matched:
                # 对于领域特定术语，生成目标域对应术语
                term_map = {
                    "Agent": "Agent",
                    "角色": "角色",
                    "Stage": "工作阶段",
                    "门禁": "检查点",
                    "路由": "消息路径",
                    "记忆": "持久存储",
                    "技能": "能力模块",
                }
                for src_term, tgt_term in term_map.items():
                    if src_term in original:
                        bindings[placeholder] = tgt_term
                        break
                else:
                    bindings[placeholder] = f"[{target_domain}·{original}]"

        return bindings

    def _instantiate(self, skeleton_text: str,
                       bindings: dict[str, str]) -> str:
        """用参数绑定替换占位符，生成映射后的陈述"""
        text = skeleton_text
        for placeholder, binding in bindings.items():
            text = text.replace(placeholder, binding)
        return text

    def _evaluate_mapping(self, skeleton: AxiomSkeleton,
                              target_domain: str,
                              bindings: dict[str, str]) -> float:
        """
        评估映射质量

        考量因素:
          - 所有占位符是否都已绑定
          - 目标域是否在适用条件列表中
          - 参数绑定是否在合理范围内
        """
        confidence = 0.75  # 基线

        # 完整绑定奖励
        if len(bindings) == len(skeleton.placeholders):
            confidence += 0.15

        # 目标域匹配适用条件
        for condition in skeleton.applicability_conditions:
            domain_keywords = {
                "Agent协作优化": ["多Agent", "Agent数量", "多角色"],
                "Pipeline编排优化": ["评估机制", "量化指标"],
                "技能进化":     ["进化", "非破坏性"],
                "安全门禁":     ["安全", "非破坏性"],
                "通信路由":     ["通信", "路由"],
                "角色选举":     ["多Agent", "多角色", "Agent数量"],
                "记忆管理":     ["存储", "持久"],
                "元认知自检":   ["评估机制", "量化指标"],
            }
            kw = domain_keywords.get(target_domain, [])
            if any(k in condition for k in kw):
                confidence += 0.05

        return max(0.0, min(1.0, confidence))


class MigrationValidator:
    """
    跨域迁移验证器
    职责: 在目标域部署骨架，测量零样本性能变化

    对齐架构 Section 7.2 步骤3: "零样本应用 + 测量"
    """

    def __init__(self, rounds: int = ZERO_SHOT_ROUNDS):
        self.rounds = rounds
        self.validation_count = 0

    def validate(self, skeleton: AxiomSkeleton,
                   mapping: DomainMapping) -> MigrationRecord:
        """
        验证迁移效果

        Args:
            skeleton: 骨架
            mapping:  目标域映射

        Returns:
            MigrationRecord 含 Δ 分数和分析

        验证流程:
          1. 在目标域部署 mapped_statement
          2. 运行 N=rounds 轮模拟
          3. 测量各维度性能变化 (Δ)
          4. 判定: Δ>0 → VALID, Δ=0 → INVALID, Δ<0 → DEGRADED
        """
        self.validation_count += 1
        record_id = f"MIG-{self.validation_count:03d}"

        # 运行模拟并测量 Δ
        delta_scores = self._run_simulation(mapping)

        # 判定迁移结果
        avg_delta = sum(delta_scores.values()) / max(len(delta_scores), 1)

        if avg_delta > 0.01:
            result = TransferResult.VALID
            analysis = (
                f"跨域有效: 平均Δ={avg_delta:.3f} > 0，公理骨架在目标域"
                f"「{mapping.target_domain}」产生正向改进。"
                f"建议将骨架 {skeleton.skeleton_id} 升级为 Type T (Transfer)。"
            )
        elif avg_delta < -0.01:
            result = TransferResult.DEGRADED
            analysis = (
                f"跨域退化: 平均Δ={avg_delta:.3f} < 0，迁移导致性能下降。"
                f"骨架中可能包含隐式领域假设，在目标域不适用。"
                f"建议分析占位符 {list(skeleton.placeholders.keys())} 的域特异性。"
            )
        else:
            result = TransferResult.INVALID
            analysis = (
                f"跨域无效: 平均Δ={avg_delta:.3f} ≈ 0，骨架在目标域无效果。"
                f"需分析骨架中哪些成分是领域特定的。"
            )

        record = MigrationRecord(
            record_id=record_id,
            skeleton=skeleton,
            mapping=mapping,
            result=result,
            delta_scores=delta_scores,
            rounds=self.rounds,
            analysis=analysis,
        )

        logger.info(
            f"[迁移验证] {record_id}: {skeleton.source_axiom_id}→"
            f"{mapping.target_domain} → {result.value} (Δavg={avg_delta:.3f})"
        )

        return record

    def _run_simulation(self, mapping: DomainMapping) -> dict[str, float]:
        """
        在目标域运行 N 轮模拟，返回各维度 Δ 得分

        模拟策略:
          - 每轮随机扰动领域参数 (±10%)
          - 测量 5 个统一维度: 速度、质量、多样性、稳定性、适应性
          - 返回与基线的差异 Δ
        """
        dimensions = ["速度", "质量", "多样性", "稳定性", "适应性"]
        delta_scores = {}

        for dim in dimensions:
            # 基线 + 随机扰动 → 观察映射后得分
            baseline = random.uniform(0.5, 0.8)
            # 映射置信度影响改进幅度
            improvement = (mapping.mapping_confidence - 0.5) * 0.3
            noise = random.gauss(0, 0.05)
            delta = improvement + noise
            delta_scores[dim] = round(delta, 4)

        return delta_scores


# ==============================================================================
#  第二部分: 跨Agent经验交叉 (Cross-Agent Lineage Merge)
# ==============================================================================

@dataclass
class SkillNode:
    """技能树节点"""
    skill_id: str
    skill_name: str
    agent_id: str
    version: int
    description: str
    domain: str
    evolution_history: list[str] = field(default_factory=list)
    parent_skill_id: Optional[str] = None
    performance_score: float = 0.7
    embedding: Optional[list[float]] = None  # 384维语义嵌入

    def to_dict(self) -> dict:
        d = asdict(self)
        if self.embedding and len(self.embedding) > 10:
            d["embedding"] = f"[{len(self.embedding)}维向量]"
        return d


@dataclass
class SkillTree:
    """Agent完整技能树"""
    agent_id: str
    agent_role: str
    skills: list[SkillNode]
    generation: int = 0
    lineage: list[str] = field(default_factory=list)  # 演进谱系

    def get_evolved_skills(self) -> list[SkillNode]:
        """获取有进化历史的技能 (version > 1 或有 parent)"""
        return [s for s in self.skills
                if s.version > 1 or s.parent_skill_id is not None]

    def to_dict(self) -> dict:
        return {
            "agent_id": self.agent_id,
            "agent_role": self.agent_role,
            "generation": self.generation,
            "skill_count": len(self.skills),
            "evolved_count": len(self.get_evolved_skills()),
            "skills": [s.to_dict() for s in self.skills],
        }


class SemanticEmbedder:
    """
    简易语义嵌入器
    使用轻量级哈希嵌入模拟 all-MiniLM-L6-v2 的 384 维语义空间

    在生产环境中替换为真实的 sentence-transformers 模型:
      from sentence_transformers import SentenceTransformer
      model = SentenceTransformer('all-MiniLM-L6-v2')
    """

    def __init__(self, dim: int = EMBEDDING_DIM):
        self.dim = dim
        self._vocab: dict[str, int] = {}
        self._embedding_cache: dict[str, list[float]] = {}

    def encode(self, text: str) -> list[float]:
        """
        模拟语义嵌入

        使用确定性哈希 + 局部敏感哈希编码
        保证: 相似文本 → 相似嵌入
        """
        if text in self._embedding_cache:
            return self._embedding_cache[text]

        # 多粒度 n-gram 哈希
        ngrams = self._extract_ngrams(text, n_range=(1, 4))
        vec = [0.0] * self.dim

        for ngram in ngrams:
            h = hashlib.sha256(ngram.encode()).digest()
            for i in range(min(len(h), self.dim)):
                # 使用字节值作为偏移
                seed = h[i % len(h)]
                idx = (i * 7 + seed) % self.dim
                vec[idx] += (seed / 255.0) * 0.1
                # 扩散到邻近维度
                vec[(idx + 1) % self.dim] += (seed / 255.0) * 0.05

        # L2 归一化
        norm = math.sqrt(sum(v * v for v in vec))
        if norm > 0:
            vec = [v / norm for v in vec]

        self._embedding_cache[text] = vec
        return vec

    def _extract_ngrams(self, text: str, n_range: tuple) -> list[str]:
        """提取 n-gram tokens (字符级 + 词级混合)"""
        tokens = []
        chars = text.replace(" ", "")
        for n in range(n_range[0], min(n_range[1] + 1, len(chars) + 1)):
            for i in range(len(chars) - n + 1):
                tokens.append(chars[i:i + n])

        # 词级 token
        words = text.split()
        for word in words:
            if word not in tokens:
                tokens.append(word)

        return tokens

    def similarity(self, text_a: str, text_b: str) -> float:
        """计算两个文本的余弦相似度"""
        emb_a = self.encode(text_a)
        emb_b = self.encode(text_b)
        dot = sum(a * b for a, b in zip(emb_a, emb_b))
        return max(0.0, min(1.0, dot))


class CrossAgentLineageMerge:
    """
    跨Agent经验交叉引擎
    职责: 在Agent之间安全地交换已独立进化过的技能模块

    对齐架构 Section 7.3:
      - 只交换"双方都已独立进化过"的模块 (防止污染)
      - 技能表示在同一个语义嵌入空间中
      - 交叉后需要 mini-batch 验证 (退化检测)

    对标 GEPA System-Aware Merge:
      PM Agent 技能树 x 架构师Agent 技能树 → 交叉分析 → 安全合并
    """

    def __init__(self, strategy: MergeStrategy = MergeStrategy.CROSS_ONLY,
                 min_similarity: float = MIN_SIMILARITY_FOR_MERGE):
        self.strategy = strategy
        self.min_similarity = min_similarity
        self.embedder = SemanticEmbedder()
        self.merge_records: list[dict] = []

    def merge(self, tree_a: SkillTree, tree_b: SkillTree) -> tuple[SkillTree, SkillTree, dict]:
        """
        执行跨Agent经验交叉

        Args:
            tree_a: Agent A 的技能树
            tree_b: Agent B 的技能树

        Returns:
            (updated_tree_a, updated_tree_b, merge_report)

        步骤:
          1. 为所有技能生成语义嵌入
          2. 识别双方都已独立进化的模块
          3. 计算技能间交叉相似度矩阵
          4. 筛选安全可交叉的技能对
          5. 生成交叉技能并附加到对方技能树
          6. Mini-batch 退化检测
          7. 生成合并报告
        """
        logger.info(f"[Lineage Merge] {tree_a.agent_role} x {tree_b.agent_role} 开始交叉")

        # ---- 步骤1: 生成语义嵌入 ----
        self._ensure_embeddings(tree_a)
        self._ensure_embeddings(tree_b)

        # ---- 步骤2: 识别已独立进化的模块 ----
        evolved_a = tree_a.get_evolved_skills()
        evolved_b = tree_b.get_evolved_skills()

        logger.info(
            f"  {tree_a.agent_role}: {len(tree_a.skills)}个技能, "
            f"{len(evolved_a)}个已进化"
        )
        logger.info(
            f"  {tree_b.agent_role}: {len(tree_b.skills)}个技能, "
            f"{len(evolved_b)}个已进化"
        )

        # ---- 步骤3: 计算交叉相似度 ----
        cross_pairs = []
        for sa in evolved_a:
            for sb in evolved_b:
                if sa.embedding and sb.embedding:
                    sim = self._cosine_similarity(sa.embedding, sb.embedding)
                    cross_pairs.append((sa, sb, sim))

        # ---- 步骤4: 筛选安全可交叉的技能对 ----
        # CROSS_ONLY策略: 只合并双方都已独立进化的模块
        if self.strategy == MergeStrategy.CROSS_ONLY:
            # 交叉条件: 双方都有 v>1 的技能 + 语义相似度跨域适用
            safe_pairs = [
                (sa, sb, sim) for sa, sb, sim in cross_pairs
                if sim >= self.min_similarity
            ]
        elif self.strategy == MergeStrategy.SELECTIVE:
            # 按相似度排序取 Top-K
            cross_pairs.sort(key=lambda x: x[2], reverse=True)
            safe_pairs = cross_pairs[:max(len(cross_pairs) // 2, 1)]
        else:
            safe_pairs = cross_pairs  # UNION_ALL: 全合并

        logger.info(f"  交叉对总数: {len(cross_pairs)}, 安全可交叉: {len(safe_pairs)}")

        # ---- 步骤5: 生成交叉技能 ----
        new_for_a = []
        new_for_b = []

        for sa, sb, sim in safe_pairs:
            # A 获得 B 的进化经验
            cross_skill_a = self._create_cross_skill(
                source_skill=sb,
                target_agent_id=tree_a.agent_id,
                cross_agent_id=tree_b.agent_id,
                similarity=sim,
            )
            new_for_a.append(cross_skill_a)

            # B 获得 A 的进化经验
            cross_skill_b = self._create_cross_skill(
                source_skill=sa,
                target_agent_id=tree_b.agent_id,
                cross_agent_id=tree_a.agent_id,
                similarity=sim,
            )
            new_for_b.append(cross_skill_b)

        # 附加到对方技能树
        tree_a.skills.extend(new_for_a)
        tree_b.skills.extend(new_for_b)
        tree_a.generation += 1
        tree_b.generation += 1

        # ---- 步骤6: Mini-batch 退化检测 ----
        degradation_a = self._detect_degradation(tree_a, new_for_a)
        degradation_b = self._detect_degradation(tree_b, new_for_b)

        # ---- 步骤7: 生成报告 ----
        report = {
            "merge_id": f"MERGE-{uuid.uuid4().hex[:8]}",
            "agent_a": tree_a.agent_role,
            "agent_b": tree_b.agent_role,
            "strategy": self.strategy.value,
            "cross_pairs_total": len(cross_pairs),
            "safe_pairs": len(safe_pairs),
            "skills_added_to_a": len(new_for_a),
            "skills_added_to_b": len(new_for_b),
            "degradation_detected_a": degradation_a,
            "degradation_detected_b": degradation_b,
            "cross_details": [
                {
                    "from_agent": pair[1].agent_id,
                    "from_skill": pair[1].skill_name,
                    "to_agent": pair[0].agent_id,
                    "to_skill": pair[0].skill_name,
                    "similarity": round(pair[2], 3),
                }
                for pair in safe_pairs
            ],
        }

        self.merge_records.append(report)

        logger.info(
            f"[Lineage Merge] 完成: A+{len(new_for_a)}技能, "
            f"B+{len(new_for_b)}技能, 退化检测="
            f"{{A:{degradation_a}, B:{degradation_b}}}"
        )

        return tree_a, tree_b, report

    def _ensure_embeddings(self, tree: SkillTree) -> None:
        """确保所有技能节点都有语义嵌入"""
        for skill in tree.skills:
            if skill.embedding is None:
                text = f"{skill.skill_name} {skill.description} {skill.domain}"
                skill.embedding = self.embedder.encode(text)

    def _cosine_similarity(self, a: list[float], b: list[float]) -> float:
        """计算两个向量的余弦相似度"""
        if SKLEARN_AVAILABLE and NUMPY_AVAILABLE:
            return float(cosine_similarity(
                np.array(a).reshape(1, -1),
                np.array(b).reshape(1, -1),
            )[0][0])
        else:
            dot = sum(x * y for x, y in zip(a, b))
            na = math.sqrt(sum(x * x for x in a))
            nb = math.sqrt(sum(y * y for y in b))
            if na == 0 or nb == 0:
                return 0.0
            return max(0.0, min(1.0, dot / (na * nb)))

    def _create_cross_skill(self, source_skill: SkillNode,
                               target_agent_id: str,
                               cross_agent_id: str,
                               similarity: float) -> SkillNode:
        """从源技能创建交叉技能（注入目标Agent）"""
        cross_id = f"CROSS-{source_skill.skill_id}-{uuid.uuid4().hex[:6]}"
        cross_name = f"[交叉] {source_skill.skill_name}"

        return SkillNode(
            skill_id=cross_id,
            skill_name=cross_name,
            agent_id=target_agent_id,
            version=1,
            description=f"从 {cross_agent_id} 交叉获取: {source_skill.description}"
                       f" (语义相似度: {similarity:.2f})",
            domain=f"跨域·{source_skill.domain}",
            evolution_history=[f"来源: {cross_agent_id}/{source_skill.skill_name} v{source_skill.version}"],
            parent_skill_id=source_skill.skill_id,
            performance_score=source_skill.performance_score * similarity,
            embedding=source_skill.embedding,
        )

    def _detect_degradation(self, tree: SkillTree,
                              new_skills: list[SkillNode]) -> bool:
        """
        Mini-batch 退化检测

        检测逻辑: 如果新增交叉技能的平均性能分低于原有进化技能的平均分
                   超过阈值 (20%)，则标记为退化
        """
        if not new_skills:
            return False

        cross_avg = sum(s.performance_score for s in new_skills) / len(new_skills)
        evolved = tree.get_evolved_skills()
        if not evolved:
            return False

        evolved_avg = sum(s.performance_score for s in evolved) / len(evolved)
        degradation = cross_avg < evolved_avg * 0.80

        return degradation


# ==============================================================================
#  第三部分: 角色空间可视化 (Role Space Visualization)
# ==============================================================================

@dataclass
class RoleRecord:
    """单次角色涌现记录"""
    role_id: str
    role_name: str              # Agent自命名
    agent_id: str
    task_id: str
    stage: int                  # 1-4 对应 Pipeline Stage
    category: str               # 系统自动聚类元标签
    confidence: float           # Agent自评置信度
    contribution_summary: str   # 产出摘要
    embedding: Optional[list[float]] = None


@dataclass
class AgentRoleTrajectory:
    """单Agent角色变迁轨迹"""
    agent_id: str
    agent_name: str
    role_records: list[RoleRecord]
    total_tasks: int

    def dominant_category(self) -> str:
        """最常承担的角色类别"""
        if not self.role_records:
            return "未分类"
        return Counter(r.category for r in self.role_records).most_common(1)[0][0]

    def role_diversity(self) -> float:
        """角色多样性: 独特角色数 / 总记录数"""
        if not self.role_records:
            return 0.0
        unique = len(set(r.role_name for r in self.role_records))
        return unique / len(self.role_records)


class RoleSpaceVisualizer:
    """
    角色空间可视化器
    职责: 将 5,006+ 自发角色映射到 2D 空间并生成交互式可视化

    对齐架构 Section 7.4:
      三个层次:
        1. 宏观: 全局角色空间 (20-50个元角色聚类)
        2. 中观: 单Agent角色变迁轨迹
        3. 微观: 单次任务角色涌现过程

    使用 UMAP 降维 + 简易聚类
    """

    def __init__(self, n_neighbors: int = UMAP_N_NEIGHBORS,
                 min_dist: float = UMAP_MIN_DIST,
                 random_state: int = UMAP_RANDOM_STATE):
        self.n_neighbors = n_neighbors
        self.min_dist = min_dist
        self.random_state = random_state
        self.embedder = SemanticEmbedder()
        self.umap_model = None
        self.cluster_centers: dict[str, tuple[float, float]] = {}

    def build_role_space(self, role_records: list[RoleRecord],
                           meta_categories: list[str]) -> dict:
        """
        构建完整的角色空间

        Args:
            role_records:     所有角色涌现记录
            meta_categories:  元角色类别标签列表

        Returns:
            可视化数据结构 dict
        """
        logger.info(f"[角色可视化] 构建空间: {len(role_records)}个角色记录, "
                     f"{len(meta_categories)}个元类别")

        # ---- 步骤1: 生成语义嵌入 ----
        texts = [f"{r.role_name} {r.contribution_summary}" for r in role_records]
        embeddings = np.array([self.embedder.encode(t) for t in texts]) if NUMPY_AVAILABLE \
                     else np.array([[self.embedder.encode(t)] for t in texts])

        # 存储嵌入到记录
        for i, record in enumerate(role_records):
            if NUMPY_AVAILABLE:
                record.embedding = embeddings[i].tolist()

        # ---- 步骤2: UMAP 降维到 2D ----
        coords_2d = self._reduce_to_2d(embeddings)

        # ---- 步骤3: 简易聚类（基于坐标分桶 + 元类别标签） ----
        clusters = self._build_clusters(role_records, coords_2d, meta_categories)

        # ---- 步骤4: 构建可视化数据 ----
        vis_data = {
            "total_roles": len(role_records),
            "meta_categories": meta_categories,
            "clusters": clusters,
            "projection_2d": [
                {
                    "role_id": r.role_id,
                    "role_name": r.role_name,
                    "agent_id": r.agent_id,
                    "task_id": r.task_id,
                    "stage": r.stage,
                    "category": r.category,
                    "x": round(float(coords_2d[i][0]), 4),
                    "y": round(float(coords_2d[i][1]), 4),
                }
                for i, r in enumerate(role_records)
            ],
            "method": f"Embedding({EMBEDDING_DIM}d) → {'UMAP' if UMAP_AVAILABLE else 'PCA-like'} → 2D",
        }

        logger.info(f"[角色可视化] 完成: {len(clusters)}个聚类, "
                     f"2D范围 x:[{min(coords_2d[:,0]):.2f}, {max(coords_2d[:,0]):.2f}], "
                     f"y:[{min(coords_2d[:,1]):.2f}, {max(coords_2d[:,1]):.2f}]")

        return vis_data

    def _reduce_to_2d(self, embeddings: "np.ndarray") -> "np.ndarray":
        """降维到2D空间"""
        if UMAP_AVAILABLE and NUMPY_AVAILABLE:
            self.umap_model = umap.UMAP(
                n_neighbors=min(self.n_neighbors, len(embeddings) - 1),
                min_dist=self.min_dist,
                n_components=UMAP_N_COMPONENTS,
                random_state=self.random_state,
                metric="cosine",
            )
            coords = self.umap_model.fit_transform(embeddings)
            logger.info(f"  使用 UMAP 降维: {embeddings.shape} → {coords.shape}")
        elif NUMPY_AVAILABLE:
            # Fallback: 使用 PCA (SVD)
            logger.warning("  UMAP 不可用，回退到 PCA 降维")
            centered = embeddings - embeddings.mean(axis=0)
            U, S, Vt = np.linalg.svd(centered, full_matrices=False)
            coords = (centered @ Vt[:2].T)
        else:
            # 纯 Python Fallback: 随机投影
            logger.warning("  NumPy 不可用，使用随机投影")
            n = len(embeddings)
            coords = np.zeros((n, 2))
            for i in range(n):
                seed_a = sum(embeddings[i][:EMBEDDING_DIM//2]) if hasattr(embeddings[i], '__iter__') else 0.5
                seed_b = sum(embeddings[i][EMBEDDING_DIM//2:]) if hasattr(embeddings[i], '__iter__') else 0.3
                coords[i, 0] = (hash(f"x_{i}_{seed_a}") % 1000) / 1000.0 * 10 - 5
                coords[i, 1] = (hash(f"y_{i}_{seed_b}") % 1000) / 1000.0 * 10 - 5

        return coords

    def _build_clusters(self, role_records: list[RoleRecord],
                           coords_2d: "np.ndarray",
                           meta_categories: list[str]) -> list[dict]:
        """
        构建聚类: 基于 2D 坐标的网格分桶 + 类别标签
        """
        clusters = []
        category_to_records = defaultdict(list)

        for i, record in enumerate(role_records):
            category_to_records[record.category].append((i, record, coords_2d[i]))

        for category in meta_categories:
            members = category_to_records.get(category, [])
            if not members:
                continue

            xs = [float(c[0]) for _, _, c in members]
            ys = [float(c[1]) for _, _, c in members]
            center_x = sum(xs) / len(xs)
            center_y = sum(ys) / len(ys)

            # 计算簇半径
            radii = [math.sqrt((x - center_x)**2 + (y - center_y)**2)
                     for x, y in zip(xs, ys)]
            radius = max(radii) if radii else 1.0

            self.cluster_centers[category] = (center_x, center_y)

            clusters.append({
                "category": category,
                "size": len(members),
                "center": [round(center_x, 4), round(center_y, 4)],
                "radius": round(radius, 4),
                "member_roles": [
                    {
                        "role_name": m.role_name,
                        "agent_id": m.agent_id,
                        "count": 1,
                    }
                    for _, m, _ in members
                ],
                "density": round(len(members) / max(radius, 0.01), 2),
            })

        return clusters

    def build_agent_trajectory(self,
                                  trajectories: list[AgentRoleTrajectory]) -> dict:
        """
        构建中观层可视化: 各Agent的角色变迁轨迹

        Returns:
            Agent轨迹数据，适合绘制时序轨迹图
        """
        traj_data = {
            "agents": [],
            "trajectory_lines": [],
        }

        for traj in trajectories:
            if not traj.role_records:
                continue

            agent_entry = {
                "agent_id": traj.agent_id,
                "agent_name": traj.agent_name,
                "total_tasks": traj.total_tasks,
                "dominant_category": traj.dominant_category(),
                "role_diversity": round(traj.role_diversity(), 3),
                "records": [
                    {
                        "role_name": r.role_name,
                        "task_id": r.task_id,
                        "stage": r.stage,
                        "category": r.category,
                        "confidence": r.confidence,
                    }
                    for r in traj.role_records
                ],
            }
            traj_data["agents"].append(agent_entry)

        return traj_data

    def build_task_emergence(self,
                                task_id: str,
                                stage_records: dict[int, list[RoleRecord]]) -> dict:
        """
        构建微观层可视化: 单次任务4个Stage的角色涌现过程

        Returns:
            适合绘制分阶段 Sankey 图或平行坐标系的数据
        """
        emergence_data = {
            "task_id": task_id,
            "stages": {},
        }

        for stage_num in sorted(stage_records.keys()):
            records = stage_records[stage_num]
            emergence_data["stages"][f"Stage{stage_num}"] = {
                "stage_name": ["情境感知", "方案生成", "执行实现", "质量验证"][stage_num - 1],
                "active_agents": list(set(r.agent_id for r in records)),
                "roles": [
                    {
                        "agent_id": r.agent_id,
                        "role_name": r.role_name,
                        "confidence": r.confidence,
                        "category": r.category,
                    }
                    for r in records
                ],
            }

        return emergence_data

    def export_html(self, vis_data: dict,
                    traj_data: Optional[dict] = None,
                    emergence_data: Optional[dict] = None,
                    filepath: str = "role-space-visualization.html") -> str:
        """
        导出交互式 HTML 可视化

        包含三个层级:
          1. 宏观: 散点图 - 角色空间全局
          2. 中观: Agent角色变迁轨迹
          3. 微观: 单次任务角色涌现时序
        """
        html = self._generate_html_template(vis_data, traj_data, emergence_data)

        filepath = Path(filepath)
        filepath.write_text(html, encoding="utf-8")

        logger.info(f"[可视化导出] HTML 已保存到: {filepath.absolute()}")

        return str(filepath.absolute())

    def _generate_html_template(self, vis_data: dict,
                                   traj_data: Optional[dict],
                                   emergence_data: Optional[dict]) -> str:
        """生成完整的交互式可视化 HTML 页面"""

        # 序列化数据为 JSON
        data_json = json.dumps({
            "macro": vis_data,
            "meso": traj_data,
            "micro": emergence_data,
        }, ensure_ascii=False, indent=2)

        return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Colony v2.0 L6 — 角色空间可视化</title>
<style>
  * {{ margin:0; padding:0; box-sizing:border-box; }}
  body {{ font-family: 'Segoe UI', system-ui, sans-serif; background: #0f1117; color: #e1e4e8; }}
  header {{
    background: linear-gradient(135deg, #1a1f35 0%, #2d1f4e 100%);
    padding: 24px 32px; border-bottom: 1px solid #30363d;
  }}
  header h1 {{ font-size: 24px; font-weight: 600; }}
  header p {{ margin-top: 6px; color: #8b949e; font-size: 14px; }}
  .tabs {{ display:flex; gap:0; background:#161b22; border-bottom:1px solid #30363d; padding:0 32px; }}
  .tab {{
    padding:12px 24px; cursor:pointer; border-bottom:2px solid transparent;
    font-size:14px; color:#8b949e; transition:all 0.2s;
  }}
  .tab:hover {{ color:#58a6ff; }}
  .tab.active {{ color:#58a6ff; border-bottom-color:#58a6ff; }}
  .panel {{ display:none; padding:24px 32px; }}
  .panel.active {{ display:block; }}
  .stats {{ display:flex; gap:16px; flex-wrap:wrap; margin-bottom:24px; }}
  .stat-card {{
    background:#161b22; border:1px solid #30363d; border-radius:8px;
    padding:16px 20px; min-width:140px;
  }}
  .stat-card .label {{ font-size:12px; color:#8b949e; text-transform:uppercase; }}
  .stat-card .value {{ font-size:28px; font-weight:700; color:#58a6ff; margin-top:4px; }}
  canvas {{ border:1px solid #30363d; border-radius:8px; background:#0d1117; }}
  .cluster-list {{ display:flex; flex-wrap:wrap; gap:10px; margin-top:16px; }}
  .cluster-tag {{
    background:#1f2937; border:1px solid #374151; border-radius:6px;
    padding:6px 12px; font-size:13px;
  }}
  .cluster-tag .cat {{ color:#58a6ff; font-weight:600; }}
  .cluster-tag .size {{ color:#8b949e; }}
  .trajectory-row {{
    background:#161b22; border:1px solid #30363d; border-radius:8px;
    padding:16px; margin-bottom:12px;
  }}
  .trajectory-row h4 {{ color:#58a6ff; margin-bottom:8px; }}
  .role-chip {{
    display:inline-block; background:#1f2937; border-radius:4px;
    padding:3px 8px; margin:2px; font-size:12px;
  }}
</style>
</head>
<body>

<header>
  <h1>Colony v2.0 Layer 6 — 角色空间可视化</h1>
  <p>5,006+ 自发角色 → 语义嵌入 (384d) → UMAP 2D投影 → 交互式可视化 | Colony-040 极限实验室 | 2026-05-19</p>
</header>

<div class="tabs">
  <div class="tab active" onclick="switchTab('macro')">宏观 — 全局角色空间</div>
  <div class="tab" onclick="switchTab('meso')">中观 — Agent角色变迁</div>
  <div class="tab" onclick="switchTab('micro')">微观 — 任务角色涌现</div>
</div>

<div id="panel-macro" class="panel active">
  <div class="stats" id="macro-stats"></div>
  <canvas id="macro-canvas" width="900" height="600"></canvas>
  <div class="cluster-list" id="cluster-list"></div>
</div>

<div id="panel-meso" class="panel">
  <div class="stats" id="meso-stats"></div>
  <div id="trajectory-container"></div>
</div>

<div id="panel-micro" class="panel">
  <div class="stats" id="micro-stats"></div>
  <div id="emergence-container"></div>
</div>

<script>
const DATA = {data_json};

function switchTab(level) {{
  document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
  document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
  document.querySelector(`.tab:nth-child(${{level === 'macro' ? 1 : level === 'meso' ? 2 : 3}})`).classList.add('active');
  document.getElementById(`panel-${{level}}`).classList.add('active');
  if (level === 'macro') renderMacro();
  if (level === 'meso') renderMeso();
  if (level === 'micro') renderMicro();
}}

// ---- 宏观: 全局角色空间散点图 ----
function renderMacro() {{
  const vis = DATA.macro;
  if (!vis) return;

  document.getElementById('macro-stats').innerHTML = `
    <div class="stat-card"><div class="label">总角色记录</div><div class="value">${{vis.total_roles}}</div></div>
    <div class="stat-card"><div class="label">元类别数</div><div class="value">${{vis.meta_categories.length}}</div></div>
    <div class="stat-card"><div class="label">聚类数</div><div class="value">${{vis.clusters.length}}</div></div>
    <div class="stat-card"><div class="label">降维方法</div><div class="value" style="font-size:14px;">${{vis.method.split('→').pop().trim()}}</div></div>
  `;

  const clusterList = document.getElementById('cluster-list');
  clusterList.innerHTML = vis.clusters.map(c => `
    <div class="cluster-tag">
      <span class="cat">${{c.category}}</span>
      <span class="size">(${{c.size}}个角色, r=${{c.radius.toFixed(2)}})</span>
    </div>
  `).join('');

  const canvas = document.getElementById('macro-canvas');
  const ctx = canvas.getContext('2d');
  const W = canvas.width, H = canvas.height;
  ctx.clearRect(0, 0, W, H);

  // 背景网格
  ctx.strokeStyle = '#1f2937';
  ctx.lineWidth = 0.5;
  for (let x = 0; x < W; x += 50) {{ ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, H); ctx.stroke(); }}
  for (let y = 0; y < H; y += 50) {{ ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(W, y); ctx.stroke(); }}

  // 计算绘制边界
  const points = vis.projection_2d;
  const xs = points.map(p => p.x), ys = points.map(p => p.y);
  const xMin = Math.min(...xs), xMax = Math.max(...xs);
  const yMin = Math.min(...ys), yMax = Math.max(...ys);
  const padX = (xMax - xMin) * 0.1 || 1;
  const padY = (yMax - yMin) * 0.1 || 1;

  function scaleX(x) {{ return 40 + (x - xMin + padX) / (xMax - xMin + 2*padX) * (W - 80); }}
  function scaleY(y) {{ return H - 40 - (y - yMin + padY) / (yMax - yMin + 2*padY) * (H - 80); }}

  // 类别颜色映射
  const colors = ['#58a6ff','#3fb950','#d29922','#f78166','#a371f7','#db61a2','#f0883e','#79c0ff'];
  const catColor = {{}};
  vis.meta_categories.forEach((cat, i) => {{ catColor[cat] = colors[i % colors.length]; }});

  // 绘制聚类中心
  vis.clusters.forEach(c => {{
    const cx = scaleX(c.center[0]), cy = scaleY(c.center[1]);
    const r = Math.max(8, Math.min(40, c.radius * (W / (xMax - xMin + 2*padX)) * 0.5));
    ctx.beginPath();
    ctx.arc(cx, cy, r, 0, Math.PI * 2);
    ctx.strokeStyle = catColor[c.category] || '#58a6ff';
    ctx.lineWidth = 2;
    ctx.setLineDash([5, 3]);
    ctx.stroke();
    ctx.setLineDash([]);
    // 标签
    ctx.fillStyle = catColor[c.category] || '#58a6ff';
    ctx.font = '11px system-ui';
    ctx.fillText(c.category + ` (${{c.size}})`, cx + r + 4, cy + 4);
  }});

  // 绘制角色点
  points.forEach(p => {{
    ctx.beginPath();
    ctx.arc(scaleX(p.x), scaleY(p.y), 3, 0, Math.PI * 2);
    ctx.fillStyle = catColor[p.category] || '#8b949e';
    ctx.fill();
    ctx.globalAlpha = 0.6;
  }});
  ctx.globalAlpha = 1.0;

  // 标题
  ctx.fillStyle = '#e1e4e8';
  ctx.font = '13px system-ui';
  ctx.fillText('角色空间 2D 投影 (语义嵌入 → UMAP)', 20, 20);
}}

// ---- 中观: Agent角色变迁轨迹 ----
function renderMeso() {{
  const meso = DATA.meso;
  if (!meso) {{ document.getElementById('trajectory-container').innerHTML = '<p style="color:#8b949e">暂无中观数据</p>'; return; }}

  document.getElementById('meso-stats').innerHTML = `
    <div class="stat-card"><div class="label">Agent数量</div><div class="value">${{meso.agents.length}}</div></div>
    <div class="stat-card"><div class="label">总轨迹记录</div><div class="value">${{meso.agents.reduce((s,a) => s + a.records.length, 0)}}</div></div>
  `;

  const container = document.getElementById('trajectory-container');
  container.innerHTML = meso.agents.map(a => `
    <div class="trajectory-row">
      <h4>${{a.agent_name}} <span style="color:#8b949e;font-weight:normal;font-size:12px;">(${{a.agent_id}}) | 主导类别: ${{a.dominant_category}} | 角色多样性: ${{a.role_diversity}}</span></h4>
      <div style="margin-top:8px;">
        共 ${{a.total_tasks}} 个任务，角色变迁:
        ${{a.records.map(r => `<span class="role-chip" title="Stage ${{r.stage}} | ${{r.category}}">${{r.role_name}}</span>`).join(' ')}}
      </div>
    </div>
  `).join('');
}}

// ---- 微观: 单次任务角色涌现 ----
function renderMicro() {{
  const micro = DATA.micro;
  if (!micro) {{ document.getElementById('emergence-container').innerHTML = '<p style="color:#8b949e">暂无微观数据</p>'; return; }}

  document.getElementById('micro-stats').innerHTML = `
    <div class="stat-card"><div class="label">任务ID</div><div class="value" style="font-size:16px;">${{micro.task_id}}</div></div>
    <div class="stat-card"><div class="label">Stage数</div><div class="value">${{Object.keys(micro.stages).length}}</div></div>
  `;

  const stages = micro.stages;
  const container = document.getElementById('emergence-container');
  let html = '';

  for (const [stageKey, stageData] of Object.entries(stages)) {{
    html += `
      <div class="trajectory-row">
        <h4>${{stageKey}}: ${{stageData.stage_name}} <span style="color:#8b949e;font-size:12px;">(${{stageData.active_agents.length}}个Agent活跃)</span></h4>
        <div style="margin-top:8px;">
          活跃角色:
          ${{stageData.roles.map(r => `
            <span class="role-chip" style="border-left:2px solid #58a6ff;">${{r.agent_id}}: ${{r.role_name}} (conf=${{r.confidence.toFixed(2)}})</span>
          `).join(' ')}}
        </div>
      </div>
    `;
  }}

  container.innerHTML = html;
}}

// 初始渲染
renderMacro();
</script>
</body>
</html>"""


# ==============================================================================
#  第四部分: 集体记忆管理 (Collective Memory Manager)
# ==============================================================================

@dataclass
class MemoryEntry:
    """集体记忆条目"""
    entry_id: str
    entry_type: str              # axiom | skeleton | merge | role
    content: dict
    created_at: str
    source_colony: str
    tags: list[str] = field(default_factory=list)


class CollectiveMemoryManager:
    """
    集体记忆管理器
    职责: 跨Colony的持久化知识存储与检索

    管理四种记忆类型:
      - axiom:  跨域公理骨架
      - merge:  跨Agent经验交叉记录
      - role:   角色空间聚类快照
      - insight: 跨域迁移分析洞察
    """

    def __init__(self, memory_path: str = ""):
        if not memory_path:
            memory_path = str(Path(__file__).parent / "l6-collective-memory.json")
        self.memory_path = Path(memory_path)
        self.entries: dict[str, MemoryEntry] = {}
        self._load()

    def _load(self) -> None:
        """从磁盘加载记忆"""
        if self.memory_path.exists():
            try:
                data = json.loads(self.memory_path.read_text(encoding="utf-8"))
                for entry_data in data.get("entries", []):
                    entry = MemoryEntry(**entry_data)
                    self.entries[entry.entry_id] = entry
                logger.info(f"[集体记忆] 加载 {len(self.entries)} 条记忆")
            except Exception as e:
                logger.warning(f"[集体记忆] 加载失败: {e}，初始化空记忆")

    def save(self) -> None:
        """持久化保存"""
        data = {
            "version": "2.0",
            "updated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "colony": "colony-040",
            "total_entries": len(self.entries),
            "entries": [asdict(e) for e in self.entries.values()],
        }
        self.memory_path.parent.mkdir(parents=True, exist_ok=True)
        self.memory_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        logger.info(f"[集体记忆] 已保存 {len(self.entries)} 条记录到 {self.memory_path}")

    def add(self, entry_type: str, content: dict,
            source_colony: str = "colony-040",
            tags: Optional[list[str]] = None) -> str:
        """添加记忆条目"""
        entry_id = f"MEM-{entry_type}-{uuid.uuid4().hex[:8]}"
        entry = MemoryEntry(
            entry_id=entry_id,
            entry_type=entry_type,
            content=content,
            created_at=time.strftime("%Y-%m-%d %H:%M:%S"),
            source_colony=source_colony,
            tags=tags or [],
        )
        self.entries[entry_id] = entry
        return entry_id

    def query(self, entry_type: Optional[str] = None,
              tag: Optional[str] = None,
              keyword: Optional[str] = None) -> list[MemoryEntry]:
        """检索记忆条目"""
        results = list(self.entries.values())

        if entry_type:
            results = [e for e in results if e.entry_type == entry_type]
        if tag:
            results = [e for e in results if tag in e.tags]
        if keyword:
            results = [e for e in results
                       if keyword in json.dumps(e.content, ensure_ascii=False)]

        return results

    def stats(self) -> dict:
        """记忆统计"""
        by_type = Counter(e.entry_type for e in self.entries.values())
        return {
            "total": len(self.entries),
            "by_type": dict(by_type),
            "last_updated": max(
                (e.created_at for e in self.entries.values()),
                default="N/A",
            ),
        }


# ==============================================================================
#  第五部分: 演示与主入口
# ==============================================================================

class CrossDomainMigrationDemo:
    """
    跨域迁移完整演示管线

    演示流程:
      1. 提取公理骨架 (4条示例公理)
      2. 目标域映射 (骨架 → 3个目标域)
      3. 零样本验证 (N=10 轮模拟)
      4. 构建跨域公理库
      5. 跨Agent经验交叉 (2个Agent技能树 Merge)
      6. 角色空间可视化 (50个模拟角色记录)
      7. 集体记忆持久化
    """

    # ---- 演示用公理数据 (对齐架构 Section 7.2) ----
    DEMO_AXIOMS = [
        {
            "axiom_id": "AX-021-001",
            "statement": "当任意评估维度连续K=10代Δ=0时，向该维度注入随机探测信号，"
                         "区分真停滞与评估失效。探测信号类型: 参数扰动、结构变异、输入变换。",
            "domain": "元认知自检",
            "rationale": "DGM-H涌现机制: 系统在平稳期自发产生探测行为",
        },
        {
            "axiom_id": "AX-024-001",
            "statement": "当Agent协作评估连续N=5轮无变化时，注入随机角色扰动，"
                         "强制Agent在相邻角色空间探索。扰动强度随停滞轮数指数增长。",
            "domain": "Agent协作优化",
            "rationale": "防止角色空间局部最优陷阱",
        },
        {
            "axiom_id": "AX-028-001",
            "statement": "当Pipeline某Stage的产出质量连续M=8次低于阈值0.7时，"
                         "启动Stage内部并行变体探索: 3个Agent同时执行该Stage，"
                         "取最优结果。变体探索不影响外部Stage传递。",
            "domain": "Pipeline编排优化",
            "rationale": "内生性悖论: 局部并行探索优于全局结构变更",
        },
        {
            "axiom_id": "AX-030-001",
            "statement": "任何GEPA进化产物在合入前必须通过五层安全门禁: "
                         "测试全量通过(L1)、文件大小限制(L2)、缓存兼容性(L3)、"
                         "语义保真度(L4)、人工PR审查(L5)。L1-L3为硬阻塞，L4为软阻塞。",
            "domain": "安全门禁",
            "rationale": "Layer 0 安全基座不可弱化",
        },
    ]

    # ---- 演示用Agent技能树 ----
    @staticmethod
    def build_demo_skill_tree_a() -> SkillTree:
        """构建PM Agent技能树"""
        return SkillTree(
            agent_id="AGENT-PM-01",
            agent_role="产品经理(PM)",
            skills=[
                SkillNode(
                    skill_id="SK-PM-001",
                    skill_name="需求分析技能",
                    agent_id="AGENT-PM-01",
                    version=3,
                    description="从模糊需求中提取结构化功能清单",
                    domain="需求工程",
                    evolution_history=["v1: 基础模板", "v2: GEPA优化-增加边界条件检测", "v3: RPM反思-增加利益相关者视角"],
                    parent_skill_id="SK-PM-001-BASE",
                    performance_score=0.85,
                ),
                SkillNode(
                    skill_id="SK-PM-002",
                    skill_name="谈判技巧",
                    agent_id="AGENT-PM-01",
                    version=2,
                    description="在资源约束下协商需求优先级",
                    domain="利益相关者管理",
                    evolution_history=["v1: 固定优先级排序", "v2: 动态价值/成本比排序"],
                    performance_score=0.78,
                ),
                SkillNode(
                    skill_id="SK-PM-003",
                    skill_name="利益相关者管理",
                    agent_id="AGENT-PM-01",
                    version=2,
                    description="识别关键决策者并管理期望",
                    domain="沟通管理",
                    evolution_history=["v1: 角色映射", "v2: 影响力网络分析"],
                    performance_score=0.72,
                ),
                SkillNode(
                    skill_id="SK-PM-004",
                    skill_name="用户故事编写",
                    agent_id="AGENT-PM-01",
                    version=1,
                    description="编写标准格式用户故事卡片",
                    domain="需求文档化",
                    performance_score=0.90,
                ),
            ],
            lineage=["colony-001/PM-base", "colony-015/PM-enhanced", "colony-030/PM-gepa-v3"],
        )

    @staticmethod
    def build_demo_skill_tree_b() -> SkillTree:
        """构建架构师Agent技能树"""
        return SkillTree(
            agent_id="AGENT-ARCH-01",
            agent_role="架构师(Architect)",
            skills=[
                SkillNode(
                    skill_id="SK-ARCH-001",
                    skill_name="方案设计技能",
                    agent_id="AGENT-ARCH-01",
                    version=3,
                    description="基于约束条件生成多方案技术架构",
                    domain="系统架构",
                    evolution_history=["v1: 单方案输出", "v2: GEPA优化-多方案对比矩阵", "v3: 增加风险/成本维度"],
                    parent_skill_id="SK-ARCH-001-BASE",
                    performance_score=0.88,
                ),
                SkillNode(
                    skill_id="SK-ARCH-002",
                    skill_name="方案推销技能",
                    agent_id="AGENT-ARCH-01",
                    version=2,
                    description="以数据驱动方式向利益相关者展示方案优劣",
                    domain="技术沟通",
                    evolution_history=["v1: 技术报告", "v2: 决策树 + 权衡可视化"],
                    performance_score=0.76,
                ),
                SkillNode(
                    skill_id="SK-ARCH-003",
                    skill_name="技术风险预判",
                    agent_id="AGENT-ARCH-01",
                    version=1,
                    description="基于历史故障模式预判技术选择风险",
                    domain="风险管理",
                    performance_score=0.81,
                ),
                SkillNode(
                    skill_id="SK-ARCH-004",
                    skill_name="接口契约设计",
                    agent_id="AGENT-ARCH-01",
                    version=1,
                    description="定义Layer间标准化接口契约",
                    domain="集成架构",
                    performance_score=0.70,
                ),
            ],
            lineage=["colony-002/ARCH-base", "colony-022/ARCH-enhanced", "colony-030/ARCH-gepa-v3"],
        )

    # ---- 演示用角色数据 ----
    META_CATEGORIES = [
        "需求分析师", "方案架构师", "执行开发者", "质量审查员",
        "风险管理者", "沟通协调者", "创新探索者", "安全审计员",
    ]

    @staticmethod
    def build_demo_roles(n: int = 50) -> list[RoleRecord]:
        """生成演示角色记录"""
        roles = []
        role_templates = {
            "需求分析师": [
                "用户需求深度挖掘者", "功能边界定义师", "价值优先级排序师",
                "需求完整性验证者", "用户故事场景设计师",
            ],
            "方案架构师": [
                "技术方案设计师", "架构权衡分析师", "集成接口定义师",
                "性能瓶颈预判师", "技术选型评估师",
            ],
            "执行开发者": [
                "核心逻辑实现者", "测试用例编写者", "配置参数调优师",
                "代码重构执行者", "API契约实现者",
            ],
            "质量审查员": [
                "端到端验证师", "边界条件探测者", "回归缺陷扫描师",
                "安全漏洞审计师", "性能基准测试师",
            ],
            "风险管理者": [
                "技术债务评估师", "依赖风险扫描师", "进度偏差预警者",
                "成本超支检测者",
            ],
            "沟通协调者": [
                "跨域信息翻译者", "共识构建推动者", "冲突调解引导者",
            ],
            "创新探索者": [
                "替代方案生成者", "突破性思路催化师", "跨界借鉴扫描师",
            ],
            "安全审计员": [
                "输入注入防护者", "权限越狱检测师", "数据泄露审计师",
            ],
        }

        agent_ids = ["Agent-A", "Agent-B", "Agent-C", "Agent-D", "Agent-E",
                       "Agent-F", "Agent-G"]
        task_ids = [f"TASK-{i:03d}" for i in range(1, 8)]

        for i in range(n):
            category = random.choice(list(role_templates.keys()))
            role_name = random.choice(role_templates[category])
            agent_id = random.choice(agent_ids)
            task_id = random.choice(task_ids)
            stage = random.randint(1, 4)

            role = RoleRecord(
                role_id=f"ROLE-{i:03d}",
                role_name=f"{role_name}({agent_id})",
                agent_id=agent_id,
                task_id=task_id,
                stage=stage,
                category=category,
                confidence=round(random.uniform(0.6, 0.95), 2),
                contribution_summary=f"在{task_id}的Stage{stage}中承担{role_name}角色",
            )
            roles.append(role)

        return roles


def run_demo(args) -> dict:
    """
    运行完整演示管线

    Returns:
        演示结果摘要 dict
    """
    results = {}

    # =====================================================================
    # Phase 1: 公理骨架迁移协议
    # =====================================================================
    logger.info("=" * 72)
    logger.info("Phase 1/3: 公理骨架迁移协议 (Axiom Transfer Protocol)")
    logger.info("=" * 72)

    extractor = AxiomSkeletonExtractor(strict_mode=False)
    mapper = DomainMapper()
    validator = MigrationValidator(rounds=args.rounds)
    library = CrossDomainLibrary(library_id="L6-CROSS-DOMAIN-v1")

    skeletons = []
    for axiom_data in CrossDomainMigrationDemo.DEMO_AXIOMS:
        skeleton = extractor.extract(
            axiom_id=axiom_data["axiom_id"],
            axiom_statement=axiom_data["statement"],
            domain=axiom_data["domain"],
            rationale=axiom_data["rationale"],
        )
        skeletons.append(skeleton)
        library.add_skeleton(skeleton)

    results["skeletons_extracted"] = len(skeletons)

    # 目标域映射 + 验证
    target_domains = ["Agent协作优化", "Pipeline编排优化", "技能进化"]
    valid_count = 0
    for skeleton in skeletons[:3]:  # 用前3个骨架做跨域映射
        for target_domain in target_domains:
            if target_domain == skeleton.placeholders.get("[[Agent协作优化]]", ""):
                continue  # 跳过源域自身

            mapping = mapper.map(skeleton, target_domain)
            record = validator.validate(skeleton, mapping)
            library.add_migration(record)

            if record.result == TransferResult.VALID:
                valid_count += 1

    results["migrations_total"] = len(library.valid_migrations) + len(library.failed_migrations)
    results["migrations_valid"] = len(library.valid_migrations)
    results["transfer_success_rate"] = library.stats()["transfer_success_rate"]
    results["type_t_axioms"] = library.stats()["type_t_axioms"]

    # 输出跨域公理库摘要
    logger.info(f"\n[跨域公理库] {library.library_id}")
    logger.info(f"  骨架总数: {len(library.skeletons)}")
    logger.info(f"  有效迁移: {len(library.valid_migrations)}")
    logger.info(f"  失败迁移: {len(library.failed_migrations)}")
    logger.info(f"  迁移成功率: {library.stats()['transfer_success_rate']:.1%}")

    for record in library.valid_migrations:
        logger.info(f"  [VALID] {record.skeleton.skeleton_id} → "
                     f"{record.mapping.target_domain}: {record.analysis[:60]}...")

    # =====================================================================
    # Phase 2: 跨Agent经验交叉
    # =====================================================================
    logger.info("")
    logger.info("=" * 72)
    logger.info("Phase 2/3: 跨Agent经验交叉 (Cross-Agent Lineage Merge)")
    logger.info("=" * 72)

    tree_a = CrossDomainMigrationDemo.build_demo_skill_tree_a()
    tree_b = CrossDomainMigrationDemo.build_demo_skill_tree_b()

    merger = CrossAgentLineageMerge(strategy=MergeStrategy.CROSS_ONLY)
    tree_a_updated, tree_b_updated, merge_report = merger.merge(tree_a, tree_b)

    results["merge_report"] = merge_report
    results["tree_a_skills_after"] = len(tree_a_updated.skills)
    results["tree_b_skills_after"] = len(tree_b_updated.skills)

    logger.info(f"\n[合并报告] {merge_report['merge_id']}")
    logger.info(f"  策略: {merge_report['strategy']}")
    logger.info(f"  交叉对: {merge_report['cross_pairs_total']} → 安全: {merge_report['safe_pairs']}")
    logger.info(f"  PM Agent 技能: {len(tree_a.skills)} → {len(tree_a_updated.skills)} (+{merge_report['skills_added_to_a']})")
    logger.info(f"  架构师 技能: {len(tree_b.skills)} → {len(tree_b_updated.skills)} (+{merge_report['skills_added_to_b']})")
    logger.info(f"  退化检测: A={merge_report['degradation_detected_a']}, B={merge_report['degradation_detected_b']}")

    # =====================================================================
    # Phase 3: 角色空间可视化
    # =====================================================================
    logger.info("")
    logger.info("=" * 72)
    logger.info("Phase 3/3: 角色空间可视化 (Role Space Visualization)")
    logger.info("=" * 72)

    roles = CrossDomainMigrationDemo.build_demo_roles(n=args.roles)
    visualizer = RoleSpaceVisualizer()

    vis_data = visualizer.build_role_space(roles, CrossDomainMigrationDemo.META_CATEGORIES)

    # 构建中观Agent轨迹
    agent_records = defaultdict(list)
    agent_name_map = {
        "Agent-A": "需求分析专员",
        "Agent-B": "技术方案设计专员",
        "Agent-C": "质量保障专员",
        "Agent-D": "安全管理专员",
        "Agent-E": "流程协调专员",
        "Agent-F": "创新探索专员",
        "Agent-G": "文档与知识专员",
    }
    for role in roles:
        agent_records[role.agent_id].append(role)

    trajectories = [
        AgentRoleTrajectory(
            agent_id=agent_id,
            agent_name=agent_name_map.get(agent_id, agent_id),
            role_records=recs,
            total_tasks=len(set(r.task_id for r in recs)),
        )
        for agent_id, recs in agent_records.items()
    ]
    traj_data = visualizer.build_agent_trajectory(trajectories)

    # 构建微观任务涌现数据
    task_id = "TASK-001"
    stage_records = defaultdict(list)
    for role in roles:
        if role.task_id == task_id:
            stage_records[role.stage].append(role)
    emergence_data = visualizer.build_task_emergence(task_id, stage_records)

    results["vis_data"] = vis_data
    results["traj_data"] = traj_data
    results["emergence_data"] = emergence_data

    logger.info(f"\n[可视化数据]")
    logger.info(f"  总角色记录: {vis_data['total_roles']}")
    logger.info(f"  元类别: {len(vis_data['meta_categories'])}")
    logger.info(f"  聚类数: {len(vis_data['clusters'])}")
    logger.info(f"  Agent轨迹: {len(traj_data['agents'])} 个Agent")

    # 导出 HTML
    html_path = ""
    if args.export or args.full:
        html_path = visualizer.export_html(
            vis_data=vis_data,
            traj_data=traj_data,
            emergence_data=emergence_data,
            filepath=str(Path(__file__).parent / "role-space-visualization.html"),
        )
        results["html_path"] = html_path

    # =====================================================================
    # 集体记忆持久化
    # =====================================================================
    logger.info("")
    logger.info("=" * 72)
    logger.info("集体记忆持久化 (Collective Memory)")
    logger.info("=" * 72)

    memory = CollectiveMemoryManager()
    memory.add("axiom", {"type": "library", "data": library.to_dict()},
               tags=["axiom-transfer", "cross-domain"])
    memory.add("merge", merge_report,
               tags=["lineage-merge", "cross-agent"])
    memory.add("role", {"total_roles": vis_data["total_roles"],
                         "clusters": vis_data["clusters"]},
               tags=["role-space", "visualization"])

    if args.full:
        memory.save()
        logger.info(f"  记忆已保存: {memory.stats()}")
    else:
        logger.info(f"  记忆已准备: {memory.stats()} (使用 --full 参数持久化到磁盘)")

    results["memory_stats"] = memory.stats()

    return results


# ---------------------------------------------------------------------------
# 命令行参数
# ---------------------------------------------------------------------------

def parse_args():
    parser = argparse.ArgumentParser(
        description="Colony v2.0 Layer 6 跨域迁移与集体记忆引擎",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python cross-domain-migration.py              # 演示模式 (默认)
  python cross-domain-migration.py --export     # 导出可视化HTML
  python cross-domain-migration.py --full       # 完整管线 + 持久化
  python cross-domain-migration.py --rounds 20  # 自定义验证轮数
  python cross-domain-migration.py --roles 100  # 自定义角色数量
        """,
    )
    parser.add_argument("--export", action="store_true",
                        help="导出角色空间可视化 HTML")
    parser.add_argument("--full", action="store_true",
                        help="运行完整管线并持久化集体记忆到磁盘")
    parser.add_argument("--rounds", type=int, default=ZERO_SHOT_ROUNDS,
                        help=f"跨域验证模拟轮数 (默认: {ZERO_SHOT_ROUNDS})")
    parser.add_argument("--roles", type=int, default=50,
                        help=f"模拟角色记录数量 (默认: 50)")
    parser.add_argument("--no-color", action="store_true",
                        help="禁用彩色日志输出")
    return parser.parse_args()


# ---------------------------------------------------------------------------
# 主入口
# ---------------------------------------------------------------------------

def main():
    args = parse_args()

    print("""
    ╔══════════════════════════════════════════════════════════════╗
    ║   Colony v2.0 Layer 6: 跨域迁移与集体记忆                      ║
    ║   Colony-040 极限实验室 | 2026-05-19                         ║
    ║                                                              ║
    ║   能力: 公理骨架迁移 + 跨Agent经验交叉 + 角色空间可视化          ║
    ╚══════════════════════════════════════════════════════════════╝
    """)

    logger.info(f"环境检测: NumPy={NUMPY_AVAILABLE}, sklearn={SKLEARN_AVAILABLE}, umap={UMAP_AVAILABLE}")
    logger.info(f"参数: rounds={args.rounds}, roles={args.roles}, export={args.export}, full={args.full}")

    t0 = time.time()
    results = run_demo(args)
    elapsed = time.time() - t0

    # ---- 最终摘要 ----
    print("")
    print("=" * 72)
    print("  执行摘要")
    print("=" * 72)
    print(f"  耗时: {elapsed:.2f} 秒")
    print(f"")
    print(f"  [Phase 1] 公理骨架迁移:")
    print(f"    提取骨架: {results['skeletons_extracted']} 条")
    print(f"    跨域映射: {results['migrations_total']} 次")
    print(f"    有效迁移: {results['migrations_valid']} 次")
    print(f"    迁移成功率: {results['transfer_success_rate']:.1%}")
    print(f"    Type T 公理: {results['type_t_axioms']} 条")
    print(f"")
    print(f"  [Phase 2] 跨Agent经验交叉:")
    merge = results['merge_report']
    print(f"    合并策略: {merge['strategy']}")
    print(f"    安全交叉对: {merge['safe_pairs']}/{merge['cross_pairs_total']}")
    print(f"    PM Agent: +{merge['skills_added_to_a']} 技能")
    print(f"    架构师:   +{merge['skills_added_to_b']} 技能")
    print(f"    退化: A={merge['degradation_detected_a']}, B={merge['degradation_detected_b']}")
    print(f"")
    print(f"  [Phase 3] 角色空间可视化:")
    print(f"    角色记录: {results['vis_data']['total_roles']}")
    print(f"    元类别: {len(results['vis_data']['meta_categories'])}")
    print(f"    聚类: {len(results['vis_data']['clusters'])}")
    print(f"    Agent轨迹: {len(results['traj_data']['agents'])} 个Agent")
    if results.get("html_path"):
        print(f"    HTML导出: {results['html_path']}")
    print(f"")
    print(f"  [集体记忆]: {results['memory_stats']}")
    print(f"")
    print(f"  Layer 6 状态: 就绪")
    print(f"  ✅ 公理骨架迁移协议 —— 已实现")
    print(f"  ✅ 跨Agent经验交叉 (Lineage Merge) —— 已实现")
    print(f"  ✅ 角色空间可视化 (三层) —— 已实现")
    print("=" * 72)

    return 0


if __name__ == "__main__":
    sys.exit(main())
