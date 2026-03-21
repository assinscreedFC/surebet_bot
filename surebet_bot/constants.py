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

REGIONS = "eu,fr,uk"


# ── BOOKMAKERS CIBLES ────────────────────────────────────────────
# Noms officiels selon The Odds API
# Docs: https://the-odds-api.com/sports-odds-data/bookmaker-apis.html

BOOKMAKERS = [
    "betclic_fr",        # Betclic (FR)
    "unibet_fr",         # Unibet (FR)
    "winamax_fr",        # Winamax (FR)
    "pmu_fr",            # PMU (FR)
    "parionssport_fr",   # Parions Sport (FR)
    "netbet_fr",         # NetBet (FR)
    "pinnacle",          # Pinnacle (EU)
    "betway",            # Betway (UK)
    "bet365",            # Bet365
    "onexbet",           # 1xBet (EU)
    #"winamax_de",        # Winamax (DE)
    #"tipico_de",         # Tipico (DE)
    "mybookieag",        # MyBookie
    "sport888",          # 888sport
    "betfair_ex_eu",     # Betfair Exchange (EU)
    #"unibet_se",         # Unibet (SE)
    #"leovegas_se",       # LeoVegas (SE)
    #"unibet_nl",         # Unibet (NL)
    "betsson",           # Betsson
]

# Noms affichables pour chaque bookmaker (clé API → nom)
BOOKMAKER_DISPLAY_NAMES = {
    "betclic_fr":    "Betclic",
    "unibet_fr":     "Unibet FR",
    "winamax_fr":    "Winamax",
    "pmu_fr":        "PMU",
    "parionssport_fr":"Parions Sport",
    "netbet_fr":     "NetBet",
    "pinnacle":      "Pinnacle",
    "betway":        "Betway",
    "bet365":        "Bet365",
    "onexbet":       "1xBet",
    "winamax_de":    "Winamax DE",
    "tipico_de":     "Tipico DE",
    "mybookieag":    "MyBookie",
    "betclic_fr":    "Betclic FR",
    "sport888":      "888sport",
    "betfair_ex_eu": "Betfair Exchange EU",
    "unibet_se":     "Unibet SE",
    "leovegas_se":   "LeoVegas SE",
    "unibet_nl":     "Unibet NL",
    "betsson":       "Betsson",
}


# ── SPORTS & LIGUES ──────────────────────────────────────────────

FOOTBALL_LEAGUES = {
    # Top 5 ligues européennes
    "soccer_epl":                            "Premier League",
    "soccer_spain_la_liga":                  "La Liga",
    "soccer_italy_serie_a":                  "Serie A",
    "soccer_germany_bundesliga":             "Bundesliga",
    "soccer_france_ligue_one":               "Ligue 1",
    # Compétitions européennes majeures
    "soccer_uefa_champs_league":             "Champions League",
    "soccer_uefa_europa_league":             "Europa League",
    "soccer_uefa_europa_conference_league":  "Conference League",
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
REQUEST_DELAY = 10       # secondes entre chaque requête API (rate limit)
COOLDOWN_MINUTES = 5     # anti-doublon d'alertes (minutes)


# ── LIENS BOOKMAKERS ─────────────────────────────────────────────
# URLs vers la section sport de chaque bookmaker (pour les alertes Telegram cliquables)

BOOKMAKER_URLS = {
    "Betclic":        "https://www.betclic.fr/football-s1",
    "Unibet":         "https://www.unibet.fr/paris-sportifs",
    "Winamax":        "https://www.winamax.fr/paris-sportifs",
    "PMU":            "https://www.pmu.fr/sport/football",
    "Parions Sport":  "https://www.enligne.parionssport.fdj.fr",
    "Betway":         "https://betway.com/fr/sports",
    "Bet365":         "https://www.bet365.com",
    "1xBet":          "https://1xbet.com/fr/sport/football",
    "Betsson":        "https://www.betsson.com/fr-fr/paris-sportifs",
    "NetBet":         "https://www.netbet.fr/football",
    "Betfair":        "https://www.betfair.fr/exchange",
    "888sport":       "https://www.888sport.fr",
    "Pinnacle":       "https://www.pinnacle.com/fr/soccer/matchups",
    "MyBookie":       "https://mybookie.ag",
}


# ── DASHBOARD ────────────────────────────────────────────────────

DASHBOARD_HOST = "0.0.0.0"
DASHBOARD_PORT = 8501


# ── DIVERS ───────────────────────────────────────────────────────

MIN_PROFIT_PCT = 1.0         # Profit minimum requis (%) pour envoyer une alerte

# ── VALUE BET ─────────────────────────────────────────────────────
VALUE_BET_MIN_THRESHOLD    = 0.03   # 3% de value minimum pour alerter
VALUE_BET_MIN_BOOKMAKERS   = 4      # Nb min de bookmakers pour consensus fiable
VALUE_BET_COOLDOWN_MINUTES = 10     # Cooldown value bets (plus long que surebets)
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
    "nfl_night": {
        "days": [0, 3, 6],             # lundi, jeudi, dimanche (prime time NFL USA = 1h-4h CET)
        "hours": (1, 4),               # 01h00 - 04h00 CET
        "scan_interval": 7,            # Scan rapide
        "label": "🏈 NFL Nuit",
        "description": "Matchs NFL en direct depuis les USA",
    },
    "evening_weekday": {
        "days": [0, 1, 2, 3, 4],       # lundi-vendredi
        "hours": (19, 21),             # 19h00 - 21h00
        "scan_interval": 5,            # Scan agressif
        "label": "🌙 Soir Semaine",
        "description": "Matchs européens et ajustements dernière minute",
    },
    "late_evening": {
        "days": [0, 1, 2, 3, 4],       # lundi-vendredi
        "hours": (21, 23),             # 21h00 - 23h00 : fin CL + tip-off NBA
        "scan_interval": 7,            # Scan rapide
        "label": "🌃 Soirée Tardive",
        "description": "Fin des matchs européens + début NBA",
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
    "nfl_night",
    "evening_weekday",
    "late_evening",
    "boosted_odds",
    "morning_realignment",
    "default",
]

# Sports prioritaires par créneau (préfixes avec * wildcard)
SPORT_PRIORITY = {
    "live_weekend":        ["soccer_*", "basketball_*", "tennis_*"],
    "nfl_night":           ["americanfootball_*", "basketball_*"],
    "evening_weekday":     ["soccer_*", "basketball_*", "tennis_*"],
    "late_evening":        ["soccer_*", "basketball_*"],
    "boosted_odds":        ["soccer_*", "tennis_*"],
    "morning_realignment": ["soccer_*", "basketball_*", "americanfootball_*"],
    # Hors-créneau : seulement les ligues les plus liquides pour économiser le quota
    "default": [
        "soccer_epl", "soccer_spain_la_liga", "soccer_italy_serie_a",
        "soccer_germany_bundesliga", "soccer_france_ligue_one",
        "soccer_uefa_champs_league", "basketball_nba", "americanfootball_nfl",
    ],
}

# Seuil en minutes avant le match pour l'alerte composition
LINEUP_ALERT_MINUTES = 60
