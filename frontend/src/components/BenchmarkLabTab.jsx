import React, { useState, useEffect, useCallback } from "react";
import { Play } from "lucide-react";
import { runLiveBenchmark, getResourceFootprint } from "../api/cacheApi";

export default function BenchmarkLabTab({ onAfterBenchmark }) {
  const [numPrompts, setNumPrompts] = useState(40);
  const [isRunning, setIsRunning] = useState(false);
  const [benchResult, setBenchResult] = useState(null);
  const [benchError, setBenchError] = useState(null);

  const [scaleEntries, setScaleEntries] = useState(100000);
  const [vectorDim, setVectorDim] = useState(384);
  const [resourceData, setResourceData] = useState(null);

  const fetchResources = useCallback(async (entries, dim) => {
    try {
      const data = await getResourceFootprint(entries, dim);
      setResourceData(data);
    } catch {
      // ignore if offline
    }
  }, []);

  useEffect(() => {
    fetchResources(scaleEntries, vectorDim);
  }, [scaleEntries, vectorDim, fetchResources]);

  async function handleRunBenchmark() {
    setIsRunning(true);
    setBenchError(null);
    try {
      const result = await runLiveBenchmark(numPrompts, true);
      setBenchResult(result);
      await fetchResources(scaleEntries, vectorDim);
      if (onAfterBenchmark) {
        onAfterBenchmark();
      }
    } catch (err) {
      setBenchError(err.message || "Benchmark execution failed.");
    } finally {
      setIsRunning(false);
    }
  }

  function renderColdStartSvg(timeline) {
    if (!timeline || timeline.length === 0) return null;
    const width = 760;
    const height = 220;
    const padLeft = 48;
    const padRight = 20;
    const padTop = 20;
    const padBottom = 32;
    const plotW = width - padLeft - padRight;
    const plotH = height - padTop - padBottom;

    const maxY = Math.max(
      900,
      ...timeline.map((t) =>
        Math.max(
          t.rolling_baseline_latency_ms || 0,
          t.rolling_hybrid_latency_ms || 0
        )
      )
    );

    const toPoint = (idx, val) => {
      const x =
        padLeft +
        (timeline.length > 1
          ? (idx / (timeline.length - 1)) * plotW
          : plotW / 2);
      const y = padTop + plotH - Math.min(1, Math.max(0, val / maxY)) * plotH;
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    };

    const baselinePoints = timeline
      .map((t, i) => toPoint(i, t.rolling_baseline_latency_ms))
      .join(" ");
    const hybridPoints = timeline
      .map((t, i) => toPoint(i, t.rolling_hybrid_latency_ms))
      .join(" ");

    return (
      <svg
        viewBox={`0 0 ${width} ${height}`}
        className="w-full h-auto overflow-visible"
      >
        {[0, 0.25, 0.5, 0.75, 1].map((ratio) => {
          const y = padTop + plotH * (1 - ratio);
          const labelVal = Math.round(maxY * ratio);
          return (
            <g key={ratio}>
              <line
                x1={padLeft}
                y1={y}
                x2={width - padRight}
                y2={y}
                className="stroke-zinc-900/10 dark:stroke-white/10"
                strokeDasharray="4 4"
                strokeWidth="1"
              />
              <text
                x={padLeft - 8}
                y={y + 4}
                textAnchor="end"
                className="fill-zinc-400 dark:fill-zinc-500 text-[10px] font-mono"
              >
                {labelVal}ms
              </text>
            </g>
          );
        })}

        {/* Baseline Curve */}
        <polyline
          fill="none"
          stroke="#f43f5e"
          strokeWidth="1.8"
          strokeDasharray="5 4"
          points={baselinePoints}
        />

        {/* Hybrid Semantic Cache Curve */}
        <polyline
          fill="none"
          stroke="#6366f1"
          strokeWidth="2.8"
          points={hybridPoints}
        />

        {timeline.map((t, i) => {
          const [cx, cy] = toPoint(i, t.rolling_hybrid_latency_ms).split(",");
          return (
            <circle
              key={t.step}
              cx={cx}
              cy={cy}
              r="3"
              fill={
                t.hybrid_tier === 1
                  ? "#10b981"
                  : t.hybrid_tier === 2
                  ? "#6366f1"
                  : "#f43f5e"
              }
            >
              <title>{`Step ${t.step}: "${t.prompt}" → ${t.rolling_hybrid_latency_ms}ms`}</title>
            </circle>
          );
        })}

        <text
          x={padLeft}
          y={height - 6}
          className="fill-zinc-400 dark:fill-zinc-500 text-[10px] font-mono"
        >
          Prompt #1 (Cold Start)
        </text>
        <text
          x={width - padRight}
          y={height - 6}
          textAnchor="end"
          className="fill-indigo-600 dark:fill-indigo-400 text-[10px] font-mono font-semibold"
        >
          Prompt #{timeline.length} (Warm Steady-State)
        </text>
      </svg>
    );
  }

  return (
    <div className="max-w-6xl w-full min-w-0 mx-auto px-3.5 sm:px-6 py-6 md:py-10 space-y-6 sm:space-y-7 overflow-x-hidden">
      {/* Header + Primary Run Benchmark Button */}
      <div className="flex flex-wrap items-center justify-between gap-3 sm:gap-4">
        <div>
          <h1 className="text-xl sm:text-2xl font-semibold tracking-tight text-zinc-900 dark:text-zinc-100">
            Benchmarks &amp; Capacity Lab
          </h1>
          <p className="text-xs text-zinc-500 dark:text-zinc-400 mt-1">
            Compare No-Cache Baseline, Exact Cache, and 3-Tier Semantic Cache on
            identical workloads
          </p>
        </div>

        <div className="flex items-center gap-3 flex-wrap w-full sm:w-auto justify-between sm:justify-end">
          <div className="flex items-center p-1 rounded-full bg-white/85 dark:bg-white/[0.06] border border-black/[0.06] dark:border-white/[0.08] shadow-sm text-xs font-mono">
            {[25, 40, 60].map((size) => (
              <button
                key={size}
                type="button"
                onClick={() => setNumPrompts(size)}
                className={`px-3 py-1.5 rounded-full transition-all duration-200 cursor-pointer ${
                  numPrompts === size
                    ? "sidebar-item-active text-indigo-950 dark:text-white font-semibold"
                    : "text-zinc-500 dark:text-zinc-400 hover:text-zinc-900 dark:hover:text-zinc-100"
                }`}
              >
                {size}
              </button>
            ))}
          </div>

          <button
            type="button"
            onClick={handleRunBenchmark}
            disabled={isRunning}
            className="inline-flex items-center gap-2 px-5 py-2.5 rounded-full bg-gradient-to-r from-indigo-600 via-violet-600 to-fuchsia-600 text-white text-xs font-medium shadow-[0_6px_20px_-4px_rgba(99,102,241,0.4)] hover:shadow-[0_10px_28px_-4px_rgba(99,102,241,0.55)] hover:-translate-y-0.5 active:scale-95 transition-all duration-200 cursor-pointer disabled:opacity-40"
          >
            {isRunning ? (
              <>
                <div className="w-3.5 h-3.5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                Running Benchmark...
              </>
            ) : (
              <>
                <Play className="w-3.5 h-3.5 fill-current" />
                Run Benchmark
              </>
            )}
          </button>
        </div>
      </div>

      {benchError && (
        <div className="p-4 rounded-2xl bg-rose-50 dark:bg-rose-500/15 border border-rose-200 dark:border-rose-500/30 text-xs text-rose-700 dark:text-rose-300">
          {benchError}
        </div>
      )}

      {isRunning && (
        <div className="semantiq-card rounded-2xl p-6 space-y-3 animate-fade-up">
          <div className="flex items-center justify-between text-xs font-mono">
            <span className="text-indigo-600 dark:text-indigo-300 font-semibold flex items-center gap-2">
              <span className="w-2.5 h-2.5 rounded-full bg-indigo-500 animate-ping" />
              Executing {numPrompts}-Prompt 3-Way Live Benchmark (No-Cache vs.
              Exact vs. Semantic Cache)...
            </span>
            <span className="text-zinc-500 dark:text-zinc-400">
              Syncing Telemetry &amp; ChromaDB Vault
            </span>
          </div>
          <div className="h-2.5 w-full rounded-full bg-zinc-100 dark:bg-white/[0.08] overflow-hidden">
            <div className="h-full w-2/3 rounded-full bg-gradient-to-r from-indigo-500 via-fuchsia-500 to-cyan-400 animate-pulse" />
          </div>
        </div>
      )}

      {benchResult ? (
        <div className="space-y-6">
          {/* Summary Strip */}
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            <div className="semantiq-card rounded-2xl p-5">
              <div className="text-xs font-medium text-zinc-500 dark:text-zinc-400">
                API Calls Reduced
              </div>
              <div className="text-2xl font-mono font-semibold text-emerald-600 dark:text-emerald-400 mt-1">
                {benchResult.summary.api_calls_reduced_percent}%
              </div>
            </div>
            <div className="semantiq-card rounded-2xl p-5">
              <div className="text-xs font-medium text-zinc-500 dark:text-zinc-400">
                Speedup Factor
              </div>
              <div className="text-2xl font-mono font-semibold text-indigo-600 dark:text-indigo-400 mt-1">
                {benchResult.summary.speedup_factor}x
              </div>
            </div>
            <div className="semantiq-card rounded-2xl p-5">
              <div className="text-xs font-medium text-zinc-500 dark:text-zinc-400">
                Semantic Hit Uplift
              </div>
              <div className="text-2xl font-mono font-semibold text-zinc-900 dark:text-zinc-100 mt-1">
                +{benchResult.summary.semantic_uplift_over_simple_percent}%
              </div>
            </div>
            <div className="semantiq-card rounded-2xl p-5">
              <div className="text-xs font-medium text-zinc-500 dark:text-zinc-400">
                Token Cost Saved
              </div>
              <div className="text-2xl font-mono font-semibold text-zinc-900 dark:text-zinc-100 mt-1">
                {benchResult.summary.cost_saved_percent}%
              </div>
            </div>
          </div>

          {/* 3 Minimal Comparison Cards */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 sm:gap-5">
            {benchResult.systems.map((sys, idx) => {
              const isSemantic = idx === 2;
              return (
                <div
                  key={sys.name}
                  className={`semantiq-card rounded-2xl p-6 space-y-5 ${
                    isSemantic
                      ? "ring-2 ring-indigo-500/30 dark:ring-indigo-400/40 bg-white/95 dark:bg-white/[0.06]"
                      : ""
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-semibold text-zinc-900 dark:text-zinc-100">
                      {sys.name}
                    </span>
                    <span
                      className={`text-xs font-mono font-medium px-2.5 py-0.5 rounded-full border ${
                        isSemantic
                          ? "bg-emerald-50 dark:bg-emerald-500/15 text-emerald-700 dark:text-emerald-300 border-emerald-200 dark:border-emerald-500/30"
                          : idx === 1
                          ? "bg-indigo-50 dark:bg-indigo-500/15 text-indigo-700 dark:text-indigo-300 border-indigo-200 dark:border-indigo-500/30"
                          : "bg-rose-50 dark:bg-rose-500/15 text-rose-700 dark:text-rose-300 border-rose-200 dark:border-rose-500/30"
                      }`}
                    >
                      {sys.hit_rate_percent}% hit
                    </span>
                  </div>

                  <div className="h-2 w-full rounded-full bg-zinc-100 dark:bg-white/[0.08] overflow-hidden">
                    <div
                      className={`h-full rounded-full ${
                        isSemantic
                          ? "bg-gradient-to-r from-indigo-500 to-emerald-500"
                          : idx === 1
                          ? "bg-indigo-500"
                          : "bg-rose-400"
                      }`}
                      style={{ width: `${Math.max(2, sys.hit_rate_percent)}%` }}
                    />
                  </div>

                  <div className="grid grid-cols-2 gap-3 text-xs font-mono">
                    <div className="p-3 rounded-xl bg-zinc-50 dark:bg-white/[0.04] border border-black/[0.04] dark:border-white/[0.08]">
                      <div className="text-zinc-400 dark:text-zinc-500 text-[11px] font-sans">
                        Avg Latency
                      </div>
                      <div className="text-zinc-900 dark:text-zinc-100 font-semibold mt-0.5">
                        {sys.avg_latency_ms} ms
                      </div>
                    </div>
                    <div className="p-3 rounded-xl bg-zinc-50 dark:bg-white/[0.04] border border-black/[0.04] dark:border-white/[0.08]">
                      <div className="text-zinc-400 dark:text-zinc-500 text-[11px] font-sans">
                        LLM Calls
                      </div>
                      <div className="text-zinc-900 dark:text-zinc-100 font-semibold mt-0.5">
                        {sys.llm_calls_made} / {benchResult.num_prompts}
                      </div>
                    </div>
                    <div className="p-3 rounded-xl bg-zinc-50 dark:bg-white/[0.04] border border-black/[0.04] dark:border-white/[0.08]">
                      <div className="text-zinc-400 dark:text-zinc-500 text-[11px] font-sans">
                        T1 / T2 Hits
                      </div>
                      <div className="text-zinc-800 dark:text-zinc-200 font-semibold mt-0.5">
                        {sys.t1_hits} / {sys.t2_hits}
                      </div>
                    </div>
                    <div className="p-3 rounded-xl bg-zinc-50 dark:bg-white/[0.04] border border-black/[0.04] dark:border-white/[0.08]">
                      <div className="text-zinc-400 dark:text-zinc-500 text-[11px] font-sans">
                        Total Time
                      </div>
                      <div className="text-zinc-800 dark:text-zinc-200 font-semibold mt-0.5">
                        {sys.total_time_s}s
                      </div>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>

          {/* Cold-Start Rolling Latency Curve */}
          <div className="semantiq-card rounded-2xl p-6 space-y-4">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <h2 className="text-sm font-semibold text-zinc-900 dark:text-zinc-100">
                  Cold-Start Warming Curve (Rolling Latency)
                </h2>
                <p className="text-xs text-zinc-500 dark:text-zinc-400 mt-0.5">
                  Illustrates latency reduction as semantic clusters populate
                  Tier-1 and Tier-2
                </p>
              </div>
              <div className="flex items-center gap-4 text-xs font-mono text-zinc-500 dark:text-zinc-400">
                <span className="flex items-center gap-1.5 text-rose-500 dark:text-rose-400">
                  <span className="w-3 h-0.5 bg-rose-500 inline-block" />
                  Baseline
                </span>
                <span className="flex items-center gap-1.5 text-indigo-600 dark:text-indigo-400 font-semibold">
                  <span className="w-3 h-0.5 bg-indigo-500 inline-block" />
                  Semantic Cache
                </span>
              </div>
            </div>

            <div className="p-4 rounded-2xl bg-zinc-50/70 dark:bg-white/[0.03] border border-black/[0.04] dark:border-white/[0.08]">
              {renderColdStartSvg(benchResult.timeline)}
            </div>
          </div>
        </div>
      ) : (
        <div className="semantiq-card rounded-2xl p-12 text-center space-y-2">
          <div className="text-sm font-semibold text-zinc-800 dark:text-zinc-100">
            Ready to benchmark 3-way caching performance
          </div>
          <p className="text-xs text-zinc-500 dark:text-zinc-400 max-w-md mx-auto">
            Click &ldquo;Run Benchmark&rdquo; above to execute a {numPrompts}
            -prompt simulation across No-Cache Baseline, Simple Exact Cache, and
            3-Tier Semantic Cache.
          </p>
        </div>
      )}

      {/* Compact Memory Scaling Calculator */}
      <div className="semantiq-card rounded-2xl p-6 space-y-5">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <h2 className="text-sm font-semibold text-zinc-900 dark:text-zinc-100">
              Memory Scaling Calculator
            </h2>
            <p className="text-xs text-zinc-500 dark:text-zinc-400 mt-0.5">
              HNSW vector index (1.5x overhead) + metadata footprint vs. Redis
              Tier-1
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-2.5 text-xs font-mono">
            <div className="flex items-center p-1 rounded-full bg-zinc-100/80 dark:bg-white/[0.06] border border-black/[0.05] dark:border-white/[0.08]">
              {[
                { label: "10K", val: 10000 },
                { label: "100K", val: 100000 },
                { label: "1M", val: 1000000 },
              ].map((opt) => (
                <button
                  key={opt.val}
                  type="button"
                  onClick={() => setScaleEntries(opt.val)}
                  className={`px-3 py-1 rounded-full transition-all duration-200 cursor-pointer ${
                    scaleEntries === opt.val
                      ? "sidebar-item-active text-indigo-950 dark:text-white font-semibold"
                      : "text-zinc-500 dark:text-zinc-400 hover:text-zinc-900 dark:hover:text-zinc-100"
                  }`}
                >
                  {opt.label}
                </button>
              ))}
            </div>

            <div className="flex items-center p-1 rounded-full bg-zinc-100/80 dark:bg-white/[0.06] border border-black/[0.05] dark:border-white/[0.08]">
              {[
                { label: "384d", val: 384 },
                { label: "768d", val: 768 },
                { label: "1024d", val: 1024 },
              ].map((dim) => (
                <button
                  key={dim.val}
                  type="button"
                  onClick={() => setVectorDim(dim.val)}
                  className={`px-3 py-1 rounded-full transition-all duration-200 cursor-pointer ${
                    vectorDim === dim.val
                      ? "sidebar-item-active text-indigo-950 dark:text-white font-semibold"
                      : "text-zinc-500 dark:text-zinc-400 hover:text-zinc-900 dark:hover:text-zinc-100"
                  }`}
                >
                  {dim.label}
                </button>
              ))}
            </div>
          </div>
        </div>

        {resourceData && (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3.5 sm:gap-4 text-xs font-mono">
            <div className="p-4 rounded-xl bg-zinc-50 dark:bg-white/[0.04] border border-black/[0.04] dark:border-white/[0.08]">
              <div className="text-zinc-400 dark:text-zinc-500 font-sans">
                Raw Vector
              </div>
              <div className="text-base text-zinc-900 dark:text-zinc-100 font-semibold mt-1">
                {resourceData.raw_vector_kb} KB
              </div>
              <div className="text-[11px] text-zinc-500 dark:text-zinc-400 mt-0.5">
                {resourceData.vector_dim}d × 4B
              </div>
            </div>

            <div className="p-4 rounded-xl bg-zinc-50 dark:bg-white/[0.04] border border-black/[0.04] dark:border-white/[0.08]">
              <div className="text-zinc-400 dark:text-zinc-500 font-sans">
                ChromaDB / Entry
              </div>
              <div className="text-base text-indigo-600 dark:text-indigo-400 font-semibold mt-1">
                {resourceData.chromadb_kb_per_entry} KB
              </div>
              <div className="text-[11px] text-zinc-500 dark:text-zinc-400 mt-0.5">
                HNSW + metadata
              </div>
            </div>

            <div className="p-4 rounded-xl bg-zinc-50 dark:bg-white/[0.04] border border-black/[0.04] dark:border-white/[0.08]">
              <div className="text-zinc-400 dark:text-zinc-500 font-sans">
                ChromaDB @ {scaleEntries.toLocaleString()}
              </div>
              <div className="text-base text-zinc-900 dark:text-zinc-100 font-semibold mt-1">
                {resourceData.ram_mb >= 1024
                  ? `${resourceData.ram_gb} GB`
                  : `${resourceData.ram_mb} MB`}
              </div>
              <div className="text-[11px] text-zinc-500 dark:text-zinc-400 mt-0.5">
                1M scale: {resourceData.scale_projections?.["1m"]?.chromadb_gb}{" "}
                GB
              </div>
            </div>

            <div className="p-4 rounded-xl bg-zinc-50 dark:bg-white/[0.04] border border-black/[0.04] dark:border-white/[0.08]">
              <div className="text-zinc-400 dark:text-zinc-500 font-sans">
                Redis @ {scaleEntries.toLocaleString()}
              </div>
              <div className="text-base text-emerald-600 dark:text-emerald-400 font-semibold mt-1">
                {resourceData.requested_scale?.redis_mb >= 1024
                  ? `${resourceData.requested_scale?.redis_gb} GB`
                  : `${resourceData.requested_scale?.redis_mb} MB`}
              </div>
              <div className="text-[11px] text-zinc-500 dark:text-zinc-400 mt-0.5">
                Live: {resourceData.live_usage?.tier1_entries} T1 /{" "}
                {resourceData.live_usage?.tier2_entries} T2
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
