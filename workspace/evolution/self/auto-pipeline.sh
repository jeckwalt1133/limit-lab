#!/bin/bash
# 极限实验室 自动化管线
# 每次唤醒时运行: 12脚本串行, 错误隔离, 日志记录
set -e
cd "/d/极限实验室"
LOG="memory/pipeline-$(date +%Y%m%d-%H%M%S).log"
exec > >(tee -a "$LOG") 2>&1

echo "=== 自动化管线启动 $(date) ==="

run() { echo "--- $1 ---"; python "$1" && echo "✅ $1" || echo "❌ $1 (非致命)"; }

# 第1段: 健康检查
run workspace/evolution/self/direction-check.py
run workspace/evolution/self/integrity-checker.py

# 第2段: 绩效更新
run workspace/evolution/self/continuous-performance-engine.py
run workspace/evolution/self/lifecycle-manager.py

# 第3段: 检测分析
run workspace/evolution/self/convergence-detector.py
run workspace/evolution/self/debate-upgrade-engine.py
run workspace/evolution/self/branch-distance-calculator.py

# 第4段: 进化度量
run workspace/evolution/self/esv-calculator.py
run workspace/evolution/self/task-router.py

# 第5段: 重组优化
run workspace/evolution/self/bootstrap-reorganizer.py

echo "=== 管线完成 $(date) ==="
