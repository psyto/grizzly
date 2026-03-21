# Grizzly

**The fierce bear. Backpack Exchange funding rate vault with three-venue cross-intelligence.**

Grizzly is a USDC vault that harvests funding rates on Backpack Exchange perpetual futures with regime-adaptive signal detection. It compares funding rates across three DEX venues — Backpack, Drift, and Hyperliquid — to optimize entry decisions. Currently in **paper trading mode** (read-only, no trades executed).

Part of the bear family: [Yogi](https://github.com/psyto/yogi) (Drift/Solana), [Kodiak](https://github.com/psyto/kodiak) (Hyperliquid), and Grizzly (Backpack).

## Strategy

Grizzly deploys capital into Backpack perp positions to harvest funding rates, with an intelligence layer that dynamically adjusts exposure:

1. **Regime-Adaptive Arbitrage (100%)** — Three stacked yield sources:
   - **Funding rate** — Bidirectional: SHORT when positive, LONG when negative
   - **Premium convergence** — Mark/index deviation mean-reverts
   - **OI rebalancing** — Position ahead of funding rate changes using imbalance signals
2. **Intelligence Layer** — Signal detection adjusts how much capital is deployed:
   - No anomalies: 70-100% deployed at target leverage
   - Low signals: 55-85% deployed, reduced leverage
   - Critical signals: 10-25% deployed, minimal leverage
   - Extreme vol: 0% deployed, fully idle

### How It Works

```
USDC Deposit --> Backpack Account
                 |
                 +-- 100% --> Backpack Perps (regime-adaptive arbitrage)
                              |
                              +-- Signal Detector (every 5 min)
                              |   +-- Spread blow-out (mark/index stress)
                              |   +-- Funding rate volatility (regime transition)
                              |   --> Severity: CLEAR / LOW / HIGH / CRITICAL
                              |
                              +-- Cross-Venue Detector (every 5 min) [Grizzly-specific]
                              |   +-- Backpack vs Drift vs Hyperliquid funding rates
                              |   +-- Three-DEX comparison (no CEX dependency)
                              |   +-- Detects Backpack divergence from DEX consensus
                              |   --> Entry direction adjustment
                              |
                              +-- Regime Engine (vol x signal --> deployment)
                              |   +-- Reads vol regime (funding rate vol proxy)
                              |   +-- Reads signal severity
                              |   --> deploymentPct + maxLeverage + rebalanceMode
                              |
                              +-- Direction: SHORT or LONG based on funding + spread
                              +-- Cross-venue adjustment on entry direction
                              +-- 30-second heartbeat monitoring
```

### What Makes Grizzly Unique

| | Yogi (Drift) | Kodiak (Hyperliquid) | Grizzly (Backpack) |
|---|---|---|---|
| Chain | Solana | Hyperliquid L1 | Backpack Exchange |
| Language | TypeScript | Python | Python |
| Vault | Voltr / Ranger Earn | HL native vault | Direct account |
| Cross-venue | Drift vs Binance/Bybit | HL vs Binance/Bybit | **BP vs Drift vs HL** |
| Unique edge | 5D signal detection | Zero-hash liquidation + funding pre-positioning | Three-DEX cross-intelligence |
| Markets | SOL, BTC, ETH, DOGE, SUI, AVAX | BTC, ETH, SOL, HYPE | BTC, ETH, SOL, SUI, DOGE, HYPE |
| Status | Live (mainnet) | Live (mainnet) | Paper trading |

**Grizzly's unique edge:** Instead of comparing against CEX venues (Binance/Bybit) which are unavailable to Japanese residents, Grizzly compares across the three DEX venues the user already operates on. This creates a closed-loop cross-venue intelligence system where each vault informs the others.

### Yield Stack

| Source | Mechanism | Est. APY Contribution |
|--------|-----------|----------------------|
| Funding harvesting | Bidirectional perp positions collect funding | 5-10% |
| Premium convergence | Mark/index deviation mean-reverts | 1-3% |
| Cross-venue timing | Enter when BP funding diverges from Drift/HL | 1-2% |
| **Combined target** | | **8-15% (normal) / 5-8% (hostile)** |

## Architecture

### Components

| Module | File | Purpose |
|--------|------|---------|
| Backpack Client | `src/keeper/backpack_client.py` | REST API client for market data, funding rates, mark prices |
| Cross-Venue Detector | `src/keeper/cross_venue_detector.py` | **[Grizzly-specific]** Three-DEX comparison (BP vs Drift vs HL) |
| Regime Engine | `src/keeper/index.py` | Vol x signal severity --> deployment % and leverage cap |
| Signal Detection | `src/keeper/index.py` | Spread blow-out and funding volatility detection |
| Paper Trading | `src/keeper/index.py` | Simulated position management and funding income tracking |
| Config | `src/config/` | Strategy parameters, signal thresholds, deployment matrices |

### Backpack API Endpoints Used

| Endpoint | Purpose |
|----------|---------|
| `GET /api/v1/markets` | List all perp markets |
| `GET /api/v1/markPrices` | Mark prices, index prices, funding rates |
| `GET /api/v1/fundingRates?symbol=X` | Historical funding rate data |
| `GET /api/v1/ticker?symbol=X` | 24h market statistics |

## Regime Engine

### Deployment Matrix (Vol Regime x Signal Severity)

|  | CLEAR | LOW | HIGH | CRITICAL |
|--|-------|-----|------|----------|
| **Very Low** (< 20% vol) | 100% @ 2.0x | 80% @ 1.5x | 50% @ 1.0x | 25% @ 0.5x |
| **Low** (20-35%) | 85% @ 1.5x | 70% @ 1.2x | 40% @ 0.8x | 20% @ 0.3x |
| **Normal** (35-50%) | 70% @ 1.0x | 55% @ 0.8x | 30% @ 0.5x | 15% @ 0.2x |
| **High** (50-75%) | 50% @ 0.5x | 35% @ 0.3x | 20% @ 0.2x | 10% @ 0.0x |
| **Extreme** (> 75%) | 0% @ 0.0x | 0% @ 0.0x | 0% @ 0.0x | 0% @ 0.0x |

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
| Min signal strength | 20% (40% in cautious/defensive) |
| Emergency rebalance | 30%+ deployment drop |

## Setup

```bash
# 1. Clone and install
git clone https://github.com/psyto/grizzly.git
cd grizzly
pip install -r requirements.txt

# 2. Run paper trading keeper
python -m src.keeper.index

# 3. For production (requires Backpack perp access):
# - Add ED25519 keypair authentication
# - Set paper_trading: False in config
# - Deploy on EC2 with pm2
```

## Cross-Venue Live Data (Sample)

```
Cross-venue funding (BP vs Drift vs HL):
  BTC: BP=-3.5% | Drift=+360.4% | HL=-5.9% | spread=-180.8% -> bp_low (100%)
  ETH: BP=-3.6% | Drift=+251.6% | HL=-3.8% | spread=-127.5% -> bp_low (100%)
  SOL: BP=+2.2% | Drift=-1235.3% | HL=+1.0% | spread=+619.3% -> bp_high (100%)
  SUI: BP=+7.3% | Drift=+1139.1% | HL=N/A | spread=-1132.0% -> bp_low (100%)
  HYPE: BP=+2.9% | Drift=N/A | HL=+11.0% | spread=-8.0% -> bp_low (85%)
```

## The Bear Family

| Vault | Venue | Tagline |
|-------|-------|---------|
| **Yogi** | Drift (Solana) | "Smarter than the average bear market vault" |
| **Kodiak** | Hyperliquid | "The biggest bear in the room" |
| **Grizzly** | Backpack Exchange | "The fierce bear" |

All three share the same strategy DNA: regime-adaptive funding rate harvesting with multi-dimensional signal detection. Each extends the base with venue-specific intelligence.

## Known Limitations

1. **Paper trading only** — Backpack perp futures are not available to Japanese residents. Live trading requires relocation or access from a non-restricted jurisdiction.
2. **No native vault** — Backpack has no vault mechanism. Grizzly trades from a direct account, meaning no external depositors.
3. **Vol estimation** — Uses funding rate volatility as a vol proxy. Backpack does not provide candle data in the same format as Drift/HL, so Parkinson estimator is approximated.
4. **Drift rate anomaly** — Drift's funding rate API returns values that appear anomalously large compared to other venues. Cross-venue spreads involving Drift should be interpreted with caution.

## License

MIT
