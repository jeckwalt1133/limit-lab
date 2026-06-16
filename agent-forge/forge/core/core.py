"""
Forge Core —— Agent能力放大引擎
31条元规则 + Auto-GE持续进化 + 哥德尔跳维度扩展 + 模型无关
"""
import json, os, random, time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List, Dict


@dataclass
class AmplifyResult:
    """能力放大结果"""
    task: str
    original_score: float
    amplified_score: float
    gain: float
    rules_applied: List[str]
    evolution_triggered: bool
    timestamp: str


class CoreEngine:
    """Agent能力放大——产品级"""

    def __init__(self, agent_id: str = "default", model: str = "deepseek-v4-pro"):
        self.agent_id = agent_id
        self.model = model
        self.rules_active = {
            "MR-010": "direction_check",
            "MR-011": "parallel_tools",
            "MR-012": "task_routing",
            "MR-013": "anti_overfit",
            "MR-014": "convergence_detect",
            "MR-017": "evolution_speed",
            "MR-020": "noise_injection",
            "MR-022": "acceleration_track",
        }
        self.history: List[AmplifyResult] = []

    def amplify(self, task: str, baseline_score: float = 0.0) -> AmplifyResult:
        """核心API——放大Agent的任务能力"""
        complexity = self._route_complexity(task)
        rules = self._select_rules(complexity)
        amplified = self._apply_rules(task, rules, baseline_score)

        result = AmplifyResult(
            task=task[:100], original_score=baseline_score,
            amplified_score=amplified, gain=round(amplified - baseline_score, 3),
            rules_applied=rules, evolution_triggered=False,
            timestamp=datetime.now().isoformat()
        )

        # 触发Auto-GE检查
        if len(self.history) > 0 and amplified < self.history[-1].amplified_score * 0.7:
            result.evolution_triggered = True
            result.rules_applied.append("AUTO-GE-TRIGGERED")

        self.history.append(result)
        return result

    def  amplify_batch(self, tasks: List[tuple]) -> List[AmplifyResult]:
        """批量并行放大"""
        independent, dependent = self._analyze_dag(tasks)
        results = []
        for task, baseline in independent:
            results.append(self.amplify(task, baseline))
        for task, baseline in dependent:
            results.append(self.amplify(task, baseline))
        return results

    def evolution_check(self) -> dict:
        """检查是否需要哥德尔跳"""
        if len(self.history) < 3:
            return {"triggered": False, "reason": "数据不足"}
        recent_3 = self.history[-3:]
        avg_gain = sum(r.gain for r in recent_3) / 3
        if avg_gain < 0.02:
            return {"triggered": True, "reason": f"连续3次增益<2%: avg={avg_gain:.3f}", "action": "启动哥德尔引擎"}
        return {"triggered": False, "avg_gain": round(avg_gain, 3)}

    def stats(self) -> dict:
        total = len(self.history)
        if total == 0:
            return {"total_tasks": 0}
        avg_gain = sum(r.gain for r in self.history) / total
        ge_triggers = sum(1 for r in self.history if r.evolution_triggered)
        return {
            "total_tasks": total, "avg_gain": round(avg_gain, 3),
            "ge_triggers": ge_triggers, "rules_active": len(self.rules_active),
            "evolution_ready": self.evolution_check()["triggered"]
        }

    def _route_complexity(self, task: str) -> str:
        """MR-012: 任务复杂度路由"""
        score = len(task) / 50
        if any(w in task for w in ["设计", "进化", "哥德尔", "架构"]):
            score += 2
        if any(w in task for w in ["检查", "更新", "日志"]):
            score -= 1
        return "high" if score > 2 else "medium" if score > 1 else "low"

    def _select_rules(self, complexity: str) -> List[str]:
        """选择适用的规则"""
        if complexity == "high":
            return ["MR-010", "MR-011", "MR-012", "MR-013", "MR-017", "MR-022"]
        elif complexity == "medium":
            return ["MR-010", "MR-011", "MR-012", "MR-017"]
        return ["MR-010", "MR-011"]

    def _apply_rules(self, task: str, rules: List[str], baseline: float) -> float:
        """应用规则——模拟能力放大"""
        gain = 0.0
        # MR-011: 并行工具调用增益
        if "MR-011" in rules:
            gain += 0.05 * len(task.split()) / 10
        # MR-012: 复杂度路由增益
        if "MR-012" in rules:
            gain += 0.03
        # MR-013: 抗过拟合——防止过度优化
        if "MR-013" in rules and len(self.history) > 5:
            recent_gains = [r.gain for r in self.history[-5:]]
            if all(g > 0.1 for g in recent_gains):
                gain -= 0.02  # 反向调节
        # MR-020: 建设性噪声
        if "MR-020" in rules and random.random() < 0.07:
            gain += random.uniform(0.01, 0.05)
        return round(baseline + gain, 3)

    def _analyze_dag(self, tasks: List[tuple]) -> tuple:
        """MR-011: 分析任务DAG"""
        independent = [(t, b) for t, b in tasks if "依赖" not in t]
        dependent = [(t, b) for t, b in tasks if "依赖" in t]
        return independent, dependent
