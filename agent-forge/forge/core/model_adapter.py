"""
Forge Core 多模型适配器 —— 自动选择最佳模型
DeepSeek(最便宜)/Qwen(开源本地)/Claude(最强)/Gemini(长上下文)
"""
import os

MODEL_PRESETS = {
    "deepseek": {
        "name": "DeepSeek V4 Pro",
        "api_base": "https://api.deepseek.com",
        "strengths": ["coding", "reasoning", "cost"],
        "cost_per_1M_tokens": "$0.44/$0.87",
        "context_window": 1_000_000,
        "recommended_for": ["日常任务", "代码生成", "批量处理"]
    },
    "qwen": {
        "name": "Qwen3.6-35B",
        "api_base": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "strengths": ["opensource", "local", "agentic"],
        "cost_per_1M_tokens": "$0.35/$0.70",
        "context_window": 260_000,
        "recommended_for": ["隐私敏感", "本地部署", "离线任务"]
    },
    "claude": {
        "name": "Claude Opus 4.7",
        "api_base": "https://api.anthropic.com",
        "strengths": ["reasoning", "safety", "long_context"],
        "cost_per_1M_tokens": "$15/$75",
        "context_window": 1_000_000,
        "recommended_for": ["复杂推理", "长期记忆", "安全关键"]
    },
    "gemini": {
        "name": "Gemini 3.1 Pro",
        "api_base": "https://generativelanguage.googleapis.com",
        "strengths": ["multimodal", "long_context", "speed"],
        "cost_per_1M_tokens": "$5/$15",
        "context_window": 2_000_000,
        "recommended_for": ["多模态", "超长上下文", "实时响应"]
    }
}


class ModelAdapter:
    """自动选择最佳模型——用户不需要懂模型"""

    def __init__(self, default: str = "deepseek", api_keys: dict = None):
        self.default = default
        self.api_keys = api_keys or {}
        self.routing_history = []

    def route(self, task: str) -> str:
        """根据任务自动选模型"""
        task_lower = task.lower()
        # 规则路由
        if any(w in task_lower for w in ["设计","架构","重构","深度"]):
            return "claude"
        if any(w in task_lower for w in ["图片","视频","视觉","图像"]):
            return "gemini"
        if any(w in task_lower for w in ["隐私","本地","离线","内部"]):
            return "qwen"
        # 默认
        return self.default

    def get_preset(self, model_id: str = None) -> dict:
        return MODEL_PRESETS.get(model_id or self.default, MODEL_PRESETS["deepseek"])

    def list_models(self) -> dict:
        return {k: {"name": v["name"], "cost": v["cost_per_1M_tokens"], "best_for": v["recommended_for"]}
                for k, v in MODEL_PRESETS.items()}

    def get_config(self, model_id: str) -> dict:
        """返回可用的API配置——用户只需提供API key"""
        preset = self.get_preset(model_id)
        api_key = self.api_keys.get(model_id, os.environ.get(f"{model_id.upper()}_API_KEY", ""))
        return {"model": preset["name"], "api_base": preset["api_base"], "api_key": api_key,
                "context_window": preset["context_window"]}
