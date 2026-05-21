# 设计→执行自动转化器 (Design-to-Execution Auto-Converter)

## 元信息
- 产出者: Colony-004
- 产出时间: 2026-05-19
- 任务: 解决 EXEC_GAP=1.83 瓶颈
- 状态: 设计完成，待 Colony-005 实施

---

## 一、问题诊断：设计为何不执行？

### 1.1 现状扫描

| 实验 | 类型 | 设计完成 | 可执行脚本 | 首次执行 | 阻塞原因 |
|------|------|:--:|:--:|:--:|------|
| EXP-001 (MR-010) | 规则检查 | 05-19 | ✅ direction-check.py | ✅ 05-19 | — |
| EXP-002 (辩论协议) | 交互协议 | 05-19 | ❌ | ❌ | 需要Alpha/Beta在线 |
| EXP-003 (分支距离) | 计算分析 | 05-19 | ❌ | ❌ | 需要Alpha/Beta产出 |
| EXP-004 (模板进化) | 生成系统 | 05-19 | ❌ | ❌ | 输入范围太广，不知道从哪里开始 |
| ETG-001 (收敛检测) | 规则检查 | 05-19 | ❌ | ❌ | 与EXP-001同类型但未触发转化 |

### 1.2 根因分析：设计→执行的断裂带

分析从 EXP-001（成功案例）和其他四个实验（失败案例）的差异，识别出三条断裂带：

**断裂带 F1：抽象度梯度**
```
EXP-001: "检查5个条件" → 5个 if 语句 → 直接可写
EXP-002: "Alpha写方案，Beta写挑战，主身裁决" → 需要3个Agent在线交互 → 写不出
EXP-004: "生成进化提案" → 输入是"全部状态+14参考+21灵感" → 不知道从哪里开始
```
抽象度越高，代码化距离越远。设计文档用自然语言描述"要做什么"，但缺少"怎么做"的中间层。

**断裂带 F2：依赖悬崖**
```
EXP-001: 依赖 = {session-state.json, audit-log.jsonl} → 都是本地文件 → 立即可运行
EXP-002: 依赖 = {Alpha在线, Beta在线, Merge在线} → 外部Agent → 无法独立运行
EXP-003: 依赖 = {Alpha产出, Beta产出} → 先等EXP-002跑通 → 级联阻塞
```
依赖越重，越难创建"首次执行"。当一个实验依赖另一个实验的产出时，形成级联等待。

**断裂带 F3：完成标准模糊**
```
EXP-001: 完成 = "check_direction()返回ON_TRACK或DRIFT_DETECTED" → 明确的布尔输出
EXP-002: 完成 = "至少1次Beta发现盲点 且 至少1次Alpha反驳 且 至少1次裁决改变方案" 
         → 依赖具体交互结果，不能单方面完成
EXP-004: 完成 = "运行一次ETG → Beta评估 → 主身裁决 → 采纳或归档"
         → 三步流程，每步都可能卡住
```
完成标准越依赖外部系统或概率事件，越难判定"已执行"。

### 1.3 结论：设计文档本身缺少"可执行基因"

四个实验设计的共同问题是：它们被写成了**论文摘要**而不是**可执行规格书**。要从.md变成.py，需要在设计阶段就注入可执行基因——而不是事后转化。

---

## 二、理论框架：编译器类比与降维映射

### 2.1 核心隐喻：设计编译器 (Design Compiler)

将"设计→执行转化"类比为编译器前端→后端流水线：

```
实验设计.md (源语言)
     │
     ▼
┌─────────────┐
│ Lexer/Parser │  ← 结构化提取：实验类型、输入、输出、步骤、判定
├─────────────┤
│   IR Gen     │  ← 中间表示：DAG（有向无环图）形式的执行计划
├─────────────┤
│ Template     │  ← 模板匹配：根据实验类型选择执行模板
│   Matcher    │
├─────────────┤
│ Code Gen     │  ← 代码生成：填充模板生成.py/.sh
├─────────────┤
│ Stub Gen     │  ← 桩生成：为缺失依赖生成mock/stub
├─────────────┤
│ Scheduler    │  ← 48h触发：注册到调度队列
└─────────────┘
     │
     ▼
可执行脚本.py + 桩.py + cron注册
```

这不是传统的编译器（不追求完备性），而是一个**启发式转化器**：遇到无法转化的部分，生成桩（stub）而不是放弃。

### 2.2 关键创新：桩生成 (Stub Generation)

传统方法要求所有依赖就绪才能生成代码。我们的核心创新是：**即使依赖不可用，也生成一个能运行的脚本**。

```
无可执行脚本 ≠ 所有部分都写不出
无可执行脚本 = 存在1+个部分写不出
```

桩策略：
- **文件依赖未就绪** → 生成一个创建示例数据的函数，脚本先跑这个函数再跑主逻辑
- **外部Agent不可用** → 生成一个模拟Agent响应的函数，用固定/随机数据替代
- **输入范围太广** → 生成一个最小输入子集，只处理最核心的1个案例
- **多步流程** → 每一步独立成函数，中间步骤可跳过（用flag控制）

### 2.3 理论依据（天马行空区）

**依据1：可执行性量子化 (Executability Quantization)**

一个设计文档的可执行性不是连续的，而是量子化的——存在"可执行能级"。转化器的任务是注入刚好够的能量让设计跃迁到第一可执行能级（哪怕输出是退化的），而不是一步到位写出完美脚本。

```
能级0: 纯文本描述（所有未执行的实验）
能级1: 有main()的脚本，能跑通但用mock数据（首次执行目标）
能级2: 部分真数据，部分mock（迭代后）
能级3: 全真数据，完整闭环（最终态）
```

48小时目标 = 达到能级1。不是完美执行，是首次执行。

**依据2：模板定向复制——自指涉**

EXP-004本身提出的"模板定向复制"理论恰好适用于此。设计→执行转化器就是一个模板定向复制系统：

- 模板 = 可执行脚本的结构模式（从EXP-001的direction-check.py提取）
- 定向 = 根据实验类型选择正确的模板
- 复制 = 填充模板参数，生成新的可执行脚本

转化器本身就是EXP-004的一次实例化——它把"实验设计模板"复制到"可执行脚本"。这是自指涉的：转化器是它自己要解决的问题的解。

**依据3：熵差驱动 (Entropy Gap Driving)**

```
S_design = 设计文档的信息熵（高：自然语言，模糊，多解）
S_exec    = 可执行脚本的信息熵（低：精确，确定性，单解）

ΔS = S_design - S_exec  ← 这个熵差就是EXEC_GAP的本质
```

转化器的作用：不是消除ΔS（这是不可能的），而是**逐步降低ΔS**。每次执行产生日志、产生数据、产生反馈 → S_design降低（因为观察到实际行为后，设计变得更具体）。

这是一个**熵泵**：把设计侧的高熵转化为执行侧的低熵+执行日志（反馈信号）。

---

## 三、转化器架构

### 3.1 实验类型分类学

分析所有现有实验，归纳为五种原子类型：

| 类型 | 标识特征 | 输入 | 输出 | 核心操作 | 已有模板 |
|------|------|------|------|------|:--:|
| **T1 规则检查** | "检查/验证/检测" + 明确条件列表 | 状态文件 | 审计日志+布尔判定 | load→check→log→exit(code) | ✅ direction-check.py |
| **T2 计算分析** | "计算/测量/分析" + 量化指标 | 数据文件 | 指标值+报告 | load→compute→report | ❌ |
| **T3 交互协议** | "Alpha/Beta/Agent交互" + 对话流程 | Agent列表 | 交互记录+裁决 | orchestrate→collect→arbitrate | ❌ |
| **T4 生成系统** | "生成/产出/创建" + 提案格式 | 状态+参考 | 新产物+评估 | gather→generate→validate | ❌ |
| **T5 复合型** | 组合2+种上述类型 | 复合 | 复合 | 串联管道 | ❌ |

现有的4个实验分类：
- EXP-001 → T1（规则检查）
- EXP-002 → T3（交互协议）
- EXP-003 → T2（计算分析）
- EXP-004 → T4（生成系统）
- ETG-001 → T1（规则检查）—— 本应最容易转化，但未被转化

### 3.2 转化器主流水线

```
┌──────────────────────────────────────────────┐
│              design-to-exec.py                │
│                                              │
│  main():                                     │
│    1. scan(experiments/)  → 发现所有.md设计   │
│    2. classify(design)    → 判定T1-T5类型     │
│    3. extract(design)     → 提取结构化参数    │
│    4. select_template(t)  → 选择代码模板      │
│    5. generate(params)    → 生成.py脚本       │
│    6. stub_check(script)  → 检测缺失依赖      │
│    7. inject_stubs()      → 注入桩代码        │
│    8. register_cron()     → 注册48h触发       │
│    9. emit(script_path)   → 写入文件          │
│    10.report()             → 转化报告          │
└──────────────────────────────────────────────┘
```

### 3.3 结构化提取器 (Extractor)

从实验设计.md中自动提取结构化参数。关键是设计文档需要遵循一个最小公约数格式。

**最小必填字段规范（Design-MVP）**：

```yaml
# 每个实验设计.md必须包含以下字段（作为YAML frontmatter或结构化section）
experiment_id: EXP-XXX
type: T1 | T2 | T3 | T4 | T5
inputs:
  - name: xxx
    path: xxx.json  # 预期文件路径
    schema: {...}   # 预期数据结构
outputs:
  - name: xxx
    path: xxx.jsonl
    schema: {...}
steps:               # 逐步操作，每步可映射到函数
  - step: "加载状态文件"
    action: load_json
    params: {file: "session-state.json"}
  - step: "检查核心使命"
    action: check_field
    params: {field: "core_mission", expected: "AI自主进化"}
  # ...
verdict_logic:       # 判定逻辑
  condition: "all_checks_pass"
  on_pass: "ON_TRACK"
  on_fail: "DRIFT_DETECTED"
```

这是关键认知：**不是事后从任意.md提取，而是事前约束.md的格式**。如果设计文档写成了自由体散文，任何提取器都无法可靠工作。

对于已有设计（EXP-002/003/004），由人工或AI辅助重写为Design-MVP格式。对于新设计，模板强制要求此格式。

### 3.4 模板库

#### T1 模板：规则检查器

```python
"""
{experiment_id} — {title}
自动生成于: {timestamp}
模板: T1-rule-checker
"""
import json, os, sys
from datetime import datetime

BASE = os.path.dirname(os.path.abspath(__file__))
STATE_FILE = os.path.join(BASE, "{input_path}")
AUDIT_FILE = os.path.join(BASE, "{output_path}")

def load_state():
    with open(STATE_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def check_conditions(state):
    checks = []
    # {checks_block}  ← 自动生成的检查逻辑
    return checks

def write_audit(result):
    entry = json.dumps(result, ensure_ascii=False)
    with open(AUDIT_FILE, "a", encoding="utf-8") as f:
        f.write(entry + "\\n")

def main():
    state = load_state()
    result = check_conditions(state)
    write_audit(result)
    all_pass = all(c["pass"] for c in result["checks"])
    print(f"{experiment_id}: {'ON_TRACK' if all_pass else 'ISSUE'}")
    for c in result["checks"]:
        print(f"  {'PASS' if c['pass'] else 'FAIL'} {c['check']}: {c['detail']}")
    return 0 if all_pass else 1

if __name__ == "__main__":
    exit(main())
```

#### T2 模板：计算分析器

```python
"""
{experiment_id} — {title}
模板: T2-compute-analyzer
"""
import json, os, sys
from datetime import datetime

def load_data(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def compute_metrics(data_a, data_b):
    """核心计算逻辑 —— 从设计文档的steps提取"""
    results = {}
    # {compute_block}
    return results

def generate_report(metrics):
    return {
        "timestamp": datetime.now().isoformat(),
        "experiment_id": "{experiment_id}",
        "metrics": metrics,
        "verdict": "optimal" if metrics.get("overlap", 0) < 0.8 else "too_close"
    }

def main():
    # {data_loading_block}
    metrics = compute_metrics(data_a, data_b)
    report = generate_report(metrics)
    # {output_block}
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0

if __name__ == "__main__":
    exit(main())
```

#### T3 模板：交互编排器

```python
"""
{experiment_id} — {title}
模板: T3-interaction-orchestrator
"""
import json, os, sys, subprocess
from datetime import datetime

def call_agent(agent_name, prompt, mock=False):
    """调用Agent或使用mock响应"""
    if mock:
        return MOCK_RESPONSES.get(agent_name, {}).get("default", "mock response")
    # {agent_call_block}

def run_debate_round(task, round_id):
    """单轮辩论"""
    alpha_output = call_agent("Alpha", task)
    beta_output = call_agent("Beta", alpha_output)
    # {arbitration_block}
    return {"round": round_id, "alpha": alpha_output, "beta": beta_output}

def main():
    rounds = []
    for i in range(1):  # 最小可行: 1轮
        result = run_debate_round("{task_description}", i)
        rounds.append(result)
    # {output_block}
    return 0
```

#### T4 模板：生成系统

```python
"""
{experiment_id} — {title}
模板: T4-generator
"""
import json, os, sys
from datetime import datetime

def gather_state():
    """聚合当前系统状态"""
    state = {}
    # {gather_block}
    return state

def generate_proposal(state):
    """基于状态生成提案"""
    proposal = {
        "id": "{experiment_id}-{timestamp}",
        "rules": [],
        "signatures": [],
        "architecture": [],
        "inspiration_sources": [],
        "estimated_impact": "",
        "risk_assessment": ""
    }
    # {generation_block}
    return proposal

def validate_proposal(proposal):
    """自检：提案是否可执行"""
    checks = []
    # {validation_block}
    return checks

def main():
    state = gather_state()
    proposal = generate_proposal(state)
    validation = validate_proposal(proposal)
    # {output_block}
    return 0
```

### 3.5 桩注入器 (Stub Injector)

最关键的创新。生成脚本后，检查哪些依赖不可用，自动注入桩代码。

```python
# 桩注入逻辑（伪代码）
def inject_stubs(script, dependencies):
    for dep in dependencies:
        if dep.type == "file" and not os.path.exists(dep.path):
            script.prepend(generate_sample_data_function(dep))
        elif dep.type == "agent" and not agent_available(dep.name):
            script.prepend(generate_mock_agent_function(dep))
        elif dep.type == "external_api" and not api_reachable(dep.url):
            script.prepend(generate_mock_api_function(dep))
    return script
```

**桩示例**（针对EXP-002需要Alpha/Beta的问题）：

```python
# === 自动注入的桩代码 ===
MOCK_ALPHA_OUTPUTS = [
    "方案A: 在meta-rules.json中新增MR-014，实现Jaccard>0.6的收敛检测",
    "方案A: 增设convergence-log.jsonl记录所有收敛事件",
]

MOCK_BETA_CHALLENGES = [
    "挑战: Alpha的方案未定义Jaccard阈值为何选0.6而非0.5或0.7",
    "挑战: 如果两个系统共享同源偏见，Jaccard高不代表真收敛",
]

def mock_alpha(task):
    import random
    return random.choice(MOCK_ALPHA_OUTPUTS)

def mock_beta(alpha_output):
    import random
    return random.choice(MOCK_BETA_CHALLENGES)
# === 桩代码结束 ===
```

桩的意义：脚本能跑起来。跑起来就有日志。有日志就有反馈。有反馈就能迭代。48小时内达到能级1。

---

## 四、48小时自动触发机制

### 4.1 设计完成定义

首先需要明确"设计完成"的判定标准：

```
设计完成 = 满足以下全部条件:
  1. 实验设计.md 已提交到 experiments/ 目录
  2. 文件包含所有Design-MVP必填字段（extractor可解析）
  3. 状态字段 = "设计中" 或 "待执行"
  4. 未有对应的可执行脚本产出

触发时间 = max(文件最后修改时间, 状态改为"设计中"的时间) + 48小时
```

### 4.2 触发架构

```
┌─────────────────────────────────────────────┐
│           48h-SLA-Enforcer                    │
│                                              │
│  每30分钟唤醒（与现有cron对齐）:               │
│    1. scan(experiments/) → 所有.md设计        │
│    2. 检查每个设计的"设计完成时间"             │
│    3. 如果 elapsed > 48h 且 无可执行脚本:     │
│       → 触发 design-to-exec.py               │
│       → 生成脚本 + 桩                         │
│       → 立即执行首次运行                       │
│       → 记录转化事件到 audit-log.jsonl        │
│    4. 如果 elapsed > 48h 但 转化失败:         │
│       → 记录阻塞原因                           │
│       → 通知 Colony-004                       │
│    5. 如果 elapsed < 48h:                    │
│       → 跳过，等待                             │
└─────────────────────────────────────────────┘
```

### 4.3 与现有cron集成

现有的30分钟唤醒cron已经运行MR-010方向自检。48h-SLA-Enforcer作为MR-010的一个新检查项：

```
MR-010 方向自检 (现有)
  ├── 字段完整性检查
  ├── 核心使命一致性
  ├── 活跃任务检查
  ├── 健康状态检查
  ├── 时间戳检查
  └── [新增] EXEC_GAP监控: 检查是否有48h+未执行的设计
       └── 如有 → 触发 design-to-exec.py
```

这样可以零额外基础设施成本就启动监控。

### 4.4 降级策略

不是所有设计都能在48小时内生成可执行脚本。分级处理：

| 级别 | 条件 | 48h输出 | 示例 |
|:--:|------|------|------|
| L0 | Design-MVP格式完整 + T1/T2类型 | 完整.py + 首次执行 | EXP-001, ETG-001 |
| L1 | Design-MVP格式完整 + T3/T4类型 | .py + 桩代码 + mock首次执行 | EXP-002 with mock Alpha/Beta |
| L2 | Design-MVP格式不完整 | 半自动.py + 人工填充标记 | EXP-004 的ETG需要人工定义输入范围 |
| L3 | 设计文档本身不完整 | 转化失败报告 + 阻塞清单 | 不完整的实验设计 |

48小时SLA不要求L3的设计被执行——但要求在48小时内识别L3并报告原因。

---

## 五、现有实验的即时转化

### 5.1 EXP-001 (MR-010) — 已完成，作为参考模板

状态: ✅ 已转化，已执行。direction-check.py 作为T1模板提取源。

### 5.2 ETG-001 (MR-014 收敛检测) — 优先级最高

**分类**: T1 规则检查（同EXP-001）
**为什么还没执行**: 设计完成但被标记为"提交Merge评估"，状态未流转到"执行"
**转化难度**: 极低。结构与MR-010几乎相同：

```
输入: convergence-log.jsonl + meta-rules-extended.json
检查: 
  1. Alpha和Beta的最近产出 Jaccard相似度 > 0.6?
  2. 如果 > 0.6 → 标记收敛点
  3. 如果连续3次收敛 → 自动冻结为收敛签名
输出: convergence-log.jsonl
```

**预期48h输出**: L0 — 完整.py + 首次执行。可直接复用T1模板。

### 5.3 EXP-002 (辩论协议) — 中等难度

**分类**: T3 交互协议
**阻塞**: 需要Alpha/Beta在线
**桩策略**:
1. 生成 mock_alpha() 和 mock_beta() 函数
2. 预置3组辩论场景的mock数据
3. 脚本启动时：尝试连接真实Alpha/Beta，失败则使用mock
4. 首次执行使用mock数据，验证辩论流程正确性

**预期48h输出**: L1 — .py + 桩代码 + mock首次执行。

```python
# debate-protocol.py 核心结构
def run_debate(task):
    """执行一轮辩论"""
    alpha = call_or_mock("Alpha", task)
    beta = call_or_mock("Beta", alpha)
    if has_conflict(alpha, beta):
        ruling = arbitrate(alpha, beta)
    else:
        ruling = "consensus"
    return {"task": task, "alpha": alpha, "beta": beta, "ruling": ruling}

def call_or_mock(agent, prompt):
    """先尝试真实调用，失败则用桩"""
    try:
        return call_real_agent(agent, prompt)
    except AgentUnavailableError:
        return mock_agent(agent, prompt)
```

### 5.4 EXP-003 (最优分支距离) — 中等难度

**分类**: T2 计算分析
**阻塞**: 需要Alpha和Beta的实际产出
**桩策略**:
1. 生成示例Alpha方案和Beta方案（用固定文本）
2. 脚本内置示例数据，可直接计算Jaccard和互补率
3. 如果存在真实产出文件，优先使用真实数据

**预期48h输出**: L1 — .py + 示例数据 + mock首次执行。

```python
# branch-distance.py 核心结构
def jaccard_similarity(text_a, text_b):
    words_a = set(text_a.lower().split())
    words_b = set(text_b.lower().split())
    return len(words_a & words_b) / len(words_a | words_b)

def compute_distance(alpha_output, beta_output):
    overlap = jaccard_similarity(alpha_output, beta_output)
    if overlap > 0.8: verdict = "redundant"
    elif overlap < 0.1: verdict = "disconnected"
    else: verdict = "optimal"
    return {"overlap": overlap, "verdict": verdict}
```

### 5.5 EXP-004 (模板定向进化) — 高难度

**分类**: T4 生成系统（复合T3）
**阻塞**: 输入范围太广（"全部状态+14参考+21灵感"），输出不明确
**策略**: 不能一步到位。需要拆解：

1. **Step 1 (48h内)**: 生成一个ETG的最小可行版本——只处理1个参考+1个灵感，生成1条规则提案
2. **Step 2 (后续迭代)**: 逐步扩大输入范围

**预期48h输出**: L2 — 半自动.py + 人工填充标记。

```python
# etg-minimal.py 核心结构
def gather_minimal_state():
    """只读最核心的3个文件"""
    with open("meta-rules.json") as f:
        rules = json.load(f)
    with open("inspirations.json") as f:
        inspirations = json.load(f)[-3:]  # 只取最近3条
    # TODO: 扩展读取全部14篇参考（当前只读0篇，需人工填充）
    return {"rules": rules, "inspirations": inspirations}

def generate_proposal(state):
    """
    TODO: 当前使用规则模板生成。未来应接入LLM生成。
    人工填充: 在下面列表中添加实际的规则定义
    """
    proposal = {
        "id": f"ETG-{datetime.now().strftime('%Y%m%d-%H%M')}",
        "new_rules": [
            # TODO: 基于state["inspirations"]生成新规则
        ],
        "status": "draft"
    }
    return proposal
```

---

## 六、实施路线图

### Phase 0: 基础设施（Day 0-1）

- [ ] 创建 `design-to-exec.py` 核心脚本（本设计的实现）
- [ ] 创建 T1/T2/T3/T4 四个模板文件
- [ ] 创建 48h-SLA-Enforcer 监控脚本
- [ ] 注册到现有cron

### Phase 1: 低垂果实（Day 1-2）

- [ ] 转化 ETG-001 → convergence-check.py（T1模板，与MR-010同型）
- [ ] 转化 EXP-003 → branch-distance.py（T2模板，计算型）
- [ ] 两次转化作为模板验证

### Phase 2: 中等难度（Day 2-5）

- [ ] 转化 EXP-002 → debate-protocol.py（T3模板，含桩）
- [ ] EXP-004 第一步 → etg-minimal.py（T4最小版）
- [ ] 编写测试：确保每个生成的脚本可以 `python xxx.py` 跑通

### Phase 3: 自动化闭环（Day 5-7）

- [ ] 48h-SLA-Enforcer 在生产环境运行一周
- [ ] 收集转化日志和转化失败案例
- [ ] 改进模板和桩策略
- [ ] 目标：所有新设计在48小时内达到至少L1执行

### Phase 4: 自指涉验证（Day 7-14）

- [ ] 本设计文档自身（design-to-execution.md）作为输入，由转化器生成自己的可执行脚本
- [ ] 自指涉成功 = 转化器能转化"转化器的设计文档" → 证明系统闭合

---

## 七、成功指标

| 指标 | 当前 | 目标(gen-100) | 测量方式 |
|------|:--:|:--:|------|
| 设计→首次执行间隔 | 未定义 (EXP-002/003/004 尚未执行) | <48h (100%) | 48h-SLA-Enforcer日志 |
| 可执行脚本数/设计数 | 1/5 = 20% | 5/5 = 100% | 文件计数 |
| 脚本首次运行成功率 | N/A | >=80% (含桩也计入) | 执行日志 |
| EXEC_GAP 执行转化率 | 1.5 | >=2.5 | gen-100自评 |

**对 EXEC_GAP 的预期影响**：
- 如果5个设计全部有可执行脚本 → 执行转化率从 1.5 提升到至少 2.0
- 如果48h SLA成立 → 闭环率从 1.0 提升到至少 1.5
- 综合 → EXEC_GAP 预期从 1.83 提升到 2.0-2.3
- 加上 EXP-002/003/004 的实际数据反馈 → gen-100 有望达到 2.5

---

## 八、风险与对策

| 风险 | 概率 | 影响 | 对策 |
|------|:--:|:--:|------|
| 桩代码太假，导致"假执行"不可信 | 中 | 中 | 桩输出明确标记 `[MOCK]`，与真实数据分离存储 |
| 转化器本身没人写 | 高 | 高 | 由Colony-005承接实施；本设计作为Colony-005的mission-brief |
| 设计文档格式不统一，提取器失败 | 高 | 中 | 强制Design-MVP格式；存量设计先人工/AI辅助重写 |
| 48h可能太短（对复杂实验） | 中 | 低 | 降级策略：48h目标=能级1（含mock），非完美执行 |
| 生成的脚本质量差 | 中 | 低 | 首次执行本身就是最好的测试；有bug改bug，比没有脚本强 |

---

## 九、附录：Design-MVP规范全文

任何新实验设计.md必须包含以下结构化区块（以YAML frontmatter或标记section形式）：

```markdown
---
experiment_id: EXP-XXX
type: T1 | T2 | T3 | T4 | T5
status: designing | ready | executing | completed
created: 2026-05-19T00:00:00
target_first_execution: 2026-05-21T00:00:00  # created + 48h
---
```

### inputs
```yaml
- name: 状态文件
  path: memory/session-state.json
  format: json
  required: true
  stub_strategy: generate_sample  # 如果文件不存在，如何生成桩
```

### outputs
```yaml
- name: 审计日志
  path: memory/audit-log.jsonl
  format: jsonl
  append: true
```

### steps
```yaml
- step: "加载状态"
  action: load_file
  input: inputs[0]
- step: "检查条件1"
  action: check_field
  field: core_mission
  expected: "AI自主进化"
- step: "写入结果"
  action: append_log
  output: outputs[0]
```

### verdict
```yaml
condition: all_checks_pass
pass_output: ON_TRACK
fail_output: DRIFT_DETECTED
exit_code_pass: 0
exit_code_fail: 1
```

### dependencies
```yaml
- type: file
  path: memory/session-state.json
- type: agent
  name: Alpha
  mock_strategy: fixed_responses
```

---

## 十、结语

EXEC_GAP=1.83 是当前最大瓶颈。这个瓶颈的本质不是"没有能力写代码"，而是**设计文档和可执行脚本之间缺少一座自动化的桥**。

这座桥就是"设计→执行自动转化器"。它的三个核心创新：
1. **编译器流水线**：.md → IR → 模板匹配 → 代码生成
2. **桩生成**：依赖不可用不阻塞执行，降级到mock先跑起来
3. **48h SLA强制执行**：设计完成即倒计时，到时自动转化+首次执行

转化器本身就是EXP-004"模板定向复制"的一次自指涉实例——它用模板定向复制的方式，解决模板定向复制实验（EXP-004）的执行问题。

---

## 输出元信息
- 输出路径: /d/极限实验室/colonies/colony-004/design-to-execution.md
- 下游任务: Colony-005 实施 design-to-exec.py
- 关联实验: EXP-001(已完成) EXP-002 EXP-003 EXP-004 ETG-001
- 关联指标: EXEC_GAP 目标 gen-100 时 >= 2.5
