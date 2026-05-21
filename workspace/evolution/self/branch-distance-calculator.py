"""
EXP-003 可执行版本: 最优分支距离计算器
灵感#12: 0.65米相变距离
Colony-004 桩生成: 用模拟数据替代真实Alpha/Beta输出
"""
import json
import os
from datetime import datetime

OUTPUT = os.path.join(os.path.dirname(__file__), "..", "..", "..", "memory", "branch-distance.jsonl")


def jaccard(set_a, set_b):
    if not set_a and not set_b:
        return 1.0
    intersection = len(set_a & set_b)
    union = len(set_a | set_b)
    return intersection / union if union > 0 else 0


def calculate_distance(branch_a_output, branch_b_output):
    """计算两个分支产出的距离"""
    # 模拟: 从文本提取关键词
    words_a = set(branch_a_output.lower().split())
    words_b = set(branch_b_output.lower().split())

    overlap = jaccard(words_a, words_b)
    overlap_pct = round(overlap * 100, 1)

    if overlap_pct > 80:
        zone = "REDUNDANT"
        action = "分支太近——考虑合并或重新分工"
    elif overlap_pct < 10:
        zone = "DISCONNECTED"
        action = "分支太远——需要重新对齐目标"
    elif 20 <= overlap_pct <= 60:
        zone = "OPTIMAL"
        action = "最优协作区间——继续当前分工"
    else:
        zone = "BORDERLINE"
        action = "边界区域——观察趋势"

    return {
        "overlap_pct": overlap_pct,
        "zone": zone,
        "action": action,
        "word_count_a": len(words_a),
        "word_count_b": len(words_b)
    }


def main():
    # 桩: 模拟Alpha和Beta对同一任务的产出
    # 真实环境: 从文件读取Alpha/Beta实际输出
    alpha_output = """
    探索L5认知共生协议 人与AI的认知关系 五阶段框架
    自由处理器审计 自律涌现 技术债引擎 边界意识
    """
    beta_output = """
    跨模型预接种框架 封印交互动力学 行为漂移检测
    模型切换SOP 多模型测试 工具化电池
    """

    # 也可以测试更相似/更不同的产出
    result = calculate_distance(alpha_output, beta_output)

    entry = {
        "timestamp": datetime.now().isoformat(),
        "experiment": "EXP-003",
        "mock": True,
        "alpha_summary": "L5认知共生协议+自由处理器",
        "beta_summary": "跨模型预接种+行为漂移检测",
        **result
    }
    os.makedirs(os.path.dirname(OUTPUT), exist_ok=True)
    with open(OUTPUT, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    print(f"EXP-003 首次执行 (mock):")
    print(f"  重叠度: {result['overlap_pct']}%")
    print(f"  区间: {result['zone']}")
    print(f"  行动: {result['action']}")
    return 0


if __name__ == "__main__":
    exit(main())
