import redis
import os
import chromadb
from chromadb.config import Settings

# --- Configuration ---
# Must match the parameters of your BGE embedding model
VECTOR_DIMENSIONS = 1024
VECTOR_DATA_TYPE_BYTES = 4  # (32-bit float = 4 bytes)

# Estimated overhead for HNSW index. This is a conservative industry estimate.
# It means the index takes about 1.5x the space of the raw vectors.
HNSW_OVERHEAD_FACTOR = 1.5 

# Average text sizes (in bytes) for estimation
AVG_PROMPT_BYTES = 100
AVG_RESPONSE_BYTES = 800
AVG_METADATA_OVERHEAD_BYTES = 100 # For timestamps, etc.

def analyze_chromadb_entry():
    """Calculates the estimated size of a single entry in the ChromaDB cache."""
    print("--- ChromaDB (Tier-2 Semantic Cache) Resource Analysis ---")
    
    # 1. Calculate raw vector size
    raw_vector_size_kb = (VECTOR_DIMENSIONS * VECTOR_DATA_TYPE_BYTES) / 1024
    print(f"\n1. Raw Vector Size:")
    print(f"   - Dimensions: {VECTOR_DIMENSIONS}")
    print(f"   - Data Type: {VECTOR_DATA_TYPE_BYTES} bytes per dimension (float32)")
    print(f"   - Size = {VECTOR_DIMENSIONS} * {VECTOR_DATA_TYPE_BYTES} bytes = {raw_vector_size_kb * 1024:.0f} bytes or {raw_vector_size_kb:.2f} KB")

    # 2. Calculate the size of the vector *within the HNSW index*
    indexed_vector_size_kb = (raw_vector_size_kb * HNSW_OVERHEAD_FACTOR)
    print(f"\n2. Indexed Vector Size (in RAM/Disk):")
    print(f"   - HNSW Index Overhead Factor: {HNSW_OVERHEAD_FACTOR}x (estimate)")
    print(f"   - Size = {raw_vector_size_kb:.2f} KB * {HNSW_OVERHEAD_FACTOR} = {indexed_vector_size_kb:.2f} KB")

    # 3. Calculate the size of stored documents and metadata
    metadata_size_kb = (AVG_PROMPT_BYTES + AVG_RESPONSE_BYTES + AVG_METADATA_OVERHEAD_BYTES) / 1024
    print(f"\n3. Document & Metadata Storage Size:")
    print(f"   - Average Prompt: {AVG_PROMPT_BYTES} bytes")
    print(f"   - Average Response: {AVG_RESPONSE_BYTES} bytes")
    print(f"   - Overhead: {AVG_METADATA_OVERHEAD_BYTES} bytes")
    print(f"   - Total Text Size = {metadata_size_kb * 1024:.0f} bytes or {metadata_size_kb:.2f} KB")

    # 4. Calculate total estimated size per entry
    total_size_per_entry_kb = indexed_vector_size_kb + metadata_size_kb
    print("\n---------------------------------------------------------")
    print(f"ESTIMATED TOTAL SIZE PER ENTRY: {total_size_per_entry_kb:.2f} KB")
    print("---------------------------------------------------------")

    # 5. Extrapolate for scale
    ram_for_1m_entries_gb = (total_size_per_entry_kb * 1_000_000) / (1024 * 1024)
    print(f"\nExtrapolation for Scale:")
    print(f" - Storing 1 Million semantic entries would require approximately {ram_for_1m_entries_gb:.2f} GB of RAM.")
    
    return total_size_per_entry_kb

def analyze_redis_usage():
    """Connects to the running Redis server and reports its memory usage."""
    print("\n\n--- Redis (Tier-1 Exact-Match Cache) Resource Analysis ---")
    try:
        r = redis.Redis(
            host=os.getenv("REDIS_HOST", "localhost"),
            port=int(os.getenv("REDIS_PORT", 6379))
        )
        r.ping()
        print("Successfully connected to Redis server.")
        
        # Get memory usage info from Redis
        info = r.info('memory')
        total_memory_used_bytes = info['used_memory']
        total_memory_used_kb = total_memory_used_bytes / 1024
        
        # Get the number of keys to calculate average
        num_keys = r.dbsize()
        
        print(f"\nLive Memory Usage:")
        print(f" - Total RAM currently used by Redis: {total_memory_used_kb:.2f} KB")
        print(f" - Number of items currently in cache: {num_keys}")
        
        if num_keys > 0:
            avg_size_per_key_bytes = total_memory_used_bytes / num_keys
            print(f" - Average size per item (incl. overhead): {avg_size_per_key_bytes:.2f} bytes")

        # Theoretical Calculation
        theoretical_size_kb = (AVG_PROMPT_BYTES + AVG_RESPONSE_BYTES) / 1024
        print(f"\nTheoretical Size per Entry (Text Only): {theoretical_size_kb:.2f} KB")

    except Exception as e:
        print("\nERROR: Could not connect to the Redis server.")
        print("Please ensure Redis is running via Docker and is accessible.")
        print(f"Details: {e}")

if __name__ == "__main__":
    analyze_chromadb_entry()
    analyze_redis_usage()