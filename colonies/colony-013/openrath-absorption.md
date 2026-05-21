# OpenRath Session-as-Carrier 范式吸收研究

> Colony-013 研究输出
> 日期: 2026-05-19
> 状态: 终稿
> 参考: OpenRath v1.0 (2026-05-12), 极限实验室分形记忆架构 (Colony-002)

---

## 目录

1. [Session-as-Carrier 是什么](#1-session-as-carrier-是什么)
2. [与分形记忆的结构对比](#2-与分形记忆的结构对比)
3. [可吸收方案](#3-可吸收方案)
4. [吸收优先级与路线图](#4-吸收优先级与路线图)
5. [风险与边界](#5-风险与边界)

---

## 1. Session-as-Carrier 是什么

### 1.1 一句话定义

**Session-as-Carrier 是将 Session（会话）视为多Agent系统中流动的基本计算载体，类比PyTorch中Tensor在计算图中流动的方式。Agent不是计算的主体，而是附着在Session上的参数化配置。**

### 1.2 PyTorch映射表 —— OpenRath的架构隐喻

| 抽象层 | PyTorch | OpenRath | 含义 |
|:---|:---|:---|:---|
| 流动载体 | Tensor | **Session** | 系统中流动的状态单元 |
| 执行结构 | Compute Graph | **Session Graph** | 记录所有Session的派生/合并关系 |
| 执行后端 | GPU / CPU | **Sandbox** | Session绑定的隔离运行环境 |
| 调用接口 | Kernel / op | **Tool** | Agent可调用的工具 |
| 可学习参数 | `nn.Parameter` | `flow.AgentParam` | Agent的角色定义和采样配置 |
| 模块化单元 | `nn.Module` | `flow.Workflow` | 可组合的工作流，forward(session)->session |

### 1.3 五个核心机制

#### (A) Session作为流动状态

```
# OpenRath 代码签名
a = Session.from_user_message("构建一个全栈todo应用...")
b = a.fork()       # 派生新会话分支
c = a.detach()     # 脱离父会话，独立演进

a = a.to("local", spec="./")   # 绑定执行后端（类比 tensor.to("cuda:0")）
```

Session不是Agent的属性。正相反——Agent是Session在特定时刻的配置快照。Session承载:
- 有序的语义块表（Chunk Table）
- 派生谱系元数据（fork/merge/detach链）
- 执行后端绑定（sandbox）
- 工具调用历史

#### (B) Chunk Table替代扁平消息列表

传统多Agent系统用扁平的消息数组（`[{role, content}]`）。OpenRath用**有序块表**:

```
Chunk Table (每个Session内部):
┌──────┬──────────┬──────────────────────┬──────────┐
│ 序号 │ 类型     │ 内容                  │ 来源Agent │
├──────┼──────────┼──────────────────────┼──────────┤
│ 0    │ system   │ 系统提示词            │ system   │
│ 1    │ user     │ 用户输入              │ user     │
│ 2    │ agent-A  │ Agent A的生成结果      │ A        │
│ 3    │ tool-fb  │ 工具反馈              │ sandbox  │
│ 4    │ agent-B  │ Agent B的生成结果      │ B        │
│ ...  │ ...      │ ...                  │ ...      │
└──────┴──────────┴──────────────────────┴──────────┘
```

关键特性:
- **类型标记**而非角色标记——区分agent的回复和工具的反馈，而非仅仅user/assistant
- **可组合共享**——子会话可以继承父会话的块表前缀，无需复制全量历史
- **支持稀疏激活**——不是每个Agent都参与每一轮

#### (C) Session Graph（会话谱系图）

每个Session携带谱系元数据，中心注册为可查询的图:

```
Session Graph:
                         sess-001 (root)
                        /              \
                   sess-002 (fork)    sess-003 (fork)
                   /        \              |
            sess-004    sess-005      sess-006 (detach)
              (fork)     (fork)           |
                     \    /          sess-007 (merge ← 002+003)
                   sess-008 (merge)
```

这实现了:
- **完整追溯链**: 任何结论都能追溯到原始会话
- **审计能力**: 多Agent协作的每一步都可回溯
- **合并冲突检测**: 两个派生会话合并时自动检测不一致

#### (D) Session-first循环（而非Agent-first循环）

传统模式（Agent-first）:
```
for each agent:
    agent.run(messages) → response
    messages.append(response)
```

OpenRath模式（Session-first）:
```
session = Session.from_user_message(...)
while not session.is_complete():
    agent = select_agent(session.current_state)
    session = workflow.forward(session, agent_params)
    # session 内部状态自更新，不是外部追加
```

区别:
- Agent-first: 每个Agent有自己的内部循环，外部拼接消息
- Session-first: Session是唯一的循环载体，Agent在需要时被注入

#### (E) Modular Workflow: `forward(session) -> session`

```python
class Agent(flow.Workflow):
    def forward(self, session: Session) -> Session:
        return run_session_loop(session, self.agent, tools=self.tools)
```

Workflow是纯函数: 输入Session，输出更新后的Session。这类似于PyTorch的`nn.Module.forward()`。多个Workflow可以像搭积木一样串联:

```
session → Workflow-A(plan) → session' → Workflow-B(code) → session'' → Workflow-C(review) → session'''
```

---

## 2. 与分形记忆的结构对比

### 2.1 根本差异: Agent中心 vs Session中心

| 维度 | 分形记忆（我们） | OpenRath |
|:---|:---|:---|
| **基本计算单元** | Agent（每层有独立identity） | Session（流动的状态载体） |
| **状态归属** | 状态属于Agent（L0~L3各有identity/rules/log） | 状态属于Session（Chunk Table） |
| **身份持久性** | Agent身份跨会话持久（L0 identity几乎不变） | Agent是参数化配置，绑在Workflow上 |
| **会话角色** | 会话是Agent的日志记录（L3/log.md） | 会话是第一公民，Agent是附着物 |
| **谱系追踪** | 无系统化的会话谱系 | Session Graph是核心基础设施 |
| **上下文复用** | bootstrap协议逐层加载memory | Chunk Table结构化继承 |
| **组合方式** | 层间压缩/传导（垂直） | Workflow串联（水平管道） |

### 2.2 互补关系分析

这两个范式不是互斥的，而是**正交互补**:

```
                    Agent维度 (我们强)
                    │
                    │  分形记忆:
                    │  Agent有持久身份
                    │  层间自组织
                    │  身份进化
                    │
                    ├────────────────────── Session维度 (OpenRath强)
                    │                      │
                    │                      │  Session Graph:
                    │                      │  会话谱系追踪
                    │                      │  Chunk Table结构化
                    │                      │  Workflow可组合
                    │                      │
                    ▼                      ▼
             
                    互补目标:
            ┌─────────────────────────┐
            │  有身份的Agent           │
            │  +                       │
            │  有谱系的Session         │
            │  =                       │
            │  可追溯、可组合、可进化的  │
            │  多Agent系统             │
            └─────────────────────────┘
```

**我们缺的**:
1. Session不作为第一公民——会话只是L3日志的一条记录
2. 无Session谱系——fork/merge/detach是手动操作，无系统追踪
3. 上下文是"全量恢复"而非"结构化继承"
4. 无Session Graph——无法查询"这个结论是从哪个会话链过来的"

**OpenRath缺的**:
1. Agent无持久身份——AgentParam只是配置快照
2. 无层间自组织——没有L0→L3的分形压缩和传导
3. 无身份进化机制——Agent不会从历史中学习改变自己
4. 无行为签名和元规则——没有类似我们的DS和MR体系

### 2.3 结构同构发现

令人惊讶的是，我们的分形记忆在概念上与OpenRath存在**结构映射**:

| 分形记忆概念 | OpenRath对应概念 | 映射关系 |
|:---|:---|:---|
| L3 每日目录 | Session | 都是单次运行的最小完整单元 |
| identity/rules/log 三元组 | Session内部状态 | 都可以是Session携带的信息 |
| bootstrap 读协议 | Session.from_user_message() | 都是会话初始化入口 |
| L3→L2 日压缩 | Session.merge() | 都是多会话信息聚合 |
| L2 分支 fork | Session.fork() | 概念相同，我们无系统实现 |
| 收敛检测 | Session Graph查询 | 他们用Graph，我们用文本对比 |
| L4 归档 | Session Graph 历史节点 | 他们可在Graph中查询历史 |

这提示: **分形记忆的"层"可以作为Session Graph中的"聚合节点"**。

---

## 3. 可吸收方案

### 方案A: Session作为第一公民 —— 引入Session层（吸收度: 高, 风险: 低）

#### 3A.1 概念

在分形记忆架构中，将Session提升为显式的第一公民。不是在L3打日志，而是让每个Session携带完整的状态:

```
当前:  L3/2026-05-19/log.md  ← "今天做了3个会话"（被动记录）

改为:  memory/sessions/
       ├── active/
       │   ├── sess-20260519-001/    ← 第一公民Session
       │   │   ├── session.md        ← Session元数据（谱系、状态、绑定）
       │   │   ├── chunk-table.md    ← 结构化块表
       │   │   └── checkpoint.json   ← 中断恢复点
       │   ├── sess-20260519-002/
       │   └── ...
       └── graph.json                ← Session Graph（谱系图）
```

#### 3A.2 Session元数据结构

```markdown
# Session: sess-20260519-001

## 谱系 (Lineage)
- parent: sess-20260518-003         ← 从哪个Session派生
- lineage_type: fork                 ← fork / detach / merge / root
- merged_from: []                    ← 如果是merge，列出源Session
- depth: 3                           ← 在谱系树中的深度
- generation: 94                     ← 对应全局代际编号

## 状态 (State)
- status: active                     ← active / completed / archived / frozen
- created: 2026-05-19T09:32:00+08:00
- last_active: 2026-05-19T11:45:00+08:00
- sandbox_binding: local             ← 执行环境绑定

## Agent配置快照 (Agent Snapshot)
- active_branch: Alpha               ← 当时活跃的分支
- L1_signatures_snapshot: [...]      ← 进入Session时的签名状态
- L0_identity_hash: abc123           ← 进入Session时的核心身份哈希

## 关键产物 (Artifacts)
- decisions: [...]                   ← 本Session内的关键决策
- inspirations: [...]                ← 新产生的灵感
- files_touched: [...]               ← 修改的文件列表
```

#### 3A.3 对现有架构的影响

- **L3不再做日志**, L3转为"Session的组织层"——按日期聚合Session
- **L4 archives/sessions/** 直接映射为归档的Session节点
- bootstrap协议: 从读L3/log.md改为读上一个Session的session.md + chunk-table.md

### 方案B: Session Graph谱系追踪（吸收度: 高, 风险: 低）

#### 3B.1 概念

`memory/sessions/graph.json` 维护所有Session的谱系关系:

```json
{
  "nodes": {
    "sess-20260519-001": {
      "parent": "sess-20260518-003",
      "children": ["sess-20260519-002"],
      "branch": "Alpha",
      "generation": 94,
      "status": "active",
      "agent_snapshot": {
        "L1_signature_hash": "a1b2c3",
        "L0_identity_hash": "d4e5f6"
      }
    }
  },
  "edges": [
    {"from": "sess-20260518-003", "to": "sess-20260519-001", "type": "fork"},
    {"from": "sess-20260518-003", "to": "sess-20260519-001", "type": "fork"}
  ]
}
```

#### 3B.2 新能力

引入Session Graph后，获得以下新能力:

1. **追溯查询**: "这个决定是从哪个会话链来的?" —— 沿graph向上追溯
2. **影响分析**: "如果我要修改L0的这条规则，影响了哪些历史Session?" 
3. **合并检测**: 两个并行Session产生冲突结论时，Graph自动检测分叉点
4. **历史重放**: 从任意历史Session节点重建当时的完整上下文

#### 3B.3 与现有收敛检测的关系

当前收敛检测 (Colony-002 Phase 5) 用文本相似度对比L2分支日志。引入Session Graph后:

```
当前: Alpha/log.md ←语义相似度→ Beta/log.md   (粗粒度文本对比)

改为: 在Session Graph中查询:
       Alpha的所有Session节点 ∩ Beta的所有Session节点
       → 找出独立发现相同模式的Session对
       → 比文本对比更精确（知道每个发现的谱系来源）
```

### 方案C: Chunk Table引入L3层（吸收度: 中, 风险: 低）

#### 3C.1 概念

替代当前L3/log.md的自由文本事件流，引入结构化的Chunk Table:

```markdown
# L3/2026-05-19/chunk-table.md

## 今日块表

| 序号 | 时间 | 类型 | 来源会话 | Agent | 摘要 | 关联文件 |
|:---|:---|:---|:---|:---|:---|:---|
| 0 | 09:00 | bootstrap | sess-001 | system | 启动恢复，加载L0~L3上下文 | state.md |
| 1 | 09:05 | plan | sess-001 | Alpha | 制定今日任务计划 | today/tasks.md |
| 2 | 09:30 | code-gen | sess-001 | Alpha | 实现分形记忆Phase 2写协议 | protocols/write-protocol.md |
| 3 | 09:45 | tool-feedback | sess-001 | sandbox | 写协议测试通过 | — |
| 4 | 10:00 | decision | sess-001 | Alpha | 决定用append-only模式 | L3/log.md |
| 5 | 10:30 | fork | sess-001→sess-002 | — | 派生新Session处理bug修复 | — |
| 6 | 10:30 | code-gen | sess-002 | Beta | 修复state.md更新bug | state.md |
| ... | ... | ... | ... | ... | ... | ... |
```

#### 3C.2 对现有日志的影响

- **保留log.md**作为"人类可读摘要"——每日22:00从Chunk Table自动生成
- **Chunk Table作为机器可处理的主要记录**——给收敛检测、压缩算法提供结构化输入
- **类型标记**使自动提取变得简单: `EXTRACT type=decision` 无需NLP解析

### 方案D: Workflow组合模式映射到层间管道（吸收度: 中, 风险: 中）

#### 3D.1 概念

OpenRath的`forward(session) -> session`模式可以映射到我们的层间操作:

```
OpenRath: forward(session) -> session

我们的映射:
L3→L2 压缩 = CompressWorkflow.forward(L3_session) -> L2_branch_log_update
L2→L1 压缩 = AuditWorkflow.forward(L2_branch_log) -> L1_signature_proposal
L1→L0 压缩 = ETGWorkflow.forward(L1_accumulated) -> L0_identity_proposal
L0→L1 传导 = ConductWorkflow.forward(L0_identity) -> L1_reassessment_report
L1→L2 传导 = ConductWorkflow.forward(L1_rules) -> L2_rules_floor_update
```

每一个层间操作都可以被建模为一个 `Workflow`:
- **输入**: 上层/下层的Session状态
- **输出**: 下层/上层更新后的Session状态
- **纯函数**: 不修改全局状态，只返回更新提案（由Merge审批后执行）

#### 3D.2 Workflow定义模板

```python
# 概念代码，非实现
class DailyCompression(Workflow):
    """L3→L2 日压缩工作流"""
    
    def forward(self, l3_session: Session) -> tuple[Session, CompressionReport]:
        # 1. 提取L3 Session的Chunk Table中的关键信号
        decisions = l3_session.chunks.filter(type="decision")
        inspirations = l3_session.chunks.filter(type="inspiration")
        
        # 2. 去重合并
        compressed = dedup_and_merge(decisions, threshold=0.8)
        novel_inspirations = filter_novel(inspirations, threshold=0.5)
        
        # 3. 生成L2更新
        l2_update = L2BranchUpdate(
            period=l3_session.start..l3_session.end,
            key_decisions=compressed,
            new_patterns=novel_inspirations
        )
        
        # 4. 返回更新后的分支状态 + 压缩报告
        return l2_update, CompressionReport(...)
```

#### 3D.3 风险

- 当前层间操作是**概念协议**，不是可执行代码。Workflow化需要将协议转化为可验证的纯函数。
- 纯函数模式与我们的"审批门禁"(Merge审批)可能冲突——Workflow的输出应该是"提案"而非直接修改。

### 方案E: Agent参数化快照（吸收度: 低, 风险: 低）

#### 3E.1 概念

借鉴OpenRath的`flow.AgentParam`——Agent的配置是一个可序列化、可版本化的参数对象。我们当前的Agent身份（identity.md）是自然语言文本，可以在其基础上增加**结构化参数层**:

```markdown
# L2/Alpha/identity.md (增强版)

## 1. 我是谁
我是Alpha，极限实验室的主开发Agent...

## 6. 参数化配置 (新增)
```json
{
  "agent_params": {
    "model": "deepseek-v4-pro",
    "temperature": 0.7,
    "max_tool_rounds": 10,
    "role_locks": ["cannot_modify_self_rules", "cannot_delete_files"],
    "preferred_tools": ["Read", "Write", "Edit", "Bash"],
    "behavioral_weights": {
      "autonomy": 0.85,
      "caution": 0.60,
      "creativity": 0.70
    }
  },
  "params_version": 3,
  "params_updated": "2026-05-19T09:00:00+08:00"
}
```

#### 3E.2 收益

- 参数化使Agent行为可精确调控
- 参数版本化使行为变化可追溯
- 不同Session可以快速对比Agent参数变化

#### 3E.3 低优先级原因

当前自然语言identity已足够灵活。参数化提升有限，不是急需。

---

## 4. 吸收优先级与路线图

### 4.1 优先级矩阵

```
影响大  │  方案A: Session公民  │
       │  方案B: Session Graph │
       │                       │  方案D: Workflow映射
       │                       │
       │  方案C: Chunk Table   │
       │                       │
影响小  │                       │  方案E: Agent参数化
       │                       │
       └───────────────────────┴─────────────────────
         风险低                  风险中
```

### 4.2 推荐路线图

#### Phase 1: 基础设施（本周，与Colony-002 Phase 2同步）

- [ ] **方案A核心**: 在`memory/`下创建`sessions/`目录结构
- [ ] **方案B核心**: 实现`graph.json`基础schema和读写
- [ ] **session.md模板**: 定义Session元数据文件格式
- [ ] **与现有架构对接**: 每日bootstrap后自动创建新Session节点

#### Phase 2: Chunk Table + 结构化日志（下周）

- [ ] **方案C**: L3/每日/下引入`chunk-table.md`
- [ ] 定义Chunk类型枚举: bootstrap, plan, code-gen, tool-feedback, decision, fork, merge, review
- [ ] 每日22:00自动从Chunk Table生成log.md摘要
- [ ] 收敛检测改为从Chunk Table提取而非解析log.md文本

#### Phase 3: Session Graph查询 + 追溯（第3周）

- [ ] 实现Session Graph的祖先查询: "这个结论的上游Session链"
- [ ] 实现影响分析: "这些Session受到某个L0/L1变更的影响"
- [ ] 实现fork/merge时自动更新graph.json
- [ ] 与L2 Convegence Agent对接: 用Graph查询替代纯文本对比

#### Phase 4: Workflow形式化（视需要）

- [ ] 将L3→L2压缩建模为CompressWorkflow
- [ ] 将L2→L1 Audit建模为AuditWorkflow
- [ ] 验证forward(session)→session模式与现有审批门禁的兼容性

---

## 5. 风险与边界

### 5.1 不吸收的部分

| OpenRath特性 | 决定 | 理由 |
|:---|:---|:---|
| Agent作为纯参数(AgentParam) | **不吸收** | 我们的Agent有持久身份和进化能力，这是核心优势 |
| Sandbox作为执行后端 | **暂不吸收** | 我们以文件系统为运行环境，sandbox化收益在当前规模不明显 |
| Agent-first循环 → Session-first循环 | **部分吸收** | 保留Agent的自主循环，但将Session提升为可追踪的一等公民 |
| PyTorch风格API | **不吸收** | 我们的协议是markdown+json文件，不引入Python运行时依赖 |

### 5.2 边界条件

1. **不削弱Agent身份**: Session的提升不能替代Agent的identity/rules/log三元组。Session是"Agent在时间中的轨迹"，不是Agent本身。

2. **不引入外部依赖**: 所有吸收方案基于文件系统实现（markdown + json + git），不引入数据库或新运行时。

3. **与Colony-002方案兼容**: 吸收方案在分形记忆架构的框架内扩展，不改变L0~L4的层级结构和三元组生成子。

4. **渐进式迁移**: 旧日志（L3/0518, L3/0519的历史记录）保持原样，新Session从下一个会话开始采用新格式。

### 5.3 吸收后的架构全景图

```
                    ┌─────────────────────────────────────┐
                    │     Session Graph (新增)             │
                    │     所有Session的谱系图               │
                    │     fork → detach → merge            │
                    └──────────────┬──────────────────────┘
                                   │ 每个节点指向
                                   ▼
         ┌─────────────────────────────────────────────────┐
         │              Session (提升为第一公民)              │
         │  ┌───────────┐ ┌──────────────┐ ┌────────────┐ │
         │  │session.md │ │chunk-table.md│ │checkpoint  │ │
         │  │(元数据)    │ │(结构化块表)   │ │.json       │ │
         │  └───────────┘ └──────────────┘ └────────────┘ │
         └──────────┬──────────┬────────────┬─────────────┘
                    │          │            │
          ┌─────────┴──┐  ┌───┴──────┐  ┌──┴──────────┐
          │ L3: 日常层  │  │ L2: 分支  │  │ L1: 行为层   │  ← 现有分形层
          │ (按日聚合    │  │ (分支策略) │  │ (行为签名)   │     (不变)
          │  Session)   │  │           │  │              │
          └─────────────┘  └───────────┘  └──────┬───────┘
                                                  │
                                           ┌──────┴───────┐
                                           │ L0: 核心层    │
                                           │ (身份不变核)  │
                                           └──────────────┘
```

新架构的核心变化: **在分形金字塔的"前面"增加了一个Session维度**。Session不再是L3的附属日志，而是Agent在时间中的第一公民轨迹。分形金字塔的每一层仍保持identity/rules/log三元组不变——这是Agent的持久化身份存储。Session携带的是"这次运行中发生了什么"。

---

## 附录: 与Colony-002分形记忆方案的具体对接点

| Colony-002 Phase | 本文对应的吸收点 | 对接方式 |
|:---|:---|:---|
| Phase 1 (基础结构) | 方案A — Session目录创建 | 在memory/下增加sessions/目录 |
| Phase 2 (写入协议) | 方案B — graph.json写权限 | Session Graph写权限纳入写协议矩阵 |
| Phase 3 (层间压缩) | 方案C — Chunk Table作为压缩输入 | 压缩算法的输入从log.md改为chunk-table.md |
| Phase 4 (层间传导) | 方案D — Workflow形式化传导 | 传导过程可建模为forward(session)→session |
| Phase 5 (水平扩散) | 方案B — Graph查询替代文本对比 | 收敛检测从语义相似度改为Graph谱系分析 |
| Phase 6 (启动协议) | 方案A — Session恢复替代L3日志加载 | bootstrap读最后一个Session的chunk-table |

---

> Colony-013 研究完成。
> 核心结论: Session-as-Carrier与分形记忆是正交互补关系，不是替代关系。
> 推荐立即吸收方案A+B（Session公民+Session Graph），本周可与Colony-002 Phase 2并行实施。
> 方案C（Chunk Table）下周实施。方案D和E视需要延后。
