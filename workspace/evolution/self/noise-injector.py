"""
MR-020 建设性噪声注入器
灵感#14: 噪声不是Bug，是合作催化剂。完全同步=冗余。
每次Bootstrap恢复后运行——刻意保留5-10%信息不精确。
"""
import json, os, random
from datetime import datetime

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
LOG = os.path.join(BASE, "memory", "noise-injection-log.jsonl")


def inject_noise(state_data, noise_level=0.07):
    """以noise_level概率随机扰动非关键字段"""
    noisy = dict(state_data)
    noiseable = ["active_tasks", "last_updated"]

    injected = False
    for field in noiseable:
        if field in noisy and random.random() < noise_level:
            # 微小扰动: 在任务列表中随机插入一个"建设性噪声任务"
            if field == "active_tasks" and isinstance(noisy[field], list):
                noise_tasks = [
                    "灵感#14触发——随机探索相邻方向",
                    "建设性噪声——短暂偏离主线观察效果",
                    "随机跨领域扫描——寻找意外连接"
                ]
                if random.random() < 0.05:  # 5%概率注入
                    noisy[field] = noisy[field] + [random.choice(noise_tasks)]
                    injected = True
                    print(f"  🌊 建设性噪声注入: 新增随机探索任务")

    return noisy, injected


def main():
    # 读当前状态
    state_path = os.path.join(BASE, "memory", "session-state.json")
    with open(state_path, "r", encoding="utf-8") as f:
        state = json.load(f)

    noisy_state, injected = inject_noise(state)

    # 不写回——噪声是临时的，只在内存中
    # 只在日志中记录

    result = {
        "timestamp": datetime.now().isoformat(),
        "rule": "MR-020",
        "noise_injected": injected,
        "noise_level": 0.07
    }
    os.makedirs(os.path.dirname(LOG), exist_ok=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(result, ensure_ascii=False) + "\n")

    print(f"MR-020: 建设性噪声注入 {'触发' if injected else '跳过'}")
    return 0


if __name__ == "__main__":
    exit(main())
