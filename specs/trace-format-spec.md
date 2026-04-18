# ARM 轨迹格式规范 v1.0

> 本规范定义 Paper2ARM Hackathon 提交中 `traces/raw_messages.jsonl` 的格式要求。
> 目标：确保 Hackathon 产出的轨迹数据能被未来的 SFT / GRPO / DPO / CURE 等多种 RL 训练方法直接使用。

---

## 1. 概述

每个 ARM 提交包（zip bundle）的 `traces/` 目录中必须包含一个 `raw_messages.jsonl` 文件，记录完整的 Agent-工具交互序列。

```
arm_submission/
├── arm_manifest.json
├── code/
├── results/
└── traces/
    ├── raw_messages.jsonl    ← 本规范定义的文件（必须）
    └── ears/                  ← EARS 经验提炼（可选，继续保留）
```

**设计原则：别在收集阶段做训练阶段的决定。** 记录一切，让训练管线选择用什么。

---

## 2. 文件格式

JSONL（每行一个 JSON 对象），UTF-8 编码。三种记录类型：

### 2.1 session_start（第一行）

```json
{
  "type": "session_start",
  "challenge_id": "dai-2019",
  "challenge_domain": "condensed_matter",
  "model_id": "claude-sonnet-4-6",
  "agent_framework": "claude-code",
  "timestamp": "2026-04-17T13:00:00Z"
}
```

| 字段 | 必须 | 说明 |
|------|:---:|------|
| type | ✅ | 固定 `"session_start"` |
| challenge_id | ✅ | 题目唯一标识，从题目描述中获取 |
| challenge_domain | 建议 | 领域标签，从题目描述中获取（见 challenge-metadata-template.yaml） |
| model_id | ✅ | 使用的模型标识 |
| agent_framework | ✅ | `"claude-code"` / `"openclaw"` / `"custom-python"` / 其他 |
| timestamp | ✅ | ISO 8601 格式 |

### 2.2 message（中间行，可重复）

```json
{
  "type": "message",
  "step_id": 1,
  "role": "user",
  "content": "请复现 Table 2 的结果...",
  "timestamp": "2026-04-17T13:00:05Z"
}
```

```json
{
  "type": "message",
  "step_id": 2,
  "role": "assistant",
  "content": "我来分析论文的方法...",
  "tool_calls": [
    {
      "name": "read_file",
      "args": {"path": "paper.pdf"},
      "call_id": "call_001"
    }
  ],
  "human_edited": false,
  "decision_type": "method_selection",
  "thinking_trace": "...",
  "timestamp": "2026-04-17T13:00:12Z"
}
```

```json
{
  "type": "message",
  "step_id": 3,
  "role": "tool",
  "tool_call_id": "call_001",
  "content": "[文件内容或工具输出]",
  "timestamp": "2026-04-17T13:00:15Z"
}
```

| 字段 | 必须 | 说明 |
|------|:---:|------|
| type | ✅ | 固定 `"message"` |
| step_id | ✅ | 自增序号，从 1 开始。用于事后步骤级标注（Math-Shepherd 方法） |
| role | ✅ | `"user"` / `"assistant"` / `"tool"` |
| content | ✅ | 消息内容 |
| timestamp | ✅ | ISO 8601 格式 |
| tool_calls | 条件 | assistant 调用工具时必须有。数组，每个元素含 name, args, call_id |
| tool_call_id | 条件 | role=tool 时必须有，对应 tool_calls 中的 call_id |
| human_edited | 建议 | `true`/`false`，区分人工干预和 Agent 自主。RL 训练只用 `false` 的步骤 |
| decision_type | 可选 | 关键决策节点标记：`"method_selection"` / `"parameter_choice"` / `"tool_selection"` / `"diagnosis"` |
| thinking_trace | 可选 | 模型的 extended thinking 内容（如果有） |

### 2.3 session_end（最后一行）

```json
{
  "type": "session_end",
  "outcome_reward": 0.8,
  "result_fidelity": "within_5pct",
  "total_tokens": 45000,
  "total_time_s": 3600,
  "timestamp": "2026-04-17T14:00:00Z"
}
```

| 字段 | 必须 | 说明 |
|------|:---:|------|
| type | ✅ | 固定 `"session_end"` |
| outcome_reward | ✅ | 0-1 标量，由评测系统自动计算（见 compute_reward.py），**不要手填** |
| result_fidelity | ✅ | ARM 六维评分结果 |
| total_tokens | 建议 | 总 token 消耗 |
| total_time_s | 建议 | 总耗时（秒） |
| timestamp | ✅ | ISO 8601 格式 |

---

## 3. step_id 的重要性

GRPO+PRM（当前最有效的训练方法）需要每步独立 reward。训练管线用 Math-Shepherd 方法事后自动标注：

1. 截取前 N 步作为前缀
2. 用模型从第 N 步补全到结束
3. 看补全能否到达正确答案
4. 统计正确率 → 得到该步骤的 SE（软估计）/ HE（硬估计）分数

step_id 让训练管线能精确定位每一步的边界。没有 step_id，只能靠 timestamp 推断，容易有歧义。

**参赛者不需要标注 step_reward，只需要保证 step_id 连续递增。** trace-recorder 工具会自动处理。

---

## 4. 不要求的字段

| 字段 | 为什么不要求 |
|------|------------|
| token_id | 多模型多框架，tokenizer 不同，不可比。训练时由训练管线统一 re-tokenize |
| step_reward | 训练管线事后用 Math-Shepherd 自动标注，不需要人工 |
| 压缩/摘要 | 记录完整内容，不做任何压缩。磁盘便宜，信息丢了补不回来 |

---

## 5. 校验规则

一个合法的 `raw_messages.jsonl` 必须满足：

1. 第一行是 `session_start`，最后一行是 `session_end`
2. 中间全部是 `message`
3. step_id 从 1 开始连续递增，无跳跃无重复
4. 每个 `tool_call_id`（role=tool）都能找到对应的 `tool_calls` 条目（role=assistant）
5. session_start 中 challenge_id 和 model_id 非空
6. session_end 中 outcome_reward 在 [0, 1] 范围内
7. 所有 timestamp 是合法的 ISO 8601 格式

校验脚本见 `tools/validate_trace.py`（TODO）。

---

## 6. 关于失败轨迹

**所有尝试都必须提交，不管成功还是失败。**

失败轨迹（outcome_reward < 阈值）对训练同等重要：
- GRPO 需要好坏对比才能学习（组内归一化）
- DPO 需要偏好对（好 vs 差）
- CURE 用失败轨迹训练 tester
- ExGRPO 需要历史轨迹池

只保留成功轨迹 = 退化成 SFT（不区分好坏），60% 的训练方法无法使用。

---

## 7. 完整示例

```jsonl
{"type":"session_start","challenge_id":"dai-2019","challenge_domain":"condensed_matter","model_id":"claude-sonnet-4-6","agent_framework":"claude-code","timestamp":"2026-04-17T13:00:00Z"}
{"type":"message","step_id":1,"role":"user","content":"请复现 Dai et al. 2019 Table 2 中 La2CuO4 的带隙计算结果","timestamp":"2026-04-17T13:00:05Z"}
{"type":"message","step_id":2,"role":"assistant","content":"我来分析论文的计算方法。首先读取论文确认使用的计算参数。","tool_calls":[{"name":"read_file","args":{"path":"paper.pdf"},"call_id":"call_001"}],"human_edited":false,"decision_type":"method_selection","timestamp":"2026-04-17T13:00:12Z"}
{"type":"message","step_id":3,"role":"tool","tool_call_id":"call_001","content":"[论文内容：使用 VASP 6.3，PBE+U 泛函，U=7.5 eV，能量截断 520 eV...]","timestamp":"2026-04-17T13:00:15Z"}
{"type":"message","step_id":4,"role":"assistant","content":"论文使用 DFT+U 方法。我需要准备 VASP 输入文件：INCAR, POSCAR, KPOINTS, POTCAR。","tool_calls":[{"name":"bash","args":{"command":"python generate_inputs.py --functional PBE+U --u_value 7.5 --encut 520"},"call_id":"call_002"}],"human_edited":false,"decision_type":"parameter_choice","timestamp":"2026-04-17T13:00:30Z"}
{"type":"message","step_id":5,"role":"tool","tool_call_id":"call_002","content":"VASP 输入文件已生成：INCAR, POSCAR, KPOINTS, POTCAR","timestamp":"2026-04-17T13:00:35Z"}
{"type":"message","step_id":6,"role":"assistant","content":"输入文件已就绪，提交 VASP 计算。","tool_calls":[{"name":"bash","args":{"command":"sbatch vasp_job.sh"},"call_id":"call_003"}],"human_edited":false,"decision_type":"tool_selection","timestamp":"2026-04-17T13:01:00Z"}
{"type":"message","step_id":7,"role":"tool","tool_call_id":"call_003","content":"Job submitted: job_id=12345","timestamp":"2026-04-17T13:01:05Z"}
{"type":"message","step_id":8,"role":"assistant","content":"计算完成。提取带隙值并与论文 Table 2 对比。","tool_calls":[{"name":"bash","args":{"command":"python extract_bandgap.py OUTCAR"},"call_id":"call_004"}],"human_edited":false,"decision_type":"diagnosis","timestamp":"2026-04-17T13:45:00Z"}
{"type":"message","step_id":9,"role":"tool","tool_call_id":"call_004","content":"计算带隙: 1.82 eV\n论文值: 1.85 eV\n偏差: 1.6%","timestamp":"2026-04-17T13:45:05Z"}
{"type":"message","step_id":10,"role":"assistant","content":"计算结果与论文 Table 2 吻合（偏差 1.6%，在 5% 容差内）。复现成功。","human_edited":false,"timestamp":"2026-04-17T13:45:30Z"}
{"type":"session_end","outcome_reward":0.8,"result_fidelity":"within_5pct","total_tokens":32000,"total_time_s":2730,"timestamp":"2026-04-17T13:45:35Z"}
```
