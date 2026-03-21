"""
Grizzly Keeper — Paper trading mode on Backpack Exchange.

Reads live market data from Backpack, runs the same regime-adaptive
signal detection as Kodiak/Yogi, and logs what it would do without
executing trades. The code is ready for live trading when Backpack
perps become accessible.
"""

import asyncio
import math
import time
from dataclasses import dataclass, field
from typing import Optional

from src.config.vault import STRATEGY_CONFIG
from src.config.constants import MONITORED_MARKETS
from src.keeper.backpack_client import (
    fetch_market_info,
    fetch_funding_rates,
    MarketInfo,
)
from src.keeper.cross_venue_detector import (
    fetch_cross_venue_funding,
    format_cross_venue,
)


# --- Signal severity levels ---
SIGNAL_NONE = 0
SIGNAL_LOW = 1
SIGNAL_HIGH = 2
SIGNAL_CRITICAL = 3


@dataclass
class PaperPosition:
    coin: str
    direction: str          # "short" | "long"
    size_usd: float
    entry_price: float
    entry_funding_rate: float
    entry_timestamp: float
    cumulative_funding: float = 0.0


@dataclass
class RegimeState:
    vol_regime: str
    signal_severity: int
    deployment_pct: float
    max_leverage: float
    rebalance_mode: str
    reason: str


# --- Global state ---
active_positions: list[PaperPosition] = []
peak_equity = 0.0
current_regime: Optional[RegimeState] = None
latest_markets: list[MarketInfo] = []
funding_history: dict[str, list[float]] = {}
initial_equity = 0.0


def classify_vol_regime(vol_bps: int) -> str:
    t = STRATEGY_CONFIG["vol_regime_thresholds"]
    if vol_bps < t["veryLow"]:
        return "veryLow"
    if vol_bps < t["low"]:
        return "low"
    if vol_bps < t["normal"]:
        return "normal"
    if vol_bps < t["high"]:
        return "high"
    return "extreme"


def compute_regime(vol_regime: str, signal_severity: int) -> RegimeState:
    deploy_row = STRATEGY_CONFIG["deployment_matrix"].get(vol_regime, [0, 0, 0, 0])
    leverage_row = STRATEGY_CONFIG["leverage_matrix"].get(vol_regime, [0, 0, 0, 0])

    deployment_pct = deploy_row[signal_severity] if signal_severity < len(deploy_row) else 0
    max_leverage = leverage_row[signal_severity] if signal_severity < len(leverage_row) else 0

    if deployment_pct >= 85:
        mode = "aggressive"
    elif deployment_pct >= 55:
        mode = "normal"
    elif deployment_pct >= 20:
        mode = "cautious"
    else:
        mode = "defensive"

    severity_labels = ["clear", "low", "high", "critical"]
    label = severity_labels[signal_severity] if signal_severity < len(severity_labels) else "?"
    reason = f"{vol_regime} vol, {label} signal -> {deployment_pct}% @ {max_leverage}x"

    return RegimeState(
        vol_regime=vol_regime,
        signal_severity=signal_severity,
        deployment_pct=deployment_pct,
        max_leverage=max_leverage,
        rebalance_mode=mode,
        reason=reason,
    )


def fetch_reference_vol() -> int:
    """
    Estimate realized vol from Backpack BTC mark price history.
    Uses funding rate volatility as a proxy (similar to Yogi's approach).
    """
    history = fetch_funding_rates("BTC_USDC_PERP", limit=168)
    if len(history) < 10:
        return 3000  # Default 30%

    rates = [h.rate for h in history]
    recent = rates[:24]  # Last 24 hours
    mean = sum(recent) / len(recent)
    variance = sum((r - mean) ** 2 for r in recent) / len(recent)
    std_dev = math.sqrt(variance)

    # Annualize: hourly data
    annualized_vol_bps = std_dev * math.sqrt(24 * 365) * 10000
    result = round(annualized_vol_bps)
    return result if math.isfinite(result) else 3000


def detect_signals(markets: list[MarketInfo]) -> int:
    """
    Simple signal detection based on spread blow-out and funding volatility.
    Returns max severity (0-3).
    """
    max_severity = SIGNAL_NONE

    # Check spread blow-out
    for m in markets:
        abs_spread = abs(m.spread_pct)
        t = STRATEGY_CONFIG["signal_thresholds"]["spread"]
        if abs_spread >= t["critical"]:
            max_severity = max(max_severity, SIGNAL_CRITICAL)
        elif abs_spread >= t["high"]:
            max_severity = max(max_severity, SIGNAL_HIGH)
        elif abs_spread >= t["low"]:
            max_severity = max(max_severity, SIGNAL_LOW)

    return max_severity


def simulate_rebalance(
    markets: list[MarketInfo],
    equity: float,
    regime: RegimeState,
) -> list[dict]:
    """
    Simulate what positions the keeper would open.
    Returns list of simulated trades.
    """
    deployment_pct = regime.deployment_pct
    leverage = regime.max_leverage

    if deployment_pct == 0 or leverage == 0:
        return []

    deployable = equity * (deployment_pct / 100)
    basis_budget = deployable * (STRATEGY_CONFIG["basis_trade_pct"] / 100)

    # Filter to positive funding markets
    positive = [m for m in markets if m.funding_rate_annualized > STRATEGY_CONFIG["min_annualized_funding_bps"] / 100]
    positive.sort(key=lambda m: m.funding_rate_annualized, reverse=True)

    max_markets = STRATEGY_CONFIG["max_markets_simultaneous"]
    selected = positive[:max_markets]

    if not selected:
        return []

    total_score = sum(m.funding_rate_annualized for m in selected)
    trades = []

    for m in selected:
        weight = m.funding_rate_annualized / total_score if total_score > 0 else 1 / len(selected)
        size_usd = basis_budget * weight * leverage
        max_size = equity * STRATEGY_CONFIG["max_position_pct_per_market"] / 100
        size_usd = min(size_usd, max_size)

        if size_usd < 1:
            continue

        trades.append({
            "coin": m.coin,
            "direction": "short",
            "size_usd": size_usd,
            "funding_apy": m.funding_rate_annualized,
            "mark_price": m.mark_price,
            "reason": f"funding {m.funding_rate_annualized:+.1f}% APY -> short",
        })

    return trades


async def main():
    """Grizzly keeper main loop — paper trading mode."""
    global current_regime, latest_markets, peak_equity, initial_equity

    print("Grizzly Keeper Starting... (PAPER TRADING MODE)")
    print("Strategy: Backpack funding rate arbitrage + signal detection")
    print("Venue: Backpack Exchange (read-only — no trades executed)")
    print(f"Markets: {', '.join(STRATEGY_CONFIG['allowed_markets'])}\n")

    # Simulated equity
    initial_equity = 500.0
    equity = initial_equity
    peak_equity = equity
    print(f"Simulated equity: ${equity:.2f}\n")

    last_scan = 0.0
    last_rebalance = 0.0
    last_signal_detection = 0.0

    while True:
        now = time.time()
        now_ms = now * 1000

        # Signal detection (every 5 min)
        if now_ms - last_signal_detection * 1000 >= STRATEGY_CONFIG["signal_detection_interval_ms"]:
            print("\n--- Signal Detection ---")

            try:
                latest_markets = fetch_market_info(STRATEGY_CONFIG["allowed_markets"])

                # Signals
                severity = detect_signals(latest_markets)
                severity_labels = ["CLEAR", "LOW", "HIGH", "CRITICAL"]
                print(f"Signal: {severity_labels[severity]}")

                # Vol regime
                vol_bps = fetch_reference_vol()
                vol_regime = classify_vol_regime(vol_bps)
                print(f"Vol: {vol_bps / 100:.1f}% ({vol_regime} regime)")

                # Regime
                current_regime = compute_regime(vol_regime, severity)
                mode_prefix = {"aggressive": ">>", "normal": "->", "cautious": "~~", "defensive": "!!"}
                print(f"Regime: [{mode_prefix.get(current_regime.rebalance_mode, '??')}] {current_regime.reason}")

                # Cross-venue
                cross_venue = fetch_cross_venue_funding()
                print(format_cross_venue(cross_venue))

            except Exception as err:
                print(f"Signal detection error: {err}")

            last_signal_detection = now

        # Funding scan (every 30 min)
        if now_ms - last_scan * 1000 >= STRATEGY_CONFIG["funding_scan_interval_ms"]:
            print("\n--- Funding Rate Scan ---")
            try:
                markets = fetch_market_info(STRATEGY_CONFIG["allowed_markets"])
                positive = [m for m in markets if m.funding_rate_annualized > 0]
                positive.sort(key=lambda m: m.funding_rate_annualized, reverse=True)

                print(f"Markets: {len(markets)} total -> {len(positive)} positive funding")
                for i, m in enumerate(positive[:5]):
                    print(f"  {i+1}. {m.coin}: {m.funding_rate_annualized:+.1f}% APY")
            except Exception as err:
                print(f"Funding scan error: {err}")

            last_scan = now

        # Rebalance (every 4 hours)
        if now_ms - last_rebalance * 1000 >= STRATEGY_CONFIG["rebalance_interval_ms"]:
            print("\n--- Rebalance (PAPER) ---")
            try:
                if current_regime and latest_markets:
                    # Simulate funding income from open positions
                    for pos in active_positions:
                        # Estimate hourly funding earned since last rebalance
                        hours = (now - pos.entry_timestamp) / 3600
                        hourly_income = pos.size_usd * pos.entry_funding_rate
                        pos.cumulative_funding += hourly_income * min(hours, 4)
                        pos.entry_timestamp = now  # Reset for next cycle

                    funding_earned = sum(p.cumulative_funding for p in active_positions)
                    equity = initial_equity + funding_earned

                    print(f"Equity: ${equity:.2f} (funding earned: ${funding_earned:.4f})")
                    print(f"Regime: {current_regime.rebalance_mode} ({current_regime.deployment_pct}% @ {current_regime.max_leverage}x)")

                    # Clear old positions and compute new ones
                    active_positions.clear()
                    trades = simulate_rebalance(latest_markets, equity, current_regime)

                    if trades:
                        print(f"Would open {len(trades)} positions:")
                        for t in trades:
                            print(f"  [PAPER] {t['direction'].upper()} ${t['size_usd']:.2f} {t['coin']} | {t['reason']}")
                            active_positions.append(PaperPosition(
                                coin=t["coin"],
                                direction=t["direction"],
                                size_usd=t["size_usd"],
                                entry_price=t["mark_price"],
                                entry_funding_rate=float(next(
                                    (m.funding_rate for m in latest_markets if m.coin == t["coin"]),
                                    0,
                                )),
                                entry_timestamp=now,
                            ))
                    else:
                        print("No positions to open (no positive funding or defensive mode)")
                else:
                    print("Waiting for signal detection to initialize...")

            except Exception as err:
                print(f"Rebalance error: {err}")

            last_rebalance = now

        # Heartbeat
        funding_earned = sum(p.cumulative_funding for p in active_positions)
        equity = initial_equity + funding_earned
        regime_str = f"{current_regime.rebalance_mode} ({current_regime.deployment_pct}% @ {current_regime.max_leverage}x)" if current_regime else "initializing"
        severity_labels = ["CLEAR", "LOW", "HIGH", "CRITICAL"]
        signal_str = severity_labels[current_regime.signal_severity] if current_regime else "?"
        next_rebalance = max(0, STRATEGY_CONFIG["rebalance_interval_ms"] / 1000 - (now - last_rebalance)) / 60

        print(
            f"[{time.strftime('%Y-%m-%dT%H:%M:%S')}] "
            f"[PAPER] Positions: {len(active_positions)} | "
            f"Equity: ${equity:.2f} | "
            f"Regime: {regime_str} | "
            f"Signal: {signal_str} | "
            f"Next rebalance: {next_rebalance:.0f}min"
        )

        await asyncio.sleep(30)


if __name__ == "__main__":
    asyncio.run(main())
