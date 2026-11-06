import requests
import time
import random
import numpy as np
import matplotlib.pyplot as plt
import subprocess

# --- Configuration ---
CACHING_API_URL = "http://127.0.0.1:8000/process-prompt/"
NO_CACHE_API_URL = "http://127.0.0.1:8000/process-prompt-no-cache/"

TOTAL_PROMPTS = 1000 # A single stream of 1000 prompts

# --- Cost and Compute Model ---
COST_PER_LLM_CALL_USD = 0.0004
GPU_SECONDS_PER_LLM_CALL = 3.5

# --- Workload Definition ---
PROMPT_CLUSTERS = [
    ["What is machine learning?", "what is ml?", "explain machine learning", "define ml"],
    ["What is the capital of France?", "france's capital?", "tell me the capital of france"],
    ["How does a neural network work?", "explain neural networks", "describe a neural network"],
    ["What is photosynthesis?", "explain photosynthesis simply", "what is the process of photosynthesis"],
    ["Who wrote 'Hamlet'?", "shakespeare's hamlet author", "author of hamlet"],
]
NOVEL_PROMPTS = [
    "What is the theory of relativity?", "Who discovered penicillin?", "What is a black hole?",
    "Explain quantum entanglement.", "What is the Fibonacci sequence?", "Who painted the Mona Lisa?",
]

def generate_workload(total_prompts):
    """Generates a single, shuffled workload stream."""
    workload = []
    for _ in range(total_prompts):
        if random.random() < 0.3: # 30% novel
            workload.append(random.choice(NOVEL_PROMPTS) + f" {random.randint(1, 1000)}?")
        else: # 70% repetitive
            workload.append(random.choice(random.choice(PROMPT_CLUSTERS)))
    random.shuffle(workload)
    return workload

def run_fair_ab_test(workload):
    """
    Runs an interleaved A/B test for a fair comparison.
    """
    results_with_cache = []
    results_no_cache = []
    
    # Before the test, we ensure the ChromaDB collection is empty for a fair start.
    try:
        print("Resetting ChromaDB collection before test run...")
        chroma_client = chromadb.HttpClient(host='localhost', port=8001)
        chroma_client.delete_collection(name="llm_cache")
        chroma_client.create_collection(name="llm_cache")
        print("ChromaDB collection reset successfully.")
    except Exception as e:
        print(f"Warning: Could not reset ChromaDB collection. It might be starting fresh. Details: {e}")

    print(f"\n--- STARTING FAIR A/B TEST ({len(workload)} prompts) ---")
    
    for i, prompt in enumerate(workload):
        if (i + 1) % 50 == 0:
            print(f"Running prompt {i+1}/{len(workload)}...")
        
        # --- Test the NO-CACHE system ---
        try:
            start_time_no_cache = time.time()
            requests.post(NO_CACHE_API_URL, json={"prompt": prompt})
            latency_no_cache = (time.time() - start_time_no_cache) * 1000
            results_no_cache.append({"latency_ms": latency_no_cache})
        except requests.exceptions.RequestException:
            results_no_cache.append({"latency_ms": 5000}) # Penalize

        # --- Test the CACHING system ---
        try:
            start_time_cache = time.time()
            response_cache = requests.post(CACHING_API_URL, json={"prompt": prompt})
            latency_cache = (time.time() - start_time_cache) * 1000
            if response_cache.status_code == 200:
                results_with_cache.append({
                    "latency_ms": latency_cache,
                    "from_cache": response_cache.json().get("from_cache", False)
                })
            else:
                results_with_cache.append({"latency_ms": 5000, "from_cache": False})
        except requests.exceptions.RequestException:
            results_with_cache.append({"latency_ms": 5000, "from_cache": False})

    print("--- FAIR A/B TEST COMPLETE ---")
    return results_with_cache, results_no_cache

def analyze_and_visualize(results_with_cache, results_no_cache):
    """Analyzes the A/B test results and generates comparison charts."""
    
    # --- Analysis for Caching System ---
    total_time_with_cache_ms = sum(r['latency_ms'] for r in results_with_cache)
    llm_calls_with_cache = sum(1 for r in results_with_cache if not r['from_cache'])
    cost_with_cache = llm_calls_with_cache * COST_PER_LLM_CALL_USD
    
    # --- Analysis for No-Cache System ---
    total_time_no_cache_ms = sum(r['latency_ms'] for r in results_no_cache)
    llm_calls_no_cache = TOTAL_PROMPTS
    cost_no_cache = llm_calls_no_cache * COST_PER_LLM_CALL_USD
    
    print("\n" + "="*50)
    print("           A/B TEST SIMULATION RESULTS")
    print("="*50)
    print(f"Total Prompts Sent (per system): {TOTAL_PROMPTS}")
    print("\n--- Caching System Performance ---")
    print(f"Total Time Taken: {total_time_with_cache_ms / 1000:.2f} seconds")
    print(f"Average Latency per Prompt: {np.mean([r['latency_ms'] for r in results_with_cache]):.2f} ms")
    print(f"Expensive LLM Calls Made: {llm_calls_with_cache}")
    print(f"Estimated Financial Cost: ${cost_with_cache:.4f}")

    print("\n--- No-Cache Baseline Performance ---")
    print(f"Total Time Taken: {total_time_no_cache_ms / 1000:.2f} seconds")
    print(f"Average Latency per Prompt: {np.mean([r['latency_ms'] for r in results_no_cache]):.2f} ms")
    print(f"Expensive LLM Calls Made: {llm_calls_no_cache}")
    print(f"Estimated Financial Cost: ${cost_no_cache:.4f}")
    
    print("\n" + "="*50)
    print("           SAVINGS ANALYSIS")
    print("="*50)
    print(f"LLM Calls Prevented: {llm_calls_no_cache - llm_calls_with_cache} ({((llm_calls_no_cache - llm_calls_with_cache)/llm_calls_no_cache)*100:.1f}%)")
    print(f"Estimated Cost Saved: ${cost_no_cache - cost_with_cache:.4f}")
    
    # --- Generate Chart (Light Theme) ---
    plt.style.use('seaborn-v0_8-whitegrid')
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(18, 7))

    # Chart 1: Total Time Comparison
    colors_throughput = ['#d9534f', '#5cb85c'] # Red for baseline, Green for our system
    ax1.bar(['No-Cache Baseline', 'Our Caching System'], 
            [total_time_no_cache_ms / 1000, total_time_with_cache_ms / 1000], 
            color=colors_throughput)
    ax1.set_ylabel('Total Time to Process 1000 Prompts (seconds)', fontsize=12)
    ax1.set_title('Overall System Throughput Comparison', fontsize=16)
    for i, v in enumerate([total_time_no_cache_ms / 1000, total_time_with_cache_ms / 1000]):
        ax1.text(i, v, f'{v:.1f}s', ha='center', va='bottom', fontsize=12, color='black', fontweight='bold')

    # Chart 2: LLM Calls Comparison
    colors_cost = ['#f0ad4e', '#5bc0de'] # Orange for baseline, Blue for our system
    ax2.bar(['No-Cache Baseline', 'Our Caching System'], 
            [llm_calls_no_cache, llm_calls_with_cache], 
            color=colors_cost)
    ax2.set_ylabel('Number of Expensive LLM API Calls', fontsize=12)
    ax2.set_title('Computational Cost Comparison', fontsize=16)
    for i, v in enumerate([llm_calls_no_cache, llm_calls_with_cache]):
        ax2.text(i, v, f'{v:.0f}', ha='center', va='bottom', fontsize=12, color='black', fontweight='bold')

    fig.suptitle('A/B Test Simulation: Caching System vs. No-Cache Baseline', fontsize=20)
    plt.tight_layout(rect=[0, 0.03, 1, 0.95])
    plt.savefig('chart_fair_ab_test_comparison.png', dpi=300)
    print("\nGenerated fair A/B test chart: chart_fair_ab_test_comparison.png")

if __name__ == '__main__':
    try:
        import numpy as np
        import matplotlib.pyplot as plt
        import chromadb
    except ImportError:
        print("Required packages (numpy, matplotlib, chromadb) are not installed.")
        print("Please run: pip install numpy matplotlib chromadb")
        exit()
        
    print("This script will run a FAIR A/B test by interleaving requests.")
    print("\nIMPORTANT: Please ensure you have manually reset the environment by:")
    print("1. Stopping and removing the Docker containers for Redis and ChromaDB.")
    print("2. Recreating the Docker containers.")
    print("3. Restarting the Uvicorn API server.")

    input("\nPress Enter to confirm the environment is reset and to begin the test...")
    
    workload = generate_workload(TOTAL_PROMPTS)
    results_with_cache, results_no_cache = run_fair_ab_test(workload)
    if results_with_cache and results_no_cache:
        analyze_and_visualize(results_with_cache, results_no_cache)