"""
dashboard.py
------------
A local web dashboard for the AI Citation Tracker — configure brand,
competitors, queries, providers, and API keys entirely through the UI,
run the tracker, and see results as an AI-visibility-style report
(overview metrics, provider breakdown, competitor share-of-voice,
trend over time, query-level detail). No config.yaml or .env file
editing required.

Run with:
    streamlit run dashboard.py
"""

import glob
import os
import sys

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

load_dotenv()  # pre-fill key fields if a .env already exists

from citation_tracker.tracker import run_from_config
from citation_tracker.providers import PROVIDER_ENV_KEYS

st.set_page_config(page_title="AI Citation Tracker", layout="wide", page_icon="🔍")

PROVIDER_LABELS = {
    "openai": "ChatGPT (OpenAI)",
    "anthropic": "Claude (Anthropic)",
    "perplexity": "Perplexity",
    "gemini": "Gemini (Google)",
    "groq": "Groq",
    "openrouter": "OpenRouter",
}

TESTING_ONLY = {"groq", "openrouter"}

DEFAULT_MODELS = {
    "openai": "gpt-4o-mini",
    "anthropic": "claude-3-5-haiku-20241022",
    "perplexity": "sonar",
    "gemini": "gemini-2.0-flash",
    "groq": "llama-3.3-70b-versatile",
    "openrouter": "meta-llama/llama-3.1-8b-instruct:free",
}

if "raw_rows" not in st.session_state:
    st.session_state.raw_rows = []
if "brand_name" not in st.session_state:
    st.session_state.brand_name = "VMware"

st.title("🔍 AI Citation Tracker")
st.caption("Track brand visibility across ChatGPT, Claude, Perplexity, Gemini and more — configure, run, and read results all from this dashboard.")

# ---------------------------------------------------------------------
# Sidebar: API keys
# ---------------------------------------------------------------------
with st.sidebar:
    st.header("🔑 API Keys")
    st.caption("Kept in memory for this session only, unless you save them below.")

    save_keys = st.checkbox("Remember keys in a local .env file", value=False,
                             help="Writes keys to .env in this folder so you don't retype them next time. Leave unchecked to keep keys in-memory only.")

    api_keys = {}
    for provider, env_var in PROVIDER_ENV_KEYS.items():
        existing = os.environ.get(env_var, "")
        api_keys[provider] = st.text_input(
            PROVIDER_LABELS[provider], value=existing, type="password", key=f"key_{provider}",
        )

    if st.button("Apply keys", use_container_width=True):
        for provider, key in api_keys.items():
            if key:
                os.environ[PROVIDER_ENV_KEYS[provider]] = key
        if save_keys:
            lines = [f"{PROVIDER_ENV_KEYS[p]}={k}" for p, k in api_keys.items() if k]
            with open(".env", "w") as f:
                f.write("\n".join(lines) + "\n")
            st.success("Keys applied and saved to .env")
        else:
            st.success("Keys applied for this session")

    st.divider()
    st.caption("⚠️ Groq / OpenRouter mostly serve open-source models — free for pipeline testing, but not real consumer AI-search products. Treat their citation rate as a sanity check, not a client-facing metric.")

st.divider()

# ---------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------
col1, col2 = st.columns(2)

with col1:
    st.subheader("Brand")
    brand_name = st.text_input("Brand name", value=st.session_state.brand_name)
    brand_aliases_raw = st.text_area(
        "Aliases (one per line)",
        value="VMware by Broadcom\nvSphere\nVMware Cloud",
        height=90,
    )
    brand_aliases = [a.strip() for a in brand_aliases_raw.splitlines() if a.strip()]

    st.subheader("Competitors")
    competitors_raw = st.text_area(
        "Competitors (one per line)",
        value="Nutanix\nMicrosoft Hyper-V\nProxmox\nRed Hat OpenShift Virtualization\nCitrix Hypervisor",
        height=110,
    )
    competitors = [c.strip() for c in competitors_raw.splitlines() if c.strip()]

with col2:
    st.subheader("Queries")
    queries_raw = st.text_area(
        "Queries to test (one per line)",
        value=(
            "best server virtualization platform for enterprise\n"
            "VMware vs Nutanix which is better for private cloud\n"
            "top hypervisors for enterprise data centers 2026\n"
            "how to migrate from VMware to another virtualization platform\n"
            "most reliable virtualization software for large enterprises"
        ),
        height=245,
    )
    queries = [q.strip() for q in queries_raw.splitlines() if q.strip()]

st.divider()

st.subheader("Providers to test")
provider_cols = st.columns(len(PROVIDER_LABELS))
providers_enabled = {}
models = {}

for i, (provider, label) in enumerate(PROVIDER_LABELS.items()):
    with provider_cols[i]:
        has_key = bool(api_keys.get(provider) or os.environ.get(PROVIDER_ENV_KEYS[provider]))
        checked = st.checkbox(label, value=has_key, key=f"enable_{provider}")
        providers_enabled[provider] = checked
        models[provider] = st.text_input(
            "Model", value=DEFAULT_MODELS[provider], key=f"model_{provider}",
            label_visibility="collapsed",
        )
        if provider in TESTING_ONLY:
            st.caption("⚠️ testing only")

st.divider()

sleep_between_calls = st.slider(
    "Delay between calls (seconds) — increase if you hit rate limits",
    min_value=0.0, max_value=10.0, value=3.0, step=0.5,
)

run_clicked = st.button("▶️ Run Citation Check", type="primary", use_container_width=True)

# ---------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------
if run_clicked:
    if not brand_name.strip():
        st.error("Enter a brand name first.")
    elif not queries:
        st.error("Add at least one query.")
    elif not any(providers_enabled.values()):
        st.error("Enable at least one provider.")
    else:
        st.session_state.brand_name = brand_name
        config = {
            "brand": {"name": brand_name, "aliases": brand_aliases},
            "competitors": competitors,
            "queries": queries,
            "providers": providers_enabled,
            "models": models,
        }

        st.session_state.raw_rows = []

        progress_area = st.empty()
        table_area = st.empty()
        total = sum(len(queries) for p, en in providers_enabled.items() if en)
        counter = {"done": 0}

        def on_progress(provider, query, row):
            counter["done"] += 1
            progress_area.progress(
                counter["done"] / total,
                text=f"[{counter['done']}/{total}] {provider} ← \"{query[:60]}\"",
            )
            st.session_state.raw_rows.append(row)
            table_area.dataframe(pd.DataFrame(st.session_state.raw_rows), use_container_width=True, height=200)

        with st.spinner("Running..."):
            run_from_config(
                config, output_dir="reports", sleep_between_calls=sleep_between_calls,
                progress_callback=on_progress,
            )

        progress_area.empty()
        table_area.empty()
        st.success("Done! See the report below.")

# ---------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------
if st.session_state.raw_rows:
    df = pd.DataFrame(st.session_state.raw_rows)
    valid = df[df["brand_mentioned"] != "ERROR"].copy()
    valid["brand_mentioned"] = valid["brand_mentioned"].astype(bool)

    st.divider()
    st.header(f"📊 AI Visibility Report — {st.session_state.brand_name}")

    # --- Overview metric cards (Semrush-style) ---
    total_queries = len(valid)
    total_citations = int(valid["brand_mentioned"].sum())
    overall_rate = round((total_citations / total_queries) * 100, 1) if total_queries else 0
    positions = valid.loc[valid["brand_mentioned"], "first_position_pct"].dropna()
    avg_position = round(positions.mean(), 1) if len(positions) else None
    error_count = int((df["brand_mentioned"] == "ERROR").sum())

    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("AI Visibility", f"{overall_rate}%", help="Share of tested queries where your brand was cited, across all enabled providers.")
    m2.metric("Queries Tested", total_queries)
    m3.metric("Times Cited", total_citations)
    m4.metric("Avg. First Position", f"{avg_position}%" if avg_position is not None else "—",
               help="How early the brand appears in the response, as % through the text (lower = earlier/more prominent).")
    m5.metric("Errors", error_count, delta=None if error_count == 0 else "check Errors tab", delta_color="inverse")

    tab_overview, tab_queries, tab_competitors, tab_trend, tab_raw, tab_errors = st.tabs(
        ["Overview", "Query Breakdown", "Competitors", "Trend", "Raw Data", "Errors"]
    )

    # --- Overview: citation rate by provider ---
    with tab_overview:
        if not valid.empty:
            scorecard = (
                valid.groupby("provider")
                .agg(queries_tested=("query", "count"), times_cited=("brand_mentioned", "sum"))
                .reset_index()
            )
            scorecard["citation_rate_pct"] = (
                scorecard["times_cited"] / scorecard["queries_tested"] * 100
            ).round(1)

            c1, c2 = st.columns(2)
            with c1:
                st.subheader("Citation rate by provider")
                st.bar_chart(scorecard.set_index("provider")["citation_rate_pct"])
            with c2:
                st.subheader("Queries tested per provider")
                st.bar_chart(scorecard.set_index("provider")["queries_tested"])

            st.subheader("Scorecard")
            st.dataframe(scorecard.rename(columns={
                "provider": "Provider", "queries_tested": "Queries Tested",
                "times_cited": "Times Cited", "citation_rate_pct": "Citation Rate %",
            }), use_container_width=True, hide_index=True)
        else:
            st.info("No successful queries yet — run a check above.")

    # --- Query-level breakdown, sortable/filterable ---
    with tab_queries:
        if not valid.empty:
            fc1, fc2 = st.columns(2)
            with fc1:
                provider_filter = st.multiselect(
                    "Filter by provider", options=sorted(valid["provider"].unique()),
                    default=sorted(valid["provider"].unique()),
                )
            with fc2:
                cited_filter = st.selectbox("Filter by citation", ["All", "Cited only", "Not cited only"])

            view = valid[valid["provider"].isin(provider_filter)]
            if cited_filter == "Cited only":
                view = view[view["brand_mentioned"]]
            elif cited_filter == "Not cited only":
                view = view[~view["brand_mentioned"]]

            st.dataframe(
                view[["provider", "query", "brand_mentioned", "mention_count",
                      "first_position_pct", "competitors_mentioned", "response_length_chars"]]
                .rename(columns={
                    "provider": "Provider", "query": "Query", "brand_mentioned": "Cited",
                    "mention_count": "Mentions", "first_position_pct": "First Position %",
                    "competitors_mentioned": "Competitors Mentioned", "response_length_chars": "Response Length",
                }),
                use_container_width=True, hide_index=True,
            )
        else:
            st.info("No successful queries yet.")

    # --- Competitor share of voice ---
    with tab_competitors:
        if not valid.empty:
            comp_counts = {}
            for comps in valid["competitors_mentioned"].dropna():
                if comps:
                    for c in str(comps).split(", "):
                        comp_counts[c] = comp_counts.get(c, 0) + 1
            if comp_counts:
                comp_df = pd.DataFrame(
                    sorted(comp_counts.items(), key=lambda x: -x[1]), columns=["Competitor", "Mentions"]
                )
                c1, c2 = st.columns([2, 1])
                with c1:
                    st.subheader("Competitor mentions")
                    st.bar_chart(comp_df.set_index("Competitor")["Mentions"])
                with c2:
                    st.subheader("Share of voice")
                    total_mentions = comp_df["Mentions"].sum() + total_citations
                    sov = pd.DataFrame({
                        "Entity": [st.session_state.brand_name] + comp_df["Competitor"].tolist(),
                        "Mentions": [total_citations] + comp_df["Mentions"].tolist(),
                    })
                    sov["Share %"] = (sov["Mentions"] / total_mentions * 100).round(1)
                    st.dataframe(sov, use_container_width=True, hide_index=True)
            else:
                st.info("No competitor mentions found in this run.")
        else:
            st.info("No successful queries yet.")

    # --- Trend over time, reading past scorecard CSVs from reports/ ---
    with tab_trend:
        scorecard_files = sorted(glob.glob(os.path.join("reports", "scorecard_*.csv")))
        if len(scorecard_files) >= 2:
            trend_rows = []
            for f in scorecard_files:
                ts = os.path.basename(f).replace("scorecard_", "").replace(".csv", "")
                try:
                    sc = pd.read_csv(f)
                    sc["run_timestamp"] = ts
                    trend_rows.append(sc)
                except Exception:
                    continue
            if trend_rows:
                trend_df = pd.concat(trend_rows, ignore_index=True)
                pivot = trend_df.pivot_table(
                    index="run_timestamp", columns="provider", values="citation_rate_pct", aggfunc="mean"
                )
                st.subheader("Citation rate over time, by provider")
                st.line_chart(pivot)
                st.caption("Built from every scorecard_*.csv saved in reports/ — run the check periodically (e.g. weekly) to build up this trend.")
            else:
                st.info("Couldn't read past scorecard files.")
        else:
            st.info("Run at least 2 checks (on different days) to see a trend line here — this reads all past scorecard_*.csv files in reports/.")

    # --- Raw data ---
    with tab_raw:
        st.dataframe(df, use_container_width=True)
        st.download_button(
            "Download raw_results.csv", df.to_csv(index=False),
            file_name="raw_results.csv", mime="text/csv",
        )

    # --- Errors ---
    with tab_errors:
        errors = df[df["brand_mentioned"] == "ERROR"]
        if errors.empty:
            st.success("No errors 🎉")
        else:
            st.dataframe(errors[["provider", "query", "snippet"]], use_container_width=True, hide_index=True)
