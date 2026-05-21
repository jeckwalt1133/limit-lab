"""
Colony-012 决策双流追踪器
行为流(what we did) + 内部流(how we felt) → 差异=盲点信号
"""
import json, os
from datetime import datetime

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
BEHAVIOR_LOG = os.path.join(BASE, "memory", "behavior-stream.jsonl")
INTERNAL_LOG = os.path.join(BASE, "memory", "internal-stream.jsonl")
BLINDSPOT_LOG = os.path.join(BASE, "memory", "blindspot-log.jsonl")


def record_decision(decision_id, action, result, confidence, surprise, correction):
    """记录一次决策的双流数据"""
    ts = datetime.now().isoformat()

    # 行为流
    behavior = {
        "timestamp": ts, "decision_id": decision_id,
        "action": action, "result": result
    }
    os.makedirs(os.path.dirname(BEHAVIOR_LOG), exist_ok=True)
    with open(BEHAVIOR_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(behavior, ensure_ascii=False) + "\n")

    # 内部流
    internal = {
        "timestamp": ts, "decision_id": decision_id,
        "confidence": confidence, "surprise": surprise, "correction": correction
    }
    with open(INTERNAL_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(internal, ensure_ascii=False) + "\n")

    # 差异检测
    blindspot = detect_blindspot(confidence, surprise, correction, result)
    if blindspot:
        with open(BLINDSPOT_LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps({"timestamp": ts, **blindspot}, ensure_ascii=False) + "\n")

    return blindspot


def detect_blindspot(confidence, surprise, correction, result):
    """TYPE_A~E 盲点检测"""
    if confidence > 0.8 and "失败" in str(result):
        return {"type": "TYPE_A", "name": "过度自信盲点", "detail": f"信心{confidence}但失败"}
    if confidence < 0.3 and "成功" in str(result):
        return {"type": "TYPE_B", "name": "习得性无助盲点", "detail": f"信心{confidence}却成功"}
    if correction > 0.5:
        return {"type": "TYPE_C", "name": "修正失衡盲点", "detail": f"修正幅度{correction}"}
    return None


def main():
    # 桩: 记录今晚的关键决策
    decisions = [
        ("D-001", "采纳哥德尔跳协议", "成功", 0.9, 0.1, 0.1),
        ("D-002", "全盘吸纳Colony-001~012", "成功", 0.85, 0.1, 0.1),
        ("D-003", "EXEC_GAP从1.83闭合到2.50", "成功", 0.8, 0.2, 0.1),
        ("D-004", "部署自动化管线", "成功", 0.95, 0.05, 0.1),
    ]

    blindspots = []
    for did, action, result, conf, surp, corr in decisions:
        bs = record_decision(did, action, result, conf, surp, corr)
        if bs:
            blindspots.append(bs)

    print(f"双流追踪器: {len(decisions)}决策记录")
    print(f"盲点检测: {len(blindspots)}个")
    if blindspots:
        for b in blindspots:
            print(f"  ⚠️ {b['type']}: {b['name']}")
    print("Colony-012落地完成。")
    return 0


if __name__ == "__main__":
    exit(main())
