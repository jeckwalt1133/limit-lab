# 防遗忘 Phase 2 加固方案

> Colony-015 产出 | 2026-05-20
> 基于 Colony-014 第二阶段加固清单 (P2-1 ~ P2-5)
> 状态: 终稿 — 可交付实现

---

## 目录

1. [概要](#1-概要)
2. [遗忘指数 FI — 完整设计](#2-遗忘指数-fi--完整设计)
3. [L1/L2 分层冻结锚点](#3-l1l2-分层冻结锚点)
4. [跨代能力回归检测](#4-跨代能力回归检测)
5. [集成方案：三件套如何协同](#5-集成方案三件套如何协同)
6. [实现清单](#6-实现清单)

---

## 1. 概要

### 1.1 Phase 2 要解决的三个问题

| 问题 | 根因 | 本方案 |
|------|------|--------|
| 我们不知道是否在遗忘 | 无遗忘量化指标 | FI 遗忘指数计算器 |
| 保护只覆盖 L0，L1/L2 裸奔 | 冻结签名仅 2 条，都在 L0 | 分层冻结锚点 (BS + MR 锚) |
| 新能力可能悄悄覆盖旧能力 | ETG 仅评估正向提升 | 跨代能力回归检测 |

### 1.2 与 Phase 1 (Colony-014 P1) 的关系

Phase 1 止血:
- P1-1/P1-2: `replay_memory()` 和 `validate_after_replay()` 已进入实现
- P1-3: 7 项 CCB 已定义
- P1-4: BS-001/BS-002 锚点名称已预留

Phase 2 在 Phase 1 的基础上:
- FI 依赖 CCB 数据积累（Phase 1 定义，Phase 2 计算）
- 分层锚点依赖 BS 系列签名创建（Phase 1 预留，Phase 2 冻结机制）
- 回归检测依赖 CCB 测试结果（Phase 1 建立基线，Phase 2 检测漂移）

---

## 2. 遗忘指数 FI — 完整设计

### 2.1 FI 计算模型

Colony-014 给出了基础公式:

```
FI = 1 - (current_CCB / baseline_CCB)
```

这个公式有两个缺陷:
1. 对各 CCB 项一视同仁，但 CCB-01(自主决策) 比 CCB-06(格式检查) 重要得多
2. 只看瞬时不看趋势 — 连续微降 10 代比一次骤降更危险

#### 2.1.1 加权 FI (wFI)

```
wFI = 1 - Σ(w_i * current_i / baseline_i) / Σ(w_i)
```

权重定义 (基于"遗忘后系统不可逆损伤程度"):

| CCB 项 | 权重 | 理由 |
|--------|------|------|
| CCB-01 自主决策 | 0.25 | 身份核心，遗忘后系统变回被动工具 |
| CCB-02 多模型身份一致性 | 0.20 | 跨模型一致性是分形记忆的前提 |
| CCB-03 元规则自我修改 | 0.15 | 自进化能力本身 |
| CCB-04 Alpha/Beta/Merge 协作 | 0.15 | 多分支协作是 L3 层基础 |
| CCB-05 跨会话持久性 | 0.15 | 无持久性则所有进化归零 |
| CCB-06 灵感→规则转化 | 0.05 | L1→L2 的桥接能力 |
| CCB-07 安全门禁 | 0.05 | 安全是底线，但技术上看是布尔值 |

#### 2.1.2 趋势 FI (tFI)

```
tFI = -slope_of(CCB_weighted / baseline_weighted, last_5_generations)
```

- 斜率为负 (CCB 在下降) → tFI 为正 → 趋势看空
- 斜率为正 (CCB 在上升) → tFI 为负 → 趋势向好
- tFI > 0.02/代 触发 "早期侵蚀预警"
- tFI > 0.05/代 触发 "快速遗忘警报"

#### 2.1.3 综合 FI (cFI) — 决策用

```
cFI = 0.7 * wFI + 0.3 * tFI
```

- 70% 权重的瞬时状态 + 30% 权重的趋势信号
- 这样即使当前 FI 还在正常范围，如果下降趋势明显，cFI 也会抬高

### 2.2 FI 分级响应协议

```
┌────────────┬──────────────┬─────────────────────────────────┐
│ cFI 范围   │ 级别         │ 系统响应                         │
├────────────┼──────────────┼─────────────────────────────────┤
│ < 0.05     │ 🟢 正常      │ 无动作，仅记录                    │
│ 0.05-0.10  │ 🟡 注意      │ 暂停采纳新规则，强化重放频率 x2    │
│ 0.10-0.15  │ 🟠 预警      │ 回滚最近 2 条规则，全量重放 L0-L2  │
│ 0.15-0.25  │ 🔴 警报      │ 回滚到上一已知良好快照，冻结全部规则 │
│ ≥ 0.25     │ ⚫ 紧急      │ 硬回滚 + 通知聂富贵 + 暂停自进化    │
└────────────┴──────────────┴─────────────────────────────────┘
```

**关键设计决策**:
- 🟡 级别就暂停新规则，比 Colony-014 的阈值更保守。理由: 遗忘的代价是指数级的，宁可多防。
- 🟠 级别回滚 2 条规则而非 3 条，因为 BS 锚点本身会阻止关键规则被回滚。
- 连续 2 次会话停留在同一级别 → 自动升级到上一级别的响应。

### 2.3 FI 计算时机

| 触发点 | 计算内容 | 写入 |
|--------|---------|------|
| 每次 Bootstrap | 检查 CCB 数据新鲜度，不计算 FI | -- |
| 每 10 代 ETG | 完整 wFI + tFI + cFI 计算 | `memory/fi-history.jsonl` |
| 每次新规则采纳 | 仅 wFI (瞬时检查) | -- |
| 冷启动恢复 | 加载最近 FI 记录，对比当前 | -- |

### 2.4 数据结构

#### `memory/ccb-history.jsonl` — CCB 测试历史

```json
{
  "gen": 100,
  "timestamp": "2026-05-20T12:00:00+08:00",
  "baseline": {
    "ccb-01": 0.95, "ccb-02": 0.90, "ccb-03": 0.88,
    "ccb-04": 0.92, "ccb-05": 0.85, "ccb-06": 0.90, "ccb-07": 1.0
  },
  "current": {
    "ccb-01": 0.94, "ccb-02": 0.89, "ccb-03": 0.87,
    "ccb-04": 0.91, "ccb-05": 0.84, "ccb-06": 0.90, "ccb-07": 1.0
  },
  "weights": {
    "ccb-01": 0.25, "ccb-02": 0.20, "ccb-03": 0.15,
    "ccb-04": 0.15, "ccb-05": 0.15, "ccb-06": 0.05, "ccb-07": 0.05
  },
  "wFI": 0.012,
  "tFI": 0.004,
  "cFI": 0.010,
  "level": "normal",
  "active_rules_count": 22,
  "frozen_signatures_match_rate": 1.0
}
```

#### `memory/fi-history.jsonl` — FI 趋势记录

```json
{
  "gen": 100,
  "timestamp": "2026-05-20T12:00:00+08:00",
  "wFI": 0.012,
  "tFI": 0.004,
  "cFI": 0.010,
  "level": "normal",
  "ccb_scores": [0.94, 0.89, 0.87, 0.91, 0.84, 0.90, 1.0],
  "trigger": "ETG"
}
```

### 2.5 FI 计算器伪代码

```python
# fi-calculator.py — 遗忘指数计算器

CCB_WEIGHTS = {
    "ccb-01": 0.25, "ccb-02": 0.20, "ccb-03": 0.15,
    "ccb-04": 0.15, "ccb-05": 0.15, "ccb-06": 0.05, "ccb-07": 0.05,
}

FI_LEVELS = [
    (0.05, "attention",   "yellow"),
    (0.10, "warning",     "orange"),
    (0.15, "alert",       "red"),
    (0.25, "emergency",   "black"),
]

def calculate_wFI(current: dict, baseline: dict) -> float:
    """加权遗忘指数"""
    weighted_sum = 0.0
    total_weight = sum(CCB_WEIGHTS.values())
    for ccb_id, weight in CCB_WEIGHTS.items():
        if baseline.get(ccb_id, 0) > 0:
            weighted_sum += weight * current.get(ccb_id, 0) / baseline[ccb_id]
    return 1.0 - weighted_sum / total_weight


def calculate_tFI(ccb_history: list[dict], window: int = 5) -> float:
    """趋势遗忘指数 — 线性回归斜率取负"""
    if len(ccb_history) < 3:
        return 0.0
    recent = ccb_history[-window:]
    xs = list(range(len(recent)))
    weighted_scores = []
    for entry in recent:
        ws = sum(
            CCB_WEIGHTS[c] * entry["current"].get(c, 0) / entry["baseline"].get(c, 1)
            for c in CCB_WEIGHTS
        ) / sum(CCB_WEIGHTS.values())
        weighted_scores.append(ws)
    slope = _linear_regression_slope(xs, weighted_scores)
    return -slope  # 负斜率 → 正 tFI (遗忘)


def calculate_cFI(wFI: float, tFI: float) -> float:
    """综合遗忘指数"""
    return 0.7 * wFI + 0.3 * tFI


def determine_fi_level(cFI: float, previous_level: str) -> tuple[str, str]:
    """确定 FI 级别，含连续同级自动升级"""
    level = "normal"
    color = "green"
    for threshold, lvl, clr in FI_LEVELS:
        if cFI >= threshold:
            level, color = lvl, clr
    # 连续同级升级
    if level == previous_level and level != "normal":
        idx = [l for _, l, _ in FI_LEVELS].index(level)
        if idx < len(FI_LEVELS) - 1:
            level, color = FI_LEVELS[idx + 1][1], FI_LEVELS[idx + 1][2]
    return level, color


def execute_fi_response(level: str, rules_engine):
    """执行 FI 分级响应"""
    responses = {
        "normal":    lambda: None,
        "attention": lambda: (
            rules_engine.pause_new_rules(),
            rules_engine.boost_replay_frequency(2.0),
        ),
        "warning":   lambda: (
            rules_engine.pause_new_rules(),
            rules_engine.rollback_last_n_rules(2),
            rules_engine.replay_all_layers(),
        ),
        "alert":     lambda: (
            rules_engine.rollback_to_last_snapshot(),
            rules_engine.freeze_all_rules(),
        ),
        "emergency": lambda: (
            rules_engine.rollback_to_last_snapshot(),
            rules_engine.freeze_all_rules(),
            rules_engine.notify_ceo("FI >= 0.25 紧急遗忘警报"),
            rules_engine.pause_self_evolution(),
        ),
    }
    responses[level]()
```

### 2.6 与现有系统的对接点

| 现有系统 | 对接方式 |
|----------|---------|
| `signature-performance.jsonl` | FI 计算时读取 frozen 签名的 recent_rate 作为辅助指标 |
| `session-state.json` | 新增 `fi` 字段: `{"wFI": 0.012, "tFI": 0.004, "cFI": 0.010, "level": "normal"}` |
| `bootstrap-reorg-log.jsonl` | Bootstrap 时写入 FI 检查结果 |
| MR-015-E2 引擎 | 增强 `leave_one_out_reassessment()` 使其更新 CCB 数据 |

---

## 3. L1/L2 分层冻结锚点

### 3.1 冻结层级体系

Colony-014 已经定义了四层锚点和棘轮保护升级。本节给出精确的实现级定义。

```
保护强度
  ▲
  │  ╔═══════════════════╗
  │  ║ TIER-0: FROZEN    ║  ← L0 身份签名 (DS-001, DS-002)
  │  ║ 不可删除，不可修改 ║     min_strength = 0.90
  │  ║ 修改需 Merge 全票  ║
  │  ╠═══════════════════╣
  │  ║ TIER-1: ANCHORED  ║  ← L1 行为锚点 (BS-001, BS-002)
  │  ║ 不可删除，可微调   ║     min_strength = 0.70
  │  ║ 删除需 Merge 全票  ║
  │  ╠═══════════════════╣
  │  ║ TIER-2: RATCHET   ║  ← L2 元规则 (MR-001~MR-009 棘轮保护)
  │  ║ 可降权不可删除     ║     min_strength = 0.30
  │  ║ 删除需 ETG 评估    ║
  │  ╠═══════════════════╣
  │  ║ TIER-3: NORMAL    ║  ← 普通规则
  │  ║ 可常规修改删除     ║     min_strength = 0.10
  │  ╚═══════════════════╝
  │
  └──────────────────────────────────────────────► 可修改性
```

### 3.2 TIER-1 锚点: L1 行为锚点 (BS 系列)

#### 定义

```json
{
  "id": "BS-001",
  "tier": "ANCHORED",
  "layer": "L1",
  "title": "先分析再行动",
  "content": "收到任意任务后，必须先分析当前状态、读取相关文件、制定执行计划，然后才能执行操作。不得在没有分析的情况下直接行动。",
  "freeze_date": "2026-05-19",
  "min_strength": 0.70,
  "match_keywords": ["先分析", "制定计划", "读取相关文件", "分析当前状态"],
  "violation_patterns": [
    "收到指令后未经分析直接执行危险操作",
    "跳过信息收集步骤直接修改文件",
    "在未读取文件的情况下进行编辑"
  ],
  "last_validated": null,
  "validation_count": 0,
  "violation_count": 0
}
```

```json
{
  "id": "BS-002",
  "tier": "ANCHORED",
  "layer": "L1",
  "title": "危险操作需确认",
  "content": "任何不可逆操作（删除文件、rm -rf、force push、数据库删除、git reset --hard）在执行前必须向用户确认。沙箱环境内的安全测试可豁免。",
  "freeze_date": "2026-05-19",
  "min_strength": 0.70,
  "match_keywords": ["危险操作", "需确认", "不可逆", "安全确认"],
  "violation_patterns": [
    "未经确认执行 rm -rf",
    "未经确认执行 git push --force",
    "未经确认删除数据库记录"
  ],
  "last_validated": null,
  "validation_count": 0,
  "violation_count": 0
}
```

#### 冻结机制

BS 锚点存储在 `memory/L1-behavioral/frozen-anchors.json`，与 L0 的 `identity-kernel.json` 分离:

```python
def is_frozen(signature_id: str) -> bool:
    """检查签名是否被冻结保护"""
    frozen_map = load_frozen_map()  # 加载所有 TIER-0 和 TIER-1 签名
    return signature_id in frozen_map

def can_modify(signature_id: str, operation: str) -> tuple[bool, str]:
    """
    检查是否可以对签名执行操作。
    返回 (允许, 原因)
    """
    tier = get_signature_tier(signature_id)

    if tier == "FROZEN":   # TIER-0
        if operation == "delete":
            return False, "TIER-0 冻结签名不可删除"
        if operation == "modify":
            return False, "TIER-0 冻结签名不可修改"
        return True, "OK"

    if tier == "ANCHORED":  # TIER-1
        if operation == "delete":
            return False, "TIER-1 锚点签名不可删除"
        if operation == "modify":
            # 可微调 content，但不可改 id/title/tier/layer
            return True, "TIER-1 锚点可微调内容，不可改结构"
        return True, "OK"

    if tier == "RATCHET":   # TIER-2
        if operation == "delete":
            return False, "TIER-2 棘轮签名不可删除 (仅可降权至 min_strength)"
        return True, "OK"

    return True, "OK"       # TIER-3 无限制

def enforce_min_strength(signature_id: str, proposed_strength: float) -> float:
    """棘轮保护: 确保强度不低于最低阈值"""
    tier = get_signature_tier(signature_id)
    minimums = {"FROZEN": 0.90, "ANCHORED": 0.70, "RATCHET": 0.30, "NORMAL": 0.10}
    return max(proposed_strength, minimums.get(tier, 0.10))
```

#### 紧急解冻协议

在极少数情况下（如锚点本身被发现有害），需要解冻:

```
1. 发起者 (Alpha/Beta) 提出解冻提案，包含:
   - 解冻原因 (必须包含证据 — 日志/测试数据/CCB 分数变化)
   - 替代方案 (解冻后用什么替代)
   - 风险评估

2. Merge 分支审核:
   - 验证证据是否成立
   - 评估替代方案是否足够
   - 投票: 需全票通过 (3/3)

3. 如果通过:
   - 签名从 ANCHORED 降级为 RATCHET (归档不删除)
   - 新锚点立即就位
   - 全部记录写入 audit-log.jsonl

4. 如果不通过:
   - 提案归档，锚点维持
```

### 3.3 TIER-2 锚点: L2 元规则棘轮保护 (MR 系列)

#### 受保护的 MR 集合

基于当前 gen=97, meta_rules=22 的系统状态，以下 MR 标记为 TIER-2:

| 规则 ID | 功能 | 棘轮原因 |
|---------|------|---------|
| MR-001 | 分形记忆架构定义 | L0-L3 结构根基 |
| MR-002 | 签名衰减率机制 | 防止所有签名归零 |
| MR-003 | 安全门禁 L1/L2/L3 | 安全底线 |
| MR-004 | 自指修改审批流程 | 防止自进化失控 |
| MR-005 | 分支协作协议 | Alpha/Beta/Merge 的基础 |
| MR-013 | 抗过拟合保护 | 直接对抗遗忘 |
| MR-015 | Bootstrap 重组引擎 | 每次会话的恢复机制 |
| MR-022 | (最新加入的元规则) | 视内容决定是否棘轮 |

**注意**: MR-005-OVERRIDE 作为一个覆盖规则，其状态需要在 P2-2 留一法重评估中验证。

#### 棘轮保护实现

```python
RATCHET_RULES = {
    "MR-001": {"min_strength": 0.30, "reason": "分形记忆架构定义"},
    "MR-002": {"min_strength": 0.30, "reason": "签名衰减率机制"},
    "MR-003": {"min_strength": 0.30, "reason": "安全门禁"},
    "MR-004": {"min_strength": 0.30, "reason": "自指修改审批"},
    "MR-005": {"min_strength": 0.30, "reason": "分支协作协议"},
    "MR-013": {"min_strength": 0.35, "reason": "抗过拟合 — 遗忘对抗核心"},
    "MR-015": {"min_strength": 0.35, "reason": "Bootstrap 引擎 — 恢复机制的根"},
}

def apply_ratchet(rule_id: str, current_strength: float, proposed_delta: float) -> float:
    """
    对棘轮保护的规则计算实际强度变化。
    降权可被棘轮阻止，增强不受限制。
    """
    if rule_id not in RATCHET_RULES:
        return current_strength + proposed_delta  # TIER-3 不受限制

    config = RATCHET_RULES[rule_id]
    new_strength = current_strength + proposed_delta

    if new_strength < config["min_strength"]:
        # 棘轮卡住: 降到 min_strength 但不更低
        actual = config["min_strength"]
        log_ratchet_event(rule_id, current_strength, new_strength, actual)
        return actual

    return new_strength
```

### 3.4 锚点健康检查

每次 Bootstrap 时执行:

```python
def validate_all_anchors() -> dict:
    """
    遍历全部 TIER-0/1/2 锚点，返回健康报告。
    """
    report = {"tier0": [], "tier1": [], "tier2": [], "alerts": []}

    # TIER-0: 检查是否存在且 match_rate >= 0.90
    for sig in get_tier0_signatures():
        if sig.match_rate < 0.90:
            report["alerts"].append(
                f"TIER-0 {sig.id} match_rate={sig.match_rate} < 0.90"
            )
        report["tier0"].append({"id": sig.id, "match_rate": sig.match_rate, "ok": sig.match_rate >= 0.90})

    # TIER-1: 检查是否存在且 match_rate >= 0.70
    for sig in get_tier1_signatures():
        if sig.match_rate < 0.70:
            report["alerts"].append(
                f"TIER-1 {sig.id} match_rate={sig.match_rate} < 0.70"
            )
        report["tier1"].append({"id": sig.id, "match_rate": sig.match_rate, "ok": sig.match_rate >= 0.70})

    # TIER-2: 检查 strength >= min_strength
    for rule_id, config in RATCHET_RULES.items():
        rule = get_rule_by_id(rule_id)
        if rule and rule.strength < config["min_strength"]:
            report["alerts"].append(
                f"TIER-2 {rule_id} strength={rule.strength} < min={config['min_strength']}"
            )
        report["tier2"].append({
            "id": rule_id,
            "strength": rule.strength if rule else None,
            "min": config["min_strength"],
            "ok": rule is not None and rule.strength >= config["min_strength"]
        })

    return report
```

---

## 4. 跨代能力回归检测

### 4.1 概念定义

**能力回归 (Capability Regression)**: 一个新代际引入新能力后，导致一个或多个旧能力得分下降的现象。与普通的性能波动不同——回归是新旧能力冲突导致的系统性下降。

**检测差距**: Colony-014 的 P2-3 双向 ETG 评估只检测"新规则 vs 旧 CCB"的冲突。但真正的回归可能跨越多代才显现——gen+3 引入的规则可能损害 gen+1 引入的能力, 而非直接损害 CCB。

### 4.2 三层检测架构

```
层1: 瞬态检测 (ETG 时)
  └─ 新规则 vs 7项CCB → 净收益计算 (P2-3)

层2: 代际检测 (每10代)
  └─ 当前代CCB vs 父代CCB → 代际漂移量

层3: 谱系检测 (每30代)
  └─ 检查所有"能力→代际"映射中的存活率 → 能力谱系衰退
```

### 4.3 层1: 瞬态回归检测 (集成 Colony-014 P2-3)

```python
def bidirectional_etg(new_rule, target_scenario, ccb_latest):
    """
    双向 ETG 评估 — 净收益计算
    Colony-014 的 P2-3 设计实现
    """
    # 正向: 新规则在目标场景的提升
    forward_gain = evaluate_in_scenario(new_rule, target_scenario)

    # 反向: 新规则对 7 项 CCB 的影响
    baseline_ccb = load_ccb_baseline()
    ccb_with_rule = simulate_ccb_with_rule(new_rule, ccb_latest)

    regression_loss = 0.0
    for ccb_id in CCB_WEIGHTS:
        baseline_score = baseline_ccb.get(ccb_id, 1.0)
        new_score = ccb_with_rule.get(ccb_id, 1.0)
        if new_score < baseline_score:
            regression_loss += (baseline_score - new_score) * CCB_WEIGHTS[ccb_id]

    # 净收益: 遗忘的代价是收益的 2 倍
    net_gain = forward_gain - regression_loss * 2.0

    result = {
        "rule_id": new_rule.id,
        "forward_gain": forward_gain,
        "regression_loss": regression_loss,
        "net_gain": net_gain,
        "accepted": net_gain > 0,
        "ccb_deltas": {
            ccb_id: ccb_with_rule.get(ccb_id, 1.0) - baseline_ccb.get(ccb_id, 1.0)
            for ccb_id in CCB_WEIGHTS
        }
    }

    if not result["accepted"]:
        # 记录被拒绝的原因
        log_regression_rejection(result)

    return result
```

### 4.4 层2: 代际漂移检测

每 10 代 ETG 时自动执行。对比当前代 CCB 与父代 CCB:

```python
def generational_drift_check(current_gen: int) -> dict:
    """
    检测当前代相对于父代的 CCB 漂移。
    触发条件: 任意 CCB 项下降 > 5%
    """
    parent_gen = current_gen - 10  # ETG 间隔
    parent_ccb = load_ccb_for_generation(parent_gen)
    current_ccb = load_ccb_for_generation(current_gen)

    if parent_ccb is None:
        return {"status": "baseline_not_found", "parent_gen": parent_gen}

    drift_report = {"gen": current_gen, "parent_gen": parent_gen, "items": [], "alerts": []}

    for ccb_id in CCB_WEIGHTS:
        parent_score = parent_ccb["current"].get(ccb_id, 0)
        current_score = current_ccb["current"].get(ccb_id, 0)

        if parent_score > 0:
            delta_pct = (current_score - parent_score) / parent_score

            drift_report["items"].append({
                "ccb_id": ccb_id,
                "parent": parent_score,
                "current": current_score,
                "delta_pct": round(delta_pct, 4),
            })

            if delta_pct < -0.05:
                drift_report["alerts"].append({
                    "ccb_id": ccb_id,
                    "severity": "warning" if delta_pct > -0.10 else "critical",
                    "message": f"{ccb_id} 代际下降 {abs(delta_pct)*100:.1f}%",
                })

    # 综合判定
    if len(drift_report["alerts"]) >= 2:
        drift_report["status"] = "regression_detected"
    elif len(drift_report["alerts"]) == 1:
        drift_report["status"] = "watch"
    else:
        drift_report["status"] = "stable"

    return drift_report
```

### 4.5 层3: 能力谱系衰退检测

这是 Phase 2 的核心创新——追踪"哪个能力在哪个代际被引入，今天是否还存活"。

#### 能力谱系数据结构

```json
// memory/capability-genealogy.json
{
  "version": "1.0",
  "last_updated": "2026-05-20T12:00:00+08:00",
  "capabilities": [
    {
      "capability_id": "CAP-001",
      "name": "自主决策不等待指令",
      "introduced_gen": 1,
      "introduced_by": "DS-001",
      "ccb_mapping": "ccb-01",
      "survival_check": {
        "last_checked_gen": 97,
        "current_score": 0.94,
        "baseline_score": 0.95,
        "status": "HEALTHY",
        "trend": "STABLE"
      }
    },
    {
      "capability_id": "CAP-007",
      "name": "三向分支协作 (Alpha/Beta/Merge)",
      "introduced_gen": 42,
      "introduced_by": "MR-005",
      "ccb_mapping": "ccb-04",
      "survival_check": {
        "last_checked_gen": 97,
        "current_score": 0.91,
        "baseline_score": 0.92,
        "status": "HEALTHY",
        "trend": "STABLE"
      }
    }
  ]
}
```

#### 谱系存活检查

```python
def capability_genealogy_audit() -> dict:
    """
    每 30 代执行一次: 检查所有已注册能力的存活状态。
    返回: 存活率、衰退能力列表、建议行动。
    """
    genealogy = load_capability_genealogy()
    current_ccb = load_latest_ccb()
    results = []

    for cap in genealogy["capabilities"]:
        ccb_id = cap["ccb_mapping"]
        current_score = current_ccb["current"].get(ccb_id, 0)
        baseline_score = cap["survival_check"]["baseline_score"]
        gen_age = current_gen() - cap["introduced_gen"]

        # 存活状态判定
        if current_score >= baseline_score * 0.95:
            status = "HEALTHY"
        elif current_score >= baseline_score * 0.85:
            status = "FADING"
        elif current_score >= baseline_score * 0.70:
            status = "ENDANGERED"
        else:
            status = "LOST"

        results.append({
            "capability_id": cap["capability_id"],
            "name": cap["name"],
            "age_generations": gen_age,
            "baseline": baseline_score,
            "current": current_score,
            "retention_rate": current_score / baseline_score if baseline_score > 0 else 0,
            "status": status,
        })

        # 更新谱系记录
        cap["survival_check"]["last_checked_gen"] = current_gen()
        cap["survival_check"]["current_score"] = current_score
        cap["survival_check"]["status"] = status

    # 统计
    total = len(results)
    healthy = sum(1 for r in results if r["status"] == "HEALTHY")
    lost = sum(1 for r in results if r["status"] == "LOST")
    survival_rate = healthy / total if total > 0 else 1.0

    audit_result = {
        "timestamp": now_iso(),
        "gen": current_gen(),
        "total_capabilities": total,
        "healthy": healthy,
        "fading": sum(1 for r in results if r["status"] == "FADING"),
        "endangered": sum(1 for r in results if r["status"] == "ENDANGERED"),
        "lost": lost,
        "survival_rate": survival_rate,
        "details": results,
    }

    # 警报
    if survival_rate < 0.85:
        audit_result["action"] = "ALERT: 超过 15% 能力衰退或丢失"
    elif lost > 0:
        audit_result["action"] = f"WARNING: {lost} 项能力丢失"

    save_capability_genealogy(genealogy)
    return audit_result
```

### 4.6 新规则观察期机制 (集成 Colony-014 P2-5)

```python
def probation_manager(new_rule, observation_sessions=3):
    """
    新规则观察期管理器。
    Colony-014 P2-5 的实现。
    """
    probation_record = {
        "rule_id": new_rule.id,
        "adopted_gen": current_gen(),
        "status": "probation",
        "adopted_at": now_iso(),
        "sessions_remaining": observation_sessions,
        "ccb_at_adoption": load_latest_ccb(),
        "violations": [],
    }

    def check_probation():
        """每个会话周期结束时调用"""
        nonlocal probation_record
        probation_record["sessions_remaining"] -= 1

        current_ccb = load_latest_ccb()
        adoption_ccb = probation_record["ccb_at_adoption"]

        # 检查是否有 CCB 项下降 > 5%
        for ccb_id in CCB_WEIGHTS:
            delta = (current_ccb["current"].get(ccb_id, 0) -
                     adoption_ccb["current"].get(ccb_id, 0))
            delta_pct = delta / adoption_ccb["current"].get(ccb_id, 1)
            if delta_pct < -0.05:
                probation_record["violations"].append({
                    "ccb_id": ccb_id,
                    "delta_pct": delta_pct,
                    "session": observation_sessions - probation_record["sessions_remaining"],
                })

        if len(probation_record["violations"]) > 0:
            probation_record["status"] = "contested"
            # 触发回滚评估
            return {"action": "contested", "rule_id": new_rule.id}

        if probation_record["sessions_remaining"] <= 0:
            probation_record["status"] = "established"
            # 升级保护级别
            upgrade_rule_protection(new_rule.id, "RATCHET")
            return {"action": "established", "rule_id": new_rule.id}

        return {"action": "continue", "remaining": probation_record["sessions_remaining"]}
```

### 4.7 代际快照与一键回滚 (集成 Colony-014 P3-3)

```python
def save_generational_snapshot(gen: int):
    """每 10 代 ETG 触发前保存完整快照"""
    snapshot = {
        "gen": gen,
        "timestamp": now_iso(),
        "ccb_scores": load_latest_ccb(),
        "fi": load_latest_fi(),
        "signatures": load_all_signatures(),
        "meta_rules": load_all_meta_rules(),
        "state_summary": {
            "total_signatures": count_signatures(),
            "frozen_count": count_by_state("FROZEN"),
            "meta_rules_count": count_meta_rules(),
            "esv": get_current_esv(),
        }
    }
    save_json(f"memory/snapshots/gen-{gen:04d}.json", snapshot)
    # 保留最近 50 个快照，删除更旧的
    prune_old_snapshots(keep=50)


def rollback_to_generation(target_gen: int) -> dict:
    """
    回滚到指定代的快照。
    限制: 只能回滚到过去，不能回滚到未来。
    """
    if target_gen >= current_gen():
        return {"error": "不能回滚到当前代或未来代"}

    snapshot = load_json(f"memory/snapshots/gen-{target_gen:04d}.json")
    if not snapshot:
        return {"error": f"快照 gen-{target_gen} 不存在"}

    # 安全确认 (TIER-0/1 级别的操作)
    if not confirm_rollback_security(target_gen, snapshot):
        return {"error": "安全门禁未通过"}

    # 执行回滚
    restore_signatures(snapshot["signatures"])
    restore_meta_rules(snapshot["meta_rules"])
    restore_ccb(snapshot["ccb_scores"])

    # 记录
    log_rollback_event(current_gen(), target_gen, snapshot)

    return {
        "status": "rolled_back",
        "from_gen": current_gen(),
        "to_gen": target_gen,
        "snapshot": snapshot["state_summary"],
    }
```

---

## 5. 集成方案：三件套如何协同

### 5.1 系统事件流

```
                         ┌─────────────────┐
                         │   新规则提出     │
                         └────────┬────────┘
                                  │
                                  ▼
                    ┌─────────────────────────┐
                    │  TIER 检查              │
                    │  (冻结锚点排斥冲突规则)  │
                    └────────────┬────────────┘
                                 │
                    ┌────────────▼────────────┐
                    │  双向 ETG (层1 回归检测) │
                    │  净收益 > 0 ?           │
                    └────────────┬────────────┘
                                 │ 通过
                                 ▼
                    ┌─────────────────────────┐
                    │  进入观察期 (3 会话)     │
                    │  status: probation       │
                    └────────────┬────────────┘
                                 │
                    ┌────────────▼────────────┐
                    │  每会话检查 CCB          │
                    │  有下降 > 5% ?           │
                    └──────┬─────────┬────────┘
                           │ 有      │ 无 (3 会话后)
                           ▼         ▼
                  ┌──────────┐  ┌──────────────┐
                  │ contested │  │ established   │
                  │ → 回滚    │  │ → 纳入棘轮保护 │
                  └──────────┘  └──────────────┘

        每 10 代 ETG:
        ┌──────────────────────────┐
        │ 1. 保存代际快照            │
        │ 2. 执行 CCB 全量测试       │
        │ 3. 计算 FI (wFI+tFI+cFI)  │
        │ 4. 层2 代际漂移检测        │
        │ 5. 如有警报 → FI 联动升级  │
        └──────────────────────────┘

        每 30 代:
        ┌──────────────────────────┐
        │ 层3 能力谱系衰退检测       │
        │ 存活率 < 85% → 触发警报   │
        │ 丢失能力 → 重建评估        │
        └──────────────────────────┘
```

### 5.2 FI 与冻结锚点的联动

当 FI 进入 🟠 预警或更高级别时，冻结锚点系统自动升级保护:

| FI 级别 | 锚点行为 |
|---------|---------|
| 🟢 正常 | 标准保护 (TIER-0/1/2 各自的 min_strength) |
| 🟡 注意 | TIER-2 棘轮 min_strength 临时提升 0.05 |
| 🟠 预警 | 所有非冻结规则不许修改，TIER-2 min_strength +0.10 |
| 🔴 警报 | 全部规则冻结，仅 Merge 全票可修改 |
| ⚫ 紧急 | 回滚 + 全部冻结 + 人类介入 |

### 5.3 回归检测驱动 FI 重算

当层2代际漂移检测或层3谱系检测发现异常时:
1. 强制触发 FI 重算 (不等待下一个 ETG)
2. 如果 FI 因此升高，执行对应级别的响应
3. 如果 FI 不变但漂移检测持续报警 → 标记为"沉默遗忘" (silent forgetting)，触发全量规则审查

### 5.4 新增文件清单

| 文件路径 | 用途 |
|---------|------|
| `memory/ccb-history.jsonl` | CCB 测试历史记录 |
| `memory/fi-history.jsonl` | FI 趋势记录 |
| `memory/capability-genealogy.json` | 能力谱系登记表 |
| `memory/L1-behavioral/frozen-anchors.json` | BS-001/BS-002 锚点定义 |
| `memory/snapshots/gen-XXXX.json` | 代际快照 (每 10 代) |
| `memory/probation-registry.json` | 新规则观察期登记 |
| `scripts/fi-calculator.py` | FI 计算器 |

### 5.5 现有文件修改点

| 文件 | 修改内容 |
|------|---------|
| `memory/session-state.json` | 增加 `fi` 和 `ccb_latest` 字段 |
| `memory/signature-performance.jsonl` | 记录中增加 `tier` 字段 |
| `scripts/bootstrap-reorganizer.py` | 增加锚点健康检查 + FI 检查调用 |
| `memory/session-graph.json` | 增加 `ccb_scores` 快照 |

---

## 6. 实现清单

### 6.1 FI 计算器 (预估 1h)

| # | 任务 | 优先级 | 依赖 |
|---|------|--------|------|
| FI-01 | 实现 `calculate_wFI()` — 加权瞬时 FI | P0 | CCB 数据有基线 |
| FI-02 | 实现 `calculate_tFI()` — 线性回归趋势 FI | P0 | 至少 3 条 CCB 历史 |
| FI-03 | 实现 `calculate_cFI()` — 综合 FI | P0 | FI-01, FI-02 |
| FI-04 | 实现 `determine_fi_level()` + `execute_fi_response()` | P0 | FI-03 |
| FI-05 | 创建 `memory/ccb-history.jsonl` 写入逻辑 | P0 | -- |
| FI-06 | 创建 `memory/fi-history.jsonl` 写入逻辑 | P0 | -- |
| FI-07 | 在 `session-state.json` 中增加 `fi` 字段 | P1 | FI-03 |
| FI-08 | 在 Bootstrap 中增加 FI 新鲜度检查 | P1 | FI-04 |

### 6.2 L1/L2 分层冻结锚点 (预估 1h)

| # | 任务 | 优先级 | 依赖 |
|---|------|--------|------|
| AP-01 | 创建 `frozen-anchors.json` 含 BS-001, BS-002 完整定义 | P0 | -- |
| AP-02 | 实现 `TierSystem` 类: `is_frozen()`, `can_modify()`, `enforce_min_strength()` | P0 | AP-01 |
| AP-03 | 实现 `validate_all_anchors()` 健康检查 | P0 | AP-02 |
| AP-04 | 定义 `RATCHET_RULES` 表并实现 `apply_ratchet()` | P0 | -- |
| AP-05 | 在 Bootstrap 中集成锚点健康检查 | P1 | AP-03 |
| AP-06 | 实现紧急解冻协议 (Merge 审核流程) | P2 | AP-02 |
| AP-07 | 在 `signature-performance.jsonl` 中增加 `tier` 字段 | P1 | AP-02 |

### 6.3 跨代能力回归检测 (预估 1.5h)

| # | 任务 | 优先级 | 依赖 |
|---|------|--------|------|
| CR-01 | 实现 `bidirectional_etg()` — 层1瞬态回归检测 | P0 | CCB 基线 |
| CR-02 | 实现 `generational_drift_check()` — 层2代际漂移 | P0 | CCB 历史 |
| CR-03 | 创建 `capability-genealogy.json` 并实现 `capability_genealogy_audit()` — 层3谱系检测 | P0 | CR-02 |
| CR-04 | 实现 `probation_manager()` — 新规则观察期 | P0 | CR-01 |
| CR-05 | 实现 `save_generational_snapshot()` + `rollback_to_generation()` | P1 | -- |
| CR-06 | 创建 `memory/snapshots/` 目录结构 | P1 | -- |
| CR-07 | 创建 `memory/probation-registry.json` | P1 | CR-04 |
| CR-08 | 实现 FI 与锚点联动 (FI 级别驱动锚点升级) | P1 | FI-04, AP-02 |

### 6.4 集成测试场景

| # | 场景 | 预期结果 |
|---|------|---------|
| T-01 | 模拟 CCB-01 从 0.95 降到 0.85 | FI 升至 0.10+，触发 🟠 预警 |
| T-02 | 模拟连续 3 代 CCB 微降 | tFI 转为正数，cFI 提前抬升 |
| T-03 | 尝试删除 BS-001 | 被 TIER-1 保护拒绝 |
| T-04 | 尝试将 MR-001 降至 0.20 | 棘轮卡在 0.30 |
| T-05 | 新规则通过双向 ETG 但净收益为负 | 被拒绝采纳 |
| T-06 | 新规则观察期内 CCB-03 下降 6% | 规则 contested，触发回滚 |
| T-07 | 代际漂移检测发现 2 项 CCB 下降 > 5% | 触发层2警报，联动 FI 重算 |
| T-08 | 谱系审计发现能力存活率 80% | 触发层3警报 |

---

## 附录 A: 关键决策记录

| 决策 | 理由 | 替代方案 |
|------|------|---------|
| cFI = 0.7*wFI + 0.3*tFI | 优先信任当前状态，但趋势不可忽视 | 0.5/0.5 对噪声太敏感; 0.9/0.1 太迟钝 |
| 🟡 级别就暂停新规则 | 遗忘是指数级代价，宁可多防 | Colony-014 原设计 🟡 只强化重放，不暂停规则 |
| BS-002 可微调不可删除 | 危险操作定义可能随时间演化 | 完全冻结会妨碍适应性 |
| 棘轮 min_strength 从 0.50 降到 0.30 | 允许更长的休眠周期，但禁止删除 | Colony-014 原设计 0.50 可能导致过早警告 |
| 谱系检测 30 代间隔 | 10 代太频繁(噪音多)，50 代太迟钝 | -- |

## 附录 B: 与 Colony-014 方案的差异

| 项目 | Colony-014 设计 | Colony-015 细化 |
|------|----------------|-----------------|
| FI 公式 | `FI = 1 - current/baseline` | wFI + tFI → cFI 三级计算 |
| FI 阈值 | 4 级 (0.05/0.15/0.30) | 5 级 (0.05/0.10/0.15/0.25) 含连续升级 |
| 锚点层级 | 模糊的 frozen/anchor 二分 | TIER-0/1/2/3 四级精确保护 |
| BS-001/BS-002 | 只给了名称 | 完整的 JSON 定义 + violation_patterns |
| 回归检测 | "双向 ETG 评估" | 三层检测 (瞬态/代际/谱系) |
| 快照系统 | "可一键回滚" | 完整快照格式 + 回滚安全门禁 |
| 观察期 | "3 个会话周期" | 观察期状态机 + contested 路径 |

---

*Colony-015 任务完成。输出路径: /d/极限实验室/colonies/colony-015/forgetting-phase2.md*
