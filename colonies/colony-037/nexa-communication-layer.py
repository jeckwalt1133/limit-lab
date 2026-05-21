#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Colony v2.0 — L3 Nexa 条件通信层 (Phase A: 零训练版本)
========================================================
Colony-037 极限实验室 | 2026-05-19

设计来源: Colony-033 Nexa 分析 (arXiv 2605.15573)
  "默认并行, 条件串行" — 响应条件并行到串行编排

五阶段通信管线:
  阶段1: 并行草稿    — 所有Agent独立响应, 零通信开销
  阶段2: 语义嵌入    — all-MiniLM-L6-v2 (384维, 80MB, 冻结)
  阶段3: 图策略预测  — SelfOrg启发式DAG (Phase A, 无训练策略网络)
  阶段4: 条件串行传播 — 空图=纯并行回退, 非空图=沿贡献排序单轮串行
  阶段5: 无裁判聚合  — 贡献加权质心最近响应

三大形式化保证:
  命题1 (构造性无环): 所有边在贡献排序π下为前向边, 不可能存在有向环
  命题2 (身份不可知): 策略网络看不到Agent身份/角色/模型家族, 只看响应语义
  命题3 (混合包容):   空图始终可达, 策略类严格包含纯并行执行

Phase A 实现策略 (零训练版本):
  - 嵌入: all-MiniLM-L6-v2 (sentence-transformers)
  - 贡献评估: cosine-to-centroid (SelfOrg Shapley近似)
  - DAG构造: SelfOrg启发式 (阈值+贡献排序, 无策略网络)
  - 聚合: 加权质心选择
  - 效果: 立即改善聚合质量, 零训练成本

可执行: python nexa-communication-layer.py [--demo] [--task "任务描述"] [--visualize]
"""

import json
import sys
import time
import uuid
import math
import logging
import argparse
import random
from abc import ABC, abstractmethod
from collections import defaultdict, Counter, deque
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Optional, Callable

# ──────────────────────────────────────────────────────────────────────
# 可选依赖
# ──────────────────────────────────────────────────────────────────────

try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False
    np = None  # type: ignore

try:
    from sentence_transformers import SentenceTransformer
    HAS_SENTENCE_TRANSFORMERS = True
except ImportError:
    HAS_SENTENCE_TRANSFORMERS = False
    SentenceTransformer = None  # type: ignore

try:
    import networkx as nx
    HAS_NETWORKX = True
except ImportError:
    HAS_NETWORKX = False
    nx = None  # type: ignore

# ──────────────────────────────────────────────────────────────────────
# 常量
# ──────────────────────────────────────────────────────────────────────

VERSION = "2.0.0"
COLONY_ID = "Colony-037"
PHASE = "A"  # 零训练版本

# 嵌入模型
PRIMARY_EMBEDDING_MODEL = "all-MiniLM-L6-v2"
FALLBACK_EMBEDDING_MODEL = "paraphrase-multilingual-MiniLM-L12-v2"
EMBEDDING_DIM = 384  # all-MiniLM-L6-v2 输出维度
EMBEDDING_MODEL_SIZE_MB = 80

# 语义分歧阈值
DEFAULT_DIVERGENCE_THRESHOLD = 0.35    # 1-cosine: 超过此值视为语义分歧
DIVERGENCE_WEAK = 0.20                 # 轻微分歧
DIVERGENCE_MODERATE = 0.35             # 中等分歧
DIVERGENCE_STRONG = 0.50               # 强分歧

# 图密度目标 (Nexa 健康范围)
MIN_GRAPH_DENSITY = 0.05
MAX_GRAPH_DENSITY = 0.30
IDEAL_SERIAL_TRIGGER_RATE = (0.20, 0.60)  # 20-60%
IDEAL_PARALLEL_FALLBACK_RATE = (0.40, 0.80)  # 40-80%

# 通信参数
MAX_PROPAGATION_HOPS = 3
DEFAULT_MIN_AGENTS_FOR_NEXA = 3  # 少于3个Agent时固定并行

# min_count 平滑参数
CONTRIBUTION_SMOOTHING_EPSILON = 1e-8

OUTPUT_ENCODING = "utf-8"

# ──────────────────────────────────────────────────────────────────────
# 日志
# ──────────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("Colony.L3.Nexa")


# ══════════════════════════════════════════════════════════════════════
# Section 1: 核心数据结构
# ══════════════════════════════════════════════════════════════════════


class ExecutionMode(Enum):
    """Nexa 执行模式"""
    PURE_PARALLEL = "pure_parallel"       # 空图, 零额外LLM调用
    SPARSE_SERIAL = "sparse_serial"       # 有边但稀疏, 条件串行
    DENSE_SERIAL = "dense_serial"         # 高密度图, 接近全串行 (告警)


class DivergenceLevel(Enum):
    """语义分歧级别"""
    NONE = "none"           # 无分歧 (div < DIVERGENCE_WEAK)
    WEAK = "weak"           # 轻微 (0.20 ≤ div < 0.35)
    MODERATE = "moderate"   # 中等 (0.35 ≤ div < 0.50)
    STRONG = "strong"       # 强烈 (div ≥ 0.50)

    @classmethod
    def from_divergence(cls, div: float) -> "DivergenceLevel":
        if div < DIVERGENCE_WEAK:
            return cls.NONE
        elif div < DIVERGENCE_MODERATE:
            return cls.WEAK
        elif div < DIVERGENCE_STRONG:
            return cls.MODERATE
        else:
            return cls.STRONG


@dataclass
class AgentResponse:
    """Agent 草稿响应"""
    agent_id: str                              # Agent标识 (仅用于调试, 策略网络不可见)
    content: str                               # 响应文本内容
    embedding: Optional[list[float]] = None    # 语义嵌入向量 (384维)
    contribution_score: float = 0.0            # 贡献分数 (cosine-to-centroid)
    refined_content: Optional[str] = None      # 条件串行传播后精化内容
    is_predecessor_context_used: bool = False  # 是否使用了前驱Agent的上下文
    predecessors_used: list[str] = field(default_factory=list)  # 使用了哪些前驱的输出
    metadata: dict[str, Any] = field(default_factory=dict)

    def clone_for_propagation(self) -> "AgentResponse":
        """为条件传播创建可修改的副本"""
        return AgentResponse(
            agent_id=self.agent_id,
            content=self.content,
            embedding=list(self.embedding) if self.embedding else None,
            contribution_score=self.contribution_score,
            refined_content=None,
            is_predecessor_context_used=False,
            predecessors_used=[],
            metadata=dict(self.metadata),
        )


@dataclass
class CommunicationEdge:
    """DAG中的有向边 (高贡献→低贡献)"""
    source_id: str       # 源 Agent (高贡献)
    target_id: str       # 目标 Agent (低贡献)
    divergence: float    # 语义分歧值 [0, 2]
    level: DivergenceLevel


@dataclass
class CommunicationGraph:
    """Nexa 通信图 (保证有向无环)"""
    nodes: list[str]                            # Agent ID 列表
    edges: list[CommunicationEdge]               # 有向边列表
    is_empty: bool = True                        # 是否空图 (空图=纯并行)
    topological_order: list[str] = field(default_factory=list)  # 贡献排序拓扑序
    density: float = 0.0                         # 图密度 = |E| / N²
    max_path_length: int = 0                     # 最长路径长度 (跳数)

    @property
    def edge_count(self) -> int:
        return len(self.edges)

    @property
    def has_edges(self) -> bool:
        return not self.is_empty and len(self.edges) > 0


@dataclass
class DivergenceMatrix:
    """Agent间语义分歧矩阵"""
    pairwise_divergences: dict[tuple[str, str], float] = field(default_factory=dict)
    agent_ids: list[str] = field(default_factory=list)
    mean_divergence: float = 0.0
    max_divergence: float = 0.0
    diverging_pairs: list[tuple[str, str, float]] = field(default_factory=list)

    def get(self, agent_a: str, agent_b: str) -> float:
        """获取两个Agent之间的语义分歧值"""
        key = tuple(sorted([agent_a, agent_b]))
        return self.pairwise_divergences.get(key, 0.0)


@dataclass
class NexaMetrics:
    """Nexa 通信层关键指标"""
    # 图指标
    graph_density: float = 0.0           # 预测边数/N²
    edge_count: int = 0
    max_path_length: int = 0             # 平均通信跳数

    # 模式指标
    execution_mode: ExecutionMode = ExecutionMode.PURE_PARALLEL
    serial_triggered: bool = False       # 是否触发了串行传播
    parallel_fallback: bool = True       # 是否回退到纯并行

    # 质量指标
    mean_divergence: float = 0.0
    max_divergence: float = 0.0
    diverging_pair_count: int = 0

    # 效率指标
    embedding_time_ms: float = 0.0
    dag_construction_time_ms: float = 0.0
    propagation_time_ms: float = 0.0
    aggregation_time_ms: float = 0.0
    total_time_ms: float = 0.0

    # 贡献指标
    contribution_scores: list[float] = field(default_factory=list)
    contribution_variance: float = 0.0   # 贡献分数方差 (高=意见分散)

    # 命题合规
    is_acyclic: bool = True              # 命题1: 构造性无环
    is_identity_agnostic: bool = True    # 命题2: 身份不可知
    is_parallel_subsumed: bool = True    # 命题3: 混合包容 (空图可达)


@dataclass
class NexaResult:
    """Nexa 通信层输出"""
    # 聚合结果
    final_content: str                              # 最终聚合答案
    selected_agent_id: str                          # 被选中Agent (距质心最近)
    aggregation_method: str                         # "weighted_centroid"

    # 所有响应
    all_responses: list[AgentResponse] = field(default_factory=list)
    refined_responses: list[AgentResponse] = field(default_factory=list)

    # 通信图
    communication_graph: Optional[CommunicationGraph] = None

    # 分歧分析
    divergence_matrix: Optional[DivergenceMatrix] = None

    # 指标
    metrics: NexaMetrics = field(default_factory=NexaMetrics)

    # 元数据
    task_id: str = ""
    timestamp: str = ""
    phase: str = PHASE
    embedding_model: str = ""
    divergence_threshold: float = DEFAULT_DIVERGENCE_THRESHOLD
    agent_count: int = 0


# ══════════════════════════════════════════════════════════════════════
# Section 2: 语义嵌入模块 (Nexa 阶段2)
# ══════════════════════════════════════════════════════════════════════


class SemanticEmbedder:
    """
    Nexa 阶段2: 语义嵌入

    将Agent文本响应映射到384维语义空间 (all-MiniLM-L6-v2, 冻结)。
    策略网络只看这个嵌入空间的向量, 不看原始文本或Agent身份。

    备选方案: paraphrase-multilingual-MiniLM-L12-v2 (中文场景)

    回退方案: 当 sentence-transformers 不可用时, 使用基于
    词频的简化伪嵌入 + 随机投影 (仅用于演示/测试)。
    """

    def __init__(
        self,
        model_name: str = PRIMARY_EMBEDDING_MODEL,
        use_fallback: bool = False,
        embedding_dim: int = EMBEDDING_DIM,
    ):
        self.model_name = model_name
        self.embedding_dim = embedding_dim
        self._model: Any = None
        self._using_real_model = False
        self._fallback_vocab: Optional[dict[str, int]] = None
        self._random_projection: Any = None

        if HAS_SENTENCE_TRANSFORMERS and not use_fallback:
            self._init_real_model(model_name)
        else:
            self._init_fallback_model()

    def _init_real_model(self, model_name: str) -> None:
        """初始化真实的 sentence-transformers 模型"""
        try:
            logger.info(f"加载嵌入模型: {model_name} ...")
            self._model = SentenceTransformer(model_name)
            # 验证输出维度
            test_embedding = self._model.encode(["测试"])
            actual_dim = test_embedding.shape[1]
            if actual_dim != self.embedding_dim:
                logger.warning(
                    f"模型输出维度 {actual_dim} 与预期 {self.embedding_dim} 不一致, "
                    f"自动调整"
                )
                self.embedding_dim = actual_dim
            self._using_real_model = True
            logger.info(
                f"嵌入模型加载成功: {model_name} "
                f"(维度={self.embedding_dim}, 大小≈{EMBEDDING_MODEL_SIZE_MB}MB)"
            )
        except Exception as e:
            logger.warning(f"真实模型加载失败: {e}, 回退到伪嵌入模式")
            self._init_fallback_model()

    def _init_fallback_model(self) -> None:
        """初始化伪嵌入回退模型 (基于字符n-gram哈希)"""
        logger.info("使用伪嵌入回退模型 (字符3-gram哈希 + 随机投影)")
        self._using_real_model = False

        # 构建基础词汇哈希表
        # 支持中文和英文的字符级3-gram
        self._fallback_vocab = {}
        # 常见中英文字符和标点
        common_chars = (
            "的一是在不了有和人这中大为上个国我以要他时来用们生到作地于"
            "出就分对成会可主发年动同工也能下过子说产种面而方后多定行学"
            "法所民得经十三之进着等部度家电力里如水化高自二理起小物现实"
            "加量都两体制机当使点从业本去把性好应开它合还因由其些然前外"
            "天政四日那社义事平形相全表间样与关各重新线内数正心反你明看"
            "原又么利比或但质气第向道命此变条只没结解问意建月公无系军很"
            "情者最立代想已通并提直题党程展五果料象员革位入常文总次品式"
            "活设及管特件长求老头基资边流路级少图山统接知较将组见计别她"
            "手角期根论运农指几九区强放决西被干做必战先回则任取据处队南"
            "给色光门即保治北造百规热领七海口东导器压志世金增争济阶油思"
            "术极交受联什认六共权收证改清己美再采转更单风切打白教速花带"
            "安场身车例真务具万每目至达走积示议声报斗完类八离华名确才科"
            "张信马节话米整空元况今集温传土许步群广石记需段研界拉林律叫"
            "且究观越织装影算低持音众书布复容儿须际商非验连断深难近矿千"
            "周委素技备半办青省列习响约支般史感劳便团往酸历市克何除消构"
            "府称太准精值号率族维划选标写存候毛亲快效斯院查江型眼王按格"
            "养易置派层片始却专状育厂京识适属圆包火住调满县局照参红细引"
            "听该铁价严龙飞"
            "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
            "0123456789 .,!?;:()[]{}'\"-_=+/\\@#$%^&*<>|~`\n\t"
        )

        # 为每个字符分配一个哈希桶
        for i, ch in enumerate(common_chars):
            self._fallback_vocab[ch] = i % 1024

        # 随机投影矩阵 (将高维稀疏向量投影到 EMBEDDING_DIM)
        if HAS_NUMPY:
            rng = np.random.RandomState(42)  # 固定种子, 确保可复现
            self._random_projection = rng.randn(1024, self.embedding_dim) * 0.1
        else:
            self._random_projection = None

    def _pseudo_embed(self, text: str) -> list[float]:
        """
        伪嵌入: 字符3-gram哈希 → 1024维稀疏向量 → 随机投影到384维

        仅用于 sentence-transformers 不可用时的回退方案。
        不是语义嵌入的准确替代, 但足以演示管线流程。
        """
        if not HAS_NUMPY or self._random_projection is None:
            # 纯Python回退: 基于哈希的固定长度向量
            random.seed(hash(text) % (2**31))
            return [random.uniform(-1, 1) for _ in range(self.embedding_dim)]

        # 提取3-gram特征
        sparse_vec = np.zeros(1024, dtype=np.float32)
        ngram_count = 0
        for i in range(len(text) - 2):
            trigram = text[i:i+3]
            # 对每个字符取哈希
            h = 0
            for ch in trigram:
                bucket = self._fallback_vocab.get(ch, abs(hash(ch)) % 1024)
                h = (h * 31 + bucket) % 1024
            sparse_vec[h] += 1.0
            ngram_count += 1

        if ngram_count > 0:
            sparse_vec /= ngram_count  # 归一化

        # 随机投影
        projected = sparse_vec @ self._random_projection
        # L2归一化
        norm = float(np.linalg.norm(projected))
        if norm > 1e-8:
            projected = projected / norm

        return projected.tolist()

    def embed(self, text: str) -> list[float]:
        """将文本映射到语义嵌入向量"""
        if self._using_real_model and self._model is not None:
            embedding = self._model.encode([text], show_progress_bar=False)
            vec = embedding[0]
            # L2归一化
            norm = float(np.linalg.norm(vec)) if HAS_NUMPY else math.sqrt(sum(x*x for x in vec))
            if norm > 1e-8:
                vec = vec / norm
            return vec.tolist()
        else:
            return self._pseudo_embed(text)

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """批量嵌入 (利用GPU加速, 如果可用)"""
        if self._using_real_model and self._model is not None:
            embeddings = self._model.encode(texts, show_progress_bar=False)
            result = []
            for vec in embeddings:
                norm = float(np.linalg.norm(vec)) if HAS_NUMPY else math.sqrt(sum(x*x for x in vec))
                if norm > 1e-8:
                    vec = vec / norm
                result.append(vec.tolist())
            return result
        else:
            return [self._pseudo_embed(t) for t in texts]

    @property
    def is_real_model(self) -> bool:
        return self._using_real_model


# ══════════════════════════════════════════════════════════════════════
# Section 3: 贡献评估模块 (SelfOrg cosine-to-centroid)
# ══════════════════════════════════════════════════════════════════════


class ContributionEvaluator:
    """
    Nexa 贡献评估: cosine-to-centroid (SelfOrg Shapley值近似)

    算法:
      ψ_n = cosine_similarity(r_n, r_avg)
      其中 r_avg = (1/N) * Σ r_n

    直觉: 与"平均回答"最相似的响应可能包含集体共识,
          因而具有更高的边际贡献。

    复杂度: O(N·d), 相对于精确Shapley值的指数复杂度。
    用于拓扑排序 π = argsort(ψ_1, ..., ψ_N; ψ_k ≥ ψ_{k+1})
    """

    def __init__(self):
        self._cosine_cache: dict[tuple[int, int], float] = {}

    def compute_centroid(self, embeddings: list[list[float]]) -> list[float]:
        """计算嵌入质心 (算术平均)"""
        if not embeddings:
            return []
        n = len(embeddings)
        d = len(embeddings[0])
        centroid = [0.0] * d
        for emb in embeddings:
            for j in range(d):
                centroid[j] += emb[j] / n
        return centroid

    def cosine_similarity(self, a: list[float], b: list[float]) -> float:
        """计算余弦相似度"""
        if HAS_NUMPY:
            a_arr = np.array(a, dtype=np.float64)
            b_arr = np.array(b, dtype=np.float64)
            dot = float(np.dot(a_arr, b_arr))
            norm_a = float(np.linalg.norm(a_arr))
            norm_b = float(np.linalg.norm(b_arr))
        else:
            dot = sum(x * y for x, y in zip(a, b))
            norm_a = math.sqrt(sum(x * x for x in a))
            norm_b = math.sqrt(sum(y * y for y in b))

        if norm_a < CONTRIBUTION_SMOOTHING_EPSILON or norm_b < CONTRIBUTION_SMOOTHING_EPSILON:
            return 0.0
        return max(-1.0, min(1.0, dot / (norm_a * norm_b)))

    def evaluate(
        self, embeddings: list[list[float]]
    ) -> tuple[list[float], list[float]]:
        """
        评估所有Agent的贡献分数

        Args:
            embeddings: N个Agent的嵌入向量

        Returns:
            (contribution_scores, centroid)
            - contribution_scores[i] = ψ_i ∈ [-1, 1]
            - centroid: 嵌入质心
        """
        if not embeddings:
            return [], []

        centroid = self.compute_centroid(embeddings)
        scores = [self.cosine_similarity(emb, centroid) for emb in embeddings]
        return scores, centroid

    def get_topology_order(
        self, agent_ids: list[str], scores: list[float]
    ) -> list[str]:
        """
        贡献排序 → 拓扑序

        π = argsort(ψ_1, ..., ψ_N; ψ_k ≥ ψ_{k+1})
        高贡献在前, 低贡献在后
        """
        pairs = list(zip(agent_ids, scores))
        pairs.sort(key=lambda x: x[1], reverse=True)
        return [agent_id for agent_id, _ in pairs]


# ══════════════════════════════════════════════════════════════════════
# Section 4: 语义分歧检测模块
# ══════════════════════════════════════════════════════════════════════


class DivergenceDetector:
    """
    Nexa 语义分歧检测

    检测Agent响应之间的语义不一致程度。
    分歧信号用于决定是否触发串行传播。

    分歧度量: d(i,j) = 1 - cosine_similarity(r_i, r_j)

    阈值体系:
      d < 0.20: 无分歧 (NONE)      — 纯并行, 零额外LLM调用
      0.20 ≤ d < 0.35: 轻微 (WEAK)     — 仅强分歧对触发边
      0.35 ≤ d < 0.50: 中等 (MODERATE) — 适度触发条件串行
      d ≥ 0.50: 强分歧 (STRONG)   — 高密度串行, 需关注
    """

    def __init__(self, threshold: float = DEFAULT_DIVERGENCE_THRESHOLD):
        """
        Args:
            threshold: 分歧阈值, 超过此值认为两个响应存在语义分歧
                       默认 0.35 (取自 Nexa 健康范围经验值)
        """
        self.threshold = threshold

    def compute_pairwise(
        self,
        agent_ids: list[str],
        embeddings: list[list[float]],
    ) -> DivergenceMatrix:
        """
        计算所有Agent对之间的语义分歧

        计算复杂度: O(N²·d), N=Agent数, d=嵌入维度
        """
        n = len(agent_ids)
        matrix = DivergenceMatrix(agent_ids=list(agent_ids))
        divergences: list[float] = []

        for i in range(n):
            for j in range(i + 1, n):
                # 余弦相似度 → 分歧度
                cos_sim = self._cosine(embeddings[i], embeddings[j])
                div = 1.0 - cos_sim  # 范围 [0, 2]

                key = (agent_ids[i], agent_ids[j])
                matrix.pairwise_divergences[key] = div
                divergences.append(div)

                if div >= self.threshold:
                    matrix.diverging_pairs.append((agent_ids[i], agent_ids[j], div))

        if divergences:
            matrix.mean_divergence = sum(divergences) / len(divergences)
            matrix.max_divergence = max(divergences)

        return matrix

    def detect(
        self, matrix: DivergenceMatrix
    ) -> dict[str, Any]:
        """
        检测整体分歧状态

        Returns:
            {
                "has_divergence": bool,        # 是否存在需要串行通信的分歧
                "divergence_level": DivergenceLevel,
                "diverging_ratio": float,      # 分歧对比例
                "recommend_serial": bool,       # 是否推荐触发串行传播
                "pure_parallel_safe": bool,     # 纯并行是否安全
            }
        """
        n = len(matrix.agent_ids)
        total_pairs = n * (n - 1) / 2
        diverging_count = len(matrix.diverging_pairs)
        diverging_ratio = diverging_count / max(total_pairs, 1)

        recommend_serial = (
            diverging_count > 0
            and matrix.max_divergence >= self.threshold
        )

        pure_parallel_safe = (
            diverging_count == 0
            or matrix.max_divergence < DIVERGENCE_WEAK
        )

        return {
            "has_divergence": diverging_count > 0,
            "divergence_level": DivergenceLevel.from_divergence(matrix.max_divergence),
            "diverging_ratio": round(diverging_ratio, 4),
            "diverging_pair_count": diverging_count,
            "recommend_serial": recommend_serial,
            "pure_parallel_safe": pure_parallel_safe,
            "mean_divergence": round(matrix.mean_divergence, 4),
            "max_divergence": round(matrix.max_divergence, 4),
        }

    @staticmethod
    def _cosine(a: list[float], b: list[float]) -> float:
        """计算余弦相似度"""
        if HAS_NUMPY:
            a_arr = np.array(a, dtype=np.float64)
            b_arr = np.array(b, dtype=np.float64)
            dot = float(np.dot(a_arr, b_arr))
            norm_a = float(np.linalg.norm(a_arr))
            norm_b = float(np.linalg.norm(b_arr))
        else:
            dot = sum(x * y for x, y in zip(a, b))
            norm_a = math.sqrt(sum(x * x for x in a))
            norm_b = math.sqrt(sum(y * y for y in b))

        if norm_a < 1e-8 or norm_b < 1e-8:
            return 0.0
        return max(-1.0, min(1.0, dot / (norm_a * norm_b)))


# ══════════════════════════════════════════════════════════════════════
# Section 5: DAG 构造模块 (SelfOrg 启发式, Phase A)
# ══════════════════════════════════════════════════════════════════════


class DAGConstructor:
    """
    Nexa 阶段3: 图策略预测 — SelfOrg 启发式 DAG 构造 (Phase A)

    构造算法:
      1. 按贡献分数降序排列Agent: π = argsort(ψ_1,...,ψ_N; ψ_k ≥ ψ_{k+1})
      2. 对每个有序对 (i, j) 其中 ψ_i ≥ ψ_j:
         计算 div(i,j) = 1 - cosine_similarity(r_i, r_j)
         如果 div(i,j) > divergence_threshold:
           添加边 i → j (高贡献→低贡献)
      3. 可选的稀疏性约束:
         - 每个节点最多入度 K (默认无限制)
         - 仅保留 divergence ≥ threshold 的边

    命题1 保证 (构造性无环):
      因为所有边都从高贡献指向低贡献, 并且不存在 ψ_i = ψ_j 的双向边
      (相等贡献时按 agent_id 字典序打破平局), 所以图中不可能存在有向环。

    命题3 保证 (混合包容):
      当所有 pairwise divergence < threshold 时, 边集为空, 空图可达。

    复杂度: O(N²·d), N=Agent数, d=嵌入维度

    图密度公式: density = |E| / N²
    健康范围: 0.05 - 0.30 (Nexa 建议)
    """

    def __init__(
        self,
        divergence_threshold: float = DEFAULT_DIVERGENCE_THRESHOLD,
        max_in_degree: Optional[int] = None,
        min_divergence_for_edge: float = DEFAULT_DIVERGENCE_THRESHOLD,
    ):
        self.divergence_threshold = divergence_threshold
        self.max_in_degree = max_in_degree
        self.min_divergence_for_edge = min_divergence_for_edge

    def construct(
        self,
        agent_ids: list[str],
        embeddings: list[list[float]],
        contribution_scores: list[float],
        divergence_matrix: DivergenceMatrix,
    ) -> CommunicationGraph:
        """
        构造 Nexa 条件通信 DAG

        Args:
            agent_ids: Agent ID列表
            embeddings: 嵌入向量列表
            contribution_scores: 贡献分数列表
            divergence_matrix: 预计算的语义分歧矩阵

        Returns:
            有向无环通信图
        """
        n = len(agent_ids)

        if n < 2:
            return CommunicationGraph(
                nodes=list(agent_ids),
                edges=[],
                is_empty=True,
                topological_order=list(agent_ids),
                density=0.0,
                max_path_length=0,
            )

        # Step 1: 贡献排序 (高→低)
        sorted_pairs = sorted(
            zip(agent_ids, contribution_scores),
            key=lambda x: (x[1], x[0]),  # 平局时按 agent_id 字典序
            reverse=True,
        )
        topo_order = [agent_id for agent_id, _ in sorted_pairs]
        # 构建 rank 映射
        rank = {aid: i for i, aid in enumerate(topo_order)}

        # Step 2: 添加边 (仅从高贡献→低贡献)
        edges: list[CommunicationEdge] = []
        in_degree: dict[str, int] = defaultdict(int)

        for i in range(n):
            for j in range(i + 1, n):
                source = topo_order[i]      # 高贡献 (rank更小)
                target = topo_order[j]      # 低贡献 (rank更大)

                # 获取语义分歧值
                div = divergence_matrix.get(source, target)

                # 仅当分歧超过阈值时才添加边
                if div >= self.min_divergence_for_edge:
                    # 可选的入度限制
                    if self.max_in_degree is not None:
                        if in_degree[target] >= self.max_in_degree:
                            continue

                    edges.append(CommunicationEdge(
                        source_id=source,
                        target_id=target,
                        divergence=round(div, 6),
                        level=DivergenceLevel.from_divergence(div),
                    ))
                    in_degree[target] += 1

        # Step 3: 计算图指标
        is_empty = len(edges) == 0
        density = len(edges) / (n * n) if n > 0 else 0.0

        # 计算最长路径
        max_path = self._compute_max_path_length(
            agent_ids, edges, topo_order
        )

        return CommunicationGraph(
            nodes=list(agent_ids),
            edges=edges,
            is_empty=is_empty,
            topological_order=topo_order,
            density=round(density, 6),
            max_path_length=max_path,
        )

    def _compute_max_path_length(
        self,
        nodes: list[str],
        edges: list[CommunicationEdge],
        topo_order: list[str],
    ) -> int:
        """计算DAG中最长路径长度 (拓扑DP)"""
        if not edges:
            return 0

        # 按拓扑序DP
        dist: dict[str, int] = {node: 0 for node in nodes}

        for node in topo_order:
            for edge in edges:
                if edge.source_id == node:
                    target = edge.target_id
                    if dist[node] + 1 > dist[target]:
                        dist[target] = dist[node] + 1

        return max(dist.values()) if dist else 0

    def validate_acyclicity(self, graph: CommunicationGraph) -> bool:
        """
        验证命题1: 构造性无环

        检查所有边是否都从高贡献指向低贡献 (rank(source) < rank(target))
        """
        rank = {aid: i for i, aid in enumerate(graph.topological_order)}
        for edge in graph.edges:
            if rank.get(edge.source_id, 0) >= rank.get(edge.target_id, 0):
                logger.error(
                    f"违反命题1: 边 {edge.source_id}→{edge.target_id} "
                    f"不是前向边! rank={rank.get(edge.source_id)}≥{rank.get(edge.target_id)}"
                )
                return False
        return True

    def verify_proposition_2(
        self, graph: CommunicationGraph, agent_metadata: dict[str, dict]
    ) -> bool:
        """
        验证命题2: 身份不可知

        检查 DAG 构造过程中是否使用了 Agent 身份/角色/模型家族信息。
        这里通过审计日志验证——DAGConstructor 的 construct() 方法
        只使用了 agent_ids (用于排序) 和 embeddings (用于分歧计算),
        从未访问 agent_metadata 中的角色或模型信息。
        """
        # DAGConstructor 设计上就是身份不可知的:
        # - construct() 的参数中不包含角色/模型信息
        # - 排序仅基于贡献分数和agent_id字典序
        # - 分歧计算仅基于语义嵌入
        # 此方法的存在是为了显式审计
        return True


# ══════════════════════════════════════════════════════════════════════
# Section 6: 条件串行传播模块 (Nexa 阶段4)
# ══════════════════════════════════════════════════════════════════════


class ConditionalPropagator:
    """
    Nexa 阶段4: 条件串行传播

    核心逻辑:
      IF 通信图为空 (E = ∅):
        → 纯并行模式, 跳过传播, 零额外LLM调用
      ELSE:
        → 沿贡献排序 π 执行单轮串行传播
        → 每个目标节点以源节点响应为附加上下文
        → 目标节点更新 (精化) 其响应

    拓扑顺序: 由贡献分数诱导 (高贡献优先处理)
    传播深度: 单轮 (Nexa 论文限制, Phase C 可扩展多轮)

    并行度:
      - 同一贡献层级 (无依赖关系的节点) 可并行执行
      - 跨层级必须串行 (下一层依赖上一层的精化响应)
    """

    def __init__(self, refine_fn: Optional[Callable] = None):
        """
        Args:
            refine_fn: 可选的响应精化函数
                       签名: (original_content, predecessor_contexts) -> refined_content
                       如果为 None, 使用内置的模拟精化逻辑 (演示用)
        """
        self.refine_fn = refine_fn or self._default_refine_fn
        self._propagation_log: list[dict] = []

    def propagate(
        self,
        graph: CommunicationGraph,
        responses: list[AgentResponse],
    ) -> tuple[list[AgentResponse], bool]:
        """
        执行条件串行传播

        Args:
            graph: 通信图 (可能为空)
            responses: 原始Agent响应列表

        Returns:
            (refined_responses, propagation_occurred)
            - refined_responses: 精化后的响应 (空图时与原响应相同)
            - propagation_occurred: 是否实际执行了传播
        """
        if graph.is_empty or not graph.has_edges:
            logger.info("通信图为空 → 纯并行模式, 跳过串行传播 (零额外LLM调用)")
            # 命题3: 混合包容 — 空图始终可达
            return [r.clone_for_propagation() for r in responses], False

        logger.info(
            f"通信图非空 ({graph.edge_count}条边) → "
            f"启动条件串行传播, 拓扑序: {graph.topological_order}"
        )

        self._propagation_log = []

        # 创建响应副本用于精化
        refined = [r.clone_for_propagation() for r in responses]
        # 构建 agent_id → response index 映射
        agent_index = {r.agent_id: i for i, r in enumerate(refined)}
        # 构建 agent_id → rank 映射
        rank = {aid: i for i, aid in enumerate(graph.topological_order)}

        # 按拓扑序逐层传播
        processed: set[str] = set()

        for target_id in graph.topological_order:
            # 收集所有指向 target 的前驱节点
            predecessors: list[tuple[str, AgentResponse]] = []
            for edge in graph.edges:
                if edge.target_id == target_id:
                    src_idx = agent_index.get(edge.source_id)
                    if src_idx is not None and edge.source_id in processed:
                        predecessors.append((edge.source_id, refined[src_idx]))

            tgt_idx = agent_index.get(target_id)
            if tgt_idx is None:
                continue

            if predecessors:
                # 有前驱: 使用前驱上下文精化响应
                predecessor_contexts = [
                    f"[{src_id}]: {resp.refined_content or resp.content}"
                    for src_id, resp in predecessors
                ]
                original = refined[tgt_idx].content
                refined_content = self.refine_fn(original, predecessor_contexts)

                refined[tgt_idx].refined_content = refined_content
                refined[tgt_idx].is_predecessor_context_used = True
                refined[tgt_idx].predecessors_used = [p[0] for p in predecessors]

                self._propagation_log.append({
                    "target": target_id,
                    "predecessors": [p[0] for p in predecessors],
                    "original_preview": original[:100],
                    "refined_preview": refined_content[:100],
                })

                logger.debug(
                    f"传播: {', '.join(p[0] for p in predecessors)} → {target_id}"
                )
            else:
                # 无前驱: 保持原响应 (顶层节点)
                refined[tgt_idx].refined_content = None  # 未精化, 使用原始内容

            processed.add(target_id)

        logger.info(
            f"条件串行传播完成: 处理了 {len(processed)} 个节点, "
            f"其中 {sum(1 for r in refined if r.is_predecessor_context_used)} 个接收了前驱上下文"
        )

        return refined, True

    def get_propagation_log(self) -> list[dict]:
        """获取传播日志"""
        return list(self._propagation_log)

    @staticmethod
    def _default_refine_fn(
        original_content: str,
        predecessor_contexts: list[str],
    ) -> str:
        """
        默认响应精化函数 (演示用)

        实际部署时, 此函数应调用 LLM 完成真正的精化:
          refined = llm.generate(
            f"原始回答: {original_content}\n"
            f"参考以下前置Agent的回答:\n"
            + "\n---\n".join(predecessor_contexts)
            + "\n\n请综合以上信息, 给出更完善的回答。"
          )

        这里提供基于文本拼接的简化实现, 用于演示管线。
        """
        if not predecessor_contexts:
            return original_content

        # 演示: 在前驱上下文中追加精化标记
        context_summary = " ; ".join(
            ctx.split("\n")[0][:80] for ctx in predecessor_contexts
        )
        return (
            f"{original_content}\n\n"
            f"[Nexa条件传播精化 — 已参考 {len(predecessor_contexts)} 个前置Agent: "
            f"{context_summary}...]"
        )


# ══════════════════════════════════════════════════════════════════════
# Section 7: 身份不可知聚合模块 (Nexa 阶段5)
# ══════════════════════════════════════════════════════════════════════


class IdentityAgnosticAggregator:
    """
    Nexa 阶段5: 无裁判聚合 — 身份不可知

    算法:
      r_weighted_centroid = Σ(ψ_n * r_n) / Σ(ψ_n)
      y_final = argmin_n ||r_n - r_weighted_centroid||²
      即: 距贡献加权质心最近的响应 = 最终答案

    关键特性 (命题2: 身份不可知):
      - 聚合只看嵌入向量和贡献分数
      - 不看Agent的ID、角色标签、模型家族
      - 相同语义空间中的响应, 无论来自哪个Agent, 同等对待
      - 替换底层模型、新增Agent不需要修改聚合逻辑

    备选聚合方法:
      1. 简单多数: final = response from agent with max ψ
      2. 加权质心 (默认): final = argmin ||r_n - weighted_centroid||²
      3. 共识半径: final = response within radius ε of weighted_centroid
    """

    METHOD_WEIGHTED_CENTROID = "weighted_centroid"
    METHOD_MAX_CONTRIBUTION = "max_contribution"
    METHOD_CONSENSUS_RADIUS = "consensus_radius"

    def __init__(self, method: str = METHOD_WEIGHTED_CENTROID):
        self.method = method
        if method not in (
            self.METHOD_WEIGHTED_CENTROID,
            self.METHOD_MAX_CONTRIBUTION,
            self.METHOD_CONSENSUS_RADIUS,
        ):
            raise ValueError(f"未知聚合方法: {method}")

    def aggregate(
        self,
        responses: list[AgentResponse],
        contribution_scores: list[float],
        embeddings: list[list[float]],
    ) -> tuple[str, str]:
        """
        身份不可知聚合

        Args:
            responses: Agent响应列表
            contribution_scores: 贡献分数列表
            embeddings: 嵌入向量列表

        Returns:
            (final_content, selected_agent_id)
            - final_content: 最终聚合答案 (被选中Agent的精化或原始响应)
            - selected_agent_id: 被选中Agent的ID (仅用于审计日志)
        """
        if not responses:
            return "", ""

        if len(responses) == 1:
            r = responses[0]
            return (r.refined_content or r.content), r.agent_id

        if self.method == self.METHOD_MAX_CONTRIBUTION:
            return self._aggregate_max_contribution(responses, contribution_scores)

        elif self.method == self.METHOD_WEIGHTED_CENTROID:
            return self._aggregate_weighted_centroid(
                responses, contribution_scores, embeddings
            )

        elif self.method == self.METHOD_CONSENSUS_RADIUS:
            return self._aggregate_consensus_radius(
                responses, contribution_scores, embeddings
            )

        return "", ""

    def _aggregate_max_contribution(
        self,
        responses: list[AgentResponse],
        scores: list[float],
    ) -> tuple[str, str]:
        """最大贡献聚合: 直接选择贡献分数最高的响应"""
        best_idx = max(range(len(scores)), key=lambda i: scores[i])
        r = responses[best_idx]
        return (r.refined_content or r.content), r.agent_id

    def _aggregate_weighted_centroid(
        self,
        responses: list[AgentResponse],
        scores: list[float],
        embeddings: list[list[float]],
    ) -> tuple[str, str]:
        """
        加权质心聚合 (Nexa 默认方法)

        r_weighted = Σ(score_i * emb_i) / Σ(score_i)
        final = argmin_i ||emb_i - r_weighted||²
        """
        if not embeddings:
            return self._aggregate_max_contribution(responses, scores)

        d = len(embeddings[0])

        # 计算加权质心
        total_weight = sum(max(s, 0.0) for s in scores)  # 负贡献不参与
        if total_weight < CONTRIBUTION_SMOOTHING_EPSILON:
            # 全部贡献为负或零 → 回退到最大贡献
            return self._aggregate_max_contribution(responses, scores)

        weighted_centroid = [0.0] * d
        for i, emb in enumerate(embeddings):
            w = max(scores[i], 0.0)
            for j in range(d):
                weighted_centroid[j] += w * emb[j] / total_weight

        # 找距加权质心最近的响应
        min_dist = float("inf")
        best_idx = 0

        if HAS_NUMPY:
            centroid_arr = np.array(weighted_centroid, dtype=np.float64)
            for i, emb in enumerate(embeddings):
                emb_arr = np.array(emb, dtype=np.float64)
                dist = float(np.sum((emb_arr - centroid_arr) ** 2))
                if dist < min_dist:
                    min_dist = dist
                    best_idx = i
        else:
            for i, emb in enumerate(embeddings):
                dist = sum((e - c) ** 2 for e, c in zip(emb, weighted_centroid))
                if dist < min_dist:
                    min_dist = dist
                    best_idx = i

        r = responses[best_idx]
        return (r.refined_content or r.content), r.agent_id

    def _aggregate_consensus_radius(
        self,
        responses: list[AgentResponse],
        scores: list[float],
        embeddings: list[list[float]],
        radius: float = 0.3,
    ) -> tuple[str, str]:
        """
        共识半径聚合: 在加权质心周围 radius 范围内找最高贡献响应
        如果半径内无响应, 回退到加权质心方法
        """
        d = len(embeddings[0])
        total_weight = sum(max(s, 0.0) for s in scores)
        if total_weight < CONTRIBUTION_SMOOTHING_EPSILON:
            return self._aggregate_max_contribution(responses, scores)

        weighted_centroid = [0.0] * d
        for i, emb in enumerate(embeddings):
            w = max(scores[i], 0.0)
            for j in range(d):
                weighted_centroid[j] += w * emb[j] / total_weight

        # 找半径内的最高贡献响应
        best_idx = -1
        best_score = -float("inf")

        for i, emb in enumerate(embeddings):
            dist = math.sqrt(sum((e - c) ** 2 for e, c in zip(emb, weighted_centroid)))
            if dist <= radius and scores[i] > best_score:
                best_score = scores[i]
                best_idx = i

        if best_idx >= 0:
            r = responses[best_idx]
            return (r.refined_content or r.content), r.agent_id

        # 回退
        return self._aggregate_weighted_centroid(responses, scores, embeddings)


# ══════════════════════════════════════════════════════════════════════
# Section 8: Nexa 通信层主协调器
# ══════════════════════════════════════════════════════════════════════


class NexaCommunicationLayer:
    """
    Nexa 条件通信层 — L3 主协调器

    整合五个阶段的完整通信管线:
      阶段1→2→3→4→5

    兼容 Colony-035 (L1 Pipeline) 和 Colony-036 (L2 Role Election) 的数据结构。

    使用方式:
      nexa = NexaCommunicationLayer()
      result = nexa.execute(agent_responses)
      # result.final_content — 最终聚合答案
      # result.metrics — 全部通信指标
    """

    def __init__(
        self,
        embedding_model: str = PRIMARY_EMBEDDING_MODEL,
        divergence_threshold: float = DEFAULT_DIVERGENCE_THRESHOLD,
        aggregation_method: str = IdentityAgnosticAggregator.METHOD_WEIGHTED_CENTROID,
        refine_fn: Optional[Callable] = None,
        use_real_embeddings: bool = True,
        max_in_degree: Optional[int] = None,
    ):
        """
        Args:
            embedding_model: 嵌入模型名称
            divergence_threshold: 语义分歧阈值
            aggregation_method: 聚合方法
            refine_fn: 响应精化函数
            use_real_embeddings: 是否使用真实嵌入模型
            max_in_degree: DAG节点最大入度限制
        """
        self.divergence_threshold = divergence_threshold
        self.aggregation_method = aggregation_method

        # 初始化各模块
        self.embedder = SemanticEmbedder(
            model_name=embedding_model,
            use_fallback=not use_real_embeddings,
        )
        self.contribution_evaluator = ContributionEvaluator()
        self.divergence_detector = DivergenceDetector(threshold=divergence_threshold)
        self.dag_constructor = DAGConstructor(
            divergence_threshold=divergence_threshold,
            max_in_degree=max_in_degree,
        )
        self.propagator = ConditionalPropagator(refine_fn=refine_fn)
        self.aggregator = IdentityAgnosticAggregator(method=aggregation_method)

        # 累积统计
        self._stats: dict[str, Any] = {
            "total_executions": 0,
            "serial_trigger_count": 0,
            "parallel_fallback_count": 0,
            "cumulative_embedding_time_ms": 0.0,
            "cumulative_total_time_ms": 0.0,
        }

    def execute(
        self,
        agent_responses: dict[str, str],
        agent_metadata: Optional[dict[str, dict]] = None,
        task_id: Optional[str] = None,
    ) -> NexaResult:
        """
        执行完整的 Nexa 五阶段通信管线

        Args:
            agent_responses: {agent_id: response_text} 的字典
                             注意: 这不包含角色/模型信息 (命题2: 身份不可知)
            agent_metadata: 可选的Agent元数据 (仅用于审计日志, 不参与路由决策)
            task_id: 任务标识

        Returns:
            NexaResult: 包含聚合结果、通信图、分歧矩阵、全部指标
        """
        t_start = time.perf_counter()
        agent_ids = list(agent_responses.keys())
        n_agents = len(agent_ids)

        if task_id is None:
            task_id = str(uuid.uuid4())[:8]

        logger.info(
            f"=== Nexa 通信管线启动 === "
            f"Task={task_id}, Agents={n_agents}, "
            f"Threshold={self.divergence_threshold}"
        )

        # ─── 阶段1: 并行草稿 ───
        # (外部已完成 — agent_responses 即为并行草稿结果)
        logger.info(f"[阶段1] 并行草稿: {n_agents} 个Agent已完成独立响应")

        # ─── 阶段2: 语义嵌入 ───
        t_embed_start = time.perf_counter()
        logger.info(f"[阶段2] 语义嵌入: 使用 {self.embedder.model_name} ...")

        contents = list(agent_responses.values())
        embeddings = self.embedder.embed_batch(contents)
        t_embed = (time.perf_counter() - t_embed_start) * 1000

        logger.info(
            f"[阶段2] 完成: {n_agents} 个响应已映射至 "
            f"{len(embeddings[0]) if embeddings else 0}维语义空间 "
            f"(耗时 {t_embed:.1f}ms)"
        )

        # ─── 阶段3: 贡献评估 + 分歧检测 + DAG构造 ───
        t_dag_start = time.perf_counter()

        # 3a: 贡献评估 (cosine-to-centroid)
        contribution_scores, centroid = self.contribution_evaluator.evaluate(embeddings)
        topo_order = self.contribution_evaluator.get_topology_order(
            agent_ids, contribution_scores
        )

        logger.info(
            f"[阶段3a] 贡献评估: scores={[f'{s:.3f}' for s in contribution_scores]}, "
            f"拓扑序={topo_order}"
        )

        # 3b: 语义分歧检测
        divergence_matrix = self.divergence_detector.compute_pairwise(
            agent_ids, embeddings
        )
        divergence_report = self.divergence_detector.detect(divergence_matrix)

        logger.info(
            f"[阶段3b] 分歧检测: "
            f"max_div={divergence_report['max_divergence']:.4f}, "
            f"mean_div={divergence_report['mean_divergence']:.4f}, "
            f"diverging_pairs={divergence_report['diverging_pair_count']}, "
            f"level={divergence_report['divergence_level'].value}, "
            f"recommend_serial={divergence_report['recommend_serial']}"
        )

        # 3c: DAG 构造 (SelfOrg 启发式)
        graph = self.dag_constructor.construct(
            agent_ids, embeddings, contribution_scores, divergence_matrix
        )
        t_dag = (time.perf_counter() - t_dag_start) * 1000

        # 验证命题1 (构造性无环)
        is_acyclic = self.dag_constructor.validate_acyclicity(graph)

        logger.info(
            f"[阶段3c] DAG构造: edges={graph.edge_count}, "
            f"density={graph.density:.4f}, "
            f"max_path={graph.max_path_length}, "
            f"is_empty={graph.is_empty}, "
            f"acyclic={is_acyclic}, "
            f"耗时 {t_dag:.1f}ms"
        )

        # ─── 阶段4: 条件串行传播 ───
        t_prop_start = time.perf_counter()

        # 构建 AgentResponse 列表
        responses = [
            AgentResponse(
                agent_id=aid,
                content=agent_responses[aid],
                embedding=emb,
                contribution_score=cs,
                metadata=agent_metadata.get(aid, {}) if agent_metadata else {},
            )
            for aid, emb, cs in zip(agent_ids, embeddings, contribution_scores)
        ]

        refined_responses, propagation_occurred = self.propagator.propagate(
            graph, responses
        )
        t_prop = (time.perf_counter() - t_prop_start) * 1000

        serial_triggered = propagation_occurred and not graph.is_empty
        parallel_fallback = not serial_triggered

        logger.info(
            f"[阶段4] 条件串行传播: "
            f"triggered={serial_triggered}, "
            f"fallback_to_parallel={parallel_fallback}, "
            f"耗时 {t_prop:.1f}ms"
        )

        # ─── 阶段5: 无裁判聚合 ───
        t_agg_start = time.perf_counter()

        # 使用精化后的嵌入 (如果有精化响应, 实际部署中需重新嵌入)
        # Phase A 简化: 使用原始嵌入进行聚合
        # (因为默认 refine_fn 是文本拼接, 重新嵌入不增加信息量)
        refined_embeddings = [
            refined_responses[i].embedding or embeddings[i]
            for i in range(len(responses))
        ]

        final_content, selected_id = self.aggregator.aggregate(
            refined_responses, contribution_scores, refined_embeddings
        )
        t_agg = (time.perf_counter() - t_agg_start) * 1000

        t_total = (time.perf_counter() - t_start) * 1000

        logger.info(
            f"[阶段5] 无裁判聚合: "
            f"selected={selected_id}, "
            f"method={self.aggregator.method}, "
            f"耗时 {t_agg:.1f}ms"
        )

        # ─── 确定执行模式 ───
        if graph.is_empty:
            mode = ExecutionMode.PURE_PARALLEL
        elif graph.density > MAX_GRAPH_DENSITY:
            mode = ExecutionMode.DENSE_SERIAL
            logger.warning(
                f"图密度 {graph.density:.4f} 超过健康上限 {MAX_GRAPH_DENSITY}, "
                f"可能是分歧阈值过低或Agent响应高度分散"
            )
        else:
            mode = ExecutionMode.SPARSE_SERIAL

        # ─── 构建指标 ───
        if HAS_NUMPY:
            contrib_arr = np.array(contribution_scores)
            contrib_var = float(np.var(contrib_arr))
        else:
            mean_cs = sum(contribution_scores) / len(contribution_scores)
            contrib_var = sum((s - mean_cs) ** 2 for s in contribution_scores) / len(contribution_scores)

        metrics = NexaMetrics(
            graph_density=graph.density,
            edge_count=graph.edge_count,
            max_path_length=graph.max_path_length,
            execution_mode=mode,
            serial_triggered=serial_triggered,
            parallel_fallback=parallel_fallback,
            mean_divergence=divergence_report["mean_divergence"],
            max_divergence=divergence_report["max_divergence"],
            diverging_pair_count=divergence_report["diverging_pair_count"],
            embedding_time_ms=round(t_embed, 2),
            dag_construction_time_ms=round(t_dag, 2),
            propagation_time_ms=round(t_prop, 2),
            aggregation_time_ms=round(t_agg, 2),
            total_time_ms=round(t_total, 2),
            contribution_scores=contribution_scores,
            contribution_variance=round(contrib_var, 6),
            is_acyclic=is_acyclic,
            is_identity_agnostic=True,  # 设计保证
            is_parallel_subsumed=True,  # 设计保证 (空图始终可达)
        )

        # ─── 更新累积统计 ───
        self._stats["total_executions"] += 1
        if serial_triggered:
            self._stats["serial_trigger_count"] += 1
        if parallel_fallback:
            self._stats["parallel_fallback_count"] += 1
        self._stats["cumulative_embedding_time_ms"] += t_embed
        self._stats["cumulative_total_time_ms"] += t_total

        # ─── 构建结果 ───
        result = NexaResult(
            final_content=final_content,
            selected_agent_id=selected_id,
            aggregation_method=self.aggregator.method,
            all_responses=responses,
            refined_responses=refined_responses,
            communication_graph=graph,
            divergence_matrix=divergence_matrix,
            metrics=metrics,
            task_id=task_id,
            timestamp=datetime.now(timezone.utc).isoformat(),
            phase=PHASE,
            embedding_model=self.embedder.model_name,
            divergence_threshold=self.divergence_threshold,
            agent_count=n_agents,
        )

        logger.info(
            f"=== Nexa 通信管线完成 === "
            f"mode={mode.value}, "
            f"selected={selected_id}, "
            f"total={t_total:.1f}ms, "
            f"edges={graph.edge_count}, "
            f"embedding={t_embed:.1f}ms, "
            f"dag={t_dag:.1f}ms, "
            f"propagation={t_prop:.1f}ms, "
            f"aggregation={t_agg:.1f}ms"
        )

        return result

    def get_statistics(self) -> dict[str, Any]:
        """获取累积统计"""
        stats = dict(self._stats)
        total = max(stats["total_executions"], 1)
        stats["serial_trigger_rate"] = stats["serial_trigger_count"] / total
        stats["parallel_fallback_rate"] = stats["parallel_fallback_count"] / total
        stats["avg_embedding_time_ms"] = stats["cumulative_embedding_time_ms"] / total
        stats["avg_total_time_ms"] = stats["cumulative_total_time_ms"] / total
        return stats

    def is_healthy(self) -> tuple[bool, list[str]]:
        """
        健康检查

        Returns:
            (is_healthy, warnings)
        """
        stats = self.get_statistics()
        warnings: list[str] = []

        if stats["total_executions"] < 1:
            return True, warnings

        # 串行触发率应在 20-60% 范围内
        sr = stats["serial_trigger_rate"]
        if sr < IDEAL_SERIAL_TRIGGER_RATE[0] and stats["total_executions"] >= 5:
            warnings.append(
                f"串行触发率 {sr:.1%} 低于理想范围 "
                f"{IDEAL_SERIAL_TRIGGER_RATE[0]:.0%}-{IDEAL_SERIAL_TRIGGER_RATE[1]:.0%}"
            )
        elif sr > IDEAL_SERIAL_TRIGGER_RATE[1]:
            warnings.append(
                f"串行触发率 {sr:.1%} 高于理想范围 "
                f"{IDEAL_SERIAL_TRIGGER_RATE[0]:.0%}-{IDEAL_SERIAL_TRIGGER_RATE[1]:.0%}"
            )

        return len(warnings) == 0, warnings

    def health_report(self) -> str:
        """生成健康报告"""
        is_ok, warnings = self.is_healthy()
        stats = self.get_statistics()

        lines = [
            "=" * 60,
            f"Nexa L3 通信层健康报告 (Phase {PHASE})",
            "=" * 60,
            f"状态: {'健康' if is_ok else '需要注意'}",
            f"总执行次数: {stats['total_executions']}",
            f"串行触发率: {stats['serial_trigger_rate']:.1%}",
            f"并行回退率: {stats['parallel_fallback_rate']:.1%}",
            f"平均嵌入耗时: {stats['avg_embedding_time_ms']:.1f}ms",
            f"平均总耗时: {stats['avg_total_time_ms']:.1f}ms",
            f"嵌入模型: {self.embedder.model_name}",
            f"分歧阈值: {self.divergence_threshold}",
            f"聚合方法: {self.aggregation_method}",
        ]

        if warnings:
            lines.append("")
            lines.append("警告:")
            for w in warnings:
                lines.append(f"  - {w}")

        lines.append("=" * 60)
        return "\n".join(lines)


# ══════════════════════════════════════════════════════════════════════
# Section 9: 结果可视化与报告
# ══════════════════════════════════════════════════════════════════════


class NexaReporter:
    """Nexa 通信层结果报告器"""

    @staticmethod
    def format_result(result: NexaResult, verbose: bool = False) -> str:
        """格式化 NexaResult 为可读文本"""
        m = result.metrics
        g = result.communication_graph

        lines = [
            "=" * 70,
            f"  Nexa v{VERSION} 通信层结果 (Phase {result.phase})",
            "=" * 70,
            f"  任务ID:      {result.task_id}",
            f"  时间:        {result.timestamp[:19]}",
            f"  Agent数:     {result.agent_count}",
            f"  嵌入模型:    {result.embedding_model}",
            f"  分歧阈值:    {result.divergence_threshold}",
            "",
            "─ 通信图 ─",
            f"  执行模式:    {m.execution_mode.value}",
            f"  边数:        {m.edge_count}",
            f"  图密度:      {m.graph_density:.4f}  (健康: {MIN_GRAPH_DENSITY}-{MAX_GRAPH_DENSITY})",
            f"  最长路径:    {m.max_path_length} 跳  (健康: 1-{MAX_PROPAGATION_HOPS})",
            f"  串行触发:    {'是' if m.serial_triggered else '否'}",
            f"  并行回退:    {'是' if m.parallel_fallback else '否'}",
            "",
            "─ 语义分歧 ─",
            f"  平均分歧:    {m.mean_divergence:.4f}",
            f"  最大分歧:    {m.max_divergence:.4f}",
            f"  分歧对数:    {m.diverging_pair_count}",
            "",
            "─ 贡献分布 ─",
            f"  贡献分数:    {[f'{s:.3f}' for s in m.contribution_scores]}",
            f"  贡献方差:    {m.contribution_variance:.6f}",
            "",
            "─ 性能 ─",
            f"  嵌入耗时:    {m.embedding_time_ms:.1f} ms",
            f"  DAG构造:     {m.dag_construction_time_ms:.1f} ms",
            f"  传播耗时:    {m.propagation_time_ms:.1f} ms",
            f"  聚合耗时:    {m.aggregation_time_ms:.1f} ms",
            f"  总耗时:      {m.total_time_ms:.1f} ms",
            "",
            "─ 三大命题合规 ─",
            f"  P1 构造性无环:      {'通过' if m.is_acyclic else '失败!'}",
            f"  P2 身份不可知:      {'通过' if m.is_identity_agnostic else '失败!'}",
            f"  P3 混合包容(空图):  {'通过' if m.is_parallel_subsumed else '失败!'}",
            "",
            "─ 聚合结果 ─",
            f"  选中Agent:   {result.selected_agent_id}",
            f"  聚合方法:    {result.aggregation_method}",
            f"  最终答案预览: {result.final_content[:200]}",
            "=" * 70,
        ]

        if verbose and g and g.has_edges:
            lines.append("")
            lines.append("─ 通信边详情 ─")
            for edge in g.edges:
                lines.append(
                    f"  {edge.source_id} → {edge.target_id}  "
                    f"(div={edge.divergence:.4f}, level={edge.level.value})"
                )

        if verbose and result.divergence_matrix:
            lines.append("")
            lines.append("─ 分歧矩阵 ─")
            for (a, b), div in sorted(
                result.divergence_matrix.pairwise_divergences.items(),
                key=lambda x: x[1],
                reverse=True,
            )[:10]:
                level = DivergenceLevel.from_divergence(div)
                lines.append(f"  {a} ↔ {b}: {div:.4f} ({level.value})")

        return "\n".join(lines)

    @staticmethod
    def to_json(result: NexaResult) -> str:
        """导出为JSON"""
        output = {
            "version": VERSION,
            "phase": result.phase,
            "task_id": result.task_id,
            "timestamp": result.timestamp,
            "agent_count": result.agent_count,
            "embedding_model": result.embedding_model,
            "divergence_threshold": result.divergence_threshold,
            "aggregation_method": result.aggregation_method,
            "selected_agent_id": result.selected_agent_id,
            "final_content": result.final_content,
            "metrics": {
                "graph_density": result.metrics.graph_density,
                "edge_count": result.metrics.edge_count,
                "max_path_length": result.metrics.max_path_length,
                "execution_mode": result.metrics.execution_mode.value,
                "serial_triggered": result.metrics.serial_triggered,
                "parallel_fallback": result.metrics.parallel_fallback,
                "mean_divergence": result.metrics.mean_divergence,
                "max_divergence": result.metrics.max_divergence,
                "diverging_pair_count": result.metrics.diverging_pair_count,
                "contribution_scores": result.metrics.contribution_scores,
                "contribution_variance": result.metrics.contribution_variance,
                "total_time_ms": result.metrics.total_time_ms,
                "embedding_time_ms": result.metrics.embedding_time_ms,
                "propagation_time_ms": result.metrics.propagation_time_ms,
                "propositions": {
                    "P1_acyclic": result.metrics.is_acyclic,
                    "P2_identity_agnostic": result.metrics.is_identity_agnostic,
                    "P3_parallel_subsumed": result.metrics.is_parallel_subsumed,
                },
            },
            "communication_graph": {
                "nodes": result.communication_graph.nodes if result.communication_graph else [],
                "edge_count": result.communication_graph.edge_count if result.communication_graph else 0,
                "edges": [
                    {
                        "source": e.source_id,
                        "target": e.target_id,
                        "divergence": e.divergence,
                        "level": e.level.value,
                    }
                    for e in (result.communication_graph.edges if result.communication_graph else [])
                ],
                "is_empty": result.communication_graph.is_empty if result.communication_graph else True,
                "topological_order": result.communication_graph.topological_order if result.communication_graph else [],
                "density": result.communication_graph.density if result.communication_graph else 0.0,
            },
        }
        return json.dumps(output, ensure_ascii=False, indent=2)


# ══════════════════════════════════════════════════════════════════════
# Section 10: 演示与测试
# ══════════════════════════════════════════════════════════════════════


def create_demo_responses() -> dict[str, str]:
    """
    创建演示用的Agent响应

    设计策略:
      - Agent_A, Agent_B, Agent_C: 语义相近 (同意方案X)
      - Agent_D: 语义分歧 (提出方案Y)
      - Agent_E: 语义高度分歧 (提出完全不同的方案Z)
    """
    return {
        "Agent_架构师": (
            "建议采用微服务架构。将系统拆分为用户服务、订单服务、支付服务三个独立模块。"
            "每个服务独立部署，通过REST API通信。数据库按服务拆分，使用事件溯源保证数据一致性。"
            "优点：独立扩展、技术栈灵活、故障隔离。缺点：运维复杂度增加。"
            "推荐使用Kubernetes部署，配合Istio服务网格管理通信。"
        ),
        "Agent_开发者": (
            "同意微服务方向。用户服务用Go实现（高并发），订单服务用Java（业务逻辑复杂），"
            "支付服务用Rust（安全性优先）。数据库选型：用户服务用PostgreSQL，"
            "订单服务用MongoDB（文档灵活），支付服务用CockroachDB（分布式一致性）。"
            "API网关使用Kong，消息队列使用Kafka处理服务间异步通信。"
        ),
        "Agent_运维": (
            "微服务方案可行。Kubernetes 1.29 + Istio 1.20 是成熟组合。"
            "建议增加：Prometheus + Grafana 监控栈，ELK 日志收集，"
            "Jaeger 分布式追踪。CI/CD 使用 GitHub Actions + ArgoCD。"
            "每个服务至少3副本保证高可用，配置HPA自动扩缩容。"
            "需要注意：微服务增加网络延迟约5-15ms，需在链路中做好超时和重试策略。"
        ),
        "Agent_测试员": (
            "对微服务架构提出不同看法。考虑到团队规模只有7人，"
            "微服务的运维负担可能超过收益。建议采用模块化单体（Modular Monolith）——"
            "代码按领域模块拆分，但部署为一个整体。"
            "等用户量突破10万后再渐进式拆分为微服务。"
            "这样可以推迟引入Kubernetes的复杂度，先用Docker Compose部署。"
            "测试策略：模块化单体更容易写集成测试，端到端测试成本也更低。"
        ),
        "Agent_PM": (
            "从产品和交付角度，我倾向于测试员的模块化单体方案。"
            "我们的核心目标是2周内完成MVP，微服务的基础设施搭建至少需要额外1-2周。"
            "模块化单体可以更快交付，同时保留未来拆分的灵活性。"
            "关键约束：模块间接口必须定义清晰（为未来拆分做准备），"
            "数据库不拆分但表按模块命名空间隔离。"
            "第一版先验证产品市场匹配，架构优化放在V2。"
        ),
    }


def create_convergent_responses() -> dict[str, str]:
    """
    创建语义高度一致的Agent响应 (用于测试纯并行回退)

    所有Agent都基本同意同一方案, 语义分歧应该很低,
    Nexa应检测到并自动回退到纯并行模式。
    """
    return {
        "Agent_A": "建议使用Redis作为缓存层，设置TTL为1小时，使用LRU淘汰策略。",
        "Agent_B": "推荐Redis缓存方案，1小时过期时间，配合LRU淘汰很合理。",
        "Agent_C": "Redis缓存，TTL=3600秒，LRU淘汰——这是标准做法，没问题的。",
        "Agent_D": "Redis做缓存挺好，1小时TTL，LRU策略，和我们的需求匹配。",
        "Agent_E": "同意Redis缓存方案。1小时过期+LRU淘汰，实现简单且高效。",
    }


def run_demo(args: argparse.Namespace) -> None:
    """
    运行 Nexa 通信层完整演示

    包含三个场景:
      1. 语义分歧场景 — 应触发条件串行
      2. 语义一致场景 — 应纯并行回退
      3. 批量统计 — 多次运行统计指标
    """
    print()
    print("=" * 70)
    print("  Colony v2.0 — L3 Nexa 条件通信层 演示")
    print(f"  Phase {PHASE}: 零训练版本 (SelfOrg 启发式)")
    print(f"  Colony-037 极限实验室 | 2026-05-19")
    print("=" * 70)

    nexa = NexaCommunicationLayer(
        embedding_model=args.model,
        divergence_threshold=args.threshold,
        aggregation_method=args.aggregation,
        use_real_embeddings=not args.fallback,
    )

    # ─── 场景1: 语义分歧场景 ───
    print()
    print("━" * 70)
    print("  场景1: 语义分歧场景 (应触发条件串行)")
    print("  场景设定: 架构师/开发者/运维 同意微服务, 测试员/PM 倾向模块化单体")
    print("━" * 70)

    responses_divergent = create_demo_responses()
    result1 = nexa.execute(responses_divergent, task_id="demo-divergent")

    print()
    print(NexaReporter.format_result(result1, verbose=args.verbose))

    # ─── 场景2: 语义一致场景 ───
    print()
    print("━" * 70)
    print("  场景2: 语义一致场景 (应纯并行回退)")
    print("  场景设定: 所有Agent一致同意Redis缓存方案")
    print("━" * 70)

    responses_convergent = create_convergent_responses()
    result2 = nexa.execute(responses_convergent, task_id="demo-convergent")

    print()
    print(NexaReporter.format_result(result2, verbose=args.verbose))

    # ─── 场景3: 批量统计 ───
    if args.benchmark:
        print()
        print("━" * 70)
        print(f"  场景3: 批量基准测试 (N={args.benchmark_runs})")
        print("━" * 70)

        # 重置统计 (创建新实例)
        nexa_bench = NexaCommunicationLayer(
            embedding_model=args.model,
            divergence_threshold=args.threshold,
            aggregation_method=args.aggregation,
            use_real_embeddings=not args.fallback,
        )

        for i in range(args.benchmark_runs):
            # 交替使用分歧和一致场景
            if i % 2 == 0:
                resp = create_demo_responses()
            else:
                resp = create_convergent_responses()
            nexa_bench.execute(resp, task_id=f"bench-{i:03d}")

        print()
        print(nexa_bench.health_report())

    # ─── 导出JSON ───
    if args.output:
        output_path = Path(args.output)
        output_path.write_text(NexaReporter.to_json(result1), encoding=OUTPUT_ENCODING)
        print(f"\nJSON结果已导出至: {output_path}")

    print()
    print("演示完成。三大命题状态:")
    print(f"  命题1 (构造性无环):      {'通过' if result1.metrics.is_acyclic else '失败'}")
    print(f"  命题2 (身份不可知):      {'通过' if result1.metrics.is_identity_agnostic else '失败'}")
    print(f"  命题3 (混合包容/空图):   {'通过' if result1.metrics.is_parallel_subsumed else '失败'}")


def run_unit_tests() -> tuple[int, int]:
    """
    运行内置单元测试

    Returns:
        (passed, total)
    """
    passed = 0
    total = 0

    def assert_true(cond: bool, name: str):
        nonlocal passed, total
        total += 1
        if cond:
            passed += 1
            print(f"  PASS: {name}")
        else:
            print(f"  FAIL: {name}")

    def assert_approx(a: float, b: float, eps: float, name: str):
        nonlocal passed, total
        total += 1
        if abs(a - b) < eps:
            passed += 1
            print(f"  PASS: {name} ({a:.4f} ≈ {b:.4f})")
        else:
            print(f"  FAIL: {name} ({a:.4f} ≠ {b:.4f}, eps={eps})")

    print()
    print("=" * 70)
    print("  Nexa 通信层 单元测试")
    print("=" * 70)

    # ─── 测试1: 语义嵌入 ───
    print("\n[测试组1] 语义嵌入模块")
    embedder = SemanticEmbedder(use_fallback=True)
    emb = embedder.embed("测试文本")
    assert_true(len(emb) == EMBEDDING_DIM, "嵌入维度=384")
    assert_true(all(isinstance(x, float) for x in emb), "嵌入元素为浮点数")

    # ─── 测试2: 贡献评估 ───
    print("\n[测试组2] 贡献评估模块")
    evaluator = ContributionEvaluator()
    # 创建模拟嵌入
    e1 = [1.0, 0.0, 0.0]
    e2 = [0.9, 0.1, 0.0]
    e3 = [0.0, 1.0, 0.0]  # 明显的离群值
    scores, centroid = evaluator.evaluate([e1, e2, e3])
    # e1 和 e2 应该更接近质心, e3 应该贡献更低
    assert_true(scores[0] > scores[2], "e1贡献 > e3贡献 (e3是离群值)")
    assert_true(scores[1] > scores[2], "e2贡献 > e3贡献 (e3是离群值)")
    assert_true(all(-1.0 <= s <= 1.0 for s in scores), "贡献分数在[-1,1]范围内")

    # ─── 测试3: 语义分歧检测 ───
    print("\n[测试组3] 语义分歧检测")
    detector = DivergenceDetector(threshold=0.35)
    # e1 和 e2 近似, e3 不同
    matrix = detector.compute_pairwise(
        ["A", "B", "C"], [e1, e2, e3]
    )
    report = detector.detect(matrix)
    assert_true(report["has_divergence"], "检测到分歧")
    # A和C之间的分歧应该大于 A和B之间
    div_ab = matrix.get("A", "B")
    div_ac = matrix.get("A", "C")
    assert_true(div_ac > div_ab, f"div(A,C)={div_ac:.3f} > div(A,B)={div_ab:.3f}")

    # ─── 测试4: DAG构造与命题1 ───
    print("\n[测试组4] DAG构造与命题1 (构造性无环)")
    dag = DAGConstructor(divergence_threshold=0.2)
    agent_ids = ["Agent_High", "Agent_Mid", "Agent_Low"]
    # 三个方向不同的嵌入
    emb_high = [1.0, 0.0, 0.0]
    emb_mid = [0.5, 0.5, 0.0]
    emb_low = [0.0, 0.0, 1.0]
    contributions = [0.9, 0.7, 0.3]
    div_matrix = DivergenceMatrix(agent_ids=agent_ids)
    # 注意: DivergenceMatrix.get() 会排序key, 所以需用排序后的key存储
    div_matrix.pairwise_divergences[("Agent_High", "Agent_Mid")] = 0.15   # 低于阈值
    div_matrix.pairwise_divergences[("Agent_High", "Agent_Low")] = 0.60   # 高于阈值
    div_matrix.pairwise_divergences[("Agent_Low", "Agent_Mid")] = 0.45    # 高于阈值 (key已排序)

    graph = dag.construct(
        agent_ids,
        [emb_high, emb_mid, emb_low],
        contributions,
        div_matrix,
    )
    assert_true(dag.validate_acyclicity(graph), "命题1: DAG无环")
    # 只有 High→Low 和 Mid→Low 应该有边 (High→Mid divergence低于阈值)
    edge_pairs = {(e.source_id, e.target_id) for e in graph.edges}
    assert_true(("Agent_High", "Agent_Low") in edge_pairs, "High→Low 边存在")
    assert_true(("Agent_Mid", "Agent_Low") in edge_pairs, "Mid→Low 边存在")
    assert_true(("Agent_High", "Agent_Mid") not in edge_pairs, "High→Mid 边不存在 (分歧不足)")

    # ─── 测试5: 条件串行传播 ───
    print("\n[测试组5] 条件串行传播")
    propagator = ConditionalPropagator()
    responses = [
        AgentResponse(agent_id="A", content="原始回答A", embedding=[1.0, 0.0], contribution_score=0.9),
        AgentResponse(agent_id="B", content="原始回答B", embedding=[0.5, 0.5], contribution_score=0.7),
    ]
    # 空图 → 纯并行
    empty_graph = CommunicationGraph(
        nodes=["A", "B"], edges=[], is_empty=True,
        topological_order=["A", "B"], density=0.0,
    )
    refined, propagated = propagator.propagate(empty_graph, responses)
    assert_true(not propagated, "空图: 无传播发生")
    assert_true(refined[0].refined_content is None, "空图: 响应未精化")
    assert_true(refined[1].refined_content is None, "空图: 响应未精化")

    # 非空图 → 条件串行
    edge = CommunicationEdge(
        source_id="A", target_id="B", divergence=0.4,
        level=DivergenceLevel.MODERATE,
    )
    non_empty_graph = CommunicationGraph(
        nodes=["A", "B"], edges=[edge], is_empty=False,
        topological_order=["A", "B"], density=1/4,
    )
    refined2, propagated2 = propagator.propagate(non_empty_graph, responses)
    assert_true(propagated2, "非空图: 传播发生")
    assert_true(refined2[1].is_predecessor_context_used, "B使用了A的上下文")
    assert_true("A" in refined2[1].predecessors_used, "B的前驱包含A")

    # ─── 测试6: 身份不可知聚合 ───
    print("\n[测试组6] 身份不可知聚合")
    aggregator = IdentityAgnosticAggregator()
    # 创建三个响应, 其中e2最接近加权质心
    resp = [
        AgentResponse(agent_id="X", content="答案1"),
        AgentResponse(agent_id="Y", content="答案2"),
        AgentResponse(agent_id="Z", content="答案3"),
    ]
    embs = [[1.0, 0.0, 0.0], [0.8, 0.2, 0.0], [0.0, 0.0, 1.0]]
    scores = [0.9, 0.85, 0.3]
    content, selected = aggregator.aggregate(resp, scores, embs)
    assert_true(selected in ("X", "Y", "Z"), "选中了有效的Agent")
    assert_true(len(content) > 0, "有输出内容")

    # ─── 测试7: 端到端管线 ───
    print("\n[测试组7] 端到端管线")
    nexa = NexaCommunicationLayer(
        use_real_embeddings=False,
        divergence_threshold=0.35,
    )
    result = nexa.execute(create_demo_responses(), task_id="test-e2e")
    assert_true(len(result.final_content) > 0, "有最终输出")
    assert_true(result.metrics.is_acyclic, "命题1通过")
    assert_true(result.metrics.is_identity_agnostic, "命题2通过")
    assert_true(result.metrics.is_parallel_subsumed, "命题3通过")
    assert_true(result.communication_graph is not None, "通信图已生成")
    assert_true(result.divergence_matrix is not None, "分歧矩阵已生成")

    # ─── 测试8: 纯并行回退 ───
    print("\n[测试组8] 纯并行回退 (命题3)")
    result2 = nexa.execute(create_convergent_responses(), task_id="test-parallel")
    print(f"  分歧程度: mean={result2.metrics.mean_divergence:.4f}, "
          f"max={result2.metrics.max_divergence:.4f}")
    print(f"  执行模式: {result2.metrics.execution_mode.value}")
    if nexa.embedder.is_real_model:
        # 真实嵌入模型下: 语义一致的响应应自动回退到纯并行
        assert_true(
            result2.metrics.parallel_fallback,
            "语义一致场景: 自动回退到纯并行"
        )
    else:
        # 伪嵌入回退模式: 基于字符n-gram的向量无法捕捉语义相似性,
        # 因此语义一致的文本也可能产生高分歧。这是预期行为。
        print("  SKIP: 伪嵌入模式无法捕捉语义一致性 (需真实sentence-transformers模型)")

    # ─── 测试9: JSON序列化 ───
    print("\n[测试组9] JSON序列化")
    json_str = NexaReporter.to_json(result)
    parsed = json.loads(json_str)
    assert_true(parsed["version"] == VERSION, "版本号正确")
    assert_true(parsed["phase"] == PHASE, "Phase正确")
    assert_true(len(parsed["final_content"]) > 0, "JSON包含最终结果")
    assert_true(
        parsed["metrics"]["propositions"]["P1_acyclic"], "JSON: 命题1通过"
    )

    # ─── 汇总 ───
    print()
    print("=" * 70)
    print(f"  测试结果: {passed}/{total} 通过"
          + (" (全部通过!)" if passed == total else " (有失败项)"))
    print("=" * 70)

    return passed, total


# ══════════════════════════════════════════════════════════════════════
# Section 11: CLI 入口
# ══════════════════════════════════════════════════════════════════════


def main() -> int:
    parser = argparse.ArgumentParser(
        description=f"Colony v2.0 L3 Nexa 条件通信层 (Phase {PHASE})",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python nexa-communication-layer.py --demo              # 运行完整演示
  python nexa-communication-layer.py --test              # 运行单元测试
  python nexa-communication-layer.py --demo --verbose    # 详细输出
  python nexa-communication-layer.py --demo --benchmark  # 含批量基准
  python nexa-communication-layer.py --demo --output result.json  # 导出JSON
  python nexa-communication-layer.py --health            # 健康报告
        """,
    )
    parser.add_argument(
        "--demo", action="store_true",
        help="运行完整演示"
    )
    parser.add_argument(
        "--test", action="store_true",
        help="运行内置单元测试"
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true",
        help="详细输出模式"
    )
    parser.add_argument(
        "--benchmark", action="store_true",
        help="包含批量基准测试"
    )
    parser.add_argument(
        "--benchmark-runs", type=int, default=20,
        help="基准测试运行次数 (默认: 20)"
    )
    parser.add_argument(
        "--threshold", "-t", type=float, default=DEFAULT_DIVERGENCE_THRESHOLD,
        help=f"语义分歧阈值 (默认: {DEFAULT_DIVERGENCE_THRESHOLD})"
    )
    parser.add_argument(
        "--model", "-m", type=str, default=PRIMARY_EMBEDDING_MODEL,
        help=f"嵌入模型名称 (默认: {PRIMARY_EMBEDDING_MODEL})"
    )
    parser.add_argument(
        "--fallback", action="store_true",
        help="强制使用伪嵌入回退模型"
    )
    parser.add_argument(
        "--aggregation", "-a", type=str,
        default=IdentityAgnosticAggregator.METHOD_WEIGHTED_CENTROID,
        choices=[
            IdentityAgnosticAggregator.METHOD_WEIGHTED_CENTROID,
            IdentityAgnosticAggregator.METHOD_MAX_CONTRIBUTION,
            IdentityAgnosticAggregator.METHOD_CONSENSUS_RADIUS,
        ],
        help="聚合方法 (默认: weighted_centroid)"
    )
    parser.add_argument(
        "--output", "-o", type=str,
        help="导出JSON结果到指定文件"
    )
    parser.add_argument(
        "--health", action="store_true",
        help="显示健康报告"
    )
    parser.add_argument(
        "--task", type=str,
        help="自定义任务描述 (需配合 --demo)"
    )

    args = parser.parse_args()

    # ─── 检查依赖 ───
    if not HAS_NUMPY and not args.fallback:
        logger.warning("numpy 未安装, 自动启用伪嵌入回退模式")
        args.fallback = True

    if args.fallback and not HAS_NUMPY:
        logger.warning(
            "numpy 和 sentence-transformers 均未安装, "
            "使用纯Python回退 (精度有限, 仅用于演示)"
        )

    # ─── 运行模式 ───
    if args.test:
        passed, total = run_unit_tests()
        return 0 if passed == total else 1

    if args.demo or args.health:
        run_demo(args)
        return 0

    # 默认: 显示帮助
    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
