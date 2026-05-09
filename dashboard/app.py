"""Streamlit dashboard for Aperture agent workflow demo."""

import json
import uuid
from pathlib import Path

import streamlit as st

st.set_page_config(page_title="Aperture Dashboard", page_icon="🔭", layout="wide")

import sys

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from aperture.demo.agent_simulator import (
    run_workflow_with_aperture,
    run_workflow_without_aperture,
)
from aperture.demo.scenarios import SCENARIOS

st.title("🔭 Aperture — Context Engineering for Composio")
st.caption("Agent workflows: measure, compact, compress, cache")

# --- Sidebar ---
with st.sidebar:
    st.header("🎬 Scenario")
    scenario_name = st.selectbox(
        "Choose a scenario",
        list(SCENARIOS.keys()),
        format_func=lambda k: f"{k.replace('_', ' ').title()} — {SCENARIOS[k].description[:50]}...",
    )

    st.divider()
    st.header("⚙️ Configuration")
    effort_mode = st.selectbox("Effort Mode", ["off", "low", "medium", "high"], index=2)
    use_cache = st.toggle("Enable Cache", value=True)
    show_raw = st.toggle("Show Raw JSON", value=False)

    run_button = st.button("🚀 Run Agent Workflow", type="primary", use_container_width=True)

scenario = SCENARIOS[scenario_name]

# --- Main ---
if run_button:
    with st.spinner("Simulating agent workflow..."):
        # Clear cache for fresh demo
        if use_cache:
            try:
                from upstash_redis import Redis
                from aperture.config import Config
                r = Redis(url=Config.UPSTASH_REDIS_REST_URL, token=Config.UPSTASH_REDIS_REST_TOKEN)
                for k in r.keys("aperture:cache:*"):
                    r.delete(k)
            except Exception:
                pass

        raw_result = run_workflow_without_aperture(scenario_name)
        opt_result = run_workflow_with_aperture(
            scenario_name, mode=effort_mode, enable_cache=use_cache
        )

    # --- Header stats ---
    st.subheader(f"📊 {scenario.description}")
    cols = st.columns(4)
    raw_total = raw_result.total_raw_tokens
    opt_total = opt_result.total_compressed_tokens
    saved = raw_total - opt_total
    ratio = saved / raw_total if raw_total > 0 else 0

    with cols[0]:
        st.metric("Raw Tokens", f"{raw_total:,}")
    with cols[1]:
        st.metric("With Aperture", f"{opt_total:,}")
    with cols[2]:
        st.metric("Tokens Saved", f"{saved:,}", delta=f"-{ratio:.0%}")
    with cols[3]:
        st.metric("Cache Hits", f"{opt_result.cache_hits}/{len(opt_result.steps)}")

    # --- Context Window Pressure ---
    st.subheader("🌊 Context Window Pressure")
    max_context = 128_000

    raw_pct = min(raw_result.context_window_used / max_context, 1.0)
    opt_pct = min(opt_result.context_window_used / max_context, 1.0)

    col1, col2 = st.columns(2)
    with col1:
        st.progress(raw_pct, text=f"Without Aperture: {raw_result.context_window_used:,} tokens ({raw_pct:.1%})")
    with col2:
        st.progress(opt_pct, text=f"With Aperture: {opt_result.context_window_used:,} tokens ({opt_pct:.1%})")

    if raw_pct > 0.5:
        st.error("⚠️ Without Aperture, you're using >50% of your context window!")
    if opt_pct < 0.1:
        st.success("✅ With Aperture, context pressure is minimal.")

    # --- Per-Step Breakdown ---
    st.subheader("🔍 Per-Step Breakdown")

    step_data = []
    for i, step in enumerate(opt_result.steps):
        step_data.append({
            "Step": i + 1,
            "Tool": step.tool_slug,
            "Raw Tokens": step.raw_tokens,
            "Compressed": step.compressed_tokens,
            "Saved": step.tokens_saved,
            "Cache": step.cache_status,
            "Strategy": step.strategy,
        })

    st.dataframe(step_data, use_container_width=True, hide_index=True)

    # --- Token Waterfall ---
    st.subheader("📉 Token Waterfall by Step")
    chart_data = {
        f"Step {i+1}": {
            "Raw": step.raw_tokens,
            "Compressed": step.compressed_tokens,
        }
        for i, step in enumerate(opt_result.steps)
    }
    st.bar_chart({k: v for k, v in chart_data.items()})

    # --- Before vs After JSON ---
    if show_raw:
        st.subheader("📄 Raw vs Compressed Output")
        for i, (raw_step, opt_step) in enumerate(zip(raw_result.steps, opt_result.steps)):
            with st.expander(f"Step {i+1}: {opt_step.tool_slug}"):
                col1, col2 = st.columns(2)
                with col1:
                    st.caption(f"Raw ({raw_step.raw_tokens:,} tokens)")
                    # Get mock result for display
                    from aperture.demo.scenarios import get_mock_result
                    st.json(get_mock_result(opt_step.tool_slug, opt_step.arguments), expanded=False)
                with col2:
                    st.caption(f"Compressed ({opt_step.compressed_tokens:,} tokens)")
                    # Show compressed payload
                    from aperture.compression.engine import compress_tool_output
                    from aperture.routing.effort_modes import get_effort_config
                    effort = get_effort_config(effort_mode)
                    compressed = compress_tool_output(
                        raw_payload=get_mock_result(opt_step.tool_slug, opt_step.arguments),
                        tool_slug=opt_step.tool_slug,
                        mode=effort.compression_mode,
                        model="gpt-4o",
                    )
                    st.json(compressed.compressed_payload, expanded=False)

    # --- Cache Demo ---
    if use_cache and opt_result.cache_misses > 0:
        st.divider()
        if st.button("🔄 Run Again (Test Cache)", use_container_width=True):
            with st.spinner("Checking cache..."):
                opt2 = run_workflow_with_aperture(scenario_name, mode=effort_mode, enable_cache=True)

            if opt2.cache_hits > 0:
                st.success(f"✅ {opt2.cache_hits}/{len(opt2.steps)} steps served from cache — zero API calls!")
            else:
                st.error("❌ Cache miss")

else:
    # Default state
    st.info("👈 Choose a scenario and click **Run Agent Workflow**")

    st.markdown("""
    ### What Aperture does for agent workflows

    Composio returns **massive** tool outputs — a 4-step agent workflow can easily consume
    **25,000+ tokens**. Aperture fixes this:

    1. **Measures** every token added to the agent's context window
    2. **Routes** tools through effort modes (`low`/`medium`/`high`) — only expose what's needed
    3. **Compresses** raw API outputs by 70-80% — drops URLs, nulls, empty objects
    4. **Caches** safe repeated reads in Redis — skip redundant API calls

    ### Demo scenarios
    - **Research Project**: GitHub repo → issues → PRs → commits (4 steps, ~25K raw tokens)
    - **Triage Bugs**: GitHub issues → Gmail search → Slack search (3 steps, ~11K raw tokens)
    - **Onboard User**: GitHub repo → commits → Slack activity (3 steps, ~7K raw tokens)
    """)
