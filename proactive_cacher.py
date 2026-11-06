import requests
import numpy as np
from sklearn.cluster import DBSCAN
from api.services.llm_provider import get_embedding, get_llm_response
from collections import Counter

# --- Configuration ---
LOG_FILE = "cache_misses.log"
API_WARM_URL = "http://127.0.0.1:8000/warm-cache/"
# DBSCAN's `eps` is the max distance between two samples. Conceptually similar to (1 - similarity_threshold).
DBSCAN_EPS = 0.4 
MIN_CLUSTER_SIZE = 3 # The minimum number of similar prompts to be considered an "emerging topic"

def read_missed_prompts():
    """Reads all unique prompts from the log file."""
    try:
        with open(LOG_FILE, "r") as f:
            prompts = set(line.strip() for line in f if line.strip())
        print(f"Read {len(prompts)} unique missed prompts from {LOG_FILE}.")
        return list(prompts)
    except FileNotFoundError:
        print(f"Log file '{LOG_FILE}' not found. No misses to analyze.")
        return []

def find_emerging_topics(prompts):
    """Uses DBSCAN clustering to find groups of semantically similar prompts."""
    if len(prompts) < MIN_CLUSTER_SIZE:
        print("Not enough unique prompts to form a cluster.")
        return None

    print("Generating embeddings for all missed prompts...")
    embeddings = np.array([get_embedding(p) for p in prompts])
    
    print(f"Running DBSCAN clustering with eps={DBSCAN_EPS} and min_samples={MIN_CLUSTER_SIZE}...")
    clustering = DBSCAN(eps=DBSCAN_EPS, min_samples=MIN_CLUSTER_SIZE, metric='cosine').fit(embeddings)
    
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

def get_canonical_response(cluster_prompts):
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
        print(f"Successfully generated canonical Q&A.")
        return question, answer
    except IndexError:
        print("Error: LLM response for canonical Q&A was not in the expected format.")
        return None, None

def generate_paraphrases(canonical_question):
    """Uses an LLM to generate variations of a question to enrich the cache."""
    print("\nGenerating paraphrases to warm the cache via LLM...")
    system_prompt = f"""
    Generate 5 common, alternative ways a user might ask the following question.
    Do not number them. Each paraphrase should be on a new line.

    Original Question: "{canonical_question}"
    """
    response = get_llm_response(system_prompt)
    paraphrases = [p.strip() for p in response.split('\n') if p.strip()]
    print(f"Generated {len(paraphrases)} paraphrases.")
    return paraphrases

def warm_cache(prompts, answer):
    """Sends prompts and a canonical answer to the warming endpoint."""
    print("\nWarming the cache by sending new entries to the API...")
    success_count = 0
    for prompt in prompts:
        try:
            response = requests.post(API_WARM_URL, json={"prompt": prompt, "answer": answer})
            if response.status_code == 200:
                success_count += 1
            else:
                print(f"  - FAILED to warm cache for: '{prompt}' (Status: {response.status_code})")
        except requests.exceptions.RequestException:
            print(f"  - FAILED to connect to API to warm cache for: '{prompt}'")
    print(f"Successfully warmed cache with {success_count} entries.")


if __name__ == "__main__":
    missed_prompts = read_missed_prompts()
    if missed_prompts:
        topic_cluster = find_emerging_topics(missed_prompts)
        if topic_cluster:
            canonical_q, canonical_a = get_canonical_response(topic_cluster)
            if canonical_q and canonical_a:
                paraphrases = generate_paraphrases(canonical_q)
                # Combine all prompts into a master list for warming
                all_prompts_to_warm = list(set(topic_cluster + paraphrases + [canonical_q]))
                warm_cache(all_prompts_to_warm, canonical_a)
                print("\nProactive caching process complete.")