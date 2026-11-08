import time
import uuid
import threading
from collections import deque

_lock = threading.Lock()

# Default baseline LLM latency (ms) used to estimate latency saved on cache hits
BASELINE_LLM_LATENCY_MS = 650.0
# Estimated cost per 1,000 tokens in USD
COST_PER_1K_TOKENS_USD = 0.0005

_recent_requests: deque[dict] = deque(maxlen=50)
_t1_latencies: list[float] = []
_t2_latencies: list[float] = []
_llm_latencies: list[float] = []
_all_latencies: list[float] = []
_embedding_times: list[float] = []

METRICS = {
    "t1_hits": 0,
    "t2_hits": 0,
    "cache_hits": 0,
    "cache_misses": 0,
    "bypass_count": 0,
    "guard_blocks": 0,
    "proactive_warm_count": 0,
    "total_requests": 0,
    "total_latency_saved": 0.0,       # in seconds
    "total_latency_saved_ms": 0.0,    # in milliseconds
    "estimated_tokens_saved": 0,
    "estimated_cost_saved_usd": 0.0,
}


def _avg(values: list[float]) -> float:
    if not values:
        return 0.0
    return round(sum(values) / len(values), 2)


def _p95(values: list[float]) -> float:
    if not values:
        return 0.0
    sorted_vals = sorted(values)
    idx = min(len(sorted_vals) - 1, int(len(sorted_vals) * 0.95))
    return round(sorted_vals[idx], 2)


def record_proactive_warm(count: int = 1) -> None:
    """Increments the count of proactively warmed cache entries."""
    with _lock:
        METRICS["proactive_warm_count"] += max(0, int(count))


def update_metrics(
    is_hit: bool,
    latency_saved: float = 0.0,
    *,
    cache_tier: int | None = None,
    latency_ms: float = 0.0,
    embedding_time_ms: float = 0.0,
    prompt: str = "",
    similarity: float | None = None,
    matched_prompt: str | None = None,
    tokens_saved: int = 0,
    guard_blocked: bool = False,
    guard_reason: str | None = None,
    temporal_bypass: bool = False,
) -> None:
    """
    Updates global telemetry metrics after each request.
    Preserves backward compatibility with `update_metrics(is_hit=..., latency_saved=...)`
    while supporting rich per-tier, guardrail, and trace telemetry.
    """
    with _lock:
        METRICS["total_requests"] += 1

        if latency_ms > 0:
            _all_latencies.append(latency_ms)
        if embedding_time_ms > 0:
            _embedding_times.append(embedding_time_ms)

        if temporal_bypass:
            METRICS["bypass_count"] += 1
        if guard_blocked:
            METRICS["guard_blocks"] += 1

        if is_hit:
            METRICS["cache_hits"] += 1
            if cache_tier == 1:
                METRICS["t1_hits"] += 1
                if latency_ms > 0:
                    _t1_latencies.append(latency_ms)
            elif cache_tier == 2:
                METRICS["t2_hits"] += 1
                if latency_ms > 0:
                    _t2_latencies.append(latency_ms)

            # Calculate latency saved in ms
            if latency_saved > 0:
                saved_ms = latency_saved if latency_saved > 20 else latency_saved * 1000.0
            else:
                baseline = _avg(_llm_latencies) if _llm_latencies else BASELINE_LLM_LATENCY_MS
                saved_ms = max(0.0, baseline - latency_ms)

            METRICS["total_latency_saved_ms"] = round(METRICS["total_latency_saved_ms"] + saved_ms, 2)
            METRICS["total_latency_saved"] = round(METRICS["total_latency_saved_ms"] / 1000.0, 3)

            est_tokens = tokens_saved if tokens_saved > 0 else 85
            METRICS["estimated_tokens_saved"] += est_tokens
            METRICS["estimated_cost_saved_usd"] = round(
                (METRICS["estimated_tokens_saved"] / 1000.0) * COST_PER_1K_TOKENS_USD, 6
            )
        else:
            METRICS["cache_misses"] += 1
            if latency_ms > 0:
                _llm_latencies.append(latency_ms)
            est_tokens = 0

        if prompt:
            _recent_requests.appendleft(
                {
                    "id": str(uuid.uuid4())[:8],
                    "timestamp": time.time(),
                    "prompt": prompt,
                    "from_cache": is_hit,
                    "cache_tier": cache_tier,
                    "similarity": round(similarity, 4) if similarity is not None else None,
                    "matched_prompt": matched_prompt,
                    "latency_ms": round(latency_ms, 2),
                    "embedding_time_ms": round(embedding_time_ms, 2),
                    "tokens_saved": est_tokens if is_hit else 0,
                    "guard_blocked": guard_blocked,
                    "guard_reason": guard_reason,
                    "temporal_bypass": temporal_bypass,
                }
            )


def get_metrics() -> dict:
    """Returns the complete telemetry snapshot including backward-compatible keys."""
    with _lock:
        total = METRICS["total_requests"]
        hits = METRICS["cache_hits"]
        t1 = METRICS["t1_hits"]
        t2 = METRICS["t2_hits"]

        hit_rate = round((hits / total) * 100.0, 2) if total > 0 else 0.0
        t1_rate = round((t1 / total) * 100.0, 2) if total > 0 else 0.0
        t2_rate = round((t2 / total) * 100.0, 2) if total > 0 else 0.0

        return {
            **METRICS,
            "hit_rate_percent": hit_rate,
            "t1_hit_rate_percent": t1_rate,
            "t2_hit_rate_percent": t2_rate,
            "avg_t1_latency_ms": _avg(_t1_latencies),
            "avg_t2_latency_ms": _avg(_t2_latencies),
            "avg_llm_latency_ms": _avg(_llm_latencies),
            "avg_embedding_time_ms": _avg(_embedding_times),
            "p95_latency_ms": _p95(_all_latencies),
            "recent_requests": list(_recent_requests),
        }


def reset_metrics() -> dict:
    """Resets all metrics counters and rolling latency buffers."""
    with _lock:
        for k in METRICS:
            if isinstance(METRICS[k], float):
                METRICS[k] = 0.0
            else:
                METRICS[k] = 0
        _recent_requests.clear()
        _t1_latencies.clear()
        _t2_latencies.clear()
        _llm_latencies.clear()
        _all_latencies.clear()
        _embedding_times.clear()
    return get_metrics()
