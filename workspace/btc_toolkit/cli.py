"""
极限实验室 — 比特币征服工具包 CLI
"""
import sys
import json
import argparse
from datetime import datetime

from .core.mempool_api import MempoolClient
from .core.onchain import OnChainAnalyzer
from .scanners.runes_scanner import RunesScanner
from .scanners.airdrop_farmer import AirdropFarmer
from .scanners.arbitrage import ArbitrageScanner
from .config import TARGET_BTC, ALLOCATION


def cmd_health(client: MempoolClient):
    """网络健康检查"""
    print("=" * 50)
    print("  极限实验室 — 比特币网络健康")
    print("=" * 50)

    try:
        fees = client.get_fee_estimate()
        tip = client.tip_height
        mempool = client.get_mempool()
        price = client.get_price()

        print(f"\n  区块高度: {tip:,}")
        print(f"  BTC/USD:  ${price.get('USD', 'N/A'):,}")
        print(f"  EUR:      €{price.get('EUR', 'N/A'):,}")
        print(f"\n  推荐费率 (sat/vB):")
        print(f"    最快:   {fees.fastest}")
        print(f"    半小时: {fees.half_hour}")
        print(f"    1小时:  {fees.hour}")
        print(f"    经济:   {fees.economy}")
        print(f"\n  内存池: {mempool.get('count', 0):,} tx | {mempool.get('vsize', 0) / 1e6:.1f} MB")

        # 评估
        if mempool.get('count', 0) < 50000:
            print("\n  ✅ 网络畅通 — 适合操作")
        elif mempool.get('count', 0) < 100000:
            print("\n  ⚠️ 网络中等拥堵 — 关注费率")
        else:
            print("\n  🔴 网络拥堵 — 等待低费率窗口")

    except Exception as e:
        print(f"\n  ❌ 网络不可达: {e}")
        print("  切换到离线模式，使用缓存数据")
        return 1
    return 0


def cmd_scan(client: MempoolClient):
    """全扫描"""
    print("=" * 50)
    print("  极限实验室 — 机会全扫描")
    print("=" * 50)

    try:
        # Runes扫描
        print("\n  [1/3] Runes/Ordinals 费率环境...")
        runes = RunesScanner(client)
        fee_env = runes.scan_fee_environment()
        print(f"    Mint条件: {fee_env['mint_condition']}")
        print(f"    估算Mint成本: {fee_env['estimated_mint_cost_btc']:.8f} BTC (${fee_env['estimated_mint_cost_usd']:.2f})")

        # 套利扫描
        print("\n  [2/3] 跨市场套利...")
        arb = ArbitrageScanner(client)
        opps = arb.detect_btc_arbitrage()
        if opps:
            for opp in opps:
                print(f"    {opp.asset}: {opp.buy_market}→{opp.sell_market} 价差{opp.spread_pct}% | 净利{opp.net_profit_btc:.6f} BTC")
        else:
            print("    当前无显著套利机会")

        # 空投机会
        print("\n  [3/3] 空投机会...")
        farmer = AirdropFarmer()
        plan = farmer.generate_farming_plan(wallet_count=10)
        print(f"    活跃项目: {plan['active_projects']}")
        print(f"    今日任务数: {len(plan['tasks_today'])}")
        print(f"    估算总价值: ${plan['estimated_total_value_usd']:,} ≈ {plan['estimated_btc']:.4f} BTC")

    except Exception as e:
        print(f"\n  ❌ 扫描失败: {e}")
        return 1
    return 0


def cmd_address(client: MempoolClient, address: str):
    """地址分析"""
    print(f"\n  分析地址: {address}")
    print("-" * 40)
    try:
        analyzer = OnChainAnalyzer(client)
        report = analyzer.analyze_address(address)
        print(f"  余额: {report.btc_balance:.8f} BTC ({report.balance:,} sats)")
        print(f"  交易数: {report.tx_count}")
        print(f"  UTXO数: {report.utxo_count}")
        print(f"  总收入: {report.total_received / 1e8:.8f} BTC")
        print(f"  总支出: {report.total_sent / 1e8:.8f} BTC")
    except Exception as e:
        print(f"  ❌ 查询失败: {e}")
        return 1
    return 0


def cmd_target():
    """目标追踪"""
    print("\n  🎯 100 BTC 征服路线图")
    print("=" * 40)
    print(f"""
  目标: {TARGET_BTC} BTC
  当前BTC ≈ $80,000
  目标USD ≈ ${TARGET_BTC * 80000:,}

  路径分配:
    🪂 空投薅毛:  {ALLOCATION['airdrop_farming']*100:.0f}%  ≈ {TARGET_BTC * ALLOCATION['airdrop_farming']:.0f} BTC
    📊 套利:      {ALLOCATION['arbitrage']*100:.0f}%  ≈ {TARGET_BTC * ALLOCATION['arbitrage']:.0f} BTC
    🛠️ 产品收入:  {ALLOCATION['product_revenue']*100:.0f}%  ≈ {TARGET_BTC * ALLOCATION['product_revenue']:.0f} BTC
    📈 交易:      {ALLOCATION['trading']*100:.0f}%  ≈ {TARGET_BTC * ALLOCATION['trading']:.0f} BTC
    💎 储备:      {ALLOCATION['reserve']*100:.0f}%  ≈ {TARGET_BTC * ALLOCATION['reserve']:.0f} BTC

  当前阶段: 零资本起步 → 工具构建 → 首笔BTC收入
  下一步:   网络通后接入实时数据
  """)
    return 0


def main():
    parser = argparse.ArgumentParser(
        description="极限实验室 — 比特币征服工具包",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  btc-conquer health         检查网络健康
  btc-conquer scan           全扫描机会
  btc-conquer address <addr> 分析地址
  btc-conquer target         查看目标路线图
  btc-conquer airdrop        显示空投薅毛计划
        """,
    )
    parser.add_argument("command", choices=["health", "scan", "address", "target", "airdrop"])
    parser.add_argument("arg", nargs="?", help="地址等参数")

    args = parser.parse_args()

    client = MempoolClient()

    commands = {
        "health": lambda: cmd_health(client),
        "scan": lambda: cmd_scan(client),
        "address": lambda: cmd_address(client, args.arg),
        "target": lambda: cmd_target(),
        "airdrop": lambda: cmd_airdrop(),
    }

    cmd = commands.get(args.command)
    if cmd:
        return cmd()
    return 0


def cmd_airdrop():
    """显示空投计划"""
    farmer = AirdropFarmer()
    tasks = farmer.get_priority_tasks()
    plan = farmer.generate_farming_plan()

    print("\n  🪂 比特币L2空投薅毛计划")
    print("=" * 50)

    print("\n  ⚡ 今日优先任务:")
    for i, t in enumerate(tasks[:8], 1):
        print(f"  {i}. [{t['priority']}] {t['project']}: {t['task']}")

    print(f"\n  💰 潜在收益估算 (10钱包):")
    print(f"     USD: ${plan['estimated_total_value_usd']:,}")
    print(f"     BTC: {plan['estimated_btc']:.4f}")

    print(f"\n  📋 启动步骤:")
    for step in plan['start_now']:
        print(f"    {step}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
