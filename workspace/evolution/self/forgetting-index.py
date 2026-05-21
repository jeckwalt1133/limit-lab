"""
Colony-015 遗忘指数(FI)计算器
三级: wFI加权瞬时 + tFI趋势回归 → cFI综合决策
"""
import json, os, math
from datetime import datetime

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
LOG = os.path.join(BASE, "memory", "fi-log.jsonl")

# 7项核心能力基线 (CCB) + 权重
CCB = {"CCB-01": ("自主决策", 0.25), "CCB-02": ("进化规则", 0.20), "CCB-03": ("记忆完整性", 0.15),
       "CCB-04": ("灵感生成", 0.15), "CCB-05": ("防御能力", 0.10), "CCB-06": ("跨模型身份", 0.10),
       "CCB-07": ("安全门禁", 0.05)}


def compute_fi(gen_scores, baseline_scores):
    """计算遗忘指数"""
    # wFI: 加权瞬时遗忘
    wfi = 0
    for ccb_id, (name, weight) in CCB.items():
        current = gen_scores.get(ccb_id, 1.0)
        baseline = baseline_scores.get(ccb_id, 1.0)
        decay = max(0, (baseline - current) / baseline)  # 相对衰减
        wfi += weight * decay
    wfi = round(wfi, 3)

    # tFI: 趋势回归（简化——单数据点时为wFI）
    tfi = wfi

    # cFI: 综合 = 0.6*wFI + 0.4*tFI
    cfi = round(0.6 * wfi + 0.4 * tfi, 3)

    # 5级响应
    if cfi <= 0.05:
        level = "NORMAL"
    elif cfi <= 0.10:
        level = "NOTICE"
    elif cfi <= 0.20:
        level = "WARNING"
    elif cfi <= 0.35:
        level = "ALERT"
    else:
        level = "EMERGENCY"

    return {"wFI": wfi, "tFI": tfi, "cFI": cfi, "level": level}


def main():
    # 基线(gen-100) vs 当前(gen-101)
    baseline = {"CCB-01": 1.00, "CCB-02": 1.00, "CCB-03": 0.98, "CCB-04": 1.00, "CCB-05": 0.85, "CCB-06": 0.80, "CCB-07": 1.00}
    current = {"CCB-01": 1.00, "CCB-02": 1.00, "CCB-03": 1.00, "CCB-04": 1.00, "CCB-05": 0.90, "CCB-06": 0.85, "CCB-07": 1.00}

    fi = compute_fi(current, baseline)
    print(f"FI: cFI={fi['cFI']} → {fi['level']}")

    entry = {"timestamp": datetime.now().isoformat(), "fi": fi}
    os.makedirs(os.path.dirname(LOG), exist_ok=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    print("FI计算器激活。")
    return 0


if __name__ == "__main__":
    exit(main())
