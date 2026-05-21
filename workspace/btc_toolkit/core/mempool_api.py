"""
Mempool.space API 客户端
免费公开端点，无需API Key
速率限制: ~10 req/min 公开端点，自建实例无限制
"""
import time
import logging
from typing import Optional, Dict, List, Any
from dataclasses import dataclass, field
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError
import json

from ..config import MEMPOOL_API_BASE, CACHE_TTL

logger = logging.getLogger(__name__)


@dataclass
class TxInput:
    txid: str
    vout: int
    value: int  # satoshis
    address: Optional[str] = None


@dataclass
class TxOutput:
    address: Optional[str]
    value: int  # satoshis
    scriptpubkey: Optional[str] = None


@dataclass
class Transaction:
    txid: str
    version: int
    locktime: int
    size: int
    weight: int
    fee: int
    status: Dict
    vin: List[TxInput] = field(default_factory=list)
    vout: List[TxOutput] = field(default_factory=list)
    confirmed: bool = False
    block_height: Optional[int] = None
    timestamp: Optional[int] = None

    @property
    def fee_rate(self) -> float:
        """sat/vB"""
        return self.fee / self.weight * 4 if self.weight > 0 else 0

    @property
    def total_input(self) -> int:
        return sum(vin.value for vin in self.vin)

    @property
    def total_output(self) -> int:
        return sum(vout.value for vout in self.vout)


@dataclass
class MempoolStats:
    count: int
    vsize: int  # virtual size
    total_fee: int
    fee_histogram: List[Dict]


@dataclass
class FeeEstimate:
    fastest: int   # 下一个区块
    half_hour: int  # 30分钟
    hour: int      # 1小时
    economy: int   # 最低
    minimum: int   # 纯最小值


class MempoolClient:
    """Mempool.space API 客户端"""

    def __init__(self, base_url: str = MEMPOOL_API_BASE, cache_ttl: dict = None):
        self.base_url = base_url.rstrip("/")
        self.cache_ttl = cache_ttl or CACHE_TTL
        self._cache: Dict[str, tuple] = {}  # key -> (data, timestamp)
        self._request_count = 0
        self._last_request_time = 0
        self._min_interval = 0.15  # 最小请求间隔(秒)，约6.7 req/s上限

    def _rate_limit(self):
        """简单的自限速"""
        elapsed = time.time() - self._last_request_time
        if elapsed < self._min_interval:
            time.sleep(self._min_interval - elapsed)
        self._last_request_time = time.time()
        self._request_count += 1

    def _get(self, path: str, use_cache: bool = True, cache_ttl: int = None) -> dict:
        """GET请求，带缓存和限速"""
        url = f"{self.base_url}{path}"

        # 检查缓存
        if use_cache and url in self._cache:
            data, ts = self._cache[url]
            ttl = cache_ttl or 30
            if time.time() - ts < ttl:
                return data

        self._rate_limit()

        req = Request(url, headers={"Accept": "application/json"})
        try:
            with urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode())
                if use_cache:
                    self._cache[url] = (data, time.time())
                return data
        except HTTPError as e:
            logger.error(f"HTTP {e.code}: {url}")
            if e.code == 429:
                logger.warning("速率限制触发，等待3秒...")
                time.sleep(3)
                return self._get(path, use_cache=False)
            raise
        except URLError as e:
            logger.error(f"网络错误: {e}")
            raise

    def get_address(self, address: str) -> dict:
        """获取地址信息"""
        return self._get(f"/address/{address}", cache_ttl=self.cache_ttl["address"])

    def get_address_txs(self, address: str, after_txid: str = None) -> list:
        """获取地址交易列表"""
        path = f"/address/{address}/txs"
        if after_txid:
            path += f"/chain/{after_txid}"
        return self._get(path, cache_ttl=self.cache_ttl["address"])

    def get_address_utxo(self, address: str) -> list:
        """获取地址UTXO"""
        return self._get(f"/address/{address}/utxo", cache_ttl=self.cache_ttl["address"])

    def get_transaction(self, txid: str) -> dict:
        """获取交易详情"""
        return self._get(f"/tx/{txid}", cache_ttl=self.cache_ttl["tx"])

    def get_transaction_hex(self, txid: str) -> str:
        """获取交易原始hex"""
        self._rate_limit()
        req = Request(f"{self.base_url}/tx/{txid}/hex", headers={"Accept": "text/plain"})
        with urlopen(req, timeout=15) as resp:
            return resp.read().decode()

    def get_transaction_status(self, txid: str) -> dict:
        """获取交易确认状态"""
        return self._get(f"/tx/{txid}/status")

    def get_block(self, hash_or_height) -> dict:
        """获取区块信息"""
        return self._get(f"/block/{hash_or_height}", cache_ttl=self.cache_ttl["block"])

    def get_block_txs(self, hash_or_height, start_index: int = 0) -> list:
        """获取区块内交易列表"""
        path = f"/block/{hash_or_height}/txs"
        if start_index:
            path += f"/{start_index}"
        return self._get(path, cache_ttl=self.cache_ttl["block"])

    def get_block_height(self, height: int) -> str:
        """根据高度获取区块哈希"""
        self._rate_limit()
        req = Request(f"{self.base_url}/block-height/{height}", headers={"Accept": "text/plain"})
        with urlopen(req, timeout=15) as resp:
            return resp.read().decode()

    def get_mempool(self) -> dict:
        """获取内存池统计"""
        return self._get("/mempool", cache_ttl=self.cache_ttl["mempool"])

    def get_mempool_txids(self) -> list:
        """获取内存池中所有txid"""
        return self._get("/mempool/txids", cache_ttl=self.cache_ttl["mempool"])

    def get_fees_recommended(self) -> dict:
        """获取推荐费率"""
        return self._get("/v1/fees/recommended", cache_ttl=self.cache_ttl["fees"])

    def get_fee_estimate(self) -> FeeEstimate:
        """获取结构化费率估算"""
        fees = self.get_fees_recommended()
        return FeeEstimate(
            fastest=fees.get("fastestFee", 50),
            half_hour=fees.get("halfHourFee", 30),
            hour=fees.get("hourFee", 15),
            economy=fees.get("economyFee", 8),
            minimum=fees.get("minimumFee", 3),
        )

    def get_difficulty_adjustment(self) -> dict:
        """获取难度调整信息"""
        return self._get("/v1/difficulty-adjustment")

    def get_hashrate(self, interval: str = "1m") -> dict:
        """获取算力数据 (1m/3m/1w/1y等)"""
        return self._get(f"/v1/mining/hashrate/{interval}")

    def get_price(self) -> dict:
        """获取BTC价格 (从mempool)"""
        return self._get("/v1/prices")

    def lookup_addresses(self, addresses: list) -> dict:
        """批量查询地址余额 (POST)"""
        self._rate_limit()
        data = json.dumps({"addresses": addresses}).encode()
        req = Request(
            f"{self.base_url}/v1/addresses/lookup",
            data=data,
            headers={"Content-Type": "application/json", "Accept": "application/json"},
            method="POST",
        )
        with urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode())

    @property
    def tip_height(self) -> int:
        """当前区块高度"""
        return self._get("/blocks/tip/height", cache_ttl=15)

    def health_check(self) -> bool:
        """API连通性检查"""
        try:
            self.get_fees_recommended()
            return True
        except Exception:
            return False
