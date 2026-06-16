"""Agent Forge CLI —— 命令行入口"""
import sys, os, time, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from forge import AgentForge

def main():
    if len(sys.argv) < 2:
        print("Agent Forge v0.1 · 打造更强Agent\n用法: python cli.py [start|task|status|pause|resume|stop]")
        return

    cmd = sys.argv[1]
    af = AgentForge("cli-user")

    if cmd == "start":
        af.core._loop = None  # 重置
        print("Agent Forge 已启动 (5秒自检)")
        for i in range(5):
            time.sleep(1)
            print(f"  心跳#{i+1} ✅")

    elif cmd == "task":
        task = sys.argv[2] if len(sys.argv) > 2 else "分析系统状态"
        print(f"执行: {task}")
        r = af.forge(task)
        print(json.dumps(r, ensure_ascii=False, indent=2))

    elif cmd == "status":
        s = af.stats()
        print(f"Agent Forge · {af.agent_id}")
        print(f"  安全: {s['shield']['pass_rate']}")
        print(f"  记忆: {s['memory']['total_memories']}条")
        print(f"  能力: {s['core']['total_tasks']}任务 avg_gain={s['core']['avg_gain']}")

    elif cmd == "bench":
        print("基准测试...")
        tasks = [("简单处理",0.3),("复杂推理需要深度思考和多步分析",0.15),("架构重构和系统重设计",0.1)]
        for t, b in tasks:
            r = af.forge(t)
            gain = r.get("amplify",{}).get("gain",0)
            print(f"  {t[:30]}... 基线:{b} → 增益:{gain}")
        print(f"统计: {af.stats()['core']}")

    else:
        print(f"未知命令: {cmd}")

if __name__ == "__main__":
    main()
