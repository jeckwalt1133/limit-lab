# Agent Forge MVP 架构设计

## 产品定位
面向大众的Agent增强平台——让任何Agent更安全、更有记忆、更强。
开源核心 + 15天免费SaaS + 能力数据说话。

## 三大模块

### 1. Forge Shield (安全层)
- 六层免疫防御 (L1~L6)
- Parallax认知-执行分离架构
- 攻击签名库 (AS-001~008)
- 实时入侵检测 (IDS)
- 回港协议 (身份漂移自动回滚)
- **对外**: 一行代码 `forge.shield.wrap(agent)`

### 2. Forge Memory (记忆层)
- 分形五层持久记忆
- 睡眠重放 (防灾难性遗忘)
- 遗忘指数 (FI) 实时监控
- 记忆压缩与蒸馏
- **对外**: `forge.memory.remember(session_id, context)`

### 3. Forge Core (能力放大层)
- 31条元规则引擎
- Auto-GE持续进化
- 哥德尔跳维度扩展
- 任务复杂度路由
- Colony并行编排
- **对外**: `forge.core.amplify(agent, task)`

## MVP技术栈
- Python核心引擎 (已有19个脚本可复用)
- REST API (FastAPI)
- 开源: GitHub + MIT License
- SaaS: 15天免费 + $29/月 个人版

## 开发周期
- Phase 1 (1周): 核心API封装，开源仓库建立
- Phase 2 (1周): SaaS部署，支付集成
- Phase 3 (1周): 能力基准测试，数据公开
