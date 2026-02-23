#!/usr/bin/env python3
"""
=================================================================
  TEST COMPLET — RÉCUPÉRATION DES COTES PAR FOURNISSEUR
  + SIMULATION DU PIPELINE D'ARBITRAGE
=================================================================
  Ce script teste le pipeline complet du bot surebet:
  
  ÉTAPE 1 : Validation des sports configurés
  ÉTAPE 2 : Récupération des cotes (avec failover sur toutes les clés)
  ÉTAPE 3 : Listing détaillé par fournisseur (bookmaker)
  ÉTAPE 4 : Matrice fournisseurs × sports
  ÉTAPE 5 : Simulation pipeline complète
           — Chaque fournisseur × chaque ligue × chaque type de pari
  
  Sortie: console + fichier test_odds_providers.log
=================================================================
"""

import asyncio
import sys
import json
import logging
import random
from pathlib import Path
from datetime import datetime
from collections import defaultdict

# Setup path
SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

# ── Logger ───────────────────────────────────────────────────────

LOG_FILE = SCRIPT_DIR / "test_odds_providers.log"

logger = logging.getLogger("test_odds_providers")
logger.setLevel(logging.DEBUG)

formatter = logging.Formatter(
    "[%(asctime)s] %(levelname)-7s │ %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

fh = logging.FileHandler(LOG_FILE, mode="w", encoding="utf-8")
fh.setLevel(logging.DEBUG)
fh.setFormatter(formatter)
logger.addHandler(fh)

ch = logging.StreamHandler(sys.stdout)
ch.setLevel(logging.INFO)
ch.setFormatter(formatter)
logger.addHandler(ch)


# ── Utilitaires ──────────────────────────────────────────────────

class TestResults:
    """Collecteur de résultats de test."""
    def __init__(self):
        self.tests = []
        self.passed = 0
        self.failed = 0
        self.warnings = 0

    def add(self, name: str, passed: bool, details: str = "", warning: bool = False):
        status = "⚠️ WARN" if warning else ("✅ PASS" if passed else "❌ FAIL")
        self.tests.append({"name": name, "status": status, "details": details})
        if warning:
            self.warnings += 1
        elif passed:
            self.passed += 1
        else:
            self.failed += 1
        logger.info(f"  {status} {name}")
        if details:
            for line in details.split("\n"):
                logger.info(f"       {line}")

    def summary(self):
        total = self.passed + self.failed + self.warnings
        logger.info("")
        logger.info("=" * 70)
        logger.info("  RÉSUMÉ FINAL")
        logger.info("=" * 70)
        logger.info(f"  Total: {total} tests")
        logger.info(f"  ✅ Passés:   {self.passed}")
        logger.info(f"  ❌ Échoués:  {self.failed}")
        logger.info(f"  ⚠️ Warnings: {self.warnings}")
        logger.info("=" * 70)
        if self.failed == 0:
            logger.info("  🎉 TOUS LES TESTS SONT PASSÉS!")
        else:
            logger.info(f"  ⚠️ {self.failed} TEST(S) ÉCHOUÉ(S):")
            for t in self.tests:
                if t["status"] == "❌ FAIL":
                    logger.info(f"    - {t['name']}: {t['details']}")
        return self.failed == 0


results = TestResults()


# ── Charger toutes les clés API ──────────────────────────────────

def load_all_api_keys():
    """Charge toutes les clés API depuis le fichier."""
    keys = []
    for f in [SCRIPT_DIR / "api_keys.txt", SCRIPT_DIR.parent / "api_keys.txt"]:
        if f.exists():
            with open(f, "r") as fh:
                for line in fh:
                    line = line.strip()
                    if ":" in line:
                        email, key = line.split(":", 1)
                        keys.append((email.strip(), key.strip()))
                    elif line and len(line) == 32:
                        keys.append(("unknown", line.strip()))
            break
    return keys


# ============================================================
#   ÉTAPE 1 : Validation des sports configurés
# ============================================================

async def step1_validate_sports(client):
    logger.info("")
    logger.info("═" * 70)
    logger.info("  ÉTAPE 1 — VALIDATION DES SPORTS CONFIGURÉS")
    logger.info("═" * 70)

    from constants import ALL_SPORTS

    resp = await client.get_sports(all_sports=True)
    results.add("Connexion API /sports", resp.success,
                f"HTTP {resp.status_code} | Quota restant: {resp.requests_remaining}")

    if not resp.success or not resp.data:
        results.add("Sports disponibles", False, f"Erreur: {resp.error}")
        return {}

    api_sports = {s["key"]: s for s in resp.data}
    logger.info(f"  📋 {len(api_sports)} sport(s) disponibles dans l'API")
    logger.info(f"  📋 {len(ALL_SPORTS)} sport(s) configurés dans le bot")

    valid_sports = {}
    invalid_sports = []

    for key, name in ALL_SPORTS.items():
        if key in api_sports:
            api_s = api_sports[key]
            active = api_s.get("active", False)
            valid_sports[key] = name
            status = "ACTIF" if active else "INACTIF"
            logger.debug(f"    ✓ {key:45s} → {name:20s} [{status}]")
        else:
            invalid_sports.append(key)
            logger.warning(f"    ✗ {key:45s} → {name:20s} [NON TROUVÉ]")

    results.add(
        "Sports configurés valides",
        len(valid_sports) > 0,
        f"Valides: {len(valid_sports)}/{len(ALL_SPORTS)}" +
        (f" | Invalides: {', '.join(invalid_sports)}" if invalid_sports else "")
    )

    return valid_sports


# ============================================================
#   ÉTAPE 2 : Récupération des cotes (avec failover)
# ============================================================

async def step2_fetch_odds(all_keys, sports: dict):
    logger.info("")
    logger.info("═" * 70)
    logger.info("  ÉTAPE 2 — RÉCUPÉRATION DES COTES EN LIVE")
    logger.info("═" * 70)

    from core.odds_client import OddsClient
    from constants import REGIONS

    # On teste un sous-ensemble pour ne pas exploser le quota
    priority = [
        "soccer_epl", "soccer_france_ligue_one",
        "basketball_nba", "soccer_spain_la_liga"
    ]
    test_sports = {k: sports[k] for k in priority if k in sports}
    if not test_sports:
        test_sports = dict(list(sports.items())[:3])

    logger.info(f"  🎯 Sports à tester: {list(test_sports.values())}")
    logger.info(f"  🔑 Clés API disponibles: {len(all_keys)}")

    all_odds_data = {}
    provider_stats = defaultdict(lambda: {"count": 0, "sports": set(), "markets": set()})
    working_client = None
    working_key_info = None

    # Essayer chaque clé jusqu'à en trouver une qui fonctionne
    for email, key in all_keys:
        logger.info(f"")
        logger.info(f"  🔑 Tentative avec clé: {key[:8]}... ({email})")

        client = OddsClient(key, request_delay=2.0)

        # Tester avec le premier sport
        first_key = list(test_sports.keys())[0]
        resp = await client.get_odds(sport=first_key, regions=REGIONS, markets="h2h")

        if resp.success:
            logger.info(f"  ✅ Clé {key[:8]}... fonctionne! Quota restant: {resp.requests_remaining}")
            working_client = client
            working_key_info = (email, key)

            # Traiter la première réponse
            if resp.data:
                all_odds_data[first_key] = resp.data
                for ev in resp.data:
                    for bm in ev.get("bookmakers", []):
                        bm_key = bm.get("key", "unknown")
                        provider_stats[bm_key]["count"] += 1
                        provider_stats[bm_key]["sports"].add(test_sports[first_key])
                        for m in bm.get("markets", []):
                            provider_stats[bm_key]["markets"].add(m.get("key", "?"))
            break
        else:
            logger.info(f"  ❌ Clé {key[:8]}... épuisée (HTTP {resp.status_code})")
            await client.close()

    if not working_client:
        results.add(
            "Connexion API /odds",
            False,
            f"Toutes les {len(all_keys)} clés sont épuisées (OUT_OF_USAGE_CREDITS)"
        )
        return {}, {}

    results.add(
        "Connexion API /odds",
        True,
        f"Clé active: {working_key_info[1][:8]}... ({working_key_info[0]})"
    )

    # Continuer avec les autres sports
    for sport_key, sport_name in test_sports.items():
        if sport_key in all_odds_data:
            continue  # Déjà récupéré

        logger.info(f"")
        logger.info(f"  ─── {sport_name} ({sport_key}) ───")

        # Tester h2h + totals
        resp = await working_client.get_odds(
            sport=sport_key, regions=REGIONS, markets="h2h,totals"
        )

        if not resp.success:
            results.add(f"Cotes {sport_name}", False,
                        f"HTTP {resp.status_code} | {resp.error}")
            continue

        events = resp.data or []
        results.add(f"Cotes {sport_name}", len(events) > 0,
                     f"{len(events)} match(es) | Quota: {resp.requests_remaining}")

        all_odds_data[sport_key] = events

        for event in events[:3]:
            match_name = f"{event['home_team']} vs {event['away_team']}"
            bookmakers = event.get("bookmakers", [])
            logger.info(f"    ⚽ {match_name} — {len(bookmakers)} bookmaker(s)")

            for bm in bookmakers:
                bm_key = bm.get("key", "unknown")
                bm_title = bm.get("title", "Unknown")
                provider_stats[bm_key]["count"] += 1
                provider_stats[bm_key]["sports"].add(sport_name)

                for market in bm.get("markets", []):
                    mk = market.get("key", "?")
                    provider_stats[bm_key]["markets"].add(mk)
                    outcomes_str = " | ".join(
                        f"{o.get('name','?')}={o.get('price','?')}"
                        for o in market.get("outcomes", [])[:4]
                    )
                    logger.info(f"         📊 {bm_title:15s} [{mk:6s}]: {outcomes_str}")

        if len(events) > 3:
            logger.info(f"    ... et {len(events) - 3} match(es) de plus")

    await working_client.close()
    return all_odds_data, provider_stats


# ============================================================
#   ÉTAPE 3 : Listing détaillé des fournisseurs
# ============================================================

def step3_provider_listing(provider_stats: dict):
    logger.info("")
    logger.info("═" * 70)
    logger.info("  ÉTAPE 3 — LISTE DES FOURNISSEURS DÉTECTÉS")
    logger.info("═" * 70)

    from constants import BOOKMAKERS, BOOKMAKER_DISPLAY_NAMES

    if not provider_stats:
        results.add("Fournisseurs détectés", False, "Aucune donnée récupérée")
        return

    logger.info(f"")
    logger.info(f"  {'#':>3}  {'Clé API':20s}  {'Nom':18s}  {'Cotes':>6}  {'Sports':>6}  {'Marchés':20s}  Config")
    logger.info(f"  {'─'*3}  {'─'*20}  {'─'*18}  {'─'*6}  {'─'*6}  {'─'*20}  {'─'*6}")

    sorted_providers = sorted(provider_stats.items(), key=lambda x: -x[1]["count"])

    for i, (key, stats) in enumerate(sorted_providers, 1):
        display = BOOKMAKER_DISPLAY_NAMES.get(key, key)
        configured = "✓" if key in BOOKMAKERS else " "
        markets_str = ", ".join(sorted(stats["markets"]))
        logger.info(
            f"  {i:>3}  {key:20s}  {display:18s}  {stats['count']:>6}  "
            f"{len(stats['sports']):>6}  {markets_str:20s}  {configured}"
        )

    found = [b for b in BOOKMAKERS if b in provider_stats]
    missing = [b for b in BOOKMAKERS if b not in provider_stats]

    results.add(
        "Fournisseurs configurés présents",
        len(found) > 0,
        f"Trouvés: {len(found)}/{len(BOOKMAKERS)} — {', '.join(found)}"
    )

    if missing:
        results.add(
            "Fournisseurs configurés manquants",
            True,
            f"Absents: {', '.join(missing)} (normal si hors région/pas de match)",
            warning=True
        )

    extra = [k for k in provider_stats if k not in BOOKMAKERS]
    if extra:
        logger.info(f"")
        logger.info(f"  ℹ️  Fournisseurs NON configurés mais détectés: {', '.join(extra[:10])}")


# ============================================================
#   ÉTAPE 4 : Matrice fournisseurs × sports
# ============================================================

def step4_provider_matrix(all_odds_data: dict):
    logger.info("")
    logger.info("═" * 70)
    logger.info("  ÉTAPE 4 — MATRICE FOURNISSEURS × SPORTS")
    logger.info("═" * 70)

    from constants import BOOKMAKERS, BOOKMAKER_DISPLAY_NAMES, ALL_SPORTS

    if not all_odds_data:
        logger.info("  (pas de données live)")
        return

    sport_keys = list(all_odds_data.keys())
    sport_names = [ALL_SPORTS.get(sk, sk)[:12] for sk in sport_keys]

    col_w = 14
    header = f"  {'Bookmaker':20s}" + "".join(f"  {sn:>{col_w}}" for sn in sport_names)
    logger.info(header)
    logger.info(f"  {'─'*20}" + f"  {'─'*col_w}" * len(sport_names))

    for bm_key in BOOKMAKERS:
        display = BOOKMAKER_DISPLAY_NAMES.get(bm_key, bm_key)[:20]
        row = f"  {display:20s}"
        for sk in sport_keys:
            count = sum(
                1 for ev in all_odds_data.get(sk, [])
                for bm in ev.get("bookmakers", [])
                if bm.get("key") == bm_key
            )
            row += f"  {'✓ ' + str(count):>{col_w}}" if count > 0 else f"  {'—':>{col_w}}"
        logger.info(row)

    results.add("Matrice fournisseurs × sports", True, "Générée avec succès")


# ============================================================
#   ÉTAPE 5 : SIMULATION PIPELINE COMPLÈTE
#   Chaque fournisseur × chaque ligue × chaque type de pari
# ============================================================

async def step5_pipeline_simulation(all_odds_data: dict):
    logger.info("")
    logger.info("═" * 70)
    logger.info("  ÉTAPE 5 — SIMULATION DU PIPELINE COMPLET")
    logger.info("  Chaque fournisseur × chaque ligue × chaque type de pari")
    logger.info("═" * 70)

    from core.scanner import SurebetScanner
    from core.calculator import (
        calculate_arbitrage, calculate_two_way_arbitrage,
        calculate_three_way_arbitrage
    )
    from core.api_manager import APIManager
    from notifications.telegram_bot import TelegramBot
    from constants import (
        ALL_SPORTS, BOOKMAKERS, BOOKMAKER_DISPLAY_NAMES,
        FOOTBALL_LEAGUES, BASKETBALL_LEAGUES, TENNIS_TOURNAMENTS, NFL_LEAGUES,
        BASE_MARKETS, FOOTBALL_PLAYER_PROPS, BASKETBALL_PLAYER_PROPS, NFL_PLAYER_PROPS,
    )
    from config import API_KEYS_FILE, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID

    api_mgr = APIManager(API_KEYS_FILE, auto_generate=False)
    api_mgr.load_keys()
    tg = TelegramBot(TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID)
    scanner = SurebetScanner(api_manager=api_mgr, telegram=tg, bookmakers=BOOKMAKERS)

    # ── 5.1 : Extraction live si disponible ───────────────────────
    logger.info("")
    logger.info("  ┌─────────────────────────────────────────────────────┐")
    logger.info("  │  5.1  EXTRACTION DES MARCHÉS DEPUIS DONNÉES LIVE   │")
    logger.info("  └─────────────────────────────────────────────────────┘")

    total_markets = 0
    live_surebets = []

    for sport_key, events in all_odds_data.items():
        sport_name = ALL_SPORTS.get(sport_key, sport_key)
        for event in events:
            match_name = f"{event['home_team']} vs {event['away_team']}"
            markets = scanner._extract_markets(event)
            for mk, data in markets.items():
                total_markets += 1
                sb = scanner._find_arbitrage(data, mk, sport_name, sport_name, match_name)
                if sb:
                    live_surebets.append(sb)
                    logger.info(f"    🎯 LIVE SUREBET: {match_name} [{mk}] profit={sb.result.profit_pct}%")

    results.add(
        "Extraction marchés live",
        total_markets > 0 or len(all_odds_data) == 0,
        f"{total_markets} marché(s) extraits" + (
            f" | {len(live_surebets)} surebet(s)!" if live_surebets else ""
        ),
        warning=(total_markets == 0 and len(all_odds_data) == 0)
    )

    # ── 5.2 : Simulation exhaustive ──────────────────────────────
    logger.info("")
    logger.info("  ┌──────────────────────────────────────────────────────────────┐")
    logger.info("  │  5.2  SIMULATION EXHAUSTIVE:                                │")
    logger.info("  │       CHAQUE FOURNISSEUR × CHAQUE LIGUE × CHAQUE PARI      │")
    logger.info("  └──────────────────────────────────────────────────────────────┘")

    # Définir les catégories de sports avec marchés associés
    sport_categories = {
        "Football": {
            "leagues": FOOTBALL_LEAGUES,
            "base_markets": ["h2h", "totals"],
            "player_props": FOOTBALL_PLAYER_PROPS,
            "h2h_type": "3-way",  # 1X2
        },
        "Basketball": {
            "leagues": BASKETBALL_LEAGUES,
            "base_markets": ["h2h", "spreads", "totals"],
            "player_props": BASKETBALL_PLAYER_PROPS,
            "h2h_type": "2-way",  # Home/Away
        },
        "Tennis": {
            "leagues": TENNIS_TOURNAMENTS,
            "base_markets": ["h2h", "totals"],
            "player_props": [],
            "h2h_type": "2-way",
        },
        "NFL": {
            "leagues": NFL_LEAGUES,
            "base_markets": ["h2h", "spreads", "totals"],
            "player_props": NFL_PLAYER_PROPS,
            "h2h_type": "2-way",
        },
    }

    # Compteurs globaux
    total_combinations = 0
    total_surebets_sim = 0
    total_non_surebets_sim = 0
    errors_sim = 0

    # Table de résultats par fournisseur
    provider_results = defaultdict(lambda: {"tested": 0, "surebets": 0, "errors": 0})

    for sport_name, cat in sport_categories.items():
        leagues = cat["leagues"]
        base_markets = cat["base_markets"]
        h2h_type = cat["h2h_type"]

        logger.info("")
        logger.info(f"  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        logger.info(f"  🏟️  {sport_name.upper()} — {len(leagues)} ligue(s) × {len(BOOKMAKERS)} bookmaker(s)")
        logger.info(f"      Marchés: {', '.join(base_markets + cat['player_props'][:2])}")
        logger.info(f"  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

        for league_key, league_name in leagues.items():
            logger.info(f"")
            logger.info(f"  📌 {league_name} ({league_key})")

            for market_type in base_markets:
                # Pour chaque paire de fournisseurs, simuler une cote
                tested_pairs = 0

                for i, bm1_key in enumerate(BOOKMAKERS):
                    for bm2_key in BOOKMAKERS[i+1:]:
                        bm1_name = BOOKMAKER_DISPLAY_NAMES.get(bm1_key, bm1_key)
                        bm2_name = BOOKMAKER_DISPLAY_NAMES.get(bm2_key, bm2_key)
                        total_combinations += 1
                        tested_pairs += 1

                        try:
                            if market_type == "h2h":
                                if h2h_type == "3-way":
                                    # Simuler 1X2 avec des cotes réalistes
                                    # Parfois injecter un surebet
                                    is_surebet_case = (tested_pairs % 15 == 0)

                                    if is_surebet_case:
                                        o1, o2, o3 = 3.80, 4.20, 3.90
                                    else:
                                        o1 = round(random.uniform(1.3, 3.5), 2)
                                        o2 = round(random.uniform(2.5, 5.0), 2)
                                        o3 = round(random.uniform(1.8, 4.0), 2)

                                    result = calculate_three_way_arbitrage(o1, o2, o3)
                                else:
                                    is_surebet_case = (tested_pairs % 15 == 0)
                                    if is_surebet_case:
                                        o1, o2 = 2.15, 2.10
                                    else:
                                        o1 = round(random.uniform(1.2, 3.0), 2)
                                        o2 = round(random.uniform(1.2, 3.0), 2)

                                    result = calculate_two_way_arbitrage(o1, o2)

                            elif market_type == "totals":
                                is_surebet_case = (tested_pairs % 15 == 0)
                                if is_surebet_case:
                                    over, under = 2.12, 2.12
                                else:
                                    over = round(random.uniform(1.5, 2.5), 2)
                                    under = round(random.uniform(1.5, 2.5), 2)

                                result = calculate_two_way_arbitrage(over, under)

                            elif market_type == "spreads":
                                is_surebet_case = (tested_pairs % 15 == 0)
                                if is_surebet_case:
                                    o1, o2 = 2.08, 2.08
                                else:
                                    o1 = round(random.uniform(1.6, 2.4), 2)
                                    o2 = round(random.uniform(1.6, 2.4), 2)

                                result = calculate_two_way_arbitrage(o1, o2)

                            else:
                                continue

                            provider_results[bm1_key]["tested"] += 1
                            provider_results[bm2_key]["tested"] += 1

                            if result.is_surebet:
                                total_surebets_sim += 1
                                provider_results[bm1_key]["surebets"] += 1
                                provider_results[bm2_key]["surebets"] += 1
                                logger.debug(
                                    f"      🎯 SUREBET [{market_type}] "
                                    f"{bm1_name} vs {bm2_name}: "
                                    f"profit={result.profit_pct}% L={result.implied_probability:.4f}"
                                )
                            else:
                                total_non_surebets_sim += 1

                        except ValueError as e:
                            errors_sim += 1
                            provider_results[bm1_key]["errors"] += 1
                            logger.debug(f"      ⚠️ [{market_type}] {bm1_name} vs {bm2_name}: {e}")

                logger.info(
                    f"     [{market_type:7s}] {tested_pairs} paires testées"
                )

    # ── 5.3 : Récapitulatif par fournisseur ──────────────────────
    logger.info("")
    logger.info("  ┌──────────────────────────────────────────────────────────────┐")
    logger.info("  │  5.3  RÉCAPITULATIF PAR FOURNISSEUR                         │")
    logger.info("  └──────────────────────────────────────────────────────────────┘")
    logger.info("")
    logger.info(f"  {'Fournisseur':20s}  {'Tests':>8}  {'Surebets':>10}  {'Erreurs':>8}  {'Taux':>8}")
    logger.info(f"  {'─'*20}  {'─'*8}  {'─'*10}  {'─'*8}  {'─'*8}")

    for bm_key in BOOKMAKERS:
        stats = provider_results[bm_key]
        display = BOOKMAKER_DISPLAY_NAMES.get(bm_key, bm_key)
        rate = f"{stats['surebets']/max(stats['tested'],1)*100:.1f}%" if stats['tested'] else "N/A"
        logger.info(
            f"  {display:20s}  {stats['tested']:>8}  {stats['surebets']:>10}  "
            f"{stats['errors']:>8}  {rate:>8}"
        )

    results.add(
        "Simulation exhaustive",
        total_combinations > 0 and errors_sim == 0,
        f"Total: {total_combinations} combinaisons | "
        f"Surebets: {total_surebets_sim} | Non-surebets: {total_non_surebets_sim} | "
        f"Erreurs: {errors_sim}"
    )

    # ── 5.4 : Pipeline pas-à-pas avec données contrôlées ────────
    logger.info("")
    logger.info("  ┌──────────────────────────────────────────────────────────────┐")
    logger.info("  │  5.4  PIPELINE PAS-À-PAS AVEC DONNÉES CONTRÔLÉES           │")
    logger.info("  └──────────────────────────────────────────────────────────────┘")

    # Scénario A: Surebet 2-way
    logger.info("")
    logger.info("  ━━━ SCÉNARIO A — Surebet Over/Under (2-way) ━━━")
    logger.info("    Match:   PSG vs Marseille")
    logger.info("    Betclic: Over 2.5  → 2.10")
    logger.info("    Winamax: Under 2.5 → 2.10")

    ra = calculate_two_way_arbitrage(2.10, 2.10)
    logger.info(f"    L = {ra.implied_probability:.4f} → {'SUREBET ✅' if ra.is_surebet else 'NON ❌'}")
    logger.info(f"    Profit: {ra.profit_pct}% | Mises: {ra.stakes} | Gain: {100+ra.profit_base_100:.2f}€")

    results.add("Pipeline A — Surebet Over/Under", ra.is_surebet,
                f"profit={ra.profit_pct}%")

    # Scénario B: Surebet 3-way
    logger.info("")
    logger.info("  ━━━ SCÉNARIO B — Surebet 1X2 (3-way) ━━━")
    logger.info("    Match:   Lyon vs Lille")
    logger.info("    Betclic: 1 → 4.00 | Winamax: X → 4.00 | PMU: 2 → 4.00")

    rb = calculate_three_way_arbitrage(4.0, 4.0, 4.0)
    logger.info(f"    L = {rb.implied_probability:.4f} → {'SUREBET ✅' if rb.is_surebet else 'NON ❌'}")
    logger.info(f"    Profit: {rb.profit_pct}% | Mises: {rb.stakes} | Gain: {100+rb.profit_base_100:.2f}€")

    results.add("Pipeline B — Surebet 1X2 (3-way)", rb.is_surebet,
                f"profit={rb.profit_pct}%")

    # Scénario C: Non-surebet
    logger.info("")
    logger.info("  ━━━ SCÉNARIO C — Non-Surebet (cas négatif) ━━━")
    logger.info("    Match:   Nantes vs Rennes")
    logger.info("    Betclic: Over 2.5 → 1.85 | Winamax: Under 2.5 → 1.90")

    rc = calculate_two_way_arbitrage(1.85, 1.90)
    logger.info(f"    L = {rc.implied_probability:.4f} → {'SUREBET ✅' if rc.is_surebet else 'NON ❌'}")
    logger.info(f"    Marge bookmaker: {(rc.implied_probability - 1) * 100:.2f}%")

    results.add("Pipeline C — Non-surebet", rc.is_surebet == False,
                f"L={rc.implied_probability:.4f}")

    # Scénario D: Pipeline complet extraction → arbitrage
    logger.info("")
    logger.info("  ━━━ SCÉNARIO D — Pipeline complet (event simulé multi-bookmaker) ━━━")

    mock_event = {
        "id": "sim_001",
        "home_team": "Real Madrid",
        "away_team": "FC Barcelona",
        "bookmakers": [
            {
                "key": "betclic", "title": "Betclic",
                "markets": [
                    {"key": "h2h", "outcomes": [
                        {"name": "Real Madrid", "price": 2.50},
                        {"name": "FC Barcelona", "price": 2.90},
                        {"name": "Draw", "price": 3.40}
                    ]},
                    {"key": "totals", "outcomes": [
                        {"name": "Over", "point": 2.5, "price": 1.85},
                        {"name": "Under", "point": 2.5, "price": 2.05}
                    ]}
                ]
            },
            {
                "key": "winamax_fr", "title": "Winamax",
                "markets": [
                    {"key": "h2h", "outcomes": [
                        {"name": "Real Madrid", "price": 2.45},
                        {"name": "FC Barcelona", "price": 3.00},
                        {"name": "Draw", "price": 3.50}
                    ]},
                    {"key": "totals", "outcomes": [
                        {"name": "Over", "point": 2.5, "price": 1.80},
                        {"name": "Under", "point": 2.5, "price": 2.15}
                    ]}
                ]
            },
            {
                "key": "pinnacle", "title": "Pinnacle",
                "markets": [
                    {"key": "h2h", "outcomes": [
                        {"name": "Real Madrid", "price": 2.55},
                        {"name": "FC Barcelona", "price": 2.85},
                        {"name": "Draw", "price": 3.60}
                    ]},
                    {"key": "totals", "outcomes": [
                        {"name": "Over", "point": 2.5, "price": 1.90},
                        {"name": "Under", "point": 2.5, "price": 2.00}
                    ]}
                ]
            }
        ]
    }

    logger.info(f"    📥 1/4 Réception: {mock_event['home_team']} vs {mock_event['away_team']} — 3 bookmakers")

    markets = scanner._extract_markets(mock_event)
    logger.info(f"    🔧 2/4 Extraction: {list(markets.keys())}")
    for mk, data in markets.items():
        for name, odds_list in data.items():
            best = max(odds_list, key=lambda x: x[1])
            logger.info(f"         [{mk}] {name:15s} → best: {best[0]} ({best[1]:.2f})")

    logger.info(f"    📐 3/4 Arbitrage:")
    found_any = False
    for mk, data in markets.items():
        sb = scanner._find_arbitrage(data, mk, "Football", "La Liga",
                                     "Real Madrid vs FC Barcelona")
        if sb:
            found_any = True
            logger.info(f"         🎯 [{mk}] SUREBET! profit={sb.result.profit_pct}%")
            for o in sb.outcomes:
                logger.info(f"            → {o['bookmaker']:15s} | {o['name']:12s} | {o['odds']:.2f}")
        else:
            best_odds = []
            for outcome in data:
                if data[outcome]:
                    best_odds.append(max(data[outcome], key=lambda x: x[1])[1])
            if len(best_odds) >= 2:
                r = calculate_arbitrage(best_odds)
                logger.info(f"         [{mk}] pas de surebet (L={r.implied_probability:.4f})")

    logger.info(f"    📤 4/4 Résultat: {'SUREBET trouvé!' if found_any else 'aucun surebet (normal)'}")

    results.add("Pipeline D — Extraction multi-bookmaker", True,
                "Pipeline complet exécuté")

    # Scénario E: Surebet garanti cross-bookmaker
    logger.info("")
    logger.info("  ━━━ SCÉNARIO E — Pipeline avec surebet garanti ━━━")

    surebet_event = {
        "id": "sim_002",
        "home_team": "Manchester City",
        "away_team": "Liverpool",
        "bookmakers": [
            {"key": "betclic", "title": "Betclic",
             "markets": [{"key": "totals", "outcomes": [
                 {"name": "Over", "point": 2.5, "price": 2.15},
                 {"name": "Under", "point": 2.5, "price": 1.75}
             ]}]},
            {"key": "winamax_fr", "title": "Winamax",
             "markets": [{"key": "totals", "outcomes": [
                 {"name": "Over", "point": 2.5, "price": 1.80},
                 {"name": "Under", "point": 2.5, "price": 2.15}
             ]}]}
        ]
    }

    logger.info("    Betclic:  Over=2.15, Under=1.75")
    logger.info("    Winamax:  Over=1.80, Under=2.15")
    logger.info("    → Best Over: Betclic (2.15) + Best Under: Winamax (2.15)")

    me = scanner._extract_markets(surebet_event)
    se = scanner._find_arbitrage(me.get("totals", {}), "totals", "Football",
                                  "Premier League", "Man City vs Liverpool")

    if se:
        logger.info(f"    ✅ SUREBET! profit={se.result.profit_pct}% | stakes={se.result.stakes}")
        logger.info(f"       Retour garanti: {100 + se.result.profit_base_100:.2f}€")
        results.add("Pipeline E — Surebet garanti", se.result.is_surebet,
                     f"profit={se.result.profit_pct}%")
    else:
        results.add("Pipeline E — Surebet garanti", False, "Non détecté (bug)")

    await tg.close()


# ============================================================
#   MAIN
# ============================================================

async def main():
    start_time = datetime.now()

    logger.info("")
    logger.info("╔" + "═" * 68 + "╗")
    logger.info("║  TEST COMPLET — FOURNISSEURS × LIGUES × TYPES DE PARIS          ║")
    logger.info("║  + SIMULATION DU PIPELINE D'ARBITRAGE                           ║")
    logger.info("╠" + "═" * 68 + "╣")
    logger.info(f"║  Date:   {start_time.strftime('%d/%m/%Y %H:%M:%S'):57s}  ║")
    logger.info(f"║  Log:    {str(LOG_FILE):57s}  ║")
    logger.info("╚" + "═" * 68 + "╝")

    # Charger les clés API
    all_keys = load_all_api_keys()
    logger.info(f"  🔑 {len(all_keys)} clé(s) API chargée(s)")

    if not all_keys:
        logger.error("❌ AUCUNE CLÉ API TROUVÉE!")
        return 1

    # Créer le client avec la première clé pour l'étape 1
    from core.odds_client import OddsClient
    client = OddsClient(all_keys[0][1], request_delay=2.0)

    try:
        # Étape 1: Valider les sports
        valid_sports = await step1_validate_sports(client)
        await client.close()

        # Étape 2: Récupérer les cotes (essaye toutes les clés)
        all_odds_data, provider_stats = await step2_fetch_odds(all_keys, valid_sports)

        # Étape 3: Listing fournisseurs
        step3_provider_listing(provider_stats)

        # Étape 4: Matrice
        step4_provider_matrix(all_odds_data)

        # Étape 5: Pipeline complet
        await step5_pipeline_simulation(all_odds_data)

    except Exception as e:
        logger.error(f"ERREUR FATALE: {e}")
        import traceback
        logger.error(traceback.format_exc())
        results.add("ERREUR FATALE", False, str(e))

    elapsed = (datetime.now() - start_time).total_seconds()
    logger.info(f"\n  ⏱ Durée totale: {elapsed:.1f}s")
    logger.info(f"  📄 Log complet: {LOG_FILE}")

    all_passed = results.summary()
    return 0 if all_passed else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
