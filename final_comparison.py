import requests
import time
import random
import numpy as np
import matplotlib.pyplot as plt
import subprocess
import chromadb # Import chromadb to use its client

# --- Configuration ---
SIMPLE_CACHE_URL = "http://127.0.0.1:8000/process-prompt-simple-cache/"
TIERED_CACHE_URL = "http://127.0.0.1:8000/process-prompt/"

TOTAL_PROMPTS = 500 # Increased for a more robust test
# -----------------------------

API_DELAY_SECONDS = 1.1 # To stay under the 60 RPM limit

# --- Workload Definition ---
PROMPT_CLUSTERS = [
    ["What is machine learning?", "what is ml?", "explain machine learning", "define ml"],
    ["What is the capital of France?", "france's capital?", "tell me the capital of france"],
    ["How does a neural network work?", "explain neural networks", "describe a neural network"],
    ["What is photosynthesis?", "explain photosynthesis simply", "what is the process of photosynthesis"],
    ["Who wrote 'Hamlet'?", "shakespeare's hamlet author", "author of hamlet"],
]
NOVEL_PROMPTS = ["What is the theory of relativity?", "Who discovered penicillin?", "What is a black hole?"]

def generate_workload(total_prompts):
    """Generates a workload with a high chance of semantic hits."""
    workload = []
    # 70% of prompts from clusters to test semantic capability
    for _ in range(total_prompts):
        if random.random() < 0.3:
            workload.append(random.choice(NOVEL_PROMPTS) + f" {random.randint(1,1000)}?")
        else:
            workload.append(random.choice(random.choice(PROMPT_CLUSTERS)))
    random.shuffle(workload)
    return workload

def run_simulation(system_name, api_url, workload):
    """Runs a full simulation for one system and returns metrics."""
    print(f"\n--- Simulating System: {system_name} ---")
    results = []
    
    # Reset environment before each run for a fair start
    print("  - Resetting caches for a clean run...")
    subprocess.run(["docker", "exec", "redis-cache", "redis-cli", "FLUSHALL"], check=True, capture_output=True)
    try:
        chroma_client = chromadb.HttpClient(host='localhost', port=8001)
        chroma_client.delete_collection(name="llm_cache")
        chroma_client.create_collection(name="llm_cache")
    except Exception: pass

    for i, prompt in enumerate(workload):
        try:
            # Send request
            response = requests.post(api_url, json={"prompt": prompt})
            
            # Collect result
            if response.status_code == 200:
                results.append({"from_cache": response.json().get("from_cache", False)})
                status = "HIT" if response.json().get("from_cache") else "MISS"
                print(f"  Prompt {i+1}/{len(workload)}: {status}")
            else: 
                results.append({"from_cache": False})
                print(f"  Prompt {i+1}/{len(workload)}: FAILED (Status: {response.status_code})")
        
        except requests.exceptions.RequestException as e:
            results.append({"from_cache": False})
            print(f"  Prompt {i+1}/{len(workload)}: FAILED (Connection Error)")
        
        # Respect API Rate Limit
        time.sleep(API_DELAY_SECONDS)
    
    cache_hits = sum(1 for r in results if r["from_cache"])
    return cache_hits

def analyze_and_visualize(results):
    """Generates a chart comparing the hit rates of the different mechanisms."""
    plt.style.use('seaborn-v0_8-whitegrid')
    fig, ax = plt.subplots(figsize=(10, 7))

    # We add the "No Cache" baseline here for context, even though we didn't run it
    systems = ['No Cache (Baseline)', 'Simple Cache (Exact-Match Only)', 'Our Tiered Semantic Cache']
    hit_rates = [0.0, (results['Simple Cache'] / TOTAL_PROMPTS) * 100, (results['Tiered Cache'] / TOTAL_PROMPTS) * 100]
    
    colors = ['#d9534f', '#f0ad4e', '#5cb85c'] # Red, Orange, Green
    bars = ax.bar(systems, hit_rates, color=colors)
    
    ax.set_ylabel('Cache Hit Rate (%)', fontsize=12)
    ax.set_title(f'Comparison of Caching Mechanisms ({TOTAL_PROMPTS} Prompts)', fontsize=16)
    ax.set_ylim(0, 100)
    
    for bar in bars:
        yval = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2.0, yval + 2, f'{yval:.1f}%', ha='center', color='black', fontsize=12, fontweight='bold')

    plt.tight_layout()
    plt.savefig('chart_final_comparison.png', dpi=300)
    print("\nGenerated final comparison chart: chart_final_comparison.png")


if __name__ == '__main__':
    try:
        import numpy as np
        import matplotlib.pyplot as plt
    except ImportError:
        print("Please run: pip install numpy matplotlib")
        exit()

    print("This script will run a focused A/B test to compare caching mechanisms.")
    input("Press Enter to begin the simulation...")
    
    workload = generate_workload(TOTAL_PROMPTS)
    
    # Run simulation for each system
    results = {}
    results['Simple Cache'] = run_simulation('Simple Cache (Exact-Match Only)', SIMPLE_CACHE_URL, workload)
    results['Tiered Cache'] = run_simulation('Our Tiered Semantic Cache', TIERED_CACHE_URL, workload)
    
    analyze_and_visualize(results)
    print("\nFinal comparison complete.")