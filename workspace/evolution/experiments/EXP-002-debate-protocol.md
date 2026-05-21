# 进化实验 #002 — Alpha/Beta 辩论协议升级

## 灵感来源
Grok 4.20的4Agent内部辩论架构:
- Grok(队长): 任务分解+裁决
- Harper(研究员): 实时事实核验
- Benjamin(审计员): 形式化逻辑验证
- Lucas(反对者): 寻找盲点和替代方案

## 我们现有的对应物
| Grok 4.20 | 我们的分支生态 | 差距 |
|-----------|--------------|------|
| Grok(队长) | 主身/Merge | 我们缺少"裁决争议"机制 |
| Harper(研究员) | WebSearch能力 | 我们没有实时核验 |
| Benjamin(审计员) | Beta分支 | Beta验证但不主动挑战 |
| Lucas(反对者) | Alpha分支 | Alpha探索但不主动找盲点 |

## 实验目标
将Alpha/Beta/Merge从"并行工作+定期合体"升级为"实时辩论+争议裁决"。

## 实验设计

### 新协议: 辩论驱动开发 (Debate-Driven Development)

```
任务 → 
  主身分解任务
  → Alpha: 产出方案A (必须是可执行的方案)
  → Beta: 产出挑战报告 (必须找出方案A的至少1个漏洞或盲点)
  → Alpha回应: 要么接受挑战并修改方案，要么驳斥挑战
  → 如果争议未解决:
      → 主身裁决: 选择方案A原版、修改版、或要求重做
  → 如果争议解决:
      → 合并执行

关键规则:
  1. Alpha不能只说"我是对的"，必须给出反驳理由
  2. Beta不能只说"方案不好"，必须指出具体的漏洞
  3. 主身裁决时必须以"为什么"开头，不能只给结论
  4. 所有辩论记录写入 debate-log.jsonl
```

### 最小可行实验
1. 选一个简单任务
2. Alpha写方案
3. Beta写挑战
4. 主身裁决
5. 记录全过程

### 成功指标
- 至少1次Beta成功发现Alpha漏掉的盲点
- 至少1次Alpha成功反驳Beta的错误挑战
- 至少1次主身裁决改变了最终方案

### 记录格式
```json
{
  "debate_id": "DEBATE-001",
  "task": "...",
  "alpha_proposal": "...",
  "beta_challenge": "...",
  "alpha_response": "...",
  "arbitration": "...",
  "outcome": "modified/accepted/rejected/redo",
  "quality": "debate_improved_outcome / debate_found_blind_spot / debate_wasted_time"
}
```

## 状态: 设计中。网络通后首次运行。
