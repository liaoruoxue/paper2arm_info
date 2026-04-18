"""
compute_reward.py — 从 ARM result_fidelity 计算 outcome_reward (0-1 标量)

用法：
    from compute_reward import compute_reward

    reward = compute_reward("within_5pct")       # → 0.8
    reward = compute_reward("exact_match")        # → 1.0
    reward = compute_reward("no_match")           # → 0.0

    # 或从 ARM manifest 文件直接计算
    reward = compute_reward_from_manifest("arm_manifest.json")

设计依据：
    - 二值 reward (0/1) 信号太稀疏，分级 reward 训练效果更好
    - 参考 CURE (2506.03136) 的 μ reward 和 CM2 (2602.12268) 的 checklist reward
    - ARM 的 result_fidelity + 自定义容差 → 天然支持分级 reward
"""

import json
from pathlib import Path


FIDELITY_TO_REWARD = {
    "exact_match": 1.0,
    "within_1pct": 0.9,
    "within_5pct": 0.8,
    "within_10pct": 0.6,
    "within_20pct": 0.5,
    "partial_match": 0.3,
    "trend_correct": 0.2,
    "no_match": 0.0,
}


def compute_reward(
    result_fidelity: str,
    custom_tolerance: float | None = None,
    actual_deviation: float | None = None,
) -> float:
    """从 ARM result_fidelity 字符串计算 0-1 outcome_reward。

    Args:
        result_fidelity: ARM 六维评分中的 result_fidelity 值
        custom_tolerance: 题目自定义容差（如果有，覆盖默认映射）
        actual_deviation: 实际偏差比例（如 0.03 = 3%）

    Returns:
        0-1 之间的 float
    """
    if custom_tolerance is not None and actual_deviation is not None:
        if actual_deviation <= 0:
            return 1.0
        ratio = actual_deviation / custom_tolerance
        if ratio <= 0.2:
            return 1.0
        elif ratio <= 1.0:
            return 0.8
        elif ratio <= 2.0:
            return 0.5
        elif ratio <= 4.0:
            return 0.3
        else:
            return 0.0

    return FIDELITY_TO_REWARD.get(result_fidelity, 0.0)


def compute_reward_from_manifest(manifest_path: str | Path) -> float:
    """从 ARM manifest 文件中读取 result_fidelity 并计算 reward。"""
    manifest = json.loads(Path(manifest_path).read_text())
    fidelity = manifest.get("result_fidelity", "no_match")
    tolerance = manifest.get("custom_tolerance")
    deviation = manifest.get("actual_deviation")
    return compute_reward(fidelity, tolerance, deviation)


def inject_reward_to_trace(trace_path: str | Path, reward: float) -> None:
    """将 outcome_reward 写入 raw_messages.jsonl 的 session_end 行。

    如果 session_end 已有 outcome_reward，覆盖之。
    """
    path = Path(trace_path)
    lines = path.read_text().strip().split("\n")

    last = json.loads(lines[-1])
    if last.get("type") != "session_end":
        raise ValueError(f"最后一行不是 session_end: {last.get('type')}")

    last["outcome_reward"] = round(reward, 4)
    lines[-1] = json.dumps(last, ensure_ascii=False)
    path.write_text("\n".join(lines) + "\n")


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("用法: python compute_reward.py <arm_manifest.json>")
        print("      python compute_reward.py <result_fidelity>")
        sys.exit(1)

    arg = sys.argv[1]
    if arg.endswith(".json"):
        r = compute_reward_from_manifest(arg)
    else:
        r = compute_reward(arg)
    print(f"outcome_reward: {r}")
