# AI Citation Tracker

Tracks whether your brand gets **cited/mentioned by AI platforms** (ChatGPT, Claude, Perplexity, Gemini) when people ask relevant questions — and which competitors show up instead. Built for GEO (Generative Engine Optimization) work: this is the "rank tracker" equivalent for the AI-search era.

Output: two CSV files per run —
- **raw_results.csv** — every query x provider combination, with mention count, position, snippet
- **scorecard.csv** — aggregated citation rate per provider, so you can say "we're cited in 60% of Perplexity answers but 0% of ChatGPT answers"

---

## 1. What you need before starting

You need at least **one** API key (you don't need all of them — the tool skips any provider without a key and tells you).

| Provider | Where to get a key | Free tier? |
|---|---|---|
| OpenAI (ChatGPT) | https://platform.openai.com/api-keys | No — pay-per-use, very cheap for this (~$0.01 per run) |
| Anthropic (Claude) | https://console.anthropic.com/settings/keys | Small free credit for new accounts |
| Perplexity | https://www.perplexity.ai/settings/api | No — pay-per-use |
| Google (Gemini) | https://aistudio.google.com/apikey | Yes — generous free tier |
| Groq | https://console.groq.com | Yes — free, but open-source models only (testing, not a real AI-search product) |
| OpenRouter | https://openrouter.ai | Only `:free`-suffixed models are free; others cost the same as calling the provider directly |

**Recommendation for a demo/portfolio run:** start with just **Gemini** and **Groq** (both free) to validate the whole pipeline at zero cost, then add OpenAI/Anthropic/Perplexity once you're happy with the output — those are the ones that reflect real AI-search citation behavior.

You'll also need **Python 3.10+** installed on your machine. Check with:
```bash
python3 --version
```

---

## 2. Setup (one-time)

```bash
# 1. Unzip / move into the project folder
cd ai-citation-tracker

# 2. Create a virtual environment (keeps this project's packages separate)
python3 -m venv venv
source venv/bin/activate        # on Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Set up your API keys
cp .env.example .env
# Now open .env in any text editor and paste in your real API keys
```

---

## 3. Configure what you're tracking

Open **`config.yaml`** and edit:

1. **`brand.name`** and **`brand.aliases`** — your brand and any common variations
2. **`competitors`** — brands you want to see if AI mentions instead of you
3. **`queries`** — the actual questions to test. Write these the way a real buyer would type them into ChatGPT — comparison queries ("X vs Y") and "best X for Y" queries are where AI platforms most often name specific brands.
4. **`providers`** — set `true`/`false` for which platforms to query (skip ones you don't have a key for)

The file already ships with a working example (VMware vs virtualization competitors) so you can test the tool immediately, then swap in your own brand.

---

## 4. Run it — Dashboard (recommended)

The easiest way to use this tool: a local web dashboard where you set the
brand, competitors, queries, providers, and API keys — and see the report —
all in the browser, without touching `config.yaml` or `.env`.

```bash
streamlit run dashboard.py
```

This opens `http://localhost:8501` in your browser. From there:

1. **Sidebar** — paste in whichever API keys you have. Kept in-memory for
   the session by default; tick "Remember keys in a local .env file" to
   persist them between runs.
2. Edit **brand / aliases / competitors / queries** directly in the text areas.
3. Tick which **providers** to run and adjust model names if needed.
4. Click **Run Citation Check** — results stream in live, then a full
   report appears below:
   - **Overview** — AI Visibility % (overall citation rate), queries
     tested, times cited, avg. first position, plus a citation-rate-by-
     provider chart
   - **Query Breakdown** — sortable/filterable table, one row per query
   - **Competitors** — mention counts and share-of-voice vs your brand
   - **Trend** — citation rate over time, built automatically from every
     past run's scorecard CSV in `reports/` (run it weekly to build history)
   - **Raw Data** — full table + CSV download
   - **Errors** — any failed provider calls, isolated for debugging

---

## 5. Run it — Command line (alternative)

If you'd rather run it headless (e.g. from a cron job or CI), edit
`config.yaml` directly and use the CLI entry point instead of the dashboard:

```bash
python run_tracker.py
```

You'll see live progress in the terminal as it queries each provider. When done, check the `reports/` folder for two new timestamped CSV files.

**Cost estimate:** with 5 queries × 4 providers = 20 API calls, this typically costs well under $0.10 total on paid providers, and is free if you're only using Gemini's free tier.

---

## 6. Reading the output

Open `sample_output/scorecard_example.csv` to see the format before running your first real pass:

| provider | queries_tested | times_cited | citation_rate_pct | avg_first_position_pct | top_competitors_seen |
|---|---|---|---|---|---|
| openai | 5 | 3 | 60.0 | 15.2 | Nutanix (2) |

- **citation_rate_pct** — % of queries where your brand was mentioned at all
- **avg_first_position_pct** — how early in the response you're mentioned, on average (lower = better; 10% means you're named in the opening lines, 80% means you're an afterthought)
- **top_competitors_seen** — who's showing up in the same answers, with count

`raw_results.csv` has the row-level detail — useful for pulling exact snippets into a slide or report.

---

## 7. Verifying it works before adding real API keys

Run the included smoke test — it mocks all four providers (no real API calls, no cost) and checks that the query loop, error handling, brand/competitor detection, and scorecard math all produce correct results:

```bash
python smoke_test.py
```

You should see 8 `[PASS]` lines ending in `=== ALL CHECKS PASSED ===`. Re-run this any time you modify the code, before spending real API credits testing against live providers.

---

## 8. Scheduling it to run automatically (optional)

To track citation trends over time (weekly, say), add a cron job (Mac/Linux):

```bash
crontab -e
# Add this line to run every Monday at 9am:
0 9 * * 1 cd /full/path/to/ai-citation-tracker && venv/bin/python run_tracker.py
```

Each run creates new timestamped files in `reports/`, so nothing gets overwritten — you build a history automatically.

---

## 9. Extending it

Ideas if you want to take this further:
- **Slack/email alerts** — send a message when citation_rate_pct drops below a threshold
- **AI Overviews specifically** — Google doesn't offer a public AI Overviews API yet, so Perplexity (which does live web browsing) is currently the closest proxy in this tool
- **More providers** — Copilot, Grok, etc. can be added the same way: one new function in `citation_tracker/providers.py`, then add it to `PROVIDER_FUNCTIONS` / `PROVIDER_ENV_KEYS`
- **Multi-brand comparison** — run the dashboard once per competitor brand and compare Overview tabs side by side

---

## Project structure

```
ai-citation-tracker/
├── config.yaml                  # what to track (edit this, or use the dashboard instead)
├── dashboard.py                  # streamlit run dashboard.py — full UI, no file editing needed
├── run_tracker.py                # CLI alternative — run this to execute a pass headlessly
├── requirements.txt
├── .env.example                  # copy to .env and fill in keys (or use the dashboard sidebar)
├── citation_tracker/
│   ├── providers.py               # API calls to each LLM (openai, anthropic, perplexity, gemini, groq, openrouter)
│   ├── detector.py                # citation detection logic
│   └── tracker.py                 # orchestration + CSV output (run() for CLI, run_from_config() for dashboard)
├── reports/                       # your run outputs land here (also powers the dashboard's Trend tab)
└── sample_output/                 # example CSVs so you can see the format
```

---

## For your resume / portfolio

Suggested bullet:
> Built an automated AI Citation Tracker (Python) monitoring brand visibility and citation position across ChatGPT, Claude, Perplexity, and Gemini — surfacing competitor share-of-voice in generative search responses to inform GEO strategy.

Push this to a public GitHub repo and link it directly from your resume/LinkedIn — a working tool with a clean README is a much stronger signal than listing "GEO" as a skill.
