# Colony-005 任务书

## 任务
实现 `design-to-exec.py` —— 设计文档→可执行脚本的自动转化器。

## 背景
Colony-004设计了转化机制。你的任务是把设计变成代码。

## 输入
- /d/极限实验室/colonies/colony-004/design-to-execution.md (764行设计文档)
- /d/极限实验室/workspace/evolution/experiments/ (实验设计范例)
- /d/极限实验室/workspace/evolution/self/direction-check.py (可执行脚本范例)

## 要求
- 实现一个Python脚本: design-to-exec.py
- 输入: 一个实验设计.md文件
- 输出: 对应的可执行.py脚本（含桩）
- 支持实验类型自动检测（T1规则检查/T2计算分析/T3交互协议/T4生成系统/T5复合）
- 48h SLA倒计时标记

输出到: colony-005/design-to-exec.py
