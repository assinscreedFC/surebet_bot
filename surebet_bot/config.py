# Configuration Bot Surebet VDO Group

import os
from pathlib import Path
from dotenv import load_dotenv

# Charger les variables d'environnement depuis .env
load_dotenv()

# === IMPORTER TOUTES LES CONSTANTES ===
from constants import (
    # API
    ODDS_API_BASE_URL,
    TELEGRAM_API_URL,
    # Bookmakers
    BOOKMAKERS,
    BOOKMAKER_DISPLAY_NAMES,
    REGIONS,
    # Sports
    FOOTBALL_LEAGUES,
    BASKETBALL_LEAGUES,
    TENNIS_TOURNAMENTS,
    NFL_LEAGUES,
    ALL_SPORTS,
    # Marchés
    BASE_MARKETS,
    FOOTBALL_PLAYER_PROPS,
    BASKETBALL_PLAYER_PROPS,
    NFL_PLAYER_PROPS,
    # Timings
    SCAN_INTERVAL,
    REQUEST_DELAY,
    COOLDOWN_MINUTES,
    # Dashboard
    DASHBOARD_HOST,
    DASHBOARD_PORT,
    # Divers
    API_KEY_LENGTH,
    MAX_RETRY_BACKOFF_MIN,
    SUREBET_HISTORY_LIMIT,
    LOW_QUOTA_THRESHOLD,
    GENERATION_TIMEOUT,
)

# === CHEMINS (dynamiques, restent dans config) ===
BASE_DIR = Path(__file__).parent
API_KEYS_FILE = BASE_DIR / "api_keys.txt"
LOG_FILE = BASE_DIR / "bot.log"
DB_FILE = BASE_DIR / "surebet.db"

# === TELEGRAM (depuis .env) ===
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# Validation des variables d'environnement requises
if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
    raise ValueError(
        "TELEGRAM_BOT_TOKEN et TELEGRAM_CHAT_ID doivent être définis "
        "dans les variables d'environnement ou dans un fichier .env"
    )
