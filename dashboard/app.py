"""Streamlit dashboard for Aperture — visual hackathon demo."""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import streamlit as st

st.set_page_config(page_title="Aperture Dashboard", page_icon="🔭", layout="wide")

from aperture.demo.agent_simulator import (
    run_workflow_with_aperture,
    run_workflow_without_aperture,
)
from aperture.demo.scenarios import SCENARIOS
from aperture.compression.engine import compress_tool_output
from aperture.tokenization import count_tokens

st.title("🔭 Aperture — Context Engineering for Composio")
st.caption("Visual demo: measure, compact, compress, cache")

# ============== TABS ==============
tab_overview, tab_gsheets, tab_mock, tab_agent, tab_dynamic, tab_live, tab_benchmarks = st.tabs([
    "📊 Overview",
    "📑 Google Sheets (10K Rows)",
    "🗂️  Mock Datasets",
    "🤖 Agent Workflows",
    "🧠 Dynamic Agent",
    "🎬 Live Agent",
    "📈 Benchmarks",
])


# =============================================================================
# TAB 1: OVERVIEW
# =============================================================================
with tab_overview:
    st.header("What Aperture Does")

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Raw Tokens", "547,522")
    with col2:
        st.metric("Compressed", "5,728", delta="-99.0%")
    with col3:
        st.metric("Cache Hit 2nd Call", "489ms", delta="-86% latency")
    with col4:
        st.metric("Cost Saved", "$1.37 → $0.014", delta="-99%")

    st.divider()

    st.subheader("Architecture")
    st.code("""
WITHOUT Aperture:
    Agent → Composio API → Raw Result (547K tokens) → LLM ❌ CRASH

WITH Aperture:
    Agent → ApertureRunner → Composio API → Raw Result (547K)
                                ↓
                        Compression (tabular_balanced)
                                ↓
                        Cache (Redis) → 5,728 tokens → LLM ✅
    """, language="text")

    st.subheader("Cache Key Scoping")
    st.code("""
aperture:cache:u:user-A:GOOGLESHEETS_BATCH_GET:ffb1e46bc5e7f63e
aperture:cache:u:user-B:GOOGLESHEETS_BATCH_GET:ffb1e46bc5e7f63e

Same tool + args, but DIFFERENT users = DIFFERENT cache entries.
No data leaks between tenants.
    """, language="text")


# =============================================================================
# TAB 2: GOOGLE SHEETS (10K ROWS)
# =============================================================================
with tab_gsheets:
    st.header("📑 Google Sheets Demo: 10,000 Rows")

    st.markdown("""
    **The Problem:** Composio reading a Google Sheet with 10K rows returns **547,522 tokens**.
    That's **4.3× your entire GPT-4o context window**.
    
    **Aperture's Solution:** Intelligent tabular compression — sample rows + statistics.
    """)

    st.link_button(
        "🔗 View Live Google Sheet (10,000 rows)",
        "https://docs.google.com/spreadsheets/d/1eyr5XV1pGyJTbRWpFVIp_fcrLK-oEp4tlVg3l1VsqR0/edit",
    )

    st.divider()

    # Visual comparison
    st.subheader("Before vs After")

    col_raw, col_comp = st.columns(2)

    with col_raw:
        st.error("❌ Vanilla Composio (Raw)")
        st.metric("Tokens", "547,522")
        st.metric("Context Window", "428% ⚠️")
        st.metric("Cost", "~$1.37")

        with st.expander("What the LLM sees (first 5 rows)", expanded=True):
            st.json([
                ["id","username","email","name","company","location","followers","following","public_repos","total_stars","account_created","bio","hireable"],
                ["1","johnsmith42","johnsmith42@example.com","John Smith","Google","San Francisco, CA","15420","340","45","89200","2015-03-12","Building AI agents at Google","TRUE"],
                ["2","maryjones88","maryjones88@example.com","Mary Jones","Microsoft","Seattle, WA","8320","120","67","45100","2016-07-22","","FALSE"],
                ["3","robertbrown","robertbrown@example.com","Robert Brown","Stripe","New York, NY","23100","890","23","120500","2014-11-05","Former Engineer at Stripe","TRUE"],
                ["4","...","...","...","...","...","...","...","...","...","...","...","..."],
            ])
            st.caption("... plus 9,997 more rows — ALL go to the LLM")

    with col_comp:
        st.success("✅ Aperture (Compressed)")
        st.metric("Tokens", "5,728")
        st.metric("Context Window", "4.5% ✅")
        st.metric("Cost", "~$0.014")

        with st.expander("What the LLM sees", expanded=True):
            st.json({
                "_aperture_summary": {
                    "total_rows": 10000,
                    "sampled_rows": 100,
                    "columns_shown": 13,
                    "columns_dropped": 0,
                    "sampling_method": "balanced_tabular",
                },
                "headers": ["id","username","email","name","company","location","followers","following","public_repos","total_stars","account_created","bio","hireable"],
                "sample": [
                    ["1","johnsmith42","johnsmith42@example.com","John Smith","Google","San Francisco, CA","15420","340","45","89200","2015-03-12","Building AI agents at Google","TRUE"],
                    ["98","juliejohnson24362","...","Julie Johnson","Alera","Kigali, RW","27063","1083","319","82635","2010-03-28","","TRUE"],
                    ["198","christopherbuckner8847","...","Christopher Buckner","","Guadalajara, MX","33611","1456","96","28835","2020-12-16","disrupting content strategy at ASRock","TRUE"],
                ],
                "stats": {
                    "followers": {"min": 13, "max": 48685, "avg": 24348},
                    "following": {"min": 158, "max": 4819, "avg": 2535},
                    "public_repos": {"min": 1, "max": 492, "avg": 228},
                    "total_stars": {"min": 954, "max": 99223, "avg": 45728},
                }
            })
            st.caption("100 representative rows + summary statistics")

    st.divider()

    # Context window bars
    st.subheader("🌊 Context Window Pressure")
    max_ctx = 128_000

    raw_pct = 547_522 / max_ctx
    comp_pct = 5_728 / max_ctx

    st.progress(min(raw_pct, 1.0), text=f"Vanilla: 547,522 tokens ({raw_pct:.1f}× overflow)")
    st.progress(min(comp_pct, 1.0), text=f"Aperture: 5,728 tokens ({comp_pct*100:.1f}% of 128K)")

    st.divider()

    # Effort modes for tabular
    st.subheader("📉 Effort Modes for Tabular Data")

    mode = st.select_slider("Select effort mode", options=["safe", "balanced", "low"], value="balanced")

    if mode == "safe":
        sample = 500
        max_cell = 200
    elif mode == "balanced":
        sample = 200
        max_cell = 100
    else:
        sample = 50
        max_cell = 50

    estimated_tokens = sample * 50  # rough estimate

    st.metric("Sampled rows", f"{sample:,}")
    st.metric("Max cell length", f"{max_cell} chars")
    st.metric("Estimated tokens", f"{estimated_tokens:,}")

    st.info(f"**{mode} mode**: Keeps {sample} representative rows out of 10,000. "
            f"Truncates cells to {max_cell} characters. "
            f"Adds statistics for numeric columns.")


# =============================================================================
# TAB 3: MOCK DATASETS (Notion / Linear / Supabase)
# =============================================================================
with tab_mock:
    st.header("🗂️  Mock Datasets — Test Nonstop")
    st.markdown("""
    Live API writes are blocked by permissions (Notion pages not shared, Linear admin-only, Supabase no-insert tools).
    
    Instead, these **realistic mock datasets** match the exact shape of Composio API responses.
    Run compression demos without API limits.
    """)

    import json as _json
    DATA_DIR = PROJECT_ROOT / "data"

    def _load_mock(name):
        with open(DATA_DIR / name) as f:
            return _json.load(f)

    def _run_mock_demo(label, filename, tool_slug):
        data = _load_mock(filename)
        raw_tc = count_tokens(data)
        raw_tokens = raw_tc.tokens

        modes = ["off", "safe", "balanced", "low"]
        rows = []
        for mode in modes:
            result = compress_tool_output(data, tool_slug, mode=mode, model="gpt-4o")
            comp_tc = count_tokens(result.compressed_payload)
            comp_tokens = comp_tc.tokens
            rows.append({
                "Mode": mode,
                "Tokens": f"{comp_tokens:,}",
                "Reduction": f"{(1 - comp_tokens / raw_tokens) * 100:.1f}%",
                "Context %": f"{comp_tokens / 128_000 * 100:.1f}%",
                "Strategy": result.strategy,
            })

        st.subheader(label)
        st.caption(f"{filename} — {len(data):,} items — {raw_tokens:,} raw tokens")
        st.dataframe(rows, width="stretch", hide_index=True)

        # Show a sample record
        balanced_result = compress_tool_output(data, tool_slug, mode="balanced", model="gpt-4o")
        sample = balanced_result.compressed_payload.get("sample", [])
        summary = balanced_result.compressed_payload.get("_aperture_summary", {})
        stats = balanced_result.compressed_payload.get("stats", {})

        c1, c2 = st.columns(2)
        with c1:
            with st.expander("Sample record (balanced mode)"):
                if sample:
                    st.json(sample[0])
        with c2:
            with st.expander("Summary & stats"):
                st.json({"summary": summary, "stats": stats})

        st.divider()

    _run_mock_demo("📄 Notion — 500 Pages", "notion_pages_500.json", "NOTION_SEARCH_NOTION_PAGE")
    _run_mock_demo("📌 Linear — 200 Issues", "linear_issues_200.json", "LINEAR_GET_LINEAR_USER_ISSUES")
    _run_mock_demo("🗃️ Supabase — 1,000 Rows", "supabase_users_1000.json", "SUPABASE_FETCH_TABLE_ROWS")


# =============================================================================
# TAB 4: AGENT WORKFLOWS
# =============================================================================
with tab_agent:
    st.header("🤖 Multi-Step Agent Workflows")

    st.markdown("""
    Real agents make **multiple tool calls** in sequence. Context window pressure builds up.
    Aperture manages this automatically.
    """)

    scenario_name = st.selectbox(
        "Choose a scenario",
        list(SCENARIOS.keys()),
        format_func=lambda k: f"{k.replace('_', ' ').title()} — {SCENARIOS[k].description[:40]}...",
    )

    effort_mode = st.selectbox("Effort Mode", ["off", "low", "medium", "high", "auto"], index=2)
    enable_cache = st.toggle("Enable Cache", value=True)
    run_workflow = st.button("🚀 Run Workflow Comparison", type="primary")

    if run_workflow:
        with st.spinner("Running agent workflow..."):
            # Clear cache for fresh demo
            if enable_cache:
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
                scenario_name, mode=effort_mode, enable_cache=enable_cache
            )

        # Summary stats
        raw_total = raw_result.total_raw_tokens
        opt_total = opt_result.total_compressed_tokens
        saved = raw_total - opt_total
        ratio = saved / raw_total if raw_total > 0 else 0

        cols = st.columns(4)
        with cols[0]:
            st.metric("Raw Tokens", f"{raw_total:,}")
        with cols[1]:
            st.metric("With Aperture", f"{opt_total:,}")
        with cols[2]:
            st.metric("Saved", f"{saved:,}", delta=f"-{ratio:.0%}")
        with cols[3]:
            st.metric("Cache Hits", f"{opt_result.cache_hits}/{len(opt_result.steps)}")

        # Context window bars
        st.subheader("Context Window Pressure")
        max_ctx = 128_000
        raw_pct = min(raw_result.context_window_used / max_ctx, 1.0)
        opt_pct = min(opt_result.context_window_used / max_ctx, 1.0)

        col1, col2 = st.columns(2)
        with col1:
            st.progress(raw_pct, text=f"Without Aperture: {raw_result.context_window_used:,} tokens ({raw_pct*100:.1f}%)")
        with col2:
            st.progress(opt_pct, text=f"With Aperture: {opt_result.context_window_used:,} tokens ({opt_pct*100:.1f}%)")

        # Per-step breakdown
        st.subheader("Per-Step Breakdown")

        step_data = []
        for i, step in enumerate(opt_result.steps):
            step_data.append({
                "Step": i + 1,
                "Tool": step.tool_slug,
                "Raw": step.raw_tokens,
                "Compressed": step.compressed_tokens,
                "Saved": step.tokens_saved,
                "Cache": step.cache_status,
                "Strategy": step.strategy,
            })

        st.dataframe(step_data, width="stretch", hide_index=True)

        # Token waterfall
        st.subheader("Token Waterfall")
        chart_data = {
            f"Step {i+1}": {
                "Raw": step.raw_tokens,
                "Compressed": step.compressed_tokens,
            }
            for i, step in enumerate(opt_result.steps)
        }
        st.bar_chart({k: v for k, v in chart_data.items()})

        # Auto reasoning
        if effort_mode == "auto":
            st.subheader("🧠 Auto Effort Decisions")
            for i, step in enumerate(opt_result.steps):
                if len(step.strategy) > 10:
                    st.info(f"**Step {i+1} ({step.tool_slug}):** {step.strategy}")

        # Cache re-run
        if enable_cache and opt_result.cache_misses > 0:
            st.divider()
            if st.button("🔄 Run Again (Test Cache)"):
                with st.spinner("Checking cache..."):
                    opt2 = run_workflow_with_aperture(scenario_name, mode=effort_mode, enable_cache=True)

                if opt2.cache_hits > 0:
                    st.success(f"✅ {opt2.cache_hits}/{len(opt2.steps)} steps served from cache — zero API calls!")
                else:
                    st.error("❌ Cache miss")


# =============================================================================
# TAB 4: DYNAMIC AGENT
# =============================================================================
with tab_dynamic:
    st.header("🧠 Dynamic Agent with Semantic Routing")

    st.markdown("""
    Instead of hardcoding tool calls, the agent **understands your intent** and
    dynamically picks the right Composio tools — even toolkits added after deployment.
    """)

    intent = st.text_input(
        "What do you want the agent to do?",
        value="Find all open bugs in composio and check if customers have reported them",
    )

    if st.button("🔍 Match Intent to Tools", type="primary"):
        from aperture.routing.semantic_selector import DynamicAgent

        AVAILABLE_TOOLS = [
            "GITHUB_GET_A_REPOSITORY", "GITHUB_LIST_ISSUES", "GITHUB_LIST_PULL_REQUESTS",
            "GITHUB_LIST_COMMITS", "GITHUB_GET_ISSUE", "GITHUB_GET_USER",
            "GMAIL_SEARCH_EMAILS", "GMAIL_FETCH_EMAILS",
            "SLACK_SEARCH_MESSAGES", "SLACK_LIST_CHANNELS", "SLACK_GET_CHANNEL",
            "GOOGLE_CALENDAR_LIST_EVENTS", "GOOGLE_CALENDAR_GET_EVENT",
            "HUBSPOT_GET_CONTACT", "HUBSPOT_LIST_CONTACTS",
            "ZENDESK_LIST_TICKETS", "ZENDESK_GET_TICKET",
            "SHOPIFY_LIST_PRODUCTS", "SHOPIFY_GET_ORDER",
        ]

        agent = DynamicAgent(available_tools=AVAILABLE_TOOLS)
        matches = agent.plan(intent)

        st.subheader("Semantic Matches")

        match_data = []
        for i, m in enumerate(matches[:5]):
            match_data.append({
                "Rank": i + 1,
                "Tool": m.tool_slug,
                "Toolkit": m.toolkit,
                "Score": f"{m.score:.2f}",
                "Effort": m.effort_mode,
                "Reasoning": m.reasoning[:80] + "..." if len(m.reasoning) > 80 else m.reasoning,
            })

        st.dataframe(match_data, width="stretch", hide_index=True)

        st.subheader("Dynamic Toolkit Expansion")
        st.markdown("New toolkits are automatically available — no code changes needed.")

        # Show auto-profile
        from aperture.schema_optimizer.auto_profile import ProfileRegistry
        registry = ProfileRegistry()

        for match in matches[:3]:
            from aperture.demo.scenarios import get_mock_result
            sample = get_mock_result(match.tool_slug, match.suggested_arguments)
            profile = registry.register(match.tool_slug, sample)

            with st.expander(f"📐 Auto-Profile: {match.tool_slug}"):
                col1, col2 = st.columns(2)
                with col1:
                    st.metric("Raw Tokens", f"{profile.typical_raw_tokens:,}")
                    st.metric("Compressed", f"{profile.typical_compressed_tokens:,}")
                with col2:
                    st.metric("Savings", f"{profile.estimated_savings:.0%}")
                    st.metric("Mode", profile.recommended_mode)

                st.caption(f"Critical fields: {', '.join(profile.critical_fields[:5])}")
                st.caption(f"Droppable fields: {', '.join(profile.droppable_fields[:5])}")


# =============================================================================
# TAB 5: LIVE AGENT — Real-Time Thinking Demo
# =============================================================================
with tab_live:
    import time

    st.header("🎬 Live Agent — See the Thinking in Real Time")
    st.markdown("""
    Watch Aperture's agent **think through every decision** — from intent parsing
to tool routing, effort selection, compression, and caching — step by step.
    """)

    intent = st.text_input(
        "What should the agent do?",
        value="Find all open bugs in composio and check if customers have reported them",
        key="live_intent",
    )

    use_live_api = st.toggle("Use Live Composio API (GitHub only)", value=False,
                              help=" Falls back to mock data if API fails or for non-GitHub tools.")
    enable_cache = st.toggle("Enable Cache", value=True, key="live_cache")

    if st.button("▶️  Run Live Agent", type="primary"):
        # -----------------------------------------------------------------
        # PHASE 0: Setup
        # -----------------------------------------------------------------
        from aperture.routing.semantic_selector import DynamicAgent, match_intent_to_tools
        from aperture.routing.intelligent_effort import select_effort
        from aperture.compression.engine import compress_tool_output
        from aperture.cache.interceptor import CachedExecutor
        from aperture.contracts import ApertureRunConfig, CompressionResult
        from aperture.tokenization import count_tokens
        from aperture.demo.scenarios import get_mock_result
        from aperture.schema_optimizer.auto_profile import ProfileRegistry

        AVAILABLE_TOOLS = [
            "GITHUB_GET_A_REPOSITORY", "GITHUB_LIST_ISSUES", "GITHUB_LIST_PULL_REQUESTS",
            "GITHUB_LIST_COMMITS", "GITHUB_GET_ISSUE", "GITHUB_GET_USER",
            "GMAIL_SEARCH_EMAILS", "GMAIL_FETCH_EMAILS",
            "SLACK_SEARCH_MESSAGES", "SLACK_LIST_CHANNELS", "SLACK_GET_CHANNEL",
            "GOOGLE_CALENDAR_LIST_EVENTS", "GOOGLE_CALENDAR_GET_EVENT",
            "HUBSPOT_GET_CONTACT", "HUBSPOT_LIST_CONTACTS",
            "ZENDESK_LIST_TICKETS", "ZENDESK_GET_TICKET",
            "SHOPIFY_LIST_PRODUCTS", "SHOPIFY_GET_ORDER",
            "NOTION_SEARCH_NOTION_PAGE", "LINEAR_GET_LINEAR_USER_ISSUES",
            "SUPABASE_FETCH_TABLE_ROWS",
        ]

        # Clear cache for fresh demo
        if enable_cache:
            try:
                from upstash_redis import Redis
                from aperture.config import Config
                r = Redis(url=Config.UPSTASH_REDIS_REST_URL, token=Config.UPSTASH_REDIS_REST_TOKEN)
                for k in r.keys("aperture:cache:*"):
                    r.delete(k)
            except Exception:
                pass

        cache = CachedExecutor()
        registry = ProfileRegistry()

        progress_bar = st.progress(0, text="Initializing...")
        log_container = st.container()

        def log(msg: str, icon: str = "", color: str = ""):
            with log_container:
                if color:
                    st.markdown(f"<span style='color:{color};'>{icon} {msg}</span>", unsafe_allow_html=True)
                else:
                    st.markdown(f"{icon} {msg}")

        # -----------------------------------------------------------------
        # PHASE 1: Intent Analysis
        # -----------------------------------------------------------------
        progress_bar.progress(5, text="Phase 1/5: Analyzing intent...")
        log("**Phase 1: Intent Analysis**", icon="🧠")

        from aperture.routing.semantic_selector import _extract_domain, _extract_verbs
        domains = _extract_domain(intent)
        verbs = _extract_verbs(intent)

        c1, c2, c3 = st.columns(3)
        with c1:
            st.metric("Domains Detected", len(domains))
            for d in domains:
                st.markdown(f"<span style='background:#dbeafe;color:#1e40af;padding:2px 8px;border-radius:12px;font-size:12px;'>{d.capitalize()}</span>", unsafe_allow_html=True)
        with c2:
            st.metric("Verbs Detected", len(verbs))
            for v in verbs:
                st.markdown(f"<span style='background:#ede9fe;color:#5b21b6;padding:2px 8px;border-radius:12px;font-size:12px;'>{v.capitalize()}</span>", unsafe_allow_html=True)
        with c3:
            st.metric("Query Length", len(intent.split()))

        time.sleep(0.4)

        # -----------------------------------------------------------------
        # PHASE 2: Semantic Routing
        # -----------------------------------------------------------------
        progress_bar.progress(20, text="Phase 2/5: Routing to tools...")
        log("**Phase 2: Semantic Routing**", icon="🗺️")

        matches = match_intent_to_tools(intent, AVAILABLE_TOOLS)
        top_matches = [m for m in matches if m.score > 0.05][:5]

        match_data = []
        for i, m in enumerate(top_matches):
            match_data.append({
                "Rank": i + 1,
                "Tool": m.tool_slug,
                "Score": f"{m.score:.2f}",
                "Effort": m.effort_mode,
                "Reasoning": m.reasoning[:60] + "..." if len(m.reasoning) > 60 else m.reasoning,
            })
        st.dataframe(match_data, width="stretch", hide_index=True)

        selected_tools = top_matches[:3]
        st.success(f"Selected top {len(selected_tools)} tools for execution")
        time.sleep(0.4)

        # -----------------------------------------------------------------
        # PHASE 3: Execution Plan
        # -----------------------------------------------------------------
        progress_bar.progress(35, text="Phase 3/5: Building execution plan...")
        log("**Phase 3: Execution Plan**", icon="📋")

        plan_cols = st.columns(len(selected_tools))
        for i, match in enumerate(selected_tools):
            with plan_cols[i]:
                st.markdown(f"**{i+1}. {match.tool_slug}**")
                st.caption(f"Score: {match.score:.2f}")
                if match.suggested_arguments:
                    st.json(match.suggested_arguments)
                else:
                    st.caption("No args suggested")

        time.sleep(0.4)

        # -----------------------------------------------------------------
        # PHASE 4: Step-by-Step Execution
        # -----------------------------------------------------------------
        progress_bar.progress(50, text="Phase 4/5: Executing tools...")
        log("**Phase 4: Live Execution**", icon="⚡")

        total_raw = 0
        total_comp = 0
        total_saved = 0
        step_results = []
        cumulative_context = []
        context_used = 0

        for step_idx, match in enumerate(selected_tools):
            step_container = st.container(border=True)

            with step_container:
                st.markdown(f"### Step {step_idx+1}: `{match.tool_slug}`")

                # ---- 4a: Effort Selection ----
                effort_col, exec_col, cache_col = st.columns(3)

                with effort_col:
                    st.markdown("🎯 **Effort Mode**")
                    decision = select_effort(
                        tool_slug=match.tool_slug,
                        arguments=match.suggested_arguments or {},
                        user_query=intent,
                        context_used=context_used,
                    )
                    st.markdown(f"<span style='background:#ffedd5;color:#9a3412;padding:2px 8px;border-radius:12px;font-size:12px;'>{decision.compression_mode.upper()}</span>", unsafe_allow_html=True)
                    st.caption(f"Confidence: {decision.confidence:.0%}")
                    with st.expander("Why this mode?"):
                        st.write(decision.reasoning)
                        st.json({
                            "complexity": decision.complexity.name,
                            "schema_depth": decision.schema_depth,
                            "estimated_savings": f"{decision.estimated_savings:,} tokens",
                            "critical_fields": decision.critical_fields[:5],
                        })

                # ---- 4b: Tool Execution ----
                with exec_col:
                    st.markdown("🔧 **Tool Call**")
                    st.code(f"{match.tool_slug}(\n  {match.suggested_arguments or {}}\n)", language="python")

                    # Try live API first if enabled and it's a GitHub tool
                    raw_result = None
                    if use_live_api and match.tool_slug.startswith("GITHUB"):
                        try:
                            import composio
                            c = composio.Composio()
                            session = c.create(
                                user_id="pg-test-77d7fa29-5fa4-4868-b9ba-39b07a17e2f6",
                                toolkits=["github"],
                                connected_accounts={"github": "ca_UZkzCbGtSDdE"},
                            )
                            raw_result = session.execute(
                                tool_slug=match.tool_slug,
                                arguments=match.suggested_arguments or {},
                            )
                            if hasattr(raw_result, "model_dump"):
                                raw_result = raw_result.model_dump()
                            st.caption("🟢 Live API")
                        except Exception as e:
                            st.caption(f"🔴 API failed: {e}")
                            raw_result = None

                    if raw_result is None:
                        raw_result = get_mock_result(match.tool_slug, match.suggested_arguments or {})
                        st.caption("🟡 Mock data")

                    raw_tc = count_tokens(raw_result)
                    st.metric("Raw Result", f"{raw_tc.tokens:,} tokens")
                    total_raw += raw_tc.tokens

                # ---- 4c: Cache + Compression ----
                with cache_col:
                    st.markdown("💾 **Cache & Compress**")

                    config = ApertureRunConfig(
                        run_id=f"live-{match.tool_slug}",
                        model="gpt-4o",
                        effort_mode="auto",
                        cache_bypass=not enable_cache,
                    )

                    def _executor():
                        return raw_result

                    cached_result, cache_event = cache.execute(
                        tool_slug=match.tool_slug,
                        arguments=match.suggested_arguments or {},
                        executor=_executor,
                        config=config,
                    )

                    if cache_event.cache_status == "hit":
                        st.markdown("<span style='background:#dcfce7;color:#166534;padding:2px 8px;border-radius:12px;font-size:12px;'>CACHE HIT</span>", unsafe_allow_html=True)
                        comp_result = CompressionResult(
                            compressed_payload=cached_result,
                            raw_tokens=0, compressed_tokens=0,
                            tokens_saved=0, compression_ratio=1.0,
                            strategy="cache_hit",
                        )
                    else:
                        st.markdown("<span style='background:#fee2e2;color:#991b1b;padding:2px 8px;border-radius:12px;font-size:12px;'>CACHE MISS</span>", unsafe_allow_html=True)
                        comp_result = compress_tool_output(
                            raw_payload=raw_result,
                            tool_slug=match.tool_slug,
                            mode=decision.compression_mode,
                            model="gpt-4o",
                        )
                        st.markdown(f"<span style='background:#ffedd5;color:#9a3412;padding:2px 8px;border-radius:12px;font-size:12px;'>{comp_result.strategy}</span>", unsafe_allow_html=True)

                    comp_tc = count_tokens(comp_result.compressed_payload)
                    st.metric("Compressed", f"{comp_tc.tokens:,} tokens")
                    saved = raw_tc.tokens - comp_tc.tokens
                    if saved > 0:
                        st.metric("Saved", f"{saved:,}", delta=f"-{saved/raw_tc.tokens:.0%}")
                    total_comp += comp_tc.tokens
                    total_saved += saved

                # ---- 4d: Preview ----
                preview_tab, summary_tab = st.tabs(["📄 Compressed Preview", "📊 Summary"])
                with preview_tab:
                    payload = comp_result.compressed_payload
                    if isinstance(payload, dict) and "sample" in payload:
                        sample = payload["sample"]
                        st.json(sample[0] if sample else {})
                        st.caption(f"Showing 1 of {len(sample)} sampled records")
                    elif isinstance(payload, dict):
                        st.json({k: v for k, v in list(payload.items())[:8]})
                    else:
                        st.json(payload)

                with summary_tab:
                    if isinstance(payload, dict):
                        summary = payload.get("_aperture_summary", {})
                        stats = payload.get("stats", {})
                        st.json({"summary": summary, "stats": stats})
                    else:
                        st.json({"type": type(payload).__name__, "length": len(str(payload))})

                # Update cumulative context
                cumulative_context.append({"tool": match.tool_slug, "result": comp_result.compressed_payload})
                context_used = count_tokens(cumulative_context).tokens
                st.progress(min(context_used / 128_000, 1.0),
                            text=f"Cumulative context: {context_used:,} / 128,000 tokens ({context_used/128_000*100:.1f}%)")

                step_results.append({
                    "tool": match.tool_slug,
                    "raw": raw_tc.tokens,
                    "compressed": comp_tc.tokens,
                    "saved": saved,
                    "cache": cache_event.cache_status,
                    "mode": decision.compression_mode,
                })

                # Small pause for visual effect
                time.sleep(0.3)

            progress_pct = 50 + ((step_idx + 1) / len(selected_tools)) * 40
            progress_bar.progress(int(progress_pct), text=f"Step {step_idx+1}/{len(selected_tools)} complete...")

        # -----------------------------------------------------------------
        # PHASE 5: Final Summary
        # -----------------------------------------------------------------
        progress_bar.progress(100, text="Complete!")
        log("**Phase 5: Final Summary**", icon="🏁")

        summary_container = st.container()
        with summary_container:
            st.subheader("📈 Workflow Summary")

            sc1, sc2, sc3, sc4, sc5 = st.columns(5)
            with sc1:
                st.metric("Tools Called", len(selected_tools))
            with sc2:
                st.metric("Total Raw", f"{total_raw:,}")
            with sc3:
                st.metric("Total Compressed", f"{total_comp:,}")
            with sc4:
                savings_pct = total_saved / total_raw if total_raw > 0 else 0
                st.metric("Tokens Saved", f"{total_saved:,}", delta=f"-{savings_pct:.0%}")
            with sc5:
                cache_hits = sum(1 for s in step_results if s["cache"] == "hit")
                st.metric("Cache Hits", f"{cache_hits}/{len(selected_tools)}")

            # Context window comparison
            st.subheader("🌊 Context Window Pressure")
            vanilla_ctx = total_raw  # Approximate: each tool result added raw
            opt_ctx = context_used

            vc1, vc2 = st.columns(2)
            with vc1:
                st.error("Without Aperture")
                st.progress(min(vanilla_ctx / 128_000, 1.0),
                           text=f"{vanilla_ctx:,} tokens ({vanilla_ctx/128_000*100:.1f}%)")
                st.caption("Every raw tool result stacks in the context window")
            with vc2:
                st.success("With Aperture")
                st.progress(min(opt_ctx / 128_000, 1.0),
                           text=f"{opt_ctx:,} tokens ({opt_ctx/128_000*100:.1f}%)")
                st.caption("Compressed results + cache = minimal pressure")

            # Cost estimate
            raw_cost = total_raw / 1_000_000 * 2.50  # GPT-4o input
            opt_cost = total_comp / 1_000_000 * 2.50
            st.info(f"💰 Estimated cost: **${raw_cost:.3f}** → **${opt_cost:.3f}** (saves ${raw_cost - opt_cost:.3f})")

            # Step table
            st.subheader("Per-Step Breakdown")
            st.dataframe(step_results, width="stretch", hide_index=True)

            # Cache re-run button
            if enable_cache and cache_hits < len(selected_tools):
                if st.button("🔄 Run Again (Test Cache)", key="live_cache_rerun"):
                    rerun_results = []
                    for match in selected_tools:
                        def _re_executor():
                            return get_mock_result(match.tool_slug, match.suggested_arguments or {})
                        _, cache_event2 = cache.execute(
                            tool_slug=match.tool_slug,
                            arguments=match.suggested_arguments or {},
                            executor=_re_executor,
                            config=config,
                        )
                        rerun_results.append(cache_event2.cache_status)

                    rerun_hits = sum(1 for r in rerun_results if r == "hit")
                    if rerun_hits > 0:
                        st.success(f"✅ {rerun_hits}/{len(selected_tools)} steps served from cache — zero API calls!")
                    else:
                        st.error("❌ Cache miss (cache may have expired or been cleared)")


# =============================================================================
# TAB 6: BENCHMARKS
# =============================================================================
with tab_benchmarks:
    st.header("📈 Benchmark Suite")

    st.markdown("""
    Comparing **vanilla Composio** (no Aperture) vs **Aperture modes** across all scenarios.
    """)

    if st.button("🏃 Run Full Benchmark Suite", type="primary"):
        from aperture.benchmarks.harness import run_full_benchmark

        with st.spinner("Running 15 benchmarks (5 modes × 3 scenarios)..."):
            results = run_full_benchmark(
                modes=["off", "low", "medium", "high", "auto"],
                scenarios=list(SCENARIOS.keys()),
            )

        for scenario in SCENARIOS.keys():
            st.subheader(f"📁 {scenario.replace('_', ' ').title()}")

            table_data = []
            for mode in ["off", "low", "medium", "high", "auto"]:
                bench = next(b for b in results[mode] if b.scenario_name == scenario)
                saved = bench.total_tokens_saved
                ratio = saved / bench.total_vanilla_tokens if bench.total_vanilla_tokens > 0 else 0

                table_data.append({
                    "Mode": mode,
                    "Raw": f"{bench.total_vanilla_tokens:,}",
                    "Compressed": f"{bench.total_aperture_tokens:,}",
                    "Saved": f"{saved:,}",
                    "Savings": f"{ratio:.1%}",
                    "Context": f"{bench.context_window_aperture:,}",
                    "Cache Hits": bench.cache_hits,
                    "Quality": f"{bench.avg_quality_score:.0%}",
                })

            st.dataframe(table_data, width="stretch", hide_index=True)

        # Winners
        st.subheader("🏆 Best Mode Per Scenario")
        for scenario in SCENARIOS.keys():
            best_mode = None
            best_savings = -1
            for mode in ["low", "medium", "high", "auto"]:
                bench = next(b for b in results[mode] if b.scenario_name == scenario)
                if bench.total_tokens_saved > best_savings:
                    best_savings = bench.total_tokens_saved
                    best_mode = mode

            bench = next(b for b in results[best_mode] if b.scenario_name == scenario)
            ratio = best_savings / bench.total_vanilla_tokens if bench.total_vanilla_tokens > 0 else 0
            st.success(f"**{scenario.replace('_', ' ').title()}:** {best_mode} mode — {ratio:.1%} savings ({best_savings:,} tokens)")

    else:
        st.info("Click **Run Full Benchmark Suite** to see all comparisons.")

        # Show cached results from a typical run
        st.subheader("Typical Results (Cached)")
        cached_results = [
            {"Scenario": "Research Project", "Best Mode": "low / auto", "Savings": "80.7%", "Tokens Saved": "20,444"},
            {"Scenario": "Triage Bugs", "Best Mode": "low / auto", "Savings": "71.0%", "Tokens Saved": "8,027"},
            {"Scenario": "Onboard User", "Best Mode": "medium", "Savings": "75.7%", "Tokens Saved": "5,863"},
        ]
        st.dataframe(cached_results, width="stretch", hide_index=True)
