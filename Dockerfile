FROM python:3.11-slim

# Install minimal system build and runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user (uid=1000) required by Hugging Face Docker Spaces
# and create writable cache directories for Hugging Face & ChromaDB
RUN useradd -m -u 1000 user && \
    mkdir -p /app /tmp/hf_cache /tmp/chroma_cache && \
    chown -R user:user /app /tmp/hf_cache /tmp/chroma_cache

WORKDIR /app

# Runtime & model cache environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    HF_HOME=/tmp/hf_cache \
    SENTENCE_TRANSFORMERS_HOME=/tmp/hf_cache \
    CHROMA_PERSIST_DIR=/tmp/chroma_cache \
    EMBEDDING_MODEL=BAAI/bge-small-en-v1.5 \
    PORT=7860

# Install CPU-only PyTorch first to keep the image small and fast to build,
# followed by the rest of requirements.txt
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir torch --extra-index-url https://download.pytorch.org/whl/cpu && \
    pip install --no-cache-dir -r /app/requirements.txt

# Pre-download BAAI/bge-small-en-v1.5 during build so container startup is instant
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('BAAI/bge-small-en-v1.5')" && \
    chown -R user:user /tmp/hf_cache /tmp/chroma_cache

# Copy backend application code with proper ownership
COPY --chown=user:user api/ /app/api/
COPY --chown=user:user proactive_cacher.py /app/proactive_cacher.py

USER user

EXPOSE 7860

CMD ["sh", "-c", "uvicorn api.main:app --host 0.0.0.0 --port ${PORT:-7860}"]
