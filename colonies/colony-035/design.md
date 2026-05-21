# Colony v2.0 — L1 固定编排框架设计文档

> Colony-035 极限实验室 | 2026-05-19
> 状态: 已实现 (pipeline-orchestrator.py v2.0.0)

---

## 一、设计来源

直接来自 **Colony-029 内生性悖论** 的核心实验发现:

| 编排模式 | 协议 | 相对性能 |
|---------|------|:------:|
| 完全自主 | Shared | 最差 (基线) |
| 完全中心化 | Coordinator | 次优 |
| **固定编排+自主角色** | **Sequential** | **最优 (+44%)** |

结论: 固定编排是"靶子" —— Agent 需要知道当前阶段要产出什么类型的成果, 角色选择才有收敛方向。

---

## 二、架构概览

```
┌──────────────────────────────────────────────────────────────────────┐
│                    Colony Pipeline v2.0                               │
│                                                                      │
│  输入(任务) ──→ Stage 1: 情境感知 ──→ Stage 2: 方案生成                │
│                     ↑↓ 完整传递        ↑↓ 完整传递                    │
│                Stage 3: 执行实现 ←──→ Stage 4: 质量验证                │
│                     ↑ 完整传递           │ 失败→重试Stage 3            │
│                                           ↓                          │
│  输出(产物) ←─────────────────────────── 通过                        │
│                                                                      │
│  核心约束: 传递完整输出(非摘要!), Stage 4失败仅回溯Stage 3             │
└──────────────────────────────────────────────────────────────────────┘
```

---

## 三、四阶段定义

### Stage 1: 情境感知 (Context Ingestion)

| 维度 | 说明 |
|------|------|
| **类** | `ContextIngestionStage` |
| **输入** | 用户原始任务 + 历史上下文 + 环境状态 + 相关MR规则快照 |
| **Agent行为** | 每个Agent独立阅读全部输入, 自主声明关注点和能力匹配 |
| **输出** | 多维情境分析矩阵 + 缺口标记 + 风险预警 + 角色声明集 |
| **弃权** | 允许: 不匹配的Agent声明弃权并说明缺口 |
| **传递格式** | 完整分析文本 (非结构化摘要), 确保后续Agent看到完整信息 |

### Stage 2: 方案生成 (Strategy Formulation)

| 维度 | 说明 |
|------|------|
| **类** | `StrategyFormulationStage` |
| **输入** | Stage 1完整输出 (所有Agent的情境分析、缺口标记、风险预警) |
| **Agent行为** | 基于前置输出自主选择: 方案提出者 / 风险分析师 / 成本估算师 / 质疑者 |
| **输出** | 多角色方案集 + 方案间对比矩阵 + 推荐排序 + 角色变迁记录 |
| **弃权** | 允许: Agent可声明"此方案空间超出我的能力, 我仅质疑方案X的假设Y" |
| **关键约束** | 角色可以重置 —— Agent在Stage 1是"领域专家", 在Stage 2可变成"质疑者" |
| **特色** | 自动追踪角色变迁(agent在Stage 1 vs Stage 2的角色变化) |

### Stage 3: 执行实现 (Execution)

| 维度 | 说明 |
|------|------|
| **类** | `ExecutionStage` |
| **输入** | Stage 2完整输出 (所有方案文本, 含对比和推荐) |
| **Agent行为** | 根据方案具体内容自主选择执行角色; 允许多Agent并行执行不同子任务 |
| **输出** | 实际产物 (代码/文档/配置) + 执行者角色 + 执行日志 |
| **传递** | 前置Agent的**已完成产出**对后续Agent可见 (不是产出计划!) |
| **关键约束** | 内生性悖论最关键发现 —— Agent必须看到"已完成的工作"而不是"工作的计划" |

### Stage 4: 质量验证 (Quality Verification)

| 维度 | 说明 |
|------|------|
| **类** | `QualityVerificationStage` |
| **输入** | Stage 3完整输出 + Stage 1原始任务定义 |
| **Agent行为** | 自主选择验证角色: 端到端测试者 / 边界条件检查者 / 安全审计员 / 体验评审员 |
| **输出** | 多维质量报告 + 各Agent独立验证结论 + PASS/FAIL/PASS_WITH_WARNINGS/INCONCLUSIVE |
| **失败处理** | 验证失败 → 触发Stage 3局部重新执行 (不回溯到Stage 1/2) |

---

## 四、核心数据结构

### StageTransfer (Stage间传递标准体)

架构文档Section 2.3定义, 对齐实现:

```python
@dataclass
class StageTransfer:
    stage_id: int                                           # Stage编号
    stage_label: str                                        # 中文标签
    stage_outputs: dict[str, StageOutput]                   # {agent_id: 完整输出}
    role_assignments: list[RoleProposal]                    # 本Stage内实际承担的角色
    abstentions: list[AbstentionRecord]                     # 弃权记录
    gap_alerts: list[GapAlert]                              # 缺口告警
    metadata: StageMetadata                                 # 时间戳/版本/耗时
    predecessor: Optional[StageTransfer]                    # 前驱引用 (流水线追踪)
```

### 为什么传递"完整输出"而非"摘要"?

内生性悖论实验的机制B(自愿弃权)依赖于Agent看到的是**实际产出而非意图**。如果传递的是摘要, 信息不对称(意图vs实际产出之间的差距)被抹去, Agent无法做出准确的弃权判断。

### RoleProposal (角色提案)

```python
@dataclass
class RoleProposal:
    agent_id: str               # Agent身份
    stage_id: int               # 所在Stage
    role_name: str              # Agent自主命名的角色, 如 "数据库迁移风险评估师"
    role_category: str          # 自动聚类标签 (Layer 2)
    rationale: str              # 基于前置输出的角色选择理由
    contribution_plan: str      # 具体可验证的产出计划
    confidence: float           # 0.0-1.0
    abstain: bool               # 是否弃权
    abstention_reason: str      # 弃权理由 (缺口信息)
    dependencies: list[str]     # 依赖的其他Agent产出
```

### GapAlert (缺口告警)

触发条件: 某个任务域 ≥ 50% Agent弃权 → 缺口告警
严重度: critical (≥75%) / warning (≥50%)

---

## 五、关键设计决策

| 决策ID | 决策 | 替代方案 | 选择理由 |
|--------|------|---------|---------|
| D-L1-001 | Stage数量固定为4 | 动态Stage数量 | 内生性悖论实验证明固定框架是必要的; 四个阶段覆盖任务全生命周期 |
| D-L1-002 | 传递完整输出而非摘要 | 摘要传递 | 自愿弃权机制依赖信息完整性; 摘要导致Agent无法做出准确弃权判断 |
| D-L1-003 | 验证失败仅回溯Stage 3 | 全Pipeline回溯 | Stage 1/2的分析和方案是稳定的上下文, 执行问题的根因在Stage 3 |
| D-L1-004 | Stage 3最大重试次数可配置(默认3) | 无限重试 | 防止无限循环; 超额后由人工介入 |
| D-L1-005 | 角色可跨Stage重置 | 角色锁定 | 内生性悖论实验发现Agent在不同Stage承担不同角色效果更好 |
| D-L1-006 | PipelineConfig配置化 | 硬编码 | 支持A/B测试不同参数组合; 后续NeuroMAS优化需要可配置接口 |

---

## 六、可配置参数 (PipelineConfig)

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `max_retry_stage3` | int | 3 | Stage 4失败后Stage 3最大重试次数 |
| `abstention_alert_threshold` | float | 0.5 | 弃权比例阈值 (≥此值触发缺口告警) |
| `agent_pool` | list[str] | [...] | Agent池ID列表 |
| `enable_role_election` | bool | True | 启用动态角色选举 |
| `enable_abstention` | bool | True | 启用自愿弃权 |
| `enable_gap_detection` | bool | True | 启用缺口检测 |
| `stage_timeout_seconds` | int | 600 | 单Stage超时 (秒) |
| `output_dir` | str | "" | 产物输出目录 |

---

## 七、文件结构

```
/d/极限实验室/colonies/colony-035/
├── mission-brief.md              # 任务简报
├── pipeline-orchestrator.py      # 主实现 (~570行)
│   ├── Section 1: 核心数据结构    (StageTransfer, RoleProposal, ...)
│   ├── Section 2: Agent抽象基类  (BaseAgent)
│   ├── Section 3: 仿真Agent      (SimulatedAgent, 演示用)
│   ├── Section 4: Stage实现      (4个Concrete Stage)
│   ├── Section 5: Pipeline编排器  (PipelineOrchestrator)
│   └── Section 6: CLI与演示      (argparse + run_demo)
└── design.md                    # 本设计文档
```

### 类层次

```
BaseAgent (ABC)
  └── SimulatedAgent          ← 演示用; 实际部署时替换为 LLMAgent

BaseStage (ABC)
  ├── ContextIngestionStage   ← Stage 1
  ├── StrategyFormulationStage ← Stage 2
  ├── ExecutionStage           ← Stage 3
  └── QualityVerificationStage ← Stage 4

PipelineOrchestrator           ← 主编排器
  ├── add_agent() / add_agents()
  ├── run(task_context) → (transfers, metrics)
  └── export_report(transfers, metrics, path)
```

---

## 八、使用方式

### 命令行

```bash
# 运行内置演示
python pipeline-orchestrator.py

# 指定自定义任务
python pipeline-orchestrator.py --task "实现用户认证模块"

# 自定义Agent数量和重试次数
python pipeline-orchestrator.py -a 5 -r 5 --task "修复数据库死锁"

# 不导出报告
python pipeline-orchestrator.py --no-export

# 详细日志
python pipeline-orchestrator.py --verbose
```

### 编程接口

```python
from pipeline_orchestrator import *

# 1. 创建配置
config = PipelineConfig(
    max_retry_stage3=3,
    agent_pool=["Agent-1", "Agent-2"],
    output_dir="./output",
)

# 2. 创建编排器和Agent
orchestrator = PipelineOrchestrator(config)
orchestrator.add_agent(SimulatedAgent("Agent-1", ["开发", "架构"]))
orchestrator.add_agent(SimulatedAgent("Agent-2", ["测试", "安全"]))

# 3. 创建任务上下文
task = TaskContext(
    task_id="TASK-001",
    original_task="实现XXX功能",
    history_context="前置已完成数据库设计",
    constraints=["性能要求: <100ms"],
    priority="high",
)

# 4. 执行Pipeline
transfers, metrics = orchestrator.run(task)

# 5. 导出报告
orchestrator.export_report(transfers, metrics, "./output/report.json")

# 6. 查看结果
print(f"结论: {metrics.final_verdict}")
print(f"耗时: {metrics.total_duration_ms:.0f}ms")
print(f"重试: {metrics.stage3_retry_count}")
```

---

## 九、集成点 (与其他Layer的接口)

| 上层 | 集成方式 | 状态 |
|------|---------|:----:|
| **Layer 2 (动态角色)** | `RoleProposal` 输出给 Colony-036 的角色选举系统 | 待集成 |
| **Layer 3 (Nexa通信)** | 每个Stage内部可接入 `nexa-router.py` 做条件串行路由 | 待Colony-037 |
| **Layer 4 (GEPA进化)** | `StageOutput.content` 作为GEPA的执行轨迹输入 | 待Colony-038 |
| **Layer 5 (Auto-GE)** | `PipelineMetrics` 作为停滞检测的输入信号 | 待Colony-039 |
| **Layer 0 (安全)** | 每个Stage执行前/后校验 core_self 兼容性 | 待Colony-040 |

---

## 十、验证清单

| 验证项 | 状态 |
|--------|:----:|
| 四阶段按序执行 (1→2→3→4) | PASS |
| Stage间传递完整StageTransfer | PASS |
| 角色变迁追踪 (Stage 1→2) | PASS |
| 弃权记录 + 缺口检测 (≥50%) | PASS |
| Stage 4失败 → Stage 3重试 (不回溯1/2) | PASS |
| CLI参数解析 (--task, --agents, --max-retry, --no-export) | PASS |
| JSON报告导出 (含完整指标) | PASS |
| 4个Stage全部出现在transfers报告中 | PASS |
| PipelineMetrics (耗时/重试/弃权/告警) | PASS |

---

## 十一、后续优化方向

1. **真实LLM Agent接入**: 替换 `SimulatedAgent` 为调用 Claude API 的 `LLMAgent`
2. **Stage间并行化**: Stage 3支持Agent间并行执行 (需要Layer 3 Nexa通信)
3. **Stage数量A/B测试**: 对比3/4/5/6个Stage的效果 (需要NeuroMAS式优化)
4. **配置文件**: 支持从 `pipeline-config.json` 加载完整配置
5. **WebHook回调**: Stage完成后触发外部系统通知
6. **Streaming输出**: 支持Stage产物的流式传输 (大产物场景)

---

*Colony-035 极限实验室 | 2026-05-19 | v2.0.0*
*实现对齐 Colony-034 架构文档 Section 2 (Layer 1) 全部规范*
