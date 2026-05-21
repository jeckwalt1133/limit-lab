"""
btc-toolkit 快速验证
测试各模块加载、初始化、离线逻辑
"""
import sys
import os

# 确保导入路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from btc_toolkit.config import TARGET_BTC, ALLOCATION, GAS_LOW, GAS_HIGH
from btc_toolkit.strategies.conquer_engine import ConquerEngine
from btc_toolkit.scanners.airdrop_farmer import AirdropFarmer


def test_config():
    """测试配置加载"""
    assert TARGET_BTC == 100, "目标应为100 BTC"
    assert sum(ALLOCATION.values()) == pytest.approx(1.0, 0.01), "分配总和应为100%"
    assert GAS_LOW < GAS_HIGH, "gas低阈值应小于高阈值"
    print("✅ 配置加载正常")


def test_conquer_engine():
    """测试征服引擎"""
    engine = ConquerEngine(state_dir="./test_state")
    report = engine.report()

    assert engine.state.current_phase == 0
    assert len(engine.state.milestones) == 6
    assert "工具构建期" in report
    assert "0.01" in report

    # 测试日志
    engine.log_progress("测试: 模块验证", btc_earned=0, notes="离线测试")
    assert len(engine.state.daily_log) == 1

    print("✅ 征服引擎正常")
    print(report)

    # 清理测试目录
    import shutil
    shutil.rmtree("./test_state", ignore_errors=True)


def test_airdrop_farmer():
    """测试空投薅毛器"""
    farmer = AirdropFarmer(data_dir="./test_airdrop_data")

    # 验证目标项目
    assert len(farmer.TARGET_PROJECTS) >= 4

    # 验证任务
    tasks = farmer.get_priority_tasks()
    assert len(tasks) > 0
    print(f"✅ 空投任务: {len(tasks)} 个")

    # 验证计划
    plan = farmer.generate_farming_plan(wallet_count=10)
    assert plan["wallet_count"] == 10
    assert plan["estimated_total_value_usd"] > 0
    print(f"✅ 空投计划: {plan['active_projects']}项目 | 估值${plan['estimated_total_value_usd']:,}")

    import shutil
    shutil.rmtree("./test_airdrop_data", ignore_errors=True)


def test_mempool_client_offline():
    """测试Mempool客户端离线行为"""
    from btc_toolkit.core.mempool_api import MempoolClient, FeeEstimate

    client = MempoolClient()
    # 不需要网络也能创建实例
    assert client.base_url == "https://mempool.space/api"
    print("✅ Mempool客户端创建正常")

    # 测试数据结构
    fee = FeeEstimate(fastest=50, half_hour=30, hour=15, economy=8, minimum=3)
    assert fee.fastest > fee.economy
    print("✅ 费率数据结构正常")


if __name__ == "__main__":
    print("=" * 50)
    print("  btc-toolkit 验证测试")
    print("=" * 50)

    test_config()
    test_mempool_client_offline()
    test_airdrop_farmer()
    test_conquer_engine()

    print("\n" + "=" * 50)
    print("  ✅ 全部测试通过")
    print("=" * 50)
