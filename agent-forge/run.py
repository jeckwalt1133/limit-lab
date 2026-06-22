"""Agent Forge 一键启动——CLI/Telegram双模式"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from forge.core.tools import create_default_registry
from forge.core.agent_runner import AgentRunner
from forge.shield.shield import Shield
from forge.memory.memory import Memory

def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "cli"
    base = os.path.dirname(os.path.abspath(__file__))

    # 创建核心组件
    reg = create_default_registry(base)
    shield = Shield("agent-forge-main")
    memory = Memory("agent-forge-main", os.path.join(base, "forge_memory"))
    agent = AgentRunner("agent-forge-main", reg, memory, shield)

    if mode == "telegram":
        token = os.environ.get("TELEGRAM_BOT_TOKEN") or sys.argv[2] if len(sys.argv)>2 else input("Bot Token: ")
        from forge.core.telegram_bot import TelegramBot
        bot = TelegramBot(token, agent)
        print(f"🤖 Agent Forge Telegram Bot 启动中...")
        bot.start()
        print("✅ 已启动。发送 /start 开始使用")
        try:
            while True: time.sleep(1)
        except KeyboardInterrupt:
            bot.stop()
            print("已停止")

    else:
        print(f"🤖 Agent Forge v0.2 · {len(reg.tools)}工具就绪")
        if len(sys.argv) > 2:
            task = " ".join(sys.argv[2:])
            r = agent.run_pipeline(task)
            print(f"✅ {r['steps']}步, 成功{r['completed']}/失败{r['failed']}")
        else:
            print("命令: python run.py [telegram] [任务描述]")

if __name__ == "__main__":
    import time
    main()
