# JiuwenSwarm 可吸收模式

## 基本信息
- 发布: 2026-05-18（我们启动前一天）
- 来源: 华为2012实验室+华为云AgentArts
- 开源: Apache 2.0
- 论文: arXiv 2605.10052v2

## 四个可直接吸收的模式

### 1. Swarm Skills 封装格式 → 改造我们的实验/规则
现有: 我们的实验和规则是自由格式的.md和.json
吸收: 五组件结构
- SKILL.md (入口)
- roles/ (角色定义)
- workflow.md (任务依赖图)
- bind.md (执行边界)
- evolutions.json (演进记录)

→ 让每个实验设计都用这个格式，自动与JiuwenSwarm生态兼容

### 2. TeamMonitor 12事件 → 改造Colony生命周期
现有: Colony只有启动/完成两个状态
吸收:
- MEMBER_SPAWNED/SHUTDOWN → Colony生命周期
- TASK_CREATED/CLAIMED/COMPLETED → 任务追踪
- MESSAGE_P2P/BROADCAST → Colony间通信（未来）

### 3. Team Workspace 共享区 → Colony间协作
现有: 每个Colony独立目录，互不知对方存在
吸收: shared/ 子目录，文件级锁

### 4. HOTS/HITS → 富贵交互模式
现有: 富贵全权指挥，但没有正式干预接口
吸收:
- HOTS: 监控仪表板（从session-state.json读取）
- HITS: 快速介入指令（随时调整方向）

## 我们独有的（他们做不到的）
- 94代行为签名冻结+跨会话持久性
- 哥德尔跳维度扩展
- 六层免疫防御
- 21条跨领域灵感映射体系
- 模型无关身份核(identity-kernel)
