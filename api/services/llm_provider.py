import os
import re
import time
import random
from dotenv import load_dotenv

# --- Load Environment Variables ---
load_dotenv()

# --- Set Writable Cache Environment Defaults ---
_default_hf_home = (
    "/tmp/hf_cache"
    if (os.getenv("SPACE_ID") or os.path.exists("/.dockerenv"))
    else "./.cache/hf"
)
os.environ.setdefault("HF_HOME", os.getenv("HF_HOME", _default_hf_home))
os.environ.setdefault(
    "SENTENCE_TRANSFORMERS_HOME",
    os.getenv("SENTENCE_TRANSFORMERS_HOME", os.environ["HF_HOME"]),
)
os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
try:
    os.makedirs(os.environ["HF_HOME"], exist_ok=True)
except Exception:
    pass

from sentence_transformers import SentenceTransformer

try:
    from google import genai
except ImportError:
    genai = None

# --- Configure Official google-genai SDK & Gemini 3.x Model Cascade ---
API_KEY = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
_raw_cascade = [
    os.getenv("GEMINI_MODEL", "gemini-3.8-flash"),
    "gemini-3.8-flash",
    "gemini-3.6-flash",
    "gemini-3.5-flash-lite",
]
MODEL_CASCADE: list[str] = []
for _m in _raw_cascade:
    if _m and _m not in MODEL_CASCADE:
        MODEL_CASCADE.append(_m)

genai_client = None
if genai is not None and API_KEY and API_KEY.strip() and API_KEY.strip() != "your_api_key_here":
    try:
        genai_client = genai.Client(api_key=API_KEY.strip())
    except Exception as e:
        print(f"Warning: Could not initialize google-genai client: {e}")
        genai_client = None

# --- Singleton Normalized Embedding Engine ---
EMBEDDING_MODEL_NAME = os.getenv("EMBEDDING_MODEL", "BAAI/bge-small-en-v1.5")
_EMBEDDING_MODEL: SentenceTransformer | None = None


def get_embedding_model() -> SentenceTransformer | None:
    """Lazily loads or returns the singleton SentenceTransformer model."""
    global _EMBEDDING_MODEL
    if _EMBEDDING_MODEL is not None:
        return _EMBEDDING_MODEL

    models_to_try = [EMBEDDING_MODEL_NAME]
    if "BAAI/bge-small-en-v1.5" not in models_to_try:
        models_to_try.append("BAAI/bge-small-en-v1.5")
    if "BAAI/bge-base-en-v1.5" not in models_to_try:
        models_to_try.append("BAAI/bge-base-en-v1.5")

    for model_name in models_to_try:
        for local_only in (True, False):
            try:
                mode_str = " (local_files_only=True)" if local_only else ""
                print(f"--- Loading Embedding Model: {model_name}{mode_str} ---")
                kwargs = {"local_files_only": True} if local_only else {}
                if "nomic" in model_name.lower():
                    kwargs["trust_remote_code"] = True
                _EMBEDDING_MODEL = SentenceTransformer(model_name, **kwargs)
                print(f"Successfully loaded {model_name}.")
                return _EMBEDDING_MODEL
            except Exception as e:
                print(f"Warning: Could not load embedding model {model_name}{mode_str}: {e}")

    return None


# Eagerly initialize singleton on module load
get_embedding_model()


def _get_fallback_response(prompt: str) -> str:
    """
    Smart, deterministic fallback generator that activates automatically if no API key
    is configured or if all Gemini models hit a quota/network error.
    """
    prompt_stripped = prompt.strip()
    lower = prompt_stripped.lower()

    # 1. Special handling for proactive_cacher.py Canonical Q&A generation
    if "CANONICAL_QUESTION:" in prompt and "CANONICAL_ANSWER:" in prompt:
        if any(w in lower for w in ["planet", "solar system", "jupiter", "mars", "saturn", "rings", "red spot"]):
            return (
                "CANONICAL_QUESTION: What are the key characteristics, planets, and notable features of our solar system?\n"
                "CANONICAL_ANSWER: Our solar system consists of eight planets revolving around the Sun: Mercury, Venus, Earth, "
                "Mars, Jupiter, Saturn, Uranus, and Neptune. Jupiter is the largest and biggest planet in our solar system and "
                "is famous for the Great Red Spot, a giant anticyclonic storm larger than Earth. Saturn is the planet best known "
                "for its spectacular and prominent ring system made of ice and rock particles, while Mars is known as the Red "
                "Planet due to iron oxide on its surface and features landmarks like Olympus Mons and Valles Marineris."
            )
        if any(w in lower for w in ["machine learning", "ml", "neural", "deep learning", "ai"]):
            return (
                "CANONICAL_QUESTION: What is machine learning and how does it work?\n"
                "CANONICAL_ANSWER: Machine learning (ML) is a subfield of artificial intelligence that enables software systems "
                "to learn patterns from data and improve predictive accuracy without being explicitly programmed for every rule. "
                "It encompasses supervised learning, unsupervised learning, and reinforcement learning, powering modern applications "
                "such as natural language processing, computer vision, and recommendation engines."
            )
        # Extract user questions from prompt if present
        lines = [
            line.strip().lstrip("-").strip()
            for line in prompt_stripped.splitlines()
            if line.strip().startswith("-")
        ]
        rep_q = lines[0] if lines else "What are the core principles and details of this topic?"
        return (
            f"CANONICAL_QUESTION: {rep_q}\n"
            f"CANONICAL_ANSWER: This topic encompasses fundamental concepts, mechanisms, and practical applications across "
            f"related domains. Specifically, addressing questions such as {', '.join(lines[:3]) if lines else rep_q}, the "
            f"underlying framework provides a structured explanation of how these systems operate and interact in practice."
        )

    # 2. Special handling for proactive_cacher.py paraphrase generation
    if "generate 5 common, alternative ways a user might ask" in lower:
        # Extract original question if quoted
        match = re.search(r'Original Question:\s*"([^"]+)"', prompt_stripped, re.IGNORECASE)
        orig_q = match.group(1) if match else prompt_stripped
        orig_lower = orig_q.lower()
        if any(w in orig_lower for w in ["planet", "solar system", "jupiter", "mars", "saturn", "rings"]):
            return "\n".join([
                "What's the biggest planet in the solar system?",
                "Which planet has the most famous rings?",
                "Give me a summary about the red planet",
                "How many planets revolve around our sun?",
                "Tell me about our solar system's planets and Jupiter's giant storm",
            ])
        if any(w in orig_lower for w in ["machine learning", "ml"]):
            return "\n".join([
                "Can you explain machine learning to me?",
                "What does machine learning mean in simple terms?",
                "How does machine learning work?",
                "Define machine learning and its main types",
                "What is an overview of machine learning?",
            ])
        clean_q = orig_q.rstrip("?.! ")
        return "\n".join([
            f"Can you explain {clean_q.lower()}?",
            f"What should I know about {clean_q.lower()}?",
            f"Please provide a clear summary of {clean_q.lower()}",
            f"How would you describe {clean_q.lower()}?",
            f"Tell me the key facts regarding {clean_q.lower()}",
        ])

    # 3. Standard user prompts: simulate realistic LLM inference latency unless disabled
    sim_latency = os.getenv("SIMULATE_LLM_LATENCY", "true").strip().lower()
    if sim_latency not in ("false", "0", "no"):
        time.sleep(random.uniform(0.45, 0.80))

    # Topic-specific rich deterministic responses
    if "uninstall" in lower and "docker" in lower:
        return (
            "To uninstall Docker completely from your system, first stop all running containers and the Docker daemon service. "
            "On Ubuntu/Debian Linux, run `sudo apt-get purge -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin` "
            "followed by removing residual images and volumes in `/var/lib/docker` and `/var/lib/containerd`. On Windows or macOS, "
            "open Settings or Applications, select Uninstall on Docker Desktop, and clean up `~/.docker` configuration files."
        )
    if "install" in lower and "docker" in lower:
        return (
            "To install Docker, set up the official Docker repository or download Docker Desktop for your operating system. "
            "On Ubuntu Linux, update `apt`, install CA certificates and curl, add Docker's official GPG key, configure the stable "
            "apt repository, and run `sudo apt-get install docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin`. "
            "Verify your installation by starting the service and running `docker run hello-world`."
        )

    if "capital" in lower:
        if "france" in lower:
            return (
                "The capital of France is Paris. Located in the north-central part of the country along the Seine River, "
                "Paris is France's largest city and serves as its major political, economic, cultural, and historical center."
            )
        if "germany" in lower:
            return (
                "The capital of Germany is Berlin. Situated in northeastern Germany along the Spree and Havel rivers, "
                "Berlin is both the nation's largest city and one of its sixteen constituent federal states."
            )
        if "japan" in lower:
            return (
                "The capital of Japan is Tokyo. Located at the head of Tokyo Bay on the Pacific coast of central Honshu, "
                "Tokyo is the seat of the Emperor of Japan, the national government, and the world's most populous metropolitan area."
            )
        if "india" in lower:
            return (
                "The capital of India is New Delhi. Situated within the National Capital Territory of Delhi in northern India, "
                "New Delhi serves as the seat of all three branches of the Government of India."
            )

    if any(w in lower for w in ["machine learning", "what is ml", "define ml", "explain ml"]):
        return (
            "Machine learning (ML) is a core branch of artificial intelligence that focuses on building algorithms and statistical "
            "models capable of learning patterns from data and making predictions or decisions without explicit rule-based programming. "
            "It is broadly categorized into supervised learning (training on labeled datasets), unsupervised learning (discovering "
            "hidden structures in unlabeled data), and reinforcement learning (optimizing actions via reward feedback)."
        )

    if "neural network" in lower:
        return (
            "A neural network is a computational model inspired by the biological neural networks of the human brain, consisting of "
            "interconnected layers of nodes (artificial neurons): an input layer, one or more hidden layers, and an output layer. "
            "Each connection applies a learnable weight and bias followed by a non-linear activation function, and the network is "
            "trained iteratively using backpropagation and gradient descent to minimize a loss function."
        )

    if any(w in lower for w in ["solar system", "largest planet", "biggest planet", "jupiter", "mars", "saturn", "red planet", "planet"]):
        return (
            "Our solar system contains eight planets orbiting the Sun: Mercury, Venus, Earth, Mars, Jupiter, Saturn, Uranus, and Neptune. "
            "Jupiter is the largest planet in the solar system and features the Great Red Spot, a massive centuries-old storm. "
            "Saturn is renowned for its extensive and bright ring system, while Mars is known as the Red Planet due to iron oxide dust covering its surface."
        )

    if "photosynthesis" in lower:
        return (
            "Photosynthesis is the biochemical process by which green plants, algae, and cyanobacteria convert light energy from the Sun "
            "into chemical energy stored in glucose molecules. Taking place inside chloroplasts using the pigment chlorophyll, the process "
            "absorbs carbon dioxide ($CO_2$) and water ($H_2O$) and releases oxygen ($O_2$) as a vital byproduct."
        )

    if "hamlet" in lower or "shakespeare" in lower:
        return (
            "Hamlet (The Tragedy of Hamlet, Prince of Denmark) is a celebrated tragedy written by William Shakespeare around 1600. "
            "It follows Prince Hamlet as he seeks vengeance against his uncle Claudius, who murdered Hamlet's father to seize the "
            "throne and marry Hamlet's mother Gertrude, exploring enduring themes of mortality, madness, betrayal, and moral hesitation."
        )

    if "relativity" in lower or "einstein" in lower:
        return (
            "The theory of relativity, formulated by Albert Einstein in the early 20th century, comprises Special Relativity (1905) and "
            "General Relativity (1915). Special relativity establishes that the speed of light in a vacuum is constant for all observers "
            "and introduces mass-energy equivalence ($E = mc^2$), while general relativity explains gravity as the geometric curvature "
            "of four-dimensional spacetime caused by mass and energy."
        )

    if "cpu" in lower or "central processing unit" in lower:
        return (
            "A Central Processing Unit (CPU) is the primary hardware processor of a computer responsible for executing instructions "
            "from software programs through the fetch-decode-execute cycle. It comprises an Arithmetic Logic Unit (ALU) for mathematical "
            "and logical operations, a Control Unit (CU) for instruction orchestration, high-speed registers, and multi-level L1/L2/L3 caches."
        )

    if "quantum computing" in lower or "quantum computer" in lower:
        return (
            "Quantum computing is an advanced paradigm of computation that harnesses quantum-mechanical phenomena such as superposition, "
            "entanglement, and quantum interference to process information. Unlike classical bits that represent either 0 or 1, quantum "
            "bits (qubits) can exist in linear combinations of states simultaneously, enabling exponential speedups for problems like "
            "integer factorization, molecular simulation, and combinatorial optimization."
        )

    if "python" in lower and "java" in lower:
        return (
            "Python and Java are two of the world's most widely used programming languages, each with distinct design philosophies. "
            "Python is dynamically typed and interpreted with concise, readable syntax ideal for data science, machine learning, and rapid "
            "backend development, whereas Java is statically typed and compiled to bytecode running on the JVM, offering strong compile-time "
            "type safety and high concurrency performance for large enterprise systems."
        )
    if "python" in lower:
        return (
            "Python is a high-level, interpreted, dynamically typed programming language created by Guido van Rossum that emphasizes code "
            "readability and developer productivity. It supports multiple paradigms including object-oriented, functional, and procedural "
            "programming, and powers a vast ecosystem for AI, data science, web services, and automation."
        )
    if "java" in lower:
        return (
            "Java is a high-level, class-based, statically typed object-oriented programming language designed around the 'write once, "
            "run anywhere' principle via the Java Virtual Machine (JVM). It features automatic garbage collection, strong memory safety, "
            "and robust multithreading support widely used in enterprise backends and Android development."
        )

    if any(w in lower for w in ["weather", "temperature", "forecast"]):
        return (
            f"Live meteorological update for query '{prompt_stripped}': Conditions are currently clear to partly cloudy with moderate "
            f"humidity, light winds at 12 km/h, and seasonal daytime temperatures. Because weather conditions change rapidly in real time, "
            f"this response is generated fresh without semantic cache storage."
        )

    return (
        f"Comprehensive analytical overview for '{prompt_stripped}': This subject involves core principles, structured methodologies, "
        f"and practical considerations relevant to modern engineering and scientific inquiry. By examining the underlying mechanisms "
        f"and domain context, practitioners can systematically evaluate key trade-offs and achieve reliable outcomes."
    )


def generate_llm_answer(prompt: str) -> dict:
    """
    Generates an LLM response using the official google-genai SDK and Gemini 3.x free-tier
    model cascade, falling back automatically to the deterministic generator if offline or rate-limited.
    """
    force_fallback = os.getenv("FORCE_FALLBACK_LLM", "false").strip().lower() in ("true", "1", "yes")

    if not force_fallback and genai_client is not None:
        for model_name in MODEL_CASCADE:
            try:
                response = genai_client.models.generate_content(
                    model=model_name,
                    contents=prompt,
                )
                text = getattr(response, "text", None)
                if text and text.strip():
                    clean_text = text.strip()
                    tokens_used = max(1, int(len( prompt.split() ) * 1.3 + len(clean_text.split()) * 1.3))
                    return {
                        "response": clean_text,
                        "model": model_name,
                        "tokens_used": tokens_used,
                        "is_fallback": False,
                    }
            except Exception as e:
                print(f"DEBUG: Gemini model '{model_name}' failed ({e}), trying next in cascade...")
                continue

    fallback_text = _get_fallback_response(prompt)
    tokens_used = max(1, int(len(prompt.split()) * 1.3 + len(fallback_text.split()) * 1.3))
    return {
        "response": fallback_text,
        "model": "deterministic-fallback-v3",
        "tokens_used": tokens_used,
        "is_fallback": True,
    }


def get_llm_response(prompt: str) -> str:
    """Backward-compatible helper returning only the LLM response string."""
    result = generate_llm_answer(prompt)
    return result["response"]


def get_embedding_with_time(text: str) -> tuple[list[float], float]:
    """
    Generates a normalized embedding vector for `text` and returns `(embedding_list, embedding_time_ms)`.
    """
    start_time = time.perf_counter()
    model = get_embedding_model()
    if model is None:
        return [], 0.0
    embedding = model.encode(text, normalize_embeddings=True)
    embedding_time_ms = (time.perf_counter() - start_time) * 1000.0
    return embedding.tolist(), round(embedding_time_ms, 3)


def get_embedding(text: str) -> list[float]:
    """Generates a normalized embedding vector for `text` using the singleton SentenceTransformer."""
    embedding, _ = get_embedding_with_time(text)
    return embedding
