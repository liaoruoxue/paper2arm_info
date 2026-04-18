"""
trace_recorder.py — Python 装饰器，3 行代码为自定义 Agent 接入轨迹记录

用法：

    from trace_recorder import TraceRecorder

    recorder = TraceRecorder(
        challenge_id="dai-2019",
        challenge_domain="condensed_matter",
        model_id="claude-sonnet-4-6",
        agent_framework="custom-python",
    )

    # 方式一：手动记录
    recorder.start()
    recorder.record_user("请复现 Table 2 的结果")
    recorder.record_assistant("我来分析论文...", tool_calls=[...])
    recorder.record_tool("call_001", "[文件内容]")
    recorder.end(outcome_reward=0.8, result_fidelity="within_5pct")

    # 方式二：装饰器自动记录 LLM API 调用
    @recorder.trace
    def call_llm(messages):
        response = anthropic_client.messages.create(...)
        return response

    # 方式三：context manager
    with recorder.session():
        # ... 你的 Agent 逻辑 ...
        pass
    # session_end 自动写入
"""

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from functools import wraps
from contextlib import contextmanager


class TraceRecorder:
    """轻量轨迹记录器，输出 raw_messages.jsonl。"""

    def __init__(
        self,
        challenge_id: str,
        model_id: str,
        agent_framework: str = "custom-python",
        challenge_domain: str | None = None,
        output_dir: str | Path = "traces",
    ):
        self.challenge_id = challenge_id
        self.model_id = model_id
        self.agent_framework = agent_framework
        self.challenge_domain = challenge_domain
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self._file_path = self.output_dir / "raw_messages.jsonl"
        self._step_id = 0
        self._started = False
        self._total_tokens = 0
        self._start_time: float | None = None

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    def _append(self, record: dict) -> None:
        with open(self._file_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    def _next_step(self) -> int:
        self._step_id += 1
        return self._step_id

    # --- 核心 API ---

    def start(self) -> None:
        """写入 session_start。"""
        if self._started:
            raise RuntimeError("Session 已启动，不要重复调用 start()")
        self._started = True
        self._start_time = time.time()

        record: dict[str, Any] = {
            "type": "session_start",
            "challenge_id": self.challenge_id,
            "model_id": self.model_id,
            "agent_framework": self.agent_framework,
            "timestamp": self._now(),
        }
        if self.challenge_domain:
            record["challenge_domain"] = self.challenge_domain
        self._append(record)

    def record_user(self, content: str) -> int:
        """记录 user message。返回 step_id。"""
        sid = self._next_step()
        self._append({
            "type": "message",
            "step_id": sid,
            "role": "user",
            "content": content,
            "timestamp": self._now(),
        })
        return sid

    def record_assistant(
        self,
        content: str,
        tool_calls: list[dict] | None = None,
        human_edited: bool = False,
        decision_type: str | None = None,
        thinking_trace: str | None = None,
        tokens_used: int = 0,
    ) -> int:
        """记录 assistant message。返回 step_id。"""
        sid = self._next_step()
        self._total_tokens += tokens_used

        record: dict[str, Any] = {
            "type": "message",
            "step_id": sid,
            "role": "assistant",
            "content": content,
            "human_edited": human_edited,
            "timestamp": self._now(),
        }
        if tool_calls:
            record["tool_calls"] = tool_calls
        if decision_type:
            record["decision_type"] = decision_type
        if thinking_trace:
            record["thinking_trace"] = thinking_trace
        self._append(record)
        return sid

    def record_tool(self, tool_call_id: str, content: str) -> int:
        """记录 tool result。返回 step_id。"""
        sid = self._next_step()
        self._append({
            "type": "message",
            "step_id": sid,
            "role": "tool",
            "tool_call_id": tool_call_id,
            "content": content,
            "timestamp": self._now(),
        })
        return sid

    def end(
        self,
        outcome_reward: float,
        result_fidelity: str,
        total_tokens: int | None = None,
    ) -> None:
        """写入 session_end。"""
        if not self._started:
            raise RuntimeError("Session 未启动，先调用 start()")

        elapsed = time.time() - self._start_time if self._start_time else 0
        self._append({
            "type": "session_end",
            "outcome_reward": round(outcome_reward, 4),
            "result_fidelity": result_fidelity,
            "total_tokens": total_tokens or self._total_tokens,
            "total_time_s": round(elapsed),
            "timestamp": self._now(),
        })
        self._started = False

    # --- 便捷接口 ---

    @contextmanager
    def session(self):
        """Context manager：自动 start，退出时提示调用 end。

        用法：
            with recorder.session():
                recorder.record_user(...)
                recorder.record_assistant(...)
            # 注意：仍需手动调用 recorder.end()，因为 outcome_reward 需要外部计算
        """
        self.start()
        try:
            yield self
        except Exception:
            # 异常时也记录 session_end，reward=0
            self.end(outcome_reward=0.0, result_fidelity="no_match")
            raise

    def trace(self, func):
        """装饰器：自动记录被装饰函数的输入输出。

        适用于包装 LLM API 调用。

        用法：
            @recorder.trace
            def call_llm(messages):
                return client.messages.create(model="...", messages=messages)
        """
        @wraps(func)
        def wrapper(*args, **kwargs):
            result = func(*args, **kwargs)

            # 尝试从 Anthropic SDK response 中提取信息
            content = ""
            tokens = 0
            if hasattr(result, "content"):
                # Anthropic SDK response
                for block in result.content:
                    if hasattr(block, "text"):
                        content += block.text
                if hasattr(result, "usage"):
                    tokens = getattr(result.usage, "output_tokens", 0)

            if content:
                self.record_assistant(content, tokens_used=tokens)

            return result
        return wrapper
