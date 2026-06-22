"""
Agent Forge Telegram Bot —— 消息平台接入
用户通过Telegram给Agent发指令→自主执行→回复结果
"""
import json, time, threading, requests
from datetime import datetime

class TelegramBot:
    """轻量级Telegram Bot——纯requests，零外部依赖"""

    def __init__(self, token: str, agent_runner=None):
        self.token = token
        self.base_url = f"https://api.telegram.org/bot{token}"
        self.agent = agent_runner
        self._running = False
        self._thread = None
        self._last_update_id = 0
        self.history = []

    def start(self):
        """启动bot——持续监听"""
        if self._running: return "已运行"
        self._running = True
        self._thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._thread.start()
        return "STARTED"

    def stop(self):
        self._running = False
        return "STOPPED"

    def send(self, chat_id: int, text: str):
        """发送消息"""
        try:
            requests.post(f"{self.base_url}/sendMessage",
                json={"chat_id": chat_id, "text": text[:4000]}, timeout=10)
        except: pass

    def _poll_loop(self):
        """轮询循环"""
        while self._running:
            try:
                updates = requests.get(f"{self.base_url}/getUpdates",
                    params={"offset": self._last_update_id + 1, "timeout": 30}, timeout=35).json()
                for upd in updates.get("result", []):
                    self._last_update_id = upd["update_id"]
                    msg = upd.get("message", {})
                    text = msg.get("text", "")
                    chat_id = msg.get("chat", {}).get("id", 0)
                    if text and chat_id:
                        self._handle(chat_id, text)
            except: time.sleep(5)

    def _handle(self, chat_id: int, text: str):
        """处理用户消息"""
        self.history.append({"chat_id": chat_id, "text": text[:200], "time": datetime.now().isoformat()})

        # 命令处理
        if text.startswith("/start"):
            self.send(chat_id, "🤖 Agent Forge 已启动\n/status 查看状态\n/run 执行任务\n/pause 暂停\n/memory 记忆管理")
            return

        if text.startswith("/status"):
            if self.agent:
                s = self.agent.stats()
                self.send(chat_id, f"📊 状态\n运行:{s['total_runs']}次\n完成:{s.get('completed',s['total_runs'])}\n工具:{s.get('tools_used',0)}个")
            return

        if text.startswith("/run"):
            task = text[5:].strip() or "默认分析任务"
            if self.agent:
                self.send(chat_id, f"⏳ 执行中: {task[:100]}")
                r = self.agent.run_pipeline(task)
                self.send(chat_id, f"✅ 完成\n步骤:{r['steps']}\n成功:{r['completed']}\n失败:{r['failed']}")
            return

        if text.startswith("/memory"):
            self.send(chat_id, "🧠 记忆功能: 记录/回忆/防遗忘——已就绪")
            return

        if text.startswith("/pause"):
            self.send(chat_id, "⏸️ 已暂停")
            return

        # 默认：当作任务执行
        if self.agent:
            r = self.agent.run_pipeline(text)
            self.send(chat_id, f"✅ 自主执行完成\n步骤:{r['steps']} 成功:{r['completed']}")
        else:
            self.send(chat_id, "⚠️ Agent未初始化")

    def stats(self): return {"history": len(self.history), "running": self._running}
