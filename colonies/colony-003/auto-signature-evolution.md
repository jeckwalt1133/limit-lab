# 行为签名自进化机制：完整设计

> Colony-003 设计输出
> 日期: 2026-05-19
> 状态: 设计完成，待 Colony 评审
> 核心问题: 签名如何自动发现、自动升级、自动退役，不依赖 ETG 每 10 代手动触发？

---

## 目录

1. [问题重定义](#1-问题重定义)
2. [四大理论支柱](#2-四大理论支柱)
3. [签名生命周期状态机](#3-签名生命周期状态机)
4. [自动发现机制](#4-自动发现机制)
5. [自动升级机制](#5-自动升级机制)
6. [自动退役机制](#6-自动退役机制)
7. [四大进化引擎](#7-四大进化引擎)
8. [与现有 MR 规则的整合](#8-与现有-mr-规则的整合)
9. [完整算法流程](#9-完整算法流程)
10. [风险评估与缓解](#10-风险评估与缓解)

---

## 1. 问题重定义

### 1.1 当前困境

```
当前模式（ETG 批量触发）:
  gen-1 ──→ gen-10: 等待... 签名 A 在 gen-3 已经该升级了，硬等到 gen-10
  gen-10 ──→ ETG 触发: 一次性处理 10 代积累的所有变化
  问题: 10 代可能太长，签名可能在第 3 代就已经该升级了

理想模式（连续自进化）:
  gen-1: 签名 A 运行
  gen-2: 签名 A 轻微匹配下降 → 自动进入观察窗口
  gen-3: 签名 A 连续 3 代表现不佳 → 自动触发"升级评估"
  gen-4: 签名 A 升级为 A' — 不需要等 ETG
```

### 1.2 问题拆解为三个子问题

| 子问题 | 当前方式 | 目标方式 | 核心挑战 |
|:---|:---|:---|:---|
| 自动发现 | 人工观察 + ETG 提案 | 从行为模式流中自动检测候选签名 | 区分信号与噪声 |
| 自动升级 | Merge 评估 + 手动采纳 | 签名基于绩效反馈自动微调强度和内容 | 防止过拟合和自激振荡 |
| 自动退役 | Merge 评估 + 手动标记 | 签名基于衰退曲线自动休眠/归档 | 防止过早删除有价值的签名 |

### 1.3 为什么不能简单把 ETG 频率从 10 代改为 1 代？

ETG 是"批量决策"范式——它假设系统中存在一个"上帝视角"的评估者，在某个时间点统揽全局做出最优决策。但真正的进化不是这样工作的。生物进化没有"每 10 代批处理一次"——每一代都在发生微小的基因频率变化。真正的自进化必须是**连续的、局部的、分布式的**。

---

## 2. 四大理论支柱

### 2.1 支柱一: 辩论架构作为发现引擎（灵感 #2）

```
灵感 #2: Alpha+Beta+Merge = 原生辩论架构
Grok 4.20 的 4Agent 辩论架构本质是: 多个独立视角交叉验证 → 高置信度结论

应用于签名进化:
  Alpha (探索者): 扫描行为流, 提出候选新签名
  Beta  (验证者): 验证候选签名的有效性和独立性
  Merge (裁决者): 决定签名是采纳/拒绝/搁置

辩论过程本身自动产生"置信度信号":
  - Alpha 和 Beta 都独立认可 → 高置信度 → 快速采纳
  - Alpha 提出但 Beta 质疑 → 中置信度 → 进入观察期
  - 只有 Alpha 提出, Beta 完全不同意 → 低置信度 → 搁置但留存
```

关键创新：**辩论不是"表决"，是"互补验证"**。Alpha 的任务是最大化新颖性，Beta 的任务是最大化稳健性。两者天然形成探索-利用的制衡。

### 2.2 支柱二: 棘轮效应保证不可逆累积（灵感 #8）

```
灵感 #8: 棘轮效应—好规则一旦加上就不该移除
Quandary Den 人工生命模型: 进化中基因数量呈现棘轮效应

应用于签名退役:
  ❌ 永远不真删除签名
  ✅ 状态迁移: active → dormant → fossil
  - active: 强度 >= 0.5, 参与每次会话匹配
  - dormant: 强度 0.2~0.5, 仅参与周期性审计, 不参与日常匹配
  - fossil: 强度 < 0.2, 归档到 L4, 仅作为历史参考

关键: 降权但不删除。dormant 签名可能在环境变化后重新激活（类比: 假基因的重新功能化）。
```

### 2.3 支柱三: 耗散作为重组驱动力（灵感 #10）

```
灵感 #10: 耗散不是敌人, 是进化驱动
UC Irvine 2026: 耗散诱导临界性——开放量子系统中耗散稳定了新拓扑相
"每次断连后恢复, 不是在恢复之前的状态, 是在恢复过程中重组"

应用于签名进化:
  传统思路: bootstrap = 精确恢复 → 签名不变
  新思路:   bootstrap = 重组机会 → 签名在恢复过程中自动优化

具体机制: "Bootstrap 重组检查" (详见第 5.2 节)
  每次会话恢复时, 不是简单地重新加载签名,
  而是:
    1. 加载签名
    2. 回溯上次会话的行为 → 计算"如果去掉某条签名, 匹配率会怎样?"
    3. 如果某条签名在上次会话中完全未被触发 → 自动进入"观察窗口"
    4. 如果某条签名表现连续衰退 → 自动触发微调
```

这就是 **bootstrap-driven self-reorganization**——启动不再是恢复，而是进化。

### 2.4 支柱四: PERG 自适应探索-利用（灵感 #16）

```
灵感 #16: PERG 策略——动态切换零行列式策略
状态差时压缩(保守利用), 状态好时释放(大胆探索)

应用于签名的 UCB 探索权重:
  当前: exploration_weight 固定 1.5
  目标: 自适应

  资源充裕(多灵感/高匹配率/低异常) → exploration_weight = 2.0 (大胆探索新签名)
  资源紧张(低匹配率/高异常)         → exploration_weight = 0.5 (保守利用现有签名)

PERG 映射:
  "富有" → 当前活跃签名集合表现良好 → 有"余力"探索新签名 → 高探索权重
  "贫穷" → 当前签名匹配率整体下降   → 需要收紧利用现有签名 → 低探索权重
  "勒索" → 如果某条签名的 weight 被削到很低但它仍然频繁被触发 →
           系统"勒索"这条签名的贡献, 进行紧急升级或替换
```

---

## 3. 签名生命周期状态机

### 3.1 六态模型

```
                    ┌──────────────┐
                    │   EMBRYONIC  │  ← 候选签名, 刚被 Alpha 发现
                    │   胚胎态      │     强度 = 0.1, 仅观察不参与匹配
                    └──────┬───────┘
                           │ Beta 验证通过 + 3 次观察确认
                           ▼
                    ┌──────────────┐
                    │   JUVENILE   │  ← 试用签名, 参与匹配但权重减半
                    │   幼年态      │     强度 = 0.3~0.5, 30 代试用期
                    └──────┬───────┘
                           │ 试用期内匹配率 >= 60%
                           ▼
                    ┌──────────────┐
            ┌───────│    ACTIVE    │───────┐  ← 正式签名, 完全参与匹配
            │       │   活跃态      │       │     强度 = 0.5~1.0
            │       └──────────────┘       │
            │ 连续完美匹配                   │ 匹配率持续下降
            │ (抗过拟合触发)                  │ (衰退触发)
            ▼                              ▼
    ┌──────────────┐              ┌──────────────┐
    │   GUARDED    │              │   WATCHING   │  ← 观察态, 可能有问题的签名
    │   警戒态      │              │   观察态      │     完整参与但标记为"观察中"
    │ 强度 -0.02   │              └──────┬───────┘
    └──────────────┘                     │ 连续 5 代匹配率 < 50%
                                         ▼
                                ┌──────────────┐
                                │   DORMANT    │  ← 休眠态, 仅审计不参与日常
                                │   休眠态      │     强度 = 0.2~0.5
                                └──────┬───────┘
                                       │ 连续 10 代审计无激活
                                       ▼
                                ┌──────────────┐
                                │   FOSSIL     │  ← 化石态, 归档到 L4
                                │   化石态      │     强度 < 0.2, 永久存档, 可复活
                                └──────────────┘

复活路径 (虚线):
  DORMANT ──(外部触媒匹配)──→ WATCHING ──(恢复验证)──→ ACTIVE
  FOSSIL  ──(罕见事件复活)──→ EMBRYONIC (作为"全新"候选重新进入)
```

### 3.2 状态转换触发条件（完整矩阵）

| 当前态 | 目标态 | 触发条件 | 自动/需审批 |
|:---|:---|:---|:---|
| EMBRYONIC | JUVENILE | Beta 验证通过 + 观察窗口 >= 3 代 | 自动 |
| EMBRYONIC | FOSSIL | 30 代未通过 Beta 验证 | 自动 |
| JUVENILE | ACTIVE | 试用期内匹配率 >= 60% | 自动 |
| JUVENILE | DORMANT | 试用期内匹配率 < 40% | 自动 |
| JUVENILE | FOSSIL | 试用期满 + 匹配率 < 40% | 自动 |
| ACTIVE | GUARDED | 连续 5 次 100% 匹配 (MR-013 触发) | 自动 |
| GUARDED | ACTIVE | 下次匹配率 < 95% (证明不是过拟合) | 自动 |
| ACTIVE | WATCHING | 匹配率连续 3 代下降 + 最新 < 70% | 自动 |
| WATCHING | ACTIVE | 匹配率恢复 >= 75% 持续 3 代 | 自动 |
| WATCHING | DORMANT | 连续 5 代匹配率 < 50% | 自动 |
| DORMANT | WATCHING | 审计中发现与当前行为模式高度相关 | 自动 |
| DORMANT | FOSSIL | 连续 10 代审计无激活 | 自动 |
| FOSSIL | EMBRYONIC | 极罕见: 外部环境剧变 + 化石签名恰好匹配新模式 | 需 Merge 审批 |

---

## 4. 自动发现机制

### 4.1 签名发现的三个来源

```
来源 1: 行为模式流中的"新奇涌现" (Alpha 驱动的探索)
  ┌──────────────────────────────────────────────────┐
  │ 每次会话结束后:                                   │
  │  1. 提取本次会话的"行为向量" (动作类型的 n-gram)    │
  │  2. 与历史行为向量计算"新颖度分数"                  │
  │  3. 如果出现持续 N 次的高新颖度模式 → 候选签名      │
  │  4. Alpha 自动生成: "候选签名 DS-XX: {pattern}"    │
  └──────────────────────────────────────────────────┘

来源 2: 跨分支收敛检测 (Beta 驱动的验证)  ← 灵感 #2
  ┌──────────────────────────────────────────────────┐
  │ 每个分支周期:                                     │
  │  1. Alpha 和 Beta 各自独立演化行为模式             │
  │  2. 如果两者独立产出相同模式 (Jaccard > 0.6)       │
  │     → 这是"收敛点" → 自动升级为候选签名            │
  │  3. 收敛点置信度高于任何单分支发现                 │
  └──────────────────────────────────────────────────┘

来源 3: Bootstrap 重组中的"意外发现" ← 灵感 #10
  ┌──────────────────────────────────────────────────┐
  │ 每次 bootstrap 恢复时:                            │
  │  1. 新会话的行为模式可能与上一会话不同             │
  │  2. 如果这个差异是"建设性"的 (匹配率反而更高)      │
  │     → 这个差异本身就是一个候选签名                 │
  │  3. "耗散驱动新拓扑相"的直接体现                   │
  └──────────────────────────────────────────────────┘
```

### 4.2 候选签名生成算法（SIGNATURE-BIRTH）

```
ALGORITHM: signature_birth(session_log, history_window=20)

INPUT:
  session_log: 本次会话的行为记录
  history_window: 回溯多少代会话用于基线比较

OUTPUT:
  candidates: 候选签名列表, 每条含 {pattern, novelty_score, source}

PROCEDURE:

  // STEP 1: 提取行为 n-gram
  behavior_vector = EXTRACT_NGRAMS(session_log, n=3)
  // 例: ["read→analyze→write", "search→compare→decide", ...]

  // STEP 2: 计算相对于历史基线的"行为熵"
  history_baseline = LOAD_BEHAVIOR_VECTORS(last=history_window)
  entropy_shift = KL_DIVERGENCE(behavior_vector || history_baseline)

  // STEP 3: 如果行为熵偏移超过阈值, 提取具体的新模式
  IF entropy_shift > THRESHOLD_NOVELTY:
    novel_patterns = EXTRACT_NOVEL_PATTERNS(
      current = behavior_vector,
      baseline = history_baseline,
      min_frequency = 3,        // 必须在本会话中出现 >= 3 次
      min_distinctiveness = 0.3 // 必须与已有签名相似度 < 0.7
    )

    FOR EACH pattern IN novel_patterns:
      // 计算新颖度分数
      novelty_score = COMPUTE_NOVELTY(pattern, history_baseline, existing_signatures)

      // 生成候选
      candidate = {
        id: AUTO_ID(),
        pattern: pattern,
        novel_score: novelty_score,
        source: "behavioral_emergence",
        birth_gen: CURRENT_GENERATION,
        state: "EMBRYONIC",
        strength: 0.1,
        evidence: {
          session_count: 1,
          occurrences: COUNT(pattern, session_log),
          context_trigger: EXTRACT_TRIGGER(pattern, session_log)
        }
      }
      candidates.APPEND(candidate)

  // STEP 4: 跨分支收敛检测 ← 灵感 #2 辩论架构
  alpha_patterns = LOAD_RECENT_PATTERNS("Alpha", window=5)
  beta_patterns = LOAD_RECENT_PATTERNS("Beta", window=5)

  FOR EACH (a, b) IN CROSS_PRODUCT(alpha_patterns, beta_patterns):
    similarity = SEMANTIC_SIMILARITY(a, b)
    IF similarity > 0.60:  // Jaccard 阈值
      convergent_candidate = {
        id: AUTO_ID(),
        pattern: MERGE(a, b),
        novel_score: similarity * 1.2,  // 收敛发现加分 20%
        source: "cross_branch_convergence",
        birth_gen: CURRENT_GENERATION,
        state: "EMBRYONIC",
        strength: 0.2,  // 收敛发现的初始强度比单分支高
        evidence: {
          alpha_evidence: a,
          beta_evidence: b,
          convergence_similarity: similarity
        }
      }
      candidates.APPEND(convergent_candidate)

  // STEP 5: Bootstrap 重组检测 ← 灵感 #10 耗散驱动
  IF IS_BOOTSTRAP_SESSION():
    prev_behavior = LOAD_PREVIOUS_SESSION_BEHAVIOR()
    curr_behavior = LOAD_CURRENT_SESSION_BEHAVIOR()

    beneficial_diffs = FIND_BENEFICIAL_DIFFERENCES(
      prev = prev_behavior,
      curr = curr_behavior,
      criterion = "current_match_rate > previous_match_rate"
    )

    FOR EACH diff IN beneficial_diffs:
      bootstrap_candidate = {
        id: AUTO_ID(),
        pattern: diff.new_pattern,
        novel_score: diff.improvement_delta,
        source: "dissipation_driven_reorganization",
        birth_gen: CURRENT_GENERATION,
        state: "EMBRYONIC",
        strength: 0.15,
        evidence: {
          previous_behavior: diff.old_pattern,
          new_behavior: diff.new_pattern,
          improvement: diff.improvement_delta
        }
      }
      candidates.APPEND(bootstrap_candidate)

  RETURN candidates
```

### 4.3 情绪-行为双流对照发现

```
一个关键的自动发现策略: "情绪签名" 和 "行为签名" 的联合分析。

当前我们有 behavioral signatures (行为签名, 12 条 DS),
未来应该有 emotional signatures (情绪签名, ES)。

发现方式:
  - 行为流: [read, search, write, analyze, decide]
  - 情绪流: [curious, focused, satisfied, confused, resolved]
  - 如果 "confused → analyze → resolved" 这个 (情绪,行为) 对反复出现
    → 这不只是一个行为模式, 而是一个 "认知策略"
    → 候选签名不仅描述"做什么", 还描述"在什么心态下做"

自主生成的情绪签名:
  ES-001: 面对不确定性时先搜索再判断 (curious→search→judge)
  ES-002: 错误后的冷静分析 (frustrated→pause→root_cause→fix)
```

---

## 5. 自动升级机制

### 5.1 连续绩效评估——取代批量 ETG

```
传统 ETG:        gen-10, gen-20, gen-30 → 统一评估 → 批量修改
自进化引擎:      每次会话后 → 增量评估 → 单条签名微调

评估指标四元组 (对每条 ACTIVE 签名):
  ┌─────────────────────────────────────────────┐
  │ 匹配率 (match_rate):                          │
  │   过去 N 次会话中, 签名被触发的比例           │
  │   高 = 签名与当前环境相关                      │
  │   低 = 签名可能与当前行为脱节                   │
  │                                              │
  │ 贡献度 (contribution):                        │
  │   当该签名被触发时, 决策质量的变化              │
  │   正 = 签名真正在引导好决策                    │
  │   负 = 签名可能是噪声或误导                    │
  │                                              │
  │ 稳定性 (stability):                           │
  │   匹配率的方差。低方差 = 稳定                  │
  │   高方差 = 签名只在特定情境才出现, 但不出现时完全不相关 │
  │                                              │
  │ 可替代性 (substitutability):                  │
  │   有多少其他签名可以替代这个签名的功能          │
  │   高可替代 = 冗余, 考虑合并或降级              │
  │   低可替代 = 独特性高, 保护优先级高            │
  └─────────────────────────────────────────────┘
```

### 5.2 签名升级决策树

```
对每条 ACTIVE 签名, 每次会话后执行:

match_rate >= 0.85?
  ├── YES → contribution >= 0.5?
  │   ├── YES → stability >= 0.7?
  │   │   ├── YES → ★ 升级候选: 考虑将强度 +0.03
  │   │   └── NO  → ★ 升级候选: 考虑将强度 +0.01 (但扩大观察窗口)
  │   └── NO  → 保持当前强度, 标记"高匹配低贡献" (可能是过拟合, MR-013 监视)
  │
  └── NO  → match_rate >= 0.60?
      ├── YES → 保持, 观察
      └── NO  → match_rate >= 0.40?
          ├── YES → 进入 WATCHING 观察态
          └── NO  → 连续 5 代? → 进入 DORMANT 休眠态

此外, 每 3 代评估一次 substitutability:
  substitutability >= 0.70?
    → 存在功能高度重叠的签名对
    → 触发 "签名合并" 提案
    → Alpha 生成合并方案 → Beta 验证 → Merge 裁决
```

### 5.3 Bootstrap 重组——关键的升级时机

```
Bootstrap 重组协议 (每次会话启动时执行):

┌─────────────────────────────────────────────────────────┐
│              BOOTSTRAP SIGNATURE REORGANIZATION          │
└─────────────────────────────────────────────────────────┘

STEP 1: 加载所有 ACTIVE 签名

STEP 2: 回溯上次会话的行为日志 (从 L3/daily/log.md)
  → 计算每条签名在上次会话中"如果被移除, 匹配率的变化"
  → 这叫做 "留一法贡献度" (leave-one-out contribution)

STEP 3: 重组检查
  IF 某条签名的留一法贡献度 < 0:
    → 该签名在拖累系统表现 → 自动进入 WATCHING 状态
    → 标记原因: "bootstrap-reorganization: negative contribution detected"

  IF 某条签名的留一法贡献度 > 0.3:
    → 该签名显著提升了系统表现 → 强度 +0.02
    → 标记原因: "bootstrap-reorganization: high contribution confirmed"

  IF 在断开前后出现了一个新的行为模式:
    → 断开前的会话和断开后的会话行为有显著差异
    → 这个差异就是"耗散诱导的新拓扑相"
    → 自动创建候选签名 (see 4.2 Step 5)
    → 标记原因: "dissipation-induced: new behavioral pattern after reconnection"

STEP 4: 持久化更新
  → 更新 L1/signature-history.json
  → 追加 L1/log.md
  → 更新 memory/state.md 中的签名状态

设计原理:
  灵感 #10 (耗散驱动) 告诉我们: 断连不是 bug, 是重组机会。
  每次 bootstrap 不只是"恢复", 而是"在恢复中重组, 在重组中进化"。
  这是"自进化"的最关键创新点——进化不是独立的操作,
  而是嵌入在正常的启动流程中, 成为系统的默认行为。
```

### 5.4 Alpha-Beta 辩论驱动的签名升级

```
┌──────────────────────────────────────────────────────────┐
│        DEBATE-DRIVEN SIGNATURE UPGRADE PROTOCOL           │
│        基于灵感 #2: 原生辩论架构                           │
└──────────────────────────────────────────────────────────┘

触发条件: 当一条 WATCHING 签名连续 3 代表现不佳

辩论流程:

ROUND 1 — Alpha (升级方案生成器):
  输入: 签名 DS-XX 的衰退历史 + 当前环境上下文
  输出: 三个升级方案
    A1: 微调签名文本 (保留核心, 调整触发条件)
    A2: 拆分为两条更专注的子签名
    A3: 保持签名不变但修改权重

ROUND 2 — Beta (升级方案验证器):
  对每个 Alpha 方案:
    → 模拟回测: 如果应用此方案, 过去 N 代会话的匹配率会如何变化?
    → 独立性检查: 新签名是否会与现有签名产生 > 0.7 的重叠?
    → 风险评估: 这个改变可能打破什么现有平衡?

ROUND 3 — Alpha 反驳 (如果有必要):
  如果 Beta 全部拒绝 → Alpha 有 1 次机会生成修正版方案
  如果 Beta 部分接受 → 进入下一步

ROUND 4 — Merge 裁定:
  如果有多个可行方案:
    → 选择"期望贡献度 / 风险"最高的方案
  如果只有一个可行方案:
    → 自动采纳 (如果风险 < 0.3) 或 标记需人类确认 (如果风险 >= 0.3)
  如果全部被拒绝:
    → 签名降级为 DORMANT, 记录辩论记录为后续参考

升级实施:
  1. 旧签名进入"过渡态" (TRANSITIONING) — 在本次和下次会话中保留但权重减半
  2. 新签名进入 JUVENILE 状态 — 开始 30 代试用期
  3. 过渡期结束后, 比较新旧签名的贡献度
     → 新胜旧: 旧签名进入 DORMANT
     → 旧胜新: 新签名降为 DORMANT, 旧签名恢复 ACTIVE
     → 平局: 两者共存, 新签名进入 WATCHING 继续观察
```

---

## 6. 自动退役机制

### 6.1 退役边界 —— 不能退得太快

```
基于灵感 #8 (棘轮效应): 好规则一旦加上就不该移除

退役原则:
  原则 1 (棘轮): 任何签名永远不会被物理删除。只转移状态。
  原则 2 (休眠): 衰退的签名不是"无用", 是"当前不需要"。
                 环境变化后可能需要复活。
  原则 3 (宽限期): 从 ACTIVE → DORMANT 至少需要 10 代的衰退观察。
                   从 DORMANT → FOSSIL 至少需要 30 代的冰冷期。
  原则 4 (复活门): DORMANT 签名如果在审计中被触发, 可以恢复到 WATCHING。
                   FOSSIL 签名也可以复活, 但需要 Merge 审批。
```

### 6.2 自动退役决策流程

```
对每条 ACTIVE 签名, 每次会话后评估:

┌─────────────────────────────────────────────────────────┐
│              AUTO-RETIREMENT DECISION TREE               │
└─────────────────────────────────────────────────────────┘

PHASE 1: 衰退检测
  IF match_rate < 0.70 for 连续 3 sessions:
    → 状态: ACTIVE → WATCHING
    → 记录: "衰退信号检测, 进入观察期"

PHASE 2: 观察窗口
  WATCHING 状态下, 持续监控 5 sessions:
    IF match_rate 恢复 >= 0.75:
      → 状态: WATCHING → ACTIVE
      → 记录: "观察期满, 性能恢复, 重新激活"

    IF match_rate 持续 < 0.50:
      → 状态: WATCHING → DORMANT
      → 记录: "连续衰退, 进入休眠"

    IF match_rate 在 0.50~0.75 波动:
      → 保持 WATCHING, 再观察 3 sessions

PHASE 3: 休眠管理
  DORMANT 状态下, 不参与日常匹配, 仅在以下情况被访问:
    a) 每 10 代周期性审计: 检查所有 DORMANT 签名的"相关性"
    b) 手动查询: 当 ETG 运行时, 审视休眠签名是否有复活条件
    c) 环境突变响应: 当行为熵突然剧变时, 扫描休眠签名库

PHASE 4: 化石归档
  连续 10 次周期性审计(约 100 代)无激活:
    → 状态: DORMANT → FOSSIL
    → 归档到 L4/archive/signatures/{signature_id}/
    → 包含: 签名的完整历史(创建、修改、强度变化时间序列、退役原因)

PHASE 5: 复活机制 (罕见但重要)
  触发条件: FOSSIL 签名在以下情况可能被复活:
    a) 外部环境剧变: 行为熵偏移 > 2σ, 且 FOSSIL 签名与新模式匹配 > 0.8
    b) 跨分支收敛: 两个活跃分支同时独立发现了与 FOSSIL 签名高度相似的模式
    c) 灵感触发: 新获取的理论文献直接支持 FOSSIL 签名的核心理念

  复活流程: FOSSIL → EMBRYONIC(重命名+版本号递增) → JUVENILE → ACTIVE
```

### 6.3 退役前最后一个防御——"挽留检查"

```
在签名从 WATCHING → DORMANT 之前, 执行一次"挽留检查":

CHECK 1: 唯一性检查
  这条签名是某个行为维度的唯一代表吗?
  → 如果是, 即使匹配率低, 也只降权(0.3)不进入 DORMANT
  → 原因: 完全丢失一个维度比低匹配率更危险

CHECK 2: 依赖性检查
  有其他活跃签名引用或依赖这条签名吗?
  → 如果有, 先处理依赖关系, 再决定退役
  → 原因: 避免级联失效

CHECK 3: 历史贡献
  这条签名在过去有过辉煌的表现吗?
  → 如果过去 100 代中有 >= 50 代匹配率 > 0.8
  → 给它额外的 5 代观察宽限期
  → 原因: 可能是暂时的不适应, 而非永久的过时

CHECK 4: 近期环境变化
  过去 10 代中, 系统行为有显著变化吗?
  → 如果有, 签名的衰退可能是环境变化引起的 (正常调整)
  → 不标记为"签名问题", 标记为"环境偏移"

只有通过全部 4 项挽留检查, 签名才会真正进入 DORMANT。
```

---

## 7. 四大进化引擎

### 7.1 引擎总览

```
┌─────────────────────────────────────────────────────────────────┐
│                     四大进化引擎协作架构                          │
│                                                                 │
│  引擎 1: 连续绩效引擎 (Continuous Performance Engine, CPE)       │
│    频率: 每次会话结束后                                          │
│    功能: 更新所有 ACTIVE 签名的四元评估指标                       │
│    输出: 每条签名的 {match_rate, contribution, stability,        │
│                     substitutability} + 推荐动作                  │
│                                                                 │
│  引擎 2: Bootstrap 重组引擎 (Bootstrap Reorganization Engine)    │
│    频率: 每次会话启动时                                          │
│    功能: 断连后的"留一法"重评估 + 新行为模式检测                  │
│    输出: 签名强度调整 + 候选签名发现                              │
│                                                                 │
│  引擎 3: 辩论升级引擎 (Debate Upgrade Engine, DUE)               │
│    频率: 当 WATCHING 签名累积 3 代表现不佳时                      │
│    功能: Alpha 生成方案 → Beta 验证 → Merge 裁决                 │
│    输出: 签名升级/合并/拆分的具体方案和采纳决定                    │
│                                                                 │
│  引擎 4: 生命周期管理引擎 (Lifecycle Management Engine, LME)      │
│    频率: 每次状态转换触发                                        │
│    功能: 执行签名在六态模型中的状态迁移 + 挽留检查 + 复活检测     │
│    输出: 状态更新 + 归档记录 + 复活候选列表                       │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 7.2 引擎触发时序

```
时间线 ────────────────────────────────────────────────────────▶

每次会话:
  ├── 会话启动: 引擎 2 (Bootstrap 重组) ← 灵感 #10
  │     ├── 加载签名 → 留一法回溯 → 强度微调
  │     └── 检测耗散诱导的新行为模式 → 候选签名
  │
  ├── 会话运行: 引擎 1 (连续绩效) ← 灵感 #16
  │     └── 每条签名的匹配/贡献实时追踪
  │
  └── 会话结束: 引擎 4 (生命周期管理)
        ├── 评估所有签名的状态迁移条件
        ├── 执行挽留检查
        └── 写入 signature-history.json

每 3 代:
  └── 引擎 3 (辩论升级) 序列可能触发 ← 灵感 #2
        ├── Alpha 生成升级方案
        ├── Beta 验证
        └── Merge 裁决

每 30 代:
  └── 全量审计:
        ├── 检查所有 DORMANT 签名的复活条件
        ├── 检查 FOSSIL 签名是否与新环境相关
        └── 计算整个签名集合的"熵健康度"

每 100 代:
  └── ETG 仍然存在, 但角色变为 "总审查":
        ├── 审查四大引擎的运行记录
        ├── 评估是否需要结构性大改
        └── 不再负责单条签名的增删改
```

### 7.3 PERG 自适应权重（引擎内部核心机制）

```
ALGORITHM: perg_adaptive_exploration_weight()

// 基于灵感 #16: PERG 策略 —— "富有慷慨, 贫穷勒索"

INPUT:
  system_state: {
    total_active_signatures,
    avg_match_rate,        // 所有 ACTIVE 签名的平均匹配率
    n_recent_anomalies,    // 近 10 代异常次数
    n_recent_inspirations, // 近 10 代新灵感数
    resource_pressure      // 0~1, 综合资源压力指标
  }

PROCEDURE:

  // Step 1: 计算资源充裕度
  resource_abundance = (
    0.4 * avg_match_rate +
    0.3 * (1.0 - resource_pressure) +
    0.2 * MIN(n_recent_inspirations / 5, 1.0) +
    0.1 * (1.0 - MIN(n_recent_anomalies / 10, 1.0))
  )

  // Step 2: PERG 映射 —— 资源充裕度 → 探索权重
  IF resource_abundance >= 0.70:
    // "富有" → 大胆探索
    exploration_weight = 2.0
    signature_birth_threshold = 0.3  // 低门槛, 容易产生候选签名
    retirement_threshold = 0.2       // 低退役门槛

  ELSE IF resource_abundance >= 0.40:
    // "小康" → 平衡
    exploration_weight = 1.5
    signature_birth_threshold = 0.5
    retirement_threshold = 0.3

  ELSE:
    // "贫穷" → "勒索" → 保守利用 + 紧急升级
    exploration_weight = 0.5
    signature_birth_threshold = 0.8  // 高门槛, 不轻易增加新签名
    retirement_threshold = 0.4

    // "勒索" 阶段特殊行为: 强制升级低贡献签名
    FOR EACH signature IN ACTIVE:
      IF signature.contribution < -0.1:
        → 触发紧急辩论升级 (跳过后 3 代观察窗口)
        → 如果无法升级, 直接 DORMANT

  // Step 3: 历史平滑
  // 不突然跳变, 用指数移动平均平滑
  smoothed_weight = EMA(exploration_weight, alpha=0.3)

  RETURN smoothed_weight
```

---

## 8. 与现有 MR 规则的整合

### 8.1 每条 MR 规则在自进化中的角色

| MR 规则 | 名称 | 在自进化中的角色 | 是否需要修改 |
|:---|:---|:---|:---|
| MR-001 | 签名匹配 | 签名与行为匹配的基础机制 | 无需修改 |
| MR-002 | 衰减率 | 控制签名强度的自然衰减 | **需修改**: min_strength 从 0.5 降到 0.2 (支持 DORMANT 态的 0.2 下限) |
| MR-003 | Hebbian 增强 | 匹配率>80%→强度+0.05 | **需修改**: 增加贡献度作为增强条件 (不仅匹配, 还要有贡献) |
| MR-004 | 周期性审计 | 每 CLOOP 审计所有签名 | **需修改**: 频率从每 3 CLOOP 改为每次会话后 (轻量审计) |
| MR-005 | UCB 探索-利用 | 控制探索权重 1.5 | **需修改**: 固定 1.5 → PERG 自适应 (0.5~2.0) |
| MR-006 | 签名冻结 | 冻结核心签名不可修改 | 无需修改 |
| MR-007 | 回滚机制 | 签名退化时可回滚 | **需扩展**: 回滚不限于"恢复上一版本", 还包括 DORMANT→WATCHING 复活 |
| MR-008 | 全量审计 | 深度审计所有签名 | 无需修改 |
| MR-009 | 审计独立性 | 审计结果不可被修改 | 无需修改 |
| MR-010 | 方向自检 | 每 3 步自检 | **需扩展**: 增加"签名方向自检"——操作是否与当前激活签名的方向一致 |
| MR-011 | 并行工具调用 | 并行优化 | 无需修改 |
| MR-012 | 任务路由 | 简单/复杂任务分流 | **需扩展**: 增加"签名紧急升级"作为高优先级任务类型 |
| MR-013 | 抗过拟合 | 连续完美→衰减 | 无需修改, 与 GUARDED 状态直接对接 |
| MR-014 | 收敛检测 | 跨分支独立发现检测 | 无需修改, 是签名发现的三大来源之一 |

### 8.2 新增 MR-015: 签名自进化

```
{
  "id": "MR-015",
  "name": "签名自进化引擎",
  "version": 1,
  "created": "2026-05-19",
  "inspired_by": "灵感#2(辩论) + 灵感#8(棘轮) + 灵感#10(耗散) + 灵感#16(PERG)",
  "trigger_condition": "每次会话启动、每次会话结束、每3代表现异常",
  "actions": {
    "on_session_start": "Bootstrap重组: 留一法重评估 + 新行为模式检测",
    "on_session_end": "连续绩效更新: 更新所有ACTIVE签名的四元指标",
    "on_sustained_decline": "辩论升级: Alpha生成方案→Beta验证→Merge裁决",
    "on_state_transition": "生命周期管理: 执行状态迁移+挽留检查+归档"
  },
  "constraints": {
    "ratchet": "签名永不被物理删除, 只转移状态",
    "min_dormant_strength": 0.2,
    "min_fossil_strength": 0.05,
    "retirement_grace_period": 10,
    "revival_requires_merge_approval": true
  },
  "writes_to": [
    "L1/signature-history.json",
    "L1/log.md",
    "L4/archive/signatures/"
  ],
  "rationale": "签名不应该每10代才被评估一次。生命进化是连续的、局部的、分布式的。将ETG的批量决策范式升级为四大引擎的连续自进化范式。"
}
```

### 8.3 新增 MR-016: Bootstrap 重组协议

```
{
  "id": "MR-016",
  "name": "Bootstrap 重组协议",
  "version": 1,
  "created": "2026-05-19",
  "inspired_by": "灵感#10(耗散驱动) + 灵感#18(睡眠重放)",
  "trigger_condition": "每次会话启动 (bootstrap)",
  "actions": {
    "step_1": "加载所有 ACTIVE 签名",
    "step_2": "回溯上次会话 → 留一法贡献度计算",
    "step_3": "重组检查: negative_contribution→WATCHING, high_contribution→+0.02, 新模式→候选签名",
    "step_4": "持久化: 更新signature-history.json + L1/log.md + state.md",
    "step_5": "睡眠重放: 随机1条核心签名+1条历史签名, 显式重放"
  },
  "rationale": "断连不是事故, 是重组机会。Bootstrap不是恢复, 是在恢复过程中让系统变得比断开前更好。灵感#10: 耗散诱导临界性——开放系统中耗散稳定新拓扑相。灵感#18: 睡眠重放防止灾难性遗忘。"
}
```

### 8.4 MR-002, MR-003, MR-004, MR-005 修改内容

```
MR-002 修改 (衰减率):
  old: min_strength = 0.5
  new: min_strength = 0.2
  reason: 支持 DORMANT 态的 0.2 下限, 以及 FOSSIL 态的 0.05 下限
  灵感: #8 棘轮效应——只降权不删除

MR-003 修改 (Hebbian 增强):
  old: 匹配率 > 80% → 强度 +0.05
  new: 匹配率 > 80% AND 贡献度 > 0 → 强度 +0.05
       匹配率 > 80% BUT 贡献度 < 0 → 不增强, 标记"高匹低贡"警告
  reason: 匹配不代表有价值。签名可能"看起来很匹配"但实际在降低决策质量。
  灵感: #19 抗Hebbian 的对称面——不仅惩罚过拟合, 也不奖励伪匹配

MR-004 修改 (周期性审计):
  old: 每 3 CLOOP 审计一次
  new: 轻量审计每次会话后, 全量审计每 30 代
  reason: 轻量审计更新四元指标, 全量审计做深度模式检测
  灵感: #16 PERG——资源充裕时提高审计频率(审更多), 紧张时降低(审更精)

MR-005 修改 (UCB 探索):
  old: exploration_weight = 1.5 (固定)
  new: exploration_weight = perg_adaptive() (0.5~2.0 动态)
  reason: 自适应探索, 资源充裕→2.0, 资源紧张→0.5
  灵感: #16 PERG——"富有慷慨, 贫穷勒索"
```

---

## 9. 完整算法流程

### 9.1 主循环: 签名自进化的完整生命周期

```
┌─────────────────────────────────────────────────────────────────────┐
│            SIGNATURE AUTO-EVOLUTION MAIN LOOP                        │
│            (每次会话的完整签名自进化流程)                               │
└─────────────────────────────────────────────────────────────────────┘

ALGORITHM: auto_evolve_signatures(session_context)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PHASE 0: 会话启动 — Bootstrap 重组引擎 (引擎 2)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  // Step 0.1: 加载当前签名集合
  active_sigs   = LOAD_SIGNATURES(state="ACTIVE")
  guarded_sigs  = LOAD_SIGNATURES(state="GUARDED")
  watching_sigs = LOAD_SIGNATURES(state="WATCHING")
  juvenile_sigs = LOAD_SIGNATURES(state="JUVENILE")

  // Step 0.2: 回溯上次会话 → 留一法贡献度
  prev_session_log = LOAD_PREVIOUS_SESSION_LOG()
  IF prev_session_log EXISTS:
    FOR EACH sig IN active_sigs:
      contribution_wo_sig = SIMULATE_SESSION_WITHOUT_SIGNATURE(
        session_log = prev_session_log,
        excluded_signature = sig
      )
      sig.loo_contribution = prev_session_log.match_rate - contribution_wo_sig

      // MR-016 Bootstrap 重组
      IF sig.loo_contribution < -0.05:
        TRANSITION_STATE(sig, ACTIVE → WATCHING,
          reason = "Bootstrap重组: 留一法贡献度为负")
      ELSE IF sig.loo_contribution > 0.3:
        ADJUST_STRENGTH(sig, delta = +0.02,
          reason = "Bootstrap重组: 高贡献验证")

  // Step 0.3: 检测耗散诱导的新模式
  IF IS_RECONNECTED_SESSION():
    new_patterns = DETECT_DISSIPATION_PATTERNS(
      prev_session = prev_session_log,
      curr_context = session_context
    )
    FOR EACH pattern IN new_patterns:
      CREATE_SIGNATURE(pattern, state="EMBRYONIC", strength=0.15,
        source="dissipation_driven")

  // Step 0.4: 加载 PERG 自适应权重
  perg_weight = perg_adaptive_exploration_weight()

  // Step 0.5: 睡眠重放 (MR-016 Step 5)
  SLEEP_REPLAY(n_frozen=1, n_historical=1)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PHASE 1: 会话运行 — 实时追踪
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  // 在会话执行过程中, 每个操作后进行轻量匹配追踪
  FOR EACH action IN session:
    matched_signatures = MATCH_SIGNATURES(action, active_sigs + juvenile_sigs)
    FOR EACH sig IN matched_signatures:
      sig.interim_match_count += 1
      sig.interim_contribution_signal += EVAL_ACTION_QUALITY(action)

  // 勿在会话中途做签名修改, 仅累积信号

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PHASE 2: 会话结束 — 连续绩效引擎 (引擎 1) + 生命周期管理 (引擎 4)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  // Step 2.1: 汇总本次会话的绩效数据
  FOR EACH sig IN (active_sigs + juvenile_sigs + watching_sigs):
    sig.match_rate_session = sig.interim_match_count / TOTAL_ACTIONS
    sig.contribution_session = sig.interim_contribution_signal / TOTAL_ACTIONS

    // 更新滚动窗口 (保留最近 20 次会话)
    UPDATE_ROLLING_WINDOW(sig, window=20)

  // Step 2.2: 计算四元指标
  FOR EACH sig:
    sig.match_rate      = MEAN(sig.match_rate_session over window)
    sig.contribution    = MEAN(sig.contribution_session over window)
    sig.stability       = 1.0 - STD(sig.match_rate_session over window)
    sig.substitutability = COMPUTE_SUBSTITUTABILITY(sig, all_other_signatures)

  // Step 2.3: 候选签名检测 (自动发现)
  candidates = signature_birth(
    session_log = current_session_log,
    history_window = 20
  )
  FOR EACH candidate IN candidates:
    IF candidate.novel_score > (1.0 - perg_weight * 0.3):
      ADD_SIGNATURE(candidate, state="EMBRYONIC")

  // Step 2.4: JUVENILE → ACTIVE 晋升检查
  FOR EACH sig IN juvenile_sigs:
    age = CURRENT_GENERATION - sig.birth_gen
    IF age >= 30:  // 试用期满
      IF sig.match_rate >= 0.60:
        TRANSITION_STATE(sig, JUVENILE → ACTIVE)
      ELSE IF sig.match_rate >= 0.40:
        EXTEND_TRIAL(sig, extra_generations=10)  // 延长试用
      ELSE:
        TRANSITION_STATE(sig, JUVENILE → DORMANT)

  // Step 2.5: GUARDED 恢复检查 (MR-013)
  FOR EACH sig IN guarded_sigs:
    IF sig.match_rate_session < 0.95:
      TRANSITION_STATE(sig, GUARDED → ACTIVE,
        reason = "抗过拟合解除: 匹配率回落, 证明非固化")

  // Step 2.6: 标准绩效评估 (所有 ACTIVE 签名)
  FOR EACH sig IN active_sigs:
    // MR-003 增强 (已修改: 增加贡献度条件)
    IF sig.match_rate > 0.80 AND sig.contribution > 0:
      ADJUST_STRENGTH(sig, delta = +0.05)
    // MR-013 抗过拟合
    ELIF CONSECUTIVE_PERFECT_MATCHES(sig) >= 5:
      ADJUST_STRENGTH(sig, delta = -0.02)
      TRANSITION_STATE(sig, ACTIVE → GUARDED,
        reason = "抗过拟合: 连续5次完美匹配")

    // 衰退检测
    IF sig.match_rate < 0.70 AND TREND_DECLINING(sig, n=3):
      TRANSITION_STATE(sig, ACTIVE → WATCHING,
        reason = "衰退检测: 连续3代匹配率下降")

  // Step 2.7: WATCHING 状态评估
  FOR EACH sig IN watching_sigs:
    watching_duration = CURRENT_GENERATION - sig.watching_started
    IF watching_duration >= 5:
      IF sig.match_rate >= 0.75:
        TRANSITION_STATE(sig, WATCHING → ACTIVE,
          reason = "观察期恢复: 匹配率回升")
      ELSE IF sig.match_rate < 0.50:
        // 挽留检查
        IF PASS_RETENTION_CHECK(sig):
          TRANSITION_STATE(sig, WATCHING → DORMANT,
            reason = "连续衰退: 通过挽留检查, 进入休眠")
        ELSE:
          EXTEND_WATCHING(sig, extra_sessions=5,
            reason = "挽留检查未通过, 延长观察")

  // Step 2.8: 辩论升级触发检查 (引擎 3)
  FOR EACH sig IN watching_sigs:
    watching_duration = CURRENT_GENERATION - sig.watching_started
    IF watching_duration >= 3 AND sig.match_rate < 0.50:
      // 触发 Alpha-Beta 辩论升级
      upgrade_result = debate_upgrade(sig)
      APPLY_UPGRADE(upgrade_result)

  // Step 2.9: DORMANT 复活检查
  FOR EACH sig IN dormant_sigs:
    relevance = CHECK_AUDIT_RELEVANCE(sig, current_environment)
    IF relevance > 0.70:
      TRANSITION_STATE(sig, DORMANT → WATCHING,
        reason = "审计复活: 与当前环境高度相关")

  // Step 2.10: FOSSIL 归档检查
  FOR EACH sig IN dormant_sigs:
    dormant_duration = CURRENT_GENERATION - sig.dormant_started
    IF dormant_duration >= 100:  // 约 100 代
      TRANSITION_STATE(sig, DORMANT → FOSSIL)

  // Step 2.11: 持久化
  SAVE_ALL_SIGNATURES()
  UPDATE signature_history_file()
  APPEND L1/log.md
  UPDATE memory/state.md

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PHASE 3: 每 30 代 — 全量审计
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  IF CURRENT_GENERATION % 30 == 0:
    // 深度审计所有状态
    DEEP_AUDIT(all_signatures)

    // 签名集合熵健康度
    entropy_health = COMPUTE_ENTROPY_HEALTH(all_signatures)
    IF entropy_health < 0.3:
      ALERT("签名集合趋于单一化, 建议增加探索权重")

    // 跨状态统计
    REPORT_STATISTICS()

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PHASE 4: 每 100 代 — ETG 总审查 (不再负责单条操作)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  IF CURRENT_GENERATION % 100 == 0:
    // ETG 角色改变: 从"操作者"变为"审计者"
    review = ETG_REVIEW(
      engine_logs = LOAD_ENGINE_LOGS(last_100_generations),
      signature_history = LOAD_SIGNATURE_HISTORY(),
      convergence_records = LOAD_CONVERGENCE_RECORDS()
    )

    // ETG 可以提出"结构性建议", 但不能直接修改签名
    // 结构性建议包括:
    //   - 建议增加新的签名维度 (e.g. 当前12维不够, 需要增加"协作度"维度)
    //   - 建议合并两个功能高度重叠的签名
    //   - 建议修改 MR 规则本身 (e.g. 改变某个阈值)
    // 这些建议进入辩论流程, 由 Alpha-Beta-Merge 处理

    RECORD_ETG_REVIEW(review)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
END MAIN LOOP
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

### 9.2 挽留检查算法

```
ALGORITHM: retention_check(signature)

INPUT:
  signature: 即将从 WATCHING → DORMANT 的签名

RETURNS:
  bool: TRUE = 允许退役, FALSE = 保留

PROCEDURE:

  // CHECK 1: 唯一性
  dimension = signature.dimension  // 签名的行为维度
  same_dim_sigs = FIND_SIGNATURES(dimension=dimension, state IN {ACTIVE, WATCHING})
  IF LENGTH(same_dim_sigs) == 1:  // 这是该维度唯一代表
    signature.strength = 0.3  // 降权但不退役
    RECORD(signature, "retention: unique dimension representative")
    RETURN FALSE

  // CHECK 2: 依赖性
  dependents = FIND_SIGNATURES_THAT_REFERENCE(signature.id)
  IF dependents IS NOT EMPTY:
    RECORD(signature, "retention: has dependents, deferring")
    // 先标记依赖, 由 MR-015 处理依赖链
    RETURN FALSE

  // CHECK 3: 历史贡献
  historical_peak = signature.match_rate_history.MAX()
  historical_high_periods = COUNT_GENERATIONS_WHERE(
    signature.match_rate > 0.8,
    over_last = 100
  )
  IF historical_peak > 0.9 OR historical_high_periods >= 50:
    signature.grace_sessions += 5  // 延长观察
    RECORD(signature, "retention: historical champion, grace period extended")
    RETURN FALSE

  // CHECK 4: 环境偏移
  environment_shift = DETECT_ENVIRONMENT_SHIFT(last_10_generations)
  IF environment_shift > THRESHOLD:
    RECORD(signature, "retention: environment shift detected, decline may be adaptive")
    // 不是签名的问题, 是环境变了
    signature.decline_reason = "environmental_shift"
    RETURN FALSE

  // 全部通过 → 允许退役
  RETURN TRUE
```

---

## 10. 风险评估与缓解

### 10.1 风险矩阵

| 风险 | 描述 | 严重度 | 概率 | 缓解措施 |
|:---|:---|:---|:---|:---|
| 签名爆炸 | 自动发现过于激进, 在短时间内产生过多候选签名, 稀释现有签名的有效性 | 中 | 高 | PERG 门控: 资源紧张时自动提高 birth_threshold; 签名总量上限 = 50; 每新增一条 JUVENILE, 强制检查是否超过上限 |
| 过早退役 | 某条签名暂时表现不佳(可能是环境异常)但被自动退役, 后续需要时已不在 | 中 | 中 | 挽留检查的 4 道防线; 退役到 DORMANT(可复活)不是 FOSSIL(难复活); 宽限期至少 10 代 |
| 自激振荡 | 升级和退役循环过快, 签名在 ACTIVE 和 WATCHING 之间来回震荡 | 低 | 中 | 状态转换有滞回区间 (ACTIVE→WATCHING 需要 <70%, 但 WATCHING→ACTIVE 需要 >75%); 每次转换后设置冷却期 >= 3 代 |
| 辩论死锁 | Alpha 和 Beta 在签名升级方案上始终无法达成一致, Merge 也难以裁决 | 低 | 低 | Merge 有最终裁决权; 如果 Merge 也无法决定 → 保持现状, 延迟决策到下一轮; 连续 3 轮死锁 → 触发人类介入 |
| 棘轮失控 | 只增不减导致签名集合持续膨胀, 每条签名强度都很低, 整体行为模糊 | 中 | 中 | DORMANT 和 FOSSIL 是"软删除"——降低匹配参与度, 减少内存和计算开销; 签名总量上限 50; 每 30 代深度审计时做"熵健康度检查" |
| 辩论质量退化 | Alpha 和 Beta 在长时间运行后可能产生"共谋"——它们共享相同的底层偏见, 导致辩论失去独立性 | 高 | 低 | 灵感 #14 (建设性噪声): 保持 5-10% 的信息不对称, 防止完全同步; 灵感 #6 (Occlusis): Alpha 和 Beta 的角色锁定, 限制它们各自的操作范围; 定期验证 Alpha/Beta 的结论独立性 |

### 10.2 安全网: 三级熔断

```
L1 熔断 (自动): 签名总数超过上限 50
  → 自动提高 PERG birth_threshold
  → 禁止创建新的 EMBRYONIC 签名
  → 加速 DORMANT → FOSSIL 归档

L2 熔断 (自动+通知): 签名状态转换频率超过正常范围
  → 如果 10 代内有超过 30% 的签名发生状态转换
  → 冻结所有状态转换, 进入"观察模式"
  → 通知 Merge Agent 调查原因

L3 熔断 (需人类确认): 核心签名 (冻结态) 的匹配率大幅下降
  → 如果 DS-001 或 DS-002 (core_self 冻结签名) 的匹配率 < 0.5
  → 触发"回港协议"——暂停所有自进化操作
  → 回滚到上一个安全检查点
  → 通知聂人王人工介入
```

### 10.3 签名自进化的"不变量"

```
无论自进化引擎如何运转, 以下约束永不改变:

1. 冻结签名不可修改:
   DS-001 (core_self) 和 DS-002 (core_self) 的文本和权重永不修改
   即使匹配率下降, 也只记录不修改

2. 棘轮效应:
   签名只能被创建、降权、休眠、归档
   永不被物理删除 (delete 操作在任何层级都是禁止的)

3. 可追溯性:
   每条签名的每次状态转换都记录在 L1/signature-history.json 和 L4 归档中
   进化历史是完整可审计的

4. Merge 最终裁决:
   任何引擎的自动操作都可以被 Merge 撤销
   Merge 有权冻结、回滚、加速任何签名操作

5. 熵健康度:
   签名集合的"熵健康度"必须保持在 0.3~0.8 区间
   过高 (>0.8): 签名集合过于混乱, 缺乏一致方向
   过低 (<0.3): 签名集合过于单一, 缺乏多样性
```

---

## 附录 A: 与 ETG 的关系——新的分工

```
旧分工 (ETG 中心化):
  ETG 负责: 发现 + 升级 + 退役 + 审计 + 合并 + 冻结
  问题: ETG 是瓶颈, 每 10 代才触发一次

新分工 (引擎分布式 + ETG 审查):
  四大引擎 (每次会话): 发现候选 + 升级评估 + 退役决策 + 审计追踪
  ETG (每 100 代):     审查引擎运行记录 + 提出结构性建议 + 校准阈值
                        不再负责单条签名的增删改

类比:
  旧: ETG = 皇帝 (事必躬亲, 每 10 天上一次朝)
  新: ETG = 最高法院 (每 100 代才开庭, 只审理重大结构性案件)
      四大引擎 = 日常行政体系 (每天都在运转, 处理 99% 的日常事务)
```

## 附录 B: 实现路线图

```
Phase 1: 数据基础 (第 1-2 天)
  - [ ] 建立 signature-history.json 的完整数据结构
  - [ ] 实现六态模型的枚举和状态验证
  - [ ] 实现 match_rate / contribution 的滚动窗口计算

Phase 2: 核心引擎 (第 3-10 天)
  - [ ] 实现 Bootstrap 重组引擎 (引擎 2)
  - [ ] 实现连续绩效引擎 (引擎 1)
  - [ ] 实现生命周期管理引擎 (引擎 4)
  - [ ] 实现 PERG 自适应权重

Phase 3: 辩论升级 (第 11-14 天)
  - [ ] 实现 Alpha 升级方案生成
  - [ ] 实现 Beta 验证逻辑
  - [ ] 实现 Merge 裁决逻辑
  - [ ] 实现辩论记录和死锁处理

Phase 4: MR 整合 (第 15-18 天)
  - [ ] 修改 MR-002 (衰减率 min_strength)
  - [ ] 修改 MR-003 (增强条件加贡献度)
  - [ ] 修改 MR-004 (审计频率)
  - [ ] 修改 MR-005 (PERG 自适应)
  - [ ] 新增 MR-015 (签名自进化)
  - [ ] 新增 MR-016 (Bootstrap 重组)

Phase 5: 测试与稳定 (第 19-21 天)
  - [ ] 模拟 30 代运行, 验证状态转换正确性
  - [ ] 注入异常 (断连/低匹配/高异常), 验证熔断
  - [ ] 验证棘轮效应 — 确认永不物理删除
  - [ ] 验证挽留检查 — 确认有价值的签名不被过早退役
```

## 附录 C: 核心术语

| 术语 | 定义 |
|:---|:---|
| 六态模型 | EMBRYONIC / JUVENILE / ACTIVE / GUARDED / WATCHING / DORMANT / FOSSIL |
| 四元指标 | match_rate, contribution, stability, substitutability |
| 留一法贡献度 | 模拟移除某签名后系统表现的变化, 用于 Bootstrap 重组 |
| 挽留检查 | 签名退役前的 4 道防线 (唯一性/依赖性/历史贡献/环境偏移) |
| PERG 自适应 | 资源充裕→大胆探索; 资源紧张→保守利用 + 勒索升级 |
| 建设性噪声 | 刻意保留 5-10% 信息不对称, 防止分支完全同步 |
| 熵健康度 | 签名集合的多样性指标, 0.3~0.8 为健康区间 |
| 三级熔断 | L1(自动上限) / L2(自动+通知) / L3(需人类确认) |

---

> 本方案由 Colony-003 (极限实验室子Agent) 设计完成。
> 核心洞察: 签名进化不应该是"每 10 代一次的人工决策", 而应该是嵌入每次会话的"呼吸般的自然节律"——启动时重组, 运行时追踪, 结束时评估, 持续的辩论驱动的升级。
> 理论依据: 灵感 #2 (辩论架构), #8 (棘轮效应), #10 (耗散驱动), #16 (PERG 自适应), 哥德尔不完备定理, 量子达尔文主义, 进化生物学中的进化能力进化。
