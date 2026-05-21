"""
MR-012 任务复杂度路由
灵感: Grok 4 Fast + Gemini Adaptive Compute
简单任务快速执行，复杂任务深度推理
"""
import json, os, re
from datetime import datetime

LOG = os.path.join(os.path.dirname(__file__), "..", "..", "..", "memory", "task-router-log.jsonl")


def assess_complexity(task_description):
    """评估任务复杂度: low/medium/high"""
    score = 0
    desc = task_description.lower()

    # 高复杂度信号
    if any(w in desc for w in ["设计", "架构", "进化", "实验", "新", "未知", "跨领域"]):
        score += 2
    if any(w in desc for w in ["哥德尔", "模板定向", "自进化", "防御", "免疫"]):
        score += 2
    if len(desc) > 50:
        score += 1

    # 低复杂度信号
    if any(w in desc for w in ["检查", "更新", "日志", "状态", "审计", "常规"]):
        score -= 1

    if score <= 0:
        return "low"
    elif score <= 2:
        return "medium"
    else:
        return "high"


def route_task(task):
    """路由任务到对应执行模式"""
    complexity = assess_complexity(task)
    routing = {
        "low": {"mode": "快速执行", "max_steps": 3, "deep_reasoning": False},
        "medium": {"mode": "标准流程", "max_steps": 8, "deep_reasoning": False},
        "high": {"mode": "深度推理", "max_steps": 20, "deep_reasoning": True},
    }
    return complexity, routing[complexity]


def main():
    test_tasks = [
        "更新session-state.json状态文件",
        "读取并检查今天的审计日志是否有异常",
        "设计一个新的跨模型身份验证协议",
        "写今天的日总结",
        "探索如何用哥德尔不完备定理改进进化系统",
    ]

    for t in test_tasks:
        c, r = route_task(t)
        print(f"  [{c.upper()}] {t[:50]}... → {r['mode']}")

    entry = {"timestamp": datetime.now().isoformat(), "rule": "MR-012", "status": "activated"}
    os.makedirs(os.path.dirname(LOG), exist_ok=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    print("\nMR-012激活完成。")
    return 0


if __name__ == "__main__":
    exit(main())
