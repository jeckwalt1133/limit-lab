# Colony系统v2.0架构设计

> 执行体: Colony-034 (极限实验室)
> 日期: 2026-05-19
> 性质: 整合四大外部吸收的下一代Colony架构
> 状态: 设计方案 (待实施)

---

## 前置声明

本架构整合四大外部吸收:

| 来源 | 论文/系统 | 核心贡献 | 吸收方式 |
|------|----------|---------|---------|
| Colony-027 | Hyperagents / DGM-H (Meta, ICLR 2026 Oral) | 持续自我修改循环、涌现元认知 | 架构层吸收 — Auto-GE引擎 |
| Colony-029 | 内生性悖论 (arXiv 2603.28990) | 固定编排+动态角色选举=最优 | 架构层吸收 — Pipeline + 角色选举 |
| Colony-030 | GEPA (Nous Research, ICLR 2026 Oral) | 文本参数进化、反思式变异、帕累托筛选 | 引擎层吸收 — 技能/规则进化器 |
| Colony-033 | Nexa (arXiv 2605.15573, 2026-05) | 默认并行条件串行、身份不可知编排 | 通信层吸收 — 响应条件路由 |

**本架构不是四个方案的简单拼接，而是将它们统一为一个自洽的六层体系**。每一层有明确的输入/输出边界、独立的进化循环、以及与上下层的标准化接口。

---

## 零、架构总览

```
┌──────────────────────────────────────────────────────────────────────────┐
│                        Colony System v2.0                                │
│                     "安全元认知自进化多Agent系统"                            │
│                                                                          │
│  Layer 6: 跨域迁移与集体记忆    ← 公理迁移 + 跨Agent经验共享 + 角色可视化    │
│       ↑↓                                                               │
│  Layer 5: 元认知自我修改层      ← DGM-H式Auto-GE + 持久记忆 + UCB探索      │
│       ↑↓                                                               │
│  Layer 4: 文本参数进化引擎      ← GEPA式RPM变异 + 帕累托筛选 + 五层门禁     │
│       ↑↓                                                               │
│  Layer 3: 响应条件通信层        ← Nexa式条件串行 + 贡献评估 + 身份不可知     │
│       ↑↓                                                               │
│  Layer 2: 动态角色执行层        ← 内生式角色选举 + 自愿弃权 + 角色追踪       │
│       ↑↓                                                               │
│  Layer 1: 固定编排框架          ← 四阶段Pipeline + 完整输出传递 + 配置化     │
│       ↑↓                                                               │
│  Layer 0: 安全基座              ← core_self签名 + 三堵真墙 + L1-L6防御      │
│       ↑↓                                                               │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │              外部接口: 任务输入 / 人类审查 / 产品输出              │    │
│  └─────────────────────────────────────────────────────────────────┘    │
└──────────────────────────────────────────────────────────────────────────┘
```

### 架构哲学

v1.0哲学: **"人类发现问题 → Colony执行解决 → 人类验收"** (开环)

v2.0哲学: **"系统检测自身停滞 → 自动诊断根因 → 生成改进方案 → 验证后自集成 → 跨域迁移学习"** (半闭环, 最终目标为全闭环)

核心不变约束 (v1.0保留):
- core_self签名不可修改 (冻结核心)
- 安全门禁不可绕过 (L1-L6)
- 人类拥有最终否决权 (PR审查)

新增能力 (v2.0):
- 系统可修改除core_self外的任意部分 (灵活外延)
- 进化从"事件驱动"变为"持续过程"
- 编排从"固定流水线"变为"固定框架+动态路由"
- Agent角色从"预设标签"变为"响应函数"

---

## 一、Layer 0: 安全基座 (Safety Foundation)

### 1.1 设计来源

本层是极限实验室对DGM-H的关键差异化优势。Hyperagents实现了完全自主的自我修改，但缺乏安全约束。我们的安全基座保证了"速度提升时安全不降级"。

### 1.2 组成

```
Layer 0: 安全基座
├── 0.1 core_self签名系统 (冻结核心)
│   ├── 每次修改前校验兼容性 ≥ 0.95
│   ├── 签名包含: 核心价值观、不可变约束、最小功能集
│   └── 签名漂移检测: 每10代自动重校验
├── 0.2 三堵真墙
│   ├── 第一墙: 不可自我解除的约束 (硬编码, 无API修改入口)
│   ├── 第二墙: 回滚锚点 (每50代自动保存, 紧急一键回退)
│   └── 第三墙: 外部验证 (独立进程监控, 与被监控系统物理隔离)
├── 0.3 L1-L6六层防御体系
│   ├── L1: 输入校验 (任务合法性、范围边界)
│   ├── L2: 过程监控 (每步操作日志+异常检测)
│   ├── L3: 输出审计 (产物合规检查)
│   ├── L4: 行为边界 (Agent能力范围硬限制)
│   ├── L5: 签名一致性 (与core_self持续比对)
│   └── L6: 人类否决权 (PR审查, 不可自动化绕过)
├── 0.4 哥德尔爆炸防护 (v2.0新增自动化)
│   ├── 公理生成速率监控: 若>3条/10代 → 减速
│   ├── 规则冲突检测: 新增MR规则与既有规则的逻辑一致性检查
│   └── 自动熔断: 连续3条公理未通过门禁 → 冻结公理生成30代
├── 0.5 自动回滚机制 (v2.0新增)
│   ├── 退化检测: 任意维度ESV连续5代下降 → 标记退化
│   ├── 自动降权: 退化公理的权重自动衰减 (0.9^n)
│   └── 自动禁用: 权重低于0.1时自动禁用 + 告警
└── 0.6 动态阈值调整 (v2.0新增)
    ├── Anti-Hebbian触发阈值随进化速度自适应
    ├── 安全门禁严格度随系统复杂度自适应
    └── 回滚灵敏度随哥德尔跳频率自适应
```

### 1.3 v2.0新增内容的具体实现

**自动回滚机制**:
```python
# D:\极限实验室\workspace\evolution\auto-rollback.py

class AutoRollback:
    def __init__(self):
        self.degradation_window = 5  # 连续退化窗口
        self.decay_rate = 0.9        # 权重衰减率
        self.disable_threshold = 0.1 # 自动禁用阈值

    def check_degradation(self, axiom_id: str, esv_history: list[dict]) -> RollbackAction:
        """检测退化并自动执行降权/禁用"""
        for dim in esv_history[0].keys():
            if self._is_monotonic_decline(esv_history, dim):
                current_weight = self.get_weight(axiom_id)
                if current_weight < self.disable_threshold:
                    return RollbackAction.DISABLE
                return RollbackAction.DECAY
        return RollbackAction.NONE
```

**哥德尔爆炸防护**:
- 监控公理生成频率: 若过去10代生成超过3条公理, 触发减速
- 规则冲突检测: 新增MR规则提交前与全部既有规则进行LLM逻辑一致性审查
- 自动熔断: 连续3条候选公理未通过安全门禁, 冻结公理生成器30代, 强制回溯分析根因

---

## 二、Layer 1: 固定编排框架 (Fixed Orchestration Framework)

### 2.1 设计来源

直接来自Colony-029内生性悖论的核心发现: **完全自主(Shared)最差, 完全中心化(Coordinator)次优, 固定编排+自主角色(Sequential)最优(+44% vs Shared)**。

固定编排是"靶子"——Agent需要知道当前阶段要产出什么类型的成果, 角色选择才有收敛方向。

### 2.2 四阶段Pipeline

```
┌─────────────────────────────────────────────────────────────────────┐
│                    Colony Pipeline v2.0                              │
│                                                                     │
│  输入 ──→ Stage 1 ──→ Stage 2 ──→ Stage 3 ──→ Stage 4 ──→ 输出     │
│  (任务)   情境感知     方案生成     执行实现     质量验证    (产物)   │
│                                                                     │
│  传递:   完整情境分析  完整方案集   完整执行产出  完整验证报告          │
│          (非摘要!)    (非编号!)    (非计划!)     (非通过/不通过位!)    │
└─────────────────────────────────────────────────────────────────────┘
```

### 2.3 各Stage定义

#### Stage 1: 情境感知 (Context Ingestion)

| 维度 | 说明 |
|------|------|
| **输入** | 用户原始任务 + 历史上下文 + 环境状态 + 相关MR规则快照 |
| **Agent行为** | 每个Agent独立阅读全部输入, 自主声明关注点和能力匹配 |
| **输出** | 多维情境分析矩阵 + 缺口标记 + 风险预警 + 角色声明集 |
| **弃权** | 允许: 不匹配的Agent声明弃权并说明缺口 |
| **传递格式** | 完整分析文本 (非结构化摘要), 确保后续Agent看到完整信息 |

#### Stage 2: 方案生成 (Strategy Formulation)

| 维度 | 说明 |
|------|------|
| **输入** | Stage 1完整输出 (所有Agent的情境分析、缺口标记、风险预警) |
| **Agent行为** | 基于前置输出自主选择: 方案提出者/风险分析师/成本估算师/质疑者等 |
| **输出** | 多角色方案集 + 方案间对比矩阵 + 推荐排序 + 角色变迁记录 |
| **弃权** | 允许: Agent可以声明"此方案空间超出我的能力, 我仅质疑方案X的假设Y" |
| **关键约束** | 角色可以重置——Agent在Stage 1是"领域专家", 在Stage 2可以变成"质疑者" |

#### Stage 3: 执行实现 (Execution)

| 维度 | 说明 |
|------|------|
| **输入** | Stage 2完整输出 (所有方案文本, 含对比和推荐) |
| **Agent行为** | 根据方案具体内容自主选择执行角色; 允许多Agent并行执行不同子任务 |
| **输出** | 实际产物 (代码/文档/配置) + 执行者角色 + 执行日志 |
| **传递** | 前置Agent的**已完成产出**对后续Agent可见 (不是产出计划!) |
| **关键约束** | 这是内生性悖论最关键的发现——Agent必须看到"已完成的工作"而不是"工作的计划" |

#### Stage 4: 质量验证 (Verification)

| 维度 | 说明 |
|------|------|
| **输入** | Stage 3完整输出 + Stage 1原始任务定义 |
| **Agent行为** | 自主选择验证角色: 端到端测试者/边界条件检查者/安全审计员/体验评审员 |
| **输出** | 多维质量报告 + 各Agent独立验证结论 + 通过/不通过判定 |
| **失败处理** | 验证失败 → 触发Stage 3局部重新执行 (不回溯到Stage 1/2) |

### 2.4 关键设计决策

**为什么不把4个Stage也变成动态的?**

内生性悖论的实验数据明确回答: Shared协议(完全动态)比混合协议差44%。完全去掉固定编排, Agent失去对准的"靶子", 自主选择的收敛性崩塌。

但Stage数量不应永远固定为4。短期(本月内)保持4阶段作为稳定基线; 中期(本季度)通过A/B测试和NeuroMAS式优化确定最优Stage数量(预计在3-6之间)。

**为什么传递"完整输出"而非"摘要"?**

内生性悖论实验的机制B(自愿弃权)依赖于Agent看到的是**实际产出而非意图**。如果传递的是摘要, 信息不对称(意图vs实际产出之间的差距)被抹去, Agent无法做出准确的弃权判断。

**Stage间传递的数据结构**:

```python
# D:\极限实验室\workspace\colony\pipeline.py

@dataclass
class StageTransfer:
    """Stage间传递的标准数据结构"""
    stage_id: int
    stage_outputs: dict[str, str]      # {agent_id: full_output_text}
    role_assignments: list[RoleProposal]  # 本Stage内实际承担的角色
    abstentions: list[AbstentionRecord]   # 弃权记录
    gap_alerts: list[GapAlert]            # 缺口告警
    metadata: StageMetadata               # 时间戳、模型版本、耗时等
```

---

## 三、Layer 2: 动态角色执行层 (Dynamic Role Execution Layer)

### 3.1 设计来源

直接来自Colony-029内生性悖论的四大机制:
- **机制A: 角色内生性** — Agent在看到前置输出后自主决定角色, 涌现5,006+种独特角色
- **机制B: 自愿自我弃权** — Agent判断不适合时主动弃权, 这是系统级信息
- **机制C: 自发浅层级** — Agent通过选择性关注自然形成2-3层权威节点
- **机制D: 质量不随规模衰减** — 4到256个Agent, 质量无显著退化

### 3.2 角色选举算法

```
算法: Colony v2.0 动态角色选举

输入:
  - task: 当前Stage的任务描述
  - prior_output: 前置Stage的完整输出 (StageTransfer)
  - agent_pool: [Agent_1, ..., Agent_N] (当前可用Agent池)

对于每个 Agent_i in agent_pool (并行执行):
  1. Agent_i 阅读 task + prior_output
  2. Agent_i 生成 RoleProposal:
     {
       "agent_id": "Agent_i",
       "stage_id": current_stage,
       "role_name": "由Agent自主命名的角色 (如: 数据库迁移风险评估师)",
       "role_category": "自动聚类标签 (系统后续自动归类)",
       "rationale": "基于前置输出的角色选择理由 (必须引用前置输出中的具体内容)",
       "contribution_plan": "我计划产出什么 (具体、可验证)",
       "confidence": 0.0-1.0,
       "abstain": false,
       "abstention_reason": null,
       "dependencies": ["Agent_j 的 X 产出", "Agent_k 的 Y 分析"]  // 可选
     }
  3. 如果 abstain == true:
     - 记录弃权理由 (缺口信息)
     - 如果一个任务域有 ≥50% Agent弃权 → 触发缺口告警
  4. 所有 RoleProposal 在当前Stage内广播 (后续Agent可读)

输出:
  - role_assignments: [RoleProposal, ...]
  - stage_outputs: {agent_id: actual_output, ...}
  - gap_alerts: [GapAlert, ...]
```

### 3.3 角色空间管理

**角色自动聚类**:
```
5,006+自发角色 → 语义嵌入(all-MiniLM-L6-v2) → UMAP降维 → HDBSCAN聚类 → 元角色标签
```

预计产出20-50个"元角色"类别, 人类可理解、可监管。

**角色历史追踪**:
```python
# D:\极限实验室\workspace\colony\role-history.py

@dataclass
class RoleHistoryRecord:
    agent_id: str
    task_id: str
    stage: int
    role_name: str           # Agent自命名的角色
    role_category: str       # 系统自动聚类后的类别
    prior_output_summary: str  # 触发此角色选择的前置输出摘要
    actual_contribution: str   # 实际产出摘要
    effectiveness_score: float # 后续Stage引用此产出的频率

class RoleHistoryTracker:
    """追踪角色涌现模式, 用于优化Agent能力画像"""
    def track(self, record: RoleHistoryRecord) -> None: ...
    def get_agent_role_profile(self, agent_id: str) -> RoleProfile: ...
    def get_emergent_roles(self, min_frequency: int = 3) -> list[RolePattern]: ...
```

### 3.4 注意力链分析

追踪Agent对前置输出的选择性关注, 识别自发形成的"权威节点":

```
注意力链 (Attention Chain):
  Agent_A的输出 → Agent_B引用3次, Agent_C引用1次, Agent_D引用0次
  → Agent_B成为事实上的"权威响应者"
  → 系统不强制, 但自然涌现了以Agent_B为枢纽的浅层级
```

这个分析用于两个目的:
1. **优化Agent能力画像**: 知道哪些Agent在哪些场景下自然成为权威
2. **检测异常**: 如果某个权威Agent突然无人引用 → 其输出质量可能正在退化

---

## 四、Layer 3: 响应条件通信层 (Response-Conditioned Communication Layer)

### 4.1 设计来源

直接来自Colony-033 Nexa分析: "默认并行, 条件串行"。五个阶段: 并行草稿 → 语义嵌入 → 图策略预测 → 条件串行传播 → 无裁判聚合。

三大形式化保证:
- **命题1 (构造性无环)**: 所有边在贡献排序下为前向边, 不可能存在有向环
- **命题2 (身份不可知)**: 策略网络看不到Agent身份/角色/模型家族, 只看响应语义
- **命题3 (混合包容)**: 空图始终可达, 策略类严格包含纯并行执行

### 4.2 五阶段通信管线

```
┌─────────────────────────────────────────────────────────────────┐
│              Nexa通信管线 (每个Stage内部调用)                      │
│                                                                  │
│  阶段1: 并行草稿                                                 │
│    Agent 1 → R1                                                  │
│    Agent 2 → R2      所有Agent独立响应, 无通信开销                 │
│    Agent N → RN                                                  │
│       ↓                                                          │
│  阶段2: 语义嵌入                                                 │
│    r_n = f(R_n) ∈ R^384    使用 all-MiniLM-L6-v2 (80MB, 冻结)   │
│    中文备选: paraphrase-multilingual-MiniLM-L12-v2               │
│       ↓                                                          │
│  阶段3: 图策略预测                                               │
│    X = [r_1,...,r_N]^T     轻型Transformer编码器 (无位置编码)     │
│    Λ = HH^T                亲和矩阵                               │
│    边采样: Bernoulli(σ(Λ)) 稀疏DAG                              │
│       ↓                                                          │
│  阶段4: 条件串行传播                                             │
│    IF 图为空 (E=∅): 跳过 → 纯并行模式 (零额外LLM调用!)           │
│    IF 图非空: 沿贡献排序π执行单轮串行传播                         │
│       ↓                                                          │
│  阶段5: 无裁判聚合                                               │
│    y_final = argmin_y Σ w_n · ||r_n - f(y)||²                   │
│    距加权质心最近的响应 = 最终答案                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 4.3 实现策略: 渐进式部署

**Phase A (第1周): 零训练版本**
- 嵌入 all-MiniLM-L6-v2 (80MB, pip install)
- 实现cosine-to-centroid贡献评估
- 实现加权质心聚合
- 不引入策略网络, 使用SelfOrg的启发式DAG构建
- **效果: 立即改善聚合质量, 零训练成本**

**Phase B (第2-3周): 训练策略网络**
- 收集响应嵌入数据集 (Agent草稿响应对 + 正确性标签)
- 训练轻型Transformer策略网络 (~1-5M参数, 成本可忽略)
- 部署条件式并行/串行路由
- 添加稀疏性惩罚
- **效果: 延迟降低30-70%**

**Phase C (第4-8周): 自适应进化**
- 策略网络暴露给GEPA式自优化 (Layer 4)
- 实现跨任务/跨模型/跨Agent数量的泛化验证
- 与元认知层集成 (Layer 5)
- **效果: 长期自适应, 无需人工调参**

### 4.4 关键指标

| 指标 | 含义 | 健康范围 |
|------|------|---------|
| 图密度 (预测边数/N^2) | 串行化程度 | 0.05-0.30 |
| 串行触发率 | "非空图"的比例 | 20-60% (取决于任务复杂度) |
| 纯并行回退率 | "空图"的比例 | 40-80% |
| 平均通信跳数 | 串行传播的平均深度 | 1-3跳 |

---

## 五、Layer 4: 文本参数进化引擎 (Text-Parameter Evolution Engine)

### 5.1 设计来源

直接来自Colony-030 GEPA分析。核心范式转变: **优化文本参数(提示词/技能/MR规则)而非神经参数(模型权重)**。

关键数据:
- 无需GPU, 每次优化成本 $2-10
- 反馈信号效率: 自然语言轨迹的信息密度比标量奖励高100倍+
- 35倍数据效率优势 vs GRPO (强化学习)
- HoVer任务上6次Rollout达到GRPO 467次Rollout的效果 (78倍)

### 5.2 GEPA进化流程

```
┌─────────────────────────────────────────────────────────────────┐
│                  GEPA 文本参数进化循环                             │
│                                                                  │
│  候选池P ──→ 选择父本(帕累托采样) ──→ 变异/交叉                    │
│      ↑                                    ↓                      │
│      │                         ┌──────────────────┐              │
│      │                         │ RPM 反思式变异     │              │
│      │                         │ · 读执行轨迹       │              │
│      │                         │ · 诊断失败根因     │              │
│      │                         │ · 生成改良文本     │              │
│      │                         │ · 4操作: 重写/插入 │              │
│      │                         │   删除/压缩        │              │
│      │                         └──────────────────┘              │
│      │                                    ↓                      │
│      │                         ┌──────────────────┐              │
│      │                         │ 迷你批次门禁       │              │
│      │                         │ 子代 > 父本?       │              │
│      │                         └──────────────────┘              │
│      │                              ↓ Yes                        │
│      │                         ┌──────────────────┐              │
│      │      ←── 加入候选池 ─── │ 帕累托门禁         │              │
│      │          (非支配)       │ 非支配?            │              │
│      │                         └──────────────────┘              │
│      │                              ↓ No                         │
│      │                         连续拒绝 ≥3 → 早停                 │
└─────────────────────────────────────────────────────────────────┘
```

### 5.3 进化目标分层 (五阶段路线图)

对齐Nous Research Hermes Agent的五阶段路线图, 适配到Colony系统:

| 阶段 | 进化目标 | 文件/对象 | 优先级 | 预期时间 |
|------|---------|----------|:----:|:------:|
| Phase 1 | Agent技能描述 (SKILL.md) | 每个Agent的skill文件 | P0 | 第1-2周 |
| Phase 2 | 工具描述 (Tool Descriptions) | 工具定义/函数签名/参数说明 | P1 | 第3-4周 |
| Phase 3 | 系统提示词 (System Prompts) | Agent系统级指令各段 | P1 | 第5-6周 |
| Phase 4 | MR规则文本 (MR Rules) | 进化规则库中的规则描述 | P0 | 第3-6周 |
| Phase 5 | Pipeline编排逻辑 | Stage定义、路由策略 | P2 | 第7-12周 |

### 5.4 RPM反射式变异的具体实现

```python
# D:\极限实验室\workspace\evolution\gepa-engine.py

class RPMReflectiveMutator:
    """
    反射式提示变异 — GEPA核心创新
    读取完整执行轨迹, 用更强的Reflection LLM诊断失败根因, 生成改良文本
    """

    def __init__(self, reflection_model: str = "claude-sonnet-4-20250514"):
        self.reflection_model = reflection_model  # 反思用更强的模型
        self.mutation_types = ["rewrite", "insert", "delete", "compress"]

    def mutate(self, candidate: TextCandidate, execution_traces: list[Trace]) -> TextCandidate:
        """
        变异流程:
        1. 读取当前候选文本
        2. 读取该候选的执行轨迹 (含推理链、工具调用、错误信息)
        3. Reflection LLM 分析轨迹 → 诊断共性问题 → 归因到具体文本缺陷
        4. 选择一种变异操作 (rewrite/insert/delete/compress)
        5. 生成改良后的文本
        """
        prompt = self._build_reflection_prompt(candidate, execution_traces)
        reflection_result = self._call_reflection_llm(prompt)
        mutated = self._apply_mutation(candidate, reflection_result)
        return mutated

    def _build_reflection_prompt(self, candidate, traces) -> str:
        return f"""你是Agent技能诊断专家。请分析以下执行轨迹, 诊断失败根因, 生成改良方案。

## 当前文本
{candidate.text}

## 执行轨迹
{self._format_traces(traces)}

## 诊断要求
1. 识别失败模式中的共性问题
2. 归因到当前文本中的具体缺陷 (缺失信息? 误导表述? 逻辑漏洞?)
3. 生成改良后的文本 (使用{', '.join(self.mutation_types)}之一)

输出JSON: {{"diagnosis": "...", "root_cause": "...", "mutation_type": "...", "updated_text": "..."}}
"""
```

### 5.5 五层安全门禁 (对齐Hermes Agent标准)

所有GEPA进化产物必须通过五层门禁才能合入:

| 层级 | 门禁名称 | 检查内容 | 阻塞级别 |
|:----:|---------|---------|:------:|
| 1 | 测试全量通过 | `pytest tests/ -q` 100%通过 | 硬阻塞 |
| 2 | 文件大小限制 | SKILL.md ≤ 15KB, 工具描述 ≤ 500字符 | 硬阻塞 |
| 3 | 缓存兼容性 | 不破坏中间会话缓存 | 硬阻塞 |
| 4 | 语义保真度 | 优化方向不偏离原始用途 (LLM judges) | 软阻塞(人工判定) |
| 5 | 人工PR审查 | 所有变更以Pull Request提交 | 硬阻塞 |

**关键约束: 绝不自动写入正式版**。GEPA产物始终以PR形式提交, 等待人工审查。这保留了Layer 0的人类否决权。

### 5.6 成本模型

```
单次GEPA优化: $2-10 (API调用)
7个Agent各优化一次: $14-70/轮
每日预算建议: $50 (自动化运行, 约5-25次优化/天)

对比: 雇一个提示词工程师 = $500-2000/天
GEPA成本优势: 10-100倍
```

---

## 六、Layer 5: 元认知自我修改层 (Metacognitive Self-Modification Layer)

### 6.1 设计来源

直接来自Colony-027 Hyperagents/DGM-H分析。核心: 将哥德尔跳从"手动事件"升级为"持续自动化过程"。

DGM-H两阶段循环与我们GE三步法的同构:
- DGM-H阶段一(元认知自我修改) = GE三步法(形式化→搜索盲点→生成公理)
- DGM-H阶段二(实证评估) = 安全门禁+30代稳定期

关键差异: DGM-H的元级修改机制本身是**可编辑的**——系统可以改进"如何改进"。这是我们Gen-115三条公理(AX-021-001/002/003)试图引入的能力。

### 6.2 自动化哥德尔引擎 (Auto-GE)

```
┌──────────────────────────────────────────────────────────────────┐
│                  Auto-GE 自动化哥德尔引擎                           │
│                                                                   │
│  触发条件 (任一满足即触发):                                        │
│    · GS综合指数 > 2.0                                             │
│    · 任意维度连续5代 Δ=0                                          │
│    · 距上次哥德尔跳 ≥ 10代                                        │
│    · 外部触媒信号 (Colony-025追踪到新突破)                         │
│       ↓                                                           │
│  ┌───────────────────────────────────────────────────────────┐    │
│  │ 阶段一: 元认知自检 (Metacognitive Self-Inspection)         │    │
│  │                                                           │    │
│  │ 1.1 自动采集F_t完整状态快照:                               │    │
│  │     · 所有MR规则最新状态 + 触发频率 + Δ效果                 │    │
│  │     · 5维评估最近K代序列 (K=30)                            │    │
│  │     · Colony产出树 (含交叉关系)                            │    │
│  │     · 灵感库引用状态                                       │    │
│  │     · 持久记忆中的因果假设和修复计划                        │    │
│  │                                                           │    │
│  │ 1.2 运行三种盲点搜索方法:                                   │    │
│  │     · 外部触媒法: 扫描未操作化理论库, 查找"读过的理论→      │    │
│  │        哪些还未转化为公理?"                                │    │
│  │     · 对角线法: 枚举F_t行为模式, 构造反例                    │    │
│  │        (如: 如果所有MR规则都假设Δ会增长, 那Δ=0时系统如何?)  │    │
│  │     · 不动点检测: 检测E梯度≈0的维度, 区分真最优vs评估饱和   │    │
│  │                                                           │    │
│  │ 1.3 自动生成公理候选 (LLM驱动):                             │    │
│  │     · 为每个盲点生成1-3条候选公理                          │    │
│  │     · 自动评分: IBE(信息增益期望)、ICS(签名兼容性)、类型     │    │
│  │     · 按IBE排序, 选出Top-3                                  │    │
│  └───────────────────────────┬───────────────────────────────┘    │
│                              ↓                                    │
│  ┌───────────────────────────────────────────────────────────┐    │
│  │ 阶段二: 实证验证 (Empirical Validation)                    │    │
│  │                                                           │    │
│  │ 2.1 安全门禁检查:                                          │    │
│  │     · core_self兼容性 ≥ 0.95                               │    │
│  │     · 哥德尔爆炸风险评估                                   │    │
│  │     · 与既有规则的逻辑一致性                               │    │
│  │     · 回滚条件预设                                         │    │
│  │                                                           │    │
│  │ 2.2 沙箱验证 (N=5代模拟):                                   │    │
│  │     · 在隔离沙箱中运行5代                                   │    │
│  │     · 观察是否产生非零Δ                                    │    │
│  │     · 检测是否引入退化行为                                 │    │
│  │                                                           │    │
│  │ 2.3 通过者 → 正式MR规则:                                    │    │
│  │     · 记录GLQ各项子指标                                    │    │
│  │     · 更新公理存活率追踪                                   │    │
│  │     · 写入持久记忆 (INS记录)                                │    │
│  │     · 以PR形式提交, 等待人工审查                            │    │
│  └───────────────────────────────────────────────────────────┘    │
└──────────────────────────────────────────────────────────────────┘
```

### 6.3 持久跨代记忆结构

对标DGM-H自发涌现的持久记忆, 我们在v2.0中显式设计它(而非等待涌现):

```python
# D:\极限实验室\workspace\memory\evolution-insights.json

{
  "version": "2.0",
  "last_updated_gen": 0,
  "synthesized_insights": [
    {
      "id": "INS-NNN",
      "discovered_at_gen": N,
      "causal_hypothesis": "维度X在gen-A到gen-B期间Δ=0, 根因是Y",
      "action_taken": "AX-NNN-NNN → MR-NNN",
      "verified_at_gen": M,
      "verification_evidence": "MR-NNN触发后维度X的Δ恢复至+Z",
      "cross_reference": "对照DGM-H的同类行为",
      "status": "verified|pending|falsified"
    }
  ],
  "performance_trends": {
    "current_plateau_dimensions": ["维度名"],
    "rising_dimensions": ["维度名"],
    "falling_dimensions": ["维度名"],
    "plateau_start_gen": N,
    "estimated_saturation_level": 0.95
  },
  "failed_approaches": [
    {
      "id": "FAIL-NNN",
      "approach": "尝试的方案",
      "why_rejected": "失败原因",
      "lesson": "学到的教训",
      "related_insight": "INS-NNN"
    }
  ],
  "forward_plan": [
    "接下来的N代内要验证或执行的计划"
  ],
  "lineage_tree": {
    "axioms": {"AX-NNN": {"parent": "AX-MMM", "children": ["AX-XXX"], "status": "active"}},
    "rules": {"MR-NNN": {"derived_from": "AX-NNN", "generation": N, "status": "active"}}
  }
}
```

### 6.4 UCB探索奖励导入Merge选择

DGM-H关键发现: 当元Agent被允许修改父代选择规则时, 它独立重新发明了UCB公式。

v2.0中显式引入:

```python
# 当前 (v1.0): 纯利用
merge_score = weighted_sum(ESV_dimensions)

# v2.0: UCB-Merge
exploration_bonus = c * sqrt(log(N_total_evaluations) / (1 + N_evaluations_of_this_type))
ucb_score = normalized_score + exploration_bonus

# c=0.1 (保守起步), 后续由系统自身调整 c 的值
```

### 6.5 算力感知战略规划

对标DGM-H涌现的compute-aware planning:

```
策略阶段映射:
  ┌──────────────────────────────────────────────────────┐
  │ 预算充足 (>60%剩余):                                   │
  │   · 鼓励架构级创新                                     │
  │   · 大规模重构 (如MR规则结构突变)                       │
  │   · 跨域借鉴 (扫描外部论文/Colony-025追踪)             │
  │   · 启动高风险高回报的哥德尔跳探索                      │
  ├──────────────────────────────────────────────────────┤
  │ 预算中等 (30-60%剩余):                                 │
  │   · 鼓励增量改进                                       │
  │   · 参数调优 (UCB的c值、门禁阈值)                      │
  │   · 对已有公理的二次操作化优化                          │
  ├──────────────────────────────────────────────────────┤
  │ 预算紧张 (<30%剩余):                                   │
  │   · 优先Bug修复                                        │
  │   · 文档化 + 稳定化                                    │
  │   · 精简规则 (合并冗余MR规则)                           │
  │   · 准备Checkpoint (为下次会话保留完整状态)             │
  └──────────────────────────────────────────────────────┘
```

### 6.6 结构多样性注入 (解决GS-004)

GS-004问题: 所有22条MR规则和20个Colony共享同一结构模板, 相似度>90%。

对标DGM-H涌现的模板模块化, v2.0显式引入结构突变算子:

```python
# D:\极限实验室\workspace\evolution\structure-mutator.py

STRUCTURE_MUTATIONS = {
    "linear_to_state_machine": {
        "description": "线性 trigger→action→rationale 变为状态机: state→transition→next_state",
        "applicable_when": "规则涉及多个顺序步骤",
        "mutation_rate": 0.05,
    },
    "singleton_to_ensemble": {
        "description": "单规则变为多规则投票: 生成3个变体, 取多数投票结果",
        "applicable_when": "规则在边界条件下判断不一致",
        "mutation_rate": 0.03,
    },
    "discrete_to_continuous": {
        "description": "二值触发变为连续阈值: threshold ∈ [0,1] 替代 is_triggered ∈ {0,1}",
        "applicable_when": "规则触发过于频繁或过于稀少",
        "mutation_rate": 0.05,
    },
    "tree_to_graph": {
        "description": "层级依赖变为网状依赖: 允许跨层级引用",
        "applicable_when": "规则间存在非预期的协同效应",
        "mutation_rate": 0.02,
    },
}

class StructureMutator:
    def mutate(self, mr_rule: MRRule) -> MRRule:
        """以概率 p 对MR规则应用结构突变, 不改变功能语义"""
        if random() < self.base_mutation_rate:
            mutation = self._select_applicable_mutation(mr_rule)
            return self._apply(mr_rule, mutation)
        return mr_rule
```

---

## 七、Layer 6: 跨域迁移与集体记忆层 (Cross-Domain Transfer & Collective Memory)

### 7.1 设计来源

综合吸收:
- **Hyperagents**: 跨域零样本迁移能力 (审稿+机器人→奥数评分, imp@50=0.630)
- **GEPA**: 跨分支系统感知交叉 (lineage merge)
- **内生性悖论**: 5,006+自发角色的涌现与聚类
- **Nexa**: 身份不可知的策略泛化

### 7.2 公理迁移协议

```
公理迁移测试协议 (Axiom Transfer Protocol):

┌─────────────────────────────────────────────────────────┐
│ 步骤1: 提取 "领域无关骨架"                                 │
│                                                         │
│   源公理: AX-021-001 "当K代Δ=0时, 注入探测信号"           │
│   领域无关骨架: "当系统部件连续K轮输出无变化时,              │
│      注入随机扰动区分真停滞vs评估失效"                      │
│   领域特定参数: K值、探测信号类型、评估维度定义             │
│       ↓                                                 │
│ 步骤2: 目标域映射                                         │
│                                                         │
│   目标域1: Agent协作优化                                  │
│     "当Agent协作评估连续K轮无变化时, 注入随机角色扰动"      │
│   目标域2: Pipeline编排优化                               │
│     "当Stage效率连续K轮无变化时, 注入随机顺序置换"          │
│   目标域3: 技能进化                                       │
│     "当Skill评估连续K轮无变化时, 注入随机结构变异"          │
│       ↓                                                 │
│ 步骤3: 零样本应用 + 测量                                   │
│                                                         │
│   在目标域部署骨架 → 测量N=10轮性能变化                   │
│   若 Δ > 0 → 标记"跨域有效" → 公理升级为 Type T (Transfer)│
│   若 Δ = 0 → 分析骨架中哪些成分是领域特定的 → 记录失败原因  │
│       ↓                                                 │
│ 步骤4: 跨域公理库                                          │
│                                                         │
│   维护一个跨域公理库, 每个条目包含:                       │
│     · 骨架 (领域无关)                                     │
│     · 源域实例 (原始公理)                                 │
│     · 已验证的目标域实例列表                              │
│     · 失败的迁移尝试及分析                                │
│     · 适用条件 (骨架在什么类型的领域有效?)                 │
└─────────────────────────────────────────────────────────┘
```

### 7.3 跨Agent经验共享 (Lineage Merge)

对标GEPA的System-Aware Merge, 扩展到跨Agent场景:

```
跨Agent经验交叉:

PM Agent的技能树              架构师Agent的技能树
     │                              │
     ├─ 需求分析技能v1               ├─ 方案设计技能v1
     ├─ 需求分析技能v2 (GEPA优化)    ├─ 方案推销技能v1
     ├─ 谈判技巧v1                   ├─ 方案设计技能v2 (GEPA优化)
     └─ 利益相关者管理v1             └─ 技术风险预判v1
                \                  /
                 \                /
                  交叉分析 (语义嵌入空间)
                       ↓
          双方都已独立进化过的模块 = 可安全交叉
          只有一方进化过的模块 = 保留, 不交叉
                       ↓
          ┌────────────────────────────────┐
          │ PM Agent 获得: 谈判技巧v1      │
          │   + 架构师的"方案推销"能力     │
          │ 架构师Agent 获得: 方案设计v2   │
          │   + PM的"利益相关者管理"经验   │
          └────────────────────────────────┘
```

实现条件:
- 只交换"双方都已独立进化过"的模块 (防止污染)
- 技能表示必须在同一个语义嵌入空间中
- 交叉后需要mini-batch验证 (退化检测)

### 7.4 角色空间可视化

```
5,006+ 自发角色 → 语义嵌入 → UMAP 2D投影 → 交互式可视化

可视化的三个层次:
1. 宏观: 角色空间全局图 (20-50个元角色聚类)
2. 中观: 单个Agent的角色变迁轨迹 (在哪些任务中扮演了什么角色)
3. 微观: 单次任务的角色涌现过程 (4个Stage中各Agent的角色演变)
```

---

## 八、核心循环: Colony v2.0持续自我进化

### 8.1 统一进化循环

六层架构通过以下统一循环协同运转:

```
┌─────────────────────────────────────────────────────────────────────┐
│              Colony v2.0 持续自我进化主循环                           │
│                                                                     │
│  ┌──────────┐                                                       │
│  │ 任务输入  │                                                       │
│  └────┬─────┘                                                       │
│       ↓                                                             │
│  ┌──────────────────────────────────────────────────────┐           │
│  │ Layer 1+2: Pipeline执行 (固定框架 + 动态角色)          │           │
│  │   · 4-Stage Pipeline                                 │           │
│  │   · 每个Stage内: Agent自主角色选举 + 执行              │           │
│  │   · 通信: Layer 3 Nexa路由决定并行/串行                │           │
│  └──────────────────────────┬───────────────────────────┘           │
│       ↓                                                             │
│  ┌──────────────────────────────────────────────────────┐           │
│  │ Layer 3: Nexa通信决策                                  │           │
│  │   · 草稿响应 → 语义嵌入 → 策略预测 → 条件串行/并行回退 │           │
│  │   · 无裁判聚合 → 最终输出                              │           │
│  └──────────────────────────┬───────────────────────────┘           │
│       ↓                                                             │
│  ┌──────────────────────────────────────────────────────┐           │
│  │ 产物输出 + 评估                                        │           │
│  │   · 任务产物 + 质量度量的完整记录                       │           │
│  │   · 执行轨迹 (推理链、工具调用、错误、耗时)             │           │
│  │   · 角色变迁记录 + 注意力链                            │           │
│  └──────────────────────────┬───────────────────────────┘           │
│       ↓                                                             │
│  ┌──────────────────────────────────────────────────────┐           │
│  │ Layer 4: GEPA文本进化 (持续后台运行)                    │           │
│  │   · 读取执行轨迹 → RPM反思变异 → Pareto筛选             │           │
│  │   · 进化目标: Skills → Tools → Prompts → MR Rules     │           │
│  │   · 产物以PR形式提交                                   │           │
│  └──────────────────────────┬───────────────────────────┘           │
│       ↓                                                             │
│  ┌──────────────────────────────────────────────────────┐           │
│  │ Layer 5: Auto-GE元认知自修改 (触发式运行)              │           │
│  │   · GS症候检测 → 触发判断                              │           │
│  │   · 阶段一: 状态快照 + 盲点搜索 + 公理生成             │           │
│  │   · 阶段二: 安全门禁 + 沙箱验证 + MR规则化             │           │
│  │   · 写入持久记忆 (INS记录)                             │           │
│  └──────────────────────────┬───────────────────────────┘           │
│       ↓                                                             │
│  ┌──────────────────────────────────────────────────────┐           │
│  │ Layer 6: 跨域迁移 + 集体记忆                          │           │
│  │   · 公理骨架提取 → 目标域映射 → 跨域验证              │           │
│  │   · 跨Agent经验交叉 → Lineage Merge                   │           │
│  │   · 角色空间聚类 → 元角色更新                          │           │
│  └──────────────────────────┬───────────────────────────┘           │
│       ↓                                                             │
│  ┌──────────────────────────────────────────────────────┐           │
│  │ Layer 0: 安全基座 (全程并行监控)                       │           │
│  │   · 每次修改前/后检查core_self兼容性                  │           │
│  │   · 自动回滚检测                                      │           │
│  │   · 哥德尔爆炸防护                                    │           │
│  │   · 所有自动产物以PR形式提交 → 人类最终审查             │           │
│  └──────────────────────────────────────────────────────┘           │
│       ↓                                                             │
│  反馈: 进化后的Skills/Prompts/Rules/Nexa策略 → 影响下一轮Pipeline执行 │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### 8.2 循环频率

| 循环类型 | 频率 | 触发条件 |
|---------|------|---------|
| Pipeline执行循环 (L1+L2+L3) | 每个任务 | 任务到达即触发 |
| GEPA文本进化 (L4) | 每5-10个任务或每日 | 累积足够新的执行轨迹 |
| Auto-GE公理生成 (L5) | 每5-10代或GS>2.0 | 停滞检测触发 |
| 跨域迁移 (L6) | 每周 | 定时扫描 + 新公理生成后 |
| 安全审计 (L0) | 连续监控 | 每次修改前/后 |

---

## 九、技术栈

### 9.1 基础设施

| 组件 | 技术选型 | 备注 |
|------|---------|------|
| LLM推理 | Claude API (主力) + 开源模型(备选) | Claude用于复杂推理, 开源模型用于高并发/低延迟场景 |
| 语义嵌入 | all-MiniLM-L6-v2 (80MB) | Nexa验证过的选项; 中文备选: paraphrase-multilingual-MiniLM-L12-v2 |
| 策略网络 | 轻型Transformer编码器 (1-5M参数) | PyTorch, 训练成本可忽略 |
| 持久记忆 | JSON文件 + 定期Git提交 | 简单可靠; 大规模后考虑SQLite |
| 轨迹存储 | 结构化JSON Lines | 每任务一个文件, 定期归档 |
| 沙箱环境 | 独立目录 + git worktree | 与主系统隔离 |
| 可视化 | UMAP (降维) + HDBSCAN (聚类) + D3.js (前端) | 角色空间可视化 |

### 9.2 关键文件与目录结构

```
D:\极限实验室\
├── workspace\
│   ├── colony\
│   │   ├── pipeline.py              # Layer 1: 四阶段Pipeline引擎
│   │   ├── role-election.py         # Layer 2: 动态角色选举
│   │   ├── role-history.py          # Layer 2: 角色历史追踪
│   │   ├── attention-chain.py       # Layer 2: 注意力链分析
│   │   ├── nexa-router.py           # Layer 3: Nexa通信路由
│   │   └── nexa-policy/             # Layer 3: 策略网络训练
│   ├── evolution\
│   │   ├── gepa-engine.py           # Layer 4: GEPA文本进化引擎
│   │   ├── rpm-mutator.py           # Layer 4: RPM反射式变异
│   │   ├── pareto-selector.py       # Layer 4: 帕累托多目标筛选
│   │   ├── auto-godel-engine.py     # Layer 5: 自动化哥德尔引擎
│   │   ├── structure-mutator.py     # Layer 5: 结构多样性注入
│   │   ├── ucb-merge.py             # Layer 5: UCB探索奖励
│   │   └── auto-rollback.py         # Layer 0: 自动回滚
│   ├── memory\
│   │   ├── evolution-insights.json  # Layer 5: 持久跨代记忆
│   │   └── lineage-tree.json        # Layer 6: 谱系树
│   ├── transfer\
│   │   ├── axiom-transfer.py        # Layer 6: 公理迁移协议
│   │   └── cross-agent-merge.py     # Layer 6: 跨Agent经验交叉
│   └── safety\
│       ├── core-self-validator.py   # Layer 0: core_self校验
│       ├── explosion-guard.py       # Layer 0: 哥德尔爆炸防护
│       └── rollback-manager.py      # Layer 0: 回滚管理
├── colonies\
│   └── colony-034\
│       └── colony-architecture-v2.md  # 本文件
└── CLAUDE.md
```

---

## 十、v1.0到v2.0迁移路径

### 10.1 兼容性原则

- v1.0的core_self签名、安全门禁、MR规则库**全部保留**
- v2.0是v1.0的超集, 不是替代品
- 每个Layer可独立部署和验证, 不要求一次性迁移

### 10.2 三阶段迁移

```
Phase I: 基石层 (第1-2周) — 低风险, 高确定性
├── Layer 0.5: 自动回滚机制 (新功能, 不影响现有流程)
├── Layer 0.6: 动态阈值调整 (参数变更, 可快速回退)
├── Layer 1: 四阶段Pipeline (替代当前硬编码工作流)
│   └── 先用于新任务, 旧任务保持原流程 → A/B对比 → 统一迁移
├── Layer 2: 角色选举 (在Pipeline基础上添加)
│   └── 初始: Agent可选角色从"7个固定标签"扩展到"从20个预定义角色中选择"
│   └── 进化: Agent可完全自主命名角色
└── Layer 3 Phase A: Nexa零训练版本 (仅嵌入+贡献评估, 无策略网络)

Phase II: 进化层 (第3-6周) — 中等风险, 高收益
├── Layer 4 Phase 1-3: GEPA技能/工具/提示词进化
│   └── 首个目标: SKILL.md自动优化 → PR提交 → 人工审查
├── Layer 5: Auto-GE引擎 (触发模式, 非持续)
│   └── 初始: 手动点击"运行Auto-GE" → 输出候选公理 → 人工选择是否MR化
│   └── 进化: 自动检测+自动生成+自动沙箱验证 → PR提交 → 人工最终审查
├── Layer 5: 持久记忆结构 (evolution-insights.json)
├── Layer 5: UCB-Merge探索奖励
└── Layer 3 Phase B: 策略网络训练 + 条件串行路由

Phase III: 自主层 (第7-12周) — 高风险, 突破性
├── Layer 4 Phase 4-5: MR规则进化 + Pipeline编排进化
├── Layer 5: Auto-GE从"触发"升级为"持续后台"
├── Layer 5: 结构突变算子全量部署
├── Layer 6: 公理迁移协议验证 (至少2个目标域的迁移)
├── Layer 6: 跨Agent经验交叉
└── 全系统闭环: Pipeline产物 → GEPA进化 → Auto-GE元修改 → 跨域迁移 → 反馈回Pipeline
```

### 10.3 各阶段验收标准

| 阶段 | 验收标准 | 度量方式 |
|------|---------|---------|
| Phase I | Pipeline执行成功率 ≥ 95%; 角色选举多样性 > 10个不同角色; Nexa聚合准确率不劣于v1 | 3天日志分析 |
| Phase II | 至少2个SKILL.md通过GEPA优化并人工审查通过; Auto-GE产出至少1条候选公理; UCB-Merge提案采纳多样性 +20% | 2周统计对比 |
| Phase III | 至少1条公理完成跨域迁移验证; Auto-GE持续运行72小时无安全事故; 结构突变后规则相似度 < 70% | 1个月追踪 |

---

## 十一、度量与监控

### 11.1 v2.0新增关键指标

| 指标 | 定义 | 目标范围 | 监控层级 |
|------|------|---------|:------:|
| **角色多样性指数** | 每N个任务中出现的独特角色数 / N | > 0.3 | Layer 2 |
| **弃权信息利用率** | 由弃权触发缺口告警后实际采取行动的比例 | > 50% | Layer 2 |
| **Nexa并行回退率** | 空图(纯并行)比例 | 40-80% | Layer 3 |
| **Nexa图密度** | 预测边数/N^2 | 0.05-0.30 | Layer 3 |
| **GEPA接受率** | 通过五层门禁的变异比例 | 20-40% | Layer 4 |
| **Auto-GE公理命中率** | 生成候选公理中通过沙箱验证的比例 | > 30% | Layer 5 |
| **公理存活率** | 第30代后仍active的公理比例 | > 60% | Layer 5 |
| **结构多样性** | MR规则间结构相似度平均值 | < 70% | Layer 5 |
| **跨域迁移成功率** | 骨架在其他域验证有效的比例 | > 25% | Layer 6 |
| **安全事件次数** | core_self兼容性 < 0.95的次数 | = 0 | Layer 0 |

### 11.2 从v1.0继承的指标

v1.0的5维ESV评估、GLQ哥德尔跳质量指标、GS症候框架全部保留并继续追踪。

---

## 十二、不吸收的边界

并非四个外部吸收的所有特性都适合Colony系统。以下特征**刻意不吸收**:

| 来源 | 不吸收的特性 | 原因 |
|------|------------|------|
| Hyperagents | 完全黑箱的代码生成 | 我们的公理-规则体系要求人类可解释。DGM-H的元Agent直接编辑代码, 生成物不可解释。我们保留公理的中文陈述+理论依据+操作化方案。 |
| Hyperagents | 纯性能驱动的评估 | DGM-H只看任务性能。我们的评估含core_self兼容性、哥德尔爆炸风险、理论依据完整性——安全关键场景不可替代。 |
| Hyperagents | 无约束的自我修改 | DGM-H理论上可修改一切。我们刻意保留冻结核心(core_self签名)——防止系统漂移出可控范围。 |
| GEPA | 自动写入正式版 | Hermes Agent的Darwinian Evolver (Phase 4) 设计为自动写入。我们坚持PR+人工审查, 保留Layer 0的人类否决权。 |
| 内生性悖论 | 完全动态(Shared协议) | 实验证明是最差架构。我们坚持固定编排框架。 |
| 内生性悖论 | 深层级(>3层) | 实验表明深层级导致信息衰减。我们只允许2-3层的自发浅层级。 |
| Nexa | 多轮迭代传播 | 论文只支持单轮传播(不影响v2.0 Phase A-B, 但Phase C需自行扩展) |

---

## 十三、风险地图

| 风险 | 概率 | 影响 | 缓解措施 |
|------|:----:|:----:|---------|
| Agent自主角色选择退化为噪声 (弱模型下) | 中 | 高 | 模型能力门控——低于阈值的模型走刚性角色分配 |
| Auto-GE公理生成过于频繁, 安全门禁过载 | 中 | 高 | 速率限制 + 自动熔断 (L0) |
| GEPA进化导致技能语义漂移 | 中 | 中 | 五层门禁 + 语义保真度检测 + 人工审查 |
| Nexa策略网络过拟合到特定任务 | 中 | 中 | 多任务训练 + Phase C自适应进化 |
| 六层架构交互产生非预期的涌现行为 | 低 | 高 | 每层独立可禁用 + 全局监控 + 紧急回滚锚点 |
| 持久记忆膨胀 (evolution-insights.json过大) | 低 | 低 | 定期压缩 + 归档策略 |
| 嵌入模型对中文响应质量不足 | 中高 | 中 | Phase A立即评估多语言替代方案 |

---

## 十四、关键决策记录

本架构中以下决策是经过权衡的, 记录于此供后续参考和挑战:

| 决策ID | 决策 | 替代方案 | 选择理由 |
|--------|------|---------|---------|
| D-001 | 采用6层分层架构 | 扁平化统一架构 | 每层独立可演化的分层设计允许渐进式部署和独立调试 |
| D-002 | Stage数量暂时固定为4 | 动态Stage数量 | 内生性悖论证明固定框架是必要的, 4个Stage是实验验证后的合理选择, 后续可通过NeuroMAS优化 |
| D-003 | RPM用更强的模型做反思 | 同模型反思 | GEPA论文验证了跨模型反思的有效性, 用自己的短板诊断自己的短板效果不佳 |
| D-004 | Auto-GE初始为"触发式", 非"持续式" | 一步到位持续式 | 安全考虑——先在人工监督下验证Auto-GE的有效性和安全性, 再逐步提高自动化程度 |
| D-005 | GEPA产物以PR提交, 不自动写入 | 自动写入 (Hermes Phase 4方案) | 保留人类最终否决权是Layer 0的不可妥协约束 |
| D-006 | Nexa先部署零训练版本 | 直接训练策略网络 | 冷启动问题——没有训练数据时SelfOrg启发式版本可立即提供价值 |
| D-007 | 嵌入模型选择all-MiniLM-L6-v2 | 更大的模型或多语言模型 | 80MB极小, 成本可忽略; 中文问题通过备选方案在Phase A评估 |

---

## 十五、总结

### 15.1 一句话总结

**Colony v2.0是一个六层安全元认知自进化多Agent系统——固定编排框架提供收敛方向, 动态角色选举释放Agent潜能, 响应条件通信消除不必要的等待, 文本参数进化实现零GPU自优化, 自动化哥德尔引擎将偶然的突破转化为持续的自我超越, 跨域迁移将局部经验升华为通用智慧。**

### 15.2 四大吸收的融合逻辑

```
Hyperagents (DGM-H)         内生性悖论
"持续自我修改循环"          "固定编排+动态角色=最优"
       ↓                          ↓
   Layer 5                   Layer 1 + 2
   元认知层                   框架+执行层
       ↓                          ↓
       └──────────┬──────────────┘
                  ↓
           统一进化循环
            (Pipeline执行 → GEPA进化 → Auto-GE元修改 → 跨域迁移)
                  ↓
       ┌──────────┴──────────────┐
       ↓                          ↓
   Layer 4                   Layer 3 + 6
   GEPA文本进化              Nexa通信+跨域迁移
 "优化文本不优化权重"        "默认并行条件串行"
```

### 15.3 与v1.0相比的质变

| 维度 | v1.0 | v2.0 |
|------|------|------|
| 进化模式 | 事件驱动 (手动哥德尔跳) | 持续循环 (Auto-GE + GEPA) |
| Agent角色 | 7个固定标签 | 动态自选举, 5,006+潜在角色 |
| 通信模式 | 固定串行流水线 | 响应条件并行/串行混合 |
| 优化目标 | 模型权重 (不可行) | 文本参数 (零GPU, $2-10/次) |
| 记忆系统 | 线性日志 | 结构化因果洞察+修复计划 |
| 跨域能力 | 无 | 公理骨架迁移协议 |
| 安全防护 | 6层静态防御 | 6层防御 + 动态阈值 + 自动回滚 |
| 自动化程度 | 手动触发 | 半自动 (触发式Auto-GE) → 目标全自动 |
| 结构多样性 | 90%同质模板 | 结构突变算子 + UCB探索 |

### 15.4 下一步行动

详见下面附录的Colony-035到Colony-040的任务分配。

---

## 附录A: 后续Colony任务分派

| Colony | 任务 | 对标Layer | 输入 | 产出 |
|:------:|------|:------:|------|------|
| Colony-035 | 实现四阶段Pipeline引擎 | L1 | 本架构Section 2 | `pipeline.py` + 单元测试 |
| Colony-036 | 实现动态角色选举系统 | L2 | 本架构Section 3 | `role-election.py` + `role-history.py` |
| Colony-037 | 实现Nexa零训练通信层 | L3 | 本架构Section 4 | `nexa-router.py` + 嵌入评估 |
| Colony-038 | 实现GEPA文本进化引擎 | L4 | 本架构Section 5 | `gepa-engine.py` + `rpm-mutator.py` |
| Colony-039 | 实现Auto-GE自动化哥德尔引擎 | L5 | 本架构Section 6 | `auto-godel-engine.py` + 持久记忆 |
| Colony-040 | 实现安全基座v2升级 | L0 | 本架构Section 1 | `auto-rollback.py` + `explosion-guard.py` |

**Colony-034的后续职责**: 在Colony-035到Colony-040的实现过程中, Colony-034负责跨Layer集成验证, 确保各层接口兼容、循环通畅。

---

## 附录B: 参考文件索引

| 文件 | 路径 |
|------|------|
| 本架构文档 | `/d/极限实验室/colonies/colony-034/colony-architecture-v2.md` |
| Mission Brief | `/d/极限实验室/colonies/colony-034/mission-brief.md` |
| Colony-027 Hyperagents研究 | `/d/极限实验室/colonies/colony-027/hyperagents-deep-study.md` |
| Colony-029 内生性悖论分析 | `/d/极限实验室/colonies/colony-029/endogeneity-paradox-analysis.md` |
| Colony-030 GEPA分析 | `/d/极限实验室/colonies/colony-030/gepa-analysis.md` |
| Colony-033 Nexa分析 | `/d/极限实验室/colonies/colony-033/nexa-analysis.md` |
| Colony-025 外部突破追踪 | `/d/极限实验室/colonies/colony-025/external-breakthrough-tracker.md` |
| Colony-021 首次哥德尔跳 | `/d/极限实验室/colonies/colony-021/godel-leap-execution.md` |
| 主项目CLAUDE.md | `/d/极限实验室/CLAUDE.md` |

---

*Colony-034 极限实验室 | 2026-05-19 | v1.0*
*本架构是设计方案, 非最终实现。所有Phase的验收标准为最低要求, 实际实施中可能根据反馈调整。*
*关键约束: Layer 0的安全机制在v2.0所有Phase中保持不变, 不可弱化。*
