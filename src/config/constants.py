"""
Grizzly Constants — Backpack Exchange configuration.
"""

BP_API_URL = "https://api.backpack.exchange"
BP_WS_URL = "wss://ws.backpack.exchange"

# Markets to monitor (Backpack perp symbols)
MONITORED_MARKETS = ["SOL", "BTC", "ETH", "DOGE", "SUI", "HYPE"]

# Backpack symbol format: {COIN}_USDC_PERP
def to_bp_symbol(coin: str) -> str:
    return f"{coin}_USDC_PERP"

# Map Backpack coins to Drift/HL for cross-venue comparison
CROSS_VENUE_MAP = {
    "SOL": {"drift": "SOL-PERP", "hl": "SOL"},
    "BTC": {"drift": "BTC-PERP", "hl": "BTC"},
    "ETH": {"drift": "ETH-PERP", "hl": "ETH"},
    "DOGE": {"drift": "DOGE-PERP", "hl": None},
    "SUI": {"drift": "SUI-PERP", "hl": None},
    "HYPE": {"drift": None, "hl": "HYPE"},
}
