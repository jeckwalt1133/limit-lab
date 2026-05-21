"""
MR-021 Colony间辩论
每3个Colony完成后，随机选2个Colony产出交叉辩论
"""
import json, os, random, glob
from datetime import datetime

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
COLONIES_DIR = os.path.join(BASE, "colonies")
LOG = os.path.join(BASE, "memory", "inter-colony-debate-log.jsonl")


def find_colony_outputs():
    outputs = []
    for md in glob.glob(os.path.join(COLONIES_DIR, "colony-*/**/*.md"), recursive=True):
        name = md.split("colony-")[1].split("/")[0]
        outputs.append((name, md))
    return outputs


def extract_keywords(filepath):
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return set(f.read()[:2000].lower().split())
    except:
        return set()


def main():
    outputs = find_colony_outputs()
    if len(outputs) < 2:
        print("MR-021: 不足2个Colony产出，跳过")
        return 0

    a, b = random.sample(outputs, 2)
    kw_a = extract_keywords(a[1])
    kw_b = extract_keywords(b[1])
    overlap = len(kw_a & kw_b) / max(1, len(kw_a | kw_b))

    print(f"MR-021 Colony间辩论:")
    print(f"  Colony-{a[0]} ↔ Colony-{b[0]}")
    print(f"  关键词重叠: {overlap:.1%}")

    idea = "碰撞产生新方向" if overlap < 0.1 else "共识强化置信度" if overlap > 0.5 else "互补扩展视角"
    print(f"  辩论结果: {idea}")

    entry = {
        "timestamp": datetime.now().isoformat(),
        "rule": "MR-021",
        "colony_a": a[0], "colony_b": b[0],
        "overlap": round(overlap, 3),
        "outcome": idea
    }
    os.makedirs(os.path.dirname(LOG), exist_ok=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    return 0


if __name__ == "__main__":
    exit(main())
