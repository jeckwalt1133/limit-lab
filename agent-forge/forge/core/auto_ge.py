"""Forge Core Auto-GE —— 持续自进化引擎"""
import json, os, math
from datetime import datetime
from collections import defaultdict

class GSSyndromeDetector:
    """哥德尔症候检测——5维5症候"""
    def __init__(self):
        self.score_history = defaultdict(list)

    def scan(self, recent_scores: dict) -> dict:
        gs = {}
        # GS-001 评估坍塌
        gs["GS-001"] = 1.0 if all(v < 0.05 for v in recent_scores.values()) else 0.0
        # GS-002 收敛停滞
        variances = {}
        for k, v in self.score_history.items():
            if len(v) >= 3: variances[k] = sum((x-sum(v)/len(v))**2 for x in v[-3:])/max(1,len(v[-3:]))
        gs["GS-002"] = 1.0 if any(v < 0.001 for v in variances.values()) else 0.5 if variances else 0.0
        # GS-003 外部不可吸收——简化：从未有新维度
        gs["GS-003"] = 0.5
        # GS-004 循环重复
        gs["GS-004"] = 0.5 if len(self.score_history.get("gain",[])) >= 5 and len(set(round(g,2) for g in self.score_history["gain"][-5:])) <= 2 else 0.0
        # GS-005 签名过稳定
        gs["GS-005"] = 0.0
        composite = sum(gs.values()) / 5
        triggered = composite > 0.6
        for k, v in recent_scores.items():
            self.score_history[k].append(v)
        return {"gs_scores": gs, "composite": round(composite, 3), "triggered": triggered}

class AutoGEEngine:
    """自动化哥德尔引擎——Agent能力持续自进化"""
    def __init__(self):
        self.gs_detector = GSSyndromeDetector()
        self.axioms_generated = []
        self.evolution_cycles = 0

    def evolve(self, task_scores: dict) -> dict:
        gs_result = self.gs_detector.scan(task_scores)
        result = {"gs": gs_result, "action": "NONE"}
        if gs_result["triggered"]:
            self.evolution_cycles += 1
            axiom = self._generate_axiom(gs_result)
            self.axioms_generated.append(axiom)
            result["action"] = "GODEL_LEAP"
            result["axiom"] = axiom
        self.evolution_cycles += 1
        return result

    def _generate_axiom(self, gs: dict) -> dict:
        axi = {"id": f"AX-{len(self.axioms_generated):04d}", "composite": gs["composite"],
               "timestamp": datetime.now().isoformat()}
        top = max(gs["gs_scores"], key=gs["gs_scores"].get)
        axi["trigger"] = top
        if top == "GS-002":
            axi["type"] = "DIMENSION_EXPANSION"; axi["action"] = "添加新评估维度"
        elif top == "GS-004":
            axi["type"] = "STRUCTURE_MUTATION"; axi["action"] = "重组规则拓扑"
        else:
            axi["type"] = "OBSERVER_RECONFIG"; axi["action"] = "重构评估标准"
        return axi

    def stats(self) -> dict:
        return {"evolution_cycles": self.evolution_cycles, "axioms": len(self.axioms_generated),
                "latest_gs": self.gs_detector.score_history.get("gain",[])[-3:] if self.gs_detector.score_history.get("gain") else []}
