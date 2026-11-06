import os
import google.generativeai as genai
from sentence_transformers import SentenceTransformer
from dotenv import load_dotenv

# --- Load Environment Variables ---
load_dotenv()

# --- Configure the Gemini API ---
try:
    genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
    GEMINI_MODEL = genai.GenerativeModel('gemini-2.0-flash')
except Exception as e:
    print(f"Error configuring Gemini API: {e}")
    GEMINI_MODEL = None

# --- Load the Local Embedding Model ---
# Get the model name from an environment variable, with a default.
EMBEDDING_MODEL_NAME = os.getenv("EMBEDDING_MODEL", "BAAI/bge-base-en-v1.5")
EMBEDDING_MODEL = None # Initialize to None

try:
    print(f"--- Loading Embedding Model: {EMBEDDING_MODEL_NAME} ---")

    # --- THIS IS THE FIX ---
    # Check if the model is Nomic and add the special flag if it is.
    if "nomic" in EMBEDDING_MODEL_NAME:
        print("   (Nomic model detected, using trust_remote_code=True)")
        EMBEDDING_MODEL = SentenceTransformer(EMBEDDING_MODEL_NAME, trust_remote_code=True)
    else:
        # All other models are loaded the standard way.
        EMBEDDING_MODEL = SentenceTransformer(EMBEDDING_MODEL_NAME)
    
    print(f"Successfully loaded {EMBEDDING_MODEL_NAME}.")

except Exception as e:
    print(f"Error loading embedding model {EMBEDDING_MODEL_NAME}: {e}")
    EMBEDDING_MODEL = None # Ensure it's None on failure


def get_llm_response(prompt: str) -> str:
    """Gets a response from the Gemini LLM."""
    if not GEMINI_MODEL:
        return "Gemini model is not configured. Please check your API key."
    try:
        response = GEMINI_MODEL.generate_content(prompt)
        return response.text
    except Exception as e:
        print(f"Error calling Gemini API: {e}")
        return f"Sorry, I encountered an error with the Gemini API: {e}"

def get_embedding(text: str) -> list[float]:
    """Gets an embedding for a given text using a local model."""
    if not EMBEDDING_MODEL:
        print("Embedding model not loaded.")
        return []
    embedding = EMBEDDING_MODEL.encode(text)
    return embedding.tolist()