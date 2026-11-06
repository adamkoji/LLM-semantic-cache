import chromadb
import json

# --- Configuration ---
COLLECTION_NAME = "llm_cache"

def inspect_chromadb():
    """Connects to the running ChromaDB server and prints its contents."""
    print("--- ChromaDB Inspection Tool ---")
    
    try:
        # We must use the same HttpClient to connect to the same server
        client = chromadb.HttpClient(host='localhost', port=8001)
        # Check if the client can connect to the server
        client.heartbeat() 
        print("Successfully connected to ChromaDB server.")
    except Exception as e:
        print("\nERROR: Could not connect to ChromaDB server.")
        print("Please ensure your main FastAPI application (uvicorn) is running, as it hosts the database.")
        print(f"Details: {e}")
        return

    try:
        collection = client.get_collection(name=COLLECTION_NAME)
        count = collection.count()
        
        if count == 0:
            print("\nThe collection is currently empty.")
            return
            
        print(f"\nFound collection '{COLLECTION_NAME}' with {count} entries.")
        
        # Retrieve all items from the collection
        # We include embeddings to show what they look like
        items = collection.get(include=["metadatas", "documents", "embeddings"])
        
        print("\n--- Contents of the Collection ---")
        for i in range(count):
            doc_id = items['ids'][i]
            document = items['documents'][i]
            metadata = items['metadatas'][i]
            embedding = items['embeddings'][i]

            print(f"\n----------------------------------")
            print(f"  ID: {doc_id}")
            print(f"  Document (Prompt): '{document}'")
            
            # Pretty print the metadata
            print(f"  Metadata: {json.dumps(metadata, indent=4)}")
            
            # Show a snippet of the embedding vector
            embedding_snippet = embedding[:5] # Show the first 5 dimensions
            print(f"  Embedding (first 5 of {len(embedding)} dims): {embedding_snippet}...")
            print(f"----------------------------------")
            
    except Exception as e:
        print(f"\nAn error occurred while fetching the collection: {e}")
        print(f"Does the collection '{COLLECTION_NAME}' exist?")

if __name__ == "__main__":
    inspect_chromadb()