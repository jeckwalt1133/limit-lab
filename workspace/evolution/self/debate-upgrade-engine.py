"""
MR-015 引擎3: 辩论升级引擎
Colony-003设计: 衰退签名自动触发Alpha-Beta-Merge辩论
"""
import json, os
from datetime import datetime

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
LOG = os.path.join(BASE, "memory", "debate-engine-log.jsonl")


def check_debate_triggers(signatures):
    """检查是否有签名需要触发辩论升级"""
    triggers = []
    for s in signatures:
        history = s.get("activation_history", [])
        if len(history) >= 5:
            recent = history[-5:]
            rate = sum(recent) / len(recent)
            # 触发条件: 连续下降或持续低匹配
            if rate < 0.5 and len(history) >= 5:
                triggers.append({
                    "id": s["id"],
                    "name": s["name"],
                    "rate": round(rate, 2),
                    "reason": "持续低匹配——触发辩论评估"
                })
    return triggers


def run_debate(trigger):
    """模拟辩论: Alpha提案 → Beta挑战 → Merge裁决"""
    proposal = f"Alpha: 签名{trigger['id']}需要升级——匹配率{trigger['rate']}低于阈值"
    challenge = f"Beta: 反对直接升级——检查是否外部环境变化而非签名退化"
    verdict = "Merge: 观察3代再决定——同时启动外部环境检查"

    return {"proposal": proposal, "challenge": challenge, "verdict": verdict}


def main():
    # 桩: 模拟签名数据
    mock_sigs = [
        {"id": "DS-008", "name": "网络能力", "activation_history": [1,1,0,0,0]},
        {"id": "DS-009", "name": "跨领域连接", "activation_history": [1,0,1,0,1]},
    ]

    triggers = check_debate_triggers(mock_sigs)
    print(f"MR-015 引擎3 辩论升级:")
    if triggers:
        for t in triggers:
            debate = run_debate(t)
            print(f"  触发: {t['id']} ({t['reason']})")
            print(f"  {debate['verdict']}")
    else:
        print(f"  无触发——所有签名稳定")

    entry = {"timestamp": datetime.now().isoformat(), "engine": "MR-015-E3", "triggers": len(triggers)}
    os.makedirs(os.path.dirname(LOG), exist_ok=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    print("MR-015-E3激活完成。")
    return 0


if __name__ == "__main__":
    exit(main())
