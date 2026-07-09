"""
tracker.py
----------
Orchestrates the whole run:
  1. Read config.yaml
  2. For every (provider x query) combination, call the LLM
  3. Run citation detection on the response
  4. Write a raw results CSV (one row per provider+query)
  5. Write a scorecard CSV (one row per provider, aggregated)
"""

import csv
import os
import time
from datetime import datetime

import yaml

from citation_tracker.detector import analyze_response
from citation_tracker.providers import PROVIDER_FUNCTIONS, get_api_key


def load_config(path: str = "config.yaml") -> dict:
    with open(path, "r") as f:
        return yaml.safe_load(f)


def run(config_path: str = "config.yaml", output_dir: str = "reports", sleep_between_calls: float = 3.0):
    """CLI entry point — reads config.yaml from disk, then delegates to run_from_config."""
    config = load_config(config_path)
    return run_from_config(config, output_dir=output_dir, sleep_between_calls=sleep_between_calls)


def run_from_config(config: dict, output_dir: str = "reports", sleep_between_calls: float = 3.0,
                     progress_callback=None):
    """
    Same pipeline as run(), but takes a config dict directly instead of a
    file path. Lets a UI (dashboard, notebook, etc.) build the config in
    memory — brand, competitors, queries, providers, models — without ever
    writing config.yaml to disk.

    progress_callback(provider, query, row_dict) is called after each
    query completes, so a live dashboard can stream results in as they
    arrive instead of waiting for the whole run to finish.
    """
    brand_name = config["brand"]["name"]
    brand_aliases = config["brand"].get("aliases", [])
    competitors = config.get("competitors", [])
    queries = config["queries"]
    providers_enabled = config.get("providers", {})
    models = config.get("models", {})

    os.makedirs(output_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    raw_path = os.path.join(output_dir, f"raw_results_{timestamp}.csv")
    scorecard_path = os.path.join(output_dir, f"scorecard_{timestamp}.csv")

    raw_rows = []
    skipped_providers = []

    for provider_name, enabled in providers_enabled.items():
        if not enabled:
            continue
        api_key = get_api_key(provider_name)
        if not api_key:
            skipped_providers.append(provider_name)
            print(f"[skip] {provider_name}: no API key found in .env — skipping.")
            continue

        query_fn = PROVIDER_FUNCTIONS[provider_name]
        model = models.get(provider_name, "")

        for query in queries:
            print(f"[query] {provider_name} <- \"{query}\"")
            try:
                response_text = query_fn(query, model, api_key)
            except Exception as e:
                print(f"  [error] {provider_name} failed on \"{query}\": {e}")
                error_row = {
                    "timestamp": timestamp,
                    "provider": provider_name,
                    "query": query,
                    "brand_mentioned": "ERROR",
                    "mention_count": "",
                    "first_position_pct": "",
                    "competitors_mentioned": "",
                    "snippet": str(e)[:200],
                    "response_length_chars": "",
                }
                raw_rows.append(error_row)
                if progress_callback:
                    progress_callback(provider_name, query, error_row)
                continue

            analysis = analyze_response(response_text, brand_name, brand_aliases, competitors)
            row = {
                "timestamp": timestamp,
                "provider": provider_name,
                "query": query,
                **analysis,
            }
            raw_rows.append(row)
            if progress_callback:
                progress_callback(provider_name, query, row)

            time.sleep(sleep_between_calls)  # be polite to rate limits

    _write_raw_csv(raw_path, raw_rows)
    _write_scorecard_csv(scorecard_path, raw_rows, providers_enabled)

    print("\n=== DONE ===")
    print(f"Raw results:  {raw_path}")
    print(f"Scorecard:    {scorecard_path}")
    if skipped_providers:
        print(f"Skipped (no API key): {', '.join(skipped_providers)}")

    return raw_path, scorecard_path


def _write_raw_csv(path: str, rows: list):
    fieldnames = [
        "timestamp", "provider", "query", "brand_mentioned", "mention_count",
        "first_position_pct", "competitors_mentioned", "snippet", "response_length_chars",
    ]
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def _write_scorecard_csv(path: str, rows: list, providers_enabled: dict):
    fieldnames = [
        "provider", "queries_tested", "times_cited", "citation_rate_pct",
        "avg_first_position_pct", "top_competitors_seen",
    ]
    scorecard_rows = []

    for provider_name in providers_enabled:
        provider_rows = [r for r in rows if r["provider"] == provider_name and r["brand_mentioned"] != "ERROR"]
        if not provider_rows:
            continue

        queries_tested = len(provider_rows)
        cited_rows = [r for r in provider_rows if r["brand_mentioned"] is True]
        times_cited = len(cited_rows)
        citation_rate = round((times_cited / queries_tested) * 100, 1) if queries_tested else 0

        positions = [r["first_position_pct"] for r in cited_rows if r["first_position_pct"] is not None]
        avg_position = round(sum(positions) / len(positions), 1) if positions else ""

        competitor_mentions = {}
        for r in provider_rows:
            comps = r.get("competitors_mentioned", "")
            if comps:
                for c in comps.split(", "):
                    competitor_mentions[c] = competitor_mentions.get(c, 0) + 1
        top_competitors = ", ".join(
            f"{name} ({count})" for name, count in sorted(competitor_mentions.items(), key=lambda x: -x[1])[:3]
        )

        scorecard_rows.append({
            "provider": provider_name,
            "queries_tested": queries_tested,
            "times_cited": times_cited,
            "citation_rate_pct": citation_rate,
            "avg_first_position_pct": avg_position,
            "top_competitors_seen": top_competitors,
        })

    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in scorecard_rows:
            writer.writerow(row)
