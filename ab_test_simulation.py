import requests
import time
import random
import numpy as np
import matplotlib.pyplot as plt
from concurrent.futures import ThreadPoolExecutor, as_completed

# --- Configuration ---
CACHING_API_URL = "http://127.0.0.1:8000/process-prompt/"
NO_CACHE_API_URL = "http://127.0.0.1:8000/process-prompt-no-cache/"

NUM_USERS = 10
PROMPTS_PER_USER = 100
TOTAL_PROMPTS = NUM_USERS * PROMPTS_PER_USER

# --- Workload Definition (same as load_tester.py) ---
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
    "What is the significance of the Rosetta Stone?", "Describe the water cycle.",
    "What is the structure of a DNA molecule?", "Explain the difference between weather and climate.",
]

def generate_user_workload(prompts_per_user):
    """Generates a workload for a single user with some repetition."""
    user_workload = []
    # 30% Novel, 70% Repetitive/Similar
    for i in range(prompts_per_user):
        if random.random() < 0.3:
            user_workload.append(random.choice(NOVEL_PROMPTS) + f" {random.randint(1, 1000)}?")
        else:
            user_workload.append(random.choice(random.choice(PROMPT_CLUSTERS)))
    return user_workload

def run_simulation_for_user(user_id, api_url, workload):
    """Simulates a single user sending all their prompts."""
    print(f"User {user_id} starting simulation for {api_url.split('/')[-2]}...")
    results = []
    for prompt in workload:
        try:
            start_time = time.time()
            response = requests.post(api_url, json={"prompt": prompt})
            latency = (time.time() - start_time) * 1000 # ms
            
            if response.status_code == 200:
                data = response.json()
                results.append({
                    "latency_ms": latency,
                    "from_cache": data.get("from_cache", False),
                })
            else:
                results.append({"latency_ms": 5000, "from_cache": False}) # Penalize errors
        except requests.exceptions.RequestException:
            results.append({"latency_ms": 5000, "from_cache": False}) # Penalize connection errors
    return results

def run_ab_test():
    # Generate a consistent workload for all users
    user_workloads = [generate_user_workload(PROMPTS_PER_USER) for _ in range(NUM_USERS)]
    
    all_results_with_cache = []
    all_results_no_cache = []

    # --- Run Simulation for "With Cache" System ---
    print(f"\n--- SIMULATING {NUM_USERS} USERS WITH CACHING SYSTEM ---")
    with ThreadPoolExecutor(max_workers=NUM_USERS) as executor:
        futures = [executor.submit(run_simulation_for_user, i+1, CACHING_API_URL, user_workloads[i]) for i in range(NUM_USERS)]
        for future in as_completed(futures):
            all_results_with_cache.extend(future.result())

    # --- Run Simulation for "No Cache" System ---
    print(f"\n--- SIMULATING {NUM_USERS} USERS WITH NO-CACHE BASELINE ---")
    with ThreadPoolExecutor(max_workers=NUM_USERS) as executor:
        futures = [executor.submit(run_simulation_for_user, i+1, NO_CACHE_API_URL, user_workloads[i]) for i in range(NUM_USERS)]
        for future in as_completed(futures):
            all_results_no_cache.extend(future.result())
            
    return all_results_with_cache, all_results_no_cache

def analyze_and_visualize(results_with_cache, results_no_cache):
    """Analyzes the A/B test results and generates comparison charts."""
    
    # --- Analysis for Caching System ---
    total_time_with_cache_ms = sum(r['latency_ms'] for r in results_with_cache)
    llm_calls_with_cache = sum(1 for r in results_with_cache if not r['from_cache'])
    
    # --- Analysis for No-Cache System ---
    total_time_no_cache_ms = sum(r['latency_ms'] for r in results_no_cache)
    llm_calls_no_cache = TOTAL_PROMPTS
    
    print("\n" + "="*50)
    print("           A/B TEST SIMULATION RESULTS")
    print("="*50)
    print(f"Total Prompts Sent (per system): {TOTAL_PROMPTS}")
    print("\n--- Caching System Performance ---")
    print(f"Total Time Taken: {total_time_with_cache_ms / 1000:.2f} seconds")
    print(f"Average Latency per Prompt: {np.mean([r['latency_ms'] for r in results_with_cache]):.2f} ms")
    print(f"Expensive LLM Calls Made: {llm_calls_with_cache}")
    
    print("\n--- No-Cache Baseline Performance ---")
    print(f"Total Time Taken: {total_time_no_cache_ms / 1000:.2f} seconds")
    print(f"Average Latency per Prompt: {np.mean([r['latency_ms'] for r in results_no_cache]):.2f} ms")
    print(f"Expensive LLM Calls Made: {llm_calls_no_cache}")
    
    print("\n" + "="*50)
    print("           COMPARATIVE ANALYSIS")
    print("="*50)
    print(f"LLM Calls Prevented: {llm_calls_no_cache - llm_calls_with_cache} ({((llm_calls_no_cache - llm_calls_with_cache)/llm_calls_no_cache)*100:.1f}%)")
    print(f"Total Time Saved: {(total_time_no_cache_ms - total_time_with_cache_ms) / 1000:.2f} seconds")
    print(f"System Speed Improvement: {total_time_no_cache_ms / total_time_with_cache_ms:.1f}x faster overall")
    
    # --- Generate Chart ---
    plt.style.use('dark_background')
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(18, 7))

    # Chart 1: Total Time Comparison
    ax1.bar(['No-Cache Baseline', 'Our Caching System'], 
            [total_time_no_cache_ms / 1000, total_time_with_cache_ms / 1000], 
            color=['#dc3545', '#28a745'])
    ax1.set_ylabel('Total Time to Process 1000 Prompts (seconds)')
    ax1.set_title('Overall System Throughput Comparison', fontsize=14)

    # Chart 2: LLM Calls Comparison
    ax2.bar(['No-Cache Baseline', 'Our Caching System'], 
            [llm_calls_no_cache, llm_calls_with_cache], 
            color=['#ffc107', '#17a2b8'])
    ax2.set_ylabel('Number of Expensive LLM API Calls')
    ax2.set_title('Computational Cost Comparison', fontsize=14)

    fig.suptitle('A/B Test Simulation: Caching System vs. No-Cache Baseline', fontsize=18)
    plt.tight_layout(rect=[0, 0.03, 1, 0.95])
    plt.savefig('chart_ab_test_comparison1.png')
    print("\nGenerated comparative analysis chart: chart_ab_test_comparison.png")


if __name__ == '__main__':
    # Make sure requirements are installed
    try:
        import numpy as np
        import matplotlib.pyplot as plt
    except ImportError:
        print("Please run: pip install numpy matplotlib")
        exit()

    results_with_cache, results_no_cache = run_ab_test()
    if results_with_cache and results_no_cache:
        analyze_and_visualize(results_with_cache, results_no_cache)