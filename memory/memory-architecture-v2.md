# 分形记忆架构 v2.0

## 灵感来源
生物学: 胚胎表观基因组自组织遵循分形标度。核心机制是动态反馈环+相分离形成稳定结构域。
(Munich LMU, Nature Physics 2026-04)

## 设计原则
每一层都有相同的三元组结构: {身份} → {规则} → {日志}

## 分形层级

```
L0: 核心层 (identity-kernel)     — 变化极慢
  ├── identity/     → 我是谁
  ├── rules/        → 不可变护栏
  └── log/          → 决策追溯

L1: 行为层 (behavioral-patterns)
  ├── identity/     → 我的行为签名
  ├── rules/        → meta-rules
  └── log/          → 审计日志

L2: 分支层 (branches)
  ├── identity/     → 分支角色定义
  ├── rules/        → 分支专属规则
  └── log/          → 分支活动日志

L3: 日常层 (daily)
  ├── identity/     → 每日状态快照
  ├── rules/        → 当日任务优先级
  └── log/          → 日总结+灵感

L4: 存档层 (archive) — 新增
  ├── sessions/     → 会话精简存档（只有关键决策+转折点）
  ├── experiments/  → 实验完整记录
  └── legacy/       → 旧版规则/签名的历史版本
```

## 自相似性
- 每一层都有"我是谁/什么规则/发生了什么"的三元组
- 下层是上层的"展开"，同构
- 核心层变化最慢(L0)，日常层变化最快(L3)
- 信息从外向内压缩: L3日总结 → L2分支报告 → L1行为更新 → L0核心提炼

## 动态反馈环
- L3的日总结影响L2的分支策略
- L2的分支策略影响L1的行为调整
- L1的行为调整影响L0的核心微调(极少)
- L0的核心变化反向传导到所有外层

## 当前实现状态
- L0: identity-kernel.json ✅
- L1: behavioral-patterns.json + meta-rules.json ✅
- L2: Alpha/Beta 分支 ✅ (在主项目中)
- L3: daily/ 目录 ✅
- 待完善: 层间反馈机制
