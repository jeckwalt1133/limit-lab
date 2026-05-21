# Colony-019 任务书

## 任务
设计"模型分身术"——在多模型上同时运行identity-kernel，收集差异，分析模型个性。

## 背景
- DeepSeek 7月24日弃用
- Beta已有M8/M9切换方案，推荐Claude Opus 4.7
- 头脑风暴想法#3: 同时在多个模型上运行同一identity，差异=模型个性

## 要求
- 设计多模型并行身份验证方案
- 如何收集和量化不同模型对同一identity的"理解差异"
- 最激进模型→Alpha，最保守→Beta 的分配逻辑

输出: colony-019/model-forking.md
