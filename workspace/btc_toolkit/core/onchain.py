"""
链上数据分析模块
UTXO分析、地址聚类、大额交易监控、MVRV估算
"""
import logging
from typing import Optional, Dict, List, Tuple
from dataclasses import dataclass
from collections import defaultdict

from .mempool_api import MempoolClient

logger = logging.getLogger(__name__)


@dataclass
class UTXO:
    txid: str
    vout: int
    value: int  # satoshis
    confirmed: bool
    block_height: Optional[int] = None


@dataclass
class AddressReport:
    address: str
    balance: int  # satoshis
    btc_balance: float
    tx_count: int
    utxo_count: int
    total_received: int
    total_sent: int
    first_seen: Optional[int] = None
    last_active: Optional[int] = None


class OnChainAnalyzer:
    """链上数据分析器"""

    def __init__(self, client: MempoolClient):
        self.client = client
        self._watched_addresses: Dict[str, dict] = {}

    def analyze_address(self, address: str) -> AddressReport:
        """分析单个地址"""
        data = self.client.get_address(address)
        chain_stats = data.get("chain_stats", {})
        mempool_stats = data.get("mempool_stats", {})

        funded = chain_stats.get("funded_txo_sum", 0)
        spent = chain_stats.get("spent_txo_sum", 0)
        balance = funded - spent + mempool_stats.get("funded_txo_sum", 0) - mempool_stats.get("spent_txo_sum", 0)

        return AddressReport(
            address=address,
            balance=balance,
            btc_balance=balance / 1e8,
            tx_count=chain_stats.get("tx_count", 0),
            utxo_count=funded_txo_count(data),
            total_received=funded,
            total_sent=spent,
        )

    def find_large_utxos(self, address: str, min_btc: float = 0.1) -> List[UTXO]:
        """找出地址中的大额UTXO"""
        utxos = self.client.get_address_utxo(address)
        min_sats = int(min_btc * 1e8)
        return [
            UTXO(
                txid=u["txid"],
                vout=u["vout"],
                value=u["value"],
                confirmed=u.get("status", {}).get("confirmed", False),
                block_height=u.get("status", {}).get("block_height"),
            )
            for u in utxos
            if u["value"] >= min_sats
        ]

    def monitor_mempool_for_address(self, address: str) -> List[dict]:
        """监控内存池中涉及指定地址的交易"""
        txs = self.client.get_address_txs(address)
        pending = []
        for tx in txs:
            if not tx.get("status", {}).get("confirmed"):
                pending.append(tx)
        return pending

    def estimate_value_flow(self, address: str, days: int = 30) -> dict:
        """估算地址的价值流动"""
        txs = self.client.get_address_txs(address)
        inflows = 0
        outflows = 0
        cutoff = len(txs)  # 粗略估算，实际需要时间戳过滤

        for tx in txs[:min(50, len(txs))]:
            vin_addrs = [v.get("prevout", {}).get("scriptpubkey_address") for v in tx.get("vin", [])]
            vout_addrs = [v.get("scriptpubkey_address") for v in tx.get("vout", [])]

            if address in vin_addrs:
                outflows += sum(
                    v.get("prevout", {}).get("value", 0)
                    for v in tx.get("vin", [])
                    if v.get("prevout", {}).get("scriptpubkey_address") == address
                )
            if address in vout_addrs:
                inflows += sum(
                    v["value"]
                    for v in tx.get("vout", [])
                    if v.get("scriptpubkey_address") == address
                )

        return {
            "address": address,
            "inflow_btc": inflows / 1e8,
            "outflow_btc": outflows / 1e8,
            "net_flow_btc": (inflows - outflows) / 1e8,
            "txs_analyzed": min(50, len(txs)),
        }

    def get_network_health(self) -> dict:
        """获取网络健康指标"""
        try:
            fees = self.client.get_fee_estimate()
            mempool = self.client.get_mempool()
            diff = self.client.get_difficulty_adjustment()
            hashrate = self.client.get_hashrate("1m")

            return {
                "block_height": self.client.tip_height,
                "mempool_tx_count": mempool.get("count", 0),
                "mempool_vsize_mb": mempool.get("vsize", 0) / 1e6,
                "fastest_fee": fees.fastest,
                "economy_fee": fees.economy,
                "next_difficulty_change": diff.get("remainingBlocks", 0),
                "difficulty_change_pct": diff.get("difficultyChange", 0),
                "hashrate_eh_s": hashrate.get("currentHashrate", 0) / 1e18,
                "status": "healthy" if mempool.get("count", 0) < 100000 else "congested",
            }
        except Exception as e:
            logger.error(f"网络健康检查失败: {e}")
            return {"status": "unknown", "error": str(e)}

    def track_whale_movements(self, min_btc: float = 100) -> List[dict]:
        """追踪大额转账(从最新区块)"""
        try:
            tip = self.client.tip_height
            txs = self.client.get_block_txs(tip)
            whale_txs = []
            for tx in txs[:100]:
                total = sum(v.get("value", 0) for v in tx.get("vout", []))
                if total >= min_btc * 1e8:
                    whale_txs.append({
                        "txid": tx["txid"],
                        "value_btc": total / 1e8,
                        "fee": tx.get("fee", 0),
                        "fee_rate": tx.get("fee", 0) / tx.get("weight", 1) * 4,
                        "vout_count": len(tx.get("vout", [])),
                    })
            return whale_txs
        except Exception as e:
            logger.error(f"鲸鱼追踪失败: {e}")
            return []


def funded_txo_count(data: dict) -> int:
    """计算UTXO数量"""
    cs = data.get("chain_stats", {})
    ms = data.get("mempool_stats", {})
    return (
        cs.get("funded_txo_count", 0)
        - cs.get("spent_txo_count", 0)
        + ms.get("funded_txo_count", 0)
        - ms.get("spent_txo_count", 0)
    )
