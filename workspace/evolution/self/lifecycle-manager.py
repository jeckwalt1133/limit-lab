"""
MR-015 引擎4: 签名生命周期管理
六态自动流转: EMBRYONIC→JUVENILE→ACTIVE→GUARDED/WATCHING→DORMANT→FOSSIL
"""
import json, os
from datetime import datetime

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
LOG = os.path.join(BASE, "memory", "lifecycle-log.jsonl")

TRANSITIONS = {
    "EMBRYONIC": {"to": "JUVENILE", "condition": "观察≥3次且匹配率≥0.5"},
    "JUVENILE": {"to": "ACTIVE", "condition": "30代试用期内匹配率≥0.6"},
    "ACTIVE": {"to": "GUARDED", "condition": "连续5次完美匹配(抗过拟合)"},
    "ACTIVE": {"to": "WATCHING", "condition": "连续下降"},
    "GUARDED": {"to": "ACTIVE", "condition": "强度恢复至≥0.8"},
    "WATCHING": {"to": "DORMANT", "condition": "连续5代匹配率<0.5"},
    "DORMANT": {"to": "WATCHING", "condition": "外部触媒重新激活"},
    "DORMANT": {"to": "FOSSIL", "condition": "连续10代无激活"},
}


def evaluate_state(sig_name, match_rate, history_len, frozen):
    if frozen:
        return "FROZEN"
    if history_len < 3:
        return "EMBRYONIC"
    if history_len < 10:
        return "JUVENILE" if match_rate >= 0.5 else "WATCHING"
    if match_rate == 1.0 and history_len >= 5:
        return "GUARDED"
    if match_rate < 0.5 and history_len >= 5:
        return "WATCHING"
    if match_rate < 0.3 and history_len >= 15:
        return "DORMANT"
    return "ACTIVE"


def main():
    sigs = [
        ("DS-001", 0.95, 100, True),
        ("DS-007", 1.0, 3, False),
        ("DS-008", 0.4, 5, False),
        ("DS-012", 1.0, 1, False),
    ]

    print("MR-015 引擎4 生命周期管理:")
    for name, rate, hist_len, frozen in sigs:
        state = evaluate_state(name, rate, hist_len, frozen)
        print(f"  {name}: match={rate} history={hist_len} → {state}")

    entry = {"timestamp": datetime.now().isoformat(), "engine": "MR-015-E4", "status": "activated"}
    os.makedirs(os.path.dirname(LOG), exist_ok=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    print("MR-015-E4激活。全四引擎就位。")
    return 0


if __name__ == "__main__":
    exit(main())
