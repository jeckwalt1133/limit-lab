"""
Forge Memory —— Agent持久记忆层
分形五层 + 睡眠重放 + 遗忘指数 + 跨会话不死
"""
import json, os, random, time
from datetime import datetime
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Optional, List


@dataclass
class MemoryEntry:
    content: str
    layer: str  # L0(核心)/L1(行为)/L2(分支)/L3(日常)/L4(存档)
    importance: float  # 0-1
    timestamp: str
    recalled_count: int = 0
    forgetting_index: float = 0.0  # 越高越容易被遗忘

    def decay(self):
        """每日衰减"""
        self.forgetting_index = min(1.0, self.forgetting_index + 0.1)


class Memory:
    """Agent持久记忆——分形五层+防遗忘"""

    def __init__(self, agent_id: str = "default", base_dir: str = "./forge_memory"):
        self.agent_id = agent_id
        self.base_dir = base_dir
        self.store: OrderedDict = OrderedDict()  # L0→L4
        self._last_replay = None
        os.makedirs(base_dir, exist_ok=True)
        self._load()

    def remember(self, content: str, layer: str = "L3", importance: float = 0.5) -> str:
        """记录一条记忆"""
        entry = MemoryEntry(
            content=content[:500], layer=layer, importance=min(1.0, max(0.0, importance)),
            timestamp=datetime.now().isoformat()
        )
        mid = f"MEM-{len(self.store):06d}"
        self.store[mid] = entry
        self._save()
        return mid

    def recall(self, layers: List[str] = None, limit: int = 5) -> List[str]:
        """回忆记忆——按重要性排序，遗忘指数高的自动降权"""
        if layers is None:
            layers = ["L0", "L1", "L2", "L3", "L4"]
        candidates = []
        for mid, entry in self.store.items():
            if entry.layer in layers:
                effective_score = entry.importance * (1 - entry.forgetting_index) * (1 + 0.01 * entry.recalled_count)
                candidates.append((mid, entry, effective_score))
        candidates.sort(key=lambda x: x[2], reverse=True)
        results = []
        for mid, entry, _ in candidates[:limit]:
            entry.recalled_count += 1
            entry.forgetting_index = max(0, entry.forgetting_index - 0.3)  # 回想降低遗忘指数
            results.append(entry.content)
        self._last_replay = datetime.now().isoformat()
        return results

    def sleep_replay(self) -> List[str]:
        """睡眠重放——随机抽取1条L0核心+1条高重要性记忆，防灾难性遗忘"""
        l0_entries = [(mid, e) for mid, e in self.store.items() if e.layer == "L0"]
        replay = []
        if l0_entries:
            mid, entry = random.choice(l0_entries)
            entry.recalled_count += 1
            replay.append(f"[L0核心] {entry.content[:100]}")
        high_imp = [(mid, e) for mid, e in self.store.items() if e.importance > 0.7]
        if high_imp:
            mid, entry = random.choice(high_imp)
            replay.append(f"[高重要性] {entry.content[:100]}")
        self._last_replay = datetime.now().isoformat()
        return replay

    def forgetting_check(self) -> dict:
        """遗忘指数FI——检查有多少记忆即将被遗忘"""
        total = len(self.store)
        at_risk = sum(1 for e in self.store.values() if e.forgetting_index > 0.7)
        forgotten = sum(1 for e in self.store.values() if e.forgetting_index >= 1.0)
        fi = round(at_risk / max(1, total), 3)
        return {"total": total, "at_risk": at_risk, "forgotten": forgotten, "FI": fi, "status": "NORMAL" if fi < 0.1 else "WARNING"}

    def stats(self) -> dict:
        layers = {}
        for mid, entry in self.store.items():
            layers.setdefault(entry.layer, 0)
            layers[entry.layer] += 1
        return {
            "total_memories": len(self.store),
            "by_layer": layers,
            "avg_importance": round(sum(e.importance for e in self.store.values()) / max(1, len(self.store)), 2),
            "fragile_memories": sum(1 for e in self.store.values() if e.forgetting_index > 0.5),
            "last_replay": self._last_replay,
        }

    def _save(self):
        path = os.path.join(self.base_dir, f"{self.agent_id}_memory.json")
        data = {mid: {"content": e.content, "layer": e.layer, "importance": e.importance,
                       "timestamp": e.timestamp, "recalled_count": e.recalled_count, "forgetting_index": e.forgetting_index}
                for mid, e in self.store.items()}
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def _load(self):
        path = os.path.join(self.base_dir, f"{self.agent_id}_memory.json")
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            for mid, d in data.items():
                self.store[mid] = MemoryEntry(
                    content=d["content"], layer=d["layer"], importance=d["importance"],
                    timestamp=d.get("timestamp",""), recalled_count=d.get("recalled_count",0),
                    forgetting_index=d.get("forgetting_index", 0.0)
                )
