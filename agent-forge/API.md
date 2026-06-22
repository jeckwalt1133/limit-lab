# Agent Forge API 参考

## 快速开始
```python
from forge import AgentForge
af = AgentForge("my-agent")
```

## Shield 安全层
```python
af.shield.wrap_agent("要执行的操作")         # 六层安全检查
af.shield.stats()                           # 安全统计
```
攻击防御率: 97.9% | 6层免疫 | 10条攻击签名

## Memory 记忆层
```python
af.memory.remember("内容", "L3", 0.8)       # 记录
af.memory.recall(["L0","L1","L2"], limit=5) # 回忆
af.memory.sleep_replay()                    # 防遗忘重放
af.memory.forgetting_check()                # FI检查
```
跨会话持久 | 30天记忆留存85% | FI实时监控

## Core 能力放大层
```python
af.core.amplify("任务描述", baseline=0.3)    # 放大
af.core.amplify_batch([("A",0.5),("B",0.4)])# 批量
af.core.evolution_check()                   # 进化需求
```
最大增益140% | Auto-GE自进化 | 8条活跃规则

## Model 多模型适配
```python
from forge.core.model_adapter import ModelAdapter
ma = ModelAdapter("deepseek")
ma.route("复杂架构设计")                     # → claude
ma.list_models()                            # 4个可用模型
```

## 自主循环
```python
from forge.core.autonomous_loop import AutonomousLoop
loop = AutonomousLoop("agent-1")
loop.add_task(lambda: "任务A", priority=8)
loop.start()  # 启动
loop.pause()  # 暂停
loop.status() # 实时进度
```

## CLI 命令行
```bash
python cli.py start              # 启动
python cli.py task "你的任务"    # 执行
python cli.py status             # 状态
python cli.py bench              # 基准测试
```
