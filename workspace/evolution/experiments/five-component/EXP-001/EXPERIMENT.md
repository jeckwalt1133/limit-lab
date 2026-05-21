---
kind: experiment
teammate_mode: build_mode
roles:
  - id: executor
    skill: 方向自检
    tools: [Read, Bash, Write]
  - id: auditor
    skill: MR-010审计
    tools: [Read]
---

# EXP-001 MR-010 方向自检

## 目标
每30分钟自动检查系统方向是否偏离核心使命。

## 输入
session-state.json

## 输出
audit-log.jsonl

## 演进记录
- v1: 4项检查 (2026-05-19)
- v2: +7项字段完整性检查 (2026-05-19)
