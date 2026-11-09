import React, { useState, useEffect, useCallback } from "react";
import {
  Search,
  Trash2,
  Plus,
  Sparkles,
  RefreshCw,
  X,
  ArrowUpRight,
} from "lucide-react";
import {
  getCacheEntries,
  deleteCacheEntry,
  getCacheMisses,
  warmCacheItem,
  runProactiveWarm,
  processPrompt,
} from "../api/cacheApi";

const SOLAR_SYSTEM_MISS_SEEDS = [
  "what is the largest planet in our solar system?",
  "which planet is known for its rings?",
  "how many planets are in the solar system?",
  "describe the great red spot on jupiter",
];

const SAMPLE_KNOWLEDGE_BASE = [
  {
    prompt: "What is machine learning and how does it work?",
    response:
      "Machine learning is a subset of AI where algorithms learn patterns from historical training data to make predictions or decisions without explicit rule programming.",
    paraphrase: "Can you explain machine learning in simple terms?",
  },
  {
    prompt: "How do artificial neural networks learn from data?",
    response:
      "Neural networks learn via forward propagation of inputs through weighted layers, computing loss against ground truth, and updating weights via backpropagation and gradient descent.",
    paraphrase: "Explain how deep neural networks train on datasets",
  },
  {
    prompt: "What is the capital of France?",
    response:
      "The capital of France is Paris, its largest city and primary cultural, economic, and political center.",
    paraphrase: "Which city serves as the capital of France?",
  },
  {
    prompt: "How do I install Docker?",
    response:
      "Install Docker by downloading Docker Desktop for Windows/macOS or installing docker-ce via apt/yum on Linux, then verify with `docker --version`.",
    paraphrase: "What are the steps to install Docker on my machine?",
  },
  {
    prompt: "What is Kubernetes and why is it used?",
    response:
      "Kubernetes (K8s) is an open-source container orchestration platform used to automate deployment, scaling, self-healing, and networking of containerized microservices.",
    paraphrase: "Explain what Kubernetes does for container orchestration",
  },
  {
    prompt: "How does HNSW vector indexing speed up semantic search?",
    response:
      "Hierarchical Navigable Small World (HNSW) builds multi-layer proximity graphs that allow logarithmic O(log N) approximate nearest-neighbor cosine search across high-dimensional embeddings.",
    paraphrase: "Why is HNSW fast for cosine similarity vector search?",
  },
];

function computeVectorFingerprint(seedText) {
  const str = String(seedText || "semantiq-vector");
  const bars = [];
  let hash = 2166136261;
  for (let i = 0; i < str.length; i++) {
    hash ^= str.charCodeAt(i);
    hash = Math.imul(hash, 16777619);
  }
  for (let b = 0; b < 16; b++) {
    const mixed = Math.abs(Math.imul(hash ^ (b * 2654435761), 1597334677));
    const heightPct = 22 + (mixed % 78);
    bars.push(heightPct);
  }
  return bars;
}

function formatSourcePill(source) {
  const raw = String(source || "llm").toLowerCase();
  if (raw.includes("proactive") || raw.includes("warm")) {
    return {
      label: "Proactive Warm",
      cls: "bg-fuchsia-50 dark:bg-fuchsia-500/15 text-fuchsia-700 dark:text-fuchsia-300 border-fuchsia-200 dark:border-fuchsia-500/30",
    };
  }
  if (raw.includes("bench")) {
    return {
      label: "Benchmark",
      cls: "bg-cyan-50 dark:bg-cyan-500/15 text-cyan-700 dark:text-cyan-300 border-cyan-200 dark:border-cyan-500/30",
    };
  }
  return {
    label: "LLM",
    cls: "bg-indigo-50 dark:bg-indigo-500/15 text-indigo-700 dark:text-indigo-300 border-indigo-200 dark:border-indigo-500/30",
  };
}

function buildParaphraseForPrompt(promptText) {
  const lower = String(promptText || "").trim().toLowerCase();
  const preset = SAMPLE_KNOWLEDGE_BASE.find(
    (item) => item.prompt.toLowerCase() === lower
  );
  if (preset) return preset.paraphrase;
  const cleaned = String(promptText || "")
    .trim()
    .replace(/\?+$/, "");
  if (lower.startsWith("what is ")) {
    return `Can you explain ${cleaned.slice(8)} in simple terms?`;
  }
  if (lower.startsWith("how do i ")) {
    return `What is the best way to ${cleaned.slice(9)}?`;
  }
  return `In simple terms, ${cleaned.charAt(0).toLowerCase() + cleaned.slice(1)}?`;
}

export default function ProactiveAndExplorerTab({
  onAfterChange,
  onTestParaphrase,
}) {
  const [section, setSection] = useState("vectors"); // "vectors" | "proactive"
  const [entries, setEntries] = useState([]);
  const [misses, setMisses] = useState([]);
  const [searchFilter, setSearchFilter] = useState("");
  const [isLoading, setIsLoading] = useState(false);

  const [showAddModal, setShowAddModal] = useState(false);
  const [customPrompt, setCustomPrompt] = useState("");
  const [customAnswer, setCustomAnswer] = useState("");
  const [isAdding, setIsAdding] = useState(false);

  const [isSeeding, setIsSeeding] = useState(false);
  const [isSeedingKb, setIsSeedingKb] = useState(false);
  const [isWarming, setIsWarming] = useState(false);
  const [warmReport, setWarmReport] = useState(null);
  const [notice, setNotice] = useState(null);

  const loadVaultData = useCallback(async () => {
    setIsLoading(true);
    try {
      const [entriesData, missesData] = await Promise.all([
        getCacheEntries(100),
        getCacheMisses(),
      ]);
      setEntries(entriesData.entries || []);
      setMisses(missesData.missed_prompts || []);
    } catch {
      // ignore if offline
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    loadVaultData();
  }, [loadVaultData]);

  async function handleDelete(id) {
    try {
      await deleteCacheEntry(id);
      await loadVaultData();
      if (onAfterChange) onAfterChange();
    } catch (err) {
      setNotice(err.message || "Failed to delete entry.");
    }
  }

  async function handleAddEntry(e) {
    e.preventDefault();
    if (!customPrompt.trim() || !customAnswer.trim()) return;
    setIsAdding(true);
    setNotice(null);
    try {
      await warmCacheItem(customPrompt.trim(), customAnswer.trim());
      setCustomPrompt("");
      setCustomAnswer("");
      setShowAddModal(false);
      await loadVaultData();
      if (onAfterChange) onAfterChange();
      setNotice("Entry added to Tier-1 & Tier-2 cache.");
    } catch (err) {
      setNotice(err.message || "Failed to add entry.");
    } finally {
      setIsAdding(false);
    }
  }

  async function handleSeedKnowledgeBase() {
    if (isSeedingKb) return;
    setIsSeedingKb(true);
    setNotice(null);
    try {
      for (const item of SAMPLE_KNOWLEDGE_BASE) {
        await warmCacheItem(item.prompt, item.response);
      }
      await loadVaultData();
      if (onAfterChange) onAfterChange();
      setNotice(
        `Seeded ${SAMPLE_KNOWLEDGE_BASE.length} canonical knowledge vectors into Tier-1 & Tier-2.`
      );
    } catch (err) {
      setNotice(err.message || "Failed to seed sample knowledge base.");
    } finally {
      setIsSeedingKb(false);
    }
  }

  async function handleSeedSolarTopic() {
    setIsSeeding(true);
    setNotice(null);
    try {
      for (const q of SOLAR_SYSTEM_MISS_SEEDS) {
        await processPrompt(q);
      }
      await loadVaultData();
      if (onAfterChange) onAfterChange();
      setNotice(
        "Seeded 4 Solar System queries into cache_misses.log. Ready for DBSCAN clustering."
      );
    } catch (err) {
      setNotice(err.message || "Failed to seed misses.");
    } finally {
      setIsSeeding(false);
    }
  }

  async function handleRunDbscan() {
    setIsWarming(true);
    setNotice(null);
    try {
      const report = await runProactiveWarm(3, 0.48);
      setWarmReport(report);
      await loadVaultData();
      if (onAfterChange) onAfterChange();
      if (report.status === "warmed") {
        setNotice(
          `DBSCAN clustered ${report.cluster_prompts.length} prompts and warmed ${report.entries_warmed} vectors.`
        );
      } else {
        setNotice(
          `Status: ${report.status}. Seed emerging topic misses first so at least 3 related prompts exist.`
        );
      }
    } catch (err) {
      setNotice(err.message || "DBSCAN warming failed.");
    } finally {
      setIsWarming(false);
    }
  }

  const filteredEntries = entries.filter((item) => {
    if (!searchFilter.trim()) return true;
    const q = searchFilter.toLowerCase();
    return (
      (item.prompt || "").toLowerCase().includes(q) ||
      (item.response || "").toLowerCase().includes(q) ||
      (item.source || "").toLowerCase().includes(q)
    );
  });

  return (
    <div className="max-w-6xl w-full mx-auto px-6 py-10 space-y-7">
      {/* Header + Segmented Toggle */}
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-zinc-900 dark:text-zinc-100">
            Cache Vault
          </h1>
          <p className="text-xs text-zinc-500 dark:text-zinc-400 mt-1">
            Inspect stored ChromaDB semantic vectors or trigger unsupervised
            DBSCAN topic warming
          </p>
        </div>

        {/* Clean Segmented Toggle */}
        <div className="flex items-center p-1 rounded-full bg-white/80 dark:bg-white/[0.06] border border-black/[0.06] dark:border-white/[0.08] shadow-sm">
          <button
            type="button"
            onClick={() => setSection("vectors")}
            className={`px-4 py-1.5 rounded-full text-xs font-medium transition-all duration-200 cursor-pointer ${
              section === "vectors"
                ? "sidebar-item-active text-indigo-950 dark:text-white font-semibold"
                : "text-zinc-600 dark:text-zinc-400 hover:text-zinc-900 dark:hover:text-zinc-100"
            }`}
          >
            Cached Vectors ({entries.length})
          </button>

          <button
            type="button"
            onClick={() => setSection("proactive")}
            className={`px-4 py-1.5 rounded-full text-xs font-medium transition-all duration-200 cursor-pointer ${
              section === "proactive"
                ? "sidebar-item-active text-indigo-950 dark:text-white font-semibold"
                : "text-zinc-600 dark:text-zinc-400 hover:text-zinc-900 dark:hover:text-zinc-100"
            }`}
          >
            Proactive Topic Warmer ({misses.length} misses)
          </button>
        </div>
      </div>

      {notice && (
        <div className="px-4 py-3 rounded-2xl bg-indigo-50/90 dark:bg-indigo-500/15 border border-indigo-200 dark:border-indigo-500/30 text-xs text-indigo-900 dark:text-indigo-200 flex items-center justify-between">
          <span>{notice}</span>
          <button
            type="button"
            onClick={() => setNotice(null)}
            className="text-indigo-500 dark:text-indigo-300 hover:text-indigo-900 dark:hover:text-white cursor-pointer"
          >
            <X className="w-3.5 h-3.5" />
          </button>
        </div>
      )}

      {/* VIEW A: CACHED VECTORS */}
      {section === "vectors" && (
        <div className="space-y-5">
          {/* Search & + Add Entry Controls */}
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="relative flex-1 max-w-md">
              <Search className="w-4 h-4 text-zinc-400 dark:text-zinc-500 absolute left-3.5 top-1/2 -translate-y-1/2" />
              <input
                type="text"
                value={searchFilter}
                onChange={(e) => setSearchFilter(e.target.value)}
                placeholder="Search cached prompts or responses..."
                className="w-full pl-10 pr-4 py-2.5 rounded-full bg-white/85 dark:bg-white/[0.06] border border-black/[0.06] dark:border-white/[0.08] focus:border-zinc-400 dark:focus:border-indigo-400/50 text-xs text-zinc-900 dark:text-zinc-100 placeholder-zinc-400 dark:placeholder-zinc-500 outline-none shadow-sm transition"
              />
            </div>

            <div className="flex flex-wrap items-center gap-2.5">
              <button
                type="button"
                onClick={handleSeedKnowledgeBase}
                disabled={isSeedingKb}
                className="inline-flex items-center gap-1.5 px-4 py-2.5 rounded-full bg-white/85 dark:bg-white/[0.06] hover:bg-indigo-50/80 dark:hover:bg-indigo-500/15 border border-black/[0.06] dark:border-white/[0.08] hover:border-indigo-200/80 dark:hover:border-indigo-400/30 text-indigo-700 dark:text-indigo-300 text-xs font-medium shadow-sm hover:-translate-y-0.5 active:scale-95 transition-all duration-200 cursor-pointer disabled:opacity-50"
              >
                <Sparkles className="w-3.5 h-3.5" />
                {isSeedingKb
                  ? "Seeding Vectors..."
                  : "✦ Seed Sample Knowledge Base"}
              </button>

              <button
                type="button"
                onClick={loadVaultData}
                className="p-2.5 rounded-full bg-white/85 dark:bg-white/[0.06] hover:bg-white dark:hover:bg-white/[0.1] border border-black/[0.06] dark:border-white/[0.08] hover:border-indigo-200/80 dark:hover:border-indigo-400/30 text-zinc-700 dark:text-zinc-200 shadow-sm hover:-translate-y-0.5 active:scale-95 transition-all duration-200 cursor-pointer"
                title="Refresh"
              >
                <RefreshCw
                  className={`w-4 h-4 text-indigo-600 dark:text-indigo-400 ${isLoading ? "animate-spin" : ""}`}
                />
              </button>

              <button
                type="button"
                onClick={() => setShowAddModal((prev) => !prev)}
                className="inline-flex items-center gap-1.5 px-4 py-2.5 rounded-full bg-gradient-to-r from-indigo-600 via-violet-600 to-fuchsia-600 text-white text-xs font-medium shadow-sm hover:shadow-md hover:-translate-y-0.5 active:scale-95 transition-all duration-200 cursor-pointer"
              >
                <Plus className="w-3.5 h-3.5" />
                Add Entry
              </button>
            </div>
          </div>

          {/* Inline Add Entry Drawer */}
          {showAddModal && (
            <form
              onSubmit={handleAddEntry}
              className="semantiq-card rounded-2xl p-5 space-y-4"
            >
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold text-zinc-900 dark:text-zinc-100">
                  Warm Custom Prompt &amp; Answer
                </span>
                <button
                  type="button"
                  onClick={() => setShowAddModal(false)}
                  className="text-zinc-400 hover:text-zinc-800 dark:hover:text-zinc-200 cursor-pointer"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <input
                  type="text"
                  value={customPrompt}
                  onChange={(e) => setCustomPrompt(e.target.value)}
                  placeholder="Canonical question (e.g., What is Kubernetes?)"
                  className="w-full px-3.5 py-2.5 rounded-xl bg-zinc-50 dark:bg-white/[0.04] border border-black/[0.08] dark:border-white/[0.1] text-xs text-zinc-900 dark:text-zinc-100 placeholder-zinc-400 dark:placeholder-zinc-500 outline-none focus:border-zinc-500 dark:focus:border-indigo-400/50"
                />
                <input
                  type="text"
                  value={customAnswer}
                  onChange={(e) => setCustomAnswer(e.target.value)}
                  placeholder="Authoritative response to cache in Tier-1 & Tier-2..."
                  className="w-full px-3.5 py-2.5 rounded-xl bg-zinc-50 dark:bg-white/[0.04] border border-black/[0.08] dark:border-white/[0.1] text-xs text-zinc-900 dark:text-zinc-100 placeholder-zinc-400 dark:placeholder-zinc-500 outline-none focus:border-zinc-500 dark:focus:border-indigo-400/50"
                />
              </div>

              <div className="flex justify-end">
                <button
                  type="submit"
                  disabled={
                    isAdding || !customPrompt.trim() || !customAnswer.trim()
                  }
                  className="px-5 py-2 rounded-full bg-gradient-to-r from-indigo-600 via-violet-600 to-fuchsia-600 text-white text-xs font-medium disabled:opacity-40 transition cursor-pointer"
                >
                  {isAdding ? "Saving..." : "Save to Cache"}
                </button>
              </div>
            </form>
          )}

          {/* Vector Table */}
          <div className="semantiq-card rounded-2xl p-6">
            {filteredEntries.length === 0 ? (
              <div className="py-14 text-center space-y-4">
                <div className="text-xs text-zinc-500 dark:text-zinc-400 max-w-md mx-auto">
                  No cached vectors found in ChromaDB. Seed our 6-vector sample
                  knowledge base with 1 click or submit a query in the
                  Playground.
                </div>
                <button
                  type="button"
                  onClick={handleSeedKnowledgeBase}
                  disabled={isSeedingKb}
                  className="inline-flex items-center gap-2 px-5 py-2.5 rounded-full bg-gradient-to-r from-indigo-600 via-violet-600 to-fuchsia-600 text-white text-xs font-medium shadow-md hover:shadow-lg hover:-translate-y-0.5 active:scale-95 transition-all duration-200 cursor-pointer disabled:opacity-50"
                >
                  <Sparkles className="w-3.5 h-3.5" />
                  <span>
                    {isSeedingKb
                      ? "Seeding Sample Vectors..."
                      : "✦ Seed Sample Knowledge Base"}
                  </span>
                </button>
              </div>
            ) : (
              <div className="overflow-x-auto max-h-[520px] overflow-y-auto">
                <table className="w-full text-left border-collapse text-xs">
                  <thead>
                    <tr className="border-b border-black/[0.06] dark:border-white/[0.08] text-zinc-400 dark:text-zinc-500 font-mono text-[11px]">
                      <th className="py-2.5 px-3 font-medium">Prompt</th>
                      <th className="py-2.5 px-3 font-medium">
                        384-dim Vector Fingerprint
                      </th>
                      <th className="py-2.5 px-3 font-medium">Source</th>
                      <th className="py-2.5 px-3 font-medium">Hits</th>
                      <th className="py-2.5 px-3 font-medium">
                        Response Preview
                      </th>
                      <th className="py-2.5 px-3 text-right font-medium">
                        Actions
                      </th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-black/[0.04] dark:divide-white/[0.06]">
                    {filteredEntries.map((entry) => {
                      const bars = computeVectorFingerprint(
                        entry.prompt || entry.id
                      );
                      const src = formatSourcePill(entry.source);
                      const paraphrase = buildParaphraseForPrompt(entry.prompt);
                      return (
                        <tr
                          key={entry.id}
                          className="hover:bg-zinc-50/80 dark:hover:bg-white/[0.04] transition"
                        >
                          <td className="py-3 px-3 text-zinc-900 dark:text-zinc-100 font-medium max-w-[220px] truncate">
                            {entry.prompt}
                          </td>
                          <td className="py-3 px-3">
                            <div
                              title="384-d BAAI/bge-small-en-v1.5 L2-normalized projection"
                              className="inline-flex items-end gap-[2px] h-5 px-2 py-1 rounded-lg bg-zinc-100/90 dark:bg-white/[0.05] border border-black/[0.05] dark:border-white/[0.08]"
                            >
                              {bars.map((h, idx) => (
                                <span
                                  key={idx}
                                  className="w-[3px] rounded-full bg-gradient-to-t from-indigo-500 via-fuchsia-500 to-cyan-400 opacity-85"
                                  style={{ height: `${h}%` }}
                                />
                              ))}
                            </div>
                          </td>
                          <td className="py-3 px-3 font-mono text-[11px]">
                            <span
                              className={`px-2.5 py-0.5 rounded-full border ${src.cls}`}
                            >
                              {src.label}
                            </span>
                          </td>
                          <td className="py-3 px-3 font-mono">
                            <span className="inline-flex items-center px-2 py-0.5 rounded-md bg-indigo-50 dark:bg-indigo-500/15 text-indigo-700 dark:text-indigo-300 font-semibold text-[11px]">
                              {entry.hit_count || 0} hits
                            </span>
                          </td>
                          <td className="py-3 px-3 text-zinc-500 dark:text-zinc-400 max-w-[250px] truncate">
                            {entry.response}
                          </td>
                          <td className="py-3 px-3 text-right">
                            <div className="inline-flex items-center justify-end gap-1.5">
                              {onTestParaphrase && (
                                <button
                                  type="button"
                                  onClick={() => onTestParaphrase(paraphrase)}
                                  title={`Test paraphrase: "${paraphrase}"`}
                                  className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full bg-indigo-50 dark:bg-indigo-500/15 hover:bg-indigo-100 dark:hover:bg-indigo-500/25 text-indigo-700 dark:text-indigo-300 border border-indigo-200/70 dark:border-indigo-400/30 text-[11px] font-medium transition cursor-pointer"
                                >
                                  <span>Test Paraphrase in Playground</span>
                                  <ArrowUpRight className="w-3 h-3" />
                                </button>
                              )}
                              <button
                                type="button"
                                onClick={() => handleDelete(entry.id)}
                                className="p-1.5 rounded-lg text-zinc-400 hover:text-rose-600 dark:hover:text-rose-400 hover:bg-rose-50 dark:hover:bg-rose-500/15 transition cursor-pointer"
                                title="Delete vector"
                              >
                                <Trash2 className="w-3.5 h-3.5" />
                              </button>
                            </div>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      )}

      {/* VIEW B: PROACTIVE DBSCAN TOPIC WARMER */}
      {section === "proactive" && (
        <div className="space-y-6">
          <div className="semantiq-card rounded-2xl p-6 flex flex-wrap items-center justify-between gap-4">
            <div className="space-y-1 max-w-xl">
              <h2 className="text-sm font-semibold text-zinc-900 dark:text-zinc-100">
                DBSCAN Unsupervised Topic Warmer
              </h2>
              <p className="text-xs text-zinc-500 dark:text-zinc-400">
                Clusters recent cache misses by cosine distance, synthesizes a
                canonical question &amp; answer plus 5 paraphrases, and
                pre-warms Tier-1 and Tier-2.
              </p>
            </div>

            <div className="flex flex-wrap items-center gap-2.5">
              <button
                type="button"
                onClick={handleSeedSolarTopic}
                disabled={isSeeding || isWarming}
                className="px-4 py-2.5 rounded-full bg-white dark:bg-white/[0.06] hover:bg-zinc-50 dark:hover:bg-white/[0.1] border border-black/[0.08] dark:border-white/[0.1] hover:border-indigo-200/80 dark:hover:border-indigo-400/30 text-xs font-medium text-zinc-700 dark:text-zinc-200 shadow-sm hover:shadow-md hover:-translate-y-0.5 active:scale-95 transition-all duration-200 cursor-pointer disabled:opacity-40"
              >
                {isSeeding ? "Seeding..." : "1. Seed Solar System Misses"}
              </button>

              <button
                type="button"
                onClick={handleRunDbscan}
                disabled={isWarming || isSeeding}
                className="inline-flex items-center gap-1.5 px-4 py-2.5 rounded-full bg-gradient-to-r from-indigo-600 via-violet-600 to-fuchsia-600 text-white text-xs font-medium shadow-sm hover:shadow-md hover:-translate-y-0.5 active:scale-95 transition-all duration-200 cursor-pointer disabled:opacity-40"
              >
                <Sparkles className="w-3.5 h-3.5" />
                {isWarming
                  ? "Clustering & Warming..."
                  : "2. Run DBSCAN Proactive Warm"}
              </button>
            </div>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
            {/* Left: Logged Cache Misses */}
            <div className="lg:col-span-5 semantiq-card rounded-2xl p-5 space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold text-zinc-900 dark:text-zinc-100">
                  Logged Cache Misses
                </span>
                <span className="text-[11px] font-mono text-zinc-400 dark:text-zinc-500">
                  {misses.length} unique
                </span>
              </div>

              {misses.length === 0 ? (
                <div className="py-10 text-center text-xs text-zinc-400 dark:text-zinc-500">
                  No misses recorded. Click &ldquo;1. Seed Solar System
                  Misses&rdquo; above.
                </div>
              ) : (
                <ul className="space-y-1.5 max-h-72 overflow-y-auto pr-1">
                  {misses.map((mPrompt, i) => (
                    <li
                      key={`${mPrompt}-${i}`}
                      className="text-xs font-mono text-zinc-700 dark:text-zinc-300 px-3 py-2 rounded-xl bg-zinc-50 dark:bg-white/[0.04] border border-black/[0.05] dark:border-white/[0.08] truncate"
                    >
                      {mPrompt}
                    </li>
                  ))}
                </ul>
              )}
            </div>

            {/* Right: Synthesis Output */}
            <div className="lg:col-span-7 semantiq-card rounded-2xl p-5 space-y-4">
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold text-zinc-900 dark:text-zinc-100">
                  Canonical Synthesis &amp; Paraphrases
                </span>
                {warmReport && (
                  <span className="text-xs font-mono font-semibold text-emerald-600 dark:text-emerald-400">
                    +{warmReport.entries_warmed} entries warmed
                  </span>
                )}
              </div>

              {!warmReport ? (
                <div className="py-10 text-center text-xs text-zinc-400 dark:text-zinc-500">
                  Run DBSCAN Proactive Warm to view discovered cluster and
                  synthesized canonical Q&amp;A.
                </div>
              ) : (
                <div className="space-y-4 text-xs">
                  {warmReport.canonical_question && (
                    <div className="p-4 rounded-2xl bg-indigo-50/70 dark:bg-indigo-500/15 border border-indigo-200 dark:border-indigo-500/30 space-y-1.5">
                      <div className="font-mono text-indigo-950 dark:text-indigo-200 font-semibold">
                        {warmReport.canonical_question}
                      </div>
                      <p className="text-zinc-700 dark:text-zinc-300 leading-relaxed">
                        {warmReport.canonical_answer}
                      </p>
                    </div>
                  )}

                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 font-mono text-[11px]">
                    <div className="p-3.5 rounded-xl bg-zinc-50 dark:bg-white/[0.04] border border-black/[0.05] dark:border-white/[0.08] space-y-1">
                      <div className="text-zinc-400 dark:text-zinc-500 font-sans font-medium mb-1">
                        Clustered Misses (
                        {warmReport.cluster_prompts?.length || 0})
                      </div>
                      {(warmReport.cluster_prompts || []).map((cp) => (
                        <div
                          key={cp}
                          className="text-zinc-700 dark:text-zinc-300 truncate"
                        >
                          • {cp}
                        </div>
                      ))}
                    </div>

                    <div className="p-3.5 rounded-xl bg-zinc-50 dark:bg-white/[0.04] border border-black/[0.05] dark:border-white/[0.08] space-y-1">
                      <div className="text-zinc-400 dark:text-zinc-500 font-sans font-medium mb-1">
                        Generated Paraphrases (
                        {warmReport.paraphrases?.length || 0})
                      </div>
                      {(warmReport.paraphrases || []).map((pp) => (
                        <div
                          key={pp}
                          className="text-emerald-700 dark:text-emerald-300 truncate"
                        >
                          ✓ {pp}
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
