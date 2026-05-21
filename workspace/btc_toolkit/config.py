"""
比特币工具包配置
零API Key模式 — 优先使用免费公开端点
"""

# Mempool.space 公开API (无需API Key)
MEMPOOL_API_BASE = "https://mempool.space/api"
MEMPOOL_TESTNET = "https://mempool.space/testnet/api"

# 备用: Bitcoin RPC (可通过Pocket Network免Key访问)
POCKET_RPC = "https://bitcoin-mainnet.rpc.pokt.network"

# 目标: 100 BTC
TARGET_BTC = 100

# 各路径分配权重
ALLOCATION = {
    "airdrop_farming": 0.30,   # 空投薅毛 30%
    "arbitrage": 0.25,         # 套利 25%
    "product_revenue": 0.25,   # 产品收入 25%
    "trading": 0.15,           # 交易 15%
    "reserve": 0.05,           # 储备 5%
}

# 费率阈值 (sat/vB)
GAS_LOW = 5       # 低费率窗口
GAS_MEDIUM = 20   # 中等
GAS_HIGH = 50     # 高费率
GAS_AVOID = 100   # 避免操作

# 链上数据缓存 (秒)
CACHE_TTL = {
    "address": 60,
    "tx": 300,
    "block": 600,
    "mempool": 15,
    "fees": 30,
}
