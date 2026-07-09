"""
detector.py
-----------
Takes a raw LLM response and figures out:
  - was the brand mentioned at all?
  - how many times?
  - how early in the response (position matters — a brand mentioned in
    sentence 1 is a much stronger signal than one mentioned in a footnote)
  - which competitors showed up in the same answer
  - a short snippet of surrounding context, for a human to sanity-check
"""

import re


def _find_mentions(text: str, term: str):
    """Case-insensitive whole-phrase search. Returns list of character
    offsets where the term starts."""
    pattern = re.escape(term)
    return [m.start() for m in re.finditer(pattern, text, flags=re.IGNORECASE)]


def _snippet(text: str, offset: int, term_len: int, window: int = 100) -> str:
    start = max(0, offset - window)
    end = min(len(text), offset + term_len + window)
    snippet = text[start:end].replace("\n", " ").strip()
    return f"...{snippet}..."


def analyze_response(response_text: str, brand_name: str, brand_aliases: list, competitors: list) -> dict:
    """
    Returns a dict with all the fields written to the results CSV.
    """
    all_brand_terms = [brand_name] + list(brand_aliases)

    mention_offsets = []
    matched_term = None
    for term in all_brand_terms:
        offsets = _find_mentions(response_text, term)
        if offsets:
            mention_offsets.extend(offsets)
            if matched_term is None:
                matched_term = term

    mention_offsets = sorted(set(mention_offsets))
    brand_mentioned = len(mention_offsets) > 0
    mention_count = len(mention_offsets)

    # Position score: where in the response (as a %) does the first
    # mention appear? 0% = opens the answer, 100% = right at the end.
    response_len = max(len(response_text), 1)
    first_position_pct = round((mention_offsets[0] / response_len) * 100, 1) if brand_mentioned else None

    snippet = ""
    if brand_mentioned:
        term_len = len(matched_term) if matched_term else len(brand_name)
        snippet = _snippet(response_text, mention_offsets[0], term_len)

    competitors_mentioned = []
    for comp in competitors:
        if _find_mentions(response_text, comp):
            competitors_mentioned.append(comp)

    return {
        "brand_mentioned": brand_mentioned,
        "mention_count": mention_count,
        "first_position_pct": first_position_pct,
        "snippet": snippet,
        "competitors_mentioned": ", ".join(competitors_mentioned) if competitors_mentioned else "",
        "response_length_chars": len(response_text),
    }
