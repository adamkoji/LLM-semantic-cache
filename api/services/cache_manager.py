import os
import re
import time
import uuid
import hashlib
import threading
from collections import OrderedDict
import redis
import chromadb
from chromadb.config import Settings

# --- Configuration ---
CACHE_MAX_SIZE = int(os.getenv("CACHE_MAX_SIZE", "1000"))
CACHE_THRESHOLD = float(os.getenv("CACHE_THRESHOLD", "0.78"))
CACHE_TTL_SECONDS = int(os.getenv("CACHE_TTL_SECONDS", "3600"))

_config_lock = threading.Lock()


def get_threshold() -> float:
    return CACHE_THRESHOLD


def set_threshold(val: float) -> float:
    global CACHE_THRESHOLD
    with _config_lock:
        CACHE_THRESHOLD = round(max(0.0, min(1.0, float(val))), 4)
    return CACHE_THRESHOLD


def set_max_size(val: int) -> int:
    global CACHE_MAX_SIZE
    with _config_lock:
        CACHE_MAX_SIZE = max(1, int(val))
    return CACHE_MAX_SIZE


# --- Prompt Normalization & SHA-256 Key Hashing ---
def normalize_prompt(prompt: str) -> str:
    """
    Normalizes a prompt: lowercase, strip leading/trailing whitespace,
    collapse multiple spaces, and strip trailing punctuation (?, !, .).
    """
    if not prompt:
        return ""
    cleaned = re.sub(r"\s+", " ", prompt.strip().lower())
    cleaned = cleaned.rstrip("?!. ").strip()
    return cleaned


def get_exact_cache_key(prompt: str) -> str:
    """Generates a deterministic SHA-256 cache key from the normalized prompt."""
    norm = normalize_prompt(prompt)
    digest = hashlib.sha256(norm.encode("utf-8")).hexdigest()
    return f"t1:exact:{digest}"


# --- Smart Guardrail #1: Temporal / Real-Time Query Bypass ---
TEMPORAL_PHRASES = [
    "weather today",
    "current weather",
    "today's weather",
    "weather right now",
    "current temperature",
    "temperature today",
    "temperature right now",
    "current time",
    "time right now",
    "what time is it",
    "right now",
    "live score",
    "current score",
    "stock price today",
    "current stock price",
    "latest news today",
    "breaking news today",
    "news right now",
    "bitcoin price today",
    "crypto price right now",
]

TEMPORAL_REGEX = re.compile(
    r"\b(weather|temperature|forecast|stock price|live score|latest news|breaking news)\b.*\b(today|now|tonight|current|live)\b"
    r"|\b(today|current|live)\b.*\b(weather|temperature|forecast|stock price|score|news)\b",
    re.IGNORECASE,
)


def is_temporal_query(prompt: str) -> tuple[bool, str | None]:
    """
    Detects time-sensitive/real-time queries that should bypass semantic caching.
    Returns (True, matched_phrase) if temporal, else (False, None).
    """
    lower = normalize_prompt(prompt)
    for phrase in TEMPORAL_PHRASES:
        if phrase in lower:
            return True, phrase
    match = TEMPORAL_REGEX.search(lower)
    if match:
        return True, match.group(0)
    return False, None


# --- Smart Guardrail #2: Semantic False-Positive Guard ---
ABBREVIATION_MAP = {
    r"\bml\b": "machine learning",
    r"\bai\b": "artificial intelligence",
    r"\bjs\b": "javascript",
    r"\bts\b": "typescript",
    r"\bk8s\b": "kubernetes",
    r"\bdb\b": "database",
    r"\bnn\b": "neural network",
    r"\bnns\b": "neural networks",
    r"\bnlp\b": "natural language processing",
    r"\bllm\b": "large language model",
    r"\bcpu\b": "central processing unit",
    r"\bgpu\b": "graphics processing unit",
    r"\bred planet\b": "mars",
    r"\buk\b": "united kingdom",
    r"\busa\b": "united states",
}

ANTONYM_GROUPS = [
    ({"install", "installing", "installation", "setup"}, {"uninstall", "uninstalling", "remove", "removing", "delete", "deleting", "purge"}),
    ({"enable", "enabling", "start", "starting", "activate"}, {"disable", "disabling", "stop", "stopping", "deactivate"}),
    ({"encrypt", "encryption"}, {"decrypt", "decryption"}),
    ({"encode", "encoding"}, {"decode", "decoding"}),
    ({"lock", "locking"}, {"unlock", "unlocking"}),
    ({"connect", "connecting"}, {"disconnect", "disconnecting"}),
    ({"upload", "uploading"}, {"download", "downloading"}),
    ({"import", "importing"}, {"export", "exporting"}),
    ({"pros", "advantages", "benefits"}, {"cons", "disadvantages", "drawbacks"}),
]

NEGATION_WORDS = {
    "not", "never", "without", "dont", "don't", "cannot", "can't",
    "isn't", "isnt", "won't", "wont", "aren't", "arent", "doesn't", "doesnt",
    "didn't", "didnt",
}

COUNTRY_PLACE_ENTITIES = {
    "france", "germany", "japan", "india", "spain", "italy", "china", "russia",
    "brazil", "canada", "australia", "mexico", "united kingdom", "united states",
    "egypt", "greece", "korea", "argentina", "nigeria", "sweden", "norway",
    "switzerland", "netherlands", "poland", "turkey", "indonesia", "thailand",
    "paris", "berlin", "tokyo", "delhi", "london", "rome", "madrid", "beijing", "moscow",
}

TECH_ENTITIES = {
    "python", "java", "javascript", "typescript", "rust", "golang", "ruby",
    "php", "swift", "kotlin", "scala", "docker", "kubernetes", "redis",
    "postgres", "postgresql", "mysql", "mongodb", "sqlite", "react", "angular",
    "vue", "django", "fastapi", "flask", "aws", "azure", "gcp", "linux",
    "windows", "macos", "ubuntu", "android", "ios",
}

PLANET_ENTITIES = {
    "mercury", "venus", "earth", "mars", "jupiter", "saturn", "uranus", "neptune", "pluto",
}

STOPWORDS = {
    "a", "an", "the", "is", "are", "was", "were", "be", "been", "being",
    "what", "which", "who", "whom", "whose", "where", "when", "why", "how",
    "can", "could", "would", "should", "will", "shall", "may", "might", "must",
    "do", "does", "did", "done", "doing", "have", "has", "had", "having",
    "you", "your", "yours", "me", "my", "mine", "i", "we", "our", "ours",
    "they", "them", "their", "he", "him", "his", "she", "her", "it", "its",
    "to", "of", "in", "on", "at", "for", "with", "about", "from", "by", "as",
    "into", "onto", "upon", "out", "up", "down", "over", "under", "around",
    "explain", "tell", "describe", "give", "summary", "define", "meaning",
    "mean", "simple", "terms", "please", "help", "know", "known", "called",
    "most", "famous", "largest", "biggest", "giant", "great", "many",
    "work", "works", "working", "way", "ways", "some", "any", "this", "that",
}


def _expand_abbreviations(text: str) -> str:
    expanded = normalize_prompt(text)
    for pattern, replacement in ABBREVIATION_MAP.items():
        expanded = re.sub(pattern, replacement, expanded)
    return expanded


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[a-z0-9']+", text.lower())


def passes_entity_and_negation_guard(query_prompt: str, matched_prompt: str) -> tuple[bool, str | None]:
    """
    Prevents semantic vector cache false positives even when cosine similarity >= threshold.
    Checks:
    1. Antonym / opposite action conflict (e.g., install vs uninstall, enable vs disable)
    2. Negation mismatch (e.g., 'not', 'never', 'without')
    3. Numeric mismatch (e.g., Python 2 vs Python 3)
    4. Distinct proper noun / subject entity mismatch (e.g., France vs Germany, Python vs Java, Mars vs Jupiter)
    Returns (True, None) if safe to match, or (False, reason) if blocked.
    """
    q_exp = _expand_abbreviations(query_prompt)
    m_exp = _expand_abbreviations(matched_prompt)

    if q_exp == m_exp:
        return True, None

    q_tokens = set(_tokenize(q_exp))
    m_tokens = set(_tokenize(m_exp))

    # 1. Antonym / Opposite Action Check
    for pos_set, neg_set in ANTONYM_GROUPS:
        q_has_pos = bool(q_tokens & pos_set)
        q_has_neg = bool(q_tokens & neg_set)
        m_has_pos = bool(m_tokens & pos_set)
        m_has_neg = bool(m_tokens & neg_set)

        if (q_has_pos and m_has_neg) or (q_has_neg and m_has_pos) or (q_has_neg != m_has_neg):
            conflict_q = (q_tokens & (pos_set | neg_set)) or {"none"}
            conflict_m = (m_tokens & (pos_set | neg_set)) or {"none"}
            return (
                False,
                f"Action/antonym conflict between '{', '.join(sorted(conflict_q))}' and '{', '.join(sorted(conflict_m))}'",
            )

    # 2. Negation Mismatch Check
    q_neg = q_tokens & NEGATION_WORDS
    m_neg = m_tokens & NEGATION_WORDS
    if bool(q_neg) != bool(m_neg):
        return (
            False,
            f"Negation mismatch: query={sorted(q_neg)} vs cached={sorted(m_neg)}",
        )

    # 3. Numeric Mismatch Check
    q_nums = set(re.findall(r"\b\d+(?:\.\d+)?\b", q_exp))
    m_nums = set(re.findall(r"\b\d+(?:\.\d+)?\b", m_exp))
    if q_nums != m_nums and (q_nums or m_nums):
        return (
            False,
            f"Number mismatch: query={sorted(q_nums)} vs cached={sorted(m_nums)}",
        )

    # 4. Curated Entity Conflict Checks
    # 4a. Countries & Places
    q_countries = {e for e in COUNTRY_PLACE_ENTITIES if re.search(rf"\b{re.escape(e)}\b", q_exp)}
    m_countries = {e for e in COUNTRY_PLACE_ENTITIES if re.search(rf"\b{re.escape(e)}\b", m_exp)}
    if q_countries != m_countries and (q_countries or m_countries):
        return (
            False,
            f"Geographic entity conflict: query={sorted(q_countries)} vs cached={sorted(m_countries)}",
        )

    # 4b. Programming Languages & Tech Stack
    q_tech = q_tokens & TECH_ENTITIES
    m_tech = m_tokens & TECH_ENTITIES
    if q_tech != m_tech and (q_tech or m_tech):
        return (
            False,
            f"Technology entity conflict: query={sorted(q_tech)} vs cached={sorted(m_tech)}",
        )

    # 4c. Planets / Celestial Entities (block when both specify disjoint planets, or query specifies a planet not in a non-general cached prompt)
    q_planets = q_tokens & PLANET_ENTITIES
    m_planets = m_tokens & PLANET_ENTITIES
    if q_planets and m_planets and not (q_planets & m_planets):
        return (
            False,
            f"Planet entity conflict: query={sorted(q_planets)} vs cached={sorted(m_planets)}",
        )

    # 4d. Template Substitution Check (e.g., "what is the capital of X" vs "what is the capital of Y")
    q_content = q_tokens - STOPWORDS
    m_content = m_tokens - STOPWORDS
    if "capital" in q_content and "capital" in m_content:
        q_subj = q_content - {"capital", "country", "city", "nation", "state"}
        m_subj = m_content - {"capital", "country", "city", "nation", "state"}
        if q_subj != m_subj:
            return (
                False,
                f"Subject mismatch for capital query: {sorted(q_subj)} vs {sorted(m_subj)}",
            )

    return True, None


# --- Tier-1 Exact Cache: Redis with Automatic In-Memory LRU+TTL Fallback ---
class InMemoryTier1Cache:
    """Thread-safe in-memory OrderedDict LRU + TTL fallback for Tier-1 cache."""

    def __init__(self, max_size: int = 1000, default_ttl: int = 3600):
        self.max_size = max_size
        self.default_ttl = default_ttl
        self._store: OrderedDict[str, tuple[str, float]] = OrderedDict()
        self._lock = threading.Lock()

    def get(self, key: str) -> str | None:
        now = time.time()
        with self._lock:
            if key not in self._store:
                return None
            value, expires_at = self._store[key]
            if now > expires_at:
                del self._store[key]
                return None
            self._store.move_to_end(key)
            return value

    def set(self, key: str, value: str, ttl: int | None = None) -> None:
        exp = time.time() + (ttl if ttl is not None else self.default_ttl)
        with self._lock:
            if key in self._store:
                self._store.move_to_end(key)
            self._store[key] = (value, exp)
            while len(self._store) > self.max_size:
                self._store.popitem(last=False)

    def clear(self) -> int:
        with self._lock:
            count = len(self._store)
            self._store.clear()
            return count

    def size(self) -> int:
        now = time.time()
        with self._lock:
            expired = [k for k, (_, exp) in self._store.items() if now > exp]
            for k in expired:
                del self._store[k]
            return len(self._store)


_memory_tier1 = InMemoryTier1Cache(max_size=1000, default_ttl=CACHE_TTL_SECONDS)
_redis_client: redis.Redis | None = None
_redis_available = False


def _init_redis() -> None:
    global _redis_client, _redis_available
    redis_url = os.getenv("REDIS_URL")
    try:
        if redis_url:
            client = redis.from_url(redis_url, decode_responses=True, socket_connect_timeout=1.5)
        else:
            client = redis.Redis(
                host=os.getenv("REDIS_HOST", "localhost"),
                port=int(os.getenv("REDIS_PORT", 6379)),
                decode_responses=True,
                socket_connect_timeout=1.5,
            )
        client.ping()
        _redis_client = client
        _redis_available = True
        print("Successfully connected to Redis for Tier-1 cache.")
    except Exception as e:
        print(f"Redis unavailable ({e}). Using thread-safe in-memory LRU+TTL Tier-1 fallback.")
        _redis_client = None
        _redis_available = False


_init_redis()


def get_from_tier1(prompt: str) -> str | None:
    """Retrieves an exact-match response from Tier-1 using the normalized SHA-256 key."""
    key = get_exact_cache_key(prompt)
    if _redis_available and _redis_client is not None:
        try:
            val = _redis_client.get(key)
            if val is not None:
                return val
            # Backward compatibility check for raw prompt key
            raw_val = _redis_client.get(prompt)
            if raw_val is not None:
                return raw_val
        except Exception as e:
            print(f"Warning: Redis get error ({e}), falling back to in-memory Tier-1.")
    return _memory_tier1.get(key)


def set_in_tier1(prompt: str, response: str, ttl: int = CACHE_TTL_SECONDS) -> None:
    """Stores a prompt-response pair in Tier-1 (both Redis if available and in-memory fallback)."""
    key = get_exact_cache_key(prompt)
    _memory_tier1.set(key, response, ttl=ttl)
    if _redis_available and _redis_client is not None:
        try:
            _redis_client.setex(key, ttl, response)
        except Exception as e:
            print(f"Warning: Redis set error ({e}), stored in in-memory Tier-1.")


def get_tier1_status() -> dict:
    """Returns diagnostic status of the Tier-1 cache."""
    if _redis_available and _redis_client is not None:
        try:
            _redis_client.ping()
            dbsize = _redis_client.dbsize()
            return {
                "backend": "redis",
                "connected": True,
                "entries": dbsize,
                "ttl_seconds": CACHE_TTL_SECONDS,
            }
        except Exception:
            pass
    return {
        "backend": "in_memory_lru_ttl",
        "connected": True,
        "entries": _memory_tier1.size(),
        "max_size": _memory_tier1.max_size,
        "ttl_seconds": CACHE_TTL_SECONDS,
    }


# --- Tier-2 Semantic Cache: Self-Contained ChromaDB PersistentClient (Cosine Space) ---
_chroma_persist_dir = os.getenv("CHROMA_PERSIST_DIR", "./.chroma_cache")
try:
    os.makedirs(_chroma_persist_dir, exist_ok=True)
    chroma_client = chromadb.PersistentClient(
        path=_chroma_persist_dir,
        settings=Settings(anonymized_telemetry=False),
    )
    _chroma_backend = "persistent"
except Exception as e:
    print(f"Warning: ChromaDB PersistentClient failed ({e}), using EphemeralClient.")
    chroma_client = chromadb.EphemeralClient(settings=Settings(anonymized_telemetry=False))
    _chroma_backend = "ephemeral"


def get_collection():
    """
    Gets or creates the 'llm_cache' collection configured with true cosine distance space.
    Automatically upgrades legacy collections that were created without hnsw:space='cosine'.
    """
    col = chroma_client.get_or_create_collection(
        name="llm_cache",
        metadata={"hnsw:space": "cosine"},
    )
    if not col.metadata or col.metadata.get("hnsw:space") != "cosine":
        try:
            chroma_client.delete_collection(name="llm_cache")
        except Exception:
            pass
        col = chroma_client.get_or_create_collection(
            name="llm_cache",
            metadata={"hnsw:space": "cosine"},
        )
    return col


def is_response_high_quality(response: str) -> bool:
    """
    Checks if an LLM response is high-quality enough to be cached.
    Prevents 'cache poisoning' with unhelpful or error responses.
    """
    if not response or len(response.strip()) < 15:
        print("DEBUG: Response rejected by quality filter (too short).")
        return False

    lower_response = response.lower()
    error_triggers = [
        "i cannot",
        "i am not sure",
        "as an ai",
        "i do not have",
        "sorry, i encountered an error",
        "quota exceeded",
        "429",
        "gemini model is not configured",
    ]
    if any(trigger in lower_response for trigger in error_triggers):
        print("DEBUG: Response rejected by quality filter (unhelpful/error phrase).")
        return False

    return True


def _enforce_lru_policy():
    """If Tier-2 cache is at or above CACHE_MAX_SIZE, evicts the least recently accessed item."""
    collection = get_collection()
    count = collection.count()
    if count >= CACHE_MAX_SIZE:
        entries = collection.get(include=["metadatas", "documents"])
        if not entries or not entries.get("ids"):
            return
        try:
            lru_index = min(
                range(len(entries["ids"])),
                key=lambda idx: (entries["metadatas"][idx] or {}).get("last_accessed_timestamp", float("inf")),
            )
            lru_id_to_delete = entries["ids"][lru_index]
            collection.delete(ids=[lru_id_to_delete])
            print(f"DEBUG: LRU - Removed item ID: {lru_id_to_delete}")
        except (ValueError, IndexError):
            print("DEBUG: LRU - Could not determine LRU item. Skipping eviction.")


def search_semantic_cache_detailed(prompt: str) -> dict:
    """
    Searches Tier-2 ChromaDB semantic cache and returns full diagnostic details:
    {
        "hit": bool,
        "response": str | None,
        "similarity": float,
        "matched_prompt": str | None,
        "id": str | None,
        "embedding_time_ms": float,
        "guard_blocked": bool,
        "guard_reason": str | None,
    }
    """
    from .llm_provider import get_embedding_with_time

    prompt_embedding, embedding_time_ms = get_embedding_with_time(prompt)
    collection = get_collection()
    count = collection.count()
    if count == 0 or not prompt_embedding:
        return {
            "hit": False,
            "response": None,
            "similarity": 0.0,
            "matched_prompt": None,
            "id": None,
            "embedding_time_ms": embedding_time_ms,
            "guard_blocked": False,
            "guard_reason": None,
        }

    n_results = min(5, count)
    results = collection.query(
        query_embeddings=[prompt_embedding],
        n_results=n_results,
        include=["metadatas", "documents", "distances"],
    )

    if not results.get("ids") or not results["ids"][0]:
        return {
            "hit": False,
            "response": None,
            "similarity": 0.0,
            "matched_prompt": None,
            "id": None,
            "embedding_time_ms": embedding_time_ms,
            "guard_blocked": False,
            "guard_reason": None,
        }

    ids_list = results["ids"][0]
    distances_list = results["distances"][0]
    metadatas_list = results["metadatas"][0]
    documents_list = results["documents"][0] if results.get("documents") else [None] * len(ids_list)

    top_blocked_info = None
    best_overall_sim = 0.0
    best_overall_prompt = None
    best_overall_id = None

    for idx, hit_id in enumerate(ids_list):
        distance = float(distances_list[idx])
        similarity = round(max(0.0, min(1.0, 1.0 - distance)), 4)
        meta = dict(metadatas_list[idx] or {})
        matched_prompt = meta.get("prompt") or documents_list[idx] or ""

        if idx == 0:
            best_overall_sim = similarity
            best_overall_prompt = matched_prompt
            best_overall_id = hit_id

        if similarity >= CACHE_THRESHOLD:
            passed, reason = passes_entity_and_negation_guard(prompt, matched_prompt)
            if passed:
                now = time.time()
                meta["last_accessed_timestamp"] = now
                meta["hit_count"] = int(meta.get("hit_count", 0)) + 1
                try:
                    collection.update(ids=[hit_id], metadatas=[meta])
                except Exception:
                    pass
                return {
                    "hit": True,
                    "response": meta.get("response"),
                    "similarity": similarity,
                    "matched_prompt": matched_prompt,
                    "id": hit_id,
                    "embedding_time_ms": embedding_time_ms,
                    "guard_blocked": False,
                    "guard_reason": None,
                }
            else:
                print(
                    f"DEBUG: Guardrail blocked semantic match '{matched_prompt}' "
                    f"(sim={similarity:.4f}): {reason}"
                )
                if top_blocked_info is None:
                    top_blocked_info = {
                        "similarity": similarity,
                        "matched_prompt": matched_prompt,
                        "id": hit_id,
                        "guard_reason": reason,
                    }

    if top_blocked_info is not None:
        return {
            "hit": False,
            "response": None,
            "similarity": top_blocked_info["similarity"],
            "matched_prompt": top_blocked_info["matched_prompt"],
            "id": top_blocked_info["id"],
            "embedding_time_ms": embedding_time_ms,
            "guard_blocked": True,
            "guard_reason": top_blocked_info["guard_reason"],
        }

    return {
        "hit": False,
        "response": None,
        "similarity": best_overall_sim,
        "matched_prompt": best_overall_prompt,
        "id": best_overall_id,
        "embedding_time_ms": embedding_time_ms,
        "guard_blocked": False,
        "guard_reason": None,
    }


def find_in_semantic_cache(prompt: str) -> tuple[dict | None, float]:
    """
    Backward-compatible Tier-2 search returning (result_dict_or_none, embedding_time_ms).
    """
    detailed = search_semantic_cache_detailed(prompt)
    embedding_time_ms = detailed["embedding_time_ms"]
    if detailed["hit"]:
        return (
            {
                "response": detailed["response"],
                "similarity": detailed["similarity"],
                "matched_prompt": detailed["matched_prompt"],
                "id": detailed["id"],
                "guard_blocked": False,
            },
            embedding_time_ms,
        )
    return None, embedding_time_ms


def add_to_semantic_cache(prompt: str, response: str, source: str = "llm") -> str | None:
    """Adds a prompt and its response to the Tier-2 ChromaDB semantic cache."""
    _enforce_lru_policy()
    collection = get_collection()

    from .llm_provider import get_embedding

    prompt_embedding = get_embedding(prompt)
    if not prompt_embedding:
        return None

    norm_prompt = normalize_prompt(prompt)
    # Use deterministic UUID5 based on normalized prompt to avoid duplicate vector entries
    doc_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"llm_cache:{norm_prompt}"))
    now = time.time()

    metadata = {
        "prompt": prompt,
        "normalized_prompt": norm_prompt,
        "response": response,
        "source": source,
        "created_at": now,
        "last_accessed_timestamp": now,
        "hit_count": 0,
        "id": doc_id,
    }

    collection.upsert(
        embeddings=[prompt_embedding],
        documents=[prompt],
        metadatas=[metadata],
        ids=[doc_id],
    )
    print(f"DEBUG: Added/updated prompt in T2 semantic cache with ID '{doc_id}' (source={source}).")
    return doc_id


# --- Management & Observability Functions ---
def list_cache_entries(limit: int = 50) -> list[dict]:
    """Returns up to `limit` entries from Tier-2 semantic cache sorted by most recently accessed."""
    collection = get_collection()
    if collection.count() == 0:
        return []
    raw = collection.get(include=["metadatas", "documents"])
    ids = raw.get("ids") or []
    metadatas = raw.get("metadatas") or []
    documents = raw.get("documents") or []

    items = []
    for idx, entry_id in enumerate(ids):
        meta = dict(metadatas[idx] or {})
        doc = documents[idx] if idx < len(documents) else ""
        items.append(
            {
                "id": entry_id,
                "prompt": meta.get("prompt") or doc,
                "normalized_prompt": meta.get("normalized_prompt") or normalize_prompt(doc),
                "response": meta.get("response", ""),
                "source": meta.get("source", "llm"),
                "created_at": meta.get("created_at"),
                "last_accessed_timestamp": meta.get("last_accessed_timestamp", 0.0),
                "hit_count": int(meta.get("hit_count", 0)),
            }
        )

    items.sort(key=lambda x: x.get("last_accessed_timestamp") or 0.0, reverse=True)
    return items[: max(1, int(limit))]


def delete_cache_entry(entry_id: str) -> bool:
    """Deletes a specific entry by ID from Tier-2 semantic cache (and corresponding Tier-1 key)."""
    collection = get_collection()
    existing = collection.get(ids=[entry_id], include=["metadatas", "documents"])
    if not existing or not existing.get("ids"):
        return False

    meta = (existing.get("metadatas") or [{}])[0] or {}
    prompt = meta.get("prompt") or ((existing.get("documents") or [""])[0])
    if prompt:
        key = get_exact_cache_key(prompt)
        if _redis_available and _redis_client is not None:
            try:
                _redis_client.delete(key)
            except Exception:
                pass
        with _memory_tier1._lock:
            _memory_tier1._store.pop(key, None)

    collection.delete(ids=[entry_id])
    return True


def clear_all_caches() -> dict:
    """Clears both Tier-1 (Redis + In-Memory) and Tier-2 (ChromaDB) caches."""
    t1_cleared = _memory_tier1.clear()
    if _redis_available and _redis_client is not None:
        try:
            _redis_client.flushdb()
        except Exception:
            pass

    collection = get_collection()
    t2_count = collection.count()
    if t2_count > 0:
        try:
            existing = collection.get(include=[])
            existing_ids = existing.get("ids") if existing else []
            if existing_ids:
                collection.delete(ids=existing_ids)
        except Exception as e:
            print(f"Warning: Could not clear Tier-2 collection items: {e}")

    return {
        "status": "cleared",
        "tier1_cleared": t1_cleared,
        "tier2_cleared": t2_count,
    }


def get_cache_config() -> dict:
    """Returns current Tier-1 and Tier-2 cache configuration and entry counts."""
    collection = get_collection()
    return {
        "threshold": CACHE_THRESHOLD,
        "max_size": CACHE_MAX_SIZE,
        "ttl_seconds": CACHE_TTL_SECONDS,
        "tier1": get_tier1_status(),
        "tier2": {
            "backend": _chroma_backend,
            "persist_dir": _chroma_persist_dir,
            "collection": "llm_cache",
            "distance_metric": "cosine",
            "entries": collection.count(),
        },
    }
