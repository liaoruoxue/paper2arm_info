# Paper2ARM 训练数据准备

给天汉的一站式参考：确保每次 Hackathon 产出的轨迹数据都能被未来 RL 训练用起来。

---

## 目录

```
paper2arm_info/
├── README.md                                ← 你在看的文件
├── specs/
│   ├── trace-format-spec.md                 ← ARM 轨迹格式规范（raw_messages.jsonl 完整定义）
│   └── challenge-metadata-template.yaml     ← 出题时的元数据模板（challenge_id + domain）
└── tools/
    ├── compute_reward.py                    ← outcome_reward 自动计算（从 result_fidelity → 0-1）
    ├── trace_recorder.py                    ← Python 装饰器（自定义 Agent 用户 3 行接入）
    └── trace_recorder_skill/
        └── SKILL.md                         ← Claude Code skill（Hooks 自动记录）
```

---

## 下一次 Hackathon 之前必须完成的 5 件事

### ① ARM 规范发布

**文件**：`specs/trace-format-spec.md`（已写好）

每个 ARM 提交包的 `traces/` 目录必须包含 `raw_messages.jsonl`。规范定义了完整的字段要求、校验规则和示例。在 Hackathon 启动前发布给参赛者。

### ② 三平台 trace-recorder 工具

**文件**：`tools/trace_recorder.py`（Python 装饰器，已写好）、`tools/trace_recorder_skill/`（Claude Code skill，已写好）

| 平台 | 状态 | 接入成本 |
|------|:---:|---------|
| Claude Code | ✅ 已写 | 配置 Hooks 即可 |
| Python 自定义 Agent | ✅ 已写 | 3 行代码 |
| OpenClaw | ❌ 待做 | 王睿思已整合 EARS，类似方式整合 |

参赛者不应手写 jsonl。工具自动记录 = 零负担 + 格式一致。

### ③ outcome_reward 自动计算

**文件**：`tools/compute_reward.py`（已写好）

outcome_reward **必须由评测系统自动算**，不让参赛者手填（会偏乐观、标准不一致）。从 ARM 的 result_fidelity 评分自动转换为 0-1 标量。

### ④ challenge 元数据预定义

**文件**：`specs/challenge-metadata-template.yaml`（模板已写好，出题人填具体内容）

每道题在出题时固定 `challenge_id` 和 `challenge_domain`，写进题目描述。不预定义 → 参赛者各填各的 → 事后没法按题分组（GRPO）和按领域聚类（专家蒸馏）。

### ⑤ 规则：失败轨迹也要提交

在 Hackathon 规则文档中明确写：

> **"所有尝试都必须提交，不管成功还是失败。失败的轨迹对模型训练同样重要。不要删除或隐藏失败的尝试。"**

为什么：10 种 RL 训练方法中有 6 种需要失败轨迹（GRPO/DPO/CURE/ExGRPO/RFT/PRM）。只保留成功轨迹 = 退化成 SFT（不区分好坏），60% 的训练方法无法使用。详见 `specs/trace-format-spec.md` §6。

---

## 验收 Checklist

下一次 Hackathon 启动前，以下全部满足：

- [ ] `specs/trace-format-spec.md` 已发布给参赛者
- [ ] 至少两个平台的 trace-recorder 可用（Claude Code + Python）
- [ ] 跑通 end-to-end 测试：用 trace-recorder 完成一道样题 → 自动生成 raw_messages.jsonl → compute_reward.py 自动算 outcome_reward → 格式校验通过
- [ ] 所有 challenge 的 id 和 domain 已在题目描述中预定义（按 template.yaml 格式）
- [ ] Hackathon 规则文档包含"失败轨迹也提交"的要求

---

## 为什么要这么做

Hackathon 产出的轨迹数据要被用于模型后训练（林峰 04-17："paper2arm 复现点后训练文章，到时候直接上"）。不同的 RL 训练方法对数据格式有不同要求：

| 训练方法 | 需要的 | 当前格式是否满足 |
|---------|-------|:---:|
| SFT | 成功轨迹 | ✅ |
| GRPO | 同题多条轨迹 + outcome_reward | ✅ |
| GRPO+PRM | 同上 + 步骤级 reward | ✅ step_id 支持事后自动标注 |
| DPO | 偏好对（好 vs 差） | ✅ 需要失败轨迹 |
| CURE | 成功+失败轨迹 | ✅ 需要失败轨迹 |
| ExGRPO | 历史轨迹池 + 难度信息 | ✅ challenge 元数据支持 |

详细分析见 `org-context/planning/rl-trajectory-requirements.md`。
