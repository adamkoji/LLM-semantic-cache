import streamlit as st
import requests
import time
import pandas as pd

st.set_page_config(page_title="Cache Performance Dashboard", layout="wide", initial_sidebar_state="collapsed")
st.title("📊 Live LLM Cache Performance Dashboard")

METRICS_URL = "http://127.0.0.1:8000/metrics/"
placeholder = st.empty()

# Loop to auto-refresh data
while True:
    try:
        r = requests.get(METRICS_URL)
        r.raise_for_status()
        metrics = r.json()

        with placeholder.container():
            # Key Performance Indicators
            kpi1, kpi2, kpi3 = st.columns(3)
            total_requests = metrics.get("total_requests", 0)
            hit_rate = (metrics.get("cache_hits", 0) / total_requests * 100) if total_requests > 0 else 0
            
            kpi1.metric(label="Cache Hit Rate", value=f"{hit_rate:.2f} %")
            kpi2.metric(label="Total Latency Saved (est.)", value=f"{metrics.get('total_latency_saved', 0):.2f} s")
            kpi3.metric(label="Total Requests Processed", value=total_requests)

            # Bar Chart for breakdown
            st.markdown("---")
            st.subheader("Request Breakdown")
            chart_data = pd.DataFrame({
                'Category': ['Cache Hits', 'Cache Misses'],
                'Count': [metrics.get("cache_hits", 0), metrics.get("cache_misses", 0)]
            })
            st.bar_chart(chart_data.set_index('Category'))

    except requests.exceptions.RequestException:
        st.warning("Waiting for the API to be available...")

    time.sleep(2) # Refresh interval