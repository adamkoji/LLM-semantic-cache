import os
import requests
import numpy as np
from sklearn.cluster import DBSCAN
from collections import Counter
from api.services.llm_provider import get_embedding, get_llm_response

# --- Configuration ---
LOG_FILE = os.getenv("CACHE_MISS_LOG_FILE", "cache_misses.log")
API_WARM_URL = os.getenv("API_WARM_URL", "http://127.0.0.1:8000/warm-cache/")
# DBSCAN's `eps` is the max cosine distance between two samples (1 - similarity).
DBSCAN_EPS = 0.42
MIN_CLUSTER_SIZE = 3  # The minimum number of similar prompts to be considered an "emerging topic"


def get_missed_prompts() -> list[str]:
    """Reads all unique missed prompts from cache_misses.log preserving order of first appearance."""
    if not os.path.exists(LOG_FILE):
        return []
    seen = set()
    unique_prompts: list[str] = []
    try:
        with open(LOG_FILE, "r", encoding="utf-8") as f:
            for line in f:
                p = line.strip()
                if p and p not in seen:
                    seen.add(p)
                    unique_prompts.append(p)
        return unique_prompts
    except Exception as e:
        print(f"Error reading '{LOG_FILE}': {e}")
        return []


def read_missed_prompts() -> list[str]:
    """Reads all unique prompts from the log file (backward-compatible helper)."""
    prompts = get_missed_prompts()
    print(f"Read {len(prompts)} unique missed prompts from {LOG_FILE}.")
    return prompts


def clear_missed_prompts() -> None:
    """Clears the cache_misses.log file."""
    try:
        if os.path.exists(LOG_FILE):
            with open(LOG_FILE, "w", encoding="utf-8") as f:
                f.write("")
    except Exception as e:
        print(f"Error clearing '{LOG_FILE}': {e}")


def find_emerging_topics(
    prompts: list[str],
    eps: float = DBSCAN_EPS,
    min_cluster_size: int = MIN_CLUSTER_SIZE,
) -> list[str] | None:
    """Uses DBSCAN clustering to find groups of semantically similar prompts."""
    if len(prompts) < min_cluster_size:
        print("Not enough unique prompts to form a cluster.")
        return None

    print("Generating embeddings for all missed prompts...")
    embeddings = np.array([get_embedding(p) for p in prompts])
    if embeddings.ndim != 2 or embeddings.shape[0] < min_cluster_size:
        return None

    print(f"Running DBSCAN clustering with eps={eps} and min_samples={min_cluster_size}...")
    clustering = DBSCAN(eps=eps, min_samples=min_cluster_size, metric="cosine").fit(embeddings)

    labels = clustering.labels_

    # Find the largest cluster (ignoring noise points, which are labeled -1)
    if len(set(labels)) == 1 and -1 in labels:
        print("No significant clusters found (all points considered noise).")
        return None

    cluster_counts = Counter(l for l in labels if l != -1).most_common(1)
    if not cluster_counts:
        print("No clusters found that met the minimum size criteria.")
        return None

    largest_cluster_label = cluster_counts[0][0]
    cluster_prompts = [prompts[i] for i, label in enumerate(labels) if label == largest_cluster_label]

    print(f"\nFound emerging topic with {len(cluster_prompts)} related prompts:")
    for p in cluster_prompts:
        print(f"  - {p}")

    return cluster_prompts


def get_canonical_response(cluster_prompts: list[str]) -> tuple[str | None, str | None]:
    """Uses an LLM to generate a single, high-quality response for a cluster of prompts."""
    print("\nGenerating a canonical response for the topic via LLM...")

    prompt_list = "\n".join(f"- {p}" for p in cluster_prompts)
    system_prompt = f"""
    The following user questions are all about the same topic.
    First, summarize these questions into a single, representative question.
    Second, provide a comprehensive, high-quality answer for that representative question.

    User Questions:
    {prompt_list}

    Format your response ONLY as follows:
    CANONICAL_QUESTION: [Your representative question here]
    CANONICAL_ANSWER: [Your comprehensive answer here]
    """

    response = get_llm_response(system_prompt)

    try:
        question = response.split("CANONICAL_QUESTION:")[1].split("CANONICAL_ANSWER:")[0].strip()
        answer = response.split("CANONICAL_ANSWER:")[1].strip()
        print("Successfully generated canonical Q&A.")
        return question, answer
    except IndexError:
        print("Error: LLM response for canonical Q&A was not in the expected format.")
        return None, None


def generate_paraphrases(canonical_question: str) -> list[str]:
    """Uses an LLM to generate variations of a question to enrich the cache."""
    print("\nGenerating paraphrases to warm the cache via LLM...")
    system_prompt = f"""
    Generate 5 common, alternative ways a user might ask the following question.
    Do not number them. Each paraphrase should be on a new line.

    Original Question: "{canonical_question}"
    """
    response = get_llm_response(system_prompt)
    paraphrases = [
        p.strip().lstrip("0123456789.-*) ").strip()
        for p in response.split("\n")
        if p.strip()
    ]
    print(f"Generated {len(paraphrases)} paraphrases.")
    return paraphrases[:5]


def warm_cache(prompts: list[str], answer: str, direct_mode: bool = False) -> int:
    """Sends prompts and a canonical answer to the warming endpoint or directly to cache_manager."""
    print("\nWarming the cache...")
    success_count = 0

    if direct_mode:
        from api.services import cache_manager, metrics_manager

        for prompt in prompts:
            cache_manager.set_in_tier1(prompt, answer)
            cache_manager.add_to_semantic_cache(prompt, answer, source="proactive_warm")
            success_count += 1
        metrics_manager.record_proactive_warm(success_count)
        print(f"Successfully warmed cache directly with {success_count} entries.")
        return success_count

    for prompt in prompts:
        try:
            response = requests.post(API_WARM_URL, json={"prompt": prompt, "answer": answer}, timeout=10)
            if response.status_code == 200:
                success_count += 1
            else:
                print(f"  - FAILED to warm cache for: '{prompt}' (Status: {response.status_code})")
        except requests.exceptions.RequestException:
            # Fallback to direct mode if API server is not reachable via HTTP
            try:
                from api.services import cache_manager, metrics_manager

                cache_manager.set_in_tier1(prompt, answer)
                cache_manager.add_to_semantic_cache(prompt, answer, source="proactive_warm")
                metrics_manager.record_proactive_warm(1)
                success_count += 1
            except Exception:
                print(f"  - FAILED to connect to API to warm cache for: '{prompt}'")

    print(f"Successfully warmed cache with {success_count} entries.")
    return success_count


def run_proactive_warming_pipeline(
    direct_mode: bool = True,
    min_cluster_size: int = MIN_CLUSTER_SIZE,
    eps: float = DBSCAN_EPS,
) -> dict:
    """
    High-level proactive caching pipeline usable from both CLI and FastAPI endpoints.
    Reads unique missed prompts from cache_misses.log, clusters them with DBSCAN (cosine),
    synthesizes a Canonical Question + Canonical Answer + 5 Paraphrases, and warms Tier-1 & Tier-2.
    """
    missed_prompts = get_missed_prompts()
    if len(missed_prompts) < min_cluster_size:
        return {
            "status": "insufficient_data",
            "missed_prompts_count": len(missed_prompts),
            "cluster_prompts": [],
            "canonical_question": None,
            "canonical_answer": None,
            "paraphrases": [],
            "entries_warmed": 0,
        }

    topic_cluster = find_emerging_topics(missed_prompts, eps=eps, min_cluster_size=min_cluster_size)
    if not topic_cluster:
        return {
            "status": "no_clusters",
            "missed_prompts_count": len(missed_prompts),
            "cluster_prompts": [],
            "canonical_question": None,
            "canonical_answer": None,
            "paraphrases": [],
            "entries_warmed": 0,
        }

    canonical_q, canonical_a = get_canonical_response(topic_cluster)
    if not canonical_q or not canonical_a:
        return {
            "status": "no_clusters",
            "missed_prompts_count": len(missed_prompts),
            "cluster_prompts": topic_cluster,
            "canonical_question": None,
            "canonical_answer": None,
            "paraphrases": [],
            "entries_warmed": 0,
        }

    paraphrases = generate_paraphrases(canonical_q)
    # Combine all unique prompts preserving order
    all_prompts_to_warm: list[str] = []
    for p in topic_cluster + [canonical_q] + paraphrases:
        if p and p not in all_prompts_to_warm:
            all_prompts_to_warm.append(p)

    entries_warmed = warm_cache(all_prompts_to_warm, canonical_a, direct_mode=direct_mode)

    return {
        "status": "warmed",
        "missed_prompts_count": len(missed_prompts),
        "cluster_prompts": topic_cluster,
        "canonical_question": canonical_q,
        "canonical_answer": canonical_a,
        "paraphrases": paraphrases,
        "entries_warmed": entries_warmed,
    }


if __name__ == "__main__":
    report = run_proactive_warming_pipeline(direct_mode=False)
    print(f"\nProactive caching process complete: status={report['status']}, entries_warmed={report['entries_warmed']}")
