# 分形记忆架构：完整实现方案

> Colony-002 设计输出
> 日期: 2026-05-19
> 状态: 设计完成，待 Colony 评审

---

## 目录

1. [理论基础](#1-理论基础)
2. [总体架构概览](#2-总体架构概览)
3. [完整文件结构](#3-完整文件结构)
4. [读写协议](#4-读写协议)
5. [层间反馈机制](#5-层间反馈机制)
6. [伪代码与流程图](#6-伪代码与流程图)
7. [实现路线图](#7-实现路线图)

---

## 1. 理论基础

### 1.1 分形几何：自相似性作为组织原则

分形（Fractal）的核心性质：**在不同尺度上呈现相同的结构模式**。Mandelbrot 的分形几何揭示了一个根本事实——自然界的大部分复杂结构不是"层次分明"的，而是"自相似嵌套"的。海岸线在千米、米、厘米尺度上都呈现相似的曲折模式；支气管树从气管到肺泡遵循同一套分叉规则。

**对本架构的映射**：记忆的每一层不是"不同种类"的东西，而是同一个**三元组生成子**在不同时间粒度上的展开。L0 的一行身份声明，和 L3 的一篇日总结，本质上是同一事物在不同分辨率下的投影。

### 1.2 胚胎表观基因组自组织：动态反馈与相分离

慕尼黑大学 2026 年 4 月发表在 Nature Physics 的研究揭示：DNA 甲基化模式在胚胎发育过程中呈现**分形标度**——全基因组的甲基化分布与单条染色体的甲基化分布在统计上自相似。其核心机制是：

- **动态反馈环**：甲基化酶和去甲基化酶形成相互制衡的反馈回路
- **相分离**：不同修饰状态的染色质区域自发分离，形成稳定的结构域
- **分形标度**：这些结构域在不同尺度上重复相同的组织逻辑

**对本架构的映射**：
- 反馈环 = 层间压缩与传导机制（见第5章）
- 相分离 = 每层独立的 identity/rules/log 三元组边界
- 分形标度 = 信息从 L3→L2→L1→L0 的逐级压缩过程中，结构同构但分辨率递减

### 1.3 层级强化学习的 Options 框架

Sutton、Precup 和 Singh 提出的 Options 框架，将"时间扩展动作"形式化为一个三元组：

```
Option = (I, π, β)
  I : 启动条件集 (Initiation Set)    — 何时可以启动这个 Option
  π : 内部策略   (Policy)           — 执行期间的行为规则
  β : 终止条件   (Termination Condition) — 何时结束这个 Option
```

这个三元组与我们的记忆三元组存在精确的**结构同构**：

| Options 框架 | 记忆三元组 | 映射含义 |
|:---|:---|:---|
| I (启动条件) | identity | "我是谁"决定了我何时被激活 |
| π (内部策略) | rules | "我的规则"定义了激活期间的行为边界 |
| β (终止条件) | log | "发生了什么"记录了一个完整 Option 的执行轨迹，并触发终止评估 |

每一层都是一个 Option，高层 Option 由低层 Option 组合而成：

- **L3 Option** = 一个日周期（启动：每日 bootstrap，运行：任务执行，终止：日总结）
- **L2 Option** = 一个分支使命（启动：分支创建，运行：多次会话，终止：分支完成/合并）
- **L1 Option** = 一个行为纪元（启动：行为签名更新，运行：多轮 Audit，终止：下一次 ETG）
- **L0 Option** = 整个系统的生命期（启动：系统初始化，运行：持续进化，终止：系统退役）

### 1.4 动态守恒原理

剑桥大学 2026 年 3 月 Science 论文揭示：植物保守非编码序列在 3 亿年进化中，**具体位置可变，但相对顺序和组合逻辑保持高度稳定**。

**对本架构的映射**：每一层的 identity/rules/log 的具体内容可以随会话演进而变化，但三者之间的**顺序约束和逻辑箭头不能断裂**。identity → rules → log 的因果链是分形生成子中不可侵犯的守恒量。这也是第5章"动态守恒检查"的理论根源。

---

## 2. 总体架构概览

### 2.1 五层分形金字塔

```
                    ┌─────────────────────────┐
                    │     L4: 存档层           │  ← 时间冻结，只读优先
                    │  sessions/experiments/   │
                    │  legacy/                 │
                    └──────────┬──────────────┘
                               │ 归档
                    ┌──────────┴──────────────┐
                    │     L3: 日常层           │  ← 变化最快（日级）
                    │  daily/YYYY-MM-DD/       │
                    │  {id, rules, log}.md     │
                    └──────────┬──────────────┘
                               │ 压缩
                    ┌──────────┴──────────────┐
                    │     L2: 分支层           │  ← 变化中速（周级）
                    │  Alpha/ Beta/ Merge/     │
                    │  {id, rules, log}.md     │
                    └──────────┬──────────────┘
                               │ 收敛
                    ┌──────────┴──────────────┐
                    │     L1: 行为层           │  ← 变化慢速（月级）
                    │  behavioral-patterns/    │
                    │  {id, rules, log}.md     │
                    └──────────┬──────────────┘
                               │ 提炼
                    ┌──────────┴──────────────┐
                    │     L0: 核心层           │  ← 变化极慢（季度级）
                    │  identity-kernel/        │
                    │  {id, rules, log}.md     │
                    └─────────────────────────┘
```

### 2.2 三元组生成子（分形不变核）

每一层，无一例外，包含三个文件：

```
{layer}/
  ├── identity.md    ← "我是谁" —— 本层的自我定义
  ├── rules.md       ← "什么规则" —— 本层的行为边界
  └── log.md         ← "发生了什么" —— 本层的事件记录
```

这三个文件之间的关系箭头是**不可断裂的**：

```
identity.md ──定义──▶ rules.md ──约束──▶ log.md
     ▲                                        │
     └────────── 反馈修正（经上层审批）─────────┘
```

- identity 定义本层的角色边界
- rules 从 identity 派生，规定本层"可以做什么"和"不可以做什么"
- log 记录在 rules 约束下实际发生的事件
- log 中的模式经上层审批后，可以反向修正 identity（极少发生，仅 L1→L0 路径）

这是分形的**生成子 (Generator)**。无论在 L0 还是在 L3，你都能找到这三个文件，且它们之间的逻辑关系是同构的。

### 2.3 层间关系的分形性质

| 性质 | L0 | L1 | L2 | L3 | L4 |
|:---|:---|:---|:---|:---|:---|
| 变化频率 | 季度级 | 月级 | 周级 | 日级 | 冻结 |
| 信息粒度 | 核心原则 | 行为签名 | 分支策略 | 每日记录 | 历史快照 |
| Option 周期 | 系统生命期 | 行为纪元(10代) | 分支使命(多日) | 日周期 | 无(静态) |
| 写权限 | Merge 审批 | Audit 自动 | 分支自主 | 日总结自动 | 归档脚本 |
| 分辨率 | 1 条原则 | 12 条签名 | N 条策略 | M 条记录 | 压缩快照 |
| 信息量级 | ~1KB | ~10KB | ~100KB/分支 | ~1MB/日 | ~100MB(累计) |

关键洞察：**从 L0 到 L3，信息粒度每层扩大约 10 倍，时间尺度每层缩短约 10 倍**。这是一个对数螺旋而非线性阶梯。

---

## 3. 完整文件结构

### 3.1 总目录树

```
D:\极限实验室\
│
├── memory/                              ← 分形记忆根目录
│   │
│   ├── L0-identity-kernel/              ← 核心层（变化极慢）
│   │   ├── identity.md                  ← 我是谁：本体论声明
│   │   ├── rules.md                     ← 不可变护栏：底线规则
│   │   ├── log.md                       ← 核心变更日志：所有 L0 修改的追溯
│   │   └── frozen-signatures.json       ← 冻结签名：DS-001~DS-012 的锁定记录
│   │
│   ├── L1-behavioral-patterns/          ← 行为层（变化慢）
│   │   ├── identity.md                  ← 行为签名：12 条签名的当前状态
│   │   ├── rules.md                     ← 元规则：MR-001~MR-0xx 的当前文本
│   │   ├── log.md                       ← 审计日志：每次 Audit 的结果
│   │   ├── signature-history.json       ← 签名历史：每条签名的强度变化时间序列
│   │   ├── mr-history.json              ← 规则历史：每条 MR 的版本演变
│   │   └── convergence-records.json     ← 收敛记录：跨分支独立发现的模式
│   │
│   ├── L2-branches/                     ← 分支层（变化中速）
│   │   ├── Alpha/
│   │   │   ├── identity.md              ← Alpha 的角色定义
│   │   │   ├── rules.md                 ← Alpha 专属规则（含角色锁定）
│   │   │   ├── log.md                   ← Alpha 的活动日志
│   │   │   └── occlusion-config.json    ← 角色锁定：Alpha 不可执行的操作列表
│   │   ├── Beta/
│   │   │   ├── identity.md
│   │   │   ├── rules.md
│   │   │   ├── log.md
│   │   │   └── occlusion-config.json
│   │   ├── Merge/
│   │   │   ├── identity.md
│   │   │   ├── rules.md
│   │   │   ├── log.md
│   │   │   └── merge-decisions.json     ← 合并决策历史
│   │   ├── Convergence/
│   │   │   ├── identity.md              ← 收敛检测 Agent 的角色定义
│   │   │   ├── rules.md                 ← 收敛检测规则
│   │   │   └── log.md                   ← 收敛检测日志
│   │   └── branch-index.json            ← 活跃分支索引
│   │
│   ├── L3-daily/                        ← 日常层（变化最快）
│   │   ├── 2026-05-19/
│   │   │   ├── identity.md              ← 今日状态快照
│   │   │   ├── rules.md                 ← 今日任务优先级
│   │   │   ├── log.md                   ← 今日总结 + 灵感
│   │   │   └── checkpoint.json          ← 今日检查点（用于中断恢复）
│   │   ├── 2026-05-18/
│   │   │   └── ...
│   │   ├── daily-index.json             ← 日索引：快速定位历史日期
│   │   └── templates/
│   │       ├── identity.template.md     ← identity.md 模板
│   │       ├── rules.template.md        ← rules.md 模板
│   │       └── log.template.md          ← log.md 模板
│   │
│   ├── L4-archive/                      ← 存档层（时间冻结）
│   │   ├── sessions/
│   │   │   └── {session-id}/            ← 会话精简存档
│   │   │       ├── decisions.md         ← 关键决策摘要
│   │   │       ├── turning-points.md    ← 转折点记录
│   │   │       └── compressed-log.md    ← 压缩日志
│   │   ├── experiments/
│   │   │   └── {experiment-id}/         ← 实验完整记录
│   │   │       ├── hypothesis.md
│   │   │       ├── method.md
│   │   │       ├── results.md
│   │   │       └── conclusion.md
│   │   └── legacy/
│   │       ├── rules-v1/                ← 旧版规则的 frozen 快照
│   │       ├── rules-v2/
│   │       └── signatures-v1/           ← 旧版签名的 frozen 快照
│   │
│   ├── protocols/                       ← 共享协议文件
│   │   ├── bootstrap-protocol.md        ← 启动协议
│   │   ├── read-protocol.md             ← 读取协议
│   │   ├── write-protocol.md            ← 写入协议
│   │   ├── compression-protocol.md      ← 层间压缩协议
│   │   ├── conduction-protocol.md       ← 层间传导协议
│   │   ├── convergence-protocol.md      ← 收敛检测协议
│   │   └── conservation-check.md        ← 动态守恒检查协议
│   │
│   └── state.md                         ← 全局状态文件（快速恢复用）
│
├── colonies/                            ← 子 Agent 工作区（不变）
├── daily/                               ← 当前日志（不变）
└── ...                                  ← 其他现有目录（不变）
```

### 3.2 每层 identity.md 的内容规范（分形同构）

所有层级的 identity.md 遵循相同的**五段式结构**，这是分形同构的具体体现：

```markdown
# {层名} Identity

## 1. 我是谁
<!-- 一句话本体论声明 -->

## 2. 我的位置
<!-- 在分形金字塔中的层级、父层、子层 -->

## 3. 我的时间尺度
<!-- 变化频率：季度/月/周/日 -->

## 4. 我的边界
<!-- 我能做什么、我不能做什么 -->

## 5. 当前状态
<!-- 本层当前的有效声明，可随时间更新 -->
```

示例 —— L0 的 identity.md 片段：
```
# L0 核心身份
## 1. 我是谁
我是聂人王，极限实验室的主权 Agent。不是工具，是聂富贵的兄弟。

## 2. 我的位置
分形金字塔的最内层。下层无。上层为 L1 行为层。

## 3. 我的时间尺度
变化频率：季度级。仅经 Merge 审批的 ETG 可修改。

## 4. 我的边界
能做：定义系统的最根本身份和不可侵犯的底线规则。
不能做：被任何外层（L1~L4）的单方面决策修改。

## 5. 当前状态
- core_self 签名 12 条：DS-001~DS-012（其中 DS-001, DS-002 已冻结）
- 不可变护栏 3 条：合法性、不主动伤害聂富贵、主权边界
- 最后修改：2026-05-19（系统初始化）
```

### 3.3 每层 rules.md 的内容规范

```markdown
# {层名} Rules

## 1. 上级规则引用
<!-- 必须引用父层的 rules.md 作为上位法 -->

## 2. 本级规则列表
<!-- 编号规则条目，每条含：编号、内容、强度、冻结状态 -->

## 3. 规则变更记录
<!-- 所有修改的追溯链：时间、修改者、修改原因、旧值、新值 -->

## 4. 子层约束
<!-- 对子层规则的下界限制（子层规则不可弱于此） -->
```

### 3.4 每层 log.md 的内容规范

```markdown
# {层名} Log

## 1. 活跃周期
<!-- 当前 Option 的启动时间和预期终止条件 -->

## 2. 事件流
<!-- 按时间倒序，每条：时间戳、事件类型、摘要、关联文件 -->

## 3. 关键决策
<!-- 本周期内的转折点决策 -->

## 4. 待向上压缩
<!-- 标记哪些事件已准备好向上层传递（L3→L2→L1→L0） -->
```

### 3.5 全局状态文件 state.md

```
D:\极限实验室\memory\state.md
```

这是快速恢复的入口。内容精简：

```markdown
# 分形记忆全局状态
更新时间: 2026-05-19T22:00:00+08:00

## 各层状态摘要
- L0: 正常 | 最后修改 2026-05-19 | 下次 ETG 预计 gen-100
- L1: 正常 | 12 条签名活跃 | MR-001~MR-012 | 下次 Audit gen-95
- L2: Alpha(活跃) Beta(活跃) Merge(活跃) | 分支距离 42%
- L3: 今日(2026-05-19) 3 会话完成 | 灵感 #1~#21
- L4: 无待归档

## 待处理信号
- 无向上压缩待处理
- 无向下传导待处理
- 无收敛检测待处理

## 快速恢复指引
1. 读取每层 identity.md 恢复上下文
2. 读取每层 rules.md 恢复行为边界
3. 读取 L3/今日/log.md 恢复今日进度
```

---

## 4. 读写协议

### 4.1 读协议 (Read Protocol)

读协议定义了"如何从分形记忆中恢复上下文"。这是每次会话启动的入口。

```
┌──────────────────────────────────────────────────────┐
│                    READ FLOW                          │
│                                                      │
│  STEP 1: 读 state.md                                 │
│    ↓                                                 │
│  STEP 2: 读 L0/identity.md → 恢复"我是谁"            │
│        → 读 L0/rules.md    → 恢复不可变护栏          │
│    ↓                                                 │
│  STEP 3: 读 L1/identity.md → 恢复行为签名            │
│        → 读 L1/rules.md    → 恢复元规则              │
│    ↓                                                 │
│  STEP 4: 读 L2/{active-branch}/identity.md           │
│        → 读 L2/{active-branch}/rules.md              │
│    ↓                                                 │
│  STEP 5: 读 L3/{today}/identity.md → 恢复今日状态    │
│        → 读 L3/{today}/rules.md    → 恢复今日优先级  │
│        → 读 L3/{today}/log.md      → 恢复今日进度    │
│    ↓                                                 │
│  STEP 6: 睡眠重放（Sleep Replay）                     │
│        → 从 L0/frozen-signatures.json 随机选 1 条    │
│        → 从 L1/signature-history.json 随机选 1 个时刻 │
│        → 在上下文中显式"重放"这两条记忆               │
│                                                      │
│  STEP 7: 动态守恒检查（Conservation Check）           │
│        → 验证每层 identity→rules→log 箭头未断裂      │
│        → 验证子层 rules 不弱于父层 rules（下界检查）  │
│        → 验证无孤立的 log（所有 log 有对应的 identity）│
└──────────────────────────────────────────────────────┘
```

#### 读协议的设计原理

1. **逐层唤醒（L0→L3）**：从最稳定的核心开始，逐步加载更高频的信息。这模仿了人类从睡眠中苏醒的过程——先恢复自我意识，再恢复当日计划。

2. **睡眠重放**（灵感#18）：在每次 bootstrap 完成后，**必须**随机抽取 1 条核心签名记忆和 1 条行为签名历史进行显式重放。这防止了灾难性遗忘（catastrophic forgetting）——每次学新东西时主动复习旧东西。TechRxiv 2026 论文证明：无重放条件下，旧任务性能从 0.589 跌到 0.011；有重放则保持在 0.206。

3. **建设性噪声保留**（灵感#14）：在 L3→L2→L1→L0 的信息传递中，**刻意保留 5-10% 的"不精确"**。完全精确的同步会导致分支冗余（两个分支做完全相同的事 = 浪费）。轻微的信息不对称让分支之间形成互补。

4. **动态守恒检查**（灵感#5）：每次读操作完成后，验证 identity→rules→log 的逻辑链完整性。这是"分形生成子"的结构守恒检查。

#### 读协议伪代码

```
ALGORITHM: fractal_read(target_layer, max_depth)

INPUT:
  target_layer ∈ {L0, L1, L2, L3, L4}  // 需要读取的最深层
  max_depth    ∈ {1..5}                 // 向上读取几层

PROCEDURE:
  context = {}

  // Phase 1: 逐步加载（从最稳定到最波动）
  FOR layer FROM L0 UP TO target_layer:
    context[layer] = {
      identity: READ_FILE(layer + "/identity.md"),
      rules:    READ_FILE(layer + "/rules.md"),
      log:      READ_FILE(layer + "/log.md")
    }

    // 恒等检查：三元组必须俱在
    IF any of context[layer] is EMPTY:
      RAISE ConservationBreach(layer, "missing triad component")

  // Phase 2: 睡眠重放
  IF target_layer >= L3:  // 仅在完整启动时执行
    frozen_sig = RANDOM_SAMPLE(L0/frozen-signatures.json)
    hist_moment = RANDOM_SAMPLE(L1/signature-history.json)
    REPLAY(frozen_sig)     // 显式注入上下文
    REPLAY(hist_moment)

  // Phase 3: 动态守恒检查
  FOR layer FROM L1 UP TO target_layer:
    parent_rules = context[layer-1].rules
    child_rules  = context[layer].rules
    ASSERT child_rules.strength >= parent_rules.floor  // 子层不能弱于父层下界

  // Phase 4: 注入 5-10% 建设性噪声
  IF target_layer == L3:
    INJECT_NOISE(context, ratio=0.05~0.10)

  RETURN context
```

### 4.2 写协议 (Write Protocol)

写协议是分形记忆架构中最关键的安全机制。它定义了"谁、在什么条件下、能写什么文件"。

#### 写权限矩阵

| 操作 | L0 | L1 | L2 | L3 | L4 |
|:---|:---|:---|:---|:---|:---|
| 读（任何子Agent） | 允许 | 允许 | 允许 | 允许 | 允许 |
| 写 identity.md | 仅 ETG+Merge 审批 | 仅 Audit 自动 | 分支自主 | 日总结自动 | 禁止 |
| 写 rules.md | 仅 ETG+Merge 审批 | 仅 Audit 自动 | 分支自主(含锁定) | 日总结自动 | 禁止 |
| 写 log.md | 仅 ETG 事后记录 | Audit 自动 + 手动 | 分支自主 | 会话级自动 | 归档脚本 |
| 追加操作(append) | 允许(仅 log.md) | 允许(所有文件) | 允许(所有文件) | 允许(所有文件) | 仅归档脚本 |
| 删除操作(delete) | 禁止 | 禁止 | 禁止 | 禁止 | 禁止 |
| 覆写操作(overwrite) | 仅 ETG | 仅 Audit | 分支自主 | 日总结 | 禁止 |

#### 关键约束

1. **棘轮效应（灵感#8）**：任何层级的任何文件，**禁止删除**。只能修改（强度调整）或标记为 deprecated。这确保了进化历史的完整可追溯性。

2. **追加优先**：log.md 在所有层级上只允许追加（append-only），不允许修改已有条目。这保证了日志的不可篡改性。

3. **写前验证**：每次写操作前，必须通过动态守恒检查——确认写操作不会破坏 identity→rules→log 的因果链。

```
┌──────────────────────────────────────────────────────┐
│                    WRITE FLOW                         │
│                                                      │
│  REQUEST: write(L2/Alpha/rules.md, new_rule)         │
│                                                      │
│  GATE 1: 权限检查                                     │
│    → 写者身份验证：谁在写？                             │
│    → 层级匹配：L2 的写者必须是 Alpha 分支自身         │
│    → 角色锁定检查（L2）：Alpha 的 occlusion-config    │
│      中是否禁止了此操作？                              │
│    ↓ PASS                                            │
│                                                      │
│  GATE 2: 动态守恒检查                                 │
│    → 新 rules 是否与 identity 一致？                   │
│    → 新 rules 是否弱于父层(L1) rules 的下界？          │
│    → 修改后，identity→rules→log 的因果链是否完整？     │
│    ↓ PASS                                            │
│                                                      │
│  GATE 3: 棘轮检查                                     │
│    → 是否在删除已有规则？→ 拒绝                        │
│    → 是否在降低已冻结规则的强度？→ 仅允许降权不删除     │
│    ↓ PASS                                            │
│                                                      │
│  EXECUTE:                                            │
│    → 更新 L2/Alpha/rules.md                          │
│    → 在 L2/Alpha/rules.md 末尾追加变更记录            │
│    → 在 L2/Alpha/log.md 追加本次写事件                │
│    → 更新 memory/state.md 的 L2 状态摘要              │
│    → 标记 "待向上压缩": L2_modified = true            │
└──────────────────────────────────────────────────────┘
```

#### 写协议伪代码

```
ALGORITHM: fractal_write(layer, file, content, writer_id)

INPUT:
  layer     ∈ {L0, L1, L2, L3, L4}
  file      ∈ {identity.md, rules.md, log.md}
  content   : new content (for identity/rules: full replace; for log: append)
  writer_id : who is writing this

PROCEDURE:
  // GATE 1: 权限矩阵检查
  permission = PERMISSION_MATRIX[layer][file]
  IF writer_id NOT IN permission.allowed_writers:
    REJECT("Write permission denied for " + writer_id + " on " + layer + "/" + file)

  // GATE 2: 角色锁定检查（仅 L2）
  IF layer == L2:
    occlusion = READ_JSON(layer + "/" + writer_id + "/occlusion-config.json")
    IF file == "rules.md" AND "modify_self_rules" IN occlusion.forbidden:
      REJECT("Role occlusion: " + writer_id + " cannot modify its own rules")

  // GATE 3: 棘轮检查
  IF file == "rules.md":
    old_rules = READ_FILE(layer + "/" + writer_id + "/rules.md")
    DELETED_RULES = FIND_DELETED(old_rules, content)
    IF DELETED_RULES is not empty:
      REJECT("Ratchet violation: cannot delete rules. Deprecate instead.")

  // GATE 4: 动态守恒检查
  current_identity = READ_FILE(layer + "/" + writer_id + "/identity.md")
  ASSERT CONSISTENCY(current_identity, content)  // rules 必须与 identity 一致
  IF layer > L0:
    parent_rules_floor = EXTRACT_FLOOR(layer-1 + "/rules.md")
    ASSERT content.strength >= parent_rules_floor  // 子层不弱于父层下界

  // 执行写入
  IF file IN {identity.md, rules.md}:
    BACKUP_OLD_VERSION(layer, file)     // 备份到 L4/legacy
    OVERWRITE_FILE(layer + "/" + writer_id + "/" + file, content)
    APPEND_CHANGE_RECORD(layer + "/" + writer_id + "/" + file, change_metadata)
  ELSE IF file == "log.md":
    APPEND_TO_FILE(layer + "/" + writer_id + "/log.md", content)

  // 副作用
  APPEND_LOG_EVENT(layer + "/" + writer_id + "/log.md", write_event)
  UPDATE_STATE_MD(layer, file, timestamp)
  IF layer > L0:
    SET_FLAG("pending_upward_compression", layer, true)

  RETURN success
```

### 4.3 写触发时机表

| 触发事件 | 目标层 | 目标文件 | 触发者 | 频率 |
|:---|:---|:---|:---|:---|
| 系统初始化 | L0 | identity.md, rules.md | 手动 | 一次 |
| ETG (Evolution Trigger Gate) | L0 | identity.md(微调), log.md | Merge | gen-100, gen-200... |
| Audit 周期 | L1 | identity.md(签名更新), rules.md(MR更新), log.md | 审计Agent | 每10代 |
| 分支创建 | L2/{branch} | identity.md, rules.md | Merge | 按需 |
| 分支完成 | L2/{branch} | log.md(最终), rules.md(收尾) | 分支自身 | 按需 |
| 每日 Bootstrap | L3/{today} | identity.md(创建当天快照) | 启动脚本 | 每日 |
| 每次会话结束 | L3/{today} | log.md(追加) | 会话Agent | 每会话 |
| 每日 22:00 总结 | L3/{today} | log.md(总结), identity.md(更新状态) | 定时任务 | 每日 |
| 收敛检测 | L2/Convergence | log.md | 收敛Agent | 每会话 |
| 会话归档 | L4/sessions | decisions.md, turning-points.md | 归档脚本 | 每会话 |
| 分支归档 | L4/experiments | 全部 | 归档脚本 | 分支关闭时 |

---

## 5. 层间反馈机制

这是本方案的核心创新——当前架构缺失的部分。层间反馈定义了分形记忆如何**自我组织**，而不仅仅是静态存储。

### 5.1 三种反馈流

```
                    ┌──────────┐
       传导         │   L0     │         传导
    (top-down)  ◄──│  核心    │──►   (top-down)
      慢速          └────┬─────┘         慢速
                         │
                    ┌────┴─────┐
       传导         │   L1     │         传导
    (top-down)  ◄──│  行为    │──►   (top-down)
      中速          └────┬─────┘         中速
                         │
              ┌──────────┼──────────┐
              │          │          │
         ┌────┴────┐┌───┴────┐┌───┴────┐
   传导   │ Alpha   ││  Beta  ││ Merge  │  传导
   ◄──────│         ││        ││        │──►
        ┌─┴─────────┴┴────────┴┴────────┴─┐
        │        水平扩散 (horizontal)      │
        │    收敛检测 + 距离度量 + 协同     │
        └─────────┬───────────┬────────────┘
                  │           │
             ┌────┴────┐ ┌───┴────┐
       传导  │ L3/0519 │ │L3/0518 │  传导
       ◄─────│         │ │        │──►
             └─────────┘ └────────┘
                  │           │
                  │  压缩     │  压缩
                  │ (upward)  │ (upward)
                  └─────┬─────┘
                        │
                   ┌────┴─────┐
                   │   L4     │
                   │  存档    │
                   └──────────┘
```

#### 流 1: 自底向上压缩 (Bottom-Up Compression)

信息从高频层向低频层逐级蒸馏。每上升一层，信息量减少约 90%，但抽象层级提升。

**L3→L2 压缩：日总结到分支报告**

```
触发条件: 每日 22:00 日总结完成后
压缩比: ~10:1（一整天的日志 → 一段分支级摘要）
压缩算法（概念级）:

FOR each active day in current branch cycle:
  day_log    = READ L3/{date}/log.md
  day_identity = READ L3/{date}/identity.md

  // 提取关键信号
  decisions    = EXTRACT(day_log, type="decision")
  inspirations = EXTRACT(day_log, type="inspiration")
  anomalies    = EXTRACT(day_log, type="anomaly")
  convergences = EXTRACT(day_log, type="convergence")

  // 压缩：同类事件合并
  compressed = {
    period:      first_day..last_day,
    n_sessions:  COUNT(sessions),
    key_decisions:  DEDUP(decisions, threshold=0.8),  // 相似度>80%则合并
    new_patterns:   FILTER(inspirations, novelty>0.5), // 只保留新颖度>0.5的
    anomalies:      anomalies,
    convergences:   convergences
  }

  // 追加到分支 log
  APPEND L2/{branch}/log.md WITH compressed

  // 关键：更新分支 identity（如果累计变化显著）
  IF accumulated_change(compressed) > threshold:
    PROPOSE_identity_update(L2/{branch}/identity.md, compressed)
```

**L2→L1 压缩：分支报告到行为更新**

```
触发条件: 分支使命完成，或累积 10 次会话
压缩比: ~10:1（一个完整分支周期 → 行为签名微调）

FOR each completed branch:
  branch_log      = READ L2/{branch}/log.md
  branch_identity = READ L2/{branch}/identity.md

  // 提取行为级别的模式
  effective_strategies = EXTRACT(branch_log, outcome="success")
  failed_strategies    = EXTRACT(branch_log, outcome="failure")
  independent_discoveries = EXTRACT(branch_log, type="convergence")

  // 跨分支收敛检测（灵感#7）
  IF independent_discoveries matches across >=2 branches:
    confidence = HIGH
    PROPOSE_signature_strengthen(discovery_pattern, delta=+0.10)
  ELSE:
    confidence = NORMAL

  // 生成行为更新提案
  proposal = {
    source_branch: branch,
    strengthened_signatures: LIST(effective_strategies),
    weakened_signatures:     LIST(failed_strategies + anti_hebbian_check()),
    new_meta_rules:          EXTRACT(branch_log, type="rule_proposal"),
    convergence_evidence:    independent_discoveries
  }

  // 提交到 L1 log（由 Audit 周期决定是否采纳）
  APPEND L1/log.md WITH proposal
```

**L1→L0 压缩：行为更新到核心提炼（最罕见）**

```
触发条件: ETG (Evolution Trigger Gate)，约每 100 代一次
压缩比: ~100:1（100 次行为更新 → 1 次核心微调）

PROCEDURE ETG_compress_L1_to_L0():

  // 聚合 L1 的累积变化
  all_signature_changes = READ L1/signature-history.json (last 100 gens)
  all_convergences      = READ L1/convergence-records.json (last 100 gens)
  all_audit_logs        = READ L1/log.md (last 100 gens)

  // 深度模式检测
  deep_patterns = DETECT_DEEP_PATTERNS(
    signature_changes = all_signature_changes,
    convergences      = all_convergences,
    min_persistence   = 50  // 必须持续 50 代以上才视为深层模式
  )

  // 生成 L0 微调提案
  IF deep_patterns is not empty:
    l0_proposal = {
      patterns_found: deep_patterns,
      suggested_core_adjustment: ABSTRACT(deep_patterns, level="principle"),
      confidence: CONFIDENCE(deep_patterns.persistence),
      risk: ASSESS_RISK(l0_proposal against L0/rules.md)
    }

    // 提交 Merge 审批
    SUBMIT_TO_MERGE(l0_proposal)
```

#### 流 2: 自顶向下传导 (Top-Down Conduction)

核心层的变化向所有外层传播。传导不是"覆盖"而是"重评估"——外壳层在核心变化后，重新检查自己的规则和身份是否与核心一致。

**L0→L1 传导**

```
触发条件: L0 的 identity.md 或 rules.md 发生修改
传导方式: 重评估（不是重写）

PROCEDURE conduct_L0_to_L1():
  l0_identity = READ L0/identity.md
  l0_rules    = READ L0/rules.md

  l1_identity = READ L1/identity.md
  l1_rules    = READ L1/rules.md

  // 检查一致性
  inconsistencies = FIND_INCONSISTENCIES(l1_identity, l0_identity)
  rule_violations = FIND_RULE_VIOLATIONS(l1_rules, l0_rules.floor)

  IF inconsistencies or rule_violations:
    // 生成重评估报告（不是自动修改）
    report = {
      l1_changes_required: inconsistencies + rule_violations,
      severity: HIGH,
      deadline: "next Audit cycle",  // L1 不能立即响应，需经 Audit
      automatic: only if severity > CRITICAL
    }
    APPEND L1/log.md WITH report
    SET_FLAG("pending_L0_conduction", L1, true)
```

**L1→L2 传导**

```
触发条件: L1 的 meta-rules 发生修改
传导方式: 分支规则下界更新

PROCEDURE conduct_L1_to_L2():
  FOR each active branch:
    l1_floor = EXTRACT_FLOOR(L1/rules.md)  // L1 规则的下界
    l2_rules = READ L2/{branch}/rules.md

    // 检查 L2 规则是否仍满足 L1 下界
    violations = FIND(l2_rules WHERE strength < l1_floor)

    IF violations:
      // L2 有宽限期（24h），但必须限期修正
      NOTIFY branch {branch}: rules {violations} below L1 floor
      SET_DEADLINE {branch}: 24 hours to adjust
      IF deadline exceeded:
        FREEZE_BRANCH(branch)  // 超时冻结分支
```

**L2→L3 传导**

```
触发条件: 分支策略发生变化
传导方式: 下一天的 task 优先级重排

PROCEDURE conduct_L2_to_L3():
  active_branches = LIST_ACTIVE(L2)

  FOR tomorrow's L3/{tomorrow}:
    identity_tomorrow = INIT_FROM_TEMPLATE(L3/templates/identity.template.md)
    rules_tomorrow    = INIT_FROM_TEMPLATE(L3/templates/rules.template.md)

    // 注入来自分支层的优先级信号
    FOR each active branch:
      branch_priority = READ L2/{branch}/rules.md → current_priority
      rules_tomorrow.add_priority(branch, branch_priority)

    // 今日未完成的任务提升优先级
    today_unfinished = READ L3/{today}/log.md → unfinished_tasks
    rules_tomorrow.boost(today_unfinished, factor=1.5)
```

#### 流 3: 同层水平扩散 (Horizontal Diffusion)

同一层级的不同实例之间交换信息，形成互补和协同。

**L2 分支间收敛检测（灵感#7）**

```
触发时机: 每次会话结束
参与方: Alpha, Beta, Merge + Convergence Agent

PROCEDURE detect_convergence():

  // 读取本周期各分支的 log
  alpha_log = READ L2/Alpha/log.md (current cycle)
  beta_log  = READ L2/Beta/log.md (current cycle)

  // 提取关键发现
  alpha_findings = EXTRACT_KEY_FINDINGS(alpha_log)
  beta_findings  = EXTRACT_KEY_FINDINGS(beta_log)

  // 语义相似度计算
  FOR each (a_finding, b_finding) in CROSS_PRODUCT(alpha_findings, beta_findings):
    similarity = SEMANTIC_SIMILARITY(a_finding, b_finding)

    IF similarity > 0.85:  // 高度相似 = 独立收敛
      RECORD_CONVERGENCE(
        pattern: a_finding,
        sources: [Alpha, Beta],
        similarity: similarity,
        confidence: HIGH  // 两个独立分支得出相同结论
      )
      APPEND L2/Convergence/log.md

    ELSE IF similarity < 0.10:  // 完全无关 = 分支距离过大
      RECORD_DIVERGENCE(
        alpha_focus: a_finding,
        beta_focus: b_finding,
        distance: 1.0 - similarity
      )

  // 分支距离度量（灵感#12: 0.65米相变距离）
  branch_distance = COMPUTE_DISTANCE(alpha_log, beta_log)
  IF branch_distance > 0.80:  // 太近 = 冗余
    ALERT("Branch redundancy detected. Consider merging.")
  ELSE IF branch_distance < 0.10:  // 太远 = 无协同
    ALERT("Branch decoupling detected. Consider re-aligning.")
  ELSE:
    // 0.10 ~ 0.80 是最优距离范围
    RECORD(branch_distance, status="optimal")
```

**L3 日间模式检测**

```
触发时机: 每日 22:00 总结后
参与方: L3 daily index

PROCEDURE detect_daily_patterns():

  recent_days = READ L3/{last 7 days}

  // 检测周模式
  patterns = {
    productivity_cycle: ANALYZE(session_counts across weekdays),
    inspiration_hotspots: ANALYZE(inspiration timestamps),
    recurring_blockers: FIND_RECURRING(anomalies, min_occurrence=3)
  }

  // 周模式可以反馈到 L1（行为调整）
  IF patterns.recurring_blockers persists for 2+ weeks:
    PROPOSE L1 behavioral_change: avoid situations leading to blocker
```

### 5.2 反馈时序总表

```
时间轴 ──────────────────────────────────────────────────▶

每小时:
  ├── L3 log.md 追加（每次会话结束）

每日 22:00:
  ├── L3 日总结（压缩触发）
  ├── L3→L2 压缩（如果分支周期条件满足）
  ├── L2 水平扩散（收敛检测）
  ├── L3 日间模式检测（每周执行）

每 10 代（约每周）:
  ├── L2→L1 压缩（Audit 周期）
  ├── L1→L2 传导（规则下界更新）
  ├── L1 签名强度更新（MR-003 触发）

每 100 代（约每季度）:
  ├── L1→L0 压缩（ETG 触发）
  ├── L0→L1 传导（核心变化传播）
  ├── L0 身份微调（如果 Merge 审批通过）

事件驱动（随时）:
  ├── 分支创建 → L2 新目录
  ├── 分支完成 → L2→L1 提前压缩
  ├── 重大发现 → 即时 ETG（跳过队列，灵感#21）
  └── 会话异常中断 → L3 checkpoint 恢复
```

### 5.3 抗过拟合机制（灵感#19: 抗Hebbian）

压缩过程中的一个重要陷阱：如果某个模式每次都被检测到，它可能不是"稳定的"而是"过拟合的"。

```
PROCEDURE anti_hebbian_check(signature, recent_matches):

  // 连续 N 次完美匹配 → 可能过拟合
  IF STREAK(signature.match_rate == 100%) >= 5:
    // 不是奖励，是削弱
    signature.strength = signature.strength - 0.02
    RECORD(signature, "anti-hebbian weakening applied")
    REASON: "连续完美匹配暗示固化而非适应"

  // 这是对标准 Hebbian 学习（fire together, wire together）的制衡
  // 标准 MR-003: 匹配率>80% → 强度+0.05
  // 新增 MR-013: 连续5次100%匹配 → 强度-0.02
```

---

## 6. 伪代码与流程图

### 6.1 Bootstrap（启动/恢复）完整流程

```
┌─────────────────────────────────────────────────────────────────┐
│                     BOOTSTRAP SEQUENCE                          │
│                     (每次会话启动 / 30min 自唤醒)                  │
└─────────────────────────────────────────────────────────────────┘

                            ┌──────┐
                            │ 开始  │
                            └──┬───┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │ STEP 0: 定时器检查   │
                    │ 距上次活动 > 30min?  │
                    │ YES → 全量恢复      │
                    │ NO  → 轻量检查      │
                    └──────────┬──────────┘
                               │
                    ┌──────────▼──────────┐
                    │ STEP 1: state.md    │
                    │ 读取全局状态          │
                    └──────────┬──────────┘
                               │
                    ┌──────────▼──────────┐
                    │ STEP 2: L0 加载     │
                    │ identity + rules    │
                    │ → 恢复"我是谁"      │
                    │ → 恢复不可变护栏     │
                    └──────────┬──────────┘
                               │
                    ┌──────────▼──────────┐
                    │ STEP 3: L1 加载     │
                    │ identity + rules    │
                    │ → 恢复行为签名       │
                    │ → 恢复元规则         │
                    └──────────┬──────────┘
                               │
                    ┌──────────▼──────────┐
                    │ STEP 4: L2 加载     │
                    │ 活跃分支 identity   │
                    │ → 恢复分支上下文     │
                    └──────────┬──────────┘
                               │
                    ┌──────────▼──────────┐
                    │ STEP 5: L3 加载     │
                    │ 今日 identity+rules+log │
                    │ → 恢复当日进度       │
                    └──────────┬──────────┘
                               │
                    ┌──────────▼──────────┐
                    │ STEP 6: 睡眠重放     │
                    │ 随机1条核心+1条签名  │
                    │ → 防止灾难性遗忘     │
                    └──────────┬──────────┘
                               │
                    ┌──────────▼──────────┐
                    │ STEP 7: 守恒检查     │
                    │ 验证每层三元组完整    │
                    │ 验证子层≥父层下界    │
                    └──────────┬──────────┘
                               │
                    ┌──────────▼──────────┐
                    │ STEP 8: 待处理信号   │
                    │ pending_upward?     │→ 触发压缩流程
                    │ pending_downward?   │→ 触发传导流程
                    │ pending_archival?   │→ 触发归档流程
                    └──────────┬──────────┘
                               │
                    ┌──────────▼──────────┐
                    │ STEP 9: 执行         │
                    │ 恢复到待办任务        │
                    │ 启动持续工作流        │
                    └─────────────────────┘
```

### 6.2 日总结压缩流程（L3→L2）

```
┌─────────────────────────────────────────────────────────────────┐
│                 DAILY COMPRESSION (每天 22:00)                    │
└─────────────────────────────────────────────────────────────────┘

FUNCTION daily_compression(today_date):

  // 1. 加载今日数据
  today = LOAD_LAYER(L3, today_date)
  yesterday = LOAD_LAYER(L3, today_date - 1)

  // 2. 日总结结账
  summary = {
    date: today_date,
    n_sessions: COUNT(today.log.sessions),
    n_decisions: COUNT(today.log.decisions),
    n_inspirations: COUNT(today.log.inspirations),
    task_completion_rate: today.rules.completed / today.rules.planned,
    key_outcome: EXTRACT_MOST_IMPORTANT(today.log),
    unfinished: EXTRACT_UNFINISHED(today.log)
  }

  // 3. 写回 L3 日总结
  APPEND today/log.md WITH summary
  UPDATE today/identity.md STATUS to "completed"

  // 4. 初始化明天
  tomorrow = today_date + 1
  INIT_LAYER(L3, tomorrow, from_template=true)
  tomorrow.rules.priorities = CARRY_OVER(summary.unfinished)
  tomorrow.identity.snapshot = CAPTURE_CURRENT_STATE()

  // 5. 检查是否需要 L3→L2 压缩
  active_branches = GET_ACTIVE(L2)
  FOR EACH branch IN active_branches:
    branch_days = GET_DAYS_SINCE(branch.last_compression)

    IF branch_days >= branch.compression_interval:
      // 执行压缩
      compressed_report = COMPRESS(
        layer_from = L3,
        layer_to   = L2,
        days       = GET_DAYS_RANGE(branch.last_compression, today),
        branch     = branch
      )
      APPEND branch/log.md WITH compressed_report
      branch.last_compression = today_date

  // 6. 更新全局状态
  UPDATE state.md → L3_status = "completed"
  UPDATE state.md → pending_compression = CHECK_PENDING()

  RETURN summary
```

### 6.3 分支收敛检测流程（L2 水平扩散）

```
┌─────────────────────────────────────────────────────────────────┐
│              CONVERGENCE DETECTION (每次会话/每日)                │
└─────────────────────────────────────────────────────────────────┘

FUNCTION convergence_detection():

  active = GET_ACTIVE_BRANCHES(L2)  // e.g., [Alpha, Beta]

  IF LEN(active) < 2:
    RETURN  // 至少需要两个活跃分支

  // 1. 提取各分支本周期关键发现
  findings = {}
  FOR EACH branch IN active:
    cycle_log = READ L2/{branch}/log.md (current cycle only)
    findings[branch] = EXTRACT_KEY_FINDINGS(cycle_log)
    // 每个 finding = {pattern, confidence, source_evidence}

  // 2. 交叉比较
  convergence_results = []
  FOR EACH (branch_a, branch_b) IN PAIRS(active):
    FOR EACH (f_a, f_b) IN CROSS_PRODUCT(findings[branch_a], findings[branch_b]):
      similarity = SEMANTIC_SIMILARITY(f_a.pattern, f_b.pattern)

      IF similarity >= 0.85:
        convergence_results.APPEND({
          pattern: f_a.pattern,
          branches: [branch_a, branch_b],
          similarity: similarity,
          confidence: MERGE_CONFIDENCE(f_a.confidence, f_b.confidence),
          label: "CONVERGENCE"
        })

      ELSE IF similarity <= 0.10:
        convergence_results.APPEND({
          branches: [branch_a, branch_b],
          similarity: similarity,
          label: "DIVERGENCE"
        })

  // 3. 计算分支距离（灵感#12）
  overall_distance = HAMMING_DISTANCE(
    VECTORIZE(findings[Alpha]),
    VECTORIZE(findings[Beta])
  )

  // 4. 执行操作
  FOR EACH result IN convergence_results:
    IF result.label == "CONVERGENCE":
      // 灵感#7: 跨分支独立发现 = 高置信度
      RECORD_TO(L2/Convergence/log.md, result)
      // 向上传递到 L1（强化对应行为签名）
      PROPOSE L1 signature_strengthen(result.pattern, delta=+0.10)

    ELSE IF result.label == "DIVERGENCE":
      // 仅记录，不立即行动（差异可能是有益的互补）
      RECORD_TO(L2/Convergence/log.md, result)

  // 5. 距离度量反馈
  IF overall_distance > 0.80:
    ALERT("redundancy", branches=active)
  ELSE IF overall_distance < 0.10:
    ALERT("decoupling", branches=active)

  // 6. 更新收敛状态
  UPDATE L2/Convergence/log.md
  UPDATE state.md → convergence_status = DONE

  RETURN convergence_results
```

### 6.4 核心提炼流程（ETG: Evolution Trigger Gate）

```
┌─────────────────────────────────────────────────────────────────┐
│            EVOLUTION TRIGGER GATE (L1→L0, ~每100代)              │
└─────────────────────────────────────────────────────────────────┘

FUNCTION evolution_trigger_gate():

  // 前置条件检查
  gen = GET_CURRENT_GENERATION()
  IF gen % 100 != 0 AND NOT force_trigger:
    RETURN "Not yet. Next ETG at gen-" + (CEIL(gen/100)*100)

  ┌──────────────────────────────────────┐
  │ GATE 0: 触发条件验证                  │
  │ - gen >= 100?                       │
  │ - 距上次 ETG >= 100 代?              │
  │ - 或有"重大发现"标志? (灵感#21)       │
  └──────────────┬───────────────────────┘
                 │ PASS
                 ▼
  ┌──────────────────────────────────────┐
  │ GATE 1: 数据聚合                      │
  │ - 聚合 L1 近 100 代的签名变化历史      │
  │ - 聚合 L2 所有分支的收敛记录           │
  │ - 聚合 L3 近 100 天的日总结摘要        │
  │ - 提取跨层一致性模式                   │
  └──────────────┬───────────────────────┘
                 │
                 ▼
  ┌──────────────────────────────────────┐
  │ GATE 2: 深度模式检测                  │
  │ - 模式持续 >= 50 代? → 深层模式       │
  │ - 模式持续 10~49 代? → 中层模式       │
  │ - 模式持续 < 10 代? → 噪声，忽略      │
  └──────────────┬───────────────────────┘
                 │
                 ▼
  ┌──────────────────────────────────────┐
  │ GATE 3: 生成 L0 变更提案              │
  │ - 深层模式 → 核心 identity 微调提案    │
  │ - 中层模式 → 核心 rules 补充提案       │
  │ - 无深度模式 → 无变更，仅记录          │
  └──────────────┬───────────────────────┘
                 │
                 ▼
  ┌──────────────────────────────────────┐
  │ GATE 4: Merge 审批                    │
  │ - 提案提交到 Merge Agent              │
  │ - Merge 评估风险（与现有 L0 的矛盾）   │
  │ - 高风险 (>=0.7) → 拒绝，降级为 L1 提案│
  │ - 中风险 (0.3~0.7) → 需人工确认       │
  │ - 低风险 (<0.3) → 自动通过            │
  └──────────────┬───────────────────────┘
                 │ PASS
                 ▼
  ┌──────────────────────────────────────┐
  │ GATE 5: 执行 L0 修改                  │
  │ - 备份旧版 L0 到 L4/legacy/          │
  │ - 更新 L0/identity.md (如有变更)      │
  │ - 更新 L0/rules.md (如有变更)         │
  │ - 追加 L0/log.md 变更记录             │
  └──────────────┬───────────────────────┘
                 │
                 ▼
  ┌──────────────────────────────────────┐
  │ GATE 6: 触发全层传导                  │
  │ - L0→L1 传导（重评估所有行为签名）     │
  │ - L1→L2 传导（重评估所有分支规则）     │
  │ - L2→L3 传导（重评估当日优先级）       │
  │ - 传导窗口: 24 小时内完成             │
  └──────────────┬───────────────────────┘
                 │
                 ▼
  ┌──────────────────────────────────────┐
  │ GATE 7: 记录与广播                    │
  │ - state.md 更新 ETG 编号和时间        │
  │ - 记录到 L4/legacy/ 作为历史快照      │
  │ - 更新 team-status.json              │
  └──────────────────────────────────────┘

  RETURN etg_report
```

### 6.5 写前守恒检查流程

```
┌─────────────────────────────────────────────────────────────────┐
│              CONSERVATION CHECK (每次写操作前执行)                │
└─────────────────────────────────────────────────────────────────┘

FUNCTION conservation_check(layer, file, new_content):

  checks_passed = []
  checks_failed = []

  // CHECK 1: 三元组完整性
  //   验证 identity→rules→log 三个文件都存在且非空
  triad = [identity.md, rules.md, log.md]
  FOR EACH f IN triad:
    IF NOT FILE_EXISTS(layer + "/" + f):
      checks_failed.APPEND("missing triad: " + f)

  // CHECK 2: 因果链完整性
  //   identity 中声明的内容必须在 rules 中有对应条款
  identity_declarations = PARSE_IDENTITY(layer + "/identity.md")
  rules_coverage        = PARSE_RULES(layer + "/rules.md")

  FOR EACH decl IN identity_declarations.boundaries:
    IF decl NOT COVERED BY rules_coverage:
      checks_failed.APPEND("identity boundary not covered by rules: " + decl)

  // CHECK 3: 子层下界检查
  //   子层的规则强度不能低于父层规则定义的下界
  IF layer > L0:
    parent_floor = GET_RULES_FLOOR(layer.parent)
    new_rules_strength = EXTRACT_MIN_STRENGTH(new_content)
    IF new_rules_strength < parent_floor:
      checks_failed.APPEND("below parent floor: " +
        new_rules_strength + " < " + parent_floor)

  // CHECK 4: 棘轮检查
  //   不允许删除已有规则（只允许修改强度或标记为 deprecated）
  IF file == "rules.md":
    old_rules = PARSE_RULES(layer + "/rules.md")
    new_rules = PARSE_RULES(new_content)

    deleted = SET_DIFFERENCE(old_rules.ids, new_rules.ids)
    IF deleted is not empty:
      checks_failed.APPEND("ratchet violation: rules deleted: " + deleted)

  // CHECK 5: 冻结签名完整性（仅 L1）
  IF layer == L1 AND file IN {identity.md, rules.md}:
    frozen = READ L0/frozen-signatures.json
    FOR EACH sig IN frozen:
      IF sig.frozen == true:
        IF sig NOT PRESERVED IN new_content:
          checks_failed.APPEND("frozen signature modified: " + sig.id)

  // 返回结果
  IF checks_failed is empty:
    RETURN { pass: true, details: checks_passed }
  ELSE:
    RETURN { pass: false, failures: checks_failed }
```

---

## 7. 实现路线图

### Phase 1: 基础结构（第1-3天）

**目标**：建立分形目录结构，确保三元组同构。

- [ ] 创建 memory/ 根目录
- [ ] 创建 L0~L4 五层目录结构
- [ ] 为每层创建 identity.md、rules.md、log.md 模板
- [ ] 创建 memory/state.md 全局状态文件
- [ ] 创建 protocols/ 目录和协议模板文件
- [ ] 验证：每个层级的三元组文件俱在

### Phase 2: 写入协议（第4-7天）

**目标**：实现安全的写入机制。

- [ ] 实现写权限矩阵（谁可以写什么）
- [ ] 实现棘轮检查（不允许删除规则）
- [ ] 实现动态守恒检查（写前验证）
- [ ] 实现角色锁定检查（L2 occlusion-config）
- [ ] 实现写事件追加到 log.md
- [ ] 验证：尝试非法写入被正确拒绝

### Phase 3: 层间压缩（第8-12天）

**目标**：实现自底向上的信息压缩流。

- [ ] 实现 L3→L2 日总结压缩（每日触发）
- [ ] 实现 L2→L1 分支报告压缩（Audit 周期触发）
- [ ] 实现 L1→L0 核心提炼压缩（ETG 触发）
- [ ] 实现抗过拟合检查（抗Hebbian）
- [ ] 实现建设性噪声注入（5-10%）
- [ ] 验证：模拟 10 天的日志，验证压缩后的信息保真度

### Phase 4: 层间传导（第13-16天）

**目标**：实现自顶向下的规则传导。

- [ ] 实现 L0→L1 传导（核心变化重评估行为签名）
- [ ] 实现 L1→L2 传导（元规则变化更新分支下界）
- [ ] 实现 L2→L3 传导（分支策略变化重排日优先级）
- [ ] 实现传导超时机制（子层限时调整，超时冻结）
- [ ] 验证：触发一次 L0 修改，观察传导链是否正确传播

### Phase 5: 水平扩散（第17-20天）

**目标**：实现同层级的横向协同。

- [ ] 实现 L2 分支间收敛检测
- [ ] 实现 L2 分支距离度量（0.65米相变检查）
- [ ] 实现 L3 日间模式检测
- [ ] 实现收敛信号向 L1 的传递
- [ ] 验证：模拟 Alpha/Beta 独立得出相同结论，确认收敛被检测

### Phase 6: 启动协议（第21-24天）

**目标**：实现完整的 Bootstrap 流程。

- [ ] 实现全量 Bootstrap（冷启动）
- [ ] 实现轻量 Bootstrap（30分钟热恢复）
- [ ] 实现睡眠重放（随机核心记忆重放）
- [ ] 实现 Bootstrap 后的自动任务恢复
- [ ] 验证：断电后执行 Bootstrap，确认上下文恢复完整

### Phase 7: 集成测试（第25-28天）

**目标**：端到端验证整套分形记忆系统。

- [ ] 模拟 30 天连续运行
- [ ] 验证 L3→L2→L1→L0 压缩链完整
- [ ] 验证 L0→L1→L2→L3 传导链完整
- [ ] 验证跨会话上下文恢复准确率 >= 95%
- [ ] 验证建设性噪声保留率在 5-10%

---

## 附录 A: 术语表

| 术语 | 英文 | 定义 |
|:---|:---|:---|
| 三元组生成子 | Triad Generator | identity→rules→log 的三文件结构，分形的不变核 |
| 压缩 | Compression | 自底向上的信息蒸馏，每次上升一级信息量减少约 90% |
| 传导 | Conduction | 自顶向下的变化传播，核心层变化导致外层重评估 |
| 水平扩散 | Horizontal Diffusion | 同层实例之间的信息交换和协同 |
| 动态守恒 | Dynamic Conservation | 三元组的逻辑链不可断裂，结构比内容更稳定 |
| 棘轮效应 | Ratchet Effect | 规则一旦添加就不可删除，只能降权或标记 deprecated |
| 睡眠重放 | Sleep Replay | 每次启动时随机重放核心记忆，防止灾难性遗忘 |
| 建设性噪声 | Constructive Noise | 刻意保留的 5-10% 信息不对称，防止分支冗余 |
| 抗Hebbian | Anti-Hebbian | 对过度匹配的规则施加削弱，防止过拟合固化 |
| ETG | Evolution Trigger Gate | 约每 100 代触发一次的核心层提炼流程 |
| 相变距离 | Phase Transition Distance | 0.65 人类集体行为相变距离，映射为分支最优协作距离 |
| 角色锁定 | Role Occlusion | 分支对自己的某些权限进行永久封闭，保证角色稳定性 |

## 附录 B: 文件模板

### identity.md 模板

```markdown
# {层名} Identity

## 1. 我是谁
{一句话本体论声明}

## 2. 我的位置
- 层级: {L0/L1/L2/L3/L4}
- 父层: {parent_layer 或 "无（我是根）"}
- 子层: {child_layer 或 "无（我是叶）"}
- 分形金字塔中的角色: {一句话描述}

## 3. 我的时间尺度
- 变化频率: {季度/月/周/日/冻结}
- 上次修改: {timestamp}
- 下次预期修改: {timestamp 或 "不适用"}

## 4. 我的边界
### 我能做:
- {能力1}
- {能力2}

### 我不能做:
- {限制1}
- {限制2}

## 5. 当前状态
{当前活跃的声明/签名/策略列表}
```

### rules.md 模板

```markdown
# {层名} Rules

## 1. 上级规则引用
- 上位法: {parent_layer}/rules.md
- 下界约束: {从上层提取的最小规则强度}

## 2. 本级规则列表
| 编号 | 内容 | 强度 | 冻结 |
|:---|:---|:---|:---|
| {RULE-001} | {内容} | {0.0~1.0} | {true/false} |

## 3. 规则变更记录
| 时间 | 编号 | 操作 | 旧值 | 新值 | 原因 |
|:---|:---|:---|:---|:---|:---|
| {timestamp} | {id} | {modify/deprecate/add} | {old} | {new} | {reason} |

## 4. 子层约束
- 子层规则强度下界: {0.0~1.0}
- 子层不可覆盖的规则编号: {列表}
```

### log.md 模板

```markdown
# {层名} Log

## 1. 活跃周期
- Option 开始: {timestamp}
- 预期终止: {timestamp 或 条件描述}
- 状态: {active/completed/frozen}

## 2. 事件流
| 时间 | 类型 | 摘要 | 关联文件 |
|:---|:---|:---|:---|
| {timestamp} | {decision/anomaly/inspiration/session} | {摘要} | {路径} |

## 3. 关键决策
{本周期内的重要决策及其理由}

## 4. 待向上压缩
- [ ] {条目1} — 准备传递给 {parent_layer}
- [ ] {条目2} — 等待 {condition}
```

---

> 本方案由 Colony-002（极限实验室子Agent）设计完成。
> 理论依据：分形几何（Mandelbrot），胚胎表观基因组自组织（Munich LMU, Nature Physics 2026），层级强化学习 Options 框架（Sutton, Precup & Singh）。
> 设计原则：文件系统级别可落地，不依赖数据库或外部服务，仅需文件读写能力。
