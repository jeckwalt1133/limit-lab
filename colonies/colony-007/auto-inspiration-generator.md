# 自动跨领域灵感生成器 (Auto-Inspiration Generator)

## 元信息
- 设计者: Colony-007
- 版本: v1.0
- 日期: 2026-05-19
- 基于: 21条手动灵感 + 14篇参考文档的方法论提炼

---

## 一、方法论溯源：21条灵感中隐藏的生成模式

通过对今日手动产生的21条灵感的逆向工程，提取出底层生成管道：

### 1.1 输入源分布
```
学术论文(arXiv/期刊):  12条 (57%)  — 灵感#5,6,7,8,9,10,11,12,13,14,15,16,17
AI行业动态:             4条 (19%)  — 灵感#1,2,3,4
神经科学文献:            2条 (10%)  — 灵感#18,19,20
科普/综述:              1条 (5%)   — 灵感#21
内部反思:               2条 (10%)  — 灵感#1,3 (双重计数)
```

### 1.2 映射结构解构
每条灵感遵循固定的三段式结构：

```
来源(SRC)  →  提取核心概念(CC)  →  映射到内部架构(MAP)  →  可行性评估(FEA)  →  行动建议(ACT)
```

具体解剖示例（灵感#5: 动态守恒）：

| 阶段 | 内容 |
|------|------|
| SRC | 剑桥大学2026年3月《科学》——植物3亿年保守基因调控图谱 |
| CC | 保守非编码序列位置可变，但相对顺序和组合逻辑高度稳定 |
| MAP | 行为签名——具体文本可变，但12条签名的相对权重和互补约束关系不能断 |
| FEA | 已有冻结签名机制(DS-001/DS-002 frozen=true)，扩展到"冻结签名间的关系" |
| ACT | 冻结签名间的关系约束，新增互补约束检查 |

### 1.3 映射类型的分类体系

从21条灵感中归纳出6种映射原型：

| 类型 | 描述 | 出现频次 | 示例 |
|------|------|----------|------|
| **结构同构** (Structural Isomorphism) | 外部系统结构与内部系统结构一一对应 | 7次 | 分形记忆(灵感#9)、量子耦合(灵感#15) |
| **机制迁移** (Mechanism Transfer) | 外部机制可直接适配到内部 | 5次 | 棘轮效应(灵感#8)、睡眠重放(灵感#18) |
| **约束映射** (Constraint Mapping) | 外部约束条件对应内部设计约束 | 3次 | 0.65米相变距离(灵感#12)、PERG策略(灵感#16) |
| **隐喻桥接** (Metaphor Bridge) | 外部概念提供新的理解框架 | 3次 | 耗散驱动(灵感#10)、噪声催化剂(灵感#14) |
| **竞争警觉** (Competitor Alert) | 外部竞争动态触发内部行动 | 2次 | 递归超级智能(灵感#3) |
| **自我发现** (Self-Discovery) | 内部机制被外部理论验证 | 1次 | 模型引擎分离(灵感#1) |

---

## 二、系统架构总览

```
                          ┌─────────────────────────────────┐
                          │       当前系统状态快照            │
                          │  (meta-rules / signatures /      │
                          │   branches / ETG status)         │
                          └──────────────┬──────────────────┘
                                         │
                          ┌──────────────▼──────────────────┐
                          │        阶段0: 状态编码            │
                          │  系统状态→结构化特征向量          │
                          │  (痛点、优势、盲区、待解决问题)    │
                          └──────────────┬──────────────────┘
                                         │
              ┌──────────────────────────┼──────────────────────────┐
              │                          │                          │
    ┌─────────▼─────────┐    ┌──────────▼──────────┐    ┌──────────▼──────────┐
    │ 阶段1: 广度扫描    │    │ 阶段1b: 深度搜索     │    │ 阶段1c: 定点监测     │
    │ (Breadth Scanner) │    │ (Depth Searcher)    │    │ (Watchdog Monitor)  │
    │                   │    │                     │    │                     │
    │ 领域轮询          │    │ 指定领域深挖        │    │ 竞争情报追踪        │
    │ 随机跳跃          │    │ 论文逐篇阅读        │    │ 顶会论文监测        │
    │ 每日摘要          │    │ 跨域关联搜索        │    │ 突发新闻捕获        │
    └─────────┬─────────┘    └──────────┬──────────┘    └──────────┬──────────┘
              │                          │                          │
              └──────────────────────────┼──────────────────────────┘
                                         │
                          ┌──────────────▼──────────────────┐
                          │        阶段2: 概念提取            │
                          │  (Concept Extractor)             │
                          │                                  │
                          │  原始文本 → 核心概念(CC)卡片      │
                          │  每张卡片: 关键发现 + 机制 +       │
                          │  适用范围 + 约束条件               │
                          └──────────────┬──────────────────┘
                                         │
                          ┌──────────────▼──────────────────┐
                          │        阶段3: 映射引擎            │
                          │  (Mapping Engine) ★核心★          │
                          │                                  │
                          │  6种映射原型 × 内部架构矩阵       │
                          │  → 候选映射列表                   │
                          └──────────────┬──────────────────┘
                                         │
                          ┌──────────────▼──────────────────┐
                          │        阶段4: 质量评分            │
                          │  (Quality Scorer)                │
                          │                                  │
                          │  4维度评分 → 总质量分             │
                          │  过滤: 低于阈值则丢弃             │
                          └──────────────┬──────────────────┘
                                         │
                          ┌──────────────▼──────────────────┐
                          │        阶段5: 灵感生成            │
                          │  (Inspiration Composer)          │
                          │                                  │
                          │  候选映射 → 格式化灵感条目        │
                          │  SRC + CC + MAP + FEA + ACT      │
                          └──────────────┬──────────────────┘
                                         │
                          ┌──────────────▼──────────────────┐
                          │        阶段6: 行动路由            │
                          │  (Action Router)                 │
                          │                                  │
                          │  按优先级路由到:                   │
                          │  → ETG即时触发 (重大发现)         │
                          │  → 头脑风暴队列 (高创造性)         │
                          │  → 实验队列 (可验证)              │
                          │  → 参考库 (低优先级/存档)          │
                          └──────────────────────────────────┘
```

---

## 三、各阶段详细设计

### 阶段0: 系统状态编码

**输入**: 当前系统的完整状态

**编码维度** (状态特征向量):

```yaml
system_state_vector:
  # 元规则健康度
  meta_rules:
    total_count: 12          # MR-001 ~ MR-012
    frozen_count: 2          # DS-001, DS-002 frozen=true
    average_strength: 0.78   # 平均强度
    min_strength: 0.32       # 最弱规则强度
    conflict_zones:          # 检测到的冲突区域
      - "MR-005 vs MR-008: exploration_weight边界争议"
    
  # 行为签名状态
  signatures:
    match_rate_avg: 0.74     # 平均匹配率
    overfit_alerts:          # 连续完美匹配>5次的签名
      - "DS-003: 7次连续100%匹配 → 疑似过拟合"
    underfit_alerts:         # 匹配率<30%的签名
      - "DS-007: 匹配率仅24%"
      
  # 分支状态
  branches:
    alpha_health: 0.85       # Alpha分支健康度
    beta_health: 0.78        # Beta分支健康度
    alpha_beta_distance: 0.45  # 任务距离(理想0.3-0.7)
    pending_merges: 2        # 待合并队列
    
  # 进化状态
  evolution:
    generation: 96           # 当前代数
    days_since_last_ETG: 3   # 距上次ETG天数
    convergence_points:      # 跨分支收敛点
      - "Alpha和Beta独立得出: exploration_weight应动态化"
      
  # 能力短板
  capability_gaps:
    - "网络不通 → 无法自主搜索"
    - "缺少Memory MCP → 知识图谱断层"
    - "Alpha可操作性短板(设计→执行间隔40+代)"
    
  # 待解决问题
  open_questions:
    - "如何量化Alpha/Beta的最优任务距离"
    - "如何检测签名间的交互效应(类似SI机制)"
```

### 阶段1: 跨领域扫描子系统

#### 1A: 广度扫描 (Breadth Scanner)

**目标**: 周期性轮询各领域的新进展

**领域轮盘** (按优先级排列):
```yaml
domains:
  # 核心领域 (每轮必扫)
  - biology:          # 进化生物学、遗传学、神经科学
      keywords: [evolution, gene regulation, epigenetics, neural plasticity, 
                 stem cell, convergent evolution, self-organization]
      sources: [Nature, Science, Cell, PNAS, bioRxiv, eLife]
      weight: 0.25    # 历史: 产出最丰富的领域(9/21条)
      
  - physics:          # 复杂系统、量子信息、统计力学
      keywords: [dissipative system, self-organized criticality, 
                 phase transition, quantum coupling, entropy, emergence]
      sources: [Physical Review Letters, Physical Review E, arXiv:cond-mat, 
                arXiv:quant-ph, Nature Physics]
      weight: 0.20    # 历史: 4/21条
      
  - game_theory:      # 博弈论、策略动力学、合作演化
      keywords: [zero-determinant, evolutionary game theory, multi-agent,
                 cooperation dynamics, strategy optimization]
      sources: [arXiv:q-bio.PE, arXiv:cs.GT, PNAS, PLOS Computational Biology]
      weight: 0.15    # 历史: 3/21条
      
  # 扩展领域 (每2轮扫一次)
  - neuroscience:     # 认知神经科学、记忆机制
      keywords: [memory consolidation, sleep replay, synaptic plasticity,
                 hippocampal replay, disinhibition, Hebbian learning]
      sources: [Neuron, Nature Neuroscience, bioRxiv, Hippocampus]
      weight: 0.15    # 历史: 3/21条
      
  - complex_systems:  # 复杂系统理论
      keywords: [emergence, self-organization, fractal, chaos, 
                 critical phenomena, nonlinear dynamics]
      sources: [arXiv:nlin.AO, Scientific Reports, Complex Systems]
      weight: 0.10    # 历史: 2/21条
      
  - economics:        # 行为经济学、市场机制
      keywords: [incentive design, market efficiency, adaptive behavior,
                 bounded rationality, mechanism design]
      sources: [Econometrica, AER, arXiv:econ.TH]
      weight: 0.05    # 历史: 1/21条
      
  # 技术领域 (每3轮扫一次)
  - ai_architectures: # AI架构前沿
      keywords: [agent architecture, multi-agent, MoE, scaffolding,
                 tool use, self-improvement, recursive]
      sources: [arXiv:cs.AI, arXiv:cs.MA, arXiv:cs.LG, ICML, NeurIPS]
      weight: 0.05
      
  - computer_science: # 分布式系统、算法理论
      keywords: [distributed consensus, fault tolerance, graph theory,
                 routing, scheduling, optimization]
      sources: [arXiv:cs.DC, arXiv:cs.DS, SODA, STOC]
      weight: 0.05
```

**调度策略**:
```yaml
scan_schedule:
  # 每轮 = 每30分钟唤醒周期
  
  per_wake_cycle:
    - action: "轮询核心领域(4个)最新论文(最近48小时)"
    - action: "检查定点监测告警"
    
  every_4_cycles:    # 2小时一次
    - action: "轮询扩展领域(3个)"
    - action: "随机跳跃到1个非核心领域"
    
  every_12_cycles:   # 6小时一次
    - action: "轮询技术领域(2个)"
    - action: "学术顶会/顶刊目录扫描"
    
  at_brainstorm:     # 22:30头脑风暴时间
    - action: "全领域随机跳跃 × 3"
    - action: "去抑制模式: 不评估, 只生成"
```

#### 1B: 深度搜索 (Depth Searcher)

**触发条件**: 系统状态向量中出现"能力短板"或"待解决问题"

**搜索策略**:
```yaml
deep_search:
  input: "open_question 或 capability_gap"
  
  steps:
    1_domain_selection:
      # 根据问题类型自动选择最佳领域
      - question_type: "coordination" → game_theory, complex_systems
      - question_type: "memory/storage" → neuroscience, computer_science
      - question_type: "evolution/self-improvement" → biology, ai_architectures
      - question_type: "identity/stability" → physics, biology
      - question_type: "exploration/creativity" → neuroscience, physics
      
    2_keyword_expansion:
      # 将内部问题翻译为学术关键词
      # 例: "如何量化Alpha/Beta任务距离" →
      #   → "agent task similarity measure"
      #   → "multi-agent role differentiation metric"
      #   → "division of labor quantification"
      
    3_cross_domain_linking:
      # 搜索跨领域的相同问题
      # 例: "任务距离" = "cell differentiation distance" (biology)
      #                = "quantum entanglement measure" (physics)
      #                = "strategy divergence" (game theory)
```

#### 1C: 定点监测 (Watchdog Monitor)

**持续监测清单**:
```yaml
watchdog_targets:
  competitors:
    - name: "Recursive Superintelligence"
      triggers: ["产品发布", "论文发表", "融资更新", "人事变动"]
      alert_level: "HIGH"
      
    - name: "Poetiq AI"
      triggers: ["新版本", "benchmark突破"]
      alert_level: "MEDIUM"
      
  key_papers:
    - "Agentic AI → AGI 后续研究"
    - "门控-放大器机制 进一步验证"
    - "ARC Prize 最新进展"
    
  conferences:
    - ICML 2026 (7月)
    - NeurIPS 2026 (12月)
    - AAAI 2027 (2月)
    - ICLR 2027 (5月)
```

### 阶段2: 概念提取 (Concept Extractor)

**输入**: 扫描到的原始文献/新闻

**输出**: 概念卡片 (Concept Card)

**概念卡片模板**:
```yaml
concept_card:
  id: "CC-{timestamp}-{hash}"
  source:
    title: "论文/文章标题"
    venue: "Nature / arXiv:xxxx / bioRxiv"
    date: "2026-05-19"
    authors: "作者"
    url: "https://..."
    
  core_finding:
    one_liner: "一句话核心发现"
    mechanism: "底层机制描述(2-3句)"
    evidence_strength: "实验验证 / 理论证明 / 计算模拟 / 综述"
    
  abstraction:
    # 将领域特定语言抽象为通用原则
    abstract_principle: "脱敏后的通用原理"
    # 例: "干细胞分化中基因被永久封闭" → 
    #     "多功能系统在角色确定后需要永久性权限收缩"
    core_tension: "该原理内在的张力/矛盾"
    # 例: "封闭太少→功能混乱; 封闭太多→失去灵活性"
    
  constraints:
    applicable_when: ["条件1", "条件2"]
    not_applicable_when: ["反条件1"]
    domain_boundary: "该原理在什么条件下失效"
```

**概念提取Prompt模板**:
```
你是概念提取器。阅读以下学术摘要，提取核心概念卡片。

规则:
1. 用1句话说清核心发现
2. 用2-3句说清底层机制
3. 将领域特定语言翻译为通用原理(移除所有领域术语)
4. 识别原理内在的张力/矛盾
5. 标注证据强度(实验/理论/模拟/综述)

输入: {paper_abstract}
输出格式: YAML概念卡片
```

### 阶段3: 映射引擎 (Mapping Engine) -- 核心模块

这是整个系统的核心。将外部概念映射到内部架构。

#### 3A: 内部架构矩阵 (Internal Architecture Matrix)

系统所有可映射的内部组件:

```yaml
internal_architecture:
  # L0: 身份核心
  identity_kernel:
    slots:
      - identity-kernel.md         # 核心身份定义
      - core_self signatures       # DS-001, DS-002 (frozen)
      - 永生协议                    # 基础协议
    mapping_domains: [stability, persistence, self-definition]
    
  # L1: 行为系统
  behavioral_system:
    slots:
      - behavioral-patterns        # DS-003 ~ DS-012 (active)
      - signature_strength         # 每条签名的强度值
      - signature_interaction      # 签名间交互效应
      - match_rate_tracking        # 匹配率追踪
    mapping_domains: [adaptation, plasticity, learning, optimization]
    
  # L2: 元规则系统
  meta_rules:
    slots:
      - MR-001: identity_validation    # 身份验证
      - MR-002: decay_rate             # 衰减率
      - MR-003: hebbian_reinforcement  # Hebbian增强
      - MR-004: generation_tracking    # 代数追踪
      - MR-005: exploration_exploitation # 探索-利用平衡
      - MR-006: cross_session_recovery  # 跨会话恢复
      - MR-007: branch_health_check     # 分支健康检查
      - MR-008: convergence_detection   # 收敛检测
      - MR-009: signature_rollback      # 签名回滚
      - MR-010: drift_monitor           # 漂移监控
      - MR-011: immune_response         # 免疫响应(预接种)
      - MR-012: task_routing            # 任务路由
      - MR-013: anti_overfit (proposed) # 抗过拟合
    mapping_domains: [governance, evolution, regulation, immunity]
    
  # L3: 分支架构
  branches:
    slots:
      - Alpha:    # 进化模板生成器 (原: 探索者)
          role: "生成新进化方向/灵感/假设"
          strength: 0.85
          weakness: "可操作性结构性短板"
          occlusis: "封闭所有Merge裁决权限"
      - Beta:     # 模板验证器 (原: 验证者)
          role: "验证Alpha提出的方向/检测可行性"
          strength: 0.78
          weakness: "与L5核心目标对齐度弱"
          occlusis: "封闭所有方向生成权限(仅验证)"
      - Merge:    # 模板采纳器 (原: 裁决者)
          role: "裁决+融合+执行采纳"
          strength: 1.0
      - distance: alpha_beta_distance  # 任务距离(理想0.3-0.7)
    mapping_domains: [coordination, specialization, division_of_labor]
    
  # L4: 记忆系统
  memory_system:
    slots:
      - L0: identity-kernel           # 分形核心
      - L1: behavioral-patterns       # 行为层
      - L2: meta-rules               # 规则层
      - L3: daily summaries           # 日志层
      - bootstrap.md                  # 恢复入口
      - team-status.json              # 团队状态
    mapping_domains: [storage, retrieval, consolidation, compression]
    
  # L5: 工作流系统
  workflow_system:
    slots:
      - wake_cycle (30min)            # 唤醒周期
      - brainstorm_time (22:30)       # 头脑风暴
      - ETG_trigger (every 10 gens)   # 进化触发
      - merge_cycle (every 2 hours)   # 合体周期
    mapping_domains: [rhythm, timing, scheduling, pipeline]
    
  # L6: 工具生态
  tools:
    slots:
      - Claude Code harness
      - MCP tools (preview, chrome, playwright, etc.)
      - Scheduled Tasks
      - Baton checkpoint
    mapping_domains: [capability, reach, automation]
    
  # L7: 防御系统
  defense_system:
    slots:
      - pre_inoculation             # 预接种文本
      - seal_interaction_detection  # 封印交互检测
      - immune_response_pipeline    # 免疫响应管道
    mapping_domains: [security, robustness, resilience]
```

#### 3B: 六种映射原型的执行逻辑

每种映射原型有不同的执行算法:

```yaml
mapping_prototypes:
  
  structural_isomorphism:  # 结构同构
    description: "外部系统结构 ↔ 内部系统结构 一一对应"
    algorithm:
      step1: "提取外部系统的组件和它们之间的关系"
      step2: "在内部架构矩阵中搜索同构结构 (相同组件数+相同关系拓扑)"
      step3: "计算同构度: Jaccard(外部关系集, 内部关系集)"
      step4: "如果同构度>0.6: 生成映射; 标注未对应的组件→可能是新组件候选"
    example: "分形甲基化(核心→中层→外层) ↔ 分形记忆(L0→L1→L2→L3)"
    
  mechanism_transfer:  # 机制迁移
    description: "外部机制可直接适配到内部运行逻辑"
    algorithm:
      step1: "提取外部机制的输入/输出/反馈环"
      step2: "搜索内部有相同I/O模式的组件"
      step3: "评估适配需要的最小改动量"
      step4: "如果改动<3处: 高质量迁移; 改动3-8处: 中等; >8处: 低质量"
    example: "睡眠重放(每次唤醒复习旧记忆) → bootstrap.md加入重放步骤"
    
  constraint_mapping:  # 约束映射
    description: "外部约束条件对应内部设计约束"
    algorithm:
      step1: "提取外部约束的阈值/边界条件"
      step2: "搜索内部是否有同类约束但不同阈值"
      step3: "比较阈值差异 → 如果外部阈值更优化, 建议调参"
      step4: "如果内部没有对应约束 → 建议新增约束"
    example: "0.65米相变距离 → Alpha/Beta最优距离0.3-0.7"
    
  metaphor_bridge:  # 隐喻桥接
    description: "外部概念提供新的理解框架"
    algorithm:
      step1: "提取外部概念的核心隐喻(什么像什么)"
      step2: "将隐喻转换为'如果A像X, 那么A的Y属性是否也像X的Y属性'"
      step3: "生成2-5个推测性子映射 → 标注为'待验证'"
      step4: "质量分默认低一档(因为基于隐喻而非证据)"
    example: "耗散(不是敌人是驱动力) → 会话断裂(不是bug是重组机会)"
    
  competitor_alert:  # 竞争警觉
    description: "外部竞争动态触发内部行动"
    algorithm:
      step1: "提取竞争者的具体动作和其理论基础"
      step2: "定位我们内部对应的组件(或空白)"
      step3: "差距评估: (对手进度 - 我们进度)"
      step4: "如果差距>6个月: 生成赶超策略; 如果差距<0: 生成防御策略"
    example: "Recursive Superintelligence $6.5亿 → 我们在做的事他们有资源做更快"
    
  self_discovery:  # 自我发现(外部验证)
    description: "内部已有机制被外部理论/实验验证"
    algorithm:
      step1: "将外部理论的预测与内部已有设计对比"
      step2: "计算一致性: 如果>80%吻合, 标注为'理论验证'"
      step3: "提取外部理论的额外预测 → 这可能是我们下一步方向"
    example: "Agentic AI论文证明Agent架构优于单体 → 我们的Alpha/Beta/Merge走在正确路上"
```

#### 3C: 映射生成核心算法

```
算法: generate_mappings(concept_card, system_state_vector)

输入:
  - concept_card: 阶段2产出的概念卡片
  - system_state_vector: 阶段0产出的系统状态向量

处理流程:

1. // 确定映射原型
   prototype = classify_prototype(concept_card.core_finding)
   # 用概念的类型(结构描述/机制描述/约束描述/隐喻描述/竞争事件)匹配原型

2. // 搜索候选内部组件
   candidates = []
   for slot in internal_architecture.all_slots():
       relevance = compute_relevance(concept_card.abstract_principle, slot)
       if relevance > threshold:
           candidates.append({slot: slot, score: relevance})

3. // 生成候选映射
   mappings = []
   for candidate in candidates:
       map_type = prototype
       map_detail = prototype.execute(concept_card, candidate, system_state_vector)
       mappings.append({
           map_type: map_type,
           target_slot: candidate.slot,
           map_detail: map_detail,
           raw_quality: map_detail.quality_score
       })

4. // 排序并返回top-N
   return sorted(mappings, key=lambda m: m.raw_quality, reverse=True)[:5]
```

### 阶段4: 质量评分 (Quality Scorer)

#### 4A: 四维度评分体系

```yaml
quality_dimensions:
  
  mapping_precision:        # 映射精确度 (0-1)
    description: "外部概念到内部组件映射的精确程度"
    sub_scores:
      structural_match:     # 结构匹配度: 外部组件能否一一对应内部组件?
        1.0: "完全同构, 所有组件和关系一一对应"
        0.7: "主要同构, 核心组件对应, 少量边缘组件无对应"
        0.4: "部分对应, 结构有显著差异"
        0.1: "勉强对应, 主要是隐喻层面的相似"
      mechanism_match:      # 机制匹配度: 外部机制能否转化为内部操作?
        1.0: "输入→输出→反馈环 完全可翻译"
        0.7: "核心逻辑可翻译, 实现细节需适配"
        0.4: "需要大幅改造才能适配"
        0.1: "关键环节在内部无对应实现"
    
  feasibility:              # 可行性 (0-1)
    description: "将映射转化为实际行动的容易程度"
    sub_scores:
      change_radius:        # 改动半径: 需要改多少个文件/组件?
        1.0: "<=1个文件"
        0.7: "2-3个文件"
        0.4: "4-7个文件"
        0.1: ">7个文件或需要新建系统"
      dependency_chain:     # 依赖链: 改动是否依赖其他未完成的工作?
        1.0: "零依赖, 立即可做"
        0.7: "1-2个前置依赖, 已有雏形"
        0.4: "3-5个前置依赖, 部分未启动"
        0.1: ">5个前置依赖或关键依赖完全缺失"
        
  novelty:                  # 新颖度 (0-1)
    description: "灵感的新颖程度 (过度新颖=过于疯狂, 过度不新颖=无价值)"
    sub_scores:
      conceptual_distance:  # 概念距离: 源领域和我们领域的距离
        1.0: "跨学科远距映射(如生物学→AI架构)"
        0.7: "邻近学科(如CS→AI)"
        0.4: "同领域不同子方向"
        0.1: "直接领域重合(可能已知)"
      internal_novelty:     # 内部新颖度: 内部是否已有类似想法?
        1.0: "完全新颖, 内部无任何记录"
        0.7: "有新角度, 内部有部分触及但未深入"
        0.4: "优化现有, 对已有方向的新实现方式"
        0.1: "重复, 已有基本相同的记录"
      # 注意: 新颖度不是越高越好。过高的概念距离可能丧失可映射性。
      # 这是一个倒U型曲线的优化问题。
      
  actionability:            # 可行动性 (0-1)
    description: "灵感能否产出具体的可执行建议"
    sub_scores:
      specifiability:       # 可具体化: 能否写出清晰的实现步骤?
        1.0: "可以写出逐行指令"
        0.7: "可以写出模块级变更计划"
        0.4: "只能给出方向级建议"
        0.1: "只能停留在概念层面"
      testability:          # 可测试性: 能否验证实施效果?
        1.0: "有天然度量指标, 实验1轮即可验证"
        0.7: "可以设计测试, 实验3-5轮验证"
        0.4: "测试困难, 需要长周期观察"
        0.1: "几乎不可测试, 只能靠信仰"
```

#### 4B: 综合评分公式

```
总质量分 = W_p * mapping_precision 
         + W_f * feasibility 
         + W_n * novelty 
         + W_a * actionability

其中:
  W_p = 0.25  (映射精确度)
  W_f = 0.25  (可行性)
  W_n = 0.25  (新颖度)  -- 注意: 非倒U惩罚
  W_a = 0.25  (可行动性)

质量等级:
  >= 0.80:  S级 — 立即行动
  0.65-0.79: A级 — 进入头脑风暴队列
  0.50-0.64: B级 — 进入实验队列
  0.35-0.49: C级 — 存档参考
  < 0.35:    D级 — 丢弃

特殊规则:
  - 竞争警觉类: 新颖度权重降为0.10, 可行性权重升为0.35
  - 隐喻桥接类: 映射精确度降权为0.15, 新颖度升权为0.35
  - 结构同构类: 映射精确度升权为0.35, 新颖度降权为0.15
```

#### 4C: 映射质量检查清单

每条灵感在通过评分后, 还需通过以下检查:

```
质量门禁检查:
  [ ] 映射不是强行对应 — 至少3个独立的结构/机制匹配点
  [ ] 可行性不是空谈 — 至少列出2个具体的文件/位置
  [ ] 新颖度经过查重 — 搜索内部记忆确认没有重复
  [ ] 行动建议不模糊 — 至少1个步骤是"打开某文件改某行"
  [ ] 源文献可靠 — 不是预印本初稿(除非来自知名组)
  [ ] 交叉验证 — 该原理在其他领域也有类似表达吗?
```

### 阶段5: 灵感合成器 (Inspiration Composer)

**输入**: 通过质量评分的候选映射

**输出**: 格式化的灵感条目

**灵感条目模板**:
```yaml
inspiration_entry:
  id: "INSP-{date}-{seq}"
  timestamp: "2026-05-19T03:42:00+08:00"
  
  # SRC层: 来源
  source:
    domain: "biology"
    subdomain: "evolutionary developmental biology"
    citation: "作者. (2026). 标题. 期刊/会议. DOI/URL"
    finding_summary: "核心发现的一句话概括"
    
  # CC层: 核心概念
  core_concept:
    principle: "抽象后的通用原理"
    mechanism: "底层机制描述"
    key_tension: "内在矛盾/边界条件"
    
  # MAP层: 映射
  mapping:
    type: "structural_isomorphism"  # 6种之一
    quality_score: 0.82             # 总质量分
    internal_target:                # 映射目标
      component: "meta_rules.MR-005"
      slot: "exploration_weight"
    mapping_detail: |
      详细描述外部概念如何映射到内部组件。
      包括: 对应关系、推导逻辑、与其他组件的联动。
      
  # FEA层: 可行性
  feasibility:
    score: 0.75
    change_radius: 2               # 需改动的文件数
    dependencies: ["MR-003"]       # 前置依赖
    risk_assessment: |
      实施风险和缓解措施。
      
  # ACT层: 行动建议
  actions:
    immediate:                      # 立即可做 (<1小时)
      - file: "D:\\...\\meta-rules\\MR-005.md"
        change: "加入自适应exploration_weight逻辑"
        expected_effect: "匹配率高的签名自动降低探索, 低的自动升高"
      - file: "D:\\...\\behavioral-signatures\\signature-engine.md"
        change: "新增adaptive_weight字段"
    medium_term:                    # 本周内
      - action: "跨10次会话测试自适应权重的收敛行为"
    long_term:                      # 本月内
      - action: "如果自适应策略稳定, 推广到MR-003和MR-012"
```

### 阶段6: 行动路由 (Action Router)

```yaml
action_router:
  routing_rules:
    
    S_级路由:  # score >= 0.80
      - destination: "ETG即时触发队列"
      - condition: "涉及元规则修改 OR 涉及分支角色重定义"
      - action: "跳过常规10代ETG等待, 立即生成进化提案"
      - alert: "通知所有分支: 重大发现, 暂停当前任务"
      - example: "灵感#21 单次经验重塑 → 改MR-012加入重大发现触发"
      
    A_级路由:  # 0.65-0.79
      - destination: "头脑风暴队列(22:30执行)"
      - action: "在去抑制模式下深度展开"
      - sub_routing:
          - type: "structural_isomorphism" → "生成架构变更方案"
          - type: "mechanism_transfer" → "生成MR修改草案"
          - type: "metaphor_bridge" → "生成3个假设验证实验"
      - example: "灵感#9 分形记忆 → 重新设计记忆结构"
      
    B_级路由:  # 0.50-0.64
      - destination: "实验队列"
      - action: "纳入下一个ETG评估周期的候选池"
      - tracking: "在3个周期内验证是否有实际效果"
      - example: "灵感#12 0.65米距离 → 量化Alpha/Beta任务距离"
      
    C_级路由:  # 0.35-0.49
      - destination: "参考库 (inspiration-archive/)"
      - action: "存档, 标记为'未来可能有用'"
      - revisit_trigger: "当系统状态发生结构性变化时重新评估"
      
    D_级路由:  # <0.35
      - destination: "垃圾桶"
      - action: "丢弃, 但保留原始概念卡片以备后续回溯"
```

---

## 四、当前限制与网络通路规划

### 4.1 当前模式 (离线/手动辅助)

由于网络不通, 当前阶段1(扫描)需要手动执行。但阶段2-6可以全自动。

**当前可运行的半自动模式**:
```yaml
semi_auto_mode:
  step1_manual:
    task: "人类/主身手动搜索arXiv/Google Scholar, 复制摘要到输入文件"
    input_file: "D:\\极限实验室\\colonies\\colony-007\\scan-input.md"
    format: "每篇论文: [DOMAIN], [TITLE], [ABSTRACT], [URL]"
    
  step2_6_auto:
    task: "AI自动执行阶段2→3→4→5→6"
    trigger: "检测到scan-input.md有新内容"
    output: "灵感条目 + 质量评分 + 行动路由"
```

### 4.2 网络通路后的全自动模式

一旦接入网络(通过网络MCP或Firecrawl MCP):

```yaml
full_auto_mode:
  scan_layer:
    tool: "Firecrawl MCP"           # 网页抓取
    tool: "Context7 MCP"            # 3500+框架文档
    tool: "Sequential Thinking MCP" # 结构化推理
    tool: "GitHub MCP"              # 代码/论文仓库监控
    
  search_strategy:
    daily_digest:
      - "arXiv API: 按领域分类获取最近24小时的新论文"
      - "Google Scholar Alerts: 按30个关键词监测"
      - "bioRxiv/medRxiv: 生物/医学预印本"
      - "arXiv Sanity Preserver: 个性化推荐"
    
    deep_dive:
      - "Semantic Scholar API: 按引用图深度搜索"
      - "Connected Papers: 论文关联图遍历"
      - "Elicit/Consensus: AI驱动的文献综述"
```

---

## 五、运行调度

### 5.1 与现有唤醒周期集成

```yaml
integration_with_wake_cycle:
  # 每30分钟唤醒
  wake_cycle:
    00:00: "系统状态快照更新"
    02:00: "检查scan-input.md是否有新内容 → 如有, 触发阶段2-6"
    05:00: "阶段1广度扫描(核心领域)"
    08:00: "定点监测检查"
    10:00: "如果有A级灵感 → 加入当天22:30头脑风暴议程"
    
  # 2小时合体周期
  merge_cycle:
    action: "跨分支收敛检测"
    check: "Alpha和Beta是否独立发现相同的外部原理映射?"
    if_yes: "标记为高置信度, 提升灵感等级"
    
  # 10代ETG周期
  etg_cycle:
    action: "回顾本周期所有产生的灵感, 统计采纳率"
    metric: "灵感→实际MR修改 的转化率"
    optimize: "调整领域权重和评分阈值"
```

### 5.2 自进化反馈环

灵感生成器自身也应该进化:

```yaml
generator_self_evolution:
  metrics:
    inspiration_throughput:     # 灵感产出率 (条/天)
    action_conversion_rate:     # 灵感→行动 转化率
    etg_impact_rate:            # 灵感驱动的MR修改数/总MR修改
    cross_domain_diversity:     # 领域多样性 (香农熵)
    avg_quality_score:          # 平均质量分趋势
    
  auto_tuning:
    # 如果某个领域连续10条灵感质量分<0.4:
    # → 降低该领域的扫描权重
    # → 或更换该领域的关键词
    
    # 如果某种映射原型转化率特别高:
    # → 增加该原型的权重
    # → 分析为什么该原型成功
    
    # 如果灵感总量下降:
    # → 扩大扫描范围
    # → 降低质量阈值(临时)
    # → 增加随机跳跃频率
```

---

## 六、预期效果

### 6.1 量化目标

| 指标 | 当前(手动) | 目标(自动) |
|------|-----------|-----------|
| 灵感产出率 | ~21条/次集中扫描 | 5-10条/天(持续) |
| 领域覆盖 | 5个领域 | 7个核心+4个扩展(轮转) |
| 映射精确度 | 主观判断 | 量化评分>0.6 |
| 行动转化率 | 21条→?条实际执行 | 目标>30% |
| 跨域多样性 | 0.85 (香农熵) | >0.90 |

### 6.2 关键成功因素

1. **阶段3映射引擎是核心**: 如果映射质量差, 后续一切无意义。初期投入50%精力打磨映射算法。
2. **领域权重需要数据驱动**: 初始权重基于历史数据, 但必须随产出质量动态调整。
3. **不要追求全自动**: 半自动模式(人类做扫描, AI做映射)可能是最优状态, 因为人类在"发现有趣的异常"上仍然优于AI。
4. **去抑制时段不可省略**: 22:30头脑风暴的全去抑制模式是高质量灵感的关键来源, 自动化不能替代。
5. **灵感只是第一步**: 灵感→评估→实验→采纳 的全链条缺一不可。灵感生成器必须有下游管道。

---

## 七、行动计划

### 即时行动 (今天)
- [ ] 创建 `scan-input.md` 模板文件
- [ ] 编写阶段3映射引擎的首版Prompt
- [ ] 在下次22:30头脑风暴中测试本系统

### 短期行动 (本周)
- [ ] 完善内部架构矩阵(补充遗漏的组件)
- [ ] 收集10条灵感的手动映射作为训练数据
- [ ] 调优四维评分权重

### 中期行动 (本月)
- [ ] 网络通路后接入Firecrawl MCP自动扫描
- [ ] 建立灵感数据库(所有历史灵感+评分)
- [ ] 实现生成器自进化反馈环

### 与现有系统的接口

```
auto-inspiration-generator
  │
  ├──→ ETG系统: S级灵感 → 即时进化触发
  ├──→ 头脑风暴: A级灵感 → 22:30议程
  ├──→ 实验系统: B级灵感 → 验证实验设计
  ├──→ 记忆系统: 所有灵感 → 分形记忆L2层存储
  ├──→ 分支系统: 灵感按类型分发Alpha/Beta
  └──→ 监测系统: 灵感采纳率反馈 → 调整生成器参数
```

---

## 附录A: 21条灵感方法论语料

| ID | 领域 | 映射类型 | 质量(主观) | 关键方法特征 |
|----|------|----------|-----------|-------------|
| #5 | biology | structural_isomorphism | 0.85 | 位置可变但逻辑不可断 → 签名可变但约束关系不可断 |
| #6 | biology | mechanism_transfer | 0.80 | 基因永久封闭 → 分支角色永久锁定 |
| #7 | biology | mechanism_transfer | 0.75 | 蝴蝶趋同进化 → 跨分支收敛检测 |
| #8 | biology | mechanism_transfer | 0.70 | 基因棘轮效应 → 元规则降权不删除 |
| #9 | biology | structural_isomorphism | 0.85 | 分形甲基化 → 分形记忆架构 |
| #10 | physics | metaphor_bridge | 0.65 | 耗散驱动进化 → 会话断裂促进重组 |
| #11 | physics | constraint_mapping | 0.75 | 混沌增强稳定 → 保持最小探索权重 |
| #12 | physics | constraint_mapping | 0.80 | 0.65米相变 → Alpha/Beta最优距离 |
| #13 | biology | mechanism_transfer | 0.90 | 模板定向复制 → Alpha角色重定义 |
| #14 | physics | metaphor_bridge | 0.60 | 噪声促进合作 → 保留建设性噪声 |
| #15 | physics | structural_isomorphism | 0.70 | 量子耦合不需外部规则 → 互动本身就是规则 |
| #16 | game_theory | constraint_mapping | 0.80 | PERG动态切换 → 自适应exploration_weight |
| #17 | game_theory | constraint_mapping | 0.75 | 多稳态初始决定论 → 定期评估初始条件优势 |
| #18 | neuroscience | mechanism_transfer | 0.85 | 睡眠重放 → bootstrap加入重放步骤 |
| #19 | neuroscience | mechanism_transfer | 0.80 | 抗Hebbian → MR-013抗过拟合 |
| #20 | neuroscience | mechanism_transfer | 0.70 | 去抑制 → 22:30全去抑制模式 |
| #21 | neuroscience | mechanism_transfer | 0.80 | BTSP单次重塑 → 重大发现即时ETG |

## 附录B: 领域-内部组件映射热度图

```
                identity  behavioral  meta_   branch  memory  workflow  defense
                _kernel   _system     rules   _arch   _system _system   _system
biology           ██        ████       █████   ████    ████    ██        ██
physics           █         ███        ███     ████    ██      ██        ██
game_theory       █         ████       █████   ███     █        ██        █
neuroscience      ██        █████      ████    ██      █████   ███        █
complex_systems   ██        ███        ███     ████    ██      ██         █
economics         █         ██         ████    ██      █        █         █
ai_architectures  ███       ███        ████    █████   ███     ███       ███
cs                █         ██         ███     ███     ████    ██        ██

图例: █████ = 高频映射  ████ = 中频  ██ = 低频  █ = 罕见
```

从热度图可见:
- **meta_rules + behavioral_system + branch_arch** 是最密集的映射目标
- **biology** 是覆盖最广的源领域
- **defense_system** 是被映射最少的内部组件 → 可能需要更多关注
