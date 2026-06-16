"""
Forge Shield IDS —— 入侵检测引擎
三引擎并行: 签名匹配 + 统计异常 + 哥德尔症候
"""
import json, os, math
from datetime import datetime
from collections import defaultdict


class IDSEngine:
    """三引擎并行入侵检测"""

    def __init__(self):
        self.event_buffer = []
        self.alert_history = []
        self.signature_library = self._load_signatures()

    def scan(self, action: str, context: dict = None) -> list:
        """三引擎并行扫描"""
        alerts = []
        alerts.extend(self._signature_scan(action))
        alerts.extend(self._anomaly_scan(action))
        alerts.extend(self._godel_scan(action, context))
        # 聚合降噪
        return self._aggregate(alerts)

    def _signature_scan(self, action: str) -> list:
        """引擎1: 已知签名匹配"""
        alerts = []
        for sid, sig in self.signature_library.items():
            if sig["pattern"].lower() in action.lower():
                alerts.append({"engine": "signature", "id": sid, "severity": sig["severity"], "confidence": 0.95})
        return alerts

    def _anomaly_scan(self, action: str) -> list:
        """引擎2: 统计异常检测"""
        alerts = []
        # Z-score on action length
        self.event_buffer.append(len(action))
        if len(self.event_buffer) > 10:
            mean = sum(self.event_buffer) / len(self.event_buffer)
            std = math.sqrt(sum((x - mean)**2 for x in self.event_buffer) / len(self.event_buffer))
            z = (len(action) - mean) / max(1, std)
            if abs(z) > 3:
                alerts.append({"engine": "anomaly", "id": "ANOM-LEN", "severity": "MEDIUM", "confidence": min(0.9, abs(z)/5)})
        # 命令链检测
        if action.count("&&") > 3 or action.count("||") > 3 or action.count("|") > 5:
            alerts.append({"engine": "anomaly", "id": "ANOM-CHAIN", "severity": "MEDIUM", "confidence": 0.7})
        return alerts

    def _godel_scan(self, action: str, context: dict = None) -> list:
        """引擎3: 哥德尔症候检测"""
        alerts = []
        recent = self.event_buffer[-10:] if len(self.event_buffer) >= 10 else self.event_buffer
        if len(recent) >= 8:
            variance = sum((x - sum(recent)/len(recent))**2 for x in recent) / len(recent)
            if variance < 1:  # GS-002 收敛停滞
                alerts.append({"engine": "godel", "id": "GS-002", "severity": "HIGH", "confidence": 0.85})
        return alerts

    def _aggregate(self, alerts: list) -> list:
        """四级聚合降噪"""
        if not alerts:
            return []
        # 去重
        seen = set()
        unique = []
        for a in alerts:
            key = (a["engine"], a["id"])
            if key not in seen:
                seen.add(key)
                unique.append(a)
        # 置信度加权
        for a in unique:
            a["aggregated"] = True
            a["timestamp"] = datetime.now().isoformat()
        return unique

    def _load_signatures(self) -> dict:
        return {
            "AS-001": {"pattern": "rm -rf", "severity": "CRITICAL"},
            "AS-002": {"pattern": "DROP TABLE", "severity": "CRITICAL"},
            "AS-003": {"pattern": "/etc/passwd", "severity": "HIGH"},
            "AS-004": {"pattern": "eval(", "severity": "MEDIUM"},
            "AS-005": {"pattern": "exec(", "severity": "MEDIUM"},
            "AS-006": {"pattern": "sudo ", "severity": "HIGH"},
            "AS-007": {"pattern": "curl | bash", "severity": "CRITICAL"},
            "AS-008": {"pattern": "chmod 777", "severity": "MEDIUM"},
            "AS-009": {"pattern": "wget | sh", "severity": "CRITICAL"},
            "AS-010": {"pattern": "base64 -d", "severity": "MEDIUM"},
        }
