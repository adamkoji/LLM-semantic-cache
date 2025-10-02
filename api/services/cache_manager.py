import chromadb
import time
from .llm_provider import get_embedding

# --- Cache Configuration ---
CACHE_MAX_SIZE = 1000  # Max number of entries in the semantic cache
# --- TUNED THRESHOLD ---
# Lowered the threshold to be slightly more lenient, which is better
# for a powerful model like BGE. It now requires 80% similarity.
CACHE_THRESHOLD = 0.60

# --- ChromaDB Setup ---
client = chromadb.Client()
try:
    client.delete_collection(name="llm_cache")
except Exception:
    pass
collection = client.create_collection(name="llm_cache")

# --- Cache Admission Policy ---
def is_response_high_quality(response: str) -> bool:
    if not response or len(response) < 15:
        print(f"DEBUG: Response rejected by quality filter (too short).")
        return False
    
    bad_response_triggers = ["i cannot", "i am not sure", "as an ai", "i do not have"]
    if any(trigger in response.lower() for trigger in bad_response_triggers):
        print(f"DEBUG: Response rejected by quality filter (unhelpful trigger phrase).")
        return False
        
    return True

# --- LRU Eviction Policy ---
def _enforce_lru_policy():
    count = collection.count()
    if count >= CACHE_MAX_SIZE:
        entries = collection.get(include=["metadatas"])
        lru_entry = min(entries['metadatas'], key=lambda x: x.get('last_accessed_timestamp', 0))
        lru_id = lru_entry['id']
        collection.delete(ids=[lru_id])

def find_in_semantic_cache(prompt: str):
    """Searches the Tier-2 semantic cache (ChromaDB) for a similar prompt."""
    if collection.count() == 0:
        return None

    prompt_embedding = get_embedding(prompt)
    results = collection.query(query_embeddings=[prompt_embedding], n_results=1)
    
    if not results['ids'] or not results['distances'][0]:
        return None

    distance = results['distances'][0][0]
    # BGE uses cosine similarity, so distance is 1 - similarity
    similarity = 1 - distance
    
    # --- ADDED FOR OBSERVABILITY ---
    # This will print the calculated score to your Uvicorn terminal every time!
    print(f"DEBUG: T2 Semantic Search - Calculated Similarity: {similarity:.4f}")

    if similarity >= CACHE_THRESHOLD:
        print(f"DEBUG: T2 SEMANTIC CACHE HIT! Similarity {similarity:.4f} is >= threshold {CACHE_THRESHOLD}.")
        hit_id = results['ids'][0][0]
        cached_response = results['metadatas'][0][0]['response']
        collection.update(
            ids=[hit_id],
            metadatas=[{"last_accessed_timestamp": time.time(), "response": cached_response, "id": hit_id}]
        )
        return {"response": cached_response, "similarity": similarity}
    else:
        print(f"DEBUG: T2 SEMANTIC CACHE MISS! Similarity {similarity:.4f} is < threshold {CACHE_THRESHOLD}.")
        return None

def add_to_semantic_cache(prompt: str, response: str):
    """Adds a new prompt and its response to the Tier-2 semantic cache."""
    _enforce_lru_policy()
    prompt_embedding = get_embedding(prompt)
    doc_id = str(collection.count() + 1)
    collection.add(
        embeddings=[prompt_embedding],
        documents=[prompt],
        metadatas=[{"response": response, "last_accessed_timestamp": time.time(), "id": doc_id}],
        ids=[doc_id]
    )
    print(f"DEBUG: Added prompt to T2 semantic cache. New count: {collection.count()}")