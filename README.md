# 🎯 Surebet & Arbitrage Bot

<div align="center">
  <p><strong>Automated multi-sports arbitrage (Surebet) detection bot with real-time Telegram notifications</strong></p>

  [![Python](https://img.shields.io/badge/Python-3.10%2B-blue?style=for-the-badge&logo=python)](https://www.python.org/)
  [![Streamlit](https://img.shields.io/badge/Streamlit-1.30%2B-FF4B4B?style=for-the-badge&logo=streamlit)](https://streamlit.io/)
  [![SQLite](https://img.shields.io/badge/SQLite-3-003B57?style=for-the-badge&logo=sqlite)](https://www.sqlite.org/)

  ![Status](https://img.shields.io/badge/Status-Active-success?style=flat-square)
  ![Version](https://img.shields.io/badge/Version-1.0.0-blue?style=flat-square)
</div>

## 📋 Overview

**Surebet & Arbitrage Bot** is a sophisticated Python application designed to identify and exploit arbitrage opportunities (surebets) in sports betting markets. By analyzing odds from multiple bookmakers in real-time, the bot guarantees mathematical profit regardless of match outcomes.

- 📊 **Smart Scanning** of h2h, totals (Over/Under), and spreads markets
- 🚀 **High Performance** with asynchronous processing for ultra-fast reaction
- 📱 **Instant Alerts** on Telegram with precise stake calculations
- 📈 **Data Visualization** via a comprehensive interactive dashboard
- 🔄 **Automatic Failover** between API keys for maximum availability

## ✨ Features

### Core Features
- **Automatic Scan**: Continuous monitoring of markets every 10 seconds.
- **Multi-Sports & Leagues**: Full support for Football, NBA, NFL, and Tennis.
- **Multi-Bookmakers**: Comparison between Betclic, Winamax, Unibet, PMU, Pinnacle, and more.
- **Arbitrage Detection**: Mathematical algorithms for Moneyline (H2H), Totals, and Spreads.
- **Live Dashboard**: Real-time Streamlit interface for tracking opportunities.

### Advanced Features
- **API Failover**: Automatic switching to backup keys if quotas are exhausted.
- **Stake Calculator**: Precise indication of amounts to bet on each outcome to secure profit.
- **Database**: Complete history of detected opportunities via SQLite.
- **Rich Notifications**: Detailed Telegram alerts (Profitability, Odds, Suggested Stakes).

## 🚀 Quick Start

### Prerequisites
- **Python 3.10+** and pip
- **The Odds API** Keys
- **Telegram Bot Token**

### Installation

1. **Clone the project**
   ```bash
  git clone https://github.com/assinscreedFC/surebet_bot
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **API Keys Configuration**
   Create an `api_keys.txt` file at the root:
   ```text
   email@example.com:your_32_character_api_key
   ```
   > Get a free key: [The Odds API](https://the-odds-api.com)

4. **Environment Configuration**
   Create a `.env` file or configure `config.py`:
   ```env
   TELEGRAM_BOT_TOKEN=your_token
   TELEGRAM_CHAT_ID=your_chat_id
   ```

## 📖 Usage

### Start the Bot
To start scanning and notifications:
```bash
python main.py
```

### Start the Dashboard
To visualize data in real-time:
```bash
python main.py --dashboard
```
Then access `http://localhost:8501` in your browser.

### Test
To perform a single verification scan:
```bash
python test_bot.py
```

## 🛠 Tech Stack

- **Language**: Python 3.10+
- **Core**: `asyncio`, `aiohttp` for fast asynchronous requests.
- **Data**: `pandas` for processing, `aiosqlite` for storage.
- **UI**: `Streamlit` with `plotly` for interactive charts.
- **API**: Full integration of The Odds API v4.
- **Logging**: Complete logging system for debugging.

## 📊 How it works

### Surebet Mathematics
A **surebet** exists when the sum of implied probabilities is less than 1.

```math
L = \frac{1}{\text{Odds}_{A}} + \frac{1}{\text{Odds}_{B}}
```

**If L < 1 → SUREBET DETECTED!**
> Profit = (1 - L) × 100%

### Concrete Example
- **Match**: PSG vs Marseille
- **Betclic**: Over 2.5 @ **2.10**
- **Winamax**: Under 2.5 @ **2.10**
- **Calculation**: (1/2.10) + (1/2.10) = 0.476 + 0.476 = **0.952**
- **Result**: 0.952 < 1 → **4.8% Guaranteed Profit!**

### Telegram Alert Format
```
🚀 SUREBET OPPORTUNITY DETECTED 🚀
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🏆 Sport: Football - Ligue 1
⚽ Match: PSG vs Marseille
📊 Market: Totals 2.5

✅ Betclic | Over 2.5 | 2.10 | Stake: 47.62€
✅ Winamax | Under 2.5 | 2.10 | Stake: 52.38€

📈 Profit: 5.04%
💰 Gain base 100€: 5.04€
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Surebet Bot
```

## 🏆 Supported Sports

### ⚽ Football - 17 Leagues
The bot actively monitors the following **17 major leagues**:

| Region | Leagues & Cups |
| :--- | :--- |
| **🇪🇺 Europe** | Champions League, Europa League, Conference League |
| **🇫🇷 France** | Ligue 1, Coupe de France |
| **🇬🇧 England** | Premier League, FA Cup, Carabao Cup |
| **🇪🇸 Spain** | La Liga, Copa del Rey |
| **🇮🇹 Italy** | Serie A, Coppa Italia |
| **🇩🇪 Germany** | Bundesliga, DFB Pokal |
| **🇵🇹 Portugal** | Liga Portugal |
| **🇹🇷 Turkey** | Superlig |
| **🇧🇷 Brazil** | Serie A |
| **🇺🇸 USA** | MLS |

### 🏀 Basketball & 🏈 US Sports
- NBA
- NFL

### 🎾 Tennis
- Grand Slams (US Open, Wimbledon, French Open, Australian Open)

## 📁 Project Structure

```
surebet_bot/
├── main.py              # Unified entry point
├── config.py            # Centralized configuration
├── test_bot.py          # Test script
├── api_keys.txt         # API keys storage
│
├── core/                # System core
│   ├── api_manager.py   # Key manager & Failover
│   ├── calculator.py    # Arbitrage calculation engine
│   ├── odds_client.py   # The Odds API client
│   └── scanner.py       # Scan orchestrator
│
├── data/                # Data layer
│   └── database.py      # SQLite management
│
├── notifications/       # Alert system
│   └── telegram_bot.py  # Telegram Bot
│
├── dashboard/           # User interface
│   └── app.py           # Streamlit application
│
└── utils/               # Utilities
    └── logger.py        # Logging system
```

## 🔧 The Odds API Details

The bot uses The Odds API v4:
- `GET /sports`: Retrieving active sports
- `GET /odds`: Retrieving odds (h2h, spreads, totals)
- `GET /events`: Retrieving events for Player Props

## 🤝 Contributing

We welcome contributions! Here's how you can help:

1. **Fork** the repository
2. **Create** a feature branch (`git checkout -b feature/amazing-feature`)
3. **Make** your changes
4. **Test** the changes thoroughly
5. **Commit** your changes (`git commit -m 'Add amazing feature'`)
6. **Push** to the branch (`git push origin feature/amazing-feature`)
7. **Open** a Pull Request

### Development Guidelines

- Follow **PEP 8** coding standards for Python
- Document your code (docstrings)
- Write tests for new features
- Update documentation as needed

## 📝 License

Copyright © 2024. All rights reserved.
Internal usage only.

---
<div align="center">
  <p>Built with ❤️ for financial optimization</p>
</div>
