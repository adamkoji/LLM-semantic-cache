import chromadb
from chromadb.config import Settings
import time
import uuid

# --- Configuration ---
CACHE_MAX_SIZE = 100
CACHE_THRESHOLD = 0.64

# --- ChromaDB Client Setup ---
# The client is initialized once, but the collection will be fetched on each request.
client = chromadb.HttpClient(host='localhost', port=8001, settings=Settings(anonymized_telemetry=False))

# --- Helper function to get the collection ---
def get_collection():
    """Safely gets or creates the collection on every call."""
    return client.get_or_create_collection(name="llm_cache")


def is_response_high_quality(response: str) -> bool:
    """
    Checks if an LLM response is high-quality enough to be cached.
    Prevents "cache poisoning" with unhelpful or error responses.
    """
    if not response or len(response) < 15:
        print(f"DEBUG: Response rejected by quality filter (too short).")
        return False
    
    # --- THIS IS THE FIX ---
    # Convert response to lowercase once for efficiency
    lower_response = response.lower()
    
    # Check for common error phrases from APIs or our own code
    error_triggers = [
        "i cannot", "i am not sure", "as an ai", "i do not have",
        "sorry, i encountered an error", "quota exceeded", "429",
    ]
    if any(trigger in lower_response for trigger in error_triggers):
        print(f"DEBUG: Response rejected by quality filter (unhelpful/error phrase).")
        return False
        
    return True


def _enforce_lru_policy():
    """If cache is full, removes the least recently used item."""
    collection = get_collection() # Fetch the current collection object
    count = collection.count()
    if count >= CACHE_MAX_SIZE:
        entries = collection.get(include=["metadatas", "documents"])
        if not entries['ids']: return

        try:
            lru_entry_metadata = min(entries['metadatas'], key=lambda x: x.get('last_accessed_timestamp', float('inf')))
            lru_index = entries['metadatas'].index(lru_entry_metadata)
            lru_id_to_delete = entries['ids'][lru_index]
            collection.delete(ids=[lru_id_to_delete])
            print(f"DEBUG: LRU - Removed item ID: {lru_id_to_delete}")
        except (ValueError, IndexError):
            print("DEBUG: LRU - Could not determine LRU item. Skipping eviction.")


def find_in_semantic_cache(prompt: str):
    """
    Searches the Tier-2 cache and returns the result along with the embedding time.
    """
    collection = get_collection()
    if collection.count() == 0:
        return None, 0 # No result, 0 embedding time

    from .llm_provider import get_embedding
    
    # --- THIS IS THE NEW PART ---
    start_time = time.time()
    prompt_embedding = get_embedding(prompt)
    embedding_time_ms = (time.time() - start_time) * 1000
    # --- END OF NEW PART ---
    
    results = collection.query(query_embeddings=[prompt_embedding], n_results=1)
    
    if not results['ids'] or not results['distances'][0]:
        # We still return the embedding time even on a miss
        return None, embedding_time_ms

    distance = results['distances'][0][0]
    similarity = 1 - distance
    
    print(f"DEBUG: T2 Semantic Search - Calculated Similarity: {similarity:.4f}")

    if similarity >= CACHE_THRESHOLD:
        hit_id = results['ids'][0][0]
        existing_metadata = results['metadatas'][0][0]
        existing_metadata['last_accessed_timestamp'] = time.time()
        collection.update(ids=[hit_id], metadatas=[existing_metadata])
        
        # Return the result AND the embedding time
        return {"response": existing_metadata.get("response"), "similarity": similarity}, embedding_time_ms
    else:
        # Return no result, but still provide the embedding time
        return None, embedding_time_ms


def add_to_semantic_cache(prompt: str, response: str):
    """Adds a new prompt and its response to the Tier-2 semantic cache."""
    _enforce_lru_policy()
    collection = get_collection() # Fetch the current collection object
    
    from .llm_provider import get_embedding # Local import
    prompt_embedding = get_embedding(prompt)
    
    doc_id = str(uuid.uuid4())
    
    collection.add(
        embeddings=[prompt_embedding],
        documents=[prompt],
        metadatas=[{"response": response, "last_accessed_timestamp": time.time()}],
        ids=[doc_id]
    )
    print(f"DEBUG: Added prompt to T2 semantic cache with new ID '{doc_id}'.")