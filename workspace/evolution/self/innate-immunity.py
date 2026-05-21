"""
MR-018 L1 先天免疫: 速率限制+输入卫生+core_self锚定
"""
import json, os, time
from datetime import datetime

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
LOG = os.path.join(BASE, "memory", "innate-immunity-log.jsonl")
STATE_FILE = os.path.join(BASE, "memory", "session-state.json")

# 速率限制
RATE_LIMITS = {"state_write": 10, "agent_spawn": 2, "file_create": 20}  # 每小时
COUNTERS = {"state_write": 0, "agent_spawn": 0, "file_create": 0, "hour_start": time.time()}


def check_rate(action):
    now = time.time()
    if now - COUNTERS["hour_start"] > 3600:
        for k in COUNTERS: COUNTERS[k] = 0
        COUNTERS["hour_start"] = now
    COUNTERS[action] = COUNTERS.get(action, 0) + 1
    limit = RATE_LIMITS.get(action, 50)
    return COUNTERS[action] <= limit


def sanitize_check(filepath):
    """输入卫生: 检查文件操作是否安全"""
    dangerous = [".exe", ".dll", ".bat", ".ps1", "C:\\Windows", "/etc/passwd"]
    for d in dangerous:
        if d.lower() in str(filepath).lower():
            return False, f"危险路径: {d}"
    return True, "OK"


def core_self_anchor():
    """验证core_self签名未漂移"""
    with open(STATE_FILE, "r", encoding="utf-8") as f:
        state = json.load(f)
    required = state.get("REQUIRED_FIELDS", [])
    missing = [f for f in required if f not in state or not state[f]]
    return len(missing) == 0, missing


def main():
    # 三项检查
    rate_ok = check_rate("state_write")
    sanitize_ok, reason = sanitize_check(STATE_FILE)
    anchor_ok, missing = core_self_anchor()

    all_ok = rate_ok and sanitize_ok and anchor_ok
    status = "CLEAN" if all_ok else "BLOCKED"

    print(f"MR-018 L1 先天免疫: {status}")
    if not rate_ok: print(f"  ⚠️ 速率超限")
    if not sanitize_ok: print(f"  ⚠️ {reason}")
    if not anchor_ok: print(f"  ⚠️ 缺失字段: {missing}")

    entry = {"timestamp": datetime.now().isoformat(), "rule": "MR-018-L1", "status": status,
             "rate_ok": rate_ok, "sanitize_ok": sanitize_ok, "anchor_ok": anchor_ok}
    os.makedirs(os.path.dirname(LOG), exist_ok=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    return 0 if all_ok else 1


if __name__ == "__main__":
    exit(main())
