# Surebet & Arbitrage Bot

Automated multi-sports arbitrage (Surebet) detection bot with real-time Telegram notifications and autonomous API registration.

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue?style=flat)](https://www.python.org/)
[![Status](https://img.shields.io/badge/Status-Active-success?style=flat)]()
[![License](https://img.shields.io/badge/License-Proprietary-red?style=flat)]()

## Overview

**Surebet & Arbitrage Bot** is a Python application designed to identify and exploit arbitrage opportunities (surebets) in sports betting markets. By analyzing odds from multiple bookmakers in real-time, the bot guarantees mathematical profit regardless of match outcomes.

Core features:
- Smart scanning of head-to-head, totals (Over/Under), and spreads markets
- High performance with asynchronous processing for fast reaction times
- Instant alerts on Telegram with precise stake calculations
- Automated API key generation and registration on The Odds API
- Complete database history of detected opportunities
- Data visualization via interactive dashboard (Streamlit)

## Features

### Core Betting Features
- **Automatic Scan**: Continuous monitoring of markets with configurable intervals
- **Multi-Sports**: Football, Basketball (NBA), American Football (NFL), and Tennis
- **Multi-Bookmakers**: Comparison between Betclic, Winamax, Unibet, PMU, Pinnacle, and more
- **Arbitrage Detection**: Mathematical algorithms for Moneyline (H2H), Totals, and Spreads
- **Stake Calculator**: Precise indication of amounts to bet on each outcome to secure profit
- **Database**: Complete history of detected opportunities via SQLite
- **Rich Notifications**: Detailed Telegram alerts with profitability, odds, and suggested stakes

### Automation Features
- **Autonomous API Registration**: Automatic account creation on The Odds API with CAPTCHA solving
- **Audio CAPTCHA Solving**: Extracts and solves audio CAPTCHAs using OpenAI Whisper API
- **Browser Automation**: Stealth browser profiles with Firefox persistence
- **Email Management**: Temporary email support for account creation
- **Telegram Relay**: Real-time status updates during automation processes

### Advanced Features
- **API Failover**: Automatic switching to backup keys if quotas are exhausted
- **Smart Scheduler**: Intelligent scheduling of API requests to maximize coverage
- **Live Dashboard**: Real-time Streamlit interface for tracking opportunities

## Quick Start

### Prerequisites
- Python 3.10+
- The Odds API key (or use autonomous registration)
- Telegram Bot Token and Chat ID
- (Optional) OpenAI API key for CAPTCHA audio solving

### Installation

1. Clone the repository
```bash
git clone https://github.com/assinscreedFC/surebet_bot
cd surebet_bot
```

2. Create and activate a virtual environment
```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

3. Install dependencies
```bash
pip install aiohttp asyncio-contextmanager python-dotenv requests faker
```

For browser automation and CAPTCHA solving (optional):
```bash
pip install scrapling openai
```

4. Configure environment variables

Create a `.env` file in the project root:
```env
# Telegram Configuration
TELEGRAM_BOT_TOKEN=your_token
TELEGRAM_CHAT_ID=your_chat_id

# Optional: API Key generation
OPENAI_API_KEY=your_openai_key
OPENAI_BASE_URL=https://your-api-endpoint/v1
WHISPER_MODEL=whisper-1
LLM_MODEL=your-llm-model

# The Odds API (can be auto-generated)
ODDS_API_KEYS=key1:key2:key3
```

5. (Optional) Generate API keys automatically
```bash
python generateur_api_manuel.py
```

This will interactively create accounts on The Odds API and populate `api_keys.txt`.

## Usage

### Start the Bot

Run continuous arbitrage scanning:
```bash
python surebet_bot/main.py
```

This will:
- Load or generate API keys
- Connect to Telegram
- Start scanning configured sports/leagues every 10 seconds
- Send alerts for detected surebets
- Log all activity to `bot.log`

### Start the Dashboard

View real-time opportunities in a web interface:
```bash
python surebet_bot/main.py --dashboard
```

Then access `http://localhost:8501` in your browser.

### Manual API Registration

Register a new The Odds API account autonomously:
```bash
python generateur_api_manuel.py
```

Features:
- Automatic name/email generation
- Audio CAPTCHA solving (requires OpenAI API)
- Browser automation with stealth profiles
- Telegram notifications during process

### Test Mode

Verify bot functionality with a single scan:
```bash
python surebet_bot/test_bot.py
```

## Project Structure

```
surebet_bot/
├── main.py                      # Bot entry point
├── config.py                    # Centralized configuration
├── constants.py                 # All constants (sports, markets, leagues)
├── test_bot.py                  # Test script
├── api_keys.txt                 # API keys storage (auto-generated)
│
├── core/                        # Core arbitrage engine
│   ├── api_manager.py          # API key management & failover
│   ├── calculator.py           # Arbitrage calculation engine
│   ├── odds_client.py          # The Odds API v4 client
│   ├── scanner.py              # Market scanning orchestrator
│   └── scheduler.py            # Smart request scheduling
│
├── data/                        # Data persistence
│   └── database.py             # SQLite opportunity history
│
├── notifications/              # Alert system
│   └── telegram_bot.py         # Telegram Bot
│
├── automation/                 # API account creation automation
│   ├── registration.py         # Account registration workflow
│   ├── captcha_handler.py      # CAPTCHA detection & solving
│   ├── mail_tm.py              # Temporary email integration
│   ├── browser_storage.py      # Browser profile management
│   ├── audio_solver.py         # Audio CAPTCHA solver (Whisper)
│   └── telegram_relay.py       # Status notifications during automation
│
├── dashboard/                  # User interface
│   └── app.py                  # Streamlit application
│
└── utils/                      # Utilities
    └── logger.py               # Logging system
```

## Tech Stack

- **Language**: Python 3.10+
- **Async**: `asyncio`, `aiohttp` for non-blocking I/O
- **Data**: `pandas` for processing, `aiosqlite` for storage
- **UI**: `Streamlit` with `plotly` for interactive charts
- **API**: Full integration with The Odds API v4
- **Automation**: `scrapling` for stealth browser automation (optional)
- **CAPTCHA**: OpenAI Whisper API for audio transcription
- **Email**: Temporary email providers for automation
- **Logging**: Python built-in logging with file persistence

## How It Works

### Surebet Mathematics

A **surebet** exists when the sum of implied probabilities is less than 1.

```
L = 1/Odds_A + 1/Odds_B

If L < 1 → SUREBET DETECTED!
Profit = (1 - L) × 100%
```

**Example:**
- Match: PSG vs Marseille
- Betclic: Over 2.5 @ 2.10
- Winamax: Under 2.5 @ 2.10
- Calculation: (1/2.10) + (1/2.10) = 0.476 + 0.476 = 0.952
- Result: 0.952 < 1 → **4.8% Guaranteed Profit!**

### Telegram Alert Format

```
SUREBET OPPORTUNITY DETECTED
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Sport: Football - Ligue 1
Match: PSG vs Marseille
Market: Totals 2.5

Betclic | Over 2.5 | 2.10 | Stake: 47.62€
Winamax | Under 2.5 | 2.10 | Stake: 52.38€

Profit: 5.04%
Gain on 100€: 5.04€
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

### Automation Workflow

The autonomous registration process:
1. Generate random realistic name and email
2. Create temporary email inbox
3. Navigate to The Odds API registration page (Scrapling)
4. Fill form fields
5. Detect and solve CAPTCHA:
   - Extract audio CAPTCHA file
   - Transcribe with OpenAI Whisper API
   - Pass transcription to LLM for validation
   - Inject token into form
6. Complete registration
7. Extract API key from confirmation email
8. Store key in `api_keys.txt`
9. Send Telegram notification

## Supported Sports

### Football (17 Leagues)
- European: Champions League, Europa League, Conference League
- France: Ligue 1, Coupe de France
- England: Premier League, FA Cup, Carabao Cup
- Spain: La Liga, Copa del Rey
- Italy: Serie A, Coppa Italia
- Germany: Bundesliga, DFB Pokal
- Portugal: Liga Portugal
- Turkey: Superlig
- Brazil: Serie A
- USA: MLS

### Basketball & US Sports
- NBA
- NFL

### Tennis
- Grand Slams (US Open, Wimbledon, French Open, Australian Open)

## Configuration

Key settings in `config.py`:
- `SCAN_INTERVAL`: How often to check markets (default: 10 seconds)
- `REQUEST_DELAY`: Delay between API requests to respect rate limits
- `COOLDOWN_MINUTES`: Cooldown between duplicate surebet alerts
- `BOOKMAKERS`: List of bookmakers to monitor
- `FOOTBALL_LEAGUES`, `BASKETBALL_LEAGUES`, etc.: Sports configuration

For automation:
- `GENERATION_TIMEOUT`: Max time to wait for API key generation
- `OPENAI_API_KEY`: For CAPTCHA audio solving
- `TELEGRAM_BOT_TOKEN`: For automation status updates

## Known Issues

See `PROJECT_STATUS.md` for:
- API routes not yet tested
- Arbitrage detection algorithm validation needed
- Registration script optimization required
- Audio CAPTCHA reliability depends on network latency

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/improvement`)
3. Make your changes
4. Test thoroughly
5. Commit with clear messages
6. Push to your branch
7. Open a Pull Request

Follow PEP 8 coding standards and document your code with docstrings.

## License

Copyright 2024. All rights reserved.
Internal usage only.

---

Built for financial optimization through arbitrage detection.
