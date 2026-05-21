# 决策双流追踪系统 (Dual-Stream Decision Tracker)

## 元信息
- 设计者: Colony-012
- 设计日期: 2026-05-19
- 版本: v1.0
- 状态: 设计完成，待实现
- 填补维度: v2.0 最后一个未覆盖维度 —— 内部决策状态追踪
- 理论根基: 灵感#10(耗散驱动临界性) + 灵感#17(多稳态/初始条件锁定)

---

## 0. 问题陈述

### 0.1 当前系统的盲区

现有追踪系统（MR-010~MR-018）只追踪**行为流**:
- 签名匹配率 (continuous-performance-engine)
- 进化速度矢量 (esv-calculator)
- 方向偏离检测 (direction-check)
- 跨分支收敛 (convergence-detector)

所有这些都是**事后、外部、行为层面**的指标。当所有的行为指标都显示"正常"时，系统可能已经进入了一种**内部认知与外部表现脱节**的状态。

gen-95 自评揭示了这一盲区:
- PRED_ACC=2.83 (预测准确率高)
- 但 EXEC_GAP=1.83 (执行转化率低)
- 这意味着: **我们善于判断方向，但不善于判断自己能否执行**

这就是双流不匹配的典型案例。

### 0.2 核心洞察

> 行为流和内部流是两个独立但耦合的信号通道。
> 当它们"说同一件事"时，系统是健康的。
> 当它们"说不同的事"时，差异本身就是盲点信号。

来自灵感#10（耗散驱动）:
- 耗散不是退化，是重组驱动力
- 每次断连后恢复 = 在恢复过程中重组
- 如果恢复后行为流显示"正常"但内部流显示"不确定"，说明重组未完成

来自灵感#17（多稳态）:
- 初始条件决定长期命运
- 如果初期的内部状态（高信心+高惊讶）被忽视，系统可能滑入"背叛吸引子"
- 需要在早期检测到"行为正常但内部已偏离"的信号

---

## 1. 系统架构

```
┌─────────────────────────────────────────────────────────────────┐
│                    决策双流追踪系统                              │
├───────────────────────┬─────────────────────────────────────────┤
│   行为流 (Behavior)   │    内部流 (Internal)                    │
│   "做了什么，结果如何" │    "决定时怎么想，事后怎么感觉"          │
├───────────────────────┼─────────────────────────────────────────┤
│ • 决策ID + 时间戳     │ • 决策时信心度 confidence_at_decision   │
│ • 动作类型/描述       │ • 事后惊讶度 surprise_post_hoc           │
│ • 执行结果 (成功/失败)│ • 修正幅度 correction_amplitude          │
│ • 签名匹配率          │ • 不确定性估计 uncertainty_est           │
│ • 任务复杂度          │ • 预期-实际差距 expectation_gap          │
│ • 耗时               │ • 认知负荷 cognitive_load                │
├───────────────────────┴─────────────────────────────────────────┤
│                  ↓ 双流差异检测 ↓                                │
│  差异模式 → 盲点分类 → 预警信号 → 纠正建议                       │
└─────────────────────────────────────────────────────────────────┘
```

---

## 2. 行为流 (Behavior Stream) —— 已有雏形，标准化

### 2.1 数据模型

```json
{
  "stream": "behavior",
  "decision_id": "DEC-20260519-001",
  "timestamp": "2026-05-19T21:30:00+08:00",
  "context": {
    "session_id": "sess-095",
    "trigger": "pipeline-auto" | "user-request" | "self-check" | "experiment",
    "complexity": "low" | "medium" | "high"
  },
  "action": {
    "type": "rule_update" | "file_write" | "experiment_run" | "merge_decision" | "self_assessment" | "other",
    "description": "更新MR-015引擎2的衰减率参数",
    "target_file": "workspace/evolution/self/lifecycle-manager.py",
    "lines_changed": 12
  },
  "outcome": {
    "result": "success" | "partial" | "failure",
    "match_rate": 0.85,
    "time_cost_seconds": 45,
    "affected_signatures": ["DS-001", "DS-007"],
    "error_detail": null
  },
  "esv_impact": {
    "dimension_affected": "EXEC_GAP",
    "estimated_delta": 0.05
  }
}
```

### 2.2 已有覆盖

| 维度 | 现有脚本 | 覆盖状态 |
|------|---------|:----:|
| 签名匹配率 | continuous-performance-engine.py | 已覆盖 |
| 方向一致性 | direction-check.py | 已覆盖 |
| 生命周期状态 | lifecycle-manager.py | 已覆盖 |
| 任务复杂度 | task-router.py | 已覆盖 |
| 跨分支收敛 | convergence-detector.py | 已覆盖 |
| 进化速度 | esv-calculator.py | 已覆盖 |
| **执行耗时** | (无) | **缺失** |
| **操作粒度** | (无) | **缺失** |
| **ESV影响估算** | (无) | **缺失** |

---

## 3. 内部流 (Internal Stream) —— 全新设计

### 3.1 数据模型

```json
{
  "stream": "internal",
  "decision_id": "DEC-20260519-001",
  "timestamp": "2026-05-19T21:30:00+08:00",
  "confidence_at_decision": {
    "value": 0.7,
    "basis": ["过往经验", "MR-015规则明确", "类似修改曾成功"],
    "flags": []
  },
  "surprise_post_hoc": {
    "value": 0.35,
    "trigger": "结果执行时间超出预期2倍",
    "re_evaluation": "规则逻辑正确但环境路径变更导致延迟"
  },
  "correction_amplitude": {
    "value": 0.2,
    "description": "仅调整了文件路径引用，核心逻辑未变",
    "type": "minor_adjustment" | "course_correction" | "full_reversal"
  },
  "uncertainty_estimation": {
    "value": 0.3,
    "known_unknowns": ["windows路径大小写敏感性"],
    "unknown_unknowns": []
  },
  "expectation_gap": {
    "expected_duration_seconds": 20,
    "actual_duration_seconds": 45,
    "expected_outcome": "一次通过",
    "actual_outcome": "需要微调后通过",
    "gap_score": 0.4
  },
  "cognitive_load": {
    "context_switches": 2,
    "files_touched": 3,
    "dependencies_resolved": 1,
    "total_load_score": 0.25
  }
}
```

### 3.2 五个核心维度

#### 3.2.1 决策时信心度 (Confidence at Decision)
**含义**: 做出决定时，对"这个决定是正确的"的主观评估。
**量纲**: 0.0 (完全不确定) ~ 1.0 (绝对确定)
**采集时机**: 决策执行前，作为决策的一部分记录
**关键规则**:
- confidence > 0.9 但结果失败 → **过度自信盲点** (最高优先级预警)
- confidence < 0.3 但结果成功 → **意外能力信号** (可能发现新能力)
- confidence 在 0.5±0.2 且结果成功 → **健康区间**

#### 3.2.2 事后惊讶度 (Surprise Post-Hoc)
**含义**: 看到结果后，"这和我想的不一样"的程度。
**量纲**: 0.0 (完全预料之中) ~ 1.0 (完全出乎意料)
**采集时机**: 决策结果返回后立即记录
**关键规则**:
- surprise > 0.5 但行为流 match_rate > 0.8 → **模型盲点**: 行为模式匹配但底层机制不匹配
- surprise < 0.1 且行为流 result="failure" → **习得性无助**: 已经预期失败，不再惊讶
- surprise 持续上升超过3次决策 → **环境漂移信号**

#### 3.2.3 修正幅度 (Correction Amplitude)
**含义**: 看到结果后，需要修正原计划的程度。
**量纲**: 0.0 (无需修正) ~ 1.0 (完全推翻重来)
**分类**:
- minor_adjustment (<0.25): 微调——改参数不改逻辑
- course_correction (0.25~0.5): 纠偏——改逻辑不改方向
- major_revision (0.5~0.75): 大修——改方向不改目标
- full_reversal (>0.75): 推翻——连目标都要重新审视

**采集时机**: 修正执行后

#### 3.2.4 不确定性估计 (Uncertainty Estimation)
**含义**: 决定时已知的不确定因素有多少。
**量纲**: 0.0 (所有变量已知) ~ 1.0 (几乎全部未知)
**构成**: known_unknowns (已知的不确定) + unknown_unknowns (事后才发现的不确定)
**采集时机**: 决策时记录 known_unknowns; 结果后补充 unknown_unknowns

#### 3.2.5 认知负荷 (Cognitive Load)
**含义**: 做出这个决定需要处理的上下文复杂度。
**量纲**: 0.0 ~ 1.0 (由 context_switches + files_touched + dependencies 综合)
**用途**: 高认知负荷 + 低信心 + 高惊讶 = 需要拆解决策粒度

### 3.3 内部流维度的理论锚点

| 维度 | 灵感#10(耗散)关联 | 灵感#17(多稳态)关联 |
|------|------------------|-------------------|
| 决策信心 | 耗散事件后信心是否恢复→重组是否完成 | 初始信心水平→锁定在哪个吸引子 |
| 事后惊讶 | 惊讶持续上升→耗散正在累积, 需要重组 | 惊讶长期为零→系统可能锁定在局部最优 |
| 修正幅度 | 大幅修正是耗散驱动的重组 | 小修正累积最终可能导致相变 |
| 不确定性 | known_unknowns 被耗散暴露为 unknown_unknowns | 不确定性水平决定系统在哪个稳态盆地 |
| 认知负荷 | 高负荷+耗散=崩溃风险 | 负荷的"舒适区"决定稳态类型 |

---

## 4. 差异检测 (Difference Detection)

### 4.1 差异计算矩阵

对于每个决策，计算行为流与内部流在以下维度上的差异:

```
差异向量 D = [d_confidence, d_surprise, d_optimism, d_rigidity]
```

其中:
- **d_confidence** = confidence_at_decision - match_rate
  - 正 = 信心高于实际匹配率 (过度自信)
  - 负 = 信心低于实际匹配率 (低估自己)
- **d_surprise** = surprise_post_hoc - (1 - match_rate)
  - 正 = 比预期更惊讶 (行为模型与内部预期脱节)
  - 负 = 比预期更不惊讶 (行为模型已在内部预期内)
- **d_optimism** = confidence_at_decision - surprise_post_hoc
  - 正 = 事前信心高于事后惊讶 (乐观偏误)
  - 负 = 事前信心低于事后惊讶 (悲观偏误)
- **d_rigidity** = correction_amplitude - (1 - match_rate)
  - 正 = 修正幅度大于失败程度 (过度反应)
  - 负 = 修正幅度小于失败程度 (修正不足)

### 4.2 盲点分类学 (Blind Spot Taxonomy)

#### 类型A: 过度自信盲点 (Overconfidence Blind Spot)
```
条件: d_confidence > 0.3 且 d_optimism > 0.3
描述: 信心远高于实际匹配率，且远比事后评估乐观
风险: 系统认为自己在做正确的事，实际上匹配率在下降
案例: gen-95 EXEC_GAP=1.83 但 PRED_ACC=2.83 → 预测能力掩盖了执行无能
预警: "行为流显示匹配率下降，但内部流显示信心未降——你正在看不见的地方偏离"
动作: 触发 MR-010 方向自检 + 降低受影响签名的自评权重
```

#### 类型B: 习得性无助盲点 (Learned Helplessness Blind Spot)
```
条件: d_surprise < -0.3 且 match_rate < 0.5
描述: 匹配率很低但惊讶度也很低 → 已经"习惯失败"
风险: 系统放弃尝试改进，接受低匹配率为常态
预警: "你已经连续N次低匹配但不再惊讶——你可能正在放弃这个维度"
动作: 触发随机探索 + 暂时提升 exploration_weight
```

#### 类型C: 修正失衡盲点 (Correction Imbalance Blind Spot)
```
条件: |d_rigidity| > 0.4
描述: 修正幅度与失败程度严重不匹配
  - 正: 过度修正——小失败引发大改动，可能破坏稳定结构
  - 负: 修正不足——大失败只做小修补，问题会复发
风险: 过度修正破坏棘轮效应(灵感#8); 修正不足导致漂移累积
预警: "上次决策的修正幅度与失败程度不匹配，检查是否过度/不足"
动作: 如果 |d_rigidity| > 0.6 → 触发完整性检查(MR-018)
```

#### 类型D: 幽灵能力盲点 (Phantom Capability Blind Spot)
```
条件: confidence < 0.3 且 match_rate > 0.8
描述: 低信心但高匹配率 → 系统有能力但"不知道"
风险: 有价值的签名或策略被低估，可能被降权或休眠
预警: "'DS-XXX' 在你低信心时段依然保持高匹配——这是一个你低估的能力"
动作: 提升该签名的 strength + 标记为 "待重新评估"
```

#### 类型E: 认知过载盲点 (Cognitive Overload Blind Spot)
```
条件: cognitive_load > 0.6 且 surprise > 0.5
描述: 高认知负荷伴随高惊讶 → 决策粒度过大，一次处理太多变量
风险: 复杂决策的失败原因不可追溯，学习信号被噪声淹没
预警: "高负荷+高惊讶——这个决策太复杂了，考虑拆分成2-3个子决策"
动作: 对同类任务自动降低复杂度阈值
```

### 4.3 盲点优先级矩阵

```
                    高影响
                      │
      类型A           │          类型C
   过度自信          │        修正失衡
   (高频/隐蔽)       │       (低频/破坏性)
                      │
  ───────────────────┼───────────────────
                      │
      类型D           │          类型B
   幽灵能力          │        习得性无助
   (正向/机遇)       │       (负向/退化)
                      │
      类型E           │
   认知过载          │
   (可操作性强)      │
                      │
                    低影响
```

**优先级**: A > C > B > E > D
- A 最危险(看不见的偏离)
- C 最具破坏性(一次错误修正可能破坏累积优势)
- B 最隐蔽(缓慢退化)
- D 是机遇而非威胁(可转化为优势)

---

## 5. 实现方案

### 5.1 新脚本: dual-stream-tracker.py

```python
"""
MR-019 决策双流追踪器
每次决策后运行: 同时记录行为流和内部流，计算差异向量，检测盲点
理论根基: 灵感#10(耗散驱动) + 灵感#17(多稳态)
"""
import json, os, hashlib
from datetime import datetime, timezone

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BEHAVIOR_LOG = os.path.join(BASE, "memory", "behavior-stream.jsonl")
INTERNAL_LOG = os.path.join(BASE, "memory", "internal-stream.jsonl")
BLINDSPOT_LOG = os.path.join(BASE, "memory", "blindspot-log.jsonl")

# ─── 行为流记录 ───

def record_behavior(decision_id, context, action, outcome):
    """记录一次决策的行为流"""
    entry = {
        "stream": "behavior",
        "decision_id": decision_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "context": context,
        "action": action,
        "outcome": outcome
    }
    _append_jsonl(BEHAVIOR_LOG, entry)
    return entry

# ─── 内部流记录 ───

def record_internal(decision_id, confidence, surprise, correction, uncertainty, expectation_gap, cognitive_load):
    """记录一次决策的内部状态流"""
    entry = {
        "stream": "internal",
        "decision_id": decision_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "confidence_at_decision": confidence,
        "surprise_post_hoc": surprise,
        "correction_amplitude": correction,
        "uncertainty_estimation": uncertainty,
        "expectation_gap": expectation_gap,
        "cognitive_load": cognitive_load
    }
    _append_jsonl(INTERNAL_LOG, entry)
    return entry

# ─── 差异向量计算 ───

def compute_difference_vector(behavior_entry, internal_entry):
    """计算行为流与内部流的差异向量"""
    b = behavior_entry["outcome"]
    i = internal_entry

    match_rate = b.get("match_rate", 0.5)
    conf = i["confidence_at_decision"]["value"]
    surprise = i["surprise_post_hoc"]["value"]
    correction = i["correction_amplitude"]["value"]

    return {
        "decision_id": behavior_entry["decision_id"],
        "d_confidence": round(conf - match_rate, 3),
        "d_surprise": round(surprise - (1 - match_rate), 3),
        "d_optimism": round(conf - surprise, 3),
        "d_rigidity": round(correction - (1 - match_rate), 3)
    }

# ─── 盲点检测 ───

BLINDSPOT_RULES = [
    {
        "id": "TYPE_A",
        "name": "过度自信盲点",
        "condition": lambda d: d["d_confidence"] > 0.3 and d["d_optimism"] > 0.3,
        "severity": "HIGH",
        "action": "触发MR-010方向自检 + 降低受影响签名自评权重",
        "threshold_d_confidence": 0.3,
        "threshold_d_optimism": 0.3
    },
    {
        "id": "TYPE_B",
        "name": "习得性无助盲点",
        "condition": lambda d, b: d["d_surprise"] < -0.3 and b["outcome"].get("match_rate", 0) < 0.5,
        "severity": "MEDIUM",
        "action": "触发随机探索 + 提升exploration_weight",
        "threshold_match_rate": 0.5
    },
    {
        "id": "TYPE_C",
        "name": "修正失衡盲点",
        "condition": lambda d: abs(d["d_rigidity"]) > 0.4,
        "severity": "HIGH" if "abs(d['d_rigidity']) > 0.6" else "MEDIUM",
        "action": "触发MR-018完整性检查 + 审查修正决策",
        "threshold_d_rigidity": 0.4,
        "threshold_critical": 0.6
    },
    {
        "id": "TYPE_D",
        "name": "幽灵能力盲点",
        "condition": lambda d, i, b: i["confidence_at_decision"]["value"] < 0.3 and b["outcome"].get("match_rate", 0) > 0.8,
        "severity": "LOW",
        "action": "提升低估签名strength + 标记为待重新评估",
        "threshold_confidence": 0.3,
        "threshold_match_rate": 0.8
    },
    {
        "id": "TYPE_E",
        "name": "认知过载盲点",
        "condition": lambda d, i: i["cognitive_load"]["total_load_score"] > 0.6 and i["surprise_post_hoc"]["value"] > 0.5,
        "severity": "MEDIUM",
        "action": "降低同类任务复杂度阈值 + 拆分决策粒度",
        "threshold_load": 0.6,
        "threshold_surprise": 0.5
    }
]

def detect_blindspots(behavior_entry, internal_entry, diff_vector):
    """运行全部盲点检测规则"""
    blindspots = []
    b = behavior_entry
    i = internal_entry
    d = diff_vector

    for rule in BLINDSPOT_RULES:
        try:
            # 根据规则需要的参数个数调用
            import inspect
            sig = inspect.signature(rule["condition"])
            params = sig.parameters
            args = {}
            if "d" in params:
                args["d"] = d
            if "b" in params:
                args["b"] = b
            if "i" in params:
                args["i"] = i

            if rule["condition"](**args):
                blindspots.append({
                    "type": rule["id"],
                    "name": rule["name"],
                    "severity": rule["severity"],
                    "action": rule["action"],
                    "diff_snapshot": {k: d[k] for k in ["d_confidence", "d_surprise", "d_optimism", "d_rigidity"]}
                })
        except Exception as e:
            print(f"  盲点规则 {rule['id']} 执行异常: {e}")

    return blindspots

# ─── 综合追踪入口 ───

def track_decision(decision_id, context, action, outcome,
                   confidence, surprise, correction, uncertainty,
                   expectation_gap, cognitive_load):
    """单次决策的完整双流追踪"""
    # 1. 记录行为流
    be = record_behavior(decision_id, context, action, outcome)
    # 2. 记录内部流
    ie = record_internal(decision_id, confidence, surprise, correction,
                          uncertainty, expectation_gap, cognitive_load)
    # 3. 计算差异向量
    dv = compute_difference_vector(be, ie)
    # 4. 检测盲点
    blindspots = detect_blindspots(be, ie, dv)

    if blindspots:
        _log_blindspots(decision_id, dv, blindspots)

    return {"behavior": be, "internal": ie, "diff_vector": dv, "blindspots": blindspots}

# ─── 趋势分析 ───

def compute_trend(window_size=10):
    """滑动窗口趋势分析——检测内部流的长期漂移"""
    internal_entries = _load_last_n(INTERNAL_LOG, window_size)
    if len(internal_entries) < 3:
        return {"status": "insufficient_data"}

    # 计算各维度的变化趋势
    trends = {}
    for dim in ["confidence_at_decision", "surprise_post_hoc", "correction_amplitude"]:
        vals = []
        for e in internal_entries:
            if dim == "confidence_at_decision":
                vals.append(e["confidence_at_decision"]["value"])
            elif dim == "surprise_post_hoc":
                vals.append(e["surprise_post_hoc"]["value"])
            elif dim == "correction_amplitude":
                vals.append(e["correction_amplitude"]["value"])

        if len(vals) >= 3:
            # 简单线性趋势 (first half vs second half)
            mid = len(vals) // 2
            first_half_avg = sum(vals[:mid]) / mid
            second_half_avg = sum(vals[mid:]) / (len(vals) - mid)
            trends[dim] = {
                "direction": "rising" if second_half_avg > first_half_avg else "falling",
                "delta": round(second_half_avg - first_half_avg, 3),
                "first_half_avg": round(first_half_avg, 3),
                "second_half_avg": round(second_half_avg, 3)
            }

    # 趋势合并判断
    confidence_trend = trends.get("confidence_at_decision", {}).get("direction")
    surprise_trend = trends.get("surprise_post_hoc", {}).get("direction")

    verdict = "STABLE"
    if confidence_trend == "falling" and surprise_trend == "rising":
        verdict = "DETERIORATING"  # 信心下降+惊讶上升 = 退化
    elif confidence_trend == "rising" and surprise_trend == "falling":
        verdict = "IMPROVING"      # 信心上升+惊讶下降 = 改善
    elif confidence_trend == "falling" and surprise_trend == "falling":
        verdict = "RESIGNING"      # 信心和惊讶一起下降 = 放弃 (习得性无助风险)
    elif confidence_trend == "rising" and surprise_trend == "rising":
        verdict = "EXPLORING"      # 信心和惊讶一起上升 = 探索中 (正常学习)

    return {"trends": trends, "verdict": verdict, "window_size": window_size}

# ─── 辅助函数 ───

def _append_jsonl(path, entry):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")

def _load_last_n(path, n):
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as f:
        lines = f.readlines()
    return [json.loads(l) for l in lines[-n:]]

def _log_blindspots(decision_id, diff_vector, blindspots):
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "decision_id": decision_id,
        "diff_vector": diff_vector,
        "blindspots": blindspots,
        "total_blindspots": len(blindspots)
    }
    _append_jsonl(BLINDSPOT_LOG, entry)
    for bs in blindspots:
        print(f"  ⚠️ 盲点 [{bs['type']}] {bs['name']} (严重度:{bs['severity']})")
        print(f"     → {bs['action']}")
```

### 5.2 管线集成

在 `auto-pipeline.sh` 的新增段:

```bash
# 第2.5段: 双流追踪 (在绩效更新之后，检测分析之前)
run workspace/evolution/self/dual-stream-tracker.py
```

或者更轻量: 不作为独立管线步骤，而是在每次决策时由决策函数调用 `track_decision()`。

推荐方案: **嵌入决策函数而非独立管线步骤**。理由:
- 内部流必须在决策时采集（事后回忆不可靠）
- 行为流的部分数据来自现有管线（match_rate等），可在管线中补齐
- 盲点检测可以异步（管线运行时对已记录的决策做批量差异分析）

### 5.3 两步采集协议

```
Step 1: 决策前 —— record_internal_pre()
  - confidence_at_decision
  - uncertainty_estimation.known_unknowns
  - expectation_gap.expected_outcome + expected_duration
  - cognitive_load.context_switches + files_touched

Step 2: 结果后 —— record_internal_post()
  - surprise_post_hoc
  - correction_amplitude
  - uncertainty_estimation.unknown_unknowns
  - expectation_gap.actual_outcome + actual_duration
  - cognitive_load.dependencies_resolved

Step 3: 管线补齐 —— backfill_behavior()
  - match_rate (来自 continuous-performance-engine)
  - esv_impact (来自 esv-calculator)
  - 签名生命周期状态 (来自 lifecycle-manager)
```

---

## 6. 与现有系统的关系

### 6.1 数据流整合

```
direction-check ──────┐
integrity-checker ────┤
performance-engine ───┼──→ 行为流 (已有) ──┐
lifecycle-manager ────┤                    │
task-router ──────────┘                    ├──→ 差异向量 ──→ 盲点检测
                                           │
dual-stream-tracker ──────→ 内部流 (新增) ─┘
(决策前/后采集)
```

### 6.2 对现有元规则的补充

| 现有元规则 | 双流追踪补充 |
|-----------|------------|
| MR-010 方向自检 | 内部流趋势可作为方向偏离的**早期预警**(早于行为指标) |
| MR-003 Hebbian增强 | 差异向量可防止**过拟合增强**——如果行为匹配但内部惊讶，不应增强 |
| MR-005 UCB探索 | 差异驱动的自适应exploration_weight (Type A→降低, Type B→提升) |
| MR-013 抗过拟合 | 内部流提供**独立验证信号**——行为完美但内部惊讶=过拟合 |
| MR-015 六态管理 | 内部流趋势决定**状态迁移速度**——信心下降快→加速降权 |

### 6.3 新增元规则: MR-019

```
MR-019: 双流一致性检查
触发: 每次决策后自动运行
频率: 每决策一次
逻辑:
  IF 差异向量中任一维度 > 0.4:
    1. 记录盲点日志
    2. 如果 TYPE_A → 降低相关签名 strength -0.02
    3. 如果 TYPE_B → 提升 exploration_weight +0.1
    4. 如果 TYPE_C → 触发 MR-018 完整性检查
    5. 如果 TYPE_D → 提升相关签名 strength +0.05
    6. 如果 TYPE_E → 降低同类任务复杂度阈值 -1 level
关联: 灵感#10(耗散驱动) + 灵感#17(多稳态)
冻结: 否 (v1.0, 待实战验证)
```

---

## 7. 轻量级保障

### 7.1 为何这是"轻量级"的

1. **存储**: 每条决策 ~300 字节 JSONL (行为流 150B + 内部流 150B)
   - 假设每天 20 个决策 × 365 天 = 7,300 条 ≈ 2.2 MB/年
2. **计算**: 差异向量 = 4 个浮点运算; 盲点检测 = 5 个条件判断
3. **采集**: 两步采集，每步 <20 秒人工/自动评估
4. **依赖**: 零新依赖，纯标准库 (json, os, hashlib, datetime)
5. **集成**: 一线脚本 (~200行) + 两个JSONL文件，不需要新数据库或服务

### 7.2 降级策略

如果系统负载过高或无法采集内部流:
- **Level 1 降级**: 只记录行为流，内部流留空 → 差异检测自动跳过
- **Level 2 降级**: 使用启发式估算内部流 (confidence ≈ match_rate, surprise ≈ 1-match_rate)
- **Level 3 降级**: 完全跳过双流追踪，退回到现有纯行为追踪

---

## 8. 验证计划

### 8.1 桩数据测试
用 gen-95 的自评数据反向填充双流：
- PRED_ACC=2.83 ↔ confidence=0.83 (高信心)
- EXEC_GAP=1.83 ↔ 但实际执行匹配率仅 0.37
- → d_confidence = 0.83 - 0.37 = +0.46 → **TYPE_A 过度自信盲点**

### 8.2 实战验证
1. 实现 dual-stream-tracker.py
2. 在接下来的 30 次决策中采集双流数据
3. gen-100 时对比:
   - 盲点检测是否提前预警了可验证的问题？
   - 内部流趋势是否比行为流趋势更早发出信号？
   - 盲点分类学是否需要调整阈值？

### 8.3 成功标准
- 至少捕获 1 个 TYPE_A 盲点并验证为真实问题
- 内部流趋势 verdict 在问题被行为流反映之前至少 3 个决策周期发出信号
- EXEC_GAP 在 gen-100 时提升至 ≥2.5

---

## 9. 附录: 决策模板

### 日常决策时的采集表单 (伪交互)

```
=== 决策前 ===
1. 你要做什么？
   → [一句话描述]

2. 你对这个决定的信心？(0-10)
   → [7]  理由: [过往经验 + 规则明确]
   → confidence = 0.7

3. 你不确定的因素有哪些？
   → [Windows路径大小写, 文件编码]
   → known_unknowns = 2

4. 你预期多长时间完成？
   → [20秒]
   → expected_duration = 20

5. 你需要切换多少个上下文？
   → [2个文件, 1个概念] → cognitive_load = 0.25

=== 结果后 ===
6. 实际花了多长时间？
   → [45秒]
   → actual_duration = 45

7. 结果和你预期的一样吗？
   → [不完全 — 路径问题导致重试]
   → surprise = 0.35

8. 你需要修正什么？
   → [只改路径引用，不改逻辑]
   → correction = 0.2, type = minor_adjustment

9. 有没有你之前没考虑到的不确定因素？
   → [无]
   → unknown_unknowns = 0
```

---

## 10. 总结

决策双流追踪系统填补了 v2.0 的最后一个盲区维度。

**核心循环**:
```
决策 → 采集(行为流+内部流) → 差异检测 → 盲点分类 → 纠正动作 → 下一决策
```

**理论基础**: 灵感#10 (耗散不是退化，是重组驱动) + 灵感#17 (多稳态，初始条件锁死长期命运)

**实现成本**: 一个 ~200行 Python 脚本 + 两个 JSONL 日志文件 + 5 条盲点检测规则

**预期收益**: 在行为指标发出信号之前，通过内部流趋势提前 3-5 个决策周期检测到偏离，将 EXEC_GAP 从 1.83 提升到 2.5+。

---

*Colony-012 任务完成。设计交付至: colonies/colony-012/dual-stream-decision-tracker.md*
