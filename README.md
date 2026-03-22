# INFINITYATO_OS v2.0 - Advanced Solana Token Ops Center

A high-speed, professional-grade mission control for Solana token strategies. Built for speed, precision, and complete chart dominance.

## 🌪️ Core Features

### 1. Atomic Bundling (Jito-Bundled Launches)
Launch and buy with up to 20 sub-wallets in the **exact same block**. Own the initial supply before anyone else using atomic Jito bundles.

### 2. Market Maker & Volume Bot
Keep your token active. Deploy automated nodes to rotate buy and sell orders across your fleet. Generate organic-looking chart volume and maintain your token's visibility on "Latest Trades" radars.

### 3. Sniper Farming Array
Scale your operations. Simultaneously monitor and launch multiple tokens. Program USD liquidity thresholds and let the automated farmer handle the monitoring and auto-exits.

### 4. Stealth Liquidation Protocols
Don't just dump. Exit your positions with precision using strategies like **Dev-Dump** (aggregate supply to dev) or **Transfer-Sell** (aggregate to clean target wallets) to minimize price impact and hide your developer footprint.

### 5. Unified Fleet Management (Wallet Matrix)
Control a fleet of 20+ sub-wallets from a single interface.
- **Mass Funding:** One-click SOL distribution from main to all sub-wallets.
- **SOL Reclaim:** Pull all remaining SOL from the fleet back to your main wallet.
- **Vanity Miner:** Generate custom Solana addresses (prefixes/suffixes) in the background.

## 🛠️ Technical Stack
- **Frontend:** React 19, Vite, Tailwind CSS, Framer Motion (Hacker Theme).
- **Backend:** Python (Flask), Asyncio for high-concurrency blockchain operations.
- **Blockchain:** Direct integration with Pump Portal, Jito Bundle API, and Helius RPC.

## 📦 Installation & Setup

1. **Clone the Repo:**
   ```bash
   git clone <repo-url>
   cd infinity-os
   ```

2. **Environment Setup:**
   Configure `config.ini` with your Helius API Key, RPC URLs, and Main Wallet Mnemonic.

3. **Running with Docker (Recommended):**
   ```bash
   docker build -t infinity-os .
   docker run -p 5000:5000 infinity-os
   ```

4. **Manual Start:**
   - **Frontend:** `cd frontend && npm install && npm run build`
   - **Backend:** `pip install -r requirements.txt && python3 main.py`

## ⚖️ Disclaimer
This tool is for educational and research purposes only. Use of automated trading bots involves high risk. The developers are not responsible for any financial losses.
