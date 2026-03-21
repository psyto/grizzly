# Grizzly Vault — Strategy Documentation

## Thesis

Backpack Exchange's perpetual futures markets exhibit funding rate dislocations that can be harvested systematically. By comparing Backpack's rates against two other DEX venues the operator already runs (Drift via Yogi, Hyperliquid via Kodiak), Grizzly creates a **closed-loop three-venue intelligence system** where each vault informs the others' entry decisions.

**Core insight**: Most cross-venue strategies compare against CEX venues (Binance, Bybit), which are inaccessible to Japanese residents. Grizzly solves this by using Drift and Hyperliquid — two DEX venues the operator already monitors — as the cross-venue reference. This is both a constraint-driven innovation and a genuine edge: DEX-to-DEX funding divergence is less arbitraged than DEX-to-CEX divergence.

**Revenue sources**: Funding payments + mark/index premium convergence + cross-venue timing alpha. Three sources active across all market conditions, with deployment scaled by regime intelligence.

## How It Works

### Capital Allocation

```
Total Capital
|
+-- 100% --> Regime-Adaptive Arbitrage Pool
             |
             +-- Signal Detector (every 5 min)
             |   +-- Spread blow-out (mark/index divergence)
             |   +-- Funding rate volatility
             |   --> CLEAR / LOW / HIGH / CRITICAL
             |
             +-- Cross-Venue Detector (every 5 min)
             |   +-- Fetches Backpack funding rates
             |   +-- Fetches Drift rates (via data.api.drift.trade)
             |   +-- Fetches Hyperliquid rates (via api.hyperliquid.xyz)
             |   +-- Classifies: bp_high / bp_low / aligned
             |   --> Entry direction adjustment
             |
             +-- Regime Engine
             |   +-- Vol regime (funding rate vol proxy)
             |   +-- Signal severity
             |   --> deploymentPct + maxLeverage + rebalanceMode
             |
             +-- Position Manager (paper trading)
                 +-- Simulated entry/exit
                 +-- Funding income tracking
                 +-- Paper PnL calculation
```

### Cross-Venue Intelligence — Three-DEX Comparison

Grizzly's unique contribution to the bear family is comparing across **three permissionless DEXs** instead of relying on CEX data:

| Venue | Data Source | Funding Interval |
|-------|-----------|------------------|
| Backpack | REST API (`/api/v1/markPrices`) | Hourly |
| Drift | REST API (`data.api.drift.trade/stats/fundingRates`) | Continuous |
| Hyperliquid | REST API (`api.hyperliquid.xyz/info`) | Hourly |

**Signal interpretation:**

| Signal | Condition | Entry Adjustment |
|--------|-----------|-----------------|
| `bp_high` | Backpack funding > DEX avg by 5%+ APY | SHORT profitable on BP, convergence risk |
| `bp_low` | Backpack funding < DEX avg by 5%+ APY | Potential LONG as BP converges up |
| `aligned` | All three venues within 5% APY | High confidence — strengthen base signal |

### Entry Criteria

A market is eligible for a position when ALL of the following are met:
1. Funding rate above 5% APY (annualized)
2. Market is on the allowed whitelist
3. Regime allows deployment > 0% and leverage > 0
4. Signal severity is not CRITICAL

### Direction Logic

```
IF funding > 0 --> SHORT (collect funding)
IF funding < 0 --> LONG (collect funding)
Cross-venue adjustment applied to entry reason
```

### Exit Criteria

A position is closed when ANY of the following occur:
1. Funding rate drops below -0.5% APY (turns against position)
2. Drawdown exceeds 3% (reduce) or 5% (close all)
3. Regime transitions to 0% deployment or 0x leverage
4. Minimum holding period (7 days) exceeded and better market available

## Regime Engine Decision Matrix

### Deployment Matrix (Vol Regime x Signal Severity)

```
                   Signal Severity
Vol Regime    CLEAR    LOW      HIGH     CRITICAL
-------------------------------------------------
Very Low     100/2.0  80/1.5   50/1.0   25/0.5
Low           85/1.5  70/1.2   40/0.8   20/0.3
Normal        70/1.0  55/0.8   30/0.5   15/0.2
High          50/0.5  35/0.3   20/0.2   10/0.0
Extreme        0/0.0   0/0.0    0/0.0    0/0.0

Format: deploymentPct / maxLeverage
```

## Execution Cost Gate

| | Taker (estimated) | Maker (estimated) |
|---|---|---|
| Backpack fee | ~4.0 bps | ~2.0 bps |
| Round-trip cost | ~10 bps | ~6 bps |
| Break-even (7-day hold) | 5.2% APY | 3.1% APY |

Note: Backpack fee tiers may vary. These are conservative estimates.

## Risk Management

| Parameter | Value |
|-----------|-------|
| Max drawdown | 3% reduce / 5% close all |
| Max leverage | 2x (regime-adaptive) |
| Signal scan | Every 5 minutes |
| Max per market | 40% |
| Max markets | 3 |
| Min hold | 7 days |
| Max rotations | 2 per week |
| Emergency rebalance | 30%+ deployment drop |

## Expected Returns

| Market Condition | Vol | Signals | Deployment | Expected APY |
|-----------------|-----|---------|------------|-------------|
| Normal | Normal | CLEAR | 70% @ 1.0x | 8-15% |
| Bear + stress | High | LOW | 35% @ 0.3x | 3-5% |
| Crisis | Extreme | CRITICAL | 0% @ 0.0x | 0% (idle) |
| Recovery | Low | CLEAR | 85% @ 1.5x | 12-20% |

## Known Limitations

1. **Paper trading only** — Backpack perp futures are not available to Japanese residents. Live trading requires access from a non-restricted jurisdiction.
2. **No native vault** — Backpack has no vault mechanism. Grizzly trades from a direct account.
3. **Vol estimation** — Uses funding rate volatility as a proxy. Less accurate than Parkinson estimator on price candles.
4. **Drift rate anomaly** — Drift's funding rate API returns values that appear anomalously large compared to Backpack and Hyperliquid. Cross-venue spreads involving Drift should be interpreted cautiously.
5. **No liquidation detection** — Unlike Kodiak (zero-hash trades), Backpack does not expose liquidation events. OI-drop proxy is the only option.
6. **Single keeper** — Same SPOF risk as Kodiak. Acceptable at current scale.

## Implementation Details

### Technology

- **Trading venue**: Backpack Exchange perpetual futures
- **Keeper**: Python bot (paper trading mode)
- **Cross-venue data**: Drift Data API + Hyperliquid REST API + Backpack REST API
- **Authentication**: ED25519 keypair (for future live trading)
- **Deployment**: Local or EC2 with pm2

### Keeper Loop Architecture

```
Main Loop (30-second tick)
+-- Every 5m:   Signal detection (spread + funding vol)
|               +-- Cross-venue comparison (BP vs Drift vs HL)
|               +-- Regime update
+-- Every 30m:  Funding scan (all allowed markets)
+-- Every 4h:   Rebalance cycle
|   +-- Apply regime-adjusted deployment %
|   +-- Scale targets by leverage
|   +-- Simulate position opens (paper trading)
|   +-- Track simulated funding income
+-- Every 30s:  Heartbeat log
```

### Execution Flow (Paper Trading)

1. **Read**: Fetch Backpack market data (funding rates, mark/index prices)
2. **Compare**: Cross-venue comparison against Drift and Hyperliquid
3. **Detect**: Signal detection (spread blow-out, funding volatility)
4. **Decide**: Regime engine determines deployment and leverage
5. **Simulate**: Log what positions would be opened/closed
6. **Track**: Accumulate simulated funding income

### Execution Flow (Future Live Trading)

1. **Deposit**: USDC to Backpack account
2. **Auth**: ED25519 keypair signs all API requests
3. **Trade**: POST `/api/v1/order` for position entry/exit
4. **Monitor**: GET `/api/v1/positions` for position tracking
5. **Funding**: Settled hourly, reflected in account balance

## Lineage

Grizzly is the third member of the bear family:

| Generation | Vault | Innovation |
|------------|-------|------------|
| 1st | Yogi (Drift) | 5D signal detection + regime engine |
| 2nd | Kodiak (Hyperliquid) | Zero-hash liquidation + funding pre-positioning + cross-venue (HL vs CEX) |
| 3rd | Grizzly (Backpack) | Three-DEX cross-intelligence (BP vs Drift vs HL) |

Each generation inherits the strategy DNA and adds venue-specific intelligence.
