"""Versioned token pricing used for estimates, never as a billing ledger."""

PRICING_VERSION = "anthropic-sonnet-4.6-standard-2026-07-03"

# USD per million tokens. These are kept beside a version label so an old
# estimate remains interpretable after provider prices change.
RATES_PER_MILLION = {
    "input_tokens": 3.00,
    "output_tokens": 15.00,
    "cache_creation_tokens": 3.75,  # five-minute cache write
    "cache_read_tokens": 0.30,
}


def estimate_cost_usd(usage: dict) -> float:
    return round(sum(
        int(usage.get(name, 0) or 0) * rate / 1_000_000
        for name, rate in RATES_PER_MILLION.items()
    ), 12)
