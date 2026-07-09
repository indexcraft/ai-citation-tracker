"""
providers.py
------------
One function per AI platform. Each function takes a plain-text query
and returns the plain-text response, or raises an exception with a
clear message if something goes wrong (bad key, rate limit, etc.)

Keeping each provider in its own small function means: if OpenAI changes
their API tomorrow, you only touch one function, not the whole tool.
"""

import os
import time
import requests


def _call_with_retry(fn, max_retries: int = 4, base_delay: float = 8.0):
    """
    Wraps an API call and retries on 429 (rate limit) with exponential
    backoff: 8s, 16s, 32s, 64s. Free tiers (especially Gemini) often
    reject bursts even when you're well under the daily quota — this
    fixes that without you having to babysit the script.
    """
    for attempt in range(max_retries + 1):
        try:
            return fn()
        except requests.exceptions.HTTPError as e:
            status = e.response.status_code if e.response is not None else None
            if status == 429 and attempt < max_retries:
                wait = base_delay * (2 ** attempt)
                print(f"    [429] rate limited — waiting {wait:.0f}s before retry {attempt + 1}/{max_retries}...")
                time.sleep(wait)
                continue
            raise


def query_openai(prompt: str, model: str, api_key: str) -> str:
    """Query ChatGPT (OpenAI) — this approximates what a user sees in
    a plain ChatGPT conversation (no browsing plugin)."""
    url = "https://api.openai.com/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.7,
        "max_tokens": 800,
    }

    def _do_call():
        resp = requests.post(url, headers=headers, json=payload, timeout=60)
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]

    return _call_with_retry(_do_call)


def query_anthropic(prompt: str, model: str, api_key: str) -> str:
    """Query Claude — useful to see how Claude itself frames the answer,
    since Claude is increasingly used for research and shopping queries."""
    url = "https://api.anthropic.com/v1/messages"
    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "max_tokens": 800,
        "messages": [{"role": "user", "content": prompt}],
    }

    def _do_call():
        resp = requests.post(url, headers=headers, json=payload, timeout=60)
        resp.raise_for_status()
        data = resp.json()
        text_blocks = [b["text"] for b in data.get("content", []) if b.get("type") == "text"]
        return "\n".join(text_blocks)

    return _call_with_retry(_do_call)


def query_perplexity(prompt: str, model: str, api_key: str) -> str:
    """Query Perplexity — this one actually browses the live web, so it's
    the closest proxy you have for 'what sources get cited right now'."""
    url = "https://api.perplexity.ai/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
    }

    def _do_call():
        resp = requests.post(url, headers=headers, json=payload, timeout=60)
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]

    return _call_with_retry(_do_call)


def query_gemini(prompt: str, model: str, api_key: str) -> str:
    """Query Gemini — proxy for how Google's AI Overviews / Gemini surface
    answers, since both draw from a similar underlying model family."""
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
    headers = {"Content-Type": "application/json"}
    payload = {"contents": [{"parts": [{"text": prompt}]}]}

    def _do_call():
        resp = requests.post(url, headers=headers, json=payload, timeout=60)
        resp.raise_for_status()
        data = resp.json()
        parts = data["candidates"][0]["content"]["parts"]
        return "\n".join(p.get("text", "") for p in parts)

    return _call_with_retry(_do_call)


def query_groq(prompt: str, model: str, api_key: str) -> str:
    """Query Groq — fast free-tier inference for open-source models
    (Llama, Gemma, etc). NOTE: this is for pipeline/testing purposes only.
    Groq doesn't power a consumer AI-search product, so citation rates
    from this provider don't reflect real-world AI-search visibility —
    use it to validate your code/config for free, not to report results."""
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.7,
        "max_tokens": 800,
    }

    def _do_call():
        resp = requests.post(url, headers=headers, json=payload, timeout=60)
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]

    return _call_with_retry(_do_call)


def query_openrouter(prompt: str, model: str, api_key: str) -> str:
    """Query OpenRouter — proxies many models through one API. Only a
    handful of models are actually free (look for ':free' suffix on the
    model name in OpenRouter's model list); paid models cost the same
    here as calling the provider directly. NOTE: testing/demo purposes
    only — same caveat as Groq re: real-world citation relevance."""
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.7,
        "max_tokens": 800,
    }

    def _do_call():
        resp = requests.post(url, headers=headers, json=payload, timeout=60)
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]

    return _call_with_retry(_do_call)


# Registry so tracker.py can loop over providers generically instead of
# writing near-identical if/elif blocks.
PROVIDER_FUNCTIONS = {
    "openai": query_openai,
    "anthropic": query_anthropic,
    "perplexity": query_perplexity,
    "gemini": query_gemini,
    "groq": query_groq,
    "openrouter": query_openrouter,
}

# Which env var holds the key for each provider.
PROVIDER_ENV_KEYS = {
    "openai": "OPENAI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "perplexity": "PERPLEXITY_API_KEY",
    "gemini": "GEMINI_API_KEY",
    "groq": "GROQ_API_KEY",
    "openrouter": "OPENROUTER_API_KEY",
}


def get_api_key(provider: str) -> str | None:
    env_var = PROVIDER_ENV_KEYS[provider]
    return os.environ.get(env_var)
