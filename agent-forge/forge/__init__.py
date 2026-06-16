"""
Agent Forge —— 打造更强Agent
安全 + 记忆 + 能力放大
"""
from .shield import Shield
from .memory import Memory
from .core import CoreEngine


class AgentForge:
    """Agent锻造厂——一行代码增强任何Agent"""

    def __init__(self, agent_id: str = "default", model: str = "deepseek-v4-pro"):
        self.agent_id = agent_id
        self.shield = Shield(agent_id)
        self.memory = Memory(agent_id)
        self.core = CoreEngine(agent_id, model)

    def forge(self, task: str, context: dict = None) -> dict:
        """完整的Agent锻造流程: 安全→记忆→能力放大"""
        # 1. 安全检查
        shield_report = self.shield.wrap_agent(task, context)
        if not shield_report.all_clear:
            return {"status": "BLOCKED", "reason": f"安全检查未通过: {shield_report.threat_count}项威胁", "shield": shield_report}

        # 2. 记忆检索
        recalled = self.memory.recall(["L0", "L1", "L2"], limit=3)

        # 3. 能力放大
        baseline = len(task) / 100  # 简化的基线分
        result = self.core.amplify(task, baseline)

        # 4. 记录这次任务
        self.memory.remember(task, "L3", importance=min(0.9, baseline))

        return {
            "status": "FORGED",
            "agent_id": self.agent_id,
            "task": task[:100],
            "shield": {"passed": True, "threats": shield_report.threat_count},
            "memory_recalled": len(recalled),
            "amplify": {"baseline": result.original_score, "amplified": result.amplified_score, "gain": result.gain},
            "evolution_triggered": result.evolution_triggered,
        }

    def stats(self) -> dict:
        return {
            "shield": self.shield.stats(),
            "memory": self.memory.stats(),
            "core": self.core.stats(),
        }


__all__ = ["AgentForge", "Shield", "Memory", "CoreEngine"]
