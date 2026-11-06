import requests
import time
import random
import numpy as np
import matplotlib.pyplot as plt
import subprocess

# --- Configuration ---
NO_CACHE_URL = "http://127.0.0.1:8000/process-prompt-no-cache/"
SIMPLE_CACHE_URL = "http://127.0.0.1:8000/process-prompt-simple-cache/"
TIERED_CACHE_URL = "http://127.0.0.1:8000/process-prompt/"

TOTAL_PROMPTS = 1000

# --- Workload Definition (same as other testers) ---
PROMPT_CLUSTERS = [
    ["What is machine learning?", "what is ml?", "explain machine learning", "define ml"],
    ["What is the capital of France?", "france's capital?", "tell me the capital of france"],
    ["How does a neural network work?", "explain neural networks", "describe a neural network"],
]
NOVEL_PROMPTS = ["What is the theory of relativity?", "Who discovered penicillin?", "What is a black hole?"]

def generate_workload(total_prompts):
    workload = []
    # 70% of prompts will be from clusters, ensuring high potential for semantic hits
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
    subprocess.run(["docker", "exec", "redis-cache", "redis-cli", "FLUSHALL"], check=True, capture_output=True)
    try:
        chroma_client = chromadb.HttpClient(host='localhost', port=8001)
        chroma_client.delete_collection(name="llm_cache")
        chroma_client.create_collection(name="llm_cache")
    except Exception: pass # Ignore if it fails (e.g., first run)

    for i, prompt in enumerate(workload):
        try:
            start_time = time.time()
            response = requests.post(api_url, json={"prompt": prompt})
            latency = (time.time() - start_time) * 1000
            if response.status_code == 200:
                results.append({"from_cache": response.json().get("from_cache", False)})
            else: results.append({"from_cache": False})
        except requests.exceptions.RequestException:
            results.append({"from_cache": False})
    
    cache_hits = sum(1 for r in results if r["from_cache"])
    return cache_hits

def analyze_and_visualize(results):
    """Generates a chart comparing the hit rates of the different mechanisms."""
    plt.style.use('seaborn-v0_8-whitegrid')
    fig, ax = plt.subplots(figsize=(10, 7))

    systems = list(results.keys())
    hit_rates = [(results[s] / TOTAL_PROMPTS) * 100 for s in systems]
    
    bars = ax.bar(systems, hit_rates, color=['#d9534f', '#f0ad4e', '#5cb85c'])
    ax.set_ylabel('Cache Hit Rate (%)', fontsize=12)
    ax.set_title('Comparison of Different Caching Mechanisms (1000 Prompts)', fontsize=16)
    ax.set_ylim(0, 100)
    
    for bar in bars:
        yval = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2.0, yval + 2, f'{yval:.1f}%', ha='center', color='black', fontsize=12, fontweight='bold')

    plt.tight_layout()
    plt.savefig('chart_mechanism_comparison.png', dpi=300)
    print("\nGenerated chart: chart_mechanism_comparison.png")


if __name__ == '__main__':
    try: import chromadb
    except ImportError: print("Please run: pip install chromadb")

    print("This script will run an A/B/C test to compare different caching mechanisms.")
    input("Press Enter to begin the simulation...")
    
    workload = generate_workload(TOTAL_PROMPTS)
    
    # Run simulation for each system
    results = {}
    results['No Cache (Baseline)'] = run_simulation('No Cache', NO_CACHE_URL, workload)
    results['Simple Cache (Exact-Match Only)'] = run_simulation('Simple Cache', SIMPLE_CACHE_URL, workload)
    results['Our Tiered Semantic Cache'] = run_simulation('Tiered Cache', TIERED_CACHE_URL, workload)
    
    analyze_and_visualize(results)