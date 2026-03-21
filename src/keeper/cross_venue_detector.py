"""
Cross-Venue Funding Detector — Grizzly's unique edge.

Compares Backpack's funding rate against Drift and Hyperliquid.
Since the user can't access Binance/Bybit from Japan, this uses
the two DEXs they already run (Yogi on Drift, Kodiak on HL) as
cross-venue references.

Three-venue comparison: Backpack vs Drift vs Hyperliquid.
"""

from dataclasses import dataclass

import requests

from src.config.constants import BP_API_URL, CROSS_VENUE_MAP, to_bp_symbol
from src.config.vault import STRATEGY_CONFIG


@dataclass
class VenueFunding:
    coin: str
    bp_rate: float              # Backpack annualized %
    drift_rate: float           # Drift annualized %
    hl_rate: float              # Hyperliquid annualized %
    bp_vs_avg_spread: float     # BP - avg(Drift, HL) annualized %
    convergence_signal: str     # "bp_high" | "bp_low" | "aligned" | "no_data"
    confidence: float           # 0-100


def _fetch_drift_funding() -> dict[str, float]:
    """Fetch Drift funding rates. Returns coin -> annualized APY."""
    result = {}
    try:
        resp = requests.get("https://data.api.drift.trade/stats/fundingRates", timeout=10)
        if resp.status_code != 200:
            return result
        data = resp.json()
        if not data.get("success") or not data.get("markets"):
            return result
        for m in data["markets"]:
            rate_24h = float(m["fundingRates"]["24h"])
            result[m["symbol"]] = rate_24h * 24 * 365 * 100
    except Exception:
        pass
    return result


def _fetch_hl_funding() -> dict[str, float]:
    """Fetch Hyperliquid predicted funding. Returns coin -> annualized APY."""
    result = {}
    try:
        resp = requests.post(
            "https://api.hyperliquid.xyz/info",
            json={"type": "metaAndAssetCtxs"},
            timeout=10,
        )
        if resp.status_code != 200:
            return result
        data = resp.json()
        meta = data[0]
        ctxs = data[1]
        for i, ctx in enumerate(ctxs):
            if i >= len(meta["universe"]):
                break
            coin = meta["universe"][i]["name"]
            rate = float(ctx.get("funding", 0))
            result[coin] = rate * 24 * 365 * 100
    except Exception:
        pass
    return result


def _fetch_bp_funding(coins: list[str]) -> dict[str, float]:
    """Fetch Backpack funding rates. Returns coin -> annualized APY."""
    result = {}
    try:
        mark_prices = requests.get(f"{BP_API_URL}/api/v1/markPrices", timeout=10)
        if mark_prices.status_code != 200:
            return result
        for item in mark_prices.json():
            symbol = item.get("symbol", "")
            if "_PERP" not in symbol:
                continue
            coin = symbol.replace("_USDC_PERP", "")
            if coin.startswith("k"):
                coin = coin[1:]  # kPEPE -> PEPE
            if coin in coins:
                rate = float(item.get("fundingRate", 0))
                result[coin] = rate * 24 * 365 * 100
    except Exception:
        pass
    return result


def fetch_cross_venue_funding(coins: list[str] = None) -> list[VenueFunding]:
    """
    Compare funding rates across Backpack, Drift, and Hyperliquid.
    """
    if coins is None:
        coins = STRATEGY_CONFIG["allowed_markets"]

    bp_rates = _fetch_bp_funding(coins)
    drift_rates = _fetch_drift_funding()
    hl_rates = _fetch_hl_funding()

    results = []
    spread_threshold = STRATEGY_CONFIG.get("cross_venue_spread_threshold_apy", 5.0)

    for coin in coins:
        bp_rate = bp_rates.get(coin, 0)
        mapping = CROSS_VENUE_MAP.get(coin, {})

        drift_symbol = mapping.get("drift")
        hl_symbol = mapping.get("hl", coin)

        drift_rate = drift_rates.get(drift_symbol, 0) if drift_symbol else 0
        hl_rate = hl_rates.get(hl_symbol, 0) if hl_symbol else 0

        # Compute average of available venues
        other_rates = []
        if drift_rate != 0:
            other_rates.append(drift_rate)
        if hl_rate != 0:
            other_rates.append(hl_rate)

        if not other_rates:
            results.append(VenueFunding(
                coin=coin, bp_rate=bp_rate, drift_rate=drift_rate,
                hl_rate=hl_rate, bp_vs_avg_spread=0,
                convergence_signal="no_data", confidence=0,
            ))
            continue

        avg_other = sum(other_rates) / len(other_rates)
        spread = bp_rate - avg_other

        if spread > spread_threshold:
            signal = "bp_high"
            confidence = min(100, abs(spread) / spread_threshold * 50)
        elif spread < -spread_threshold:
            signal = "bp_low"
            confidence = min(100, abs(spread) / spread_threshold * 50)
        else:
            signal = "aligned"
            confidence = 20.0

        results.append(VenueFunding(
            coin=coin, bp_rate=bp_rate, drift_rate=drift_rate,
            hl_rate=hl_rate, bp_vs_avg_spread=spread,
            convergence_signal=signal, confidence=confidence,
        ))

    return results


def format_cross_venue(venues: list[VenueFunding]) -> str:
    """Format cross-venue comparison for logging."""
    if not venues:
        return "Cross-venue: no data"

    lines = ["Cross-venue funding (BP vs Drift vs HL):"]
    for v in venues:
        bp = f"BP={v.bp_rate:+.1f}%"
        dr = f"Drift={v.drift_rate:+.1f}%" if v.drift_rate else "Drift=N/A"
        hl = f"HL={v.hl_rate:+.1f}%" if v.hl_rate else "HL=N/A"
        sp = f"spread={v.bp_vs_avg_spread:+.1f}%"
        lines.append(
            f"  {v.coin}: {bp} | {dr} | {hl} | {sp} -> {v.convergence_signal} ({v.confidence:.0f}%)"
        )
    return "\n".join(lines)
