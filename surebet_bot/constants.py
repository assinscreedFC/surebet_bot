# ================================================================
#   CONSTANTS — Surebet Bot VDO Group
# ================================================================
#   Fichier centralisant TOUTES les constantes du projet.
#   Importé par config.py et les modules du projet.
# ================================================================


# ── API URLs ─────────────────────────────────────────────────────

ODDS_API_BASE_URL = "https://api.the-odds-api.com/v4"
TELEGRAM_API_URL = "https://api.telegram.org/bot{token}/{method}"


# ── RÉGIONS ──────────────────────────────────────────────────────
# Régions des bookmakers à interroger
# Disponibles: us, uk, eu, au, fr

REGIONS = "eu,fr"


# ── BOOKMAKERS CIBLES ────────────────────────────────────────────
# Noms officiels selon The Odds API
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

# Noms affichables pour chaque bookmaker (clé API → nom)
BOOKMAKER_DISPLAY_NAMES = {
    "betclic":       "Betclic",
    "unibet_fr":     "Unibet FR",
    "winamax_fr":    "Winamax FR",
    "pmu":           "PMU",
    "parionssport":  "Parions Sport",
    "netbet_fr":     "NetBet FR",
    "pinnacle":      "Pinnacle",
    "betway":        "Betway",
    "bet365":        "Bet365",
    "1xbet":         "1xBet",
}


# ── SPORTS & LIGUES ──────────────────────────────────────────────

FOOTBALL_LEAGUES = {
    "soccer_france_ligue_one":               "Ligue 1",
    "soccer_epl":                            "Premier League",
    "soccer_spain_la_liga":                   "La Liga",
    "soccer_italy_serie_a":                   "Serie A",
    "soccer_germany_bundesliga":              "Bundesliga",
    "soccer_brazil_campeonato":               "Brasileirão",
    "soccer_turkey_super_league":             "Superlig",
    "soccer_portugal_primeira_liga":          "Liga Portugal",
    "soccer_uefa_champs_league":              "Champions League",
    "soccer_uefa_europa_league":              "Europa League",
    "soccer_uefa_europa_conference_league":   "Conference League",
    "soccer_fa_cup":                          "FA Cup",
    "soccer_england_efl_cup":                 "Carabao Cup",
    "soccer_spain_copa_del_rey":              "Copa del Rey",
    "soccer_france_coupe_de_france":          "Coupe de France",
    "soccer_italy_coppa_italia":              "Coupe d'Italie",
    "soccer_germany_dfb_pokal":              "DFB Pokal",
    "soccer_usa_mls":                         "MLS",
}

BASKETBALL_LEAGUES = {
    "basketball_nba": "NBA",
}

TENNIS_TOURNAMENTS = {
    "tennis_atp_us_open":          "US Open",
    "tennis_atp_wimbledon":        "Wimbledon",
    "tennis_atp_french_open":      "Roland Garros",
    "tennis_atp_aus_open_singles": "Australian Open",
}

NFL_LEAGUES = {
    "americanfootball_nfl": "NFL",
}

# Fusion de tous les sports
ALL_SPORTS = {
    **FOOTBALL_LEAGUES,
    **BASKETBALL_LEAGUES,
    **TENNIS_TOURNAMENTS,
    **NFL_LEAGUES,
}


# ── MARCHÉS ──────────────────────────────────────────────────────

# Marchés de base (disponibles pour tous les sports via /sports/{sport}/odds)
BASE_MARKETS = [
    "h2h",       # Moneyline / 1X2
    "spreads",   # Handicap
    "totals",    # Over/Under
]

# Marchés Football (via /events/{eventId}/odds)
# Player props limités à: EPL, Ligue 1, Bundesliga, Serie A, La Liga, MLS
FOOTBALL_PLAYER_PROPS = [
    "player_goal_scorer_anytime",   # Buteur
    "player_first_goal_scorer",     # Premier buteur
    "player_shots",                  # Tirs
    "player_shots_on_target",       # Tirs cadrés
]

# Marchés Basketball (NBA — via /events/{eventId}/odds)
BASKETBALL_PLAYER_PROPS = [
    "player_points",
    "player_rebounds",
    "player_assists",
    "player_threes",
    "player_points_rebounds_assists",
]

# Marchés NFL (via /events/{eventId}/odds)
NFL_PLAYER_PROPS = [
    "player_pass_tds",
    "player_pass_yds",
    "player_rush_yds",
    "player_reception_yds",
    "player_anytime_td",
]


# ── TIMINGS ──────────────────────────────────────────────────────

SCAN_INTERVAL = 10       # secondes entre chaque cycle complet
REQUEST_DELAY = 3        # secondes entre chaque requête API (rate limit)
COOLDOWN_MINUTES = 5     # anti-doublon d'alertes (minutes)


# ── DASHBOARD ────────────────────────────────────────────────────

DASHBOARD_HOST = "0.0.0.0"
DASHBOARD_PORT = 8501


# ── DIVERS ───────────────────────────────────────────────────────

API_KEY_LENGTH = 32          # Longueur attendue d'une clé API
MAX_RETRY_BACKOFF_MIN = 10   # Backoff max entre retries (minutes)
SUREBET_HISTORY_LIMIT = 1000 # Nombre max de surebets en mémoire
LOW_QUOTA_THRESHOLD = 50     # Seuil d'alerte quota bas
GENERATION_TIMEOUT = 600     # Timeout génération de clé (secondes)


# ── SCHEDULING ──────────────────────────────────────────────
# Créneaux temporels stratégiques pour la détection de surebets.
# Les créneaux sont évalués par ordre de priorité (SLOT_PRIORITY).
# Le premier créneau correspondant à jour+heure est retourné.

SCHEDULE_SLOTS = {
    "live_weekend": {
        "days": [5, 6],                # samedi=5, dimanche=6
        "hours": (14, 22),             # 14h00 - 22h00
        "scan_interval": 5,            # Scan très agressif (5s)
        "label": "🔴 LIVE Week-end",
        "description": "Volume massif de matchs en Live",
    },
    "evening_weekday": {
        "days": [0, 1, 2, 3, 4],       # lundi-vendredi
        "hours": (19, 21),             # 19h00 - 21h00
        "scan_interval": 5,            # Scan agressif
        "label": "🌙 Soir Semaine",
        "description": "Matchs européens et ajustements dernière minute",
    },
    "boosted_odds": {
        "days": [0, 1, 2, 3, 4, 5, 6], # tous les jours
        "hours": (17, 20),             # 17h00 - 20h00
        "scan_interval": 7,            # Scan rapide
        "label": "🚀 Cotes Boostées",
        "description": "Winamax/Unibet sortent les cotes boostées",
    },
    "morning_realignment": {
        "days": [0, 1, 2, 3, 4, 5, 6], # tous les jours
        "hours": (9, 10),              # 09h00 - 10h00
        "scan_interval": 8,            # Scan modéré
        "label": "☀️ Réalignement Matin",
        "description": "Réalignement des cotes sur les marchés mondiaux",
    },
    "default": {
        "days": [0, 1, 2, 3, 4, 5, 6],
        "hours": (0, 24),
        "scan_interval": 15,           # Scan calme
        "label": "💤 Hors-créneau",
        "description": "Période calme, scan de routine",
    },
}

# Ordre d'évaluation des créneaux (du plus prioritaire au moins)
SLOT_PRIORITY = [
    "live_weekend",
    "evening_weekday",
    "boosted_odds",
    "morning_realignment",
    "default",
]

# Sports prioritaires par créneau (préfixes avec * wildcard)
SPORT_PRIORITY = {
    "live_weekend":        ["soccer_*", "basketball_*", "tennis_*"],
    "evening_weekday":     ["soccer_*", "basketball_*"],
    "boosted_odds":        ["soccer_*"],
    "morning_realignment": ["basketball_*", "americanfootball_*", "soccer_*"],
    "default":             ["*"],
}

# Seuil en minutes avant le match pour l'alerte composition
LINEUP_ALERT_MINUTES = 60
