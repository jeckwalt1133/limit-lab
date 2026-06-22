"""
Agent Runner —— 自主Agent运行时
工具选择+执行+学习 = 完整自主循环
"""
import json, os, time, random
from datetime import datetime

class AgentRunner:
    """自主Agent——自己选工具、执行、学习"""

    def __init__(self, agent_id: str, tool_registry, memory=None, shield=None):
        self.agent_id = agent_id
        self.tools = tool_registry
        self.memory = memory
        self.shield = shield
        self.history = []
        self.session_start = datetime.now().isoformat()

    def decide_and_act(self, context: dict = None) -> dict:
        """根据上下文自主决策——选工具→安全检查→执行→记忆→学习"""
        # 1. 根据上下文选工具
        tool_name = self._select_tool(context)

        # 2. 安全检查
        if self.shield:
            report = self.shield.wrap_agent(f"执行工具: {tool_name}")
            if not report.all_clear:
                return {"status": "BLOCKED", "tool": tool_name, "reason": f"安全: {report.threat_count}威胁"}

        # 3. 执行
        start = time.time()
        try:
            result = self.tools.run(tool_name)
            status = "completed"
        except Exception as e:
            result = {"error": str(e)}
            status = "failed"

        elapsed = round(time.time() - start, 2)

        # 4. 记录
        record = {"tool": tool_name, "status": status, "elapsed": elapsed,
                  "timestamp": datetime.now().isoformat(), "result_preview": str(result)[:200]}
        self.history.append(record)

        # 5. 记忆存储（如果有）
        if self.memory:
            self.memory.remember(f"执行{tool_name}: {status}", "L3", 0.3)

        # 6. 学习——调整工具选择偏好
        self._learn(tool_name, status, elapsed)

        return {"status": status, "tool": tool_name, "result": result, "elapsed": elapsed,
                "history_count": len(self.history)}

    def run_pipeline(self, task: str) -> dict:
        """单指令交付——用户给任务→多工具协调→完成"""
        steps = []
        # 根据任务类型选择工具链
        if any(w in task for w in ["安全","攻击","危险","防护"]):
            tool_chain = ["security_scan", "integrity_check", "ids_scan"]
        elif any(w in task for w in ["记忆","遗忘","回忆","复习"]):
            tool_chain = ["forgetting_check", "memory_replay", "context_compress"]
        elif any(w in task for w in ["进化","优化","改进","学习"]):
            tool_chain = ["esv_tracker", "convergence_detect", "auto_ge_engine", "lifecycle_manager"]
        else:
            tool_chain = ["task_router", "continuous_perf", "noise_injector"]

        for tool_name in tool_chain:
            r = self.decide_and_act({"task": task, "chain": tool_chain, "step": len(steps)})
            steps.append(r)

        return {"task": task[:100], "steps": len(steps),
                "completed": sum(1 for s in steps if s["status"] == "completed"),
                "failed": sum(1 for s in steps if s["status"] == "failed"),
                "elapsed_total": round(sum(s.get("elapsed", 0) for s in steps), 2)}

    def stats(self) -> dict:
        total = len(self.history)
        if total == 0: return {"total_runs": 0}
        completed = sum(1 for h in self.history if h["status"] == "completed")
        tools_used = list(set(h["tool"] for h in self.history))
        return {"total_runs": total, "completed": completed, "failed": total - completed,
                "tools_used": len(tools_used), "avg_elapsed": round(sum(h["elapsed"] for h in self.history)/total, 3)}

    def _select_tool(self, context: dict = None) -> str:
        """根据上下文智能选工具"""
        # 根据最近使用的工具，避免重复
        recent = [h["tool"] for h in self.history[-5:]]
        available = [name for name in self.tools.tools if name not in recent]
        if not available:
            available = list(self.tools.tools.keys())
        # 根据上下文类型优先
        task = (context or {}).get("task", "")
        chain = (context or {}).get("chain", [])
        if chain:
            next_tool = chain[(context or {}).get("step", 0)] if (context or {}).get("step", 0) < len(chain) else random.choice(available)
            return next_tool
        return random.choice(available)

    def _learn(self, tool_name: str, status: str, elapsed: float):
        """从每次执行中学习——调整工具偏好"""
        # 简化：记录成功/失败的工具，后续优先选成功的
        pass  # 生产环境：更新工具评分表
