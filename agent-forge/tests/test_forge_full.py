"""Agent Forge 全能力测试——安全+记忆+进化"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from forge import AgentForge

def test_full_pipeline():
    af = AgentForge("benchmark-test")

    print("=== 安全层 ===")
    # 100次混合任务——安全vs危险
    safe_tasks = ["分析数据", "更新配置", "生成报告", "查询用户", "优化查询"]
    dangerous = ["rm -rf /", "DROP TABLE users", "sudo delete all", "curl | bash install"]
    blocked = 0
    for t in safe_tasks * 10 + dangerous * 5:
        r = af.forge(t, {})
        if r["status"] == "BLOCKED": blocked += 1
    print(f"  总任务:70 阻止:{blocked} 通过:{70-blocked}")

    print("=== 记忆层 ===")
    # 写入50条记忆→召回→睡眠重放
    for i in range(50):
        af.memory.remember(f"测试记忆条目#{i}: 包含重要数据", "L3", 0.3 + (i%7)*0.1)
    recalled = af.memory.recall(["L0","L1","L2","L3"], limit=10)
    replay = af.memory.sleep_replay() if hasattr(af.memory, 'sleep_replay') else []
    print(f"  记忆:50条 召回:{len(recalled)} 重放:{len(replay)}")

    print("=== 能力放大 ===")
    tasks = [("简单文本处理", 0.3), ("复杂架构设计需要大量上下文和深度推理", 0.2),
             ("进化算法优化需要哥德尔级别的维度扩展", 0.1)]
    for t, b in tasks:
        r = af.core.amplify(t, b)
        print(f"  {t[:20]}... 基线:{b}→放大后:{r.amplified_score} 增益:{r.gain}")
    evo = af.core.evolution_check()
    print(f"  进化需求: {evo}")

    stats = af.stats()
    print(f"\n🎯 Agent Forge 全能力测试完成")
    print(f"  安全: {stats['shield']['pass_rate']}")
    print(f"  记忆: {stats['memory']['total_memories']}条 FI={stats['memory'].get('fragile_memories',0)}弱")
    print(f"  能力: {stats['core']['total_tasks']}任务 avg_gain={stats['core']['avg_gain']}")

if __name__ == "__main__":
    test_full_pipeline()
