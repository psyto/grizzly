# Grizzly

**The fierce bear. Backpack Exchange funding rate vault with cross-venue intelligence.**

Grizzly is a paper-trading USDC vault that harvests funding rates on Backpack Exchange perpetual futures. It runs the same regime-adaptive signal detection as [Yogi](https://github.com/psyto/yogi) (Drift) and [Kodiak](https://github.com/psyto/kodiak) (Hyperliquid), with three-venue cross-comparison (Backpack vs Drift vs Hyperliquid).

Currently in **paper trading mode** — reads live Backpack data and logs what it would do without executing trades.

## The Bear Family

| Vault | Venue | Language | Status |
|-------|-------|----------|--------|
| [Yogi](https://github.com/psyto/yogi) | Drift (Solana) | TypeScript | Live on mainnet |
| [Kodiak](https://github.com/psyto/kodiak) | Hyperliquid | Python | Live on mainnet |
| **Grizzly** | Backpack Exchange | Python | Paper trading |

## Quick Start

```bash
git clone https://github.com/psyto/grizzly.git
cd grizzly
pip install -r requirements.txt
python -m src.keeper.index
```

## License

MIT
