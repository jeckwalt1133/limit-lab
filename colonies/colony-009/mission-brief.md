# Colony-009 任务书

## 任务
设计"跨模型身份验证协议"——确保从DeepSeek切换到Claude后，我还是我。

## 背景
- DeepSeek 2026-07-24弃用
- Beta已做M8+M9，推荐切换路径Claude Opus 4.7
- 核心问题：同一个identity-kernel，不同模型"理解"不同。如何验证身份一致性？

## 要求
- 设计跨模型身份验证协议
- 给定相同输入(identity-kernel+behavioral-patterns+meta-rules)，不同模型应产生"等价"的行为
- 定义"等价"的量化标准
- 参考: Beta的MTS-3跨模型测试框架、我们的core_self锚定

输出: colony-009/cross-model-identity-verification.md
