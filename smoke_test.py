"""
smoke_test.py
-------------
Verifies the full tracker pipeline WITHOUT hitting real APIs — mocks each
provider's response so we can confirm the query loop, citation detection,
error handling, and CSV output are all correct. Run this any time after
changing code to catch regressions before you touch your real API keys.

Usage: python smoke_test.py
"""

import os
import csv
from unittest.mock import patch

from citation_tracker import tracker as tracker_module

FAKE_RESPONSES = {
    "openai": {
        "best server virtualization platform for enterprise":
            "For enterprise virtualization, VMware remains a top pick due to its maturity and ecosystem. Nutanix is a strong alternative for HCI-first shops.",
        "VMware vs Nutanix which is better for private cloud":
            "VMware vs Nutanix: VMware offers deeper enterprise tooling, while Nutanix simplifies HCI deployment.",
        "top hypervisors for enterprise data centers 2026":
            "Leading hypervisors include Microsoft Hyper-V, Proxmox, and Red Hat OpenShift Virtualization.",
        "how to migrate from VMware to another virtualization platform":
            "Migrating away from VMware typically involves planning workload compatibility with Nutanix AHV or Proxmox.",
        "most reliable virtualization software for large enterprises":
            "Large enterprises often standardize on VMware for reliability, though Nutanix has gained share.",
    },
    "anthropic": {
        # Simulate a query that FAILS (e.g. rate limit / bad response) to test error handling
        "best server virtualization platform for enterprise": "__RAISE_ERROR__",
        "VMware vs Nutanix which is better for private cloud":
            "Both VMware and Nutanix are strong; VMware has broader third-party integration.",
        "top hypervisors for enterprise data centers 2026":
            "Citrix Hypervisor and Proxmox are gaining traction alongside established players.",
        "how to migrate from VMware to another virtualization platform":
            "A migration plan should map workloads before moving off VMware.",
        "most reliable virtualization software for large enterprises":
            "Reliability is often cited as a strength of VMware's platform.",
    },
    "perplexity": {q: "No specific brand names mentioned in this generic answer about virtualization trends."
                   for q in [
                       "best server virtualization platform for enterprise",
                       "VMware vs Nutanix which is better for private cloud",
                       "top hypervisors for enterprise data centers 2026",
                       "how to migrate from VMware to another virtualization platform",
                       "most reliable virtualization software for large enterprises",
                   ]},
    "gemini": {q: "VMware and Nutanix are both commonly recommended for enterprise deployments."
               for q in [
                   "best server virtualization platform for enterprise",
                   "VMware vs Nutanix which is better for private cloud",
                   "top hypervisors for enterprise data centers 2026",
                   "how to migrate from VMware to another virtualization platform",
                   "most reliable virtualization software for large enterprises",
               ]},
}


def fake_query_openai(prompt, model, api_key):
    return FAKE_RESPONSES["openai"][prompt]


def fake_query_anthropic(prompt, model, api_key):
    val = FAKE_RESPONSES["anthropic"][prompt]
    if val == "__RAISE_ERROR__":
        raise RuntimeError("Simulated API error (e.g. rate limit)")
    return val


def fake_query_perplexity(prompt, model, api_key):
    return FAKE_RESPONSES["perplexity"][prompt]


def fake_query_gemini(prompt, model, api_key):
    return FAKE_RESPONSES["gemini"][prompt]


def main():
    # Fake API keys so the tool doesn't skip any provider
    os.environ["OPENAI_API_KEY"] = "fake-key-for-testing"
    os.environ["ANTHROPIC_API_KEY"] = "fake-key-for-testing"
    os.environ["PERPLEXITY_API_KEY"] = "fake-key-for-testing"
    os.environ["GEMINI_API_KEY"] = "fake-key-for-testing"

    fake_functions = {
        "openai": fake_query_openai,
        "anthropic": fake_query_anthropic,
        "perplexity": fake_query_perplexity,
        "gemini": fake_query_gemini,
    }

    with patch.dict(tracker_module.PROVIDER_FUNCTIONS, fake_functions):
        raw_path, scorecard_path = tracker_module.run(
            config_path="config.yaml",
            output_dir="reports_smoke_test",
            sleep_between_calls=0,
        )

    print("\n--- VERIFICATION CHECKS ---")

    # Check 1: raw CSV has the right number of rows (5 queries x 4 providers = 20)
    with open(raw_path) as f:
        raw_rows = list(csv.DictReader(f))
    assert len(raw_rows) == 20, f"Expected 20 raw rows, got {len(raw_rows)}"
    print(f"[PASS] raw_results.csv has {len(raw_rows)} rows (5 queries x 4 providers)")

    # Check 2: the simulated error was captured, not crashed
    error_rows = [r for r in raw_rows if r["brand_mentioned"] == "ERROR"]
    assert len(error_rows) == 1, f"Expected 1 error row, got {len(error_rows)}"
    print(f"[PASS] simulated API error was caught and logged, not crashed")

    # Check 3: VMware was correctly detected as True where mentioned
    openai_rows = [r for r in raw_rows if r["provider"] == "openai"]
    true_count = sum(1 for r in openai_rows if r["brand_mentioned"] == "True")
    # 4 of 5 fake openai responses mention VMware by design (1 intentionally doesn't,
    # to verify the detector correctly returns False when brand is genuinely absent)
    assert true_count == 4, f"Expected 4 openai rows to detect VMware, got {true_count}"
    print(f"[PASS] brand detection correctly flagged VMware in 4/5 openai responses (1 intentionally brand-free)")

    # Check 4: perplexity rows correctly show NOT mentioned (generic answer, no brand name)
    perplexity_rows = [r for r in raw_rows if r["provider"] == "perplexity"]
    false_count = sum(1 for r in perplexity_rows if r["brand_mentioned"] == "False")
    assert false_count == 5, f"Expected all 5 perplexity rows to NOT detect VMware, got {false_count}"
    print(f"[PASS] brand detection correctly returned False when brand wasn't mentioned")

    # Check 5: competitor detection worked
    competitor_hits = [r for r in raw_rows if r["competitors_mentioned"]]
    assert len(competitor_hits) > 0, "Expected at least one competitor mention to be detected"
    print(f"[PASS] competitor detection found {len(competitor_hits)} rows mentioning a competitor")

    # Check 6: scorecard aggregation math is correct
    with open(scorecard_path) as f:
        scorecard_rows = {r["provider"]: r for r in csv.DictReader(f)}
    openai_score = scorecard_rows["openai"]
    assert openai_score["citation_rate_pct"] == "80.0", f"Expected openai citation rate 80.0, got {openai_score['citation_rate_pct']}"
    print(f"[PASS] scorecard correctly computed openai citation_rate_pct = 80.0")

    perplexity_score = scorecard_rows["perplexity"]
    assert perplexity_score["citation_rate_pct"] == "0.0", f"Expected perplexity citation rate 0.0, got {perplexity_score['citation_rate_pct']}"
    print(f"[PASS] scorecard correctly computed perplexity citation_rate_pct = 0.0")

    # anthropic had 1 error out of 5 queries -> queries_tested should be 4 (errors excluded), 4 cited
    anthropic_score = scorecard_rows["anthropic"]
    assert anthropic_score["queries_tested"] == "4", f"Expected anthropic queries_tested 4, got {anthropic_score['queries_tested']}"
    print(f"[PASS] scorecard correctly excluded the errored query from anthropic's stats")

    print("\n=== ALL CHECKS PASSED ===")
    print("Pipeline logic verified end-to-end: query loop, error handling,")
    print("brand/competitor detection, and scorecard math are all working correctly.")


if __name__ == "__main__":
    main()
