import React, { useState, useEffect, useRef } from "react";
import {
  Sparkles,
  ShieldCheck,
  Clock,
  Plus,
  ChevronDown,
  ChevronUp,
  SlidersHorizontal,
  RotateCcw,
  ArrowUpRight,
  ArrowRight,
  Zap,
  Database,
  Cpu,
  ShieldAlert,
  Square,
} from "lucide-react";
import { processPrompt, processPromptNoCache } from "../api/cacheApi";

const SAMPLE_PROMPTS_CYCLE = [
  "What is machine learning and how does it work?",
  "Can you explain machine learning in simple terms?",
  "How do artificial neural networks learn from data?",
  "What is the capital of France?",
  "What is the capital of Germany?",
  "How do I install Docker?",
  "How do I uninstall Docker?",
  "What is the weather in Delhi today?",
];

const QUESTION_SUGGESTIONS = [
  {
    prompt: "What is machine learning and how does it work?",
    icon: Sparkles,
    iconColor:
      "text-indigo-500 dark:text-indigo-300 bg-indigo-50 dark:bg-indigo-500/15 border-indigo-100 dark:border-indigo-400/25",
  },
  {
    prompt: "Can you explain machine learning in simple terms?",
    icon: Zap,
    iconColor:
      "text-violet-500 dark:text-violet-300 bg-violet-50 dark:bg-violet-500/15 border-violet-100 dark:border-violet-400/25",
  },
  {
    prompt: "How do artificial neural networks learn from data?",
    icon: Cpu,
    iconColor:
      "text-fuchsia-500 dark:text-fuchsia-300 bg-fuchsia-50 dark:bg-fuchsia-500/15 border-fuchsia-100 dark:border-fuchsia-400/25",
  },
  {
    prompt: "What is the capital of France?",
    icon: ShieldCheck,
    iconColor:
      "text-amber-500 dark:text-amber-300 bg-amber-50 dark:bg-amber-500/15 border-amber-100 dark:border-amber-400/25",
  },
  {
    prompt: "What is the weather in Delhi today?",
    icon: Clock,
    iconColor:
      "text-emerald-500 dark:text-emerald-300 bg-emerald-50 dark:bg-emerald-500/15 border-emerald-100 dark:border-emerald-400/25",
  },
];

function getFollowUpsForPrompt(promptText) {
  const lower = (promptText || "").trim().toLowerCase();
  if (
    lower === "what is machine learning?" ||
    lower === "what is machine learning and how does it work?"
  ) {
    return [
      {
        label: "Test Tier-1 Exact Hit",
        prompt: `  ${promptText.trim().toLowerCase()} `,
      },
      {
        label: "Test Tier-2 Semantic Hit",
        prompt: "Can you explain machine learning in simple terms?",
      },
    ];
  }
  if (lower === "what is the capital of france?") {
    return [
      {
        label: "Test Entity Guard: Capital of Germany",
        prompt: "What is the capital of Germany?",
      },
      {
        label: "Seed: How do I install Docker?",
        prompt: "How do I install Docker?",
      },
    ];
  }
  if (lower === "how do i install docker?") {
    return [
      {
        label: "Test Antonym Guard: Uninstall Docker",
        prompt: "How do I uninstall Docker?",
      },
    ];
  }
  return [];
}

export default function PlaygroundTab({
  threshold = 0.78,
  onThresholdChange,
  onAfterQuery,
  initialPrompt,
  onClearInitialPrompt,
}) {
  const [promptInput, setPromptInput] = useState("");
  const [sampleIndex, setSampleIndex] = useState(0);
  const [cacheMode, setCacheMode] = useState("auto"); // "auto" | "bypass"
  const [showModeMenu, setShowModeMenu] = useState(false);
  const [autoExpandTrace, setAutoExpandTrace] = useState(false);
  const [expandedTraces, setExpandedTraces] = useState({});
  const [history, setHistory] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState(null);
  const textareaRef = useRef(null);
  const abortControllerRef = useRef(null);

  useEffect(() => {
    if (initialPrompt && initialPrompt.trim()) {
      const toRun = initialPrompt;
      if (onClearInitialPrompt) {
        onClearInitialPrompt();
      }
      handleSendPrompt(toRun);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [initialPrompt]);

  function handleCycleSamplePrompt() {
    const nextPrompt =
      SAMPLE_PROMPTS_CYCLE[sampleIndex % SAMPLE_PROMPTS_CYCLE.length];
    setPromptInput(nextPrompt);
    setSampleIndex((prev) => prev + 1);
    if (textareaRef.current) {
      textareaRef.current.focus();
    }
  }

  function handleStopExecution() {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
    setIsLoading(false);
  }

  async function handleSendPrompt(overridePrompt) {
    const queryText =
      overridePrompt !== undefined ? overridePrompt : promptInput;
    if (!queryText || !queryText.trim() || isLoading) return;

    const controller = new AbortController();
    abortControllerRef.current = controller;

    setIsLoading(true);
    setErrorMsg(null);
    if (overridePrompt === undefined) {
      setPromptInput("");
    }

    try {
      const data =
        cacheMode === "bypass"
          ? await processPromptNoCache(queryText, {
              signal: controller.signal,
            })
          : await processPrompt(queryText, { signal: controller.signal });

      const id = `${Date.now()}-${Math.random().toString(36).slice(2, 6)}`;
      const entry = {
        id,
        prompt: queryText,
        timestamp: new Date().toLocaleTimeString([], {
          hour: "2-digit",
          minute: "2-digit",
          second: "2-digit",
        }),
        mode: cacheMode,
        ...data,
      };

      setHistory((prev) => [...prev, entry]);
      if (autoExpandTrace) {
        setExpandedTraces((prev) => ({ ...prev, [id]: true }));
      }
      if (onAfterQuery) {
        onAfterQuery();
      }
    } catch (err) {
      if (err?.name === "AbortError") {
        return;
      }
      setErrorMsg(
        err.message || "Request failed. Ensure the API server is running."
      );
    } finally {
      if (abortControllerRef.current === controller) {
        abortControllerRef.current = null;
      }
      setIsLoading(false);
    }
  }

  function handleKeyDown(e) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSendPrompt();
    }
  }

  function toggleTrace(id) {
    setExpandedTraces((prev) => ({
      ...prev,
      [id]: !prev[id],
    }));
  }

  function renderPerformancePill(item) {
    const lat = Number(item.latency_ms || 0).toFixed(
      Number(item.latency_ms || 0) < 10 ? 1 : 0
    );
    const simPct = Math.round(Number(item.similarity || 0) * 100);

    if (item.temporal_bypass) {
      return (
        <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium bg-amber-50 dark:bg-amber-500/15 text-amber-700 dark:text-amber-300 border border-amber-200 dark:border-amber-500/30 shadow-sm">
          <span>🕒</span>
          <span>Real-Time Bypass · {lat}ms · Fresh LLM response</span>
        </span>
      );
    }
    if (item.guard_blocked) {
      return (
        <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium bg-amber-50 dark:bg-amber-500/15 text-amber-700 dark:text-amber-300 border border-amber-200 dark:border-amber-500/30 shadow-sm">
          <span>🛡️</span>
          <span>
            Guardrail Protected · Blocked {simPct}% false match
          </span>
        </span>
      );
    }
    if (item.from_cache && item.cache_tier === 1) {
      return (
        <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium bg-emerald-50 dark:bg-emerald-500/15 text-emerald-700 dark:text-emerald-300 border border-emerald-200 dark:border-emerald-500/30 shadow-sm">
          <span>⚡</span>
          <span>Tier-1 Exact Hit · {lat}ms · 100% match</span>
        </span>
      );
    }
    if (item.from_cache && item.cache_tier === 2) {
      return (
        <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium bg-indigo-50 dark:bg-indigo-500/15 text-indigo-700 dark:text-indigo-300 border border-indigo-200 dark:border-indigo-500/30 shadow-sm">
          <span>✦</span>
          <span>
            Tier-2 Semantic Hit · {lat}ms · {simPct}% similarity
          </span>
        </span>
      );
    }
    return (
      <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium bg-rose-50 dark:bg-rose-500/15 text-rose-700 dark:text-rose-300 border border-rose-200 dark:border-rose-500/30 shadow-sm">
        <span>●</span>
        <span>
          {item.model && !item.model.includes("fallback")
            ? item.model
            : "Gemini 3.8 Flash"}{" "}
          · {lat}ms ·{" "}
          {item.mode === "bypass" ? "No-Cache Mode" : "Cached for future"}
        </span>
      </span>
    );
  }

  function renderComposer(isDocked = false) {
    return (
      <div
        className={`w-full ${
          isDocked ? "max-w-3xl" : "max-w-2xl"
        } mx-auto relative`}
      >
        <div className="rainbow-prompt-box rounded-3xl p-4">
          <textarea
            ref={textareaRef}
            rows={isDocked ? 2 : 3}
            value={promptInput}
            onChange={(e) => setPromptInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask Anything..."
            className="w-full bg-transparent text-zinc-800 dark:text-zinc-100 placeholder-zinc-400 dark:placeholder-zinc-500 text-base leading-relaxed outline-none resize-none px-1"
          />

          {/* Bottom Bar inside the Prompt Box */}
          <div className="flex items-center justify-between gap-2 flex-wrap sm:flex-nowrap pt-3 mt-1">
            {/* Left Side: Circular + Button & Pill Selector */}
            <div className="flex items-center gap-2 relative">
              <button
                type="button"
                onClick={handleCycleSamplePrompt}
                title="Cycle sample verification prompt"
                className="w-9 h-9 shrink-0 rounded-full bg-zinc-100 dark:bg-white/[0.08] hover:bg-indigo-50 dark:hover:bg-indigo-500/20 text-zinc-700 dark:text-zinc-200 hover:text-indigo-600 dark:hover:text-indigo-300 flex items-center justify-center hover:rotate-90 hover:scale-105 active:scale-95 transition-all duration-300 cursor-pointer"
              >
                <Plus className="w-4 h-4" />
              </button>

              <button
                type="button"
                onClick={() => setShowModeMenu((prev) => !prev)}
                className="bg-zinc-100/90 dark:bg-white/[0.08] hover:bg-indigo-50/80 dark:hover:bg-indigo-500/20 text-zinc-800 dark:text-zinc-200 hover:text-indigo-950 dark:hover:text-white text-xs font-medium px-3 py-1.5 sm:px-3.5 sm:py-2 rounded-full border border-transparent focus:outline-none focus-visible:ring-2 focus-visible:ring-indigo-200 dark:focus-visible:ring-indigo-400/40 flex items-center gap-1.5 hover:scale-[1.02] active:scale-95 transition-all duration-200 cursor-pointer whitespace-nowrap"
              >
                <span>
                  {cacheMode === "auto"
                    ? `⚡ Auto · ${Number(threshold).toFixed(2)}`
                    : "● Bypass Cache"}
                </span>
                <ChevronDown className="w-3.5 h-3.5 text-zinc-500 dark:text-zinc-400" />
              </button>

              {showModeMenu && (
                <div className="absolute left-0 bottom-12 w-64 max-w-[calc(100vw-3rem)] rounded-2xl bg-white/95 dark:bg-[#10131E]/95 backdrop-blur-2xl border border-black/[0.08] dark:border-white/[0.1] p-3.5 shadow-[0_20px_50px_rgba(15,23,42,0.12)] dark:shadow-[0_20px_50px_rgba(0,0,0,0.65)] space-y-3 z-30 animate-fade-up">
                  <div className="text-[11px] font-medium uppercase tracking-wider text-zinc-400 dark:text-zinc-500">
                    Routing Mode
                  </div>

                  <div className="space-y-1">
                    <button
                      type="button"
                      onClick={() => {
                        setCacheMode("auto");
                        setShowModeMenu(false);
                      }}
                      className={`w-full text-left px-3 py-2 rounded-xl text-xs flex items-center justify-between transition cursor-pointer ${
                        cacheMode === "auto"
                          ? "sidebar-item-active text-indigo-950 dark:text-white font-semibold"
                          : "text-zinc-600 dark:text-zinc-300 hover:bg-zinc-100 dark:hover:bg-white/[0.06]"
                      }`}
                    >
                      <span>⚡ Auto (3-Tier Semantic)</span>
                      {cacheMode === "auto" && <span>✓</span>}
                    </button>

                    <button
                      type="button"
                      onClick={() => {
                        setCacheMode("bypass");
                        setShowModeMenu(false);
                      }}
                      className={`w-full text-left px-3 py-2 rounded-xl text-xs flex items-center justify-between transition cursor-pointer ${
                        cacheMode === "bypass"
                          ? "sidebar-item-active text-indigo-950 dark:text-white font-semibold"
                          : "text-zinc-600 dark:text-zinc-300 hover:bg-zinc-100 dark:hover:bg-white/[0.06]"
                      }`}
                    >
                      <span>● Direct LLM (Bypass Cache)</span>
                      {cacheMode === "bypass" && <span>✓</span>}
                    </button>
                  </div>

                  {onThresholdChange && (
                    <div className="pt-2 border-t border-black/[0.06] dark:border-white/[0.08] space-y-1.5">
                      <div className="flex justify-between text-xs">
                        <span className="text-zinc-500 dark:text-zinc-400">
                          Cosine Threshold
                        </span>
                        <span className="font-mono font-semibold text-indigo-600 dark:text-indigo-300">
                          {Number(threshold).toFixed(2)}
                        </span>
                      </div>
                      <input
                        type="range"
                        min="0.50"
                        max="0.95"
                        step="0.01"
                        value={threshold}
                        onChange={(e) => onThresholdChange(e.target.value)}
                        className="w-full accent-indigo-600 cursor-pointer h-1.5 bg-zinc-200 dark:bg-white/[0.12] rounded-lg"
                      />
                    </div>
                  )}
                </div>
              )}
            </div>

            {/* Right Side: Trace Toggle Icon + Reactive Gradient Send Button */}
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={() => setAutoExpandTrace((prev) => !prev)}
                title={
                  autoExpandTrace
                    ? "Auto-expand routing trace: ON"
                    : "Auto-expand routing trace: OFF"
                }
                className={`w-9 h-9 rounded-full flex items-center justify-center hover:scale-105 active:scale-95 transition-all duration-200 cursor-pointer ${
                  autoExpandTrace
                    ? "bg-indigo-100 dark:bg-indigo-500/25 text-indigo-700 dark:text-indigo-300 shadow-sm"
                    : "bg-zinc-100 dark:bg-white/[0.08] hover:bg-zinc-200 dark:hover:bg-white/[0.14] text-zinc-700 dark:text-zinc-200"
                }`}
              >
                <SlidersHorizontal className="w-4 h-4" />
              </button>

              {history.length > 0 && (
                <button
                  type="button"
                  onClick={() => {
                    setHistory([]);
                    setExpandedTraces({});
                    setErrorMsg(null);
                  }}
                  title="Clear conversation"
                  className="w-9 h-9 rounded-full bg-zinc-100 dark:bg-white/[0.08] hover:bg-rose-50 dark:hover:bg-rose-500/20 text-zinc-700 dark:text-zinc-200 hover:text-rose-600 dark:hover:text-rose-300 flex items-center justify-center hover:scale-105 active:scale-95 transition-all duration-200 cursor-pointer"
                >
                  <RotateCcw className="w-4 h-4" />
                </button>
              )}

              {isLoading ? (
                <button
                  type="button"
                  onClick={handleStopExecution}
                  title="Stop current execution"
                  className="bg-gradient-to-r from-rose-500 to-pink-600 hover:from-rose-600 hover:to-pink-700 text-white rounded-full px-4 py-2 sm:px-5 sm:py-2.5 text-xs font-medium shadow-md hover:shadow-lg hover:scale-[1.03] active:scale-95 transition-all flex items-center gap-2 cursor-pointer"
                >
                  <span className="relative flex items-center justify-center w-3.5 h-3.5">
                    <span className="absolute inset-0 rounded-full border-2 border-white/35 border-t-white animate-spin" />
                    <Square className="w-2 h-2 fill-current" />
                  </span>
                  <span>Stop</span>
                </button>
              ) : (
                <button
                  type="button"
                  disabled={!promptInput.trim()}
                  onClick={() => handleSendPrompt()}
                  className="group bg-gradient-to-r from-indigo-600 via-violet-600 to-fuchsia-600 text-white rounded-full px-4 py-2 sm:px-5 sm:py-2.5 text-xs font-medium flex items-center justify-center gap-1.5 shadow-md hover:shadow-lg hover:scale-[1.03] active:scale-95 disabled:opacity-40 disabled:hover:scale-100 transition-all duration-200 cursor-pointer"
                >
                  <span>Send</span>
                  <ArrowUpRight className="w-3.5 h-3.5 group-hover:translate-x-0.5 group-hover:-translate-y-0.5 transition-transform duration-200" />
                </button>
              )}
            </div>
          </div>
        </div>

        {errorMsg && (
          <div className="mt-3 px-4 py-2.5 rounded-2xl bg-rose-50 dark:bg-rose-500/15 border border-rose-200 dark:border-rose-500/30 text-xs text-rose-700 dark:text-rose-300 text-center animate-fade-up">
            {errorMsg}
          </div>
        )}
      </div>
    );
  }

  // --- EMPTY / CENTERED HERO STATE ---
  if (history.length === 0) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center w-full min-w-0 px-3.5 sm:px-6 py-6 md:py-12 overflow-x-hidden">
        <div className="flex flex-col items-center text-center w-full max-w-2xl">
          {/* Stylized Calligraphic "Semantiq" Brand Wordmark with Ambient Pastel Halo */}
          <div className="relative flex items-center justify-center mb-3">
            <div
              aria-hidden="true"
              className="pointer-events-none absolute -inset-x-10 -inset-y-4 rounded-full bg-gradient-to-r from-indigo-300/30 via-fuchsia-300/30 to-cyan-300/30 dark:from-indigo-500/25 dark:via-fuchsia-500/25 dark:to-cyan-500/25 blur-2xl opacity-80"
            />
            <div className="relative text-4xl sm:text-5xl md:text-6xl brand-calligraphic select-none cursor-default hover:scale-105 hover:-translate-y-0.5 transition-all duration-500">
              Semantiq
            </div>
          </div>

          {/* Two-Line Greeting Header */}
          <div className="text-sm font-medium text-zinc-500 dark:text-zinc-400 mb-1.5">
            Hey! Semantiq Cache Engine 👋
          </div>
          <h1 className="text-2xl sm:text-3xl md:text-4xl px-2 text-center leading-tight font-semibold tracking-tight text-zinc-900 dark:text-zinc-100 mb-6 sm:mb-8">
            Ask Anything, Cached{" "}
            <span className="bg-gradient-to-r from-indigo-600 via-fuchsia-600 to-cyan-500 dark:from-indigo-400 dark:via-fuchsia-400 dark:to-cyan-300 bg-clip-text text-transparent">
              Instantly
            </span>
          </h1>

          {/* Prismatic Rainbow-Border Prompt Box */}
          {renderComposer(false)}

          {/* 5 Natural Question Suggestions Below the Prompt Box */}
          <div className="flex flex-wrap justify-center gap-2.5 max-w-2xl w-full mt-6">
            {QUESTION_SUGGESTIONS.map((item) => {
              const Icon = item.icon;
              return (
                <button
                  key={item.prompt}
                  type="button"
                  disabled={isLoading}
                  onClick={() => handleSendPrompt(item.prompt)}
                  className="group w-full sm:w-auto justify-between sm:justify-start text-left text-xs sm:text-sm bg-white/80 dark:bg-white/[0.04] hover:bg-white dark:hover:bg-white/[0.08] backdrop-blur-xl border border-black/[0.06] dark:border-white/[0.09] hover:border-indigo-200/80 dark:hover:border-indigo-400/35 rounded-2xl px-3.5 sm:px-4 py-2.5 text-zinc-700 dark:text-zinc-200 hover:text-indigo-950 dark:hover:text-white shadow-[0_2px_12px_rgb(0,0,0,0.03)] hover:shadow-[0_10px_25px_-6px_rgba(99,102,241,0.16)] dark:hover:shadow-[0_10px_25px_-6px_rgba(99,102,241,0.3)] hover:-translate-y-0.5 active:scale-95 transition-all duration-200 flex items-center gap-2.5 cursor-pointer disabled:opacity-50 disabled:pointer-events-none"
                >
                  <span className="flex items-center gap-2.5 min-w-0">
                    <span
                      className={`w-6 h-6 rounded-lg border flex items-center justify-center shrink-0 transition-transform duration-200 group-hover:scale-110 ${item.iconColor}`}
                    >
                      <Icon className="w-3.5 h-3.5" />
                    </span>
                    <span className="leading-snug">{item.prompt}</span>
                  </span>
                  <ArrowRight className="w-3.5 h-3.5 text-indigo-500 dark:text-indigo-400 opacity-50 -translate-x-0.5 group-hover:opacity-100 group-hover:translate-x-0.5 transition-all duration-200 shrink-0" />
                </button>
              );
            })}
          </div>
        </div>
      </div>
    );
  }

  // --- ACTIVE CONVERSATION / RESPONSE CARDS ---
  return (
    <div className="flex-1 flex flex-col justify-between max-w-3xl w-full min-w-0 mx-auto px-3.5 sm:px-6 py-6 md:py-8 gap-6 overflow-x-hidden">
      <div className="space-y-5">
        {history.map((item) => {
          const isTraceOpen = Boolean(expandedTraces[item.id]);
          const followUps = getFollowUpsForPrompt(item.prompt);
          const simVal = Number(item.similarity || 0);

          return (
            <div
              key={item.id}
              className="semantiq-card rounded-3xl p-6 space-y-4 animate-fade-up"
            >
              {/* User Query Header */}
              <div className="flex items-start justify-between gap-4 border-b border-black/[0.06] dark:border-white/[0.08] pb-3.5">
                <div className="text-base font-semibold text-zinc-900 dark:text-zinc-100">
                  {item.prompt}
                </div>
                <span className="text-[11px] font-mono text-zinc-400 dark:text-zinc-500 shrink-0">
                  {item.timestamp}
                </span>
              </div>

              {/* Performance Pill + Expandable Trace Toggle */}
              <div className="flex flex-wrap items-center justify-between gap-3">
                {renderPerformancePill(item)}

                <button
                  type="button"
                  onClick={() => toggleTrace(item.id)}
                  className="inline-flex items-center gap-1.5 text-xs font-medium text-zinc-500 dark:text-zinc-400 hover:text-indigo-600 dark:hover:text-indigo-300 transition cursor-pointer"
                >
                  <span>Inspect Routing Trace</span>
                  {isTraceOpen ? (
                    <ChevronUp className="w-3.5 h-3.5" />
                  ) : (
                    <ChevronDown className="w-3.5 h-3.5" />
                  )}
                </button>
              </div>

              {/* Response Content */}
              <div className="text-sm md:text-[15px] text-zinc-700 dark:text-zinc-300 leading-relaxed whitespace-pre-line">
                {item.response}
              </div>

              {/* Expandable 3-Stage Pipeline Breakdown Drawer */}
              {isTraceOpen && (
                <div className="mt-3 pt-4 border-t border-black/[0.06] dark:border-white/[0.08] space-y-3 text-xs animate-fade-up">
                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-2.5 font-mono">
                    {/* Stage 1 */}
                    <div
                      className={`p-3 rounded-2xl border ${
                        item.from_cache && item.cache_tier === 1
                          ? "bg-emerald-50/80 dark:bg-emerald-500/15 border-emerald-200 dark:border-emerald-500/30 text-emerald-900 dark:text-emerald-200"
                          : "bg-zinc-50 dark:bg-white/[0.03] border-black/[0.05] dark:border-white/[0.08] text-zinc-500 dark:text-zinc-400"
                      }`}
                    >
                      <div className="flex items-center justify-between mb-1">
                        <span className="flex items-center gap-1.5 font-semibold text-zinc-800 dark:text-zinc-100">
                          <Zap className="w-3.5 h-3.5 text-emerald-600 dark:text-emerald-400" />{" "}
                          Tier-1 Exact
                        </span>
                        <span className="font-semibold">
                          {item.temporal_bypass
                            ? "BYPASSED"
                            : item.from_cache && item.cache_tier === 1
                            ? "HIT"
                            : "MISS"}
                        </span>
                      </div>
                      <div className="text-[11px] text-zinc-500 dark:text-zinc-400 truncate">
                        Norm: &ldquo;
                        {item.pipeline_trace?.normalized_prompt ||
                          item.prompt?.trim().toLowerCase()}
                        &rdquo;
                      </div>
                    </div>

                    {/* Stage 2 */}
                    <div
                      className={`p-3 rounded-2xl border ${
                        item.from_cache && item.cache_tier === 2
                          ? "bg-indigo-50/80 dark:bg-indigo-500/15 border-indigo-200 dark:border-indigo-500/30 text-indigo-900 dark:text-indigo-200"
                          : item.guard_blocked
                          ? "bg-amber-50 dark:bg-amber-500/15 border-amber-200 dark:border-amber-500/30 text-amber-900 dark:text-amber-200"
                          : "bg-zinc-50 dark:bg-white/[0.03] border-black/[0.05] dark:border-white/[0.08] text-zinc-500 dark:text-zinc-400"
                      }`}
                    >
                      <div className="flex items-center justify-between mb-1">
                        <span className="flex items-center gap-1.5 font-semibold text-zinc-800 dark:text-zinc-100">
                          <Database className="w-3.5 h-3.5 text-indigo-600 dark:text-indigo-400" />{" "}
                          Tier-2 Cosine
                        </span>
                        <span className="font-semibold">
                          {item.from_cache && item.cache_tier === 1
                            ? "SKIPPED"
                            : item.from_cache && item.cache_tier === 2
                            ? "HIT"
                            : item.guard_blocked
                            ? "BLOCKED"
                            : "MISS"}
                        </span>
                      </div>
                      <div className="text-[11px] text-zinc-500 dark:text-zinc-400">
                        Sim: {simVal.toFixed(4)} · Emb:{" "}
                        {Number(item.embedding_time_ms || 0).toFixed(1)}ms
                      </div>
                    </div>

                    {/* Stage 3 */}
                    <div
                      className={`p-3 rounded-2xl border ${
                        !item.from_cache
                          ? "bg-rose-50/80 dark:bg-rose-500/15 border-rose-200 dark:border-rose-500/30 text-rose-900 dark:text-rose-200"
                          : "bg-zinc-50 dark:bg-white/[0.03] border-black/[0.05] dark:border-white/[0.08] text-zinc-500 dark:text-zinc-400"
                      }`}
                    >
                      <div className="flex items-center justify-between mb-1">
                        <span className="flex items-center gap-1.5 font-semibold text-zinc-800 dark:text-zinc-100">
                          <Cpu className="w-3.5 h-3.5 text-rose-600 dark:text-rose-400" />{" "}
                          Tier-3 Gemini
                        </span>
                        <span className="font-semibold">
                          {!item.from_cache ? "CALLED" : "SAVED"}
                        </span>
                      </div>
                      <div className="text-[11px] text-zinc-500 dark:text-zinc-400 truncate">
                        Total: {Number(item.latency_ms || 0).toFixed(2)}ms
                      </div>
                    </div>
                  </div>

                  {/* Cosine Similarity Progress Bar */}
                  <div className="p-3 rounded-2xl bg-zinc-50 dark:bg-white/[0.03] border border-black/[0.05] dark:border-white/[0.08] space-y-1.5 font-mono">
                    <div className="flex flex-wrap items-center justify-between gap-1.5 text-[11px] text-zinc-500 dark:text-zinc-400">
                      <span>
                        Cosine Similarity: {simVal.toFixed(4)} (Threshold:{" "}
                        {Number(threshold).toFixed(2)})
                      </span>
                      {item.matched_prompt && (
                        <span className="text-zinc-700 dark:text-zinc-300 truncate max-w-full sm:max-w-[280px]">
                          Nearest: &ldquo;{item.matched_prompt}&rdquo;
                        </span>
                      )}
                    </div>
                    <div className="relative h-2 w-full rounded-full bg-zinc-200 dark:bg-white/[0.12] overflow-hidden">
                      <div
                        className={`h-full rounded-full transition-all duration-500 ${
                          item.guard_blocked
                            ? "bg-amber-500"
                            : "bg-gradient-to-r from-indigo-500 to-emerald-500"
                        }`}
                        style={{
                          width: `${Math.min(100, Math.max(2, simVal * 100))}%`,
                        }}
                      />
                      <div
                        className="absolute top-0 bottom-0 w-0.5 bg-zinc-900 dark:bg-white"
                        style={{
                          left: `${Math.min(99, Math.max(1, threshold * 100))}%`,
                        }}
                      />
                    </div>
                  </div>

                  {item.guard_blocked && item.guard_reason && (
                    <div className="p-3 rounded-2xl bg-amber-50 dark:bg-amber-500/15 border border-amber-200 dark:border-amber-500/30 text-amber-800 dark:text-amber-200 flex items-center gap-2 font-mono text-[11px]">
                      <ShieldAlert className="w-4 h-4 shrink-0 text-amber-600 dark:text-amber-400" />
                      <span>Guardrail Reason: {item.guard_reason}</span>
                    </div>
                  )}

                  {item.pipeline_trace?.cascade_attempts?.length > 0 && (
                    <div className="p-3 rounded-2xl bg-zinc-50 dark:bg-white/[0.03] border border-black/[0.05] dark:border-white/[0.08] space-y-2 font-mono text-[11px]">
                      <div className="flex flex-wrap items-center justify-between gap-1.5 text-zinc-600 dark:text-zinc-300 font-semibold">
                        <span>Tier-3 Gemini Failover Cascade (15.0s timeout/node)</span>
                        <span className="text-indigo-600 dark:text-indigo-300">
                          {item.pipeline_trace.cascade_step}
                        </span>
                      </div>
                      <div className="space-y-1">
                        {item.pipeline_trace.cascade_attempts.map((att, idx) => (
                          <div
                            key={`${att.step}-${idx}`}
                            className="flex flex-wrap items-center justify-between gap-1.5 px-2.5 py-1.5 rounded-xl bg-white/80 dark:bg-white/[0.04] border border-black/[0.04] dark:border-white/[0.06]"
                          >
                            <span className="text-zinc-700 dark:text-zinc-200 truncate">
                              {att.step}
                            </span>
                            <span
                              className={
                                att.succeeded
                                  ? "text-emerald-600 dark:text-emerald-400 font-semibold"
                                  : "text-amber-600 dark:text-amber-400"
                              }
                            >
                              {att.succeeded
                                ? `✓ ${Number(att.latency_ms || 0).toFixed(0)}ms`
                                : `↷ ${att.reason || "failover"} (${Number(att.latency_ms || 0).toFixed(0)}ms)`}
                            </span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              )}

              {/* Contextual 1-Click Follow-Up Chips */}
              {followUps.length > 0 && (
                <div className="pt-2 flex flex-wrap items-center gap-2">
                  <span className="text-[11px] font-medium text-zinc-400 dark:text-zinc-500">
                    Try next:
                  </span>
                  {followUps.map((f) => (
                    <button
                      key={f.label}
                      type="button"
                      disabled={isLoading}
                      onClick={() => handleSendPrompt(f.prompt)}
                      className="px-3.5 py-1.5 rounded-full bg-indigo-50/70 dark:bg-indigo-500/15 hover:bg-indigo-100/80 dark:hover:bg-indigo-500/25 border border-indigo-200/60 dark:border-indigo-400/30 text-xs font-medium text-indigo-700 dark:text-indigo-300 hover:text-indigo-950 dark:hover:text-white hover:-translate-y-0.5 active:translate-y-0 transition-all duration-200 cursor-pointer"
                    >
                      {f.label} →
                    </button>
                  ))}
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* Bottom Docked Rainbow-Border Composer */}
      <div className="sticky bottom-5 pt-2">{renderComposer(true)}</div>
    </div>
  );
}
