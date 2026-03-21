"""
Grizzly strategy configuration.
Ported from Kodiak, tuned for Backpack Exchange dynamics.
"""

STRATEGY_CONFIG = {
    # Capital allocation
    "lending_floor_pct": 0,        # No lending on Backpack — 100% to perps
    "basis_trade_pct": 100,

    # Funding rate thresholds
    "min_annualized_funding_bps": 500,   # 5% minimum
    "exit_funding_bps": -50,             # -0.5% exit

    # AMM imbalance signals
    "min_signal_strength": 20,
    "use_imbalance_signals": True,

    # Order execution
    # Backpack fee tiers TBD — using conservative estimates
    "use_limit_orders": False,     # Market orders for now (paper trading)
    "bp_maker_fee_bps": 2.0,
    "bp_taker_fee_bps": 4.0,
    "estimated_slippage_bps": 2,

    # Low-turnover model
    "min_holding_period_hours": 168,    # 7 days
    "min_funding_advantage_to_rotate_bps": 200,
    "max_rotations_per_week": 2,

    # Market quality filters
    "max_markets_simultaneous": 3,
    "allowed_markets": ["BTC", "ETH", "SOL", "SUI", "DOGE", "HYPE"],
    "exclude_markets": [],

    # Dynamic leverage control
    "leverage_by_vol_regime": {
        "veryLow": 2.0,
        "low": 1.5,
        "normal": 1.0,
        "high": 0.5,
        "extreme": 0.0,
    },
    "max_leverage": 2,

    "vol_regime_thresholds": {
        "veryLow": 2000,
        "low": 3500,
        "normal": 5000,
        "high": 7500,
    },

    # Risk limits
    "max_drawdown_pct": 3,
    "severe_drawdown_pct": 5,
    "max_position_pct_per_market": 40,

    # Health ratio monitoring
    "min_margin_ratio": 1.15,
    "critical_margin_ratio": 1.08,
    "health_check_interval_ms": 30 * 1000,

    # Timing
    "rebalance_interval_ms": 4 * 60 * 60 * 1000,
    "funding_scan_interval_ms": 30 * 60 * 1000,
    "emergency_check_interval_ms": 30 * 1000,

    # Signal detection
    "signal_detection_interval_ms": 5 * 60 * 1000,
    "monitored_markets": ["BTC", "ETH", "SOL"],
    "signal_history_size": 12,
    "funding_history_size": 168,
    "funding_vol_window": 24,

    # Signal thresholds
    "signal_thresholds": {
        "oi_shift":    {"low": 4, "high": 12, "critical": 25},
        "oi_drop":     {"low": 4, "high": 12, "critical": 25},
        "funding_vol": {"low": 500, "high": 1500, "critical": 3000},
        "spread":      {"low": 0.3, "high": 1.0, "critical": 2.5},
    },

    # Imbalance signal scoring weights
    "signal_weights": {
        "funding": 0.5,
        "premium": 0.3,
        "oi": 0.2,
    },

    "signal_scale_factors": {
        "funding": 500,
        "premium": 10,
        "oi": 10,
    },

    # Regime matrices (same as Kodiak)
    "deployment_matrix": {
        "veryLow": [100, 80, 50, 25],
        "low":     [85,  70, 40, 20],
        "normal":  [70,  55, 30, 15],
        "high":    [50,  35, 20, 10],
        "extreme": [0,   0,  0,  0],
    },

    "leverage_matrix": {
        "veryLow": [2.0, 1.5, 1.0, 0.5],
        "low":     [1.5, 1.2, 0.8, 0.3],
        "normal":  [1.0, 0.8, 0.5, 0.2],
        "high":    [0.5, 0.3, 0.2, 0.0],
        "extreme": [0.0, 0.0, 0.0, 0.0],
    },

    "cautious_min_signal_strength": 40,
    "emergency_deployment_drop_pct": 30,

    # Cross-venue funding
    "cross_venue_spread_threshold_apy": 5.0,

    # Paper trading mode
    "paper_trading": True,
}
