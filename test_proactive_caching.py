import requests
import time
import random
import matplotlib.pyplot as plt
import subprocess
import os

# --- Configuration ---
API_URL = "http://127.0.0.1:8000/process-prompt/"
LOG_FILE = "cache_misses.log"
PROACTIVE_CACHER_SCRIPT = "proactive_cacher.py"

# --- Experiment Definition ---
# This is our "emerging topic".
# We have a set of questions that will be asked BEFORE warming.
EMERGING_TOPIC_QUERIES = [
    "what is the largest planet in our solar system?",
    "which planet is known for its rings?",
    "tell me about Mars",
    "how many planets are in the solar system?",
    "describe the great red spot on jupiter",
]

# This is a set of NEW, never-before-seen paraphrases of the same topic.
# These will be asked AFTER warming to test the cacher's effectiveness.
VERIFICATION_QUERIES = [
    "what's the biggest planet in the solar system?",
    "which planet has the most famous rings?",
    "give me a summary about the red planet",
    "how many planets revolve around our sun?",
    "what is jupiter's giant storm called?",
    "tell me about our solar system's planets", # General paraphrase
]

def run_phase(phase_name, prompts):
    """Generic function to run a set of prompts and collect results."""
    print(f"\n--- Running Phase: {phase_name} ---")
    results = {"hits": 0, "misses": 0, "latencies": []}
    
    for prompt in prompts:
        try:
            start_time = time.time()
            response = requests.post(API_URL, json={"prompt": prompt})
            latency = (time.time() - start_time) * 1000 # in ms
            
            if response.status_code == 200:
                data = response.json()
                results["latencies"].append(latency)
                if data.get("from_cache"):
                    results["hits"] += 1
                    print(f"  - SUCCESS (CACHE HIT): '{prompt[:50]}...' ({latency:.0f} ms)")
                else:
                    results["misses"] += 1
                    print(f"  - SUCCESS (CACHE MISS): '{prompt[:50]}...' ({latency:.0f} ms)")
            else:
                print(f"  - FAILED: '{prompt[:50]}...' (Status: {response.status_code})")
        except requests.exceptions.RequestException:
            print(f"FATAL: Could not connect to the API at {API_URL}. Is the server running?")
            return None
    
    return results

def run_proactive_cacher():
    """Executes the proactive_cacher.py script as a subprocess."""
    print("\n--- Running Proactive Cacher Script ---")
    try:
        # We run the script using the same Python interpreter as our venv
        python_executable = os.path.join(".venv", "Scripts", "python.exe") if os.name == 'nt' else os.path.join("venv", "bin", "python")
        result = subprocess.run([python_executable, PROACTIVE_CACHER_SCRIPT], capture_output=True, text=True, check=True)
        print("Proactive cacher script ran successfully.")
        # print(result.stdout) # Uncomment to see the full output of the script
    except FileNotFoundError:
        print("ERROR: Could not find the python executable for the virtual environment.")
        print("Please ensure the script is run from the project root.")
    except subprocess.CalledProcessError as e:
        print("ERROR: The proactive cacher script failed to run.")
        print(e.stderr)

def reset_environment():
    """Resets the log file and Redis cache for a clean test."""
    print("--- Resetting Environment ---")
    # Reset log file
    if os.path.exists(LOG_FILE):
        os.remove(LOG_FILE)
        print(f"  - Deleted {LOG_FILE}.")
    
    # Reset Redis
    try:
        subprocess.run(["docker", "exec", "redis-cache", "redis-cli", "FLUSHALL"], capture_output=True, text=True, check=True)
        print("  - Flushed Redis cache.")
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        print("Warning: Could not flush Redis. Is Docker running and is the container named 'redis-cache'?")
        print(e)

def generate_chart(before_results, after_results):
    """Generates a bar chart comparing the performance before and after warming."""
    plt.style.use('dark_background')
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 7))

    # --- Chart 1: Cache Hit Rate ---
    before_hit_rate = (before_results['hits'] / len(EMERGING_TOPIC_QUERIES)) * 100
    after_hit_rate = (after_results['hits'] / len(VERIFICATION_QUERIES)) * 100
    
    ax1.bar(['Before Warming', 'After Warming'], [before_hit_rate, after_hit_rate], color=['#dc3545', '#28a745'])
    ax1.set_ylabel('Cache Hit Rate (%)')
    ax1.set_title('Proactive Caching: Cache Hit Rate Uplift', fontsize=14)
    ax1.set_ylim(0, 110)
    for i, v in enumerate([before_hit_rate, after_hit_rate]):
        ax1.text(i, v + 2, f"{v:.0f}%", ha='center', color='white', fontsize=12)

    # --- Chart 2: Average Latency ---
    avg_latency_before = sum(before_results['latencies']) / len(before_results['latencies'])
    avg_latency_after = sum(after_results['latencies']) / len(after_results['latencies'])
    
    bars = ax2.bar(['Before Warming', 'After Warming'], [avg_latency_before, avg_latency_after], color=['#dc3545', '#28a745'])
    ax2.set_ylabel('Average Response Time (ms)')
    ax2.set_title('Proactive Caching: Latency Reduction', fontsize=14)
    
    for bar in bars:
        yval = bar.get_height()
        ax2.text(bar.get_x() + bar.get_width()/2.0, yval * 1.05, f'{yval:.0f} ms', ha='center', va='bottom', fontsize=12)

    fig.suptitle('Evaluation of Proactive Caching Feature', fontsize=18)
    plt.tight_layout(rect=[0, 0.03, 1, 0.95])
    plt.savefig('chart_proactive_caching_evaluation.png')
    print("\nGenerated chart: chart_proactive_caching_evaluation.png")


if __name__ == "__main__":
    # 1. Reset the environment for a clean test
    reset_environment()

    # 2. Run the "Before" phase to generate misses
    before_results = run_phase("Phase 1: Before Warming", EMERGING_TOPIC_QUERIES)
    
    if before_results:
        # 3. Run the proactive cacher script to analyze logs and warm the cache
        run_proactive_cacher()

        # 4. Run the "After" phase to verify the cache is now warm
        after_results = run_phase("Phase 2: After Warming (Verification)", VERIFICATION_QUERIES)

        if after_results:
            # 5. Generate the final comparison chart
            generate_chart(before_results, after_results)