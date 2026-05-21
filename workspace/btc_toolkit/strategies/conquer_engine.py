"""
征服策略引擎
100 BTC总体路线图 → 分阶段执行计划
"""
from dataclasses import dataclass, field
from typing import List, Optional
from datetime import datetime, timedelta
import json
from pathlib import Path

from ..config import TARGET_BTC, ALLOCATION


@dataclass
class Milestone:
    btc_target: float
    phase: int
    name: str
    strategy: str
    eta: str
    status: str  # pending / active / completed


@dataclass
class ConquerState:
    total_btc: float = 0.0
    current_phase: int = 1
    start_date: str = ""
    milestones: List[Milestone] = field(default_factory=list)
    daily_log: List[dict] = field(default_factory=list)

    def progress_pct(self) -> float:
        return self.total_btc / TARGET_BTC * 100


class ConquerEngine:
    """征服引擎 — 100 BTC总指挥"""

    PHASES = [
        {
            "phase": 0,
            "name": "工具构建期",
            "btc_target": 0.01,
            "strategy": "搭建全套自动化工具、MCP接入、测试网验证",
            "eta": "1-2周",
            "actions": [
                "完成btc-toolkit核心模块",
                "接入Mempool MCP + Boar MCP",
                "测试网空投脚本验证",
                "GitHub部署(网络可用时)",
            ],
        },
        {
            "phase": 1,
            "name": "空投收割期",
            "btc_target": 1.0,
            "strategy": "多钱包空投交互 → 空投变现 → BTC累积",
            "eta": "1-3个月",
            "actions": [
                "创建50+钱包矩阵",
                "执行Beyond Protocol测试网交互",
                "执行Bitlayer积分任务",
                "Stacks DeFi协议交互",
                "空投变现→转入BTC",
            ],
        },
        {
            "phase": 2,
            "name": "套利加速期",
            "btc_target": 10.0,
            "strategy": "系统化链上套利 + Runes/Ordinals低买高卖",
            "eta": "3-6个月",
            "actions": [
                "启动跨市场套利扫描器(7x24)",
                "Runes低价mint+高价卖策略",
                "THORChain跨链套利",
                "BTC期货/现货基差套利",
                "利润再投资→复合增长",
            ],
        },
        {
            "phase": 3,
            "name": "产品变现期",
            "btc_target": 30.0,
            "strategy": "AI驱动的交易信号/数据分析产品 → BTC订阅收入",
            "eta": "6-12个月",
            "actions": [
                "发布链上数据分析SaaS",
                "交易信号Bot (Telegram/Discord)",
                "机构级套利API服务",
                "BTC计价订阅模式",
            ],
        },
        {
            "phase": 4,
            "name": "复合增长期",
            "btc_target": 70.0,
            "strategy": "多策略并行 + 量化交易 + 被动收入",
            "eta": "12-24个月",
            "actions": [
                "量化交易策略(CTA+网格+波动率)",
                "矿机投资(低价电力)",
                "BTC借贷/质押收益",
                "生态项目早期投资",
            ],
        },
        {
            "phase": 5,
            "name": "征服完成期",
            "btc_target": 100.0,
            "strategy": "稳定现金流 + 资产增值 → 达到100 BTC",
            "eta": "18-36个月",
            "actions": [
                "所有策略优化到最大产出",
                "BTC本位资产配置",
                "被动收入覆盖日常",
                "富贵的财富自由达成",
            ],
        },
    ]

    def __init__(self, state_dir: str = None):
        self.state_dir = Path(state_dir or "./conquer_state")
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.state = self._load_state()

    def _load_state(self) -> ConquerState:
        state_file = self.state_dir / "conquer.json"
        if state_file.exists():
            try:
                data = json.loads(state_file.read_text(encoding="utf-8"))
                return ConquerState(**data)
            except Exception:
                pass
        return ConquerState(
            total_btc=0.0,
            current_phase=0,
            start_date=datetime.now().isoformat(),
            milestones=[
                Milestone(
                    btc_target=p["btc_target"],
                    phase=p["phase"],
                    name=p["name"],
                    strategy=p["strategy"],
                    eta=p["eta"],
                    status="active" if p["phase"] == 0 else "pending",
                )
                for p in self.PHASES
            ],
        )

    def save_state(self):
        state_file = self.state_dir / "conquer.json"
        state_file.write_text(
            json.dumps(self.state.__dict__, indent=2, ensure_ascii=False, default=str),
            encoding="utf-8",
        )

    def get_current_phase(self) -> dict:
        return self.PHASES[self.state.current_phase]

    def get_next_actions(self) -> List[str]:
        phase = self.get_current_phase()
        return phase["actions"]

    def report(self) -> str:
        """生成状态报告"""
        phase = self.get_current_phase()
        progress = self.state.progress_pct()

        lines = [
            "=" * 60,
            "  极限实验室 — 100 BTC 征服报告",
            "=" * 60,
            f"",
            f"  进度: {self.state.total_btc:.4f} / {TARGET_BTC} BTC ({progress:.2f}%)",
            f"  当前阶段: Phase {self.state.current_phase} — {phase['name']}",
            f"  阶段目标: {phase['btc_target']} BTC",
            f"  策略: {phase['strategy']}",
            f"  预计时间: {phase['eta']}",
            f"",
            f"  📋 下一步行动:",
        ]
        for i, action in enumerate(phase["actions"], 1):
            lines.append(f"    {i}. {action}")

        lines.extend([
            "",
            f"  🛤️ 完整路线:",
        ])
        for m in self.state.milestones:
            icon = "✅" if m.status == "completed" else "🟢" if m.status == "active" else "⏳"
            lines.append(f"    {icon} Phase {m.phase}: {m.name} → {m.btc_target} BTC ({m.eta})")

        return "\n".join(lines)

    def log_progress(self, action: str, btc_earned: float = 0, notes: str = ""):
        """记录进度"""
        self.state.total_btc += btc_earned
        self.state.daily_log.append({
            "timestamp": datetime.now().isoformat(),
            "action": action,
            "btc_earned": btc_earned,
            "total_btc": self.state.total_btc,
            "notes": notes,
        })
        self.save_state()
