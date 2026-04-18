name: trace-recorder
description: 自动记录 Agent 交互轨迹到 raw_messages.jsonl，用于后续 RL 训练。无脑记每一步，参赛者零负担。
---

# Trace Recorder — ARM 轨迹自动记录

在 Claude Code 中自动记录完整的 Agent-工具交互序列到 `traces/raw_messages.jsonl`。

## 前置条件

当前目录下有 `arm_manifest.json`（包含 challenge_id）。

## 使用方式

在 Claude Code session 开始时执行：

```
/trace-recorder start
```

之后所有工具调用自动记录。session 结束时执行：

```
/trace-recorder stop
```

自动写入 session_end（outcome_reward 从 ARM result_fidelity 计算）。

## 实现说明

### Hooks 配置

trace-recorder 通过 Claude Code Hooks 自动记录，需要在 `.claude/settings.json` 中配置：

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "command": "python3 ~/.claude/skills/trace-recorder/record_step.py PostToolUse \"$TOOL_NAME\" \"$TOOL_RESULT\"",
        "description": "记录工具调用到 raw_messages.jsonl"
      }
    ],
    "SessionStart": [
      {
        "command": "python3 ~/.claude/skills/trace-recorder/record_step.py SessionStart",
        "description": "写入 session_start"
      }
    ],
    "SessionEnd": [
      {
        "command": "python3 ~/.claude/skills/trace-recorder/record_step.py SessionEnd",
        "description": "写入 session_end"
      }
    ]
  }
}
```

### record_step.py 核心逻辑

```python
#!/usr/bin/env python3
"""Hook 入口：根据事件类型追加一行到 raw_messages.jsonl"""

import sys
import json
import os
from datetime import datetime, timezone
from pathlib import Path

TRACE_FILE = Path("traces/raw_messages.jsonl")
STEP_COUNTER_FILE = Path("traces/.step_counter")


def now():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def next_step_id():
    """读取并递增 step_id 计数器。"""
    counter_file = STEP_COUNTER_FILE
    if counter_file.exists():
        step = int(counter_file.read_text().strip()) + 1
    else:
        step = 1
    counter_file.write_text(str(step))
    return step


def read_manifest():
    """从 arm_manifest.json 读取 challenge 信息。"""
    manifest_path = Path("arm_manifest.json")
    if not manifest_path.exists():
        return {}
    return json.loads(manifest_path.read_text())


def append(record):
    TRACE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(TRACE_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def handle_session_start():
    manifest = read_manifest()
    STEP_COUNTER_FILE.parent.mkdir(parents=True, exist_ok=True)
    STEP_COUNTER_FILE.write_text("0")
    append({
        "type": "session_start",
        "challenge_id": manifest.get("challenge_id", "unknown"),
        "challenge_domain": manifest.get("challenge_domain", ""),
        "model_id": os.environ.get("CLAUDE_MODEL", "unknown"),
        "agent_framework": "claude-code",
        "timestamp": now(),
    })


def handle_post_tool_use(tool_name, tool_result):
    # assistant 的工具调用
    sid = next_step_id()
    append({
        "type": "message",
        "step_id": sid,
        "role": "assistant",
        "content": "",
        "tool_calls": [{"name": tool_name, "args": {}, "call_id": f"call_{sid:04d}"}],
        "human_edited": False,
        "timestamp": now(),
    })
    # tool 的返回结果
    sid2 = next_step_id()
    # 截断过长的 tool result（保留前后各 2000 字符）
    if len(tool_result) > 5000:
        tool_result = tool_result[:2000] + "\n...[truncated]...\n" + tool_result[-2000:]
    append({
        "type": "message",
        "step_id": sid2,
        "role": "tool",
        "tool_call_id": f"call_{sid:04d}",
        "content": tool_result,
        "timestamp": now(),
    })


def handle_session_end():
    manifest = read_manifest()
    fidelity = manifest.get("result_fidelity", "no_match")
    # 简化版 reward 计算
    reward_map = {
        "exact_match": 1.0, "within_1pct": 0.9, "within_5pct": 0.8,
        "within_10pct": 0.6, "within_20pct": 0.5, "partial_match": 0.3,
        "trend_correct": 0.2, "no_match": 0.0,
    }
    append({
        "type": "session_end",
        "outcome_reward": reward_map.get(fidelity, 0.0),
        "result_fidelity": fidelity,
        "timestamp": now(),
    })


if __name__ == "__main__":
    event = sys.argv[1] if len(sys.argv) > 1 else ""
    if event == "SessionStart":
        handle_session_start()
    elif event == "PostToolUse":
        tool_name = sys.argv[2] if len(sys.argv) > 2 else "unknown"
        tool_result = sys.argv[3] if len(sys.argv) > 3 else ""
        handle_post_tool_use(tool_name, tool_result)
    elif event == "SessionEnd":
        handle_session_end()
```

### 与 EARS 的关系

两者互补，不替代：

```
EARS：提炼经验 → pitfalls.yaml / unknowns.yaml → 给 Agent 的 prompt 用 → prompt 级改进
trace-recorder：记录原始轨迹 → raw_messages.jsonl → 给训练管线用 → weight 级改进
```

trace-recorder 比 EARS 简单得多：EARS 需要判断"是不是有价值的学习时刻"，trace-recorder 只需要无脑记每一步。
