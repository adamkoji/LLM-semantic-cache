import React, { useState, useEffect, useCallback, useRef } from "react";
import {
  Plus,
  Compass,
  BarChart2,
  LayoutGrid,
  Activity,
  Settings,
  Trash2,
  PanelLeftClose,
  PanelLeftOpen,
  Sun,
  Moon,
  Menu,
} from "lucide-react";
import {
  getHealth,
  getMetrics,
  resetMetrics,
  updateCacheConfig,
  clearAllCaches,
  API_BASE_URL,
} from "./api/cacheApi";
import PlaygroundTab from "./components/PlaygroundTab.jsx";
import TelemetryTab from "./components/TelemetryTab.jsx";
import ProactiveAndExplorerTab from "./components/ProactiveAndExplorerTab.jsx";
import BenchmarkLabTab from "./components/BenchmarkLabTab.jsx";

const NAV_ITEMS = [
  { id: "playground", label: "Playground", icon: Compass },
  { id: "telemetry", label: "Analytics", icon: BarChart2 },
  { id: "proactive", label: "Cache Vault", icon: LayoutGrid },
  { id: "benchmark", label: "Benchmarks", icon: Activity },
];

export default function App() {
  const [activeTab, setActiveTab] = useState("playground");
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);
  const [theme, setTheme] = useState(() => {
    try {
      return localStorage.getItem("semantiq_theme") || "light";
    } catch {
      return "light";
    }
  });
  const [playgroundResetKey, setPlaygroundResetKey] = useState(0);
  const [pendingPlaygroundPrompt, setPendingPlaygroundPrompt] = useState(null);
  const [health, setHealth] = useState(null);
  const [metrics, setMetrics] = useState(null);
  const [backendOnline, setBackendOnline] = useState(false);
  const [threshold, setThreshold] = useState(0.78);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [isFlushing, setIsFlushing] = useState(false);
  const [showSystemPopover, setShowSystemPopover] = useState(false);
  const popoverRef = useRef(null);

  useEffect(() => {
    const isDark = theme === "dark";
    document.documentElement.classList.toggle("dark", isDark);
    try {
      localStorage.setItem("semantiq_theme", theme);
    } catch {
      // ignore storage errors
    }
  }, [theme]);

  function handleToggleTheme() {
    setTheme((prev) => (prev === "dark" ? "light" : "dark"));
  }

  const syncSystemState = useCallback(async () => {
    setIsRefreshing(true);
    try {
      const [healthData, metricsData] = await Promise.all([
        getHealth(),
        getMetrics(),
      ]);
      setHealth(healthData);
      setMetrics(metricsData);
      if (healthData?.threshold !== undefined) {
        setThreshold(Number(healthData.threshold));
      }
      setBackendOnline(true);
    } catch {
      setBackendOnline(false);
    } finally {
      setIsRefreshing(false);
    }
  }, []);

  useEffect(() => {
    syncSystemState();
    const interval = setInterval(syncSystemState, 8000);
    return () => clearInterval(interval);
  }, [syncSystemState]);

  useEffect(() => {
    function handleResize() {
      if (window.innerWidth >= 768) {
        setIsMobileMenuOpen(false);
      }
    }
    window.addEventListener("resize", handleResize);
    return () => window.removeEventListener("resize", handleResize);
  }, []);

  useEffect(() => {
    function handleClickOutside(e) {
      if (
        e.target.closest("[data-system-popover]") ||
        e.target.closest("[data-system-popover-trigger]")
      ) {
        return;
      }
      if (popoverRef.current && !popoverRef.current.contains(e.target)) {
        setShowSystemPopover(false);
      }
    }
    if (showSystemPopover) {
      document.addEventListener("mousedown", handleClickOutside);
    }
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [showSystemPopover]);

  async function handleThresholdChange(newVal) {
    const num = Number(newVal);
    setThreshold(num);
    try {
      await updateCacheConfig(num);
      await syncSystemState();
    } catch {
      // ignore if offline
    }
  }

  async function handleFlushAllCaches() {
    setIsFlushing(true);
    try {
      await clearAllCaches();
      await syncSystemState();
    } catch {
      // ignore
    } finally {
      setIsFlushing(false);
    }
  }

  async function handleResetMetrics() {
    try {
      const resetData = await resetMetrics();
      setMetrics(resetData);
    } catch {
      // ignore
    }
  }

  function handleSelectTab(tabId) {
    setActiveTab(tabId);
    setIsMobileMenuOpen(false);
  }

  function handleNewQuery() {
    setPendingPlaygroundPrompt(null);
    setActiveTab("playground");
    setPlaygroundResetKey((prev) => prev + 1);
    setIsMobileMenuOpen(false);
  }

  function handleTestInPlayground(promptText) {
    setPendingPlaygroundPrompt(promptText);
    setActiveTab("playground");
    setIsMobileMenuOpen(false);
  }

  const isCollapsed = sidebarCollapsed && !isMobileMenuOpen;
  const t1Entries = health?.tier1?.entries ?? 0;
  const t2Entries = health?.tier2?.entries ?? 0;
  const embModel = health?.embedding_model || "BAAI/bge-small-en-v1.5";
  const geminiModel = health?.gemini_model_cascade?.[0] || "gemini-3.6-flash";

  function renderPopoverContent() {
    return (
      <>
        <div className="flex items-center justify-between">
          <span className="text-xs font-semibold text-zinc-900 dark:text-zinc-100">
            Engine Configuration
          </span>
          <span
            className={`inline-flex items-center gap-1.5 text-[11px] font-medium px-2.5 py-0.5 rounded-full ${
              backendOnline
                ? "bg-emerald-50 dark:bg-emerald-500/15 text-emerald-700 dark:text-emerald-300 border border-emerald-200 dark:border-emerald-500/30"
                : "bg-amber-50 dark:bg-amber-500/15 text-amber-700 dark:text-amber-300 border border-amber-200 dark:border-amber-500/30"
            }`}
          >
            <span
              className={`w-1.5 h-1.5 rounded-full ${
                backendOnline ? "bg-emerald-500" : "bg-amber-500"
              }`}
            />
            {backendOnline ? "API Online" : "Offline"}
          </span>
        </div>

        {/* Cosine Similarity Threshold Slider */}
        <div className="space-y-2 pt-2 border-t border-black/[0.06] dark:border-white/[0.08]">
          <div className="flex items-center justify-between text-xs">
            <span className="text-zinc-600 dark:text-zinc-400 font-medium">
              Cosine Similarity Threshold
            </span>
            <span className="font-mono font-semibold text-indigo-600 dark:text-indigo-300 bg-indigo-50 dark:bg-indigo-500/20 px-2 py-0.5 rounded-md">
              {Number(threshold).toFixed(2)}
            </span>
          </div>
          <input
            type="range"
            min="0.50"
            max="0.95"
            step="0.01"
            value={threshold}
            onChange={(e) => handleThresholdChange(e.target.value)}
            className="w-full accent-indigo-600 cursor-pointer h-1.5 bg-zinc-200 dark:bg-white/[0.12] rounded-lg"
          />
          <div className="flex justify-between text-[10px] font-mono text-zinc-400 dark:text-zinc-500">
            <span>0.50 (Broad)</span>
            <span>0.78 (Default)</span>
            <span>0.95 (Strict)</span>
          </div>
        </div>

        {/* Tier Status Grid */}
        <div className="grid grid-cols-2 gap-2.5 pt-2 border-t border-black/[0.06] dark:border-white/[0.08] text-xs">
          <div className="p-2.5 rounded-2xl bg-zinc-50 dark:bg-white/[0.04] border border-black/[0.05] dark:border-white/[0.08]">
            <div className="text-[11px] text-zinc-400 dark:text-zinc-500">
              Tier-1 Exact
            </div>
            <div className="font-mono font-semibold text-zinc-900 dark:text-zinc-100 mt-0.5">
              {t1Entries} entries
            </div>
          </div>
          <div className="p-2.5 rounded-2xl bg-zinc-50 dark:bg-white/[0.04] border border-black/[0.05] dark:border-white/[0.08]">
            <div className="text-[11px] text-zinc-400 dark:text-zinc-500">
              Tier-2 ChromaDB
            </div>
            <div className="font-mono font-semibold text-zinc-900 dark:text-zinc-100 mt-0.5">
              {t2Entries} vectors
            </div>
          </div>
        </div>

        <div className="text-[11px] text-zinc-500 dark:text-zinc-400 space-y-1 pt-2 border-t border-black/[0.06] dark:border-white/[0.08] font-mono">
          <div className="flex justify-between">
            <span>Embedding</span>
            <span className="text-zinc-800 dark:text-zinc-200 font-medium">
              {embModel.split("/").pop()}
            </span>
          </div>
          <div className="flex justify-between">
            <span>LLM Model</span>
            <span className="text-zinc-800 dark:text-zinc-200 font-medium">
              {geminiModel}
            </span>
          </div>
          <div className="flex justify-between">
            <span>API Host</span>
            <span className="text-zinc-600 dark:text-zinc-400 truncate max-w-[155px]">
              {API_BASE_URL}
            </span>
          </div>
        </div>

        <button
          type="button"
          onClick={handleFlushAllCaches}
          disabled={isFlushing}
          className="w-full py-2.5 px-3 rounded-2xl bg-rose-50 dark:bg-rose-500/15 hover:bg-rose-100 dark:hover:bg-rose-500/25 text-rose-700 dark:text-rose-300 border border-rose-200 dark:border-rose-500/30 text-xs font-medium flex items-center justify-center gap-2 transition cursor-pointer disabled:opacity-50"
        >
          <Trash2 className="w-3.5 h-3.5" />
          {isFlushing ? "Flushing Caches..." : "Flush All Caches"}
        </button>
      </>
    );
  }

  return (
    <div className="h-screen overflow-hidden pastel-mesh-canvas text-zinc-900 dark:text-zinc-100 flex flex-col md:flex-row">
      {/* Mobile Top Navigation Bar (< 768px) */}
      <header className="flex md:hidden items-center justify-between px-4 py-3 mx-3 mt-2.5 shrink-0 rounded-2xl bg-white/85 dark:bg-white/[0.05] backdrop-blur-xl border border-black/[0.06] dark:border-white/[0.09] shadow-sm z-30">
        <button
          type="button"
          onClick={() => setIsMobileMenuOpen(true)}
          aria-label="Open navigation menu"
          className="w-9 h-9 rounded-xl flex items-center justify-center text-zinc-600 dark:text-zinc-300 hover:bg-zinc-100/80 dark:hover:bg-white/[0.08] transition cursor-pointer"
        >
          <Menu className="w-5 h-5" />
        </button>

        <div
          onClick={() => handleSelectTab("playground")}
          className="relative flex items-center justify-center cursor-pointer"
        >
          <span className="brand-calligraphic text-2xl select-none whitespace-nowrap">
            Semantiq
          </span>
        </div>

        <div className="flex items-center gap-1.5">
          <button
            type="button"
            onClick={handleToggleTheme}
            title={
              theme === "dark" ? "Switch to Light Mode" : "Switch to Dark Mode"
            }
            className="relative w-9 h-9 rounded-xl bg-zinc-100/80 dark:bg-white/[0.06] border border-black/[0.05] dark:border-white/[0.08] flex items-center justify-center cursor-pointer"
          >
            <Sun
              className={`w-4 h-4 text-amber-500 absolute transition-all duration-500 ${
                theme === "dark"
                  ? "-rotate-90 scale-0 opacity-0"
                  : "rotate-0 scale-100 opacity-100"
              }`}
            />
            <Moon
              className={`w-4 h-4 text-indigo-300 absolute transition-all duration-500 ${
                theme === "dark"
                  ? "rotate-0 scale-100 opacity-100"
                  : "rotate-90 scale-0 opacity-0"
              }`}
            />
          </button>

          <button
            type="button"
            data-system-popover-trigger="true"
            onClick={() => setShowSystemPopover((prev) => !prev)}
            title="Engine Configuration"
            className="relative w-9 h-9 rounded-xl bg-gradient-to-br from-indigo-500/15 via-fuchsia-500/15 to-cyan-500/15 dark:from-indigo-500/25 dark:via-fuchsia-500/20 dark:to-cyan-500/20 border border-indigo-200/60 dark:border-indigo-400/30 flex items-center justify-center text-indigo-600 dark:text-indigo-300 cursor-pointer"
          >
            <Settings className="w-4 h-4" />
            <span
              className={`absolute top-1.5 right-1.5 w-1.5 h-1.5 rounded-full ${
                backendOnline ? "bg-emerald-500" : "bg-amber-500"
              }`}
            />
          </button>
        </div>
      </header>

      {/* Mobile Dark/Frosted Backdrop Overlay */}
      {isMobileMenuOpen && (
        <div
          onClick={() => setIsMobileMenuOpen(false)}
          className="fixed inset-0 bg-black/35 backdrop-blur-xs z-40 md:hidden transition-opacity duration-300"
        />
      )}

      {/* Floating Rounded-3xl Prismatic Rainbow Sidebar (Slide-over on Mobile, Fixed-Height Locked on Desktop) */}
      <aside
        className={`fixed inset-y-2.5 left-2.5 h-[calc(100vh-20px)] z-50 w-64 md:relative md:inset-auto md:my-3 md:ml-3 md:mr-0 md:h-[calc(100vh-24px)] px-3 py-4 rainbow-sidebar backdrop-blur-2xl rounded-3xl flex flex-col justify-between transition-[width,transform,opacity,box-shadow] duration-300 ease-[cubic-bezier(0.22,1,0.36,1)] will-change-[width,transform] shrink-0 select-none md:z-30 ${
          isMobileMenuOpen
            ? "translate-x-0 opacity-100 pointer-events-auto"
            : "-translate-x-[115%] opacity-0 pointer-events-none md:translate-x-0 md:opacity-100 md:pointer-events-auto"
        } ${sidebarCollapsed ? "md:w-[76px]" : "md:w-64"}`}
      >
        {/* Top Section: Header + Primary Action + Navigation */}
        <div className="space-y-3">
          {/* Top Header Row: Centered Stylized "Semantiq" Wordmark + Collapse/Expand Button */}
          <div className="h-12 flex items-center justify-between">
            <div
              onClick={() => handleSelectTab("playground")}
              className={`group relative flex items-center justify-center cursor-pointer transition-all duration-300 ease-[cubic-bezier(0.22,1,0.36,1)] ${
                isCollapsed
                  ? "opacity-0 max-w-0 -translate-x-3 overflow-hidden pointer-events-none"
                  : "flex-1 opacity-100 max-w-[180px] translate-x-0 pl-4"
              }`}
            >
              {/* Soft Pastel Glow Halo Behind "Semantiq" */}
              <div
                aria-hidden="true"
                className="pointer-events-none absolute -inset-x-3 -inset-y-1.5 rounded-full bg-gradient-to-r from-indigo-400/25 via-fuchsia-400/30 to-cyan-400/25 blur-xl opacity-75 group-hover:opacity-100 group-hover:scale-110 group-hover:from-indigo-400/40 group-hover:via-fuchsia-400/45 group-hover:to-cyan-400/40 transition-all duration-500"
              />
              <span className="relative brand-calligraphic text-[30px] select-none whitespace-nowrap group-hover:scale-105 group-hover:-translate-y-0.5 transition-all duration-300">
                Semantiq
              </span>
            </div>

            <div className="w-[52px] h-10 shrink-0 flex items-center justify-center">
              <button
                type="button"
                onClick={() => {
                  if (window.innerWidth < 768) {
                    setIsMobileMenuOpen(false);
                  } else {
                    setSidebarCollapsed((prev) => !prev);
                  }
                }}
                title={isCollapsed ? "Expand sidebar" : "Collapse sidebar"}
                className="w-10 h-10 shrink-0 flex items-center justify-center rounded-xl text-zinc-400 hover:text-zinc-700 dark:text-zinc-400 dark:hover:text-zinc-100 hover:bg-zinc-100/80 dark:hover:bg-white/[0.08] transition-colors duration-200 cursor-pointer"
              >
                {isCollapsed ? (
                  <PanelLeftOpen className="w-5 h-5" />
                ) : (
                  <PanelLeftClose className="w-5 h-5" />
                )}
              </button>
            </div>
          </div>

          {/* Soft Lavender Primary Action Button (+ New Query) */}
          <button
            type="button"
            onClick={handleNewQuery}
            title="Start a new query session"
            className="group w-full h-10 bg-[#F3F1FF] hover:bg-[#EAE6FF] dark:bg-indigo-500/15 dark:hover:bg-indigo-500/25 text-indigo-600 dark:text-indigo-300 font-medium rounded-xl flex items-center overflow-hidden transition-all duration-300 ease-[cubic-bezier(0.22,1,0.36,1)] hover:shadow-[0_6px_20px_-4px_rgba(99,102,241,0.22)] cursor-pointer"
          >
            <div className="w-[52px] h-10 shrink-0 flex items-center justify-center">
              <Plus className="w-5 h-5 shrink-0 stroke-[2.2] group-hover:rotate-90 transition-transform duration-300" />
            </div>
            <span
              className={`text-sm leading-normal py-0.5 whitespace-nowrap overflow-hidden transition-all duration-300 ease-[cubic-bezier(0.22,1,0.36,1)] ${
                isCollapsed
                  ? "max-w-0 opacity-0 -translate-x-2"
                  : "max-w-[160px] opacity-100 translate-x-0 pr-3"
              }`}
            >
              New Query
            </span>
          </button>

          {/* Navigation Menu */}
          <nav className="space-y-1.5 pt-1">
            {NAV_ITEMS.map((item) => {
              const Icon = item.icon;
              const isActive = activeTab === item.id;
              return (
                <button
                  key={item.id}
                  type="button"
                  onClick={() => handleSelectTab(item.id)}
                  title={isCollapsed ? item.label : undefined}
                  className={`group w-full h-10 rounded-xl flex items-center overflow-hidden transition-all duration-300 ease-[cubic-bezier(0.22,1,0.36,1)] cursor-pointer ${
                    isActive
                      ? "sidebar-item-active text-indigo-950 dark:text-white font-semibold"
                      : "text-zinc-600 dark:text-zinc-400 hover:text-zinc-900 dark:hover:text-zinc-100 hover:bg-gradient-to-r hover:from-zinc-100/80 hover:to-indigo-50/40 dark:hover:from-white/[0.06] dark:hover:to-indigo-500/10"
                  }`}
                >
                  <div className="w-[52px] h-10 shrink-0 flex items-center justify-center">
                    <Icon
                      className={`w-5 h-5 shrink-0 transition-transform duration-200 group-hover:scale-110 ${
                        isActive
                          ? "text-indigo-600 dark:text-indigo-300"
                          : "text-zinc-500 dark:text-zinc-400 group-hover:text-indigo-600 dark:group-hover:text-indigo-300"
                      }`}
                    />
                  </div>
                  <span
                    className={`text-sm leading-normal py-0.5 whitespace-nowrap overflow-hidden transition-all duration-300 ease-[cubic-bezier(0.22,1,0.36,1)] ${
                      isCollapsed
                        ? "max-w-0 opacity-0 -translate-x-2"
                        : "max-w-[160px] opacity-100 translate-x-0 pr-3"
                    }`}
                  >
                    {item.label}
                  </span>
                </button>
              );
            })}
          </nav>
        </div>

        {/* Bottom Section: Theme Switcher + "Semantic Engine" Settings Button */}
        <div
          className="pt-3 border-t border-black/[0.05] dark:border-white/[0.08] space-y-2 relative"
          ref={popoverRef}
        >
          {/* Theme Switcher Button (Animated Sun / Moon Morph) */}
          <button
            type="button"
            onClick={handleToggleTheme}
            title={
              theme === "dark" ? "Switch to Light Mode" : "Switch to Dark Mode"
            }
            className="group w-full h-10 rounded-xl flex items-center overflow-hidden cursor-pointer transition-all duration-300 ease-[cubic-bezier(0.22,1,0.36,1)] bg-zinc-50/90 dark:bg-white/[0.04] hover:bg-gradient-to-r hover:from-amber-50/80 hover:via-indigo-50/70 hover:to-fuchsia-50/70 dark:hover:from-indigo-500/15 dark:hover:via-fuchsia-500/15 dark:hover:to-cyan-500/15 ring-1 ring-inset ring-black/[0.05] dark:ring-white/[0.08] hover:ring-indigo-300/70 dark:hover:ring-indigo-400/40"
          >
            <div className="w-[52px] h-10 shrink-0 flex items-center justify-center">
              <div className="relative w-7 h-7 rounded-lg bg-gradient-to-br from-amber-500/15 via-indigo-500/15 to-fuchsia-500/15 dark:from-indigo-500/25 dark:via-fuchsia-500/20 dark:to-cyan-500/20 border border-indigo-200/60 dark:border-indigo-400/30 flex items-center justify-center shrink-0">
                <Sun
                  className={`w-4 h-4 text-amber-500 absolute transition-all duration-500 ${
                    theme === "dark"
                      ? "-rotate-90 scale-0 opacity-0"
                      : "rotate-0 scale-100 opacity-100"
                  }`}
                />
                <Moon
                  className={`w-4 h-4 text-indigo-300 absolute transition-all duration-500 ${
                    theme === "dark"
                      ? "rotate-0 scale-100 opacity-100"
                      : "rotate-90 scale-0 opacity-0"
                  }`}
                />
              </div>
            </div>

            <div
              className={`flex-1 flex items-center justify-between whitespace-nowrap overflow-hidden transition-all duration-300 ease-[cubic-bezier(0.22,1,0.36,1)] ${
                isCollapsed
                  ? "max-w-0 opacity-0 -translate-x-2"
                  : "max-w-[165px] opacity-100 translate-x-0 pr-3"
              }`}
            >
              <span className="text-sm leading-normal py-0.5 font-medium text-zinc-700 dark:text-zinc-200 group-hover:text-indigo-950 dark:group-hover:text-white truncate">
                {theme === "dark" ? "Dark Mode" : "Light Mode"}
              </span>
            </div>
          </button>

          {/* Single-Line "Semantic Engine" Settings Button */}
          <button
            type="button"
            data-system-popover-trigger="true"
            onClick={() => setShowSystemPopover((prev) => !prev)}
            title="Engine Configuration"
            className={`group w-full h-10 rounded-xl flex items-center overflow-hidden cursor-pointer transition-all duration-300 ease-[cubic-bezier(0.22,1,0.36,1)] ${
              showSystemPopover
                ? "sidebar-item-active text-indigo-950 dark:text-white"
                : "bg-zinc-50/90 dark:bg-white/[0.04] hover:bg-gradient-to-r hover:from-indigo-50/80 hover:via-fuchsia-50/70 hover:to-cyan-50/80 dark:hover:from-indigo-500/15 dark:hover:via-fuchsia-500/15 dark:hover:to-cyan-500/15 ring-1 ring-inset ring-black/[0.05] dark:ring-white/[0.08] hover:ring-indigo-300/70 dark:hover:ring-indigo-400/40 hover:shadow-[0_4px_18px_-4px_rgba(139,92,246,0.25)]"
            }`}
          >
            <div className="w-[52px] h-10 shrink-0 flex items-center justify-center">
              <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-indigo-500/15 via-fuchsia-500/15 to-cyan-500/15 dark:from-indigo-500/25 dark:via-fuchsia-500/20 dark:to-cyan-500/20 border border-indigo-200/60 dark:border-indigo-400/30 flex items-center justify-center text-indigo-600 dark:text-indigo-300 shrink-0">
                <Settings className="w-4 h-4 group-hover:rotate-45 transition-transform duration-300" />
              </div>
            </div>

            <div
              className={`flex-1 flex items-center justify-between whitespace-nowrap overflow-hidden transition-all duration-300 ease-[cubic-bezier(0.22,1,0.36,1)] ${
                isCollapsed
                  ? "max-w-0 opacity-0 -translate-x-2"
                  : "max-w-[165px] opacity-100 translate-x-0 pr-3"
              }`}
            >
              <span className="text-sm leading-normal py-0.5 font-semibold text-zinc-800 dark:text-zinc-100 group-hover:text-indigo-950 dark:group-hover:text-white truncate">
                Semantic Engine
              </span>
              <span
                className={`w-2 h-2 rounded-full shrink-0 ml-2 ${
                  backendOnline
                    ? "bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.6)]"
                    : "bg-amber-500"
                }`}
              />
            </div>
          </button>

          {/* Desktop System Settings Popover anchored to bottom of sidebar */}
          {showSystemPopover && (
            <div
              data-system-popover="true"
              className="hidden md:block absolute left-full ml-3 bottom-0 w-80 rounded-3xl bg-white/95 dark:bg-[#10131E]/95 backdrop-blur-2xl border border-black/[0.08] dark:border-white/[0.1] p-5 shadow-[0_24px_60px_rgba(15,23,42,0.14)] dark:shadow-[0_24px_60px_rgba(0,0,0,0.65)] space-y-4 z-50 animate-fade-up"
            >
              {renderPopoverContent()}
            </div>
          )}
        </div>
      </aside>

      {/* Mobile System Settings Popover (< 768px) */}
      {showSystemPopover && (
        <div
          data-system-popover="true"
          className="md:hidden fixed left-3 right-3 sm:left-4 sm:right-auto sm:w-80 bottom-16 z-50 max-w-[calc(100vw-1.5rem)] rounded-3xl bg-white/95 dark:bg-[#10131E]/95 backdrop-blur-2xl border border-black/[0.08] dark:border-white/[0.1] p-5 shadow-[0_24px_60px_rgba(15,23,42,0.18)] dark:shadow-[0_24px_60px_rgba(0,0,0,0.75)] space-y-4 animate-fade-up"
        >
          {renderPopoverContent()}
        </div>
      )}

      {/* Main Content Stage (Independently Scrollable) */}
      <div className="flex-1 flex flex-col w-full min-w-0 h-full overflow-y-auto overflow-x-hidden relative">
        <main
          key={activeTab}
          className="flex-1 flex flex-col w-full min-w-0 animate-fade-up"
        >
          {activeTab === "playground" && (
            <PlaygroundTab
              key={playgroundResetKey}
              threshold={threshold}
              onThresholdChange={handleThresholdChange}
              onAfterQuery={syncSystemState}
              initialPrompt={pendingPlaygroundPrompt}
              onClearInitialPrompt={() => setPendingPlaygroundPrompt(null)}
            />
          )}

          {activeTab === "telemetry" && (
            <TelemetryTab
              metrics={metrics}
              onRefreshMetrics={syncSystemState}
              onResetMetrics={handleResetMetrics}
              isRefreshing={isRefreshing}
            />
          )}

          {activeTab === "proactive" && (
            <ProactiveAndExplorerTab
              onAfterChange={syncSystemState}
              onTestParaphrase={handleTestInPlayground}
            />
          )}

          {activeTab === "benchmark" && (
            <BenchmarkLabTab onAfterBenchmark={syncSystemState} />
          )}
        </main>
      </div>
    </div>
  );
}
