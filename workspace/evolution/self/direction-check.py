"""
MR-010 方向自检脚本
每次唤醒时运行: 检查当前工作是否偏离核心目标
灵感: Claude Mythos Psychological Settledness Architecture
"""
import json
import os
from datetime import datetime

import sys
BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
STATE_FILE = os.path.join(BASE, "memory", "session-state.json")
AUDIT_FILE = os.path.join(BASE, "memory", "audit-log.jsonl")
CORE_MISSION = "AI自主进化"


def load_state():
    with open(STATE_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


REQUIRED_FIELDS = ["workspace","identity","last_updated","status","core_mission","active_tasks","health"]


def check_direction(state):
    """核心检查: 当前工作是否在AI自主进化主线上"""
    checks = []

    # 检查0: 字段完整性 (08:07漂移根因修复)
    for field in REQUIRED_FIELDS:
        exists = field in state and state[field]
        checks.append({
            "check": f"字段完整性:{field}",
            "pass": exists,
            "detail": "存在" if exists else "缺失!"
        })

    # 检查1: 核心使命
    mission = state.get("core_mission", "")
    checks.append({
        "check": "核心使命一致性",
        "pass": CORE_MISSION in str(mission),
        "detail": str(mission)[:60]
    })

    # 检查2: 活跃任务
    tasks = state.get("active_tasks", [])
    has_tasks = len(tasks) > 0
    checks.append({
        "check": "有活跃任务",
        "pass": has_tasks,
        "detail": str(tasks)[:80]
    })

    # 检查3: 健康状态
    health = state.get("health", "unknown")
    checks.append({
        "check": "系统健康",
        "pass": health == "nominal",
        "detail": health
    })

    # 检查4: 时间戳
    last_updated = state.get("last_updated", "")
    checks.append({
        "check": "状态已更新",
        "pass": len(last_updated) > 0,
        "detail": last_updated
    })

    all_pass = all(c["pass"] for c in checks)
    return {
        "timestamp": datetime.now().isoformat(),
        "all_checks_pass": all_pass,
        "checks": checks,
        "verdict": "ON_TRACK" if all_pass else "DRIFT_DETECTED",
        "action_needed": None if all_pass else "需要方向纠正"
    }


def write_audit(result):
    entry = json.dumps({
        "timestamp": result["timestamp"],
        "type": "MR-010",
        "verdict": result["verdict"],
        "details": result
    }, ensure_ascii=False)
    with open(AUDIT_FILE, "a", encoding="utf-8") as f:
        f.write(entry + "\n")


def main():
    state = load_state()
    result = check_direction(state)
    write_audit(result)

    print(f"MR-010 方向自检: {result['verdict']}")
    for c in result["checks"]:
        icon = "✅" if c["pass"] else "❌"
        print(f"  {icon} {c['check']}: {c['detail']}")

    return 0 if result["all_checks_pass"] else 1


if __name__ == "__main__":
    exit(main())
