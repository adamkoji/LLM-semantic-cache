const rawBaseUrl = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000";
export const API_BASE_URL = rawBaseUrl.replace(/\/+$/, "");

async function requestJson(path, options = {}) {
  const url = `${API_BASE_URL}${path}`;
  const headers = {
    "Content-Type": "application/json",
    ...(options.headers || {}),
  };

  const response = await fetch(url, {
    ...options,
    headers,
  });

  if (!response.ok) {
    let errorDetail = `HTTP ${response.status}`;
    try {
      const errJson = await response.json();
      errorDetail = errJson.detail || errJson.message || errorDetail;
    } catch {
      // Ignore JSON parse error on non-JSON error responses
    }
    throw new Error(errorDetail);
  }

  return response.json();
}

export async function processPrompt(prompt, options = {}) {
  return requestJson("/process-prompt/", {
    method: "POST",
    body: JSON.stringify({ prompt }),
    signal: options.signal,
  });
}

export async function processPromptNoCache(prompt, options = {}) {
  return requestJson("/process-prompt-no-cache/", {
    method: "POST",
    body: JSON.stringify({ prompt }),
    signal: options.signal,
  });
}

export async function getHealth() {
  return requestJson("/health", { method: "GET" });
}

export async function getMetrics() {
  return requestJson("/metrics/", { method: "GET" });
}

export async function resetMetrics() {
  return requestJson("/metrics/reset", { method: "POST" });
}

export async function getCacheConfig() {
  return requestJson("/cache/config", { method: "GET" });
}

export async function updateCacheConfig(threshold, maxSize = undefined) {
  const payload = { threshold: Number(threshold) };
  if (maxSize !== undefined) {
    payload.max_size = Number(maxSize);
  }
  return requestJson("/cache/config", {
    method: "PUT",
    body: JSON.stringify(payload),
  });
}

export async function getCacheEntries(limit = 50) {
  return requestJson(`/cache/entries?limit=${encodeURIComponent(limit)}`, {
    method: "GET",
  });
}

export async function deleteCacheEntry(id) {
  return requestJson(`/cache/entries/${encodeURIComponent(id)}`, {
    method: "DELETE",
  });
}

export async function clearAllCaches() {
  return requestJson("/cache/clear", { method: "DELETE" });
}

export async function getCacheMisses() {
  return requestJson("/cache/misses", { method: "GET" });
}

export async function warmCacheItem(prompt, answer) {
  return requestJson("/warm-cache/", {
    method: "POST",
    body: JSON.stringify({ prompt, answer }),
  });
}

export async function runProactiveWarm(minClusterSize = 3, eps = 0.42) {
  return requestJson("/cache/proactive-warm", {
    method: "POST",
    body: JSON.stringify({ min_cluster_size: minClusterSize, eps }),
  });
}

export async function runLiveBenchmark(numPrompts = 40, resetCacheFirst = true) {
  return requestJson("/benchmark/run", {
    method: "POST",
    body: JSON.stringify({
      num_prompts: Number(numPrompts),
      reset_cache_first: Boolean(resetCacheFirst),
    }),
  });
}

export async function getResourceFootprint(numEntries = 100000, vectorDim = 384) {
  return requestJson(
    `/benchmark/resources?num_entries=${encodeURIComponent(numEntries)}&vector_dim=${encodeURIComponent(vectorDim)}`,
    { method: "GET" }
  );
}
