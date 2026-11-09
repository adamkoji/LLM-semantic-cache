import React, { useState } from "react";
import { RefreshCw, RotateCcw, Zap } from "lucide-react";
import { processPrompt } from "../api/cacheApi";

const LIVE_TRAFFIC_WORKLOAD = [
  "What is machine learning and how does it work?",
  "  what is machine learning and how does it work? ",
  "Can you explain machine learning in simple terms?",
  "What is the capital of France?",
  "What is the capital of Germany?",
  "what is the capital of france?",
  "How do I install Docker?",
  "How do I uninstall Docker?",
  "How do artificial neural networks learn from data?",
  "What is the weather in Delhi today?",
];

export default function TelemetryTab({
  metrics,
  onRefreshMetrics,
  onResetMetrics,
  isRefreshing,
}) {
  const [isSimulating, setIsSimulating] = useState(false);
  const [simStep, setSimStep] = useState(0);

  async function handleSimulateTraffic() {
    if (isSimulating) return;
    setIsSimulating(true);
    setSimStep(0);
    try {
      for (let i = 0; i < LIVE_TRAFFIC_WORKLOAD.length; i++) {
        setSimStep(i + 1);
        await processPrompt(LIVE_TRAFFIC_WORKLOAD[i]);
        if (onRefreshMetrics) {
          await onRefreshMetrics();
        }
      }
    } catch {
      // ignore if interrupted
    } finally {
      setIsSimulating(false);
      setSimStep(0);
    }
  }
  const m = metrics || {
    t1_hits: 0,
    t2_hits: 0,
    cache_hits: 0,
    cache_misses: 0,
    bypass_count: 0,
    guard_blocks: 0,
    proactive_warm_count: 0,
    total_requests: 0,
    hit_rate_percent: 0,
    t1_hit_rate_percent: 0,
    t2_hit_rate_percent: 0,
    total_latency_saved: 0,
    total_latency_saved_ms: 0,
    avg_t1_latency_ms: 0,
    avg_t2_latency_ms: 0,
    avg_llm_latency_ms: 0,
    avg_embedding_time_ms: 0,
    p95_latency_ms: 0,
    estimated_tokens_saved: 0,
    estimated_cost_saved_usd: 0,
    recent_requests: [],
  };

  const totalReq = Math.max(1, m.total_requests || 0);
  const t1Pct =
    m.total_requests > 0 ? ((m.t1_hits / totalReq) * 100).toFixed(1) : "0.0";
  const t2Pct =
    m.total_requests > 0 ? ((m.t2_hits / totalReq) * 100).toFixed(1) : "0.0";
  const missPct =
    m.total_requests > 0
      ? ((m.cache_misses / totalReq) * 100).toFixed(1)
      : "0.0";

  const avgT1 = m.avg_t1_latency_ms || 0.8;
  const avgT2 = m.avg_t2_latency_ms || 14.5;
  const avgLlm = m.avg_llm_latency_ms || 680.0;
  const maxLat = Math.max(avgLlm, avgT2, avgT1, 100);

  return (
    <div className="max-w-6xl w-full min-w-0 mx-auto px-3.5 sm:px-6 py-6 md:py-10 space-y-6 sm:space-y-7 overflow-x-hidden">
      {/* Header */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
        <div>
          <h1 className="text-xl sm:text-2xl font-semibold tracking-tight text-zinc-900 dark:text-zinc-100">
            Analytics &amp; Cost Savings
          </h1>
          <p className="text-xs text-zinc-500 dark:text-zinc-400 mt-1">
            Real-time multi-tier hit ratios, latency percentiles, and inference
            savings
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2 sm:gap-2.5 w-full sm:w-auto">
          <button
            type="button"
            onClick={handleSimulateTraffic}
            disabled={isSimulating}
            className="inline-flex items-center gap-2 px-4 py-2 rounded-full text-xs font-medium bg-gradient-to-r from-indigo-600 via-violet-600 to-fuchsia-600 text-white shadow-[0_6px_20px_-4px_rgba(99,102,241,0.4)] hover:shadow-[0_10px_28px_-4px_rgba(99,102,241,0.55)] hover:-translate-y-0.5 active:scale-95 transition-all duration-200 cursor-pointer disabled:opacity-60"
          >
            {isSimulating ? (
              <>
                <span className="w-3.5 h-3.5 rounded-full border-2 border-white/30 border-t-white animate-spin" />
                <span>
                  Simulating ({simStep}/{LIVE_TRAFFIC_WORKLOAD.length})...
                </span>
              </>
            ) : (
              <>
                <Zap className="w-3.5 h-3.5 fill-current" />
                <span>⚡ Simulate Live Traffic (10 Queries)</span>
              </>
            )}
          </button>

          <button
            type="button"
            onClick={onRefreshMetrics}
            disabled={isRefreshing || isSimulating}
            className="inline-flex items-center gap-2 px-4 py-2 rounded-full text-xs font-medium bg-white/85 dark:bg-white/[0.06] hover:bg-white dark:hover:bg-white/[0.1] text-zinc-700 dark:text-zinc-200 border border-black/[0.06] dark:border-white/[0.08] hover:border-indigo-200/80 dark:hover:border-indigo-400/30 shadow-sm hover:shadow-md hover:-translate-y-0.5 active:scale-95 transition-all duration-200 cursor-pointer disabled:opacity-50"
          >
            <RefreshCw
              className={`w-3.5 h-3.5 text-indigo-600 dark:text-indigo-400 ${isRefreshing ? "animate-spin" : ""}`}
            />
            Refresh
          </button>

          <button
            type="button"
            onClick={onResetMetrics}
            disabled={isSimulating}
            className="inline-flex items-center gap-2 px-4 py-2 rounded-full text-xs font-medium bg-white/85 dark:bg-white/[0.06] hover:bg-rose-50 dark:hover:bg-rose-500/15 text-zinc-700 dark:text-zinc-200 hover:text-rose-700 dark:hover:text-rose-300 border border-black/[0.06] dark:border-white/[0.08] hover:border-rose-200 dark:hover:border-rose-500/30 shadow-sm hover:shadow-md hover:-translate-y-0.5 active:scale-95 transition-all duration-200 cursor-pointer disabled:opacity-50"
          >
            <RotateCcw className="w-3.5 h-3.5" />
            Reset Counters
          </button>
        </div>
      </div>

      {/* Live Traffic Simulation Progress Banner */}
      {isSimulating && (
        <div className="semantiq-card rounded-2xl p-4 space-y-2 animate-fade-up">
          <div className="flex items-center justify-between text-xs font-mono">
            <span className="text-indigo-600 dark:text-indigo-300 font-semibold flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-indigo-500 animate-ping" />
              Executing Query {simStep} of {LIVE_TRAFFIC_WORKLOAD.length}: &ldquo;
              {LIVE_TRAFFIC_WORKLOAD[Math.max(0, simStep - 1)]}&rdquo;
            </span>
            <span className="text-zinc-500 dark:text-zinc-400">
              {Math.round((simStep / LIVE_TRAFFIC_WORKLOAD.length) * 100)}%
            </span>
          </div>
          <div className="h-2 w-full rounded-full bg-zinc-100 dark:bg-white/[0.08] overflow-hidden">
            <div
              className="h-full rounded-full bg-gradient-to-r from-indigo-500 via-fuchsia-500 to-cyan-500 transition-all duration-300"
              style={{
                width: `${(simStep / LIVE_TRAFFIC_WORKLOAD.length) * 100}%`,
              }}
            />
          </div>
        </div>
      )}

      {/* 4-Card KPI Row */}
      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-3.5 sm:gap-4">
        <div className="semantiq-card rounded-2xl p-5 space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-zinc-500 dark:text-zinc-400">
              Cache Hit Rate
            </span>
            <span className="text-[11px] font-medium px-2 py-0.5 rounded-full bg-emerald-50 dark:bg-emerald-500/15 text-emerald-700 dark:text-emerald-300 border border-emerald-200 dark:border-emerald-500/30">
              Active
            </span>
          </div>
          <div className="text-3xl font-semibold tracking-tight text-zinc-900 dark:text-zinc-100 font-mono">
            {Number(m.hit_rate_percent || 0).toFixed(1)}%
          </div>
          <div className="text-[11px] font-mono text-zinc-500 dark:text-zinc-400 flex items-center justify-between pt-1">
            <span>T1: {m.t1_hits}</span>
            <span>T2: {m.t2_hits}</span>
            <span>Total: {m.total_requests}</span>
          </div>
        </div>

        <div className="semantiq-card rounded-2xl p-5 space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-zinc-500 dark:text-zinc-400">
              Avg Cache Latency
            </span>
            <span className="text-[11px] font-medium px-2 py-0.5 rounded-full bg-indigo-50 dark:bg-indigo-500/15 text-indigo-700 dark:text-indigo-300 border border-indigo-200 dark:border-indigo-500/30">
              Tier-2
            </span>
          </div>
          <div className="text-3xl font-semibold tracking-tight text-zinc-900 dark:text-zinc-100 font-mono">
            {Number(m.avg_t2_latency_ms || 0).toFixed(1)}
            <span className="text-sm text-zinc-400 dark:text-zinc-500 ml-1">
              ms
            </span>
          </div>
          <div className="text-[11px] font-mono text-zinc-500 dark:text-zinc-400 flex items-center justify-between pt-1">
            <span>T1: {Number(m.avg_t1_latency_ms || 0).toFixed(1)}ms</span>
            <span>LLM: {Number(m.avg_llm_latency_ms || 0).toFixed(0)}ms</span>
          </div>
        </div>

        <div className="semantiq-card rounded-2xl p-5 space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-zinc-500 dark:text-zinc-400">
              Cumulative Time Saved
            </span>
            <span className="text-[11px] font-medium px-2 py-0.5 rounded-full bg-sky-50 dark:bg-sky-500/15 text-sky-700 dark:text-sky-300 border border-sky-200 dark:border-sky-500/30">
              Speedup
            </span>
          </div>
          <div className="text-3xl font-semibold tracking-tight text-zinc-900 dark:text-zinc-100 font-mono">
            {Number(m.total_latency_saved || 0).toFixed(2)}
            <span className="text-sm text-zinc-400 dark:text-zinc-500 ml-1">
              s
            </span>
          </div>
          <div className="text-[11px] font-mono text-zinc-500 dark:text-zinc-400 flex items-center justify-between pt-1">
            <span>{Number(m.total_latency_saved_ms || 0).toFixed(0)} ms</span>
            <span>P95: {Number(m.p95_latency_ms || 0).toFixed(0)}ms</span>
          </div>
        </div>

        <div className="semantiq-card rounded-2xl p-5 space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-zinc-500 dark:text-zinc-400">
              Cost Saved &amp; Guards
            </span>
            <span className="text-[11px] font-medium px-2 py-0.5 rounded-full bg-amber-50 dark:bg-amber-500/15 text-amber-700 dark:text-amber-300 border border-amber-200 dark:border-amber-500/30">
              Safety
            </span>
          </div>
          <div className="text-3xl font-semibold tracking-tight text-zinc-900 dark:text-zinc-100 font-mono">
            ${Number(m.estimated_cost_saved_usd || 0).toFixed(4)}
          </div>
          <div className="text-[11px] font-mono text-zinc-500 dark:text-zinc-400 flex items-center justify-between pt-1">
            <span>{(m.estimated_tokens_saved || 0).toLocaleString()} tok</span>
            <span>
              Guards: {(m.guard_blocks || 0) + (m.bypass_count || 0)}
            </span>
          </div>
        </div>
      </div>

      {/* Distribution & Latency Breakdown */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 sm:gap-6">
        {/* Left: Tier Resolution Split */}
        <div className="semantiq-card rounded-2xl p-5 sm:p-6 space-y-5">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-semibold text-zinc-900 dark:text-zinc-100">
              Tier Resolution Distribution
            </h2>
            <span className="text-xs font-mono text-zinc-400 dark:text-zinc-500">
              {m.total_requests} queries
            </span>
          </div>

          <div className="h-3 w-full rounded-full bg-zinc-100 dark:bg-white/[0.08] overflow-hidden flex">
            <div
              className="bg-emerald-500 h-full transition-all duration-500"
              style={{ width: `${t1Pct}%` }}
            />
            <div
              className="bg-indigo-500 h-full transition-all duration-500"
              style={{ width: `${t2Pct}%` }}
            />
            <div
              className="bg-rose-400 h-full transition-all duration-500"
              style={{ width: `${missPct}%` }}
            />
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-2.5 sm:gap-3 pt-1">
            <div className="p-3.5 rounded-xl bg-zinc-50/80 dark:bg-white/[0.03] border border-black/[0.04] dark:border-white/[0.07]">
              <div className="flex items-center gap-2 text-xs text-zinc-600 dark:text-zinc-300 font-medium">
                <span className="w-2.5 h-2.5 rounded-full bg-emerald-500" />
                Tier-1 Exact
              </div>
              <div className="text-lg font-mono font-semibold text-zinc-900 dark:text-zinc-100 mt-1">
                {m.t1_hits}{" "}
                <span className="text-xs font-normal text-zinc-400 dark:text-zinc-500">
                  ({t1Pct}%)
                </span>
              </div>
            </div>

            <div className="p-3.5 rounded-xl bg-zinc-50/80 dark:bg-white/[0.03] border border-black/[0.04] dark:border-white/[0.07]">
              <div className="flex items-center gap-2 text-xs text-zinc-600 dark:text-zinc-300 font-medium">
                <span className="w-2.5 h-2.5 rounded-full bg-indigo-500" />
                Tier-2 Cosine
              </div>
              <div className="text-lg font-mono font-semibold text-zinc-900 dark:text-zinc-100 mt-1">
                {m.t2_hits}{" "}
                <span className="text-xs font-normal text-zinc-400 dark:text-zinc-500">
                  ({t2Pct}%)
                </span>
              </div>
            </div>

            <div className="p-3.5 rounded-xl bg-zinc-50/80 dark:bg-white/[0.03] border border-black/[0.04] dark:border-white/[0.07]">
              <div className="flex items-center gap-2 text-xs text-zinc-600 dark:text-zinc-300 font-medium">
                <span className="w-2.5 h-2.5 rounded-full bg-rose-400" />
                Tier-3 LLM
              </div>
              <div className="text-lg font-mono font-semibold text-zinc-900 dark:text-zinc-100 mt-1">
                {m.cache_misses}{" "}
                <span className="text-xs font-normal text-zinc-400 dark:text-zinc-500">
                  ({missPct}%)
                </span>
              </div>
            </div>
          </div>
        </div>

        {/* Right: Latency Comparison */}
        <div className="semantiq-card rounded-2xl p-6 space-y-5">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-semibold text-zinc-900 dark:text-zinc-100">
              Latency Profile by Tier
            </h2>
            <span className="text-xs font-mono text-zinc-400 dark:text-zinc-500">
              Emb avg: {Number(m.avg_embedding_time_ms || 0).toFixed(1)}ms
            </span>
          </div>

          <div className="space-y-4">
            <div className="space-y-1.5">
              <div className="flex justify-between text-xs font-mono">
                <span className="text-zinc-600 dark:text-zinc-400">
                  Tier-1 SHA-256 Exact
                </span>
                <span className="text-zinc-900 dark:text-zinc-100 font-semibold">
                  {Number(m.avg_t1_latency_ms || 0.5).toFixed(2)} ms
                </span>
              </div>
              <div className="h-2.5 w-full rounded-full bg-zinc-100 dark:bg-white/[0.08] overflow-hidden">
                <div
                  className="h-full bg-emerald-500 rounded-full"
                  style={{ width: `${Math.max(3, (avgT1 / maxLat) * 100)}%` }}
                />
              </div>
            </div>

            <div className="space-y-1.5">
              <div className="flex justify-between text-xs font-mono">
                <span className="text-zinc-600 dark:text-zinc-400">
                  Tier-2 ChromaDB HNSW
                </span>
                <span className="text-zinc-900 dark:text-zinc-100 font-semibold">
                  {Number(m.avg_t2_latency_ms || 12.0).toFixed(2)} ms
                </span>
              </div>
              <div className="h-2.5 w-full rounded-full bg-zinc-100 dark:bg-white/[0.08] overflow-hidden">
                <div
                  className="h-full bg-indigo-500 rounded-full"
                  style={{ width: `${Math.max(6, (avgT2 / maxLat) * 100)}%` }}
                />
              </div>
            </div>

            <div className="space-y-1.5">
              <div className="flex justify-between text-xs font-mono">
                <span className="text-zinc-600 dark:text-zinc-400">
                  Tier-3 Gemini Inference
                </span>
                <span className="text-zinc-900 dark:text-zinc-100 font-semibold">
                  {Number(m.avg_llm_latency_ms || 650.0).toFixed(0)} ms
                </span>
              </div>
              <div className="h-2.5 w-full rounded-full bg-zinc-100 dark:bg-white/[0.08] overflow-hidden">
                <div
                  className="h-full bg-rose-400 rounded-full"
                  style={{
                    width: `${Math.min(100, Math.max(25, (avgLlm / maxLat) * 100))}%`,
                  }}
                />
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Request Log Table */}
      <div className="semantiq-card rounded-2xl p-6 space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-semibold text-zinc-900 dark:text-zinc-100">
            Recent Request Telemetry Log
          </h2>
          <span className="text-xs font-mono text-zinc-400 dark:text-zinc-500">
            {(m.recent_requests || []).length} events
          </span>
        </div>

        {!m.recent_requests || m.recent_requests.length === 0 ? (
          <div className="py-12 text-center space-y-4">
            <div className="text-xs text-zinc-500 dark:text-zinc-400 max-w-md mx-auto">
              No requests recorded yet. Run a realistic 10-query workload
              (exact hits, semantic paraphrases, guardrail blocks, and misses)
              to populate live analytics in real time.
            </div>
            <button
              type="button"
              onClick={handleSimulateTraffic}
              disabled={isSimulating}
              className="inline-flex items-center gap-2 px-5 py-2.5 rounded-full text-xs font-medium bg-gradient-to-r from-indigo-600 via-violet-600 to-fuchsia-600 text-white shadow-md hover:shadow-lg hover:-translate-y-0.5 active:scale-95 transition-all duration-200 cursor-pointer disabled:opacity-50"
            >
              <Zap className="w-3.5 h-3.5 fill-current" />
              <span>
                {isSimulating
                  ? `Simulating (${simStep}/${LIVE_TRAFFIC_WORKLOAD.length})...`
                  : "⚡ Simulate Live Traffic (10 Queries)"}
              </span>
            </button>
          </div>
        ) : (
          <div className="overflow-x-auto max-h-[380px] overflow-y-auto">
            <table className="w-full text-left border-collapse text-xs">
              <thead>
                <tr className="border-b border-black/[0.06] dark:border-white/[0.08] text-zinc-400 dark:text-zinc-500 font-mono text-[11px]">
                  <th className="py-2.5 px-3 font-medium">Prompt</th>
                  <th className="py-2.5 px-3 font-medium">Resolution</th>
                  <th className="py-2.5 px-3 font-medium">Similarity</th>
                  <th className="py-2.5 px-3 font-medium">Matched / Note</th>
                  <th className="py-2.5 px-3 text-right font-medium">
                    Latency
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-black/[0.04] dark:divide-white/[0.06]">
                {m.recent_requests.map((req, idx) => (
                  <tr
                    key={`${req.id || idx}-${idx}`}
                    className="hover:bg-zinc-50/70 dark:hover:bg-white/[0.04] transition"
                  >
                    <td className="py-3 px-3 text-zinc-800 dark:text-zinc-200 font-medium max-w-[260px] truncate">
                      {req.prompt}
                    </td>
                    <td className="py-3 px-3 font-medium text-[11px]">
                      {req.temporal_bypass ? (
                        <span className="px-2.5 py-0.5 rounded-full bg-amber-50 dark:bg-amber-500/15 text-amber-700 dark:text-amber-300 border border-amber-200 dark:border-amber-500/30">
                          Temporal Bypass
                        </span>
                      ) : req.guard_blocked ? (
                        <span className="px-2.5 py-0.5 rounded-full bg-amber-50 dark:bg-amber-500/15 text-amber-700 dark:text-amber-300 border border-amber-200 dark:border-amber-500/30">
                          Guard Blocked
                        </span>
                      ) : req.from_cache && req.cache_tier === 1 ? (
                        <span className="px-2.5 py-0.5 rounded-full bg-emerald-50 dark:bg-emerald-500/15 text-emerald-700 dark:text-emerald-300 border border-emerald-200 dark:border-emerald-500/30">
                          Tier-1 Exact
                        </span>
                      ) : req.from_cache && req.cache_tier === 2 ? (
                        <span className="px-2.5 py-0.5 rounded-full bg-indigo-50 dark:bg-indigo-500/15 text-indigo-700 dark:text-indigo-300 border border-indigo-200 dark:border-indigo-500/30">
                          Tier-2 Cosine
                        </span>
                      ) : (
                        <span className="px-2.5 py-0.5 rounded-full bg-rose-50 dark:bg-rose-500/15 text-rose-700 dark:text-rose-300 border border-rose-200 dark:border-rose-500/30">
                          Tier-3 LLM
                        </span>
                      )}
                    </td>
                    <td className="py-3 px-3 font-mono text-zinc-700 dark:text-zinc-300">
                      {req.similarity !== null && req.similarity !== undefined
                        ? Number(req.similarity).toFixed(3)
                        : "—"}
                    </td>
                    <td className="py-3 px-3 font-mono text-zinc-500 dark:text-zinc-400 max-w-[240px] truncate">
                      {req.guard_reason || req.matched_prompt || "—"}
                    </td>
                    <td className="py-3 px-3 text-right font-mono font-semibold text-zinc-900 dark:text-zinc-100">
                      {Number(req.latency_ms || 0).toFixed(1)} ms
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
