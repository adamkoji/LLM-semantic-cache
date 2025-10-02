import os
import google.generativeai as genai
from dotenv import load_dotenv

# --- 1. Load Environment Variables ---
# This loads the GOOGLE_API_KEY from your .env file
load_dotenv()
print("Attempting to load API key from .env file...")

try:
    # --- 2. Configure the API ---
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError("GOOGLE_API_KEY not found in .env file.")
    
    print("API Key loaded successfully.")
    genai.configure(api_key=api_key)

    # --- 3. Initialize the Model ---
    # We are using the most standard model name for this test.
    print("Initializing model 'gemini-pro'...")
    model = genai.GenerativeModel('gemini-pro')

    # --- 4. Generate Content ---
    print("Sending prompt to Gemini API...")
    response = model.generate_content("What is deep learning? Explain it in one sentence.")

    # --- 5. Print the Result ---
    print("\n--- SUCCESS! ---")
    print(response.text)

except Exception as e:
    print("\n--- AN ERROR OCCURRED ---")
    print(f"The test failed with the following error:\n{e}")