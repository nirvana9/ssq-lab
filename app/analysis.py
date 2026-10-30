from __future__ import annotations

import math
import random
from collections import Counter
from typing import Any

import pandas as pd


def _zone_counts(red: list[int]) -> list[int]:
    return [sum(1 for n in red if 1 <= n <= 11),
            sum(1 for n in red if 12 <= n <= 22),
            sum(1 for n in red if 23 <= n <= 33)]


def summarize(draws: list[dict[str, Any]], window: int = 30) -> dict[str, Any]:
    if not draws:
        return {"count": 0, "window": window, "red_frequency": {}, "blue_frequency": {},
                "red_omission": {}, "blue_omission": {}, "latest": None, "metrics": {}}
    sample = draws[-window:] if window > 0 else draws
    df = pd.DataFrame(sample)
    df["red_sum"] = df["red"].apply(sum)
    df["odd_count"] = df["red"].apply(lambda nums: sum(n % 2 for n in nums))
    df["red_span"] = df["red"].apply(lambda nums: max(nums) - min(nums))
    red_freq = Counter(n for d in sample for n in d["red"])
    blue_freq = Counter(d["blue"] for d in sample)
    red_omit: dict[int, int] = {}
    blue_omit: dict[int, int] = {}
    for n in range(1, 34):
        red_omit[n] = next((i for i, d in enumerate(reversed(draws)) if n in d["red"]), len(draws))
    for n in range(1, 17):
        blue_omit[n] = next((i for i, d in enumerate(reversed(draws)) if d["blue"] == n), len(draws))
    sums = df["red_sum"].tolist()
    odds = df["odd_count"].tolist()
    spans = df["red_span"].tolist()
    zones = [_zone_counts(d["red"]) for d in sample]
    odd_even = Counter(f"{odd}:{6-odd}" for odd in odds)
    zone_dist = Counter("-".join(map(str, z)) for z in zones)
    red_freq_full = {n: int(red_freq.get(n, 0)) for n in range(1, 34)}
    blue_freq_full = {n: int(blue_freq.get(n, 0)) for n in range(1, 17)}
    red_mean = (len(sample) * 6 / 33) if sample else 0
    hot = sorted(red_freq_full, key=lambda n: (-red_freq_full[n], n))[:8]
    cold = sorted(red_freq_full, key=lambda n: (red_freq_full[n], n))[:8]
    return {
        "count": len(draws),
        "window": len(sample),
        "red_frequency": red_freq_full,
        "blue_frequency": blue_freq_full,
        "red_omission": red_omit,
        "blue_omission": blue_omit,
        "hot_red": hot,
        "cold_red": cold,
        "hot_blue": sorted(blue_freq_full, key=lambda n: (-blue_freq_full[n], n))[:5],
        "cold_blue": sorted(blue_freq_full, key=lambda n: (blue_freq_full[n], n))[:5],
        "metrics": {
            "avg_sum": round(sum(sums) / len(sums), 2) if sums else 0,
            "avg_odd": round(sum(odds) / len(odds), 2) if odds else 0,
            "avg_blue": round(sum(d["blue"] for d in sample) / len(sample), 2) if sample else 0,
            "avg_span": round(sum(spans) / len(spans), 2) if spans else 0,
            "sum_min": min(sums) if sums else 0,
            "sum_max": max(sums) if sums else 0,
            "odd_even_distribution": dict(odd_even),
            "zone_distribution": dict(zone_dist),
            "average_red_frequency": round(red_mean, 2),
        },
        "latest": draws[-1],
    }


def _weighted_sample(numbers: list[int], weights: list[float], k: int, rng: random.Random) -> list[int]:
    pool = list(zip(numbers, weights))
    selected: list[int] = []
    for _ in range(k):
        total = sum(max(0.0001, w) for _, w in pool)
        point = rng.random() * total
        acc = 0.0
        chosen_idx = len(pool) - 1
        for idx, (_, weight) in enumerate(pool):
            acc += max(0.0001, weight)
            if acc >= point:
                chosen_idx = idx
                break
        selected.append(pool.pop(chosen_idx)[0])
    return sorted(selected)


def generate_picks(draws: list[dict[str, Any]], count: int = 5, mode: str = "random",
                   window: int = 50, sum_min: int = 70, sum_max: int = 150,
                   use_filters: bool = True, avoid_latest: bool = False,
                   seed: int | None = None) -> list[dict[str, Any]]:
    rng = random.Random(seed)
    history = draws[-window:] if draws and window > 0 else draws
    red_freq = Counter(n for d in history for n in d["red"])
    blue_freq = Counter(d["blue"] for d in history)
    avg = max(1.0, len(history) * 6 / 33)
    latest_red = set(draws[-1]["red"]) if draws else set()
    red_numbers = list(range(1, 34))
    if mode == "hot":
        red_weights = [1.0 + red_freq[n] for n in red_numbers]
        blue_weights = [1.0 + blue_freq[n] for n in range(1, 17)]
    elif mode == "cold":
        red_weights = [1.0 / (1.0 + red_freq[n]) for n in red_numbers]
        blue_weights = [1.0 / (1.0 + blue_freq[n]) for n in range(1, 17)]
    elif mode == "balanced":
        red_weights = [1.0 / (1.0 + abs(red_freq[n] - avg)) for n in red_numbers]
        blue_avg = max(1.0, len(history) / 16)
        blue_weights = [1.0 / (1.0 + abs(blue_freq[n] - blue_avg)) for n in range(1, 17)]
    else:
        red_weights = [1.0] * 33
        blue_weights = [1.0] * 16

    results: list[dict[str, Any]] = []
    attempts = 0
    max_attempts = max(200, count * 300)
    while len(results) < count and attempts < max_attempts:
        attempts += 1
        weights = red_weights[:]
        if avoid_latest:
            weights = [w * (0.05 if n in latest_red else 1.0) for n, w in zip(red_numbers, weights)]
        red = _weighted_sample(red_numbers, weights, 6, rng)
        total = sum(red)
        odd = sum(n % 2 for n in red)
        zones = _zone_counts(red)
        if total < sum_min or total > sum_max:
            continue
        if use_filters and (odd < 2 or odd > 4 or any(z < 1 or z > 3 for z in zones)):
            continue
        blue = _weighted_sample(list(range(1, 17)), blue_weights, 1, rng)[0]
        key = (tuple(red), blue)
        if any((tuple(x["red"]), x["blue"]) == key for x in results):
            continue
        results.append({"red": red, "blue": blue, "sum": total, "odd": odd, "zones": zones,
                        "span": max(red) - min(red)})
    return results


def prize_tier(red_hits: int, blue_hit: bool) -> int | None:
    if red_hits == 6 and blue_hit:
        return 1
    if red_hits == 6:
        return 2
    if red_hits == 5 and blue_hit:
        return 3
    if (red_hits == 5) or (red_hits == 4 and blue_hit):
        return 4
    if (red_hits == 4) or (red_hits == 3 and blue_hit):
        return 5
    if blue_hit:
        return 6
    return None


def backtest(draws: list[dict[str, Any]], window: int = 50, warmup: int = 100,
             strategies: list[str] | None = None, seed: int = 20261030) -> dict[str, Any]:
    strategies = strategies or ["random", "balanced", "hot", "cold"]
    names = {"random": "均匀随机", "balanced": "均衡参考", "hot": "热号参考", "cold": "冷号参考"}
    start = max(warmup, window, 30)
    if len(draws) <= start:
        return {"sample_count": 0, "warmup": start, "results": [],
                "message": f"历史数据只有 {len(draws)} 期，至少需要 {start + 1} 期才能回测。"}
    summaries = []
    for strategy_index, strategy in enumerate(strategies):
        rng = random.Random(seed + strategy_index * 1009)
        tier_counts: Counter[int] = Counter()
        red_hit_counts: Counter[int] = Counter()
        blue_hits = 0
        tested = 0
        for idx in range(start, len(draws)):
            history = draws[max(0, idx - window):idx]
            ticket = generate_picks(history, count=1, mode=strategy, window=len(history),
                                    sum_min=1, sum_max=183, use_filters=False,
                                    seed=rng.randrange(0, 2**31 - 1))[0]
            actual = draws[idx]
            red_hits = len(set(ticket["red"]) & set(actual["red"]))
            blue_hit = ticket["blue"] == actual["blue"]
            tier = prize_tier(red_hits, blue_hit)
            red_hit_counts[red_hits] += 1
            if blue_hit:
                blue_hits += 1
            if tier is not None:
                tier_counts[tier] += 1
            tested += 1
        summaries.append({
            "strategy": strategy,
            "name": names.get(strategy, strategy),
            "tested": tested,
            "prize_draws": sum(tier_counts.values()),
            "blue_hits": blue_hits,
            "red_hit_distribution": {str(k): red_hit_counts.get(k, 0) for k in range(7)},
            "tiers": {str(k): tier_counts.get(k, 0) for k in range(1, 7)},
            "tier6_plus": tier_counts.get(6, 0),
            "hit_rate": round(sum(tier_counts.values()) / tested * 100, 2),
        })
    return {"sample_count": len(draws) - start, "warmup": start,
            "test_from": draws[start]["issue"], "test_to": draws[-1]["issue"],
            "window": window, "results": summaries,
            "note": "严格按时间顺序回测：每期只使用该期之前的数据生成号码。单注随机中奖概率不因历史频次而改变；回测样本不代表未来表现。"}
