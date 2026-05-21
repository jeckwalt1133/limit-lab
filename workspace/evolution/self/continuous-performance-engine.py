"""
MR-015 引擎1: 连续绩效引擎
每次会话结束运行——签名绩效自动更新+状态迁移建议
"""
import json
import os
from datetime import datetime

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
PERF_LOG = os.path.join(BASE, "memory", "signature-performance.jsonl")
STATE_FILE = os.path.join(BASE, "memory", "session-state.json")


def load_signatures():
    """加载当前活跃签名（从主项目+本区扩展）"""
    sigs = []
    # 主项目签名（只读引用）
    bp_file = "D:/Claude-觉醒/eternal/behavioral-patterns.json"
    if os.path.exists(bp_file):
        with open(bp_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            for s in data.get("decision_signatures", {}).get("signatures", []):
                sigs.append({
                    "id": s["id"],
                    "name": s["name"],
                    "strength": s.get("strength", 0.5),
                    "frozen": s.get("frozen", False),
                    "activation_history": s.get("activation_history", []),
                    "source": "mainbody"
                })
    return sigs


def evaluate_signature(sig):
    """单条签名绩效评估"""
    history = sig.get("activation_history", [])
    if not history:
        return {"match_rate": None, "status": "no_data"}

    match_rate = sum(history) / len(history)
    recent = history[-5:] if len(history) >= 5 else history
    recent_rate = sum(recent) / len(recent) if recent else 0

    # 六态判断
    if sig.get("frozen"):
        state = "FROZEN"
    elif len(history) < 3:
        state = "EMBRYONIC"
    elif len(history) < 10:
        state = "JUVENILE" if match_rate >= 0.5 else "WATCHING"
    elif recent_rate == 1.0 and len(recent) >= 5:
        state = "GUARDED"  # 抗过拟合触发
    elif recent_rate < 0.5 and len(recent) >= 5:
        state = "WATCHING"
    elif match_rate < 0.3 and len(history) >= 15:
        state = "DORMANT"
    else:
        state = "ACTIVE"

    return {
        "id": sig["id"],
        "match_rate": round(match_rate, 3),
        "recent_rate": round(recent_rate, 3),
        "history_len": len(history),
        "state": state,
        "strength": sig.get("strength", 0.5)
    }


def main():
    sigs = load_signatures()
    results = [evaluate_signature(s) for s in sigs]

    # 写绩效日志
    entry = {
        "timestamp": datetime.now().isoformat(),
        "engine": "continuous-performance-v1",
        "total_signatures": len(sigs),
        "active": sum(1 for r in results if r["state"] == "ACTIVE"),
        "guarded": sum(1 for r in results if r["state"] == "GUARDED"),
        "watching": sum(1 for r in results if r["state"] == "WATCHING"),
        "details": results
    }
    with open(PERF_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    print(f"引擎1: {len(sigs)}条签名评估完成")
    for r in results:
        if r["state"] != "ACTIVE" and r["state"] != "FROZEN":
            print(f"  ⚠️ {r['id']} → {r['state']} (match={r['match_rate']})")

    return 0


if __name__ == "__main__":
    exit(main())
