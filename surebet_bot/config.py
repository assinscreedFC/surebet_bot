# Configuration Bot Surebet VDO Group

import os
from pathlib import Path
from dotenv import load_dotenv

# Charger les variables d'environnement depuis .env
load_dotenv()

# === CHEMINS ===
BASE_DIR = Path(__file__).parent
API_KEYS_FILE = BASE_DIR / "api_keys.txt"
LOG_FILE = BASE_DIR / "bot.log"
DB_FILE = BASE_DIR / "surebet.db"

# === SCAN ===
SCAN_INTERVAL = 10  # secondes
COOLDOWN_MINUTES = 5  # anti-doublon d'alertes

# === TELEGRAM ===
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# Validation des variables d'environnement requises
if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
    raise ValueError(
        "TELEGRAM_BOT_TOKEN et TELEGRAM_CHAT_ID doivent être définis "
        "dans les variables d'environnement ou dans un fichier .env"
    )

# === DASHBOARD ===
DASHBOARD_HOST = "0.0.0.0"
DASHBOARD_PORT = 8501

# === BOOKMAKERS CIBLES ===
# Noms officiels selon l'API (région eu + fr)
# Docs: https://the-odds-api.com/sports-odds-data/bookmaker-apis.html
BOOKMAKERS = [
    "betclic",           # Betclic (FR)
    "unibet_fr",         # Unibet (FR)
    "winamax_fr",        # Winamax (FR)
    "pmu",               # PMU (FR)
    "parionssport",      # Parions Sport (FR)
    "netbet_fr",         # NetBet (FR)
    "pinnacle",          # Pinnacle (EU)
    "betway",            # Betway (UK)
    "bet365",            # Bet365
    "1xbet",             # 1xBet (EU)
]

# Régions à utiliser (fr = bookmakers français)
REGIONS = "eu,fr"


# === SPORTS & LIGUES ===
FOOTBALL_LEAGUES = {
    "soccer_france_ligue_one": "Ligue 1",
    "soccer_epl": "Premier League",
    "soccer_spain_la_liga": "La Liga",
    "soccer_italy_serie_a": "Serie A",
    "soccer_germany_bundesliga": "Bundesliga",
    "soccer_brazil_serie_a": "Serie A Brésil",
    "soccer_turkey_super_league": "Superlig",
    "soccer_portugal_primeira_liga": "Liga Portugal",
    "soccer_uefa_champs_league": "Champions League",
    "soccer_uefa_europa_league": "Europa League",
    "soccer_uefa_conference_league": "Conference League",
    "soccer_england_fa_cup": "FA Cup",
    "soccer_england_efl_cup": "Carabao Cup",
    "soccer_spain_copa_del_rey": "Copa del Rey",
    "soccer_france_coupe_de_france": "Coupe de France",
    "soccer_italy_coppa_italia": "Coupe d'Italie",
    "soccer_germany_dfb_pokal": "DFB Pokal",
    "soccer_usa_mls": "MLS",
}

BASKETBALL_LEAGUES = {
    "basketball_nba": "NBA",
}

TENNIS_TOURNAMENTS = {
    "tennis_atp_us_open": "US Open",
    "tennis_atp_wimbledon": "Wimbledon",
    "tennis_atp_french_open": "Roland Garros",
    "tennis_atp_australian_open": "Australian Open",
}

NFL_LEAGUES = {
    "americanfootball_nfl": "NFL",
}

# Tous les sports
ALL_SPORTS = {
    **FOOTBALL_LEAGUES,
    **BASKETBALL_LEAGUES,
    **TENNIS_TOURNAMENTS,
    **NFL_LEAGUES,
}

# === MARCHÉS ===
# Marchés de base (disponibles pour tous les sports)
BASE_MARKETS = [
    "h2h",       # Moneyline / 1X2
    "spreads",   # Handicap (principalement sports US)
    "totals",    # Over/Under (principalement sports US)
]

# Marchés Football (via endpoint /events/{eventId}/odds)
# Player props limités à: EPL, Ligue 1, Bundesliga, Serie A, La Liga, MLS
FOOTBALL_PLAYER_PROPS = [
    "player_goal_scorer_anytime",   # Buteur
    "player_first_goal_scorer",     # Premier buteur
    "player_shots",                  # Tirs (limité)
    "player_shots_on_target",       # Tirs cadrés (limité)
]

# Marchés Basketball (NBA - disponibles via /events/{eventId}/odds)
BASKETBALL_PLAYER_PROPS = [
    "player_points",
    "player_rebounds",
    "player_assists",
    "player_threes",
    "player_points_rebounds_assists",
]

# Marchés NFL (disponibles via /events/{eventId}/odds)
NFL_PLAYER_PROPS = [
    "player_pass_tds",
    "player_pass_yds",
    "player_rush_yds",
    "player_reception_yds",
    "player_anytime_td",
]

# === THE ODDS API ===
ODDS_API_BASE_URL = "https://api.the-odds-api.com/v4"

# NOTE: Les Player Props nécessitent:
# 1. D'abord récupérer les events via /sports/{sport}/events
# 2. Puis récupérer les odds via /sports/{sport}/events/{eventId}/odds?markets=player_xxx
# Les marchés de base (h2h, spreads, totals) fonctionnent via /sports/{sport}/odds

