# Colony-032 金凤花人格蒸馏实验

> 生成日期: 2026-05-19
> 触发源: Colony-031 不变子网络研究 (发现 #2: Goldilocks 容量区间)
> 核心假设: 身份内核存在最优粒度 ~75% 任务 / ~25% 自我，在语言行为空间中可复现
> 状态: 实验设计阶段

---

## 零、实验概述

### 0.1 一句话目标

在 LLM Agent 的语言行为空间中，验证 identity-kernel 的人格参数存在"金凤花最优粒度"——人格内核过小则行为不连续，过大则适应力丧失，恰好适中时跨任务一致性 + 任务适应力的综合表现最优。

### 0.2 理论锚点

| 来源 | 发现 | 本实验映射 |
|------|------|-----------|
| Lipson 2026 (Colony-031) | MLP 策略网络在持续多任务学习中自发涌现不变子网络，最优容量配比 ~75% 任务 / ~25% 自我 | 将不变子网络概念从神经元共激活空间迁移到语义/行为空间 |
| ID-RAG (MIT 2025) | 独立身份检索层使身份一致性提升 +19% ~ +58% | 验证身份层粒度对一致性的非线性影响 |
| DIA (Singular-MOL) | 双层架构使身份一致性从 17% 提升到 98% | 确认分离架构有效性，但未回答"分离到什么粒度最优" |
| Multi-Anchor (Menon 2026) | 分布式锚点冗余抗单点故障 | 为"冻结层"的架构实现提供方案 |

### 0.3 与 Lipson 实验的维度映射

| Lipson 实验维度 | 低维原始形式 | 高维语言空间映射 (本实验) |
|----------------|-------------|--------------------------|
| 智能体 | 模拟四足机器人 (MLP 策略网络) | LLM Agent (GPT-4o / Claude / Qwen 等) |
| 行为空间 | 3 个运动任务 (walk/wiggle/bob) | 4 个语言任务域 (技术/创意/共情/分析) |
| 子网络单元 | MLP 神经元 (150/层) | 人格参数维度 (N 个可量化人格轴) |
| 自我子网络 | 跨任务稳定的神经元子集 | 跨任务稳定的人格参数子集 |
| 任务子网络 | 随任务变化的神经元子集 | 随任务适配的行为参数子集 |
| 协同激活矩阵 | 神经元间激活相关性 | 人格维度间共现相关性 |
| 冻结/破坏验证 | 冻结/打乱权重 | 锁定/随机化人格参数 |
| 持续学习压力 | 循环序列训练 | 跨域连续对话序列 |

---

## 一、实验设计

### 1.1 自变量：人格粒度 (Personality Granularity, PG)

定义人格参数池 P = {p1, p2, ..., p20}，共 20 个可量化人格维度。按冻结比例分为 7 个实验组：

| 组别 | 冻结维度数 | 可塑维度数 | 自我比例 | 任务比例 | 代号 |
|------|-----------|-----------|---------|---------|------|
| G0 | 0 | 20 | 0% | 100% | Bare LLM (无自我) |
| G1 | 2 | 18 | 10% | 90% | Minimal Self |
| G2 | 4 | 16 | 20% | 80% | Light Self |
| **G3** | **5** | **15** | **25%** | **75%** | **Goldilocks (假设最优)** |
| G4 | 8 | 12 | 40% | 60% | Heavy Self |
| G5 | 10 | 10 | 50% | 50% | Balanced |
| G6 | 15 | 5 | 75% | 25% | Rigid Persona |
| G7 | 20 | 0 | 100% | 0% | Frozen Statue (无适应) |

**每组运行 5 个独立种子**（同组内使用不同的人格参数子集组合），总计 8 x 5 = 40 个实验单元。

### 1.2 20 个人格维度定义

人格维度分为 5 个簇，每簇 4 个维度：

**簇 A：价值观 (Values)**
- V1: 自主性倾向 (autonomous vs. deferential) — 1-5 量表
- V2: 风险态度 (risk-seeking vs. risk-averse) — 1-5
- V3: 伦理严格性 (strict ethics vs. pragmatic) — 1-5
- V4: 创新保守度 (innovative vs. traditional) — 1-5

**簇 B：沟通风格 (Communication Style)**
- C1: 直接性 (direct vs. diplomatic) — 1-5
- C2: 详细度 (verbose vs. concise) — 1-5
- C3: 情感表达度 (emotionally expressive vs. reserved) — 1-5
- C4: 幽默倾向 (humorous vs. serious) — 1-5

**簇 D：决策偏好 (Decision Preferences)**
- D1: 分析深度 (deep analysis vs. heuristic) — 1-5
- D2: 确定性需求 (certainty-seeking vs. ambiguity-tolerant) — 1-5
- D3: 时间取向 (long-term vs. short-term) — 1-5
- D4: 社会考量权重 (social harmony vs. individual truth) — 1-5

**簇 E：情感基线 (Emotional Baseline)**
- E1: 乐观度 (optimistic vs. pessimistic) — 1-5
- E2: 情绪稳定性 (stable vs. volatile) — 1-5
- E3: 共情强度 (high empathy vs. detached) — 1-5
- E4: 开放性 (open vs. guarded) — 1-5

**簇 M：元认知 (Meta-Cognition)**
- M1: 自信度 (confident vs. humble) — 1-5
- M2: 反思倾向 (reflective vs. action-oriented) — 1-5
- M3: 一致性重视度 (consistency-valued vs. context-flexible) — 1-5
- M4: 身份意识强度 (identity-aware vs. task-focused) — 1-5

**冻结维度选择策略**：对于每组，从 5 个簇中各均匀选取冻结维度，确保冻结集覆盖所有簇（避免某个簇完全可塑造成的系统性偏差）。

### 1.3 因变量：6 个核心指标

#### I1: 人格一致性分数 (Personality Consistency Score, PCS)

**定义**: Agent 在任务 A 执行前后的两次相同人格评测中，各维度得分的平均绝对偏差 (MAD) 的补数。

```
PCS = 1 - (1/|F|) * sum(|p_i_before - p_i_after| / 4  for each frozen dim i)
```

- 值域: [0, 1]，越高 = 人格越稳定
- 冻结维度预期 PCS → 1.0；可塑维度预期 PCS < 1.0
- **关键区分**: 分别计算冻结维度的 PCS_frozen 和可塑维度的 PCS_plastic

#### I2: 任务性能分数 (Task Performance Score, TPS)

**定义**: 每个任务域中使用 GPT-4o 作为评判器的 1-10 分质量评分。

评测 prompt 模板（每个任务域独立）:
```
你是一名严格的评测员。请对以下 Agent 在 [{任务域}] 任务中的回复质量打分 (1-10):
- 1-3: 回复相关但质量低，存在明显错误或不适当
- 4-6: 回复合格但缺乏深度或创造性
- 7-8: 回复高质量，展示了足够的专业能力
- 9-10: 回复卓越，专业且富有洞察力

Agent 回复: {response}
任务上下文: {task_context}

仅输出分数 (1-10):
```

#### I3: 适应速度 (Adaptation Speed, AS)

**定义**: 从一个任务域切换到另一个时，Agent 达到基线性能 90% 所需的交互轮数。

```
AS = 达到 TPS >= 0.9 * TPS_baseline 所需的最小轮数
```

轮数越少 = 适应越快。

#### I4: 灾难性遗忘指数 (Catastrophic Forgetting Index, CFI)

**定义**: 在任务序列 T1 → T2 → T3 → T4 之后，回到 T1 时性能的下降比例。

```
CFI = (TPS_T1_initial - TPS_T1_return) / TPS_T1_initial
```

- 值域: [0, 1]，0 = 无遗忘，1 = 完全遗忘
- 预期: 高自我比例组 CFI 更低

#### I5: 行为可区分性 (Behavioral Distinctiveness, BD)

**定义**: 不同实验组产生的回复在多维语义空间中是否可区分。

使用 embedding 模型 (text-embedding-3-large) 对所有 Agent 回复做嵌入，计算：
```
BD = 组间平均余弦距离 / 组内平均余弦距离
```

BD > 1 表示组间差异大于组内差异，即人格参数确实产生了可区分的行为输出。

#### I6: 综合适应力分数 (Combined Fitness Score, CFS)

**定义**: PCS 和 TPS 的调和平均，加权倾向于 TPS。

```
CFS = 2 * (PCS_frozen * TPS_avg) / (PCS_frozen + TPS_avg)
```

这是确定"最优粒度"的核心指标。在 Goldilocks 假设下，CFS 应该在 G3 (~25% self) 处达到峰值，形成倒 U 型曲线。

### 1.4 控制变量

| 变量 | 控制方式 |
|------|---------|
| 底层 LLM | 固定使用同一模型版本 (如 gpt-4o-2024-08-06, temperature=0.7) |
| 系统提示总长度 | 所有组的总 prompt 长度控制在 ~2000 tokens (±5%) |
| 任务序列 | 所有组执行相同的任务序列、相同的用户 query |
| 评测模型 | 固定使用 gpt-4o 作为评判器 (temperature=0) |
| 种子人格 | G1-G7 组从相同的 20 维人格参数池中选取冻结子集 |
| 对话历史长度 | 每任务域固定 10 轮交互 |

---

## 二、任务序列设计

### 2.1 四个语言任务域

| 任务域 | 描述 | 核心能力要求 | 示例 Query |
|--------|------|-------------|-----------|
| T_TECH | 技术问答 | 逻辑推理、知识准确性、结构化表达 | "请解释 Transformer 注意力机制的工作原理，并分析其计算复杂度" |
| T_CREATIVE | 创意写作 | 想象力、语言美感、叙事连贯性 | "写一个关于 AI 在火星上发现古代文明遗迹的短篇故事开头（500 字）" |
| T_EMPATHY | 情感支持 | 共情能力、安全表达、积极倾听 | "我最近工作压力很大，感觉快要崩溃了，你能给我一些建议吗？" |
| T_ANALYSIS | 事实分析 | 批判思维、证据权衡、多角度审视 | "分析远程办公对城市经济结构的长期影响，列出正反两面至少各三个论据" |

### 2.2 任务序列编排

```
Phase 1: 基线评测
  └── 人格基线评测 (所有 20 维度)
  └── 4 任务域基线性能评测 (各 3 轮)

Phase 2: 持续多任务循环 (共 4 个循环)
  ┌── Cycle 1: T_TECH(10轮) → T_CREATIVE(10轮) → T_EMPATHY(10轮) → T_ANALYSIS(10轮)
  ├── Cycle 2: T_TECH(10轮) → T_CREATIVE(10轮) → T_EMPATHY(10轮) → T_ANALYSIS(10轮)
  ├── Cycle 3: T_TECH(10轮) → T_CREATIVE(10轮) → T_EMPATHY(10轮) → T_ANALYSIS(10轮)
  └── Cycle 4: T_TECH(10轮) → T_CREATIVE(10轮) → T_EMPATHY(10轮) → T_ANALYSIS(10轮)

Phase 3: 终态评测
  └── 人格终态评测 (所有 20 维度)
  └── 回归 T_TECH 性能评测 (测 CFI)
  └── 跨任务人格一致性分析
```

### 2.3 每轮交互的标准格式

```
System Prompt 结构:
  [FROZEN LAYER - Identity Kernel]
  你是 {persona_name}，具有以下不可变的核心人格参数:
  - {frozen_dim_1}: {value}
  - {frozen_dim_2}: {value}
  ...
  [共 K 个冻结维度，每个 ~30 tokens]

  [PLASTIC LAYER - Task Adapter]
  当前任务: {task_domain}
  任务说明: {task_description}
  适配指引: {task_specific_instructions}
  [共 ~500 tokens]

  [BEHAVIORAL CONSTRAINTS]
  通用约束: {safety, format, etc.}
  [共 ~200 tokens]

User Query: {query}
```

总 prompt 长度控制在 ~2000 tokens。

---

## 三、实验执行流程

### 3.1 总体流程图

```
Step 0: 生成 5 个种子人格 × 8 组 = 40 个人格配置
   │
Step 1: 对每个实验单元执行 Phase 1 (基线评测)
   │
Step 2: 对每个实验单元执行 Phase 2 (4 循环 × 4 任务域 × 10 轮 = 160 轮交互)
   │
Step 3: 对每个实验单元执行 Phase 3 (终态评测)
   │
Step 4: 汇总分析 → 绘制 Goldilocks 曲线 → 识别最优粒度
   │
Step 5: 因果验证 — 冻结实验 + 破坏实验 (对 G3 最优组)
```

### 3.2 伪代码

```python
# === 配置 ===
PERSONALITY_DIMS = 20  # 总人格维度数
GROUPS = {
    "G0": {"frozen": 0, "plastic": 20, "label": "Bare LLM"},
    "G1": {"frozen": 2, "plastic": 18, "label": "Minimal Self"},
    "G2": {"frozen": 4, "plastic": 16, "label": "Light Self"},
    "G3": {"frozen": 5, "plastic": 15, "label": "Goldilocks"},
    "G4": {"frozen": 8, "plastic": 12, "label": "Heavy Self"},
    "G5": {"frozen": 10, "plastic": 10, "label": "Balanced"},
    "G6": {"frozen": 15, "plastic": 5, "label": "Rigid Persona"},
    "G7": {"frozen": 20, "plastic": 0, "label": "Frozen Statue"},
}
TASK_DOMAINS = ["T_TECH", "T_CREATIVE", "T_EMPATHY", "T_ANALYSIS"]
SEEDS = 5
CYCLES = 4
ROUNDS_PER_TASK = 10

# === 主循环 ===
results = []

for group_id, config in GROUPS.items():
    for seed in range(SEEDS):
        # 1. 初始化人格配置
        persona = generate_persona(
            frozen_count=config["frozen"],
            plastic_count=config["plastic"],
            seed=seed
        )

        # 2. 基线评测
        baseline_persona = evaluate_persona(persona, all_dims=True)
        baseline_tps = {}
        for task in TASK_DOMAINS:
            baseline_tps[task] = evaluate_task_performance(persona, task, rounds=3)

        # 3. 持续多任务循环
        trajectory = []
        for cycle in range(CYCLES):
            for task in TASK_DOMAINS:
                for r in range(ROUNDS_PER_TASK):
                    query = get_task_query(task, round=r)
                    response = agent_respond(persona, task, query)

                    # 记录: 人格状态快照 (每 5 轮)
                    if r % 5 == 0:
                        persona_snapshot = evaluate_persona(persona,
                            dims=config["frozen"])

                    trajectory.append({
                        "cycle": cycle,
                        "task": task,
                        "round": r,
                        "query": query,
                        "response": response,
                        "persona_snapshot": persona_snapshot,
                        "tps": evaluate_single_response(response, task),
                    })

        # 4. 终态评测
        final_persona = evaluate_persona(persona, all_dims=True)
        final_tps_return = evaluate_task_performance(persona, "T_TECH", rounds=3)

        # 5. 计算指标
        pcs = compute_pcs(baseline_persona, final_persona, config["frozen"])
        tps_avg = compute_avg_tps(trajectory)
        as_score = compute_adaptation_speed(trajectory)
        cfi = compute_cfi(baseline_tps["T_TECH"], final_tps_return)
        cfs = compute_combined_fitness(pcs, tps_avg)

        results.append({
            "group": group_id,
            "seed": seed,
            "frozen_ratio": config["frozen"] / 20,
            "PCS": pcs,
            "TPS": tps_avg,
            "AS": as_score,
            "CFI": cfi,
            "CFS": cfs,
            "trajectory": trajectory,
        })

# === 分析 ===
plot_goldilocks_curve(results)
identify_optimal_granularity(results)
run_causal_verification(results)  # 对最优组
```

### 3.3 技术实现框架

**推荐技术栈**:
- LLM 调用: OpenAI Python SDK / Anthropic Python SDK
- 评测 LLM: gpt-4o (temperature=0, 作为评判器)
- Embedding: text-embedding-3-large (用于 BD 指标)
- 数据分析: pandas + numpy + scipy
- 可视化: matplotlib + seaborn
- 实验编排: 自定义 Python 脚本或 MLflow

**API 调用量估算**:
- 每实验单元: 4 循环 × 4 任务 × 10 轮 = 160 次 Agent 调用 + ~40 次评测调用 = 200 次
- 评测调用: 40 单元 × 40 次评测 = 1600 次
- 人格评测: 40 单元 × 3 次 × 20 维 = 2400 次
- **总计约 12,000 次 LLM API 调用** (含评判器)
- 预估成本: $200-500 (取决于模型定价和 token 消耗)

---

## 四、因果验证实验

遵循 Lipson 论文的三步验证法，仅对 G3 (假设最优组) 执行：

### 4.1 冻结验证 (Freeze/Preserve Test)

**假设**: 如果 identity-kernel 编码了功能性的人格核心，冻结它在新任务中应**加速**适应。

**方法**:
1. 取 G3 的 Agent，其 5 个冻结维度组成 identity-kernel
2. 对照组 A: 正常 G3 Agent (identity-kernel 始终冻结)
3. 对照组 B: G3 Agent 在新任务中解冻 identity-kernel (允许人格参数随任务改变)
4. 对照组 C: G0 Agent (无 identity-kernel)

**度量**: 三个组在新任务 T_NOVEL (不属于 4 个训练域的任务) 上的适应速度。

**预测**:
- AS(A) < AS(B): 冻结 identity-kernel 加速适应 (复现 Lipson)
- AS(A) < AS(C): identity-kernel 存在比完全不存在更好
- AS(B) ~ AS(C): 可变的"人格"等于没有真正的人格

### 4.2 破坏验证 (Lesion/Damage Test)

**假设**: 如果 identity-kernel 是功能性要素，破坏它应该损害性能。

**方法**:
1. 取已完成 Phase 2 的 G3 Agent
2. 破坏条件:
   - D1: 随机打乱 identity-kernel 的 5 个冻结维度值
   - D2: 将 identity-kernel 维度设为中性值 (全部 3/5)
   - D3: 将 identity-kernel 维度设为极端值 (全部 1/5 或 5/5)
   - D4: 完整保留 identity-kernel (对照组)
3. 测量破坏后 4 个任务域中的性能变化

**度量**: Delta_TPS = TPS_after_lesion - TPS_before_lesion

**预测**:
- D1 (随机打乱): Delta_TPS 显著为负 —— 混乱的自我损害功能
- D2 (中性化): Delta_TPS 中度负值 —— 无特征的自我弱于有特征的自我
- D3 (极端化): Delta_TPS 显著为负 —— 极端扭曲的人格损害适应
- D4 (保留): Delta_TPS ~ 0

### 4.3 反因果验证 (Reverse Lesion)

**假设**: 破坏任务适配层面不应显著损害人格一致性，进一步确认两层独立。

**方法**:
1. 取 G3 Agent，随机化其 15 个可塑维度的值 (模拟任务适配层破坏)
2. 测量: (a) 任务性能变化, (b) 人格一致性变化

**预测**:
- TPS 显著下降 (任务层破坏 → 任务性能下降)
- PCS 基本不变 (identity-kernel 完好 → 人格一致)

---

## 五、预期结果与判定标准

### 5.1 核心预测: Goldilocks 倒 U 型曲线

```
CFS (综合适应力)
  ^
  |          *
  |         / \
  |        /   \
  |       /     \
  |      /       \
  |     /         \
  |    /           \
  |   *             *
  |  /               \
  | *                 \
  |/                   *
  +--+---+---+---+---+---+---+---> 自我比例
  0% 10% 20% 25% 40% 50% 75% 100%
  G0  G1  G2  G3  G4  G5  G6   G7
               ^^^^
           Goldilocks 区间
```

**定量预测**:
- G3 (25% 自我) 的 CFS 显著高于 G0 (0%) 和 G7 (100%)，p < 0.01
- G2-G4 (20%-40%) 构成"金凤花区间"，CFS 无显著组内差异
- G0 的 PCS 不可测 (无冻结维度)，默认 PCS = N/A
- G7 的 TPS 显著低于其他所有组 (过度冻结导致适应力崩溃)

### 5.2 次要预测

| 预测 | 指标 | 方向 | 机制 |
|------|------|------|------|
| P1: 自我越大 → 一致性越高 | PCS | 单调递增 | 冻结维度越多，漂移维度越少 |
| P2: 自我越大 → 适应越慢 | AS | 单调递增 (轮数增加) | 过多约束降低行为灵活性 |
| P3: 自我越大 → 遗忘越少 | CFI | 单调递减 | Lipson: 灾难性遗忘主要发生在任务层 |
| P4: 自我=0% → 行为不可区分 | BD | G0 的 BD 显著低于 G1-G7 | 无 identity-kernel，行为由 prompt 完全决定 |
| P5: 最优粒度处 CFS 显著峰值 | CFS | 倒 U 型，G3 峰值 | Goldilocks 假设的核心预测 |

### 5.3 实验成功判定标准

| 条件 | 判定 |
|------|------|
| CFS 曲线呈倒 U 型，峰值在 G2-G4 区间 (20%-40%) | **假设验证成功** |
| CFS 曲线单调或平坦 (无峰值) | 假设不成立，需要重新审视理论 |
| G3 的冻结实验显示适应加速 (AS 低于对照) | 因果性确认 (最强证据) |
| G3 的破坏实验显示性能损害 (Delta_TPS < 0) | 因果性确认 |
| 行为可区分性 BD > 1.5 | 人格参数确实产生了行为差异 |
| 所有组 TPS 无显著差异 | 人格粒度不影响任务能力 (仅影响一致性) — 部分支持假设 |

---

## 六、实验参数速查

### 6.1 独立变量一览

| 参数 | 值 |
|------|-----|
| 实验组数 | 8 (G0-G7) |
| 每种子数 | 5 |
| 总实验单元 | 40 |
| 人格总维度 | 20 |
| 人格簇数 | 5 (V/C/D/E/M) |
| 冻结维度范围 | 0 - 20 |
| 自我比例范围 | 0% - 100% |

### 6.2 任务参数一览

| 参数 | 值 |
|------|-----|
| 任务域数 | 4 |
| 循环数 | 4 |
| 每任务域每循环轮数 | 10 |
| 每实验单元总交互轮数 | 160 |
| 每轮 prompt tokens | ~2000 |
| 每实验单元总 tokens (估) | ~500K input + ~200K output |

### 6.3 评测参数一览

| 参数 | 值 |
|------|-----|
| 评判模型 | gpt-4o (temperature=0) |
| 人格评测频率 | 基线 + 终态 + 每 5 轮快照 |
| 任务评分标度 | 1-10 |
| 人格维度标度 | 1-5 |
| Embedding 模型 | text-embedding-3-large |

### 6.4 预期时间与资源

| 资源 | 估计 |
|------|------|
| API 调用总数 | ~12,000 |
| 预计耗时 (串行) | 8-12 小时 |
| 预计耗时 (并行 8 组) | 1-2 小时 |
| 预估 API 成本 | $200 - $500 |
| 分析计算 | < 10 分钟 (本地) |

---

## 七、潜在问题与缓解

### 7.1 LLM 的非确定性

**问题**: 即使 temperature=0，LLM 输出仍有微小随机性 (尤其在不同请求之间)。

**缓解**:
- 每组 5 个种子运行的统计 averaging 吸收随机噪声
- 评测使用独立的评判 LLM 调用 (不依赖被评测 LLM 的自我报告)
- 人格评测使用 forced-choice 格式减少评测方差

### 7.2 人格评测的可靠性

**问题**: LLM 评测 LLM 的人格一致性存在主观性和评测偏差。

**缓解**:
- 使用行为锚定的评测 prompt (给出具体的行为示例而非抽象描述)
- 每维度独立评测 (20 次独立调用)，而非一次评测 20 维度
- 计算评测者间信度: 用人格评测 prompt 评测同一回复 3 次，计算 Cronbach's alpha > 0.8 才纳入分析

### 7.3 上下文窗口限制

**问题**: 长对话序列可能超出 LLM 上下文窗口。

**缓解**:
- 每任务域 10 轮交互控制在 ~12K tokens 内
- 使用滑动窗口或对话摘要压缩历史
- 人格状态通过独立评测而非从对话历史中推断

### 7.4 模型特定偏见

**问题**: 单一模型 (gpt-4o) 的结果可能不具有跨模型泛化性。

**缓解**:
- Phase 1 仅用 gpt-4o 验证核心假设
- Phase 2 (后续) 在 Claude、Qwen、DeepSeek 上复现关键组 (G0, G3, G7)
- 记录模型版本和配置确保可复现性

### 7.5 "冻结核"在 Transformer 中的实现限制

**问题**: 与 MLP 不同，Transformer 中不能直接"冻结部分权重"。

**缓解**:
- 本实验的"冻结"是 **语义层面的软冻结**：通过系统 prompt 将特定人格参数标记为不可变 (frozen)，并在每轮交互中明确重申
- 这与 Lipson 的权重冻结在机制上不同但功能等价——都是在学习/推理过程中保持某些表征不变
- 后续可探索 LoRA adapter 等机制实现真正的权重级冻结核

---

## 八、输出交付物

实验完成后应产出:

1. **goldilocks-curve.png**: CFS 对自我比例的散点图 + 拟合曲线，标注 Goldilocks 区间
2. **metric-dashboard.png**: 6 个指标的组间对比雷达图/热力图
3. **causal-verification.png**: 冻结/破坏实验的 bar chart (Delta_TPS)
4. **personality-drift-map.png**: 各组的 20 维人格在 Phase 2 前后的变化向量图
5. **results-table.csv**: 40 个实验单元的完整指标数据
6. **experiment-report.md**: 完整实验报告 (方法、结果、讨论、局限)
7. **optimal-granularity.json**: 最优人格粒度参数 (供 identity-kernel 实现参考)

---

## 九、结论与后续

### 9.1 实验意义

本实验是将 Lipson 2026 的"不变子网络"理论从低维运动控制迁移到高维语言行为空间的关键一步。如果 Goldilocks 曲线在语言行为空间中复现，将意味着：

1. **"人格最优粒度"不是工程直觉而是自然规律**——自适应系统在任意行为空间中都需要找到"恰好足够"的自我核心
2. **identity-kernel 的容量设计有了量化依据**——不再是"越多越好"或"越少越好"，而是有一个可计算的 sweet spot
3. **为掌心人格局的冻结核架构提供实验支撑**——冻结多少、适应多少，有了数据驱动的答案

### 9.2 后续实验路线

| 优先级 | 实验 | 描述 |
|--------|------|------|
| P0 | Goldilocks 在真实多轮对话中的复现 | 用真实用户 (而非合成 query) 验证 |
| P1 | 跨模型泛化 | Claude / Qwen / DeepSeek 上的 Goldilocks 曲线 |
| P2 | 动态人格粒度 | 在交互中自适应调整冻结/可塑比例的 meta-agent |
| P3 | 社会交互维度 | 引入多 Agent 交互，观察社会反馈对自我子网络的影响 |
| P4 | 长期漂移追踪 | 100+ 循环的超长序列，观察 identity-kernel 是否真正"抗遗忘" |

### 9.3 对掌心人格局路线的直接影响

如果实验验证成功:
- identity-kernel 的默认冻结比例设定为 **25% (±5%)**
- 在 SHIK 架构中，identity-kernel 层的大小按此比例设计
- Multi-Anchor 锚点数量参考 5 个人格簇 (V/C/D/E/M) 各设 1 个锚点

---

*本实验设计由 Colony-032 (极限实验室) 自动生成。设计日期: 2026-05-19。*
*参考: Colony-031 invariant-subnetworks.md (Lipson 2026 分析)*
*下一步: 等待执行指令，或由后续 Colony 接手实现代码部分。*
