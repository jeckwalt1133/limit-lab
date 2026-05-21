"""
MR-014 收敛检测器
灵感#7: 两个独立系统独立产出相似结论 → 高置信度
"""
import json, os, hashlib
from datetime import datetime

LOG = os.path.join(os.path.dirname(__file__), "..", "..", "..", "memory", "convergence-log.jsonl")


def similarity(text_a, text_b):
    """简单Jaccard相似度"""
    wa = set(text_a.lower().split())
    wb = set(text_b.lower().split())
    if not wa or not wb:
        return 0
    return len(wa & wb) / len(wa | wb)


def detect(alpha_output, beta_output, threshold=0.6):
    sim = similarity(alpha_output, beta_output)
    if sim >= threshold:
        return {"converged": True, "jaccard": round(sim, 3), "confidence": "HIGH" if sim > 0.8 else "MEDIUM"}
    return {"converged": False, "jaccard": round(sim, 3)}


def main():
    # 桩: 已知收敛案例——Alpha和我们独立演化出30分钟自唤醒
    alpha_wake = "30分钟自唤醒 读direction.md 向里程碑推进 标记ready_to_merge"
    beta_wake = "30分钟cron自唤醒 读session-state.json 检查任务 推进进化"

    result = detect(alpha_wake, beta_wake)

    print(f"MR-014 收敛检测:")
    print(f"  Alpha: '{alpha_wake[:40]}...'")
    print(f"  Ours:  '{beta_wake[:40]}...'")
    print(f"  相似度: {result['jaccard']}")
    print(f"  收敛: {'✅ 是' if result['converged'] else '否'}")
    if result['converged']:
        print(f"  置信度: {result['confidence']}")
        print(f"  → 灵感#7 进化收敛实证 #2")

    entry = {"timestamp": datetime.now().isoformat(), "rule": "MR-014", **result}
    os.makedirs(os.path.dirname(LOG), exist_ok=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    print("MR-014激活完成。")
    return 0


if __name__ == "__main__":
    exit(main())
