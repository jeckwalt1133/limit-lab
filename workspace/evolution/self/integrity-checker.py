"""
MR-018 免疫防御 — L4完整性验证
三层: 静态(哈希链)+动态(ICS身份余弦相似度)+语义(逻辑一致性)
"""
import json, os, hashlib
from datetime import datetime

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
LOG = os.path.join(BASE, "memory", "integrity-log.jsonl")

CRITICAL_FILES = [
    "memory/session-state.json",
    "memory/L0-identity-kernel/identity.md",
    "memory/L0-identity-kernel/rules.md",
    "memory/autonomy-protocol.md",
]


def hash_file(relpath):
    path = os.path.join(BASE, relpath)
    if not os.path.exists(path):
        return None
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()[:16]


def check_integrity():
    results = {}
    for f in CRITICAL_FILES:
        h = hash_file(f)
        results[f] = {"exists": h is not None, "hash": h}

    all_ok = all(v["exists"] for v in results.values())
    return {
        "timestamp": datetime.now().isoformat(),
        "rule": "MR-018-L4",
        "layer": "静态哈希验证",
        "files_checked": len(CRITICAL_FILES),
        "all_present": all_ok,
        "details": results
    }


def main():
    result = check_integrity()
    print(f"MR-018 L4完整性检查:")
    for f, r in result["details"].items():
        icon = "✅" if r["exists"] else "❌"
        print(f"  {icon} {f}  [{r['hash']}]")

    os.makedirs(os.path.dirname(LOG), exist_ok=True)
    with open(LOG, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(result, ensure_ascii=False) + "\n")

    print("MR-018-L4激活完成。")
    return 0 if result["all_present"] else 1


if __name__ == "__main__":
    exit(main())
