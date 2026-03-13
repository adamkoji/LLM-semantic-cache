# LLM Inference Cache with Semantic Similarity

This project is a comprehensive, full-stack implementation of a tiered semantic caching system for Large Language Model (LLM) inference. It is designed to solve the critical challenges of high latency and computational cost associated with deploying LLMs in production environments.

The system intelligently caches LLM responses and serves them for subsequent queries that are not just textually identical, but **semantically equivalent**. This is achieved through a state-of-the-art tiered architecture, which is then enhanced with a novel **proactive caching** mechanism that allows the system to learn from its own failures and anticipate user needs.

This repository contains the full application code, along with a suite of **five advanced analysis scripts** used to rigorously benchmark the system's performance, cost-effectiveness, and intelligence.

![Project Demo GIF](https://i.imgur.com/your-demo.gif)
_Recommendation: Create a short screen recording (GIF) of your chatbot and dashboard working, upload it to a service like Imgur, and paste the direct link here._

---

## Table of Contents
- [Problem Statement](#problem-statement)
- [Our Solution: An Intelligent Tiered Architecture](#our-solution-an-intelligent-tiered-architecture)
- [Key Features](#key-features)
- [Performance Highlights](#performance-highlights)
- [Technology Stack](#technology-stack)
- [Project Structure](#project-structure)
- [Setup and Installation](#setup-and-installation)
- [How to Run the Project](#how-to-run-the-project)
- [How to Run the Analysis Suite](#how-to-run-the-analysis-suite)
- [Future Work](#future-work)

---

## Problem Statement

Large Language Models are computationally expensive. In real-world applications, users frequently ask the same question using different wording. Traditional caches, which rely on exact-text matches, fail to handle this linguistic variation. This leads to redundant API calls, increasing both user latency and operational costs. Our project aims to solve this inefficiency.

---

## Our Solution: An Intelligent Tiered Architecture

This project implements a sophisticated, multi-layered caching system that understands the *meaning* of a prompt, not just the words.

- **Tier 1: Redis Cache (Exact-Match):** A lightning-fast in-memory cache that handles high-frequency, identical queries with microsecond latency.
- **Tier 2: ChromaDB Cache (Semantic Match):** A powerful vector database that stores prompt embeddings using the `BAAI/bge-large-en-v1.5` model to identify and serve paraphrased queries.
- **Tier 3: Google Gemini LLM (Cache Miss):** Only if both caches miss does the system make an expensive call to the primary LLM.

---

## Key Features

- **Tiered Caching:** Combines the speed of key-value caching with the intelligence of vector search for optimal performance.
- **Advanced Cache Management:** Implements an **LRU (Least Recently Used) Eviction Policy** to manage cache size and a **Quality Admission Policy** to prevent "cache poisoning" from LLM errors.
- **Proactive Caching (Self-Optimization):** Includes a novel mechanism to analyze logs of cache misses, identify emerging topics using **DBSCAN clustering**, and proactively "warm" the cache to anticipate future user queries.
- **Full-Stack Observability:** Comes with a live, auto-refreshing Streamlit dashboard to monitor real-time performance metrics.
- **Rigorous Analysis Suite:** Includes five standalone Python scripts to perform deep, data-driven analysis of the system's performance, cost, and intelligence.

---

## Performance Highlights

Our extensive benchmarking proves the system's effectiveness, with our final architecture achieving an **86.8% cache hit rate** in focused tests, significantly outperforming both a simple cache and published research benchmarks like GPTCache.

| Response Type          | Average Latency | Speed Improvement (vs. LLM) |
| ---------------------- | --------------- | --------------------------- |
| LLM Call (Cache Miss)  | ~4541 ms        | 1x                          |
| **T2 Semantic Hit**    | **~204 ms**     | **~22x faster**             |
| **T1 Exact-Match Hit** | **~5 ms**       | **~900x faster**            |

![Comparison of Caching Mechanisms](chart_final_definitive_comparison.png)
_This chart shows our tiered cache (right) significantly outperforming a simple exact-match cache (middle) by successfully handling paraphrased queries._

---

## Technology Stack

- **Backend:** FastAPI, Uvicorn
- **LLM:** Google Gemini API (`gemini-pro`)
- **Semantic Caching (Tier 2):**
  - **Vector Database:** ChromaDB
  - **Embedding Model:** `BAAI/bge-large-en-v1.5`
- **Exact-Match Caching (Tier 1):** Redis
- **Proactive Caching Analysis:** Scikit-learn (for DBSCAN)
- **Frontend & Dashboard:** Streamlit
- **Containerization:** Docker (for Redis & ChromaDB)
- **Analysis & Visualization:** Matplotlib, NumPy

---

## Project Structure
 <img width="695" height="850" alt="image" src="https://github.com/adamkoji/LLM-semantic-cache/edit/main/prj-structure.png" /> 
