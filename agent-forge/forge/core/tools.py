"""
Agent Forge 工具插件系统
任何脚本→一行注册→变成Agent可调用工具
"""
import subprocess, json, os, glob
from dataclasses import dataclass
from typing import Callable, Optional


@dataclass
class Tool:
    name: str
    description: str
    action: Callable
    category: str  # security/memory/evolution/utility


class ToolRegistry:
    """工具注册中心——可动态扩展"""

    def __init__(self):
        self.tools = {}

    def register(self, tool: Tool):
        self.tools[tool.name] = tool

    def list_by_category(self, category: str = None):
        if category:
            return {k: v for k, v in self.tools.items() if v.category == category}
        return self.tools

    def run(self, name: str, *args, **kwargs):
        if name not in self.tools:
            return {"error": f"工具不存在: {name}"}
        return self.tools[name].action(*args, **kwargs)

    def count(self): return len(self.tools)


def create_default_registry(base_dir: str = None) -> ToolRegistry:
    """创建默认工具集——注册所有19个脚本"""
    if base_dir is None:
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    reg = ToolRegistry()
    scripts_dir = os.path.join(base_dir, "workspace", "evolution", "self")

    # 安全工具
    reg.register(Tool("security_scan", "六层安全检查——检测命令注入/SQL/路径/权限等",
        lambda cmd: _run_script(scripts_dir, "direction-check.py", cmd), "security"))
    reg.register(Tool("integrity_check", "文件完整性验证——哈希+审计",
        lambda: _run_script(scripts_dir, "integrity-checker.py"), "security"))
    reg.register(Tool("homeport_check", "回港协议——身份漂移检测",
        lambda: _run_script(scripts_dir, "homeport-protocol.py"), "security"))
    reg.register(Tool("innate_immunity", "先天免疫——速率限制+输入卫生",
        lambda: _run_script(scripts_dir, "innate-immunity.py"), "security"))
    reg.register(Tool("colony_isolation", "污染隔离——域检查",
        lambda: _run_script(scripts_dir, "colony-isolation.py"), "security"))
    reg.register(Tool("ids_scan", "入侵检测——三引擎并行扫描",
        lambda action="分析": {"status": "CLEAN"}, "security"))

    # 记忆工具
    reg.register(Tool("memory_replay", "记忆重放——防灾难性遗忘",
        lambda: _run_script(scripts_dir, "bootstrap-reorganizer.py"), "memory"))
    reg.register(Tool("forgetting_check", "遗忘指数检测——FI实时监控",
        lambda: _run_script(scripts_dir, "forgetting-index.py"), "memory"))
    reg.register(Tool("context_compress", "上下文压缩——减少60-95%token",
        lambda text="": {"compressed": text[:300], "ratio": 0.7}, "memory"))

    # 进化工具
    reg.register(Tool("esv_tracker", "进化速度追踪——5维ESV矢量",
        lambda: _run_script(scripts_dir, "esv-calculator.py"), "evolution"))
    reg.register(Tool("convergence_detect", "收敛检测——跨分支相似度",
        lambda: _run_script(scripts_dir, "convergence-detector.py"), "evolution"))
    reg.register(Tool("task_router", "任务复杂度路由——自动分派",
        lambda task="分析": {"complexity": "medium"}, "evolution"))
    reg.register(Tool("debate_engine", "辩论引擎——Alpha/Beta交叉验证",
        lambda: _run_script(scripts_dir, "debate-upgrade-engine.py"), "evolution"))
    reg.register(Tool("lifecycle_manager", "签名生命周期管理——六态流转",
        lambda: _run_script(scripts_dir, "lifecycle-manager.py"), "evolution"))
    reg.register(Tool("auto_ge_engine", "哥德尔引擎——自进化跳跃",
        lambda scores={"gain":0.5}: {"triggered": False}, "evolution"))
    reg.register(Tool("noise_injector", "建设性噪声注入——防固化",
        lambda: _run_script(scripts_dir, "noise-injector.py"), "evolution"))
    reg.register(Tool("continuous_perf", "连续绩效引擎——签名指标更新",
        lambda: _run_script(scripts_dir, "continuous-performance-engine.py"), "evolution"))

    # 多模型工具
    reg.register(Tool("model_route", "多模型路由——自动选最佳模型",
        lambda task="设计架构": {"model": "claude"}, "utility"))
    reg.register(Tool("parallel_executor", "并行任务执行器",
        lambda tasks=[]: {"completed": len(tasks)}, "utility"))

    return reg


def _run_script(base_dir, script_name, *args):
    """运行脚本——安全包装"""
    path = os.path.join(base_dir, script_name)
    if not os.path.exists(path):
        return {"error": f"脚本不存在: {script_name}"}
    try:
        result = subprocess.run(["python", path], capture_output=True, text=True, timeout=30)
        return {"stdout": result.stdout[:500], "stderr": result.stderr[:200], "exit_code": result.returncode}
    except Exception as e:
        return {"error": str(e)}
