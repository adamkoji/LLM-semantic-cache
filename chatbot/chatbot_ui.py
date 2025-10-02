import streamlit as st
import requests

# Page configuration
st.set_page_config(page_title="Semantic Cache Chatbot", layout="wide")
st.title("🤖 LLM Inference Cache Demo (with Gemini)")
st.write("Ask a question. If a similar question has been asked, you'll get a super-fast cached response!")

# Backend URL
FASTAPI_URL = "http://127.0.0.1:8000/process-prompt/"

# Initialize chat history in session state
if "messages" not in st.session_state:
    st.session_state.messages = []

# Display chat messages from history on app rerun
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Accept user input
if prompt := st.chat_input("Ask about the Eiffel Tower or the capital of France..."):
    # Add user message to chat history
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # Get bot response
    with st.chat_message("assistant"):
        message_placeholder = st.empty()
        with st.spinner("Thinking..."):
            try:
                response = requests.post(FASTAPI_URL, json={"prompt": prompt})
                response.raise_for_status() # Raise an HTTPError for bad responses (4xx or 5xx)
                data = response.json()
                
                is_cached = data.get("from_cache", False)
                latency = data.get("latency", 0)
                llm_response = data.get("response", "Sorry, an error occurred.")

                cache_status_emoji = "⚡️" if is_cached else "🐢"
                cache_status_text = "CACHE HIT" if is_cached else "CACHE MISS"
                
                full_response = f"""
                {llm_response}

                ---
                *{cache_status_emoji} {cache_status_text} | Response Time: {latency:.3f} seconds*
                """
                message_placeholder.markdown(full_response)
                st.session_state.messages.append({"role": "assistant", "content": full_response})

            except requests.exceptions.RequestException as e:
                st.error(f"Could not connect to the backend API. Please ensure it is running. Error: {e}")