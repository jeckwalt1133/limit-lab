"""
Runes / Ordinals 机会扫描器
检测新Rune蚀刻、低价mint机会、稀有sat检测
"""
import logging
from typing import List, Dict, Optional
from dataclasses import dataclass
from datetime import datetime

from ..core.mempool_api import MempoolClient

logger = logging.getLogger(__name__)


@dataclass
class RuneOpportunity:
    rune_id: str
    name: str
    symbol: str
    divisibility: int
    supply: int
    minted: int
    mint_progress: float  # 0-100
    current_floor: Optional[float]  # BTC
    estimated_mint_cost: float  # BTC (at current fee)
    profit_potential: str  # "HIGH" / "MEDIUM" / "LOW"
    reason: str


@dataclass
class RareSat:
    number: int
    name: str
    rarity: str  # uncommon, rare, epic, legendary, mythic
    block_height: int
    txid: Optional[str] = None
    value: Optional[int] = None  # satoshis


class RunesScanner:
    """Runes和Ordinals机会扫描"""

    # 稀有sat类型
    RARE_SAT_TYPES = {
        "mythic": "创世块第一个sat，仅1个",
        "legendary": "每个周期第一个块，约4年一个",
        "epic": "每个减半块第一个sat，约4年一个",
        "rare": "每个难度调整周期第一个块，约2016块一个",
        "uncommon": "每个块第一个sat，约每10分钟一个",
    }

    def __init__(self, client: MempoolClient):
        self.client = client

    def scan_fee_environment(self) -> dict:
        """扫描当前费率环境是否适合mint"""
        fees = self.client.get_fee_estimate()
        mempool = self.client.get_mempool()

        # 判断费率环境
        if fees.economy <= 5:
            mint_condition = "EXCELLENT"
        elif fees.economy <= 10:
            mint_condition = "GOOD"
        elif fees.economy <= 20:
            mint_condition = "ACCEPTABLE"
        elif fees.economy <= 50:
            mint_condition = "EXPENSIVE"
        else:
            mint_condition = "AVOID"

        return {
            "fastest_fee": fees.fastest,
            "economy_fee": fees.economy,
            "mempool_tx_count": mempool.get("count", 0),
            "mempool_mb": mempool.get("vsize", 0) / 1e6,
            "mint_condition": mint_condition,
            "estimated_mint_cost_btc": self._estimate_mint_cost(fees.economy),
            "estimated_mint_cost_usd": self._estimate_mint_cost_usd(fees.economy),
        }

    def _estimate_mint_cost(self, fee_rate: int) -> float:
        """估算mint一个Rune的BTC成本
        典型mint交易约200-400 vBytes
        """
        avg_vsize = 300
        return avg_vsize * fee_rate / 1e8

    def _estimate_mint_cost_usd(self, fee_rate: int) -> float:
        """估算mint的USD成本"""
        btc_cost = self._estimate_mint_cost(fee_rate)
        try:
            price_data = self.client.get_price()
            btc_usd = price_data.get("USD", 80000)
            return btc_cost * btc_usd
        except Exception:
            return btc_cost * 80000

    def scan_rare_sats(self, address: Optional[str] = None) -> List[RareSat]:
        """扫描稀有sat（需要ordinals索引）"""
        # 基于区块高度推算稀有sat位置（简化版，完整版需要ord服务器）
        rare_sats = []
        tip = self.client.tip_height

        # 检查最近的史诗/稀有sat可能出现的区块
        for h in range(tip - 2016, tip + 1):
            if h % 210000 == 0:
                rare_sats.append(RareSat(
                    number=h * 1e8,  # 近似值
                    name=f"Epic sat @ block {h}",
                    rarity="epic",
                    block_height=h,
                ))
            if h % 2016 == 0:
                rare_sats.append(RareSat(
                    number=h * 1e8,
                    name=f"Rare sat @ block {h}",
                    rarity="rare",
                    block_height=h,
                ))

        return rare_sats

    def monitor_new_etchings(self) -> List[dict]:
        """监控内存池中新的Rune蚀刻交易"""
        try:
            mempool_txids = self.client.get_mempool_txids()
            # 检查最近100个内存池交易
            # 完整的Rune检测需要解析OP_RETURN和见证数据
            # 这里给出框架，实际运行需要完整解析
            candidates = []
            for txid in mempool_txids[:100]:
                try:
                    tx = self.client.get_transaction(txid)
                    # 检测是否有OP_RETURN输出(Rune蚀刻的标志)
                    for vout in tx.get("vout", []):
                        if vout.get("scriptpubkey_type") == "op_return":
                            candidates.append({
                                "txid": txid,
                                "fee": tx.get("fee", 0),
                                "fee_rate": tx.get("fee", 0) / tx.get("weight", 1) * 4,
                                "size": tx.get("size", 0),
                                "timestamp": datetime.now().isoformat(),
                            })
                            break
                except Exception:
                    continue
            return candidates
        except Exception as e:
            logger.error(f"蚀刻监控失败: {e}")
            return []

    def generate_opportunity_report(self) -> dict:
        """生成完整机会报告"""
        fee_env = self.scan_fee_environment()

        opportunities = []
        if fee_env["mint_condition"] in ("EXCELLENT", "GOOD"):
            opportunities.append({
                "action": "LOW_FEE_MINT_WINDOW",
                "priority": "HIGH",
                "detail": f"当前经济费率 {fee_env['economy_fee']} sat/vB, mint成本约 ${fee_env['estimated_mint_cost_usd']:.2f}",
                "suggestion": "扫描高交易量Rune进行低成本mint",
            })

        return {
            "timestamp": datetime.now().isoformat(),
            "fee_environment": fee_env,
            "opportunities": opportunities,
            "block_height": self.client.tip_height,
        }
