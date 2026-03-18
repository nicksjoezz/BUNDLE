# INFINITYATO_OS v2.0 - Ultimate Solana Token Launcher & Bundler

A professional-grade, high-speed Solana token launcher and management suite with a "Hacker OS" aesthetic. Built for pump.fun token strategies, including bundling, sniping, and volume generation.

## 🚀 Features

### 1. Token Forge (Launch Suite)
* **Bundle Launch:** Launch a token and buy with up to 20 wallets in a single Jito bundle.
* **Clone + Snipe:** Clone metadata from an existing token and snipe it immediately.
* **Snipe Only:** Precise sniping by mint address.
* **Bundle + Stagger:** Launch with a bundle, then stagger secondary buys for natural chart growth.
* **Sniper Farmer:** Automates the launch of multiple tokens with configurable liquidity thresholds and exit triggers.

### 2. Exit Strategy (Sell Suite)
* **Dump All:** Instantly liquidate all sub-wallet positions.
* **Delayed Sell:** Sell sub-wallet balances one-by-one with configurable delays to avoid price crashes.
* **Dev Dump All:** Transfer all tokens to the main wallet before selling to minimize transaction footprints.
* **Transfer Sell:** Aggregate all tokens to a clean target wallet and sell from there.

### 3. Wallet Matrix (Management)
* **Mass Funding:** Distribute SOL from main to all sub-wallets in one click.
* **SOL Reclaim:** Pull all remaining SOL from sub-wallets back to the main wallet.
* **Wallet Warmup:** Generate organic transaction volume to season fresh wallets.
* **Vanity Engine:** High-performance background miner to generate custom Solana addresses (prefixes/suffixes).
* **Burn Dev Supply:** Instantly burn remaining developer token supply to build community trust.

### 4. Advanced Dashboards
* **Performance Metrics:** Real-time tracking of profit, launch history, and active tasks.
* **Terminal Output:** Live backend logs streamed directly to the frontend for full transparency.
* **Neural Settings:** Centralized configuration for RPCs, Jito, Helius, and strategy parameters.

## 🛠️ Technical Stack
* **Frontend:** React 19, Vite, Tailwind CSS, Framer Motion (Hacker Theme).
* **Backend:** Python (Flask), Asyncio for high-concurrency blockchain ops.
* **Blockchain:** `solders`, `solana-py`, Jito Bundle API, Helius RPC.

## 📦 Installation & Setup

1. **Clone the Repo:**
   ```bash
   git clone <repo-url>
   cd infinity-ato-os
   ```

2. **Environment Setup:**
   Configure `config.ini` with your Helius API Key, RPC URLs, and Main Wallet Mnemonic.

3. **Running with Docker (Recommended):**
   ```bash
   docker build -t infinity-os .
   docker run -p 5000:5000 infinity-os
   ```

4. **Manual Start:**
   * **Frontend:** `cd frontend && npm install && npm run build`
   * **Backend:** `pip install -r requirements.txt && python3 main.py`

## ⚖️ Disclaimer
This tool is for educational and research purposes only. Use of automated trading bots involves high risk. The developers are not responsible for any financial losses.
