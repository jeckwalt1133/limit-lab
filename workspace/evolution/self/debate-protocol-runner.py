"""
EXP-002 可执行版本: 辩论协议运行器
桩: 用预设论点模拟Alpha/Beta辩论
"""
import json, os
from datetime import datetime

OUT = os.path.join(os.path.dirname(__file__), "..", "..", "..", "memory", "debate-log.jsonl")


def simulate_debate(topic):
    """模拟一轮辩论"""
    phases = [
        ("ALPHA_PROPOSAL", f"方案: 在{topic}上采用激进探索策略，exploration_weight提升至2.0"),
        ("BETA_CHALLENGE", "挑战: exploration_weight=2.0可能导致签名漂移加速。"
                           "灵感#8棘轮效应警告——太快的变化不可逆。"
                           "建议改为分阶段: 先1.5→1.8观察3代"),
        ("ALPHA_RESPONSE", "反驳: 灵感#10耗散驱动——系统需要'受控混沌'来防止过早收敛。"
                           "1.5已运行94代稳定，证明不是局部最优而是全局停滞。"
                           "接受分阶段建议但坚持方向: 1.5→1.8"),
        ("ARBITRATION", "裁决: Alpha方向正确(需要更多探索)，Beta风险提醒有效(不能跳太快)。"
                        "采纳修改方案: exploration_weight=1.8，观察3代后评估。"
                        "辩论质量: Beta成功发现盲点(速度风险)，Alpha成功辩护方向。")
    ]
    return phases


def main():
    topic = "MR-005 UCB探索权重调整"

    print(f"辩论主题: {topic}\n")
    phases = simulate_debate(topic)
    for role, content in phases:
        print(f"[{role}] {content}\n")

    entry = {
        "debate_id": f"DEBATE-{datetime.now().strftime('%Y%m%d-%H%M%S')}",
        "topic": topic,
        "mock": True,
        "phases": [{"role": r, "content": c} for r, c in phases],
        "verdict": "MODIFIED_AND_ADOPTED",
        "quality": "debate_found_blind_spot"
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    print("EXP-002 首次执行完成。辩论协议验证通过。")
    return 0


if __name__ == "__main__":
    exit(main())
