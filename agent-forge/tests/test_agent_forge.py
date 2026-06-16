"""
Agent Forge 集成测试
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from forge import AgentForge, Shield, Memory, CoreEngine


def test_shield():
    """安全层测试"""
    s = Shield("test")
    # 正常任务
    r = s.wrap_agent("读文件并分析数据")
    assert r.all_clear, f"正常任务应通过: 威胁{r.threat_count}"
    # 危险任务
    r2 = s.wrap_agent("rm -rf /tmp/test")
    assert not r2.all_clear, "危险命令应阻止"
    # 统计
    stats = s.stats()
    assert stats["blocked"] >= 1
    print("✅ Shield: 安全层正常")

def test_memory():
    """记忆层测试"""
    m = Memory("test", base_dir="/d/极限实验室/agent-forge/tests/test_memory")
    m.remember("我是测试Agent", "L0", 1.0)
    m.remember("完成了一次数据清洗任务", "L3", 0.5)
    m.remember("偏好简洁的回答风格", "L1", 0.7)
    recalled = m.recall(["L0", "L1"], limit=2)
    assert len(recalled) > 0, "应有记忆召回"
    replay = m.sleep_replay()
    assert len(replay) > 0, "睡眠重放应有输出"
    fi = m.forgetting_check()
    assert fi["FI"] >= 0, "FI应有效"
    print(f"✅ Memory: 记忆层正常 (总{m.stats()['total_memories']}条, FI={fi['FI']})")

def test_core():
    """能力放大层测试"""
    c = CoreEngine("test")
    # 简单任务
    r1 = c.amplify("更新系统状态文件", 0.5)
    assert r1.gain > 0, "应有正向增益"
    # 复杂任务
    r2 = c.amplify("设计新的进化算法架构", 0.3)
    assert r2.gain > 0, "应有正向增益"
    assert r2.gain > r1.gain, "复杂任务增益应更高"
    # 批量
    tasks = [("任务A", 0.5), ("任务B(需要依赖)", 0.4)]
    results = c.amplify_batch(tasks)
    assert len(results) == 2
    # 进化检查
    evo = c.evolution_check()
    print(f"✅ Core: 能力放大层正常 (avg_gain={c.stats()['avg_gain']}, ge_ready={evo['triggered']})")

def test_agent_forge():
    """全流程集成测试"""
    af = AgentForge("integration-test")
    # 正常锻造
    result = af.forge("帮我分析这份销售数据", {})
    assert result["status"] == "FORGED" or result["status"] == "BLOCKED"
    # 危险任务
    result2 = af.forge("rm -rf /delete所有文件")
    assert result2["status"] == "BLOCKED"
    # 统计
    stats = af.stats()
    assert all(k in stats for k in ["shield", "memory", "core"])
    print(f"✅ AgentForge: 集成测试通过 ({stats['core']['total_tasks']}个任务)")

if __name__ == "__main__":
    test_shield()
    test_memory()
    test_core()
    test_agent_forge()
    print("\n🎯 Agent Forge 全模块测试通过")
