import os
import subprocess
import time
import requests
import random
import numpy as np
import matplotlib.pyplot as plt
import redis # For robust cache flushing

# --- Configuration ---
API_URL = "http://127.0.0.1:8000/process-prompt/"
TOTAL_PROMPTS = 100 # A focused workload for a clean comparison
API_DELAY_SECONDS = 1.1

MODELS_TO_TEST = {
    "MiniLM-L6-v2": "all-MiniLM-L6-v2",
    "E5-Base-v2": "intfloat/e5-base-v2",
    "BGE-Base-v1.5": "BAAI/bge-base-en-v1.5",
    "Nomic-Embed-v1": "nomic-ai/nomic-embed-text-v1",
}

# --- Semantically Focused Workload Definition ---
def generate_semantic_workload(total_prompts):
    """
    Generates a workload with ZERO identical repeats to test semantic capabilities.
    """
    print(f"\nGenerating a semantically-focused workload of {total_prompts} unique prompts...")
    
    prompt_map = {
        "ml": ["What is machine learning?", "what is ml?", "explain machine learning", "define ml", "how does machine learning work"],
        "france": ["What is the capital of France?", "france's capital?", "tell me the capital of france", "paris is the capital of what country"],
        "nn": ["How does a neural network work?", "explain neural networks", "describe a neural network", "what are artificial neural networks"],
        "photo": ["What is photosynthesis?", "explain photosynthesis simply", "what is the process of photosynthesis", "how do plants make food"],
        "hamlet": ["Who wrote 'Hamlet'?", "shakespeare's hamlet author", "author of hamlet", "did shakespeare write hamlet"],
        "relativity": ["What is the theory of relativity?", "explain relativity", "einstein's theory of relativity", "what is e=mc^2"],
    }
    
    all_unique_prompts = [prompt for sublist in prompt_map.values() for prompt in sublist]
    
    if total_prompts > len(all_unique_prompts):
        print(f"Warning: Workload size ({total_prompts}) is larger than unique prompts ({len(all_unique_prompts)}). Using all available.")
        workload = all_unique_prompts
    else:
        workload = random.sample(all_unique_prompts, total_prompts)

    random.shuffle(workload)
    print(f"Workload generated with {len(workload)} unique, paraphrased prompts.")
    return workload, len(prompt_map)

def run_test_for_current_model(model_name, workload, num_topics):
    """Runs the workload and collects detailed performance metrics."""
    print(f"\n--- Running simulation for model: {model_name} ---")
    
    # --- ROBUST CACHE RESET ---
    print("  - Resetting caches before the run...")
    try:
        r = redis.Redis(host=os.getenv("REDIS_HOST", "localhost"), port=int(os.getenv("REDIS_PORT", 6379)))
        r.flushall()
        print("  - Redis cache flushed successfully.")
        
        import chromadb
        chroma_client = chromadb.HttpClient(host='localhost', port=8001)
        chroma_client.delete_collection(name="llm_cache")
        chroma_client.create_collection(name="llm_cache")
        print("  - ChromaDB collection reset successfully.")
    except Exception as e:
        print(f"  - WARNING: Could not reset caches. {e}")

    results = []
    for i, prompt in enumerate(workload):
        try:
            response = requests.post(API_URL, json={"prompt": prompt})
            if response.status_code == 200:
                data = response.json()
                results.append(data) # Append the full JSON response
                status = "HIT (T" + str(data.get('cache_tier')) + ")" if data.get("from_cache") else "MISS"
                print(f"  Prompt {i+1}/{len(workload)}: {status} (Latency: {data.get('latency_ms',0):.0f}ms, Embed: {data.get('embedding_time_ms',0):.0f}ms)")
            else:
                results.append({})
            time.sleep(API_DELAY_SECONDS)
        except requests.exceptions.RequestException:
            results.append({})
            
    # --- METRIC CALCULATION FOR ALL THREE METRICS ---
    total_requests = len(results)
    semantic_hits = sum(1 for r in results if r.get('cache_tier') == 2)
    semantic_opportunities = total_requests - num_topics
    
    # 1. Accuracy
    semantic_hit_rate = (semantic_hits / semantic_opportunities) * 100 if semantic_opportunities > 0 else 0
    # 2. Latency
    avg_latency = np.mean([r.get('latency_ms', 0) for r in results if 'latency_ms' in r])
    # 3. Embedding Time
    avg_embedding_time = np.mean([r.get('embedding_time_ms', 0) for r in results if r.get('embedding_time_ms', 0) > 0])
    
    return {
        "accuracy": semantic_hit_rate,
        "latency": avg_latency,
        "embedding_time": avg_embedding_time,
    }

def analyze_and_visualize(all_results):
    """Generates a grouped bar chart for all three metrics."""
    plt.style.use('seaborn-v0_8-whitegrid')
    fig, ax = plt.subplots(figsize=(14, 8))

    model_names = list(all_results.keys())
    embedding_times = [r['embedding_time'] for r in all_results.values()]
    latencies = [r['latency'] for r in all_results.values()]
    accuracies = [r['accuracy'] for r in all_results.values()]

    bar_width = 0.25
    index = np.arange(len(model_names))

    # Bar for Embedding Time (Left Axis)
    bar1 = ax.bar(index, embedding_times, bar_width, label='Avg. Embedding Time (ms)', color='skyblue')
    # Bar for Latency (Left Axis)
    bar2 = ax.bar(index + bar_width, latencies, bar_width, label='Avg. Overall Latency (ms)', color='royalblue')
    
    # Accuracy on a secondary Y-axis (Right Axis)
    ax2 = ax.twinx()
    bar3 = ax2.bar(index + 2*bar_width, accuracies, bar_width, label='Semantic Hit Rate (%)', color='seagreen')
    
    ax.set_ylabel('Time (ms)', fontsize=12, color='black')
    ax2.set_ylabel('Hit Rate (%)', fontsize=12, color='black')
    ax.set_title('In-System Benchmark of Open-Source Embedding Models', fontsize=16)
    ax.set_xticks(index + bar_width)
    ax.set_xticklabels(model_names, rotation=15, ha="right")
    
    # Combine legends from both axes
    lines, labels = ax.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax2.legend(lines + lines2, labels + labels2, loc='upper left')

    ax.set_ylim(0, max(latencies) * 1.2)
    ax2.set_ylim(0, 110)

    plt.tight_layout()
    plt.savefig('chart_full_model_benchmark.png', dpi=300)
    print("\nGenerated full model benchmark chart: chart_full_model_benchmark.png")

if __name__ == '__main__':
    # ... (This part of the script with the interactive workflow is correct and remains the same) ...
    print("--- Welcome to the Full Embedding Model Benchmark Test ---")
    workload, num_topics = generate_semantic_workload(TOTAL_PROMPTS)
    all_results = {}

    try:
        for model_name, model_hf_path in MODELS_TO_TEST.items():
            print(f"\n{'='*60}\nNext model to test: {model_name}\n{'='*60}")
            print("\n--- ACTION REQUIRED ---")
            print(f"1. Open your '.env' file and set: EMBEDDING_MODEL={model_hf_path}")
            if "nomic" in model_hf_path:
                print("\n   SPECIAL INSTRUCTION: In 'api/services/llm_provider.py', temporarily change the model loading line to:")
                print("   EMBEDDING_MODEL = SentenceTransformer(EMBEDDING_MODEL_NAME, trust_remote_code=True)")
            else:
                print("\n   Ensure 'trust_remote_code' is NOT set for other models.")
            print("\n2. In a SEPARATE terminal, start the Uvicorn server and wait for it to load.")
            input("\nPress Enter here once the server is ready...")
            
            result = run_test_for_current_model(model_name, workload, num_topics)
            all_results[model_name] = result
            
            print("\n--- ACTION REQUIRED ---")
            print("Please STOP the Uvicorn server now (Ctrl+C in its terminal).")

    except KeyboardInterrupt:
        print("\n\nTest interrupted.")
    finally:
        if all_results:
            print("\n--- FINAL ANALYSIS ---")
            analyze_and_visualize(all_results)
            print("Benchmark complete.")
        else:
            print("No results to analyze.")