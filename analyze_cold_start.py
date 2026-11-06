import requests
import time
import random
import numpy as np
import matplotlib.pyplot as plt

# --- Configuration ---
API_URL = "http://127.0.0.1:8000/process-prompt/"
TOTAL_PROMPTS = 1000
ROLLING_WINDOW_SIZE = 50 # The number of prompts to average over for smoothing the curve

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
    "What is the significance of the Rosetta Stone?", "Describe the water cycle.",
    "What is the structure of a DNA molecule?", "Explain the difference between weather and climate.",
]

def generate_workload(total_prompts):
    """Generates a realistic workload with a mix of novel, identical, and similar prompts."""
    workload = []
    for _ in range(total_prompts):
        if random.random() < 0.3:
            workload.append(random.choice(NOVEL_PROMPTS) + f" {random.randint(1, 1000)}?")
        else:
            workload.append(random.choice(random.choice(PROMPT_CLUSTERS)))
    random.shuffle(workload)
    return workload

def run_simulation(workload):
    """Runs the simulation and records the latency for each sequential prompt."""
    latencies = []
    print(f"--- Starting Cold Start Analysis with {len(workload)} prompts ---")

    for i, prompt in enumerate(workload):
        try:
            start_time = time.time()
            response = requests.post(API_URL, json={"prompt": prompt})
            latency = (time.time() - start_time) * 1000 # in ms
            
            if response.status_code == 200:
                latencies.append(latency)
                status = "HIT" if response.json().get("from_cache") else "MISS"
                if (i + 1) == 1 or (i + 1) % 50 == 0: # Print first prompt and then every 50
                    print(f"Prompt {i+1}/{len(workload)}: {status} ({latency:.0f} ms)")
            else:
                latencies.append(5000) # Penalize errors with a high latency value
                if (i + 1) == 1 or (i + 1) % 50 == 0:
                    print(f"Prompt {i+1}/{len(workload)}: FAILED (Status Code: {response.status_code})")
        except requests.exceptions.RequestException as e:
            print(f"\nFATAL: Could not connect to the API at {API_URL}.")
            print(f"Please ensure the Uvicorn server is running. Error: {e}")
            return None
            
    print("--- Simulation Finished ---")
    return latencies

def analyze_and_visualize(latencies):
    """Calculates the rolling average and generates the performance-over-time chart."""
    if not latencies or len(latencies) < ROLLING_WINDOW_SIZE:
        print("Not enough data to generate a rolling average chart.")
        return
        
    # Calculate the rolling average to smooth the line
    rolling_avg = np.convolve(latencies, np.ones(ROLLING_WINDOW_SIZE)/ROLLING_WINDOW_SIZE, mode='valid')
    
    # --- Generate Chart (Light Theme) ---
    plt.style.use('seaborn-v0_8-whitegrid')
    fig, ax = plt.subplots(figsize=(12, 7))
    
    ax.plot(rolling_avg, color='#007bff', linewidth=2.5)
    
    ax.set_xlabel('Number of Prompts Processed', fontsize=12)
    ax.set_ylabel('Rolling Average Latency (ms)', fontsize=12)
    ax.set_title(f'System Performance Over Time: The "Warming" Effect\n(Rolling Window: {ROLLING_WINDOW_SIZE} Prompts)', fontsize=16)
    ax.grid(True, linestyle='--', alpha=0.6)
    
    # Add annotations for clarity
    ax.text(len(rolling_avg) * 0.1, rolling_avg[int(len(rolling_avg) * 0.1)] * 1.1, 
            '"Cold Start" Phase\n(High Latency, Many Misses)', ha='center', color='black', alpha=0.8, fontsize=11)
    ax.text(len(rolling_avg) * 0.8, rolling_avg[int(len(rolling_avg) * 0.8)] * 0.8, 
            '"Warm" Phase\n(Low Latency, Many Hits)', ha='center', color='black', alpha=0.8, fontsize=11)

    plt.tight_layout()
    plt.savefig('chart_cold_start_analysis_1.png', dpi=300)
    print("\nGenerated chart: chart_cold_start_analysis.png")


if __name__ == '__main__':
    try:
        import numpy as np
        import matplotlib.pyplot as plt
    except ImportError:
        print("Required packages numpy and matplotlib are not installed.")
        print("Please run: pip install numpy matplotlib")
        exit()

    print("This script will analyze the 'cold start' performance of the caching system.")
    print("\nIMPORTANT: Please ensure you have manually reset the environment by:")
    print("1. Stopping and removing the Docker containers for Redis and ChromaDB.")
    print("2. Recreating the Docker containers.")
    print("3. Restarting the Uvicorn API server.")
    
    input("\nPress Enter to confirm the environment is reset and to begin the simulation...")

    # The Docker reset commands have been removed from here.

    workload = generate_workload(TOTAL_PROMPTS)
    latencies = run_simulation(workload)
    if latencies:
        analyze_and_visualize(latencies)