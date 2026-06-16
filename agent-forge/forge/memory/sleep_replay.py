"""Forge Memory 睡眠重放引擎——防灾难性遗忘"""
import json, os, random, hashlib
from datetime import datetime
from collections import deque

class SleepReplay:
    def __init__(self, memory_store):
        self.memory = memory_store
        self.replay_history = deque(maxlen=100)

    def replay(self) -> list:
        results = []
        l0 = [(mid,e) for mid,e in self.memory.store.items() if e.layer=="L0"]
        if l0:
            mid, entry = random.choice(l0)
            entry.recalled_count += 1
            entry.forgetting_index = max(0, entry.forgetting_index - 0.3)
            results.append(f"[L0] {entry.content[:120]}")
        high = [(mid,e) for mid,e in self.memory.store.items() if e.importance>0.6 and e.layer!="L0"]
        if high:
            mid, entry = random.choice(high)
            entry.recalled_count += 1
            results.append(f"[高重要性] {entry.content[:120]}")
        self.replay_history.append({"time": datetime.now().isoformat(), "count": len(results)})
        return results

class ForgettingIndex:
    def __init__(self, memory_store):
        self.memory = memory_store
        self.thresholds = {"NORMAL": 0.05, "NOTICE": 0.10, "WARNING": 0.20, "ALERT": 0.35, "EMERGENCY": 0.50}

    def compute(self) -> dict:
        total = len(self.memory.store)
        if total == 0: return {"cFI": 0, "level": "NORMAL"}
        wfi = sum(e.forgetting_index * e.importance for e in self.memory.store.values()) / total
        cfi = round(wfi, 3)
        level = "NORMAL"
        for name, threshold in sorted(self.thresholds.items(), key=lambda x: x[1], reverse=True):
            if cfi >= threshold: level = name; break
        return {"cFI": cfi, "level": level, "total": total, "at_risk": sum(1 for e in self.memory.store.values() if e.forgetting_index > 0.5)}
