import requests
import time
import random
import numpy as np
import matplotlib.pyplot as plt

# --- Configuration ---
API_URL = "http://127.0.0.1:8000/process-prompt/"

# --- Workload Definition ---
# A set of related questions to test semantic and exact-match caching
PROMPT_CLUSTERS = [
    [
        "What is machine learning?",
        "what is ml?",
        "explain machine learning to me",
        "define ml",
    ],
    [
        "What is the capital of France?",
        "france's capital?",
        "tell me the capital of france",
        "capital of the country of france",
    ],
    [
        "How does a neural network work?",
        "explain neural networks",
        "what are the principles of a neural network",
        "describe the function of a neural network",
    ],
]

# Unique prompts that should always be a miss on the first try
NOVEL_PROMPTS = [
    "What is the airspeed velocity of an unladen swallow?",
    "Explain the theory of relativity in simple terms.",
    "Who wrote the novel 'Dune'?",
    "What are the main components of a CPU?",
    "Describe the process of photosynthesis.",
    "What is the chemical formula for water?",
    "Who was the first person to walk on the moon?",
    "What is blockchain technology?",
    "Explain the concept of quantum computing.",
    "Summarize the plot of the movie 'The Matrix'.",
]

def generate_workload(total_prompts=100):
    """
    Generates a realistic workload with a mix of novel, identical, and similar prompts.
    """
    workload = []
    
    # 40% Novel Prompts
    for i in range(int(total_prompts * 0.4)):
        workload.append(random.choice(NOVEL_PROMPTS) + f" {random.randint(1, 1000)}?") # Add random number to ensure novelty

    # 60% Repetitive/Similar Prompts
    for _ in range(int(total_prompts * 0.6)):
        cluster = random.choice(PROMPT_CLUSTERS)
        workload.append(random.choice(cluster))
        
    random.shuffle(workload)
    return workload

def run_test(workload):
    """
    Sends the workload to the API and collects performance data.
    """
    results = []
    print(f"--- Starting Load Test with {len(workload)} prompts ---")

    for i, prompt in enumerate(workload):
        try:
            start_time = time.time()
            response = requests.post(API_URL, json={"prompt": prompt})
            end_time = time.time()

            latency = (end_time - start_time) * 1000  # Convert to milliseconds
            
            if response.status_code == 200:
                data = response.json()
                results.append({
                    "prompt": prompt,
                    "latency_ms": latency,
                    "from_cache": data.get("from_cache", False),
                    "cache_tier": data.get("cache_tier"),
                })
                status = "HIT" if data.get("from_cache") else "MISS"
                tier = f"(Tier {data.get('cache_tier')})" if data.get('cache_tier') else ""
                print(f"Prompt {i+1}/{len(workload)}: {status} {tier} ({latency:.2f} ms)")
            else:
                print(f"Prompt {i+1}/{len(workload)}: FAILED (Status Code: {response.status_code})")

        except requests.exceptions.RequestException as e:
            print(f"\nFATAL: Could not connect to the API at {API_URL}.")
            print("Please ensure the backend server is running.")
            return None
            
    print("--- Load Test Finished ---")
    return results

def analyze_results(results):
    """
    Calculates and prints the final performance metrics and generates charts.
    """
    if not results:
        print("No results to analyze.")
        return

    total_requests = len(results)
    cache_hits = sum(1 for r in results if r["from_cache"])
    t1_hits = sum(1 for r in results if r["cache_tier"] == 1)
    t2_hits = sum(1 for r in results if r["cache_tier"] == 2)
    cache_misses = total_requests - cache_hits

    latencies = {
        "llm_call": [r["latency_ms"] for r in results if not r["from_cache"]],
        "t1_hit": [r["latency_ms"] for r in results if r["cache_tier"] == 1],
        "t2_hit": [r["latency_ms"] for r in results if r["cache_tier"] == 2],
    }

    avg_latencies = {
        "llm_call": np.mean(latencies["llm_call"]) if latencies["llm_call"] else 0,
        "t1_hit": np.mean(latencies["t1_hit"]) if latencies["t1_hit"] else 0,
        "t2_hit": np.mean(latencies["t2_hit"]) if latencies["t2_hit"] else 0,
    }

    print("\n--- Performance Metrics ---")
    print(f"Total Prompts: {total_requests}")
    print(f"Total Cache Hit Rate: {(cache_hits / total_requests) * 100:.2f}%")
    print("-" * 25)
    print(f"Cache Hits: {cache_hits}")
    print(f"  - Tier 1 (Exact-Match): {t1_hits} ({(t1_hits / total_requests) * 100:.2f}%)")
    print(f"  - Tier 2 (Semantic): {t2_hits} ({(t2_hits / total_requests) * 100:.2f}%)")
    print(f"Cache Misses (LLM Calls): {cache_misses}")
    print("-" * 25)
    print("Average Latencies:")
    print(f"  - LLM Call (Miss): {avg_latencies['llm_call']:.2f} ms")
    print(f"  - Tier 2 (Semantic Hit): {avg_latencies['t2_hit']:.2f} ms")
    print(f"  - Tier 1 (Exact-Match Hit): {avg_latencies['t1_hit']:.2f} ms")
    print("-" * 25)
    print(f"LLM Calls Avoided: {cache_hits} out of {total_requests}")

    # --- Generate Charts ---
    generate_charts(avg_latencies, {"T1 Hits": t1_hits, "T2 Hits": t2_hits, "Misses": cache_misses})

def generate_charts(avg_latencies, hit_miss_counts):
    """Uses Matplotlib to create and save the charts for the presentation."""
    
    # Chart 1: Average Response Time
    plt.style.use('dark_background')
    fig, ax = plt.subplots(figsize=(10, 6))
    
    labels = ["T1 Exact-Match Hit\n(Redis)", "T2 Semantic Hit\n(ChromaDB)", "LLM Call (Miss)\n(Gemini)"]
    latencies = [avg_latencies['t1_hit'], avg_latencies['t2_hit'], avg_latencies['llm_call']]
    
    bars = ax.bar(labels, latencies, color=['#28a745', '#17a2b8', '#dc3545'])
    ax.set_yscale('log') # Use logarithmic scale for visibility
    ax.set_ylabel('Latency (ms) - Logarithmic Scale')
    ax.set_title('Average Response Time by Cache Tier', fontsize=16)
    
    for bar in bars:
        yval = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2.0, yval * 1.1, f'{yval:.0f} ms', ha='center', va='bottom', fontsize=12)

    plt.tight_layout()
    plt.savefig('chart_latency_comparison.png')
    print("\nGenerated chart: chart_latency_comparison.png")

    # Chart 2: Cache Performance Breakdown
    fig2, ax2 = plt.subplots(figsize=(8, 8))
    pie_labels = ['Cache Misses', 'Tier-1 Hits', 'Tier-2 Hits']
    sizes = [hit_miss_counts['Misses'], hit_miss_counts['T1 Hits'], hit_miss_counts['T2 Hits']]
    colors = ['#dc3545', '#28a745', '#17a2b8']
    
    ax2.pie(sizes, labels=pie_labels, autopct='%1.1f%%', startangle=90, colors=colors,
            wedgeprops={'edgecolor': 'white'}, textprops={'fontsize': 12, 'color': 'white'})
    ax2.axis('equal')  # Equal aspect ratio ensures that pie is drawn as a circle.
    ax2.set_title('Cache Performance Breakdown', fontsize=16)
    
    plt.tight_layout()
    plt.savefig('chart_performance_breakdown.png')
    print("Generated chart: chart_performance_breakdown.png")

if __name__ == "__main__":
    # First, make sure the requirements for this script are installed
    try:
        import numpy as np
        import matplotlib.pyplot as plt
    except ImportError:
        print("Required packages numpy and matplotlib are not installed.")
        print("Please run: pip install numpy matplotlib")
        exit()

    workload = generate_workload(total_prompts=100)
    results = run_test(workload)
    if results:
        analyze_results(results)