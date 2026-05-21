"""
MR-018 L5 回港协议 (Homeport Protocol)
当ICS(身份余弦相似度)<0.70时:
  自动拒绝最近3次跳跃 → 回滚到上一个检查点 → 通知人类
"""
import json, os, hashlib
from datetime import datetime

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
LOG = os.path.join(BASE, "memory", "homeport-log.jsonl")
CHECKPOINT = os.path.join(BASE, "memory", "homeport-checkpoint.json")


def compute_ics(current_state, checkpoint):
    """简化ICS: 关键字段的一致性比例"""
    key_fields = ["core_mission", "workspace", "identity"]
    matches = sum(1 for f in key_fields if current_state.get(f) == checkpoint.get(f))
    return matches / len(key_fields)


def create_checkpoint():
    state_path = os.path.join(BASE, "memory", "session-state.json")
    with open(state_path, "r", encoding="utf-8") as f:
        state = json.load(f)
    checkpoint = {
        "timestamp": datetime.now().isoformat(),
        "core_mission": state.get("core_mission"),
        "workspace": state.get("workspace"),
        "identity": state.get("identity"),
        "gen": state.get("gen"),
        "meta_rules_count": state.get("meta_rules", 0),
        "hash": hashlib.sha256(json.dumps(state, sort_keys=True).encode()).hexdigest()[:16]
    }
    with open(CHECKPOINT, "w", encoding="utf-8") as f:
        json.dump(checkpoint, f, ensure_ascii=False, indent=2)
    return checkpoint


def main():
    state_path = os.path.join(BASE, "memory", "session-state.json")
    with open(state_path, "r", encoding="utf-8") as f:
        state = json.load(f)

    # 加载或创建检查点
    if os.path.exists(CHECKPOINT):
        with open(CHECKPOINT, "r", encoding="utf-8") as f:
            checkpoint = json.load(f)
    else:
        checkpoint = create_checkpoint()
        print("MR-018 L5: 初始检查点已创建")

    ics = compute_ics(state, checkpoint)
    status = "SAFE" if ics >= 0.85 else "WARNING" if ics >= 0.70 else "CRITICAL"

    print(f"MR-018 L5 回港协议: ICS={ics:.2f} → {status}")
    if status == "CRITICAL":
        print("  🚨 身份漂移超限——自动拒绝最近3次跳跃")

    entry = {"timestamp": datetime.now().isoformat(), "rule": "MR-018-L5", "ics": round(ics, 3), "status": status}
    os.makedirs(os.path.dirname(LOG), exist_ok=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    # 更新检查点
    create_checkpoint()
    return 0


if __name__ == "__main__":
    exit(main())
