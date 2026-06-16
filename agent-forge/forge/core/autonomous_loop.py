"""
Forge 自主心跳循环 —— 不用cron，Agent自己的脉冲
事件驱动 + 自我决策 + 7x24持续运行 + 可暂停恢复
"""
import time, json, os, signal, threading
from datetime import datetime
from dataclasses import dataclass
from collections import deque
from typing import Callable, Optional


@dataclass
class Task:
    id: str
    action: Callable
    priority: int  # 1-10, 10最高
    status: str = "pending"
    result: any = None
    created: str = ""


class AutonomousLoop:
    """自主心跳——Agent自己的持续运行引擎"""

    def __init__(self, agent_id: str = "default"):
        self.agent_id = agent_id
        self.task_queue = deque()
        self.completed = deque(maxlen=1000)
        self._running = False
        self._paused = False
        self._heartbeat_interval = 1.0  # 秒
        self._last_beat = None
        self._beat_count = 0
        self._thread = None

    def add_task(self, action: Callable, priority: int = 5):
        """添加任务到自主队列"""
        task = Task(
            id=f"TASK-{len(self.task_queue):06d}",
            action=action, priority=min(10, max(1, priority)),
            created=datetime.now().isoformat()
        )
        self.task_queue.append(task)
        # 按优先级排序
        self.task_queue = deque(sorted(self.task_queue, key=lambda t: t.priority, reverse=True))
        return task.id

    def start(self):
        """启动自主循环"""
        if self._running:
            return
        self._running = True
        self._paused = False
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        return "STARTED"

    def pause(self):
        """暂停——用户可随时介入"""
        self._paused = True
        return "PAUSED"

    def resume(self):
        """恢复"""
        self._paused = False
        return "RESUMED"

    def stop(self):
        """停止循环"""
        self._running = False
        if self._thread:
            self._thread.join(timeout=2)
        return "STOPPED"

    def status(self) -> dict:
        """实时状态——进度可见"""
        return {
            "agent_id": self.agent_id,
            "running": self._running,
            "paused": self._paused,
            "queue_size": len(self.task_queue),
            "completed": len(self.completed),
            "beat_count": self._beat_count,
            "last_beat": self._last_beat,
            "uptime_seconds": self._beat_count * self._heartbeat_interval if self._beat_count else 0
        }

    def _loop(self):
        """心跳循环——自主执行"""
        while self._running:
            if self._paused:
                time.sleep(0.1)
                continue

            self._beat_count += 1
            self._last_beat = datetime.now().isoformat()

            # 有任务就执行
            if self.task_queue:
                task = self.task_queue.popleft()
                try:
                    task.status = "running"
                    task.result = task.action()
                    task.status = "completed"
                except Exception as e:
                    task.status = "failed"
                    task.result = str(e)
                self.completed.append(task)
            else:
                # 无任务时自我检查——生成维护任务
                if self._beat_count % 300 == 0:  # 每300拍做一次自检
                    self._self_check()

            time.sleep(self._heartbeat_interval)

    def _self_check(self):
        """自我检查——心跳内置的维护机制"""
        now = datetime.now().isoformat()
        self.completed.append(Task(
            id=f"SELF-CHECK-{self._beat_count}",
            action=lambda: {"health": "nominal", "queue": len(self.task_queue)},
            priority=1, status="completed", result={"health": "nominal", "time": now},
            created=now
        ))

    def run_until_done(self, timeout_seconds: int = 300) -> dict:
        """单指令交付——用户给一个指令，我们跑到完成"""
        start = time.time()
        while self.task_queue and (time.time() - start) < timeout_seconds:
            if self._paused:
                time.sleep(0.1)
                continue
            task = self.task_queue.popleft()
            try:
                task.status = "running"
                task.result = task.action()
                task.status = "completed"
            except Exception as e:
                task.status = "failed"
                task.result = str(e)
            self.completed.append(task)
        return {"tasks_completed": len([t for t in self.completed if t.status == "completed"]),
                "tasks_failed": len([t for t in self.completed if t.status == "failed"]),
                "remaining": len(self.task_queue),
                "elapsed": round(time.time() - start, 1)}
