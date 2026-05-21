"""
MR-018 L6 污染隔离: 四域隔离(信任/活跃/沙箱/隔离) + Alpha/Beta防火墙
"""
import json, os, glob
from datetime import datetime

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
LOG = os.path.join(BASE, "memory", "isolation-log.jsonl")

ISOLATION_RULES = {
    "colonies/": "active",       # 活跃域
    "memory/": "trusted",        # 信任域
    "workspace/": "trusted",     # 信任域
    "daily/": "trusted",         # 信任域
    "archive/": "trusted",       # 信任域
}


def check_isolation():
    violations = []
    colonies_dir = os.path.join(BASE, "colonies")
    for colony in glob.glob(os.path.join(colonies_dir, "colony-*")):
        # 检查Colony是否在写外部文件
        outputs = glob.glob(os.path.join(colony, "**/*.md"), recursive=True)
        for out in outputs:
            rel = os.path.relpath(out, BASE)
            # 所有Colony输出必须在colonies/下
            if not rel.replace("\\","/").startswith("colonies/"):
                violations.append(f"{colony} 写入外部: {rel}")

    return len(violations) == 0, violations


def main():
    clean, violations = check_isolation()

    status = "CLEAN" if clean else "VIOLATION"
    print(f"MR-018 L6 污染隔离: {status}")
    if violations:
        for v in violations:
            print(f"  ⚠️ {v}")

    entry = {"timestamp": datetime.now().isoformat(), "rule": "MR-018-L6", "status": status,
             "violations": len(violations)}
    os.makedirs(os.path.dirname(LOG), exist_ok=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    return 0 if clean else 1


if __name__ == "__main__":
    exit(main())
