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
try:
    # --- UPGRADE ---
    # Switched to a much more powerful embedding model for better semantic understanding.
    EMBEDDING_MODEL = SentenceTransformer('BAAI/bge-large-en-v1.5')
    print("BGE Large embedding model loaded successfully.")
except Exception as e:
    print(f"Error loading SentenceTransformer model: {e}")
    EMBEDDING_MODEL = None

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