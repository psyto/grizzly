"""
Backpack Exchange API Client — read-only for paper trading.

Fetches market data, funding rates, mark prices, and order book data
from Backpack Exchange's REST API.
"""

import requests
from dataclasses import dataclass

from src.config.constants import BP_API_URL, to_bp_symbol


@dataclass
class MarketInfo:
    symbol: str
    coin: str
    mark_price: float
    index_price: float
    funding_rate: float          # Hourly rate
    funding_rate_annualized: float  # APY %
    open_interest: float         # In base asset
    open_interest_usd: float
    spread_pct: float            # (mark - index) / index * 100


@dataclass
class FundingHistory:
    symbol: str
    rate: float
    timestamp: str


def fetch_markets() -> list[dict]:
    """Fetch all markets from Backpack."""
    resp = requests.get(f"{BP_API_URL}/api/v1/markets", timeout=10)
    resp.raise_for_status()
    return resp.json()


def fetch_perp_markets() -> list[str]:
    """Get list of all perp market symbols."""
    markets = fetch_markets()
    return [m["symbol"] for m in markets if "_PERP" in m.get("symbol", "")]


def fetch_mark_prices() -> dict[str, dict]:
    """Fetch mark prices for all markets. Returns map of symbol -> data."""
    resp = requests.get(f"{BP_API_URL}/api/v1/markPrices", timeout=10)
    resp.raise_for_status()
    data = resp.json()
    return {item["symbol"]: item for item in data}


def fetch_ticker(symbol: str) -> dict:
    """Fetch 24h ticker for a symbol."""
    resp = requests.get(f"{BP_API_URL}/api/v1/ticker?symbol={symbol}", timeout=10)
    resp.raise_for_status()
    return resp.json()


def fetch_funding_rates(symbol: str, limit: int = 24) -> list[FundingHistory]:
    """Fetch funding rate history for a symbol."""
    resp = requests.get(
        f"{BP_API_URL}/api/v1/fundingRates?symbol={symbol}",
        timeout=10,
    )
    if resp.status_code != 200:
        return []

    data = resp.json()
    results = []
    for entry in data[:limit]:
        results.append(FundingHistory(
            symbol=entry.get("symbol", symbol),
            rate=float(entry.get("fundingRate", 0)),
            timestamp=entry.get("intervalEndTimestamp", ""),
        ))
    return results


def fetch_market_info(coins: list[str]) -> list[MarketInfo]:
    """
    Fetch market info for specified coins.
    Combines mark prices and funding rates.
    """
    mark_prices = fetch_mark_prices()
    results = []

    for coin in coins:
        symbol = to_bp_symbol(coin)
        mp = mark_prices.get(symbol)
        if not mp:
            continue

        mark_price = float(mp.get("markPrice", 0))
        index_price = float(mp.get("indexPrice", 0))
        funding_rate = float(mp.get("fundingRate", 0))

        # Estimate OI from mark price data if available
        oi_base = float(mp.get("openInterest", 0)) if "openInterest" in mp else 0
        oi_usd = oi_base * index_price if index_price > 0 else 0

        spread_pct = ((mark_price - index_price) / index_price * 100) if index_price > 0 else 0
        annualized = funding_rate * 24 * 365 * 100

        results.append(MarketInfo(
            symbol=symbol,
            coin=coin,
            mark_price=mark_price,
            index_price=index_price,
            funding_rate=funding_rate,
            funding_rate_annualized=annualized,
            open_interest=oi_base,
            open_interest_usd=oi_usd,
            spread_pct=spread_pct,
        ))

    return results


def fetch_all_funding_rates(coins: list[str]) -> list[MarketInfo]:
    """Fetch current funding rates for all monitored coins."""
    return fetch_market_info(coins)
