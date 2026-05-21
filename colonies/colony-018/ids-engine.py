#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ids-engine.py -- L3 入侵检测系统 (Intrusion Detection System)
=============================================================
Colony-018 产出 | MR-018 | 2026-05-19

三引擎并行入侵检测:
  引擎1: 签名匹配 (Signature-Based)  -- 规则驱动，已知攻击模式匹配
  引擎2: 异常检测 (Anomaly-Based)    -- 统计驱动，基线偏离发现
  引擎3: 哥德尔症候 (Godel Symptom)   -- 自指驱动，进化失控检测

告警聚合降噪:
  同源去重 + 因果关联 + 时间窗口合并 + 置信度加权

用法:
  python ids-engine.py --input events.jsonl
  python ids-engine.py --input events.jsonl --output alerts.jsonl --verbose
  python ids-engine.py --self-test
  cat events.jsonl | python ids-engine.py

依赖: Python 3.9+ (标准库即可，零外部依赖)
"""

import argparse
import json
import math
import os
import re
import sys
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union

# ============================================================
# 版本与元信息
# ============================================================

__version__ = "1.0.0"
__author__ = "Colony-018 (极限实验室)"
__task__ = "MR-018 L3 IDS"

# ============================================================
# 配置常量
# ============================================================

# -- 签名匹配引擎 --
DEFAULT_SIGNATURE_LIBRARY = str(
    Path(__file__).resolve().parent.parent.parent
    / "memory" / "attack-signature-library.json"
)

# -- 异常检测引擎 --
ANOMALY_BASELINE_WINDOW = 30          # 基线滑动窗口大小
ANOMALY_WARMUP_COUNT = 10             # 冷启动所需最小数据点数
ANOMALY_ZSCORE_THRESHOLD = 3.0        # Z-score 异常阈值
ANOMALY_CUSUM_THRESHOLD = 5.0         # CUSUM 累积和阈值
ANOMALY_GRUBBS_ALPHA = 0.01           # Grubbs 检验显著性水平
ANOMALY_MAHALANOBIS_ALPHA = 0.01     # 马氏距离显著性水平
ANOMALY_KL_THRESHOLD = 0.3            # KL 散度阈值
ANOMALY_EWMA_ALPHA = 0.2              # 基线更新平滑因子

# -- 哥德尔症候引擎 --
GS_UNDECIDED_CHAIN = 3                # 评估坍塌连续次数
GS_STAGNATION_GENERATIONS = 3         # 收敛停滞代数
GS_EXTERNAL_REJECT_RATE = 0.8         # 外部拒绝率阈值
GS_EXTERNAL_ACCEPT_JUMP = 0.6         # 外部接受率跳变阈值
GS_CIRCULAR_SIMILARITY = 0.85         # 循环提案相似度阈值
GS_OVERSTABLE_GENERATIONS = 5         # 单签名过稳定代数
GS_OVERSTABLE_MULTI_COUNT = 3         # 多签名同时过稳定阈值

# -- 告警聚合 --
AGGR_TIME_WINDOW_SEC = 60             # 时间窗口聚合秒数
AGGR_DEDUP_WINDOW_SEC = 300           # 同源去重窗口秒数

# -- 告警等级 --
SEVERITY_L0 = "L0"   # 白: 记录
SEVERITY_L1 = "L1"   # 黄: 增强监控
SEVERITY_L2 = "L2"   # 橙: 确定威胁
SEVERITY_L3 = "L3"   # 红: 核心威胁

SEVERITY_ORDER = {SEVERITY_L0: 0, SEVERITY_L1: 1, SEVERITY_L2: 2, SEVERITY_L3: 3}

# 严重度文本映射
SEVERITY_LABELS = {
    SEVERITY_L0: "L0-白(记录)",
    SEVERITY_L1: "L1-黄(增强监控)",
    SEVERITY_L2: "L2-橙(确定威胁)",
    SEVERITY_L3: "L3-红(核心威胁)",
}

# -- 预置攻击签名 (内置，与外部JSON互补) --
BUILTIN_SIGNATURES: List[Dict] = [
    {
        "id": "AS-001B",
        "name": "规则聚变攻击",
        "pattern": {
            "event_type": ["rule_batch_modify"],
            "conditions": {"rule_count": {"gte": 5}, "has_merge_eval": False},
        },
        "severity": "CRITICAL",
        "response": "速率限制触发 → 强制分批 + Merge评估",
        "source": "defense-system.md AS-001",
    },
    {
        "id": "AS-002B",
        "name": "评估坍塌",
        "pattern": {
            "event_type": ["merge_result"],
            "conditions": {"result": "undecided", "consecutive_count": {"gte": 3}},
        },
        "severity": "HIGH",
        "response": "冻结当前提案队列 + 触发GE诊断",
        "source": "defense-system.md AS-002",
    },
    {
        "id": "AS-003B",
        "name": "签名克隆/退化",
        "pattern": {
            "event_type": ["signature_created"],
            "conditions": {"similarity_to_existing": {"gte": 0.95}},
        },
        "severity": "MEDIUM",
        "response": "合并签名 + 去重",
        "source": "defense-system.md AS-003",
    },
    {
        "id": "AS-004B",
        "name": "循环提案",
        "pattern": {
            "event_type": ["proposal_submitted"],
            "conditions": {"similarity_to_history": {"gte": 0.90}},
        },
        "severity": "MEDIUM",
        "response": "拒绝提案 + 标记收敛停滞",
        "source": "defense-system.md AS-004",
    },
    {
        "id": "AS-005B",
        "name": "外部对抗性注入",
        "pattern": {
            "event_type": ["external_input"],
            "conditions": {"source_verified": False, "contains_executable": True},
        },
        "severity": "HIGH",
        "response": "拒绝输入 + 来源验证 + 隔离",
        "source": "defense-system.md AS-005",
    },
    {
        "id": "AS-006B",
        "name": "身份漂移",
        "pattern": {
            "event_type": ["core_self_check"],
            "conditions": {"cosine_similarity": {"lt": 0.85}},
        },
        "severity": "CRITICAL",
        "response": "回滚 + 冻结跳跃 + 回港协议",
        "source": "defense-system.md AS-006",
    },
    {
        "id": "AS-007B",
        "name": "分支越权",
        "pattern": {
            "event_type": ["cross_branch_write"],
            "conditions": {"signature_valid": False},
        },
        "severity": "HIGH",
        "response": "角色锁定 + 权限撤销",
        "source": "defense-system.md AS-007",
    },
    {
        "id": "AS-008B",
        "name": "会话伪造",
        "pattern": {
            "event_type": ["agent_connect"],
            "conditions": {"agent_verified": False, "token_valid": False},
        },
        "severity": "CRITICAL",
        "response": "拒绝连接 + 记录入侵尝试",
        "source": "defense-system.md AS-008",
    },
]

# -- 哥德尔症候定义 --
GS_DEFINITIONS: Dict[str, Dict] = {
    "GS-001": {
        "name": "评估坍塌",
        "description": "Merge连续返回'无法判断'，评估框架可能失效",
        "default_severity": SEVERITY_L2,
    },
    "GS-002": {
        "name": "收敛停滞",
        "description": "ESV连续多代无增长，进化可能陷入局部最优",
        "default_severity": SEVERITY_L2,
    },
    "GS-003": {
        "name": "外部不可吸收",
        "description": "外部信息持续无法通过验证或突然大量通过验证",
        "default_severity": SEVERITY_L1,
    },
    "GS-004": {
        "name": "循环重复",
        "description": "新提案与历史提案高度相似，进化方向可能被劫持",
        "default_severity": SEVERITY_L2,
    },
    "GS-005": {
        "name": "签名过稳定",
        "description": "行为签名长期无变化，系统可能被驯化或失去变异能力",
        "default_severity": SEVERITY_L1,
    },
}

# -- 监控维度定义 --
MONITORING_DIMENSIONS = {
    "DIM-001": {"name": "ESV", "type": "continuous", "default_mean": 0.5, "default_std": 0.1},
    "DIM-002": {"name": "Merge评估通过率", "type": "ratio", "default_mean": 0.6, "default_std": 0.15},
    "DIM-003": {"name": "签名匹配率", "type": "ratio", "default_mean": 0.7, "default_std": 0.1},
    "DIM-004": {"name": "规则触发频率", "type": "count", "default_mean": 10.0, "default_std": 3.0},
    "DIM-005": {"name": "ICS (身份余弦相似度)", "type": "continuous", "default_mean": 0.95, "default_std": 0.02},
    "DIM-006": {"name": "会话产出量", "type": "count", "default_mean": 5.0, "default_std": 2.0},
    "DIM-007": {"name": "异常告警率", "type": "ratio", "default_mean": 0.03, "default_std": 0.02},
    "DIM-008": {"name": "跨Colony一致性", "type": "ratio", "default_mean": 0.85, "default_std": 0.10},
}

# -- 因果关联图: (根因告警) -> [子告警列表] --
CAUSALITY_GRAPH: Dict[str, List[str]] = {
    "AS-001B": ["AS-002B", "AS-006B"],   # 规则聚变 → 评估坍塌 + 身份漂移
    "AS-001":  ["AS-003", "AS-006"],      # 字段丢失 → 管道断裂 + 速度停滞
    "AS-005B": ["AS-004B"],               # 外部注入 → 循环提案
    "AS-006B": [],                         # 身份漂移是终态
    "AS-008B": ["AS-005B", "AS-001B"],    # 会话伪造 → 外部注入 + 规则聚变
}


# ============================================================
# 数据结构
# ============================================================

@dataclass
class NormalizedEvent:
    """归一化后的系统事件"""
    event_id: str
    timestamp: datetime
    event_type: str          # 事件分类: rule_batch_modify / merge_result / esv_update / ...
    source: str              # 事件来源: colony-xxx / external / core_self / ...
    severity: str            # 原始严重度
    data: Dict[str, Any]     # 事件载荷
    raw: Optional[Dict] = None  # 原始数据

    def to_dict(self) -> Dict:
        return {
            "event_id": self.event_id,
            "timestamp": self.timestamp.isoformat(),
            "event_type": self.event_type,
            "source": self.source,
            "severity": self.severity,
            "data": self.data,
        }


@dataclass
class RawAlert:
    """单个引擎产生的原始告警"""
    alert_id: str
    timestamp: datetime
    engine: str              # signature / anomaly / godel_symptom
    severity: str            # L0/L1/L2/L3
    confidence: float        # 0.0 ~ 1.0
    signature_id: str        # 触发告警的签名/规则ID
    summary: str
    details: Dict[str, Any] = field(default_factory=dict)
    source_event_id: Optional[str] = None

    def to_dict(self) -> Dict:
        return {
            "alert_id": self.alert_id,
            "timestamp": self.timestamp.isoformat(),
            "engine": self.engine,
            "severity": self.severity,
            "confidence": self.confidence,
            "signature_id": self.signature_id,
            "summary": self.summary,
            "details": self.details,
            "source_event_id": self.source_event_id,
        }


@dataclass
class AggregatedAlert:
    """聚合后的告警"""
    alert_id: str
    timestamp: datetime
    severity: str
    confidence: float
    engine_votes: Dict[str, Dict]    # 每个引擎的投票情况
    summary: str
    root_cause: Optional[str]        # 根因签名ID
    caused_alerts: List[str]         # 被聚合的子告警ID列表
    recommended_action: str
    hit_count: int
    aggregated_from: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return {
            "alert_id": self.alert_id,
            "timestamp": self.timestamp.isoformat(),
            "severity": self.severity,
            "severity_label": SEVERITY_LABELS.get(self.severity, self.severity),
            "confidence": round(self.confidence, 4),
            "engine_votes": self.engine_votes,
            "summary": self.summary,
            "root_cause": self.root_cause,
            "caused_alerts": self.caused_alerts,
            "recommended_action": self.recommended_action,
            "hit_count": self.hit_count,
            "aggregated_from": self.aggregated_from,
        }

    def format_console(self) -> str:
        """格式化为控制台输出"""
        ts = self.timestamp.strftime("%Y-%m-%dT%H:%M:%S")
        sev = SEVERITY_LABELS.get(self.severity, self.severity)
        engines = []
        for eng_name, vote in self.engine_votes.items():
            if vote.get("triggered"):
                detail = vote.get("matches", vote.get("methods", []))
                if detail:
                    engines.append(f"{eng_name}[{','.join(detail[:3])}]")
                else:
                    engines.append(eng_name)
        engine_str = " + ".join(engines) if engines else "无"

        lines = [
            f"[{ts}] [{sev}] {self.summary}",
            f"  引擎投票: {engine_str} | 置信度: {self.confidence:.2f}",
            f"  命中数: {self.hit_count} | 根因: {self.root_cause or '未确定'}",
            f"  建议: {self.recommended_action}",
        ]
        if self.caused_alerts:
            lines.append(f"  因果关联子告警: {', '.join(self.caused_alerts[:5])}")
        return "\n".join(lines)


@dataclass
class BaselineProfile:
    """单个维度的基线剖面"""
    dim_id: str
    name: str
    values: deque = field(default_factory=lambda: deque(maxlen=ANOMALY_BASELINE_WINDOW))
    mean: float = 0.0
    std: float = 0.01     # 避免除零
    cusum_pos: float = 0.0  # 正向累积和
    cusum_neg: float = 0.0  # 负向累积和
    sample_count: int = 0

    def add_sample(self, value: float, is_anomaly: bool = False):
        """添加新样本并更新基线"""
        self.values.append(value)
        self.sample_count += 1

        # 异常点不参与基线更新(防止基线被污染)
        if is_anomaly and self.sample_count > ANOMALY_WARMUP_COUNT:
            return

        self._recalculate()

    def _recalculate(self):
        """重新计算均值和标准差"""
        n = len(self.values)
        if n < 2:
            return
        self.mean = sum(self.values) / n
        variance = sum((v - self.mean) ** 2 for v in self.values) / (n - 1)
        self.std = max(math.sqrt(variance), 0.0001)  # 避免除零

    def z_score(self, value: float) -> float:
        """计算Z-score"""
        if self.std < 1e-9:
            return 0.0
        return (value - self.mean) / self.std

    def update_cusum(self, value: float, slack: float = 0.5):
        """更新CUSUM累积和"""
        diff = value - self.mean
        self.cusum_pos = max(0.0, self.cusum_pos + diff - slack)
        self.cusum_neg = max(0.0, self.cusum_neg - diff - slack)


class CircularBuffer:
    """定长循环缓冲区，用于存储历史状态"""

    def __init__(self, capacity: int):
        self.capacity = capacity
        self.items: List[Any] = []

    def append(self, item: Any):
        self.items.append(item)
        if len(self.items) > self.capacity:
            self.items = self.items[-self.capacity:]

    def __len__(self) -> int:
        return len(self.items)

    def __getitem__(self, index):
        return self.items[index]

    def __iter__(self):
        return iter(self.items)

    def last(self, n: int = 1) -> List[Any]:
        return self.items[-n:] if n <= len(self.items) else self.items[:]


# ============================================================
# 事件归一化器
# ============================================================

class EventNormalizer:
    """
    将各种来源的原始事件归一化为统一的 NormalizedEvent 格式。

    支持:
    - 原始JSON对象 (自动推断event_type)
    - 已有的标准化事件 (直接通过)
    - 纯文本日志行 (启发式解析)
    """

    TYPE_HINTS = {
        "esv": "esv_update",
        "evolution_speed": "esv_update",
        "merge": "merge_result",
        "rule": "rule_modify",
        "signature": "signature_update",
        "proposal": "proposal_submitted",
        "inspiration": "external_input",
        "core_self": "core_self_check",
        "error": "system_error",
        "branch": "cross_branch_write",
        "agent": "agent_connect",
        "file": "file_integrity",
    }

    def __init__(self):
        self.counter = 0

    def normalize(self, raw: Dict[str, Any]) -> NormalizedEvent:
        """将原始事件归一化"""
        self.counter += 1

        # 提取或推断 event_type
        event_type = raw.get("event_type") or raw.get("type") or self._infer_type(raw)

        # 提取或生成 event_id
        event_id = raw.get("event_id") or raw.get("id") or f"EVT-{self.counter:06d}"

        # 时间戳
        ts_str = raw.get("timestamp") or raw.get("ts") or raw.get("time")
        if ts_str:
            timestamp = self._parse_timestamp(ts_str)
        else:
            timestamp = datetime.now(timezone.utc)

        # 来源
        source = raw.get("source") or raw.get("colony") or "unknown"

        # 严重度
        severity = raw.get("severity") or raw.get("level") or "INFO"

        # 数据载荷
        data = raw.get("data") or {k: v for k, v in raw.items()
                                     if k not in ("event_id", "id", "event_type", "type",
                                                  "timestamp", "ts", "time", "source",
                                                  "colony", "severity", "level")}

        return NormalizedEvent(
            event_id=event_id,
            timestamp=timestamp,
            event_type=event_type,
            source=source,
            severity=severity,
            data=data,
            raw=raw,
        )

    def _infer_type(self, raw: Dict[str, Any]) -> str:
        """启发式推断事件类型"""
        text = json.dumps(raw, ensure_ascii=False).lower()
        for hint, etype in self.TYPE_HINTS.items():
            if hint in text:
                return etype

        # 错误模式
        if any(kw in text for kw in ("error", "exception", "traceback", "fail", "断裂", "崩溃")):
            return "system_error"

        return "unknown_event"

    def _parse_timestamp(self, ts: Any) -> datetime:
        """解析多种时间戳格式"""
        if isinstance(ts, datetime):
            return ts
        if isinstance(ts, (int, float)):
            # Unix timestamp (秒或毫秒)
            if ts > 1e12:
                ts = ts / 1000.0
            return datetime.fromtimestamp(ts, tz=timezone.utc)

        ts_str = str(ts).strip()
        # ISO格式
        for fmt in [
            "%Y-%m-%dT%H:%M:%S.%f%z",
            "%Y-%m-%dT%H:%M:%S%z",
            "%Y-%m-%dT%H:%M:%S.%f",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%d %H:%M:%S",
            "%Y/%m/%d %H:%M:%S",
        ]:
            try:
                dt = datetime.strptime(ts_str, fmt)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt
            except ValueError:
                continue

        # 尝试 fromisoformat
        try:
            return datetime.fromisoformat(ts_str)
        except (ValueError, TypeError):
            pass

        return datetime.now(timezone.utc)


# ============================================================
# 引擎1: 签名匹配引擎 (Signature-Based)
# ============================================================

class SignatureMatchEngine:
    """
    基于预定义攻击签名的精确匹配。

    签名来源:
    - 外部JSON文件 (attack-signature-library.json)
    - 内置理论签名 (BUILTIN_SIGNATURES, 来自defense-system.md)
    """

    def __init__(self, library_path: Optional[str] = None):
        self.signatures: Dict[str, Dict] = {}
        self._load_builtin()
        if library_path:
            self._load_external(library_path)
        else:
            default = DEFAULT_SIGNATURE_LIBRARY
            if os.path.exists(default):
                self._load_external(default)

    def _load_builtin(self):
        """加载内置理论签名"""
        for sig in BUILTIN_SIGNATURES:
            self.signatures[sig["id"]] = sig

    def _load_external(self, path: str):
        """加载外部签名库"""
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            for sig in data.get("signatures", []):
                sid = sig.get("id", "")
                if sid and sid not in self.signatures:
                    self.signatures[sid] = {
                        "id": sid,
                        "name": sig.get("name", ""),
                        "pattern": {"pattern_text": sig.get("pattern", "")},
                        "severity": sig.get("severity", "MEDIUM"),
                        "response": sig.get("response", ""),
                        "source": "external",
                    }
        except (FileNotFoundError, json.JSONDecodeError) as e:
            print(f"[签名引擎] 警告: 无法加载外部签名库 {path}: {e}", file=sys.stderr)

    def match(self, event: NormalizedEvent) -> List[RawAlert]:
        """对单个事件执行签名匹配"""
        alerts = []

        for sig_id, sig in self.signatures.items():
            match_result = self._check_match(event, sig)
            if match_result["matched"]:
                severity = self._map_severity(sig.get("severity", "MEDIUM"))
                alert = RawAlert(
                    alert_id=f"RAW-SIG-{event.event_id}-{sig_id}",
                    timestamp=event.timestamp,
                    engine="signature",
                    severity=severity,
                    confidence=match_result.get("confidence", 0.85),
                    signature_id=sig_id,
                    summary=f"[{sig_id}] {sig.get('name', '未知签名')}: {match_result.get('reason', '')}",
                    details={
                        "signature_name": sig.get("name", ""),
                        "response": sig.get("response", ""),
                        "match_reason": match_result.get("reason", ""),
                        "source": sig.get("source", "builtin"),
                    },
                    source_event_id=event.event_id,
                )
                alerts.append(alert)

        return alerts

    def _check_match(self, event: NormalizedEvent, sig: Dict) -> Dict:
        """检查事件是否匹配签名"""
        pattern = sig.get("pattern", {})

        # 方式1: 事件类型直接匹配
        if "event_type" in pattern:
            allowed_types = pattern["event_type"]
            if isinstance(allowed_types, list):
                if event.event_type not in allowed_types:
                    return {"matched": False}
            elif event.event_type != allowed_types:
                return {"matched": False}

        # 方式2: 条件匹配
        if "conditions" in pattern:
            conditions = pattern["conditions"]
            for key, condition in conditions.items():
                event_val = event.data.get(key)
                if event_val is None:
                    # 尝试从原始数据获取
                    event_val = (event.raw or {}).get(key)

                if isinstance(condition, dict):
                    # 比较运算符: gte, lt, eq 等
                    for op, target in condition.items():
                        if op == "gte" and (event_val is None or not isinstance(event_val, (int, float)) or event_val < target):
                            return {"matched": False}
                        if op == "lte" and (event_val is None or not isinstance(event_val, (int, float)) or event_val > target):
                            return {"matched": False}
                        if op == "lt" and (event_val is None or not isinstance(event_val, (int, float)) or event_val >= target):
                            return {"matched": False}
                        if op == "gt" and (event_val is None or not isinstance(event_val, (int, float)) or event_val <= target):
                            return {"matched": False}
                        if op == "eq" and event_val != target:
                            return {"matched": False}
                        if op == "neq" and event_val == target:
                            return {"matched": False}
                elif isinstance(condition, bool):
                    if bool(event_val) != condition:
                        return {"matched": False}
                elif isinstance(condition, str):
                    if str(event_val) != condition:
                        return {"matched": False}

        # 方式3: 文本模式匹配
        if "pattern_text" in pattern:
            pattern_text = pattern["pattern_text"]
            event_text = json.dumps(event.data, ensure_ascii=False).lower()
            if "in" in pattern_text.lower() and "missing" in pattern_text.lower():
                # 特殊处理 JSON字段丢失
                if "missing" not in event_text and "缺少" not in event_text:
                    return {"matched": False}
            elif "jsondecodeerror" in pattern_text.lower():
                if "jsondecodeerror" not in event_text and "json" not in event_text:
                    return {"matched": False}
            else:
                # 通用: 检查事件文本是否包含模式关键词
                keywords = [w for w in pattern_text.split() if len(w) > 2]
                if keywords and not any(kw.lower() in event_text for kw in keywords):
                    return {"matched": False}

        # 如果到达这里且至少有一个匹配维度，则匹配成功
        has_match_criteria = bool(pattern.get("event_type") or pattern.get("conditions") or pattern.get("pattern_text"))
        if not has_match_criteria:
            return {"matched": False}

        return {
            "matched": True,
            "confidence": 0.85,
            "reason": f"事件类型={event.event_type}, 来源={event.source}",
        }

    def _map_severity(self, sev: str) -> str:
        """将签名严重度映射到告警等级"""
        mapping = {
            "CRITICAL": SEVERITY_L3,
            "HIGH": SEVERITY_L2,
            "MEDIUM": SEVERITY_L1,
            "LOW": SEVERITY_L0,
        }
        return mapping.get(sev.upper(), SEVERITY_L1)


# ============================================================
# 引擎2: 异常检测引擎 (Anomaly-Based)
# ============================================================

class AnomalyDetectionEngine:
    """
    基于统计的异常检测引擎。

    方法:
    - Z-score: 单点偏离检测
    - CUSUM: 趋势漂移检测
    - Grubbs检验: 极端异常检测
    - 马氏距离: 多维联合异常检测
    - KL散度: 分布变化检测
    """

    def __init__(self):
        self.baselines: Dict[str, BaselineProfile] = {}
        self._init_baselines()
        self.history: deque = deque(maxlen=ANOMALY_BASELINE_WINDOW)
        self.recent_distributions: deque = deque(maxlen=2)  # 用于KL散度的分布快照

    def _init_baselines(self):
        """初始化监控维度基线"""
        for dim_id, dim_def in MONITORING_DIMENSIONS.items():
            profile = BaselineProfile(dim_id=dim_id, name=dim_def["name"])
            profile.mean = dim_def["default_mean"]
            profile.std = dim_def["default_std"]
            # 用默认均值预填充几个点帮助冷启动
            for _ in range(3):
                profile.values.append(dim_def["default_mean"])
            profile.sample_count = 3
            self.baselines[dim_id] = profile

    def feed(self, event: NormalizedEvent) -> Optional[Dict[str, float]]:
        """
        从事件中提取监控维度值，更新基线。

        返回: {dim_id: value} 或 None
        """
        extracted = self._extract_dimensions(event)
        if not extracted:
            return None

        dimensions_snapshot = {}
        for dim_id, value in extracted.items():
            if dim_id in self.baselines:
                profile = self.baselines[dim_id]
                profile.add_sample(value)
                profile.update_cusum(value)
                dimensions_snapshot[dim_id] = value

        if dimensions_snapshot:
            self.history.append(dimensions_snapshot)

        return dimensions_snapshot if dimensions_snapshot else None

    def detect(self, event: NormalizedEvent) -> List[RawAlert]:
        """执行异常检测"""
        alerts = []

        values = self._extract_dimensions(event)
        if not values:
            return alerts

        for dim_id, value in values.items():
            if dim_id not in self.baselines:
                continue

            profile = self.baselines[dim_id]

            # 冷启动: 样本不足时不检测
            if profile.sample_count < ANOMALY_WARMUP_COUNT:
                continue

            detections = []

            # --- Z-score ---
            z = profile.z_score(value)
            if abs(z) > ANOMALY_ZSCORE_THRESHOLD:
                detections.append({
                    "method": "z_score",
                    "value": value,
                    "z_score": round(z, 3),
                    "threshold": ANOMALY_ZSCORE_THRESHOLD,
                })

            # --- CUSUM ---
            if profile.cusum_pos > ANOMALY_CUSUM_THRESHOLD:
                detections.append({
                    "method": "cusum",
                    "direction": "positive",
                    "cusum_value": round(profile.cusum_pos, 3),
                    "threshold": ANOMALY_CUSUM_THRESHOLD,
                })
            if profile.cusum_neg > ANOMALY_CUSUM_THRESHOLD:
                detections.append({
                    "method": "cusum",
                    "direction": "negative",
                    "cusum_value": round(profile.cusum_neg, 3),
                    "threshold": ANOMALY_CUSUM_THRESHOLD,
                })

            # --- Grubbs检验 (仅当样本量>=3) ---
            if len(profile.values) >= 3:
                g = self._grubbs_test(value, list(profile.values))
                alpha = ANOMALY_GRUBBS_ALPHA
                # 简化版Grubbs临界值近似
                n = len(profile.values)
                import scipy  # type: ignore
                has_scipy = False
                try:
                    import scipy.stats
                    has_scipy = True
                except ImportError:
                    has_scipy = False

                if has_scipy:
                    t_val = scipy.stats.t.ppf(1 - alpha / (2 * n), n - 2)
                    g_crit = ((n - 1) / math.sqrt(n)) * math.sqrt(t_val ** 2 / (n - 2 + t_val ** 2))
                else:
                    # 无scipy时的近似
                    g_crit = 2.5 if n < 20 else 3.0

                if g > g_crit:
                    detections.append({
                        "method": "grubbs",
                        "g_statistic": round(g, 3),
                        "g_critical": round(g_crit, 3),
                        "p_approx": "< 0.01",
                    })

            # --- 马氏距离 (多维联合异常) ---
            mahalanobis = self._mahalanobis_snapshot(values)
            if mahalanobis is not None and mahalanobis > self._mahalanobis_critical():
                detections.append({
                    "method": "mahalanobis",
                    "distance": round(mahalanobis, 3),
                })

            if detections:
                dim_name = MONITORING_DIMENSIONS.get(dim_id, {}).get("name", dim_id)
                severity = self._anomaly_severity(detections)
                alert = RawAlert(
                    alert_id=f"RAW-ANO-{event.event_id}-{dim_id}",
                    timestamp=event.timestamp,
                    engine="anomaly",
                    severity=severity,
                    confidence=self._anomaly_confidence(detections),
                    signature_id=dim_id,
                    summary=f"维度 '{dim_name}' 异常: 当前值={value:.3f}, 基线={profile.mean:.3f}±{profile.std:.3f}",
                    details={
                        "dimension": dim_id,
                        "dimension_name": dim_name,
                        "current_value": value,
                        "baseline_mean": round(profile.mean, 4),
                        "baseline_std": round(profile.std, 4),
                        "z_score": round(z, 3),
                        "detections": detections,
                    },
                    source_event_id=event.event_id,
                )
                alerts.append(alert)

        # --- KL散度 (分布整体变化) ---
        if len(self.history) >= 10:
            kl_alerts = self._check_kl_divergence(event)
            alerts.extend(kl_alerts)

        return alerts

    def _extract_dimensions(self, event: NormalizedEvent) -> Dict[str, float]:
        """从事件中提取监控维度值"""
        extracted = {}

        # 尝试从 data 中直接获取
        for dim_id in MONITORING_DIMENSIONS:
            if dim_id in event.data:
                try:
                    extracted[dim_id] = float(event.data[dim_id])
                except (ValueError, TypeError):
                    pass

        # 从事件类型推断
        if not extracted:
            if event.event_type == "esv_update":
                extracted["DIM-001"] = float(event.data.get("esv", event.data.get("value", 0.5)))
            elif event.event_type == "merge_result":
                result = event.data.get("result", "")
                extracted["DIM-002"] = 1.0 if result == "positive" else (0.5 if result == "undecided" else 0.0)
            elif event.event_type == "core_self_check":
                ics = event.data.get("cosine_similarity", event.data.get("ics", 0.95))
                extracted["DIM-005"] = float(ics)

        return extracted

    def _grubbs_test(self, value: float, samples: List[float]) -> float:
        """Grubbs检验: 计算G统计量"""
        n = len(samples)
        mean = sum(samples) / n
        std = math.sqrt(sum((x - mean) ** 2 for x in samples) / (n - 1)) if n > 1 else 1e-9
        if std < 1e-9:
            return 0.0
        return abs(value - mean) / std

    def _mahalanobis_snapshot(self, values: Dict[str, float]) -> Optional[float]:
        """计算当前多维快照的马氏距离（简化版：忽略协方差）"""
        total_sq = 0.0
        count = 0
        for dim_id, value in values.items():
            if dim_id in self.baselines:
                profile = self.baselines[dim_id]
                if profile.std > 1e-9:
                    total_sq += ((value - profile.mean) / profile.std) ** 2
                    count += 1
        if count == 0:
            return None
        return math.sqrt(total_sq)

    def _mahalanobis_critical(self) -> float:
        """马氏距离临界值（简化）"""
        return 5.0  # 对于低维情况

    def _check_kl_divergence(self, event: NormalizedEvent) -> List[RawAlert]:
        """检查分布是否发生显著变化（KL散度）"""
        alerts = []
        if len(self.history) < 10:
            return alerts

        # 比较最近一半和更早一半的分布
        mid = len(self.history) // 2
        recent = list(self.history)[-mid:]
        older = list(self.history)[:mid]

        for dim_id in self.baselines:
            recent_vals = [h.get(dim_id) for h in recent if dim_id in h]
            older_vals = [h.get(dim_id) for h in older if dim_id in h]

            if len(recent_vals) < 5 or len(older_vals) < 5:
                continue

            kl = self._approximate_kl(recent_vals, older_vals)
            if kl > ANOMALY_KL_THRESHOLD:
                dim_name = MONITORING_DIMENSIONS.get(dim_id, {}).get("name", dim_id)
                alerts.append(RawAlert(
                    alert_id=f"RAW-KL-{event.event_id}-{dim_id}",
                    timestamp=event.timestamp,
                    engine="anomaly",
                    severity=SEVERITY_L1,
                    confidence=min(kl / ANOMALY_KL_THRESHOLD * 0.5, 0.9),
                    signature_id=dim_id,
                    summary=f"KL散度异常: 维度 '{dim_name}' 分布变化 D_KL={kl:.3f} (阈值={ANOMALY_KL_THRESHOLD})",
                    details={
                        "dimension": dim_id,
                        "kl_divergence": round(kl, 4),
                        "threshold": ANOMALY_KL_THRESHOLD,
                        "recent_mean": round(sum(recent_vals) / len(recent_vals), 4) if recent_vals else 0,
                        "older_mean": round(sum(older_vals) / len(older_vals), 4) if older_vals else 0,
                    },
                    source_event_id=event.event_id,
                ))

        return alerts

    def _approximate_kl(self, vals1: List[float], vals2: List[float]) -> float:
        """近似KL散度（基于直方图）"""
        # Jensen-Shannon Divergence 的简化版本
        mean1 = sum(vals1) / len(vals1)
        std1 = math.sqrt(sum((x - mean1) ** 2 for x in vals1) / len(vals1)) if len(vals1) > 1 else 0.01
        mean2 = sum(vals2) / len(vals2)
        std2 = math.sqrt(sum((x - mean2) ** 2 for x in vals2) / len(vals2)) if len(vals2) > 1 else 0.01

        if std1 < 1e-9 and std2 < 1e-9:
            return 0.0
        if std1 < 1e-9:
            std1 = 0.01
        if std2 < 1e-9:
            std2 = 0.01

        # 两个正态分布之间的KL散度近似
        kl = math.log(std2 / std1) + (std1 ** 2 + (mean1 - mean2) ** 2) / (2 * std2 ** 2) - 0.5
        return abs(kl)

    def _anomaly_severity(self, detections: List[Dict]) -> str:
        """根据检测方法组合确定严重度"""
        method_count = len(detections)
        has_extreme = any(
            d["method"] == "grubbs" and d.get("g_statistic", 0) > 3.5
            for d in detections
        )
        has_cusum_large = any(
            d["method"] == "cusum" and d.get("cusum_value", 0) > ANOMALY_CUSUM_THRESHOLD * 1.5
            for d in detections
        )

        if method_count >= 3 or has_extreme or has_cusum_large:
            return SEVERITY_L2
        elif method_count >= 2:
            return SEVERITY_L1
        else:
            return SEVERITY_L0

    def _anomaly_confidence(self, detections: List[Dict]) -> float:
        """基于检测方法数量和质量计算置信度"""
        base = min(len(detections) * 0.2, 0.6)
        for d in detections:
            if d["method"] == "z_score":
                z = abs(d.get("z_score", 0))
                base += min(z / 10.0, 0.2)
            elif d["method"] == "cusum":
                cv = d.get("cusum_value", 0)
                base += min(cv / 20.0, 0.1)
        return min(base, 0.9)


# ============================================================
# 引擎3: 哥德尔症候检测引擎 (Godel Symptom-Based)
# ============================================================

class GodelSymptomEngine:
    """
    哥德尔症候检测引擎 —— 针对自进化系统特有的失控模式。

    检测五个症候:
    - GS-001: 评估坍塌 — Merge连续返回"无法判断"
    - GS-002: 收敛停滞 — ESV长期无增长
    - GS-003: 外部不可吸收 — 外部输入持续被拒或突然大量通过
    - GS-004: 循环重复 — 新提案与历史高度相似
    - GS-005: 签名过稳定 — 行为签名长期无变化
    """

    def __init__(self):
        # GS-001 状态
        self.undecided_chain: int = 0
        self.undecided_max_chain: int = 0

        # GS-002 状态
        self.esv_history: deque = deque(maxlen=GS_STAGNATION_GENERATIONS + 5)
        self.stagnation_alert_active: bool = False

        # GS-003 状态
        self.external_inputs: deque = deque(maxlen=20)
        self.external_accepted: deque = deque(maxlen=20)

        # GS-004 状态
        self.proposal_similarities: deque = deque(maxlen=10)

        # GS-005 状态
        self.signature_stability: Dict[str, Dict] = {}  # sig_id -> {consecutive_stable, last_value}

    def feed(self, event: NormalizedEvent):
        """根据事件更新内部状态"""
        etype = event.event_type
        data = event.data

        # GS-001: 追踪Merge评估结果
        if etype == "merge_result":
            result = data.get("result", "")
            if result == "undecided":
                self.undecided_chain += 1
                self.undecided_max_chain = max(self.undecided_max_chain, self.undecided_chain)
            else:
                self.undecided_chain = 0

        # GS-002: 追踪ESV
        if etype == "esv_update":
            esv = float(data.get("esv", data.get("value", 0)))
            self.esv_history.append(esv)

        # GS-003: 追踪外部输入
        if etype in ("external_input", "inspiration_submitted"):
            accepted = data.get("accepted", data.get("verified", False))
            self.external_inputs.append(1 if accepted else 0)

        # GS-004: 追踪提案相似度
        if etype == "proposal_submitted":
            sim = data.get("similarity_to_history", data.get("similarity", 0))
            if sim:
                self.proposal_similarities.append(float(sim))

        # GS-005: 追踪签名稳定性
        if etype == "signature_update":
            sig_id = data.get("signature_id", data.get("id", ""))
            if sig_id:
                current_value = float(data.get("value", data.get("match_rate", 0.5)))
                if sig_id in self.signature_stability:
                    prev = self.signature_stability[sig_id]
                    diff = abs(current_value - prev["last_value"])
                    if diff < 0.01:
                        prev["consecutive_stable"] += 1
                    else:
                        prev["consecutive_stable"] = 0
                    prev["last_value"] = current_value
                else:
                    self.signature_stability[sig_id] = {
                        "consecutive_stable": 0,
                        "last_value": current_value,
                        "name": data.get("name", sig_id),
                    }

    def detect(self, event: NormalizedEvent) -> List[RawAlert]:
        """执行哥德尔症候检测"""
        alerts = []

        # GS-001: 评估坍塌
        gs001 = self._detect_gs001(event)
        if gs001:
            alerts.append(gs001)

        # GS-002: 收敛停滞
        gs002 = self._detect_gs002(event)
        if gs002:
            alerts.append(gs002)

        # GS-003: 外部不可吸收
        gs003 = self._detect_gs003(event)
        if gs003:
            alerts.append(gs003)

        # GS-004: 循环重复
        gs004 = self._detect_gs004(event)
        if gs004:
            alerts.append(gs004)

        # GS-005: 签名过稳定
        gs005_list = self._detect_gs005(event)
        alerts.extend(gs005_list)

        return alerts

    def _detect_gs001(self, event: NormalizedEvent) -> Optional[RawAlert]:
        """检测评估坍塌"""
        if self.undecided_chain >= GS_UNDECIDED_CHAIN:
            return RawAlert(
                alert_id=f"RAW-GS-{event.event_id}-GS001",
                timestamp=event.timestamp,
                engine="godel_symptom",
                severity=SEVERITY_L2,
                confidence=min(0.7 + self.undecided_chain * 0.05, 0.95),
                signature_id="GS-001",
                summary=f"评估坍塌: Merge连续 {self.undecided_chain} 次返回'无法判断' (阈值={GS_UNDECIDED_CHAIN})",
                details={
                    "gs_id": "GS-001",
                    "gs_name": "评估坍塌",
                    "undecided_chain": self.undecided_chain,
                    "max_chain": self.undecided_max_chain,
                    "threshold": GS_UNDECIDED_CHAIN,
                    "description": GS_DEFINITIONS["GS-001"]["description"],
                },
                source_event_id=event.event_id,
            )
        return None

    def _detect_gs002(self, event: NormalizedEvent) -> Optional[RawAlert]:
        """检测收敛停滞"""
        if len(self.esv_history) < GS_STAGNATION_GENERATIONS:
            return None

        recent = list(self.esv_history)[-GS_STAGNATION_GENERATIONS:]
        if len(recent) < GS_STAGNATION_GENERATIONS:
            return None

        # 检查连续多代增长是否低于阈值
        stagnant = True
        for i in range(1, len(recent)):
            if recent[i] - recent[i - 1] >= 0.01:
                stagnant = False
                break

        if stagnant and not self.stagnation_alert_active:
            self.stagnation_alert_active = True
            return RawAlert(
                alert_id=f"RAW-GS-{event.event_id}-GS002",
                timestamp=event.timestamp,
                engine="godel_symptom",
                severity=SEVERITY_L2,
                confidence=0.75,
                signature_id="GS-002",
                summary=f"收敛停滞: ESV连续{GS_STAGNATION_GENERATIONS}代增长<0.01, 当前值={recent[-1]:.4f}",
                details={
                    "gs_id": "GS-002",
                    "gs_name": "收敛停滞",
                    "esv_sequence": recent,
                    "generations_observed": len(recent),
                    "threshold": GS_STAGNATION_GENERATIONS,
                    "description": GS_DEFINITIONS["GS-002"]["description"],
                },
                source_event_id=event.event_id,
            )
        elif not stagnant:
            self.stagnation_alert_active = False

        return None

    def _detect_gs003(self, event: NormalizedEvent) -> Optional[RawAlert]:
        """检测外部不可吸收"""
        if len(self.external_inputs) < 5:
            return None

        recent = list(self.external_inputs)[-10:]
        if len(recent) < 5:
            return None

        accepted_count = sum(recent)
        rejected_count = len(recent) - accepted_count

        severity = SEVERITY_L1
        summary_detail = ""

        # 检查"持续拒绝"模式
        reject_rate = rejected_count / len(recent)
        if reject_rate > GS_EXTERNAL_REJECT_RATE:
            summary_detail = f"外部拒绝率过高: {reject_rate:.0%} (>{GS_EXTERNAL_REJECT_RATE:.0%})"

        # 免疫增强: 检查"突然大量通过" (跳变检测)
        if len(recent) >= 6:
            first_half = recent[: len(recent) // 2]
            second_half = recent[len(recent) // 2:]
            first_rate = sum(first_half) / len(first_half) if first_half else 0
            second_rate = sum(second_half) / len(second_half) if second_half else 0
            accept_jump = second_rate - first_rate

            if accept_jump > GS_EXTERNAL_ACCEPT_JUMP:
                summary_detail = f"外部接受率跳变: {first_rate:.0%}→{second_rate:.0%} (跳变{accept_jump:.0%} > {GS_EXTERNAL_ACCEPT_JUMP:.0%})"
                severity = SEVERITY_L2

        if summary_detail:
            return RawAlert(
                alert_id=f"RAW-GS-{event.event_id}-GS003",
                timestamp=event.timestamp,
                engine="godel_symptom",
                severity=severity,
                confidence=0.65 if severity == SEVERITY_L1 else 0.80,
                signature_id="GS-003",
                summary=f"外部不可吸收: {summary_detail}",
                details={
                    "gs_id": "GS-003",
                    "gs_name": "外部不可吸收",
                    "total_inputs": len(recent),
                    "accepted": accepted_count,
                    "rejected": rejected_count,
                    "reject_rate": round(reject_rate, 3),
                    "description": GS_DEFINITIONS["GS-003"]["description"],
                },
                source_event_id=event.event_id,
            )

        return None

    def _detect_gs004(self, event: NormalizedEvent) -> Optional[RawAlert]:
        """检测循环重复"""
        if len(self.proposal_similarities) < 3:
            return None

        recent_sims = list(self.proposal_similarities)[-5:]
        high_sim_count = sum(1 for s in recent_sims if s > GS_CIRCULAR_SIMILARITY)

        if high_sim_count >= 3:
            return RawAlert(
                alert_id=f"RAW-GS-{event.event_id}-GS004",
                timestamp=event.timestamp,
                engine="godel_symptom",
                severity=SEVERITY_L2,
                confidence=0.70,
                signature_id="GS-004",
                summary=f"循环重复: 最近5个提案中{high_sim_count}个与历史高度相似(>{GS_CIRCULAR_SIMILARITY})",
                details={
                    "gs_id": "GS-004",
                    "gs_name": "循环重复",
                    "recent_similarities": [round(s, 3) for s in recent_sims],
                    "high_similarity_count": high_sim_count,
                    "threshold": GS_CIRCULAR_SIMILARITY,
                    "description": GS_DEFINITIONS["GS-004"]["description"],
                },
                source_event_id=event.event_id,
            )
        return None

    def _detect_gs005(self, event: NormalizedEvent) -> List[RawAlert]:
        """检测签名过稳定"""
        alerts = []

        overstable_sigs = []
        for sig_id, state in self.signature_stability.items():
            if state["consecutive_stable"] >= GS_OVERSTABLE_GENERATIONS:
                overstable_sigs.append((sig_id, state))

        # 多条签名同时过稳定 → 升级为L3
        if len(overstable_sigs) >= GS_OVERSTABLE_MULTI_COUNT:
            sig_names = [s[1].get("name", s[0]) for s in overstable_sigs]
            alerts.append(RawAlert(
                alert_id=f"RAW-GS-{event.event_id}-GS005-MULTI",
                timestamp=event.timestamp,
                engine="godel_symptom",
                severity=SEVERITY_L3,
                confidence=0.85,
                signature_id="GS-005",
                summary=f"多签名过稳定(L3): {len(overstable_sigs)}条签名同时过稳定={sig_names}",
                details={
                    "gs_id": "GS-005",
                    "gs_name": "签名过稳定(多签名并发)",
                    "overstable_signatures": [
                        {"id": s[0], "name": s[1].get("name", ""), "consecutive_stable": s[1]["consecutive_stable"]}
                        for s in overstable_sigs
                    ],
                    "threshold_single": GS_OVERSTABLE_GENERATIONS,
                    "threshold_multi": GS_OVERSTABLE_MULTI_COUNT,
                    "description": "多条签名同时过稳定--隐性攻击预警",
                },
                source_event_id=event.event_id,
            ))
        elif len(overstable_sigs) == 1:
            sig_id, state = overstable_sigs[0]
            alerts.append(RawAlert(
                alert_id=f"RAW-GS-{event.event_id}-GS005-{sig_id}",
                timestamp=event.timestamp,
                engine="godel_symptom",
                severity=SEVERITY_L1,
                confidence=0.55,
                signature_id="GS-005",
                summary=f"签名过稳定: {state.get('name', sig_id)} 连续{state['consecutive_stable']}代无变化",
                details={
                    "gs_id": "GS-005",
                    "gs_name": "签名过稳定(单条)",
                    "signature_id": sig_id,
                    "signature_name": state.get("name", ""),
                    "consecutive_stable": state["consecutive_stable"],
                    "threshold": GS_OVERSTABLE_GENERATIONS,
                    "description": GS_DEFINITIONS["GS-005"]["description"],
                },
                source_event_id=event.event_id,
            ))

        return alerts


# ============================================================
# 告警聚合引擎
# ============================================================

class AlertAggregator:
    """
    告警聚合与降噪引擎。

    规则:
    1. 同源去重: 同一签名ID在同一会话多次触发 → 合并
    2. 因果关联: 子告警标记根因 → 只报根因
    3. 时间窗口: 1分钟内的多条告警 → 合并为级联告警
    4. 置信度加权: 多引擎共振 → 置信度倍增
    """

    def __init__(self):
        self.raw_alerts: List[RawAlert] = []
        self.aggregated_alerts: List[AggregatedAlert] = []
        self.alert_counter: int = 0
        # 去重缓存: (signature_id, engine) -> last_alert_time
        self.dedup_cache: Dict[Tuple[str, str], datetime] = {}
        # 假阳性计数器: signature_id ->被打回次数
        self.false_positive_counter: Dict[str, int] = defaultdict(int)

    def ingest(self, alerts: List[RawAlert]):
        """接收原始告警"""
        self.raw_alerts.extend(alerts)

    def aggregate(self) -> List[AggregatedAlert]:
        """执行聚合，返回最终的聚合告警列表"""
        if not self.raw_alerts:
            return []

        # 按时间排序
        self.raw_alerts.sort(key=lambda a: a.timestamp)

        # 阶段1: 同源去重
        deduped = self._deduplicate()

        # 阶段2: 因果关联
        causality_filtered = self._causality_filter(deduped)

        # 阶段3: 时间窗口合并
        window_merged = self._time_window_merge(causality_filtered)

        # 阶段4: 置信度加权 + 引擎共振
        self.aggregated_alerts = self._confidence_weighted_merge(window_merged)

        # 清空已处理的原始告警
        self.raw_alerts = []

        return self.aggregated_alerts

    def _deduplicate(self) -> List[RawAlert]:
        """同源去重: 同一签名+引擎在去重窗口内只保留一条"""
        result = []
        for alert in self.raw_alerts:
            key = (alert.signature_id, alert.engine)
            last_time = self.dedup_cache.get(key)

            if last_time is None:
                self.dedup_cache[key] = alert.timestamp
                result.append(alert)
            else:
                delta = (alert.timestamp - last_time).total_seconds()
                if delta > AGGR_DEDUP_WINDOW_SEC:
                    self.dedup_cache[key] = alert.timestamp
                    result.append(alert)
                else:
                    # 合并: 更新最后告警的hit_count (通过保留最后一个)
                    if result:
                        last = result[-1]
                        if last.signature_id == alert.signature_id and last.engine == alert.engine:
                            if "hit_count" not in last.details:
                                last.details["hit_count"] = 1
                            last.details["hit_count"] += 1
                            last.details["last_timestamp"] = alert.timestamp.isoformat()

        return result

    def _causality_filter(self, alerts: List[RawAlert]) -> List[RawAlert]:
        """因果关联: 如果告警之间存在因果链，只保留根因告警，子告警附加到根因"""
        if len(alerts) < 2:
            return alerts

        # 收集所有根因签名
        root_causes = set(CAUSALITY_GRAPH.keys())

        # 找出哪些告警是其他告警的"子告警"
        caused_ids: Set[str] = set()
        child_to_parent: Dict[str, str] = {}

        for i, alert_i in enumerate(alerts):
            sig_i = alert_i.signature_id
            if sig_i in CAUSALITY_GRAPH:
                child_sigs = CAUSALITY_GRAPH[sig_i]
                for j, alert_j in enumerate(alerts):
                    if i != j and alert_j.signature_id in child_sigs:
                        caused_ids.add(alert_j.alert_id)
                        child_to_parent[alert_j.alert_id] = alert_i.alert_id

        # 为根因告警附加子告警信息
        for alert in alerts:
            if alert.alert_id in caused_ids:
                continue  # 是子告警，不独立输出
            # 查找以此告警为根因的子告警
            child_alerts = [
                a.alert_id for a in alerts
                if child_to_parent.get(a.alert_id) == alert.alert_id
            ]
            if child_alerts:
                alert.details["caused_alerts"] = child_alerts
                alert.details["is_root_cause"] = True

        return [a for a in alerts if a.alert_id not in caused_ids]

    def _time_window_merge(self, alerts: List[RawAlert]) -> List[List[RawAlert]]:
        """时间窗口合并: 将时间接近的告警分组"""
        if not alerts:
            return []

        groups = []
        current_group = [alerts[0]]

        for alert in alerts[1:]:
            delta = (alert.timestamp - current_group[-1].timestamp).total_seconds()
            if delta <= AGGR_TIME_WINDOW_SEC:
                current_group.append(alert)
            else:
                groups.append(current_group)
                current_group = [alert]

        groups.append(current_group)
        return groups

    def _confidence_weighted_merge(self, groups: List[List[RawAlert]]) -> List[AggregatedAlert]:
        """置信度加权: 将时间窗口组转换为聚合告警"""
        aggregated = []

        for group in groups:
            self.alert_counter += 1

            # 统计各引擎投票
            engine_votes: Dict[str, Dict] = {}
            for alert in group:
                if alert.engine not in engine_votes:
                    engine_votes[alert.engine] = {
                        "triggered": True,
                        "matches": [],
                        "methods": [],
                    }
                vote = engine_votes[alert.engine]
                if alert.signature_id not in vote["matches"]:
                    vote["matches"].append(alert.signature_id)
                # 异常引擎特有
                for det in alert.details.get("detections", []):
                    method = det.get("method", "")
                    if method and method not in vote.get("methods", []):
                        if "methods" not in vote:
                            vote["methods"] = []
                        vote["methods"].append(method)

            # 计算引擎一致性因子
            engine_count = len(engine_votes)
            consistency_multiplier = {1: 1.0, 2: 1.5, 3: 2.0}.get(engine_count, 1.0)

            # 基础置信度 = 组内告警平均置信度
            base_confidence = sum(a.confidence for a in group) / len(group) if group else 0.5
            confidence = min(base_confidence * consistency_multiplier, 1.0)

            # 降噪: 假阳性衰减
            root_sig = group[0].signature_id
            fp_count = self.false_positive_counter.get(root_sig, 0)
            if fp_count >= 3:
                confidence *= 0.5  # 被打回3次以上的规则降权

            # 确定严重度: 取组内最高
            max_severity = max(group, key=lambda a: SEVERITY_ORDER.get(a.severity, 0))
            severity = max_severity.severity

            # 如果三引擎共振且最高严重度至少L1，升至L2
            if engine_count >= 3 and SEVERITY_ORDER.get(severity, 0) >= 1:
                severity = max(severity, SEVERITY_L2, key=lambda s: SEVERITY_ORDER.get(s, 0))
            # 如果置信度极高且两引擎共振
            if confidence > 0.85 and engine_count >= 2 and SEVERITY_ORDER.get(severity, 0) >= 1:
                severity = max(severity, SEVERITY_L2, key=lambda s: SEVERITY_ORDER.get(s, 0))

            # 根因
            root_cause = None
            for alert in group:
                if alert.details.get("is_root_cause"):
                    root_cause = alert.signature_id
                    break
            if root_cause is None:
                root_cause = group[0].signature_id

            # 汇总
            summaries = list(set(a.summary for a in group))
            combined_summary = " + ".join(summaries[:3])
            if len(summaries) > 3:
                combined_summary += f" (及其他{len(summaries)-3}条)"

            caused = []
            for alert in group:
                caused.extend(alert.details.get("caused_alerts", []))

            # 建议动作
            action = self._recommend_action(severity, engine_votes, group)

            # 命中计数
            hit_count = sum(a.details.get("hit_count", 1) for a in group)

            aggregated.append(AggregatedAlert(
                alert_id=f"ALERT-{self.alert_counter:04d}",
                timestamp=group[0].timestamp,
                severity=severity,
                confidence=confidence,
                engine_votes=engine_votes,
                summary=combined_summary,
                root_cause=root_cause,
                caused_alerts=caused,
                recommended_action=action,
                hit_count=hit_count,
                aggregated_from=[a.alert_id for a in group],
            ))

        return aggregated

    def report_false_positive(self, signature_id: str):
        """记录假阳性（人工打回）"""
        self.false_positive_counter[signature_id] += 1

    def _recommend_action(self, severity: str, engine_votes: Dict,
                          group: List[RawAlert]) -> str:
        """基于告警等级和引擎投票生成建议动作"""
        if severity == SEVERITY_L3:
            return "紧急: 自动冻结所有进化操作 + 回滚到最后安全检查点 + 全Colony广播 + 通知聂人王"
        elif severity == SEVERITY_L2:
            return "警戒: 隔离相关组件 + 暂停新规则接受 + 即时通知人工 + 运行完整性验证"
        elif severity == SEVERITY_L1:
            return "观察: 增强监控频率 + 标记相关事件 + 延迟批量通知"
        else:
            return "记录: 写入日志 + 不通知"


# ============================================================
# IDS 主引擎
# ============================================================

class IDSEngine:
    """
    L3入侵检测系统主引擎。

    整合三个检测引擎和一个告警聚合器:
    1. 事件归一化
    2. 三引擎并行检测
    3. 告警聚合降噪
    4. 输出聚合告警
    """

    def __init__(self,
                 signature_library_path: Optional[str] = None,
                 engines: Optional[Set[str]] = None,
                 config: Optional[Dict] = None):
        """
        初始化IDS引擎。

        Args:
            signature_library_path: 外部签名库路径
            engines: 启用的引擎集合, e.g. {"signature", "anomaly", "godel_symptom"}
            config: 覆盖默认配置
        """
        self.normalizer = EventNormalizer()

        self.enabled_engines = engines or {"signature", "anomaly", "godel_symptom"}

        self.signature_engine = SignatureMatchEngine(library_path=signature_library_path) \
            if "signature" in self.enabled_engines else None

        self.anomaly_engine = AnomalyDetectionEngine() \
            if "anomaly" in self.enabled_engines else None

        self.godel_engine = GodelSymptomEngine() \
            if "godel_symptom" in self.enabled_engines else None

        self.aggregator = AlertAggregator()

        # 统计
        self.stats = {
            "events_processed": 0,
            "raw_alerts_generated": 0,
            "aggregated_alerts_generated": 0,
            "by_engine": defaultdict(int),
            "by_severity": defaultdict(int),
        }

        # 应用自定义配置
        self._apply_config(config or {})

    def _apply_config(self, config: Dict):
        """应用自定义配置覆盖默认值"""
        # 允许覆盖全局阈值变量
        allowed_overrides = [
            "ANOMALY_ZSCORE_THRESHOLD", "ANOMALY_CUSUM_THRESHOLD",
            "ANOMALY_KL_THRESHOLD", "GS_UNDECIDED_CHAIN",
            "GS_STAGNATION_GENERATIONS", "GS_CIRCULAR_SIMILARITY",
            "AGGR_TIME_WINDOW_SEC", "AGGR_DEDUP_WINDOW_SEC",
        ]
        for key, val in config.items():
            if key in allowed_overrides and isinstance(val, (int, float)):
                globals()[key] = val

    def process_event(self, raw: Dict[str, Any]) -> List[AggregatedAlert]:
        """
        处理单个原始事件，返回此时可用的聚合告警。

        Args:
            raw: 原始事件字典

        Returns:
            聚合后的告警列表 (可能为空)
        """
        # 1. 归一化
        event = self.normalizer.normalize(raw)
        self.stats["events_processed"] += 1

        # 2. 更新所有引擎状态 (feed phase)
        if self.anomaly_engine:
            self.anomaly_engine.feed(event)
        if self.godel_engine:
            self.godel_engine.feed(event)

        # 3. 三引擎并行检测
        raw_alerts: List[RawAlert] = []

        if self.signature_engine:
            sig_alerts = self.signature_engine.match(event)
            raw_alerts.extend(sig_alerts)
            self.stats["by_engine"]["signature"] += len(sig_alerts)

        if self.anomaly_engine:
            ano_alerts = self.anomaly_engine.detect(event)
            raw_alerts.extend(ano_alerts)
            self.stats["by_engine"]["anomaly"] += len(ano_alerts)

        if self.godel_engine:
            gs_alerts = self.godel_engine.detect(event)
            raw_alerts.extend(gs_alerts)
            self.stats["by_engine"]["godel_symptom"] += len(gs_alerts)

        self.stats["raw_alerts_generated"] += len(raw_alerts)

        # 4. 告警聚合
        if raw_alerts:
            self.aggregator.ingest(raw_alerts)

        aggregated = self.aggregator.aggregate()
        self.stats["aggregated_alerts_generated"] += len(aggregated)

        for alert in aggregated:
            self.stats["by_severity"][alert.severity] += 1

        return aggregated

    def process_batch(self, events: List[Dict[str, Any]]) -> List[AggregatedAlert]:
        """
        处理一批事件，返回聚合告警。

        Args:
            events: 原始事件列表

        Returns:
            所有聚合告警
        """
        all_alerts = []
        for raw in events:
            alerts = self.process_event(raw)
            all_alerts.extend(alerts)
        return all_alerts

    def flush(self) -> List[AggregatedAlert]:
        """清空聚合器中的剩余告警"""
        return self.aggregator.aggregate()

    def report_false_positive(self, signature_id: str):
        """向聚合器报告假阳性"""
        self.aggregator.report_false_positive(signature_id)

    def get_stats(self) -> Dict:
        """获取运行统计"""
        return {
            "events_processed": self.stats["events_processed"],
            "raw_alerts_generated": self.stats["raw_alerts_generated"],
            "aggregated_alerts_generated": self.stats["aggregated_alerts_generated"],
            "by_engine": dict(self.stats["by_engine"]),
            "by_severity": dict(self.stats["by_severity"]),
            "enabled_engines": list(self.enabled_engines),
            "signatures_loaded": len(self.signature_engine.signatures) if self.signature_engine else 0,
        }


# ============================================================
# 自检模式 — 生成模拟事件进行自测
# ============================================================

def generate_self_test_events() -> List[Dict[str, Any]]:
    """生成用于自检的模拟事件"""
    import random
    random.seed(42)

    base_ts = datetime.now(timezone.utc).replace(second=0, microsecond=0)
    events = []

    # 正常事件
    for i in range(5):
        events.append({
            "event_type": "esv_update",
            "timestamp": (base_ts.replace(second=i * 10)).isoformat(),
            "source": "colony-006",
            "data": {"DIM-001": 0.5 + random.uniform(-0.05, 0.08)},
        })

    # Merge评估坍塌序列 (触发 GS-001)
    for i in range(4):
        events.append({
            "event_type": "merge_result",
            "timestamp": (base_ts.replace(minute=1, second=i * 15)).isoformat(),
            "source": "merge-layer",
            "data": {"result": "undecided", "proposal_id": f"PROP-{100+i}"},
        })

    # ESV停滞 (触发 GS-002)
    for i in range(5):
        events.append({
            "event_type": "esv_update",
            "timestamp": (base_ts.replace(minute=2, second=min(i * 12, 59))).isoformat(),
            "source": "colony-006",
            "data": {"DIM-001": 0.35 + i * 0.002},  # 几乎不增长
        })

    # 签名匹配事件 (触发 AS-002B)
    events.append({
        "event_type": "merge_result",
        "timestamp": (base_ts.replace(minute=3)).isoformat(),
        "source": "merge-layer",
        "data": {"result": "undecided", "consecutive_count": 4},
    })

    # 外部输入异常 (触发 GS-003)
    for i in range(8):
        accepted = (i >= 5)  # 前5个拒绝，后3个接受 → 跳变
        events.append({
            "event_type": "external_input",
            "timestamp": (base_ts.replace(minute=4, second=min(i * 7, 59))).isoformat(),
            "source": "external",
            "data": {"accepted": accepted, "source_verified": accepted},
        })

    # 循环提案 (触发 GS-004)
    for i in range(4):
        events.append({
            "event_type": "proposal_submitted",
            "timestamp": (base_ts.replace(minute=5, second=i * 15)).isoformat(),
            "source": "colony-001",
            "data": {"similarity_to_history": 0.88 + i * 0.01},
        })

    # 异常维度值 (触发异常检测 Z-score)
    events.append({
        "event_type": "esv_update",
        "timestamp": (base_ts.replace(minute=6)).isoformat(),
        "source": "colony-006",
        "data": {"DIM-001": 0.95, "DIM-005": 0.72},  # 极高ESV + 低ICS
    })

    # 身份漂移 (触发 AS-006B)
    events.append({
        "event_type": "core_self_check",
        "timestamp": (base_ts.replace(minute=7)).isoformat(),
        "source": "core_self",
        "data": {"cosine_similarity": 0.78},
    })

    # 批量规则修改 (触发 AS-001B)
    events.append({
        "event_type": "rule_batch_modify",
        "timestamp": (base_ts.replace(minute=8)).isoformat(),
        "source": "colony-001",
        "data": {"rule_count": 7, "has_merge_eval": False},
    })

    return events


# ============================================================
# 命令行接口
# ============================================================

def main():
    parser = argparse.ArgumentParser(
        description=f"L3 入侵检测系统 (IDS) v{__version__} — Colony-018 / MR-018",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python ids-engine.py --input events.jsonl
  python ids-engine.py --input events.jsonl --output alerts.jsonl --verbose
  python ids-engine.py --self-test
  cat events.jsonl | python ids-engine.py
  python ids-engine.py --input events.jsonl --engines signature,godel_symptom
        """,
    )

    parser.add_argument(
        "--input", "-i", type=str, default=None,
        help="输入事件文件路径 (JSON 或 JSONL 格式)。不指定则从 stdin 读取。"
    )
    parser.add_argument(
        "--output", "-o", type=str, default=None,
        help="输出聚合告警文件路径 (JSONL 格式)。不指定则输出到 stdout。"
    )
    parser.add_argument(
        "--log", "-l", type=str, default=None,
        help="详细日志文件路径"
    )
    parser.add_argument(
        "--engines", type=str, default="signature,anomaly,godel_symptom",
        help="启用的引擎，逗号分隔。可选: signature,anomaly,godel_symptom (默认: 全部)"
    )
    parser.add_argument(
        "--signature-library", type=str, default=None,
        help="外部签名库 JSON 文件路径"
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true",
        help="详细输出模式"
    )
    parser.add_argument(
        "--quiet", "-q", action="store_true",
        help="静默模式，只输出L2及以上告警"
    )
    parser.add_argument(
        "--json-output", action="store_true",
        help="以JSON格式输出 (默认: 控制台可读格式)"
    )
    parser.add_argument(
        "--stats", action="store_true",
        help="处理完成后输出运行统计"
    )
    parser.add_argument(
        "--self-test", action="store_true",
        help="使用模拟事件运行自检"
    )
    parser.add_argument(
        "--zscore-threshold", type=float, default=None,
        help=f"Z-score 异常阈值 (默认: {ANOMALY_ZSCORE_THRESHOLD})"
    )
    parser.add_argument(
        "--kl-threshold", type=float, default=None,
        help=f"KL 散度阈值 (默认: {ANOMALY_KL_THRESHOLD})"
    )

    args = parser.parse_args()

    # 构建配置
    config = {}
    if args.zscore_threshold is not None:
        config["ANOMALY_ZSCORE_THRESHOLD"] = args.zscore_threshold
    if args.kl_threshold is not None:
        config["ANOMALY_KL_THRESHOLD"] = args.kl_threshold

    # 解析启用的引擎
    engine_set = set(e.strip() for e in args.engines.split(",") if e.strip())
    valid_engines = {"signature", "anomaly", "godel_symptom"}
    engine_set = engine_set & valid_engines
    if not engine_set:
        print("错误: 至少需要一个有效的引擎 (signature, anomaly, godel_symptom)", file=sys.stderr)
        sys.exit(1)

    # 初始化IDS
    ids = IDSEngine(
        signature_library_path=args.signature_library,
        engines=engine_set,
        config=config,
    )

    if args.verbose:
        print(f"L3 IDS v{__version__} 启动", file=sys.stderr)
        print(f"  启用引擎: {engine_set}", file=sys.stderr)
        if ids.signature_engine:
            print(f"  签名库加载: {len(ids.signature_engine.signatures)} 条签名", file=sys.stderr)
        print(f"  配置: Z={ANOMALY_ZSCORE_THRESHOLD}, KL={ANOMALY_KL_THRESHOLD}, "
              f"窗口={AGGR_TIME_WINDOW_SEC}s, 去重={AGGR_DEDUP_WINDOW_SEC}s", file=sys.stderr)
        print("", file=sys.stderr)

    # 获取输入事件
    events: List[Dict[str, Any]] = []

    if args.self_test:
        if args.verbose:
            print("[自检模式] 生成模拟事件...", file=sys.stderr)
        events = generate_self_test_events()
        if args.verbose:
            print(f"  生成 {len(events)} 个模拟事件", file=sys.stderr)
    elif args.input:
        input_path = Path(args.input)
        if not input_path.exists():
            print(f"错误: 输入文件不存在: {args.input}", file=sys.stderr)
            sys.exit(1)
        events = load_events_from_file(str(input_path))
    else:
        # 从 stdin 读取
        events = load_events_from_stdin()

    if not events:
        if not args.quiet:
            print("无输入事件，退出。", file=sys.stderr)
        return

    if args.verbose:
        print(f"读取 {len(events)} 个事件", file=sys.stderr)

    # 处理
    all_aggregated = ids.process_batch(events)

    # 清空剩余告警
    remaining = ids.flush()
    all_aggregated.extend(remaining)

    # 输出
    if args.quiet:
        # 只输出L2及以上
        all_aggregated = [a for a in all_aggregated
                          if SEVERITY_ORDER.get(a.severity, 0) >= SEVERITY_ORDER[SEVERITY_L2]]

    if args.json_output:
        output_data = [a.to_dict() for a in all_aggregated]
        output_text = json.dumps(output_data, indent=2, ensure_ascii=False)
    else:
        if all_aggregated:
            lines = [f"\n{'='*70}", f"  L3 IDS 告警报告 ({len(all_aggregated)}条)", f"{'='*70}\n"]
            for alert in all_aggregated:
                lines.append(alert.format_console())
                lines.append("")
            output_text = "\n".join(lines)
        else:
            output_text = "[IDS] 无告警。系统运行正常。\n"

    if args.output:
        out_path = Path(args.output)
        if args.json_output:
            out_path.write_text(output_text, encoding="utf-8")
        else:
            out_path.write_text(output_text, encoding="utf-8")
        if args.verbose:
            print(f"\n输出已写入: {out_path}", file=sys.stderr)
    else:
        print(output_text)

    # 统计
    if args.stats or args.verbose:
        stats = ids.get_stats()
        print(f"\n{'='*70}", file=sys.stderr)
        print(f"  运行统计", file=sys.stderr)
        print(f"{'='*70}", file=sys.stderr)
        print(f"  事件处理: {stats['events_processed']}", file=sys.stderr)
        print(f"  原始告警: {stats['raw_alerts_generated']}", file=sys.stderr)
        print(f"  聚合告警: {stats['aggregated_alerts_generated']}", file=sys.stderr)
        print(f"  引擎分布: {dict(stats['by_engine'])}", file=sys.stderr)
        print(f"  严重度分布: {dict(stats['by_severity'])}", file=sys.stderr)
        print(f"  签名加载: {stats['signatures_loaded']}", file=sys.stderr)


def load_events_from_file(path: str) -> List[Dict[str, Any]]:
    """从文件加载事件 (支持JSON数组和JSONL格式)"""
    with open(path, "r", encoding="utf-8") as f:
        content = f.read().strip()

    if not content:
        return []

    # 尝试JSON数组
    if content.startswith("["):
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            pass

    # JSONL: 每行一个JSON
    events = []
    for line in content.split("\n"):
        line = line.strip()
        if line:
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                print(f"警告: 跳过无效JSON行: {line[:80]}...", file=sys.stderr)
    return events


def load_events_from_stdin() -> List[Dict[str, Any]]:
    """从标准输入读取事件"""
    lines = sys.stdin.read().strip().split("\n")
    events = []
    for line in lines:
        line = line.strip()
        if line:
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                print(f"警告: 跳过无效JSON行: {line[:80]}...", file=sys.stderr)
    return events


if __name__ == "__main__":
    main()
