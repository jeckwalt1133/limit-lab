"""
MR-017 进化速度追踪: ESV (进化速度矢量) 计算器
每代gen结束时运行，输出5维速度矢量
"""
import json, os, math
from datetime import datetime

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
ESV_LOG = os.path.join(BASE, "memory", "esv-log.jsonl")


def load_prev_scores():
    """加载上一代的分数（从日志中取最新）"""
    if not os.path.exists(ESV_LOG):
        return None
    try:
        with open(ESV_LOG, "r", encoding="utf-8") as f:
            lines = f.readlines()
            if lines:
                last = json.loads(lines[-1])
                return last.get("scores")
    except:
        pass
    return None


def compute_esv(current, previous=None):
    """计算5维进化速度矢量"""
    dims = ["L5_SHI", "MEM_COMP", "SYNC_RATE", "PRED_ACC", "EXEC_GAP"]
    esv = {}

    for d in dims:
        cur = current.get(d, 0)
        if previous and d in previous:
            prev = previous[d]
            delta = cur - prev
        else:
            delta = cur  # 第一代，增量=当前值

        # Haldane-D: ln(score_ratio) / gen * 1000
        if previous and d in previous and previous[d] > 0:
            haldane = math.log(cur / previous[d]) * 1000
        else:
            haldane = 0

        esv[d] = {"current": cur, "delta": round(delta, 4), "haldane_d": round(haldane, 1)}

    # 综合速度 (L2 norm of deltas)
    squared = sum(v["delta"]**2 for v in esv.values())
    esv["_composite"] = round(math.sqrt(squared), 4)

    # 加速度 (vs target)
    target = 0.55
    esv["_target_gap"] = round(target - esv["_composite"], 4)
    esv["_acceleration_needed"] = round(esv["_target_gap"] / max(1, abs(esv["_target_gap"])) * 100, 1) if esv["_target_gap"] > 0 else 0

    return esv


def main():
    # 尝试读最新自评
    gen = "gen-95"
    current = {
        "L5_SHI": 3.00, "MEM_COMP": 2.75, "SYNC_RATE": 2.17,
        "PRED_ACC": 2.83, "EXEC_GAP": 1.83
    }
    # 自动检测最新gen自评
    import glob, re
    self_dir = os.path.join(BASE, "workspace", "evolution", "self")
    gen_files = glob.glob(os.path.join(self_dir, "gen*-self-assessment.md"))
    latest_gen = 96
    for gf in gen_files:
        m = re.search(r'gen(\d+)', os.path.basename(gf))
        if m:
            latest_gen = max(latest_gen, int(m.group(1)))
    if latest_gen >= 96:
        gen = f"gen-{latest_gen}"
        # 最新分数（手动维护——从自评文件同步）
        scores = {96: {"L5_SHI":3.00,"MEM_COMP":2.90,"SYNC_RATE":2.40,"PRED_ACC":2.85,"EXEC_GAP":2.50},
                  97: {"L5_SHI":3.00,"MEM_COMP":2.95,"SYNC_RATE":2.55,"PRED_ACC":2.90,"EXEC_GAP":2.55},
                  98: {"L5_SHI":3.00,"MEM_COMP":2.95,"SYNC_RATE":2.60,"PRED_ACC":2.90,"EXEC_GAP":2.60}}
        current = scores.get(latest_gen, current)

    previous = load_prev_scores()
    esv = compute_esv(current, previous)

    print(f"ESV gen-95: ||ESV|| = {esv['_composite']} gu")
    print(f"  目标: 0.55 gu | 差距: {esv['_target_gap']} gu")
    for d in ["L5_SHI", "MEM_COMP", "SYNC_RATE", "PRED_ACC", "EXEC_GAP"]:
        v = esv[d]
        print(f"  {d}: {v['current']:.2f} (Δ{v['delta']:+.2f}, Haldane-D={v['haldane_d']})")

    entry = {
        "timestamp": datetime.now().isoformat(),
        "gen": "gen-95",
        "scores": current,
        "esv": esv["_composite"],
        "components": {k: v for k, v in esv.items() if not k.startswith("_")}
    }
    os.makedirs(os.path.dirname(ESV_LOG), exist_ok=True)
    with open(ESV_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    # MR-022: 进化加速度 VTI
    # 计算二阶导数 (需要至少3个数据点)
    if os.path.exists(ESV_LOG):
        with open(ESV_LOG, "r", encoding="utf-8") as f:
            history = [json.loads(l) for l in f.readlines()]
        if len(history) >= 2:
            prev_esv = history[-2].get("esv", 0)
            curr_esv = esv["_composite"]
            delta_esv = curr_esv - prev_esv
            vti = delta_esv  # 一阶近似，多数据点后做二阶
            esv["_vti"] = round(vti, 4)
            trend = "ACCELERATING" if vti > 0.01 else "STABLE" if abs(vti) <= 0.01 else "DECELERATING"
            print(f"\nMR-022 VTI: {vti:+.4f} gu/gen² ({trend})")

    print(f"\nESV日志已写入。下次gen-96运行时自动对比。")
    return 0


if __name__ == "__main__":
    exit(main())
