#!/usr/bin/env python3
"""
=================================================================
  CHECKUP COMPLET API - SUREBET BOT
=================================================================
  Ce script teste toutes les fonctionnalités liées à l'API:
  1. The Odds API (endpoints)
  2. Calculator (calculs d'arbitrage)
  3. APIManager (gestion des clés)
  4. Telegram Bot (connexion)
  5. Database (CRUD)
  6. Scanner (extraction marchés + détection arbitrage)
=================================================================
"""

import asyncio
import sys
import os
import json
import traceback
from pathlib import Path
from datetime import datetime

# Setup path
SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

# ============================================================
# Utilitaires de test
# ============================================================

class TestResults:
    def __init__(self):
        self.tests = []
        self.passed = 0
        self.failed = 0
        self.warnings = 0
    
    def add(self, name, passed, details="", warning=False):
        status = "⚠️ WARN" if warning else ("✅ PASS" if passed else "❌ FAIL")
        self.tests.append({"name": name, "status": status, "details": details})
        if warning:
            self.warnings += 1
        elif passed:
            self.passed += 1
        else:
            self.failed += 1
        print(f"  {status} {name}")
        if details:
            for line in details.split("\n"):
                print(f"       {line}")
    
    def summary(self):
        total = self.passed + self.failed + self.warnings
        print("\n" + "=" * 60)
        print("  RÉSUMÉ DU CHECKUP")
        print("=" * 60)
        print(f"  Total: {total} tests")
        print(f"  ✅ Passés: {self.passed}")
        print(f"  ❌ Échoués: {self.failed}")
        print(f"  ⚠️ Warnings: {self.warnings}")
        print("=" * 60)
        
        if self.failed == 0:
            print("\n  🎉 TOUS LES TESTS SONT PASSÉS!\n")
        else:
            print(f"\n  ⚠️ {self.failed} TEST(S) ÉCHOUÉ(S)\n")
            for t in self.tests:
                if t["status"] == "❌ FAIL":
                    print(f"    - {t['name']}: {t['details']}")
        
        return self.failed == 0


results = TestResults()


# ============================================================
# Charger la clé API depuis api_keys.txt (racine du projet)
# ============================================================

def load_api_key():
    """Charge la clé API depuis le fichier à la racine."""
    root_key_file = SCRIPT_DIR.parent / "api_keys.txt"
    local_key_file = SCRIPT_DIR / "api_keys.txt"
    
    key = None
    email = None
    source = None
    
    for f, name in [(root_key_file, "racine"), (local_key_file, "surebet_bot")]:
        if f.exists():
            with open(f, "r") as fh:
                for line in fh:
                    line = line.strip()
                    if ":" in line:
                        email, key = line.split(":", 1)
                        source = name
                        break
                    elif line and len(line) == 32:
                        key = line
                        email = "unknown"
                        source = name
                        break
        if key:
            break
    
    return email, key, source


# ============================================================
# TEST 1: The Odds API - Liste des sports
# ============================================================

async def test_api_sports(client):
    print("\n" + "─" * 60)
    print("  TEST 1: GET /sports")
    print("─" * 60)
    
    resp = await client.get_sports()
    
    results.add(
        "API connexion (GET /sports)",
        resp.success,
        f"Status: {resp.status_code}" + (f" | Erreur: {resp.error}" if resp.error else "")
    )
    
    if resp.success and resp.data:
        active = [s for s in resp.data if not s.get("has_outrights")]
        all_count = len(resp.data)
        results.add(
            "Sports disponibles",
            all_count > 0,
            f"Total: {all_count} | Actifs (non-outrights): {len(active)}"
        )
        
        # Vérifier que les sports configurés existent
        from config import ALL_SPORTS
        sport_keys = {s["key"] for s in resp.data}
        
        configured_found = 0
        configured_missing = []
        for key in ALL_SPORTS:
            if key in sport_keys:
                configured_found += 1
            else:
                configured_missing.append(key)
        
        results.add(
            "Sports configurés trouvés dans l'API",
            configured_found > 0,
            f"Trouvés: {configured_found}/{len(ALL_SPORTS)}" +
            (f"\nManquants: {', '.join(configured_missing[:5])}" if configured_missing else "")
        )
        
        # Afficher les quotas
        results.add(
            "Quota API",
            resp.requests_remaining > 0,
            f"Requêtes utilisées: {resp.requests_used} | Restantes: {resp.requests_remaining}"
        )
        
        return resp.data
    
    return None


# ============================================================
# TEST 2: Récupération des événements
# ============================================================

async def test_api_events(client):
    print("\n" + "─" * 60)
    print("  TEST 2: GET /sports/{sport}/events")
    print("─" * 60)
    
    # Tester avec un sport populaire
    test_sports = [
        ("soccer_epl", "Premier League"),
        ("soccer_france_ligue_one", "Ligue 1"),
        ("basketball_nba", "NBA"),
    ]
    
    event_id = None
    event_sport = None
    
    for sport_key, sport_name in test_sports:
        resp = await client.get_events(sport_key)
        
        has_events = resp.success and resp.data and len(resp.data) > 0
        detail = f"Status: {resp.status_code}"
        
        if has_events:
            detail += f" | {len(resp.data)} événement(s)"
            ev = resp.data[0]
            detail += f"\n  → {ev.get('home_team', '?')} vs {ev.get('away_team', '?')}"
            detail += f"\n  → ID: {ev.get('id', 'N/A')}"
            detail += f"\n  → Date: {ev.get('commence_time', 'N/A')}"
            
            if not event_id:
                event_id = ev["id"]
                event_sport = sport_key
        elif resp.success:
            detail += " | 0 événement (hors saison?)"
        else:
            detail += f" | Erreur: {resp.error}"
        
        results.add(
            f"Events {sport_name}",
            resp.success,
            detail
        )
        
        if not resp.success and resp.status_code in [401, 402, 429]:
            results.add("Quota insuffisant", False, "Arrêt des tests API")
            return None, None
    
    return event_id, event_sport


# ============================================================
# TEST 3: Cotes de base (h2h, totals, spreads)
# ============================================================

async def test_api_odds(client):
    print("\n" + "─" * 60)
    print("  TEST 3: GET /sports/{sport}/odds (h2h + totals)")
    print("─" * 60)
    
    from config import BOOKMAKERS, REGIONS
    
    resp = await client.get_odds(
        sport="soccer_epl",
        regions=REGIONS,
        markets="h2h,totals"
    )
    
    results.add(
        "Odds h2h + totals (Premier League)",
        resp.success,
        f"Status: {resp.status_code}" + (f" | Erreur: {resp.error}" if resp.error else "")
    )
    
    if resp.success and resp.data:
        results.add(
            "Matches avec cotes",
            len(resp.data) > 0,
            f"{len(resp.data)} match(es) avec cotes"
        )
        
        # Vérifier la structure des données
        if resp.data:
            event = resp.data[0]
            has_required = all(k in event for k in ["id", "home_team", "away_team", "bookmakers"])
            results.add(
                "Structure données (id, home_team, away_team, bookmakers)",
                has_required,
                f"Clés présentes: {list(event.keys())}"
            )
            
            # Vérifier les bookmakers
            bookmakers = event.get("bookmakers", [])
            bm_names = [b["title"] for b in bookmakers]
            results.add(
                "Bookmakers présents",
                len(bookmakers) > 0,
                f"{len(bookmakers)} bookmaker(s): {', '.join(bm_names[:5])}"
            )
            
            # Vérifier la présence des bookmakers configurés
            configured_found = [b for b in BOOKMAKERS if any(bm["key"] == b for bm in bookmakers)]
            results.add(
                "Bookmakers configurés trouvés",
                len(configured_found) > 0,
                f"Trouvés: {len(configured_found)}/{len(BOOKMAKERS)}: {', '.join(configured_found[:5])}",
                warning=len(configured_found) == 0
            )
            
            # Vérifier les marchés
            all_markets = set()
            for bm in bookmakers:
                for m in bm.get("markets", []):
                    all_markets.add(m.get("key"))
            
            results.add(
                "Marchés disponibles",
                len(all_markets) > 0,
                f"Marchés: {', '.join(all_markets)}"
            )
            
            # Vérifier les cotes h2h
            h2h_data = None
            for bm in bookmakers:
                for m in bm.get("markets", []):
                    if m["key"] == "h2h":
                        h2h_data = m
                        break
                if h2h_data:
                    break
            
            if h2h_data:
                outcomes = h2h_data.get("outcomes", [])
                results.add(
                    "Cotes h2h (outcomes)",
                    len(outcomes) >= 2,
                    f"{len(outcomes)} outcomes: " + 
                    ", ".join(f"{o['name']}={o['price']}" for o in outcomes)
                )
                
                # Vérifier que les cotes sont > 1.0
                valid_odds = all(o["price"] > 1.0 for o in outcomes)
                results.add(
                    "Cotes valides (> 1.0)",
                    valid_odds,
                    f"Toutes les cotes sont > 1.0: {valid_odds}"
                )
        
        return resp.data
    
    return None


# ============================================================
# TEST 4: Event Odds (Player Props)
# ============================================================

async def test_api_event_odds(client, event_id, event_sport):
    print("\n" + "─" * 60)
    print("  TEST 4: GET /sports/{sport}/events/{id}/odds (Player Props)")
    print("─" * 60)
    
    if not event_id:
        results.add("Event Odds", False, "Pas d'event_id disponible (tests précédents échoués)")
        return
    
    resp = await client.get_event_odds(
        sport=event_sport,
        event_id=event_id,
        regions="eu,fr",
        markets="player_goal_scorer_anytime"
    )
    
    results.add(
        "Event Odds / Player Props",
        resp.success,
        f"Status: {resp.status_code}" + 
        (f" | Erreur: {(resp.error or '')[:100]}" if resp.error else "") +
        (f" | Bookmakers: {len(resp.data.get('bookmakers', []))}" if resp.success and isinstance(resp.data, dict) else "")
    )
    
    # Tester aussi les scores
    resp2 = await client.get_scores(event_sport, days_from=3)
    results.add(
        "Scores récents",
        resp2.success,
        f"Status: {resp2.status_code}" + 
        (f" | {len(resp2.data)} score(s)" if resp2.success and resp2.data else "")
    )


# ============================================================
# TEST 5: Calculator (Calculs d'arbitrage)
# ============================================================

def test_calculator():
    print("\n" + "─" * 60)
    print("  TEST 5: Calculator (Calculs d'arbitrage)")
    print("─" * 60)
    
    from core.calculator import (
        calculate_implied_probability,
        calculate_arbitrage,
        calculate_two_way_arbitrage,
        calculate_three_way_arbitrage,
        format_surebet_message
    )
    
    # Test 5.1: Probabilité implicite
    prob = calculate_implied_probability([2.0, 2.0])
    expected = 1.0  # 0.5 + 0.5 = 1.0 (pas de marge)
    results.add(
        "Probabilité implicite [2.0, 2.0]",
        abs(prob - expected) < 0.001,
        f"Résultat: {prob} (attendu: {expected})"
    )
    
    # Test 5.2: Surebet 2-way (cas positif)
    # Over=2.10, Under=2.10 → L = 1/2.10 + 1/2.10 = 0.952 < 1 → SUREBET
    result = calculate_two_way_arbitrage(2.10, 2.10)
    results.add(
        "Surebet 2-way [2.10, 2.10]",
        result.is_surebet == True,
        f"is_surebet={result.is_surebet} | profit={result.profit_pct}% | stakes={result.stakes}"
    )
    
    # Vérifier que le profit est correct
    # L = 1/2.10 + 1/2.10 = 0.9524
    # profit = (1 - 0.9524) * 100 = 4.76%
    expected_profit = round((1 - (1/2.10 + 1/2.10)) * 100, 2)
    results.add(
        "Profit calculé correct",
        abs(result.profit_pct - expected_profit) < 0.1,
        f"Calculé: {result.profit_pct}% | Attendu: {expected_profit}%"
    )
    
    # Vérifier les mises optimales
    # Gain garanti = stake * cote
    gain1 = result.stakes[0] * 2.10
    gain2 = result.stakes[1] * 2.10
    results.add(
        "Mises optimales symétriques",
        abs(gain1 - gain2) < 0.1,
        f"Gain 1: {gain1:.2f}€ | Gain 2: {gain2:.2f}€ | Diff: {abs(gain1-gain2):.4f}€"
    )
    
    # Test 5.3: Non-surebet (cas négatif)
    result2 = calculate_two_way_arbitrage(1.50, 2.20)
    # L = 1/1.50 + 1/2.20 = 0.667 + 0.455 = 1.121 > 1 → PAS surebet
    results.add(
        "Non-surebet [1.50, 2.20]",
        result2.is_surebet == False,
        f"is_surebet={result2.is_surebet} | L={result2.implied_probability}"
    )
    
    # Test 5.4: Arbitrage 3-way (football 1X2)
    # Home=3.10, Draw=3.60, Away=2.50 → L = 1/3.1+1/3.6+1/2.5 = 0.322+0.278+0.400 = 1.0 → non surebet
    result3 = calculate_three_way_arbitrage(3.10, 3.60, 2.50)
    results.add(
        "3-way arbitrage [3.10, 3.60, 2.50]",
        isinstance(result3.is_surebet, bool),
        f"is_surebet={result3.is_surebet} | L={result3.implied_probability} | profit={result3.profit_pct}%"
    )
    
    # Test 5.5: Surebet 3-way réel
    # Home=4.0, Draw=4.0, Away=4.0 → L = 3 * 1/4 = 0.75 < 1 → SUREBET
    result4 = calculate_three_way_arbitrage(4.0, 4.0, 4.0)
    results.add(
        "Surebet 3-way [4.0, 4.0, 4.0]",
        result4.is_surebet == True,
        f"is_surebet={result4.is_surebet} | profit={result4.profit_pct}% | L={result4.implied_probability}"
    )
    
    # Test 5.6: Validation des erreurs
    try:
        calculate_arbitrage([])
        results.add("Validation cotes vides", False, "Pas d'exception levée")
    except ValueError:
        results.add("Validation cotes vides", True, "ValueError levée correctement")
    
    try:
        calculate_arbitrage([1.5])
        results.add("Validation cote unique", False, "Pas d'exception levée")
    except ValueError:
        results.add("Validation cote unique", True, "ValueError levée correctement")
    
    try:
        calculate_arbitrage([0.5, 1.5])
        results.add("Validation cotes <= 1.0", False, "Pas d'exception levée")
    except ValueError:
        results.add("Validation cotes <= 1.0", True, "ValueError levée correctement")
    
    # Test 5.7: Format message
    from core.calculator import SurebetResult
    test_result = SurebetResult(
        is_surebet=True, profit_pct=2.34, profit_base_100=2.34,
        stakes=[54.05, 45.95], implied_probability=0.9766
    )
    msg = format_surebet_message(
        sport="Football", league="Ligue 1", match="PSG vs OM",
        market="Over/Under 2.5",
        outcomes=[
            {"bookmaker": "Betclic", "name": "Over 2.5", "odds": 1.85},
            {"bookmaker": "Winamax", "name": "Under 2.5", "odds": 2.20}
        ],
        result=test_result
    )
    results.add(
        "Format message surebet",
        "SUREBET" in msg and "PSG" in msg and "2.34" in msg,
        f"Message ({len(msg)} chars) contient les infos requises"
    )


# ============================================================
# TEST 6: APIManager
# ============================================================

async def test_api_manager():
    print("\n" + "─" * 60)
    print("  TEST 6: APIManager (Gestion des clés)")
    print("─" * 60)
    
    from core.api_manager import APIManager
    from config import API_KEYS_FILE
    
    manager = APIManager(API_KEYS_FILE, auto_generate=False)
    
    # Test 6.1: Chargement des clés
    count = manager.load_keys()
    results.add(
        "Chargement clés depuis api_keys.txt",
        count > 0,
        f"{count} clé(s) chargée(s) depuis {API_KEYS_FILE}"
    )
    
    # Test 6.2: Clé active
    results.add(
        "Clé active disponible",
        manager.current_key is not None,
        f"Clé: {manager.current_key[:8]}..." if manager.current_key else "Aucune clé"
    )
    
    # Test 6.3: Email associé
    results.add(
        "Email associé",
        manager.current_email is not None and "@" in (manager.current_email or ""),
        f"Email: {manager.current_email}"
    )
    
    # Test 6.4: Compteur de clés valides
    results.add(
        "Clés valides",
        manager.valid_keys_count > 0,
        f"Valides: {manager.valid_keys_count}/{len(manager.keys)}"
    )
    
    # Test 6.5: Status
    status = manager.get_status()
    required_keys = ["total_keys", "valid_keys", "current_key", "auto_generate", "failover_count"]
    has_all = all(k in status for k in required_keys)
    results.add(
        "Status complet",
        has_all,
        f"Contient: {list(status.keys())}"
    )
    
    # Test 6.6: Failover (simulation)
    if count >= 2:
        old_key = manager.current_key
        failover_success = await manager.failover()
        new_key = manager.current_key
        results.add(
            "Failover vers clé suivante",
            failover_success and new_key != old_key,
            f"Avant: {old_key[:8]}... → Après: {new_key[:8]}..." if failover_success else "Échec du failover"
        )
    else:
        results.add(
            "Failover",
            True,
            f"Ignoré: une seule clé disponible",
            warning=True
        )
    
    # Test 6.7: Handle API error (simulation 401)
    manager2 = APIManager(API_KEYS_FILE, auto_generate=False)
    manager2.load_keys()
    
    if manager2.valid_keys_count >= 2:
        handled = await manager2.handle_api_error(401, "OUT_OF_USAGE_CREDITS")
        results.add(
            "Handle API error 401",
            handled,
            "Failover déclenché par erreur 401"
        )
    else:
        results.add("Handle API error", True, "Ignoré: pas assez de clés", warning=True)


# ============================================================
# TEST 7: Telegram Bot
# ============================================================

async def test_telegram():
    print("\n" + "─" * 60)
    print("  TEST 7: Telegram Bot (connexion)")
    print("─" * 60)
    
    from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
    from notifications.telegram_bot import TelegramBot
    
    # Test 7.1: Token et chat_id configurés
    results.add(
        "Telegram config",
        bool(TELEGRAM_BOT_TOKEN) and bool(TELEGRAM_CHAT_ID),
        f"Token: {TELEGRAM_BOT_TOKEN[:15]}... | Chat ID: {TELEGRAM_CHAT_ID}"
    )
    
    bot = TelegramBot(TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID)
    
    # Test 7.2: Envoi message de test
    try:
        success = await bot.send_message(
            "🧪 <b>TEST CHECKUP</b>\n\n"
            "Test automatique du bot Surebet.\n"
            f"Date: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}"
        )
        results.add(
            "Envoi message Telegram",
            success,
            "Message de test envoyé avec succès" if success else "Échec envoi"
        )
    except Exception as e:
        results.add("Envoi message Telegram", False, f"Exception: {e}")
    
    # Test 7.3: Check commandes (non-bloquant)
    try:
        commands = await bot.check_commands()
        results.add(
            "Check commandes Telegram",
            isinstance(commands, list),
            f"{len(commands)} commande(s) en attente"
        )
    except Exception as e:
        results.add("Check commandes Telegram", False, f"Exception: {e}")
    
    await bot.close()


# ============================================================
# TEST 8: Database
# ============================================================

async def test_database():
    print("\n" + "─" * 60)
    print("  TEST 8: Database (SQLite asynchrone)")
    print("─" * 60)
    
    from data.database import Database, SurebetRecord
    import tempfile
    
    # Utiliser une DB temporaire pour les tests
    test_db_path = Path(tempfile.mktemp(suffix=".db"))
    
    try:
        db = Database(test_db_path)
        
        # 8.1: Connexion
        await db.connect()
        results.add("DB connexion", True, f"Connecté à {test_db_path}")
        
        # 8.2: Sauvegarder un surebet
        record = SurebetRecord(
            id=None,
            detected_at=datetime.now(),
            sport="Football",
            league="Ligue 1",
            match="PSG vs OM",
            market="1X2",
            bookmaker1="Betclic",
            odds1=1.85,
            bookmaker2="Winamax",
            odds2=4.50,
            profit_pct=2.34,
            profit_base_100=2.34
        )
        
        record_id = await db.save_surebet(record)
        results.add(
            "DB save surebet",
            record_id is not None and record_id > 0,
            f"ID enregistré: {record_id}"
        )
        
        # 8.3: Récupérer les surebets
        surebets = await db.get_surebets(limit=10)
        results.add(
            "DB get surebets",
            len(surebets) == 1 and surebets[0]["match"] == "PSG vs OM",
            f"{len(surebets)} surebet(s) récupéré(s)"
        )
        
        # 8.4: Stats
        stats = await db.get_stats()
        results.add(
            "DB get stats",
            stats["total_surebets"] == 1 and abs(stats["total_profit_pct"] - 2.34) < 0.01,
            f"Total: {stats['total_surebets']} | Profit: {stats['total_profit_pct']}%"
        )
        
        # 8.5: Log API usage
        await db.log_api_usage("test_key_12345678", 5, 495)
        usage = await db.get_api_usage(limit=1)
        results.add(
            "DB log API usage",
            len(usage) == 1 and usage[0]["requests_remaining"] == 495,
            f"Usage enregistré: used=5, remaining=495"
        )
        
        # 8.6: Logs
        await db.add_log("INFO", "Test log message")
        logs = await db.get_logs(limit=1)
        results.add(
            "DB logs",
            len(logs) == 1 and logs[0]["message"] == "Test log message",
            f"{len(logs)} log(s) récupéré(s)"
        )
        
        # 8.7: Raw odds batch
        raw_batch = [
            {"sport": "Football", "match": "PSG vs OM", "market": "h2h", 
             "bookmaker": "Betclic", "outcome": "Home", "odds": 1.85},
            {"sport": "Football", "match": "PSG vs OM", "market": "h2h",
             "bookmaker": "Winamax", "outcome": "Away", "odds": 4.50},
            {"sport": "Football", "match": "PSG vs OM", "market": "h2h",
             "bookmaker": "Betclic", "outcome": "Draw", "odds": 3.60},
        ]
        await db.save_raw_odds_batch(raw_batch)
        raw_odds = await db.get_raw_odds(limit=10)
        results.add(
            "DB save/get raw odds batch",
            len(raw_odds) == 3,
            f"{len(raw_odds)} cote(s) brute(s) enregistrée(s)"
        )
        
        # Vérifier implied_prob
        if raw_odds:
            has_prob = raw_odds[0].get("implied_prob") is not None
            results.add(
                "DB probabilité implicite calculée",
                has_prob and raw_odds[0]["implied_prob"] > 0,
                f"implied_prob={raw_odds[0]['implied_prob']:.4f}" if has_prob else "Non calculée"
            )
        
        # 8.8: Scans
        await db.save_scan(18, 45, 0, "test_key_12345678", 490)
        scans = await db.get_scans(limit=1)
        results.add(
            "DB save/get scans",
            len(scans) == 1 and scans[0]["sports_scanned"] == 18,
            f"{len(scans)} scan(s) | sports_scanned={scans[0]['sports_scanned']}"
        )
        
        await db.close()
        
    except Exception as e:
        results.add("Database", False, f"Exception: {e}\n{traceback.format_exc()}")
    finally:
        # Nettoyer
        if test_db_path.exists():
            os.remove(test_db_path)


# ============================================================
# TEST 9: Scanner (logique d'extraction et d'arbitrage)
# ============================================================

async def test_scanner_logic():
    print("\n" + "─" * 60)
    print("  TEST 9: Scanner (logique d'arbitrage)")
    print("─" * 60)
    
    from core.scanner import SurebetScanner
    from core.api_manager import APIManager
    from notifications.telegram_bot import TelegramBot
    from config import API_KEYS_FILE, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
    
    # Créer un scanner pour accéder aux méthodes internes
    api_mgr = APIManager(API_KEYS_FILE, auto_generate=False)
    api_mgr.load_keys()
    tg = TelegramBot(TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID)
    scanner = SurebetScanner(api_manager=api_mgr, telegram=tg)
    
    # 9.1: Extract markets
    mock_event = {
        "home_team": "PSG",
        "away_team": "OM",
        "bookmakers": [
            {
                "key": "betclic",
                "title": "Betclic",
                "markets": [
                    {
                        "key": "h2h",
                        "outcomes": [
                            {"name": "PSG", "price": 1.45},
                            {"name": "OM", "price": 6.50},
                            {"name": "Draw", "price": 4.20}
                        ]
                    },
                    {
                        "key": "totals",
                        "outcomes": [
                            {"name": "Over", "point": 2.5, "price": 1.85},
                            {"name": "Under", "point": 2.5, "price": 2.05}
                        ]
                    }
                ]
            },
            {
                "key": "winamax_fr",
                "title": "Winamax",
                "markets": [
                    {
                        "key": "h2h",
                        "outcomes": [
                            {"name": "PSG", "price": 1.50},
                            {"name": "OM", "price": 6.00},
                            {"name": "Draw", "price": 4.00}
                        ]
                    },
                    {
                        "key": "totals",
                        "outcomes": [
                            {"name": "Over", "point": 2.5, "price": 1.80},
                            {"name": "Under", "point": 2.5, "price": 2.15}
                        ]
                    }
                ]
            }
        ]
    }
    
    markets = scanner._extract_markets(mock_event)
    
    results.add(
        "Extract markets - marchés trouvés",
        "h2h" in markets and "totals" in markets,
        f"Marchés: {list(markets.keys())}"
    )
    
    # Vérifier h2h
    if "h2h" in markets:
        h2h = markets["h2h"]
        results.add(
            "Extract h2h - 3 outcomes",
            len(h2h) == 3,
            f"Outcomes: {list(h2h.keys())}"
        )
        
        # Vérifier que les bookmakers sont collectés
        psg_odds = h2h.get("PSG", [])
        results.add(
            "Extract h2h - cotes PSG",
            len(psg_odds) == 2,
            f"PSG: {psg_odds}"  # Devrait avoir Betclic=1.45, Winamax=1.50
        )
    
    # Vérifier totals
    if "totals" in markets:
        totals = markets["totals"]
        results.add(
            "Extract totals - Over/Under",
            "Over 2.5" in totals and "Under 2.5" in totals,
            f"Outcomes: {list(totals.keys())}"
        )
    
    # 9.2: Find h2h arbitrage (pas de surebet dans ce cas)
    if "h2h" in markets:
        arb = scanner._find_h2h_arbitrage(
            markets["h2h"], "Football", "Ligue 1", "PSG vs OM", "h2h"
        )
        results.add(
            "H2H arbitrage - aucun surebet (cotes normales)",
            arb is None,
            "Aucun surebet détecté (attendu)"
        )
    
    # 9.3: Find totals arbitrage (pas de surebet ici non plus)
    if "totals" in markets:
        arb = scanner._find_totals_arbitrage(
            markets["totals"], "Football", "Ligue 1", "PSG vs OM", "totals"
        )
        results.add(
            "Totals arbitrage - aucun surebet (cotes normales)",
            arb is None,
            "Aucun surebet détecté (attendu)"
        )
    
    # 9.4: Simuler un surebet réel sur totals 
    # Over=2.10 chez Betclic + Under=2.10 chez Winamax → L = 0.952 < 1
    surebet_market = {
        "Over 2.5": [("Betclic", 2.10), ("Unibet", 1.90)],
        "Under 2.5": [("Winamax", 2.10), ("Pinnacle", 1.95)]
    }
    
    arb = scanner._find_totals_arbitrage(
        surebet_market, "Football", "Ligue 1", "Lyon vs Lille", "totals"
    )
    
    results.add(
        "Totals surebet simulé [Over=2.10, Under=2.10]",
        arb is not None and arb.result.is_surebet,
        f"Surebet détecté: profit={arb.result.profit_pct}%" if arb else "Non détecté"
    )
    
    if arb:
        results.add(
            "Surebet outcomes corrects",
            len(arb.outcomes) == 2 and arb.outcomes[0]["bookmaker"] == "Betclic",
            f"O1: {arb.outcomes[0]} | O2: {arb.outcomes[1]}"
        )
    
    # 9.5: Simuler un surebet 1X2
    surebet_h2h = {
        "Home": [("Betclic", 4.0), ("Unibet", 3.5)],
        "Draw": [("Winamax", 4.0), ("Pinnacle", 3.8)],
        "Away": [("PMU", 4.0), ("Betway", 3.5)]
    }
    
    arb2 = scanner._find_h2h_arbitrage(
        surebet_h2h, "Football", "Ligue 1", "Nantes vs Rennes", "h2h"
    )
    
    results.add(
        "H2H surebet 3-way simulé [4.0, 4.0, 4.0]",
        arb2 is not None and arb2.result.is_surebet,
        f"Surebet détecté: profit={arb2.result.profit_pct}%" if arb2 else "Non détecté"
    )
    
    # 9.6: Cooldown
    # Le premier surebet devrait être en cooldown maintenant
    arb3 = scanner._find_totals_arbitrage(
        surebet_market, "Football", "Ligue 1", "Lyon vs Lille", "totals"
    )
    results.add(
        "Cooldown fonctionne",
        arb3 is None,
        "Même surebet ignoré car en cooldown (attendu)"
    )
    
    # 9.7: Stats
    stats = scanner.get_stats()
    results.add(
        "Scanner stats",
        "scans_count" in stats and "requests_remaining" in stats,
        f"Stats: {stats}"
    )
    
    await tg.close()


# ============================================================
# MAIN
# ============================================================

async def main():
    print("\n" + "=" * 60)
    print("  CHECKUP COMPLET - SUREBET BOT API")
    print(f"  {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
    print("=" * 60)
    
    # Charger la clé API
    email, api_key, source = load_api_key()
    
    if not api_key:
        print("\n  ❌ AUCUNE CLÉ API TROUVÉE!")
        print("  Vérifiez api_keys.txt à la racine du projet")
        return
    
    print(f"\n  🔑 Clé API: {api_key[:8]}...")
    print(f"  📧 Email: {email}")
    print(f"  📁 Source: {source}")
    
    # Créer le client
    from core.odds_client import OddsClient
    client = OddsClient(api_key)
    
    try:
        # Tests API (réseau)
        await test_api_sports(client)
        event_id, event_sport = await test_api_events(client)
        await test_api_odds(client)
        await test_api_event_odds(client, event_id, event_sport)
        
        # Tests logiques (locaux)
        test_calculator()
        await test_api_manager()
        
        # Tests intégration
        await test_telegram()
        await test_database()
        await test_scanner_logic()
        
    except Exception as e:
        print(f"\n  ❌ ERREUR FATALE: {e}")
        traceback.print_exc()
        results.add("ERREUR FATALE", False, str(e))
    finally:
        await client.close()
    
    # Résumé
    all_passed = results.summary()
    return 0 if all_passed else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
