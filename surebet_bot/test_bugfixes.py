# Tests ciblés sur les bug fixes appliqués
# Couvre: cooldown atomique, déduplication totals/spreads, scheduler nouveaux créneaux

import asyncio
import sys
import os
from datetime import datetime, timedelta
from unittest.mock import MagicMock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.scanner import SurebetScanner, SurebetOpportunity
from core.calculator import SurebetResult
from core.scheduler import SmartScheduler
from constants import SCHEDULE_SLOTS, SLOT_PRIORITY, SPORT_PRIORITY


# ─── Helpers ────────────────────────────────────────────────────────────────

def make_scanner(cooldown_minutes=5):
    """Crée un SurebetScanner minimal pour les tests."""
    api_manager = MagicMock()
    api_manager.current_key = "test_key_12345678"
    telegram = MagicMock()
    scanner = SurebetScanner(
        api_manager=api_manager,
        telegram=telegram,
        cooldown_minutes=cooldown_minutes
    )
    return scanner


def make_surebet_result(profit_pct=2.0):
    return SurebetResult(
        is_surebet=True,
        profit_pct=profit_pct,
        profit_base_100=profit_pct,
        stakes=[50.0, 50.0],
        implied_probability=1.0 - profit_pct / 100
    )


def make_event_with_totals(lines: list[tuple[float, float]]) -> dict:
    """Génère un event API avec plusieurs lignes Over/Under.
    lines: [(line_value, over_odds, under_odds), ...]
    """
    bookmakers = []
    for i, (line, over, under) in enumerate(lines):
        bookmakers.append({
            "title": f"Bookmaker{i}",
            "markets": [{
                "key": "totals",
                "outcomes": [
                    {"name": "Over", "point": line, "price": over},
                    {"name": "Under", "point": line, "price": under},
                ]
            }]
        })
    return {
        "home_team": "PSG",
        "away_team": "OM",
        "bookmakers": bookmakers
    }


class TestResults:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.errors = []

    def ok(self, name):
        self.passed += 1
        print(f"  ✅ {name}")

    def fail(self, name, reason):
        self.failed += 1
        self.errors.append(f"{name}: {reason}")
        print(f"  ❌ {name}: {reason}")

    def summary(self):
        total = self.passed + self.failed
        print(f"\n{'='*50}")
        print(f"Résultats: {self.passed}/{total} tests passés")
        if self.errors:
            print("Échecs:")
            for e in self.errors:
                print(f"  - {e}")
        return self.failed == 0


# ─── TEST 1: Cooldown atomique ───────────────────────────────────────────────

def test_cooldown_atomique(r: TestResults):
    print("\n[TEST 1] Cooldown atomique (_check_and_add_cooldown)")
    scanner = make_scanner(cooldown_minutes=5)

    # Premier appel → pas en cooldown, doit ajouter et retourner False
    result = scanner._check_and_add_cooldown("PSG_vs_OM_h2h")
    if result is False:
        r.ok("Premier appel retourne False (pas en cooldown)")
    else:
        r.fail("Premier appel retourne False", f"Reçu: {result}")

    # Deuxième appel immédiat → en cooldown, doit retourner True
    result2 = scanner._check_and_add_cooldown("PSG_vs_OM_h2h")
    if result2 is True:
        r.ok("Deuxième appel retourne True (en cooldown)")
    else:
        r.fail("Deuxième appel retourne True", f"Reçu: {result2}")

    # Identifier différent → pas en cooldown
    result3 = scanner._check_and_add_cooldown("PSG_vs_OM_totals")
    if result3 is False:
        r.ok("Identifier différent n'est pas en cooldown")
    else:
        r.fail("Identifier différent n'est pas en cooldown", f"Reçu: {result3}")


# ─── TEST 2: Expiration du cooldown ──────────────────────────────────────────

def test_cooldown_expiration(r: TestResults):
    print("\n[TEST 2] Expiration du cooldown")
    scanner = make_scanner(cooldown_minutes=0)  # Expire immédiatement

    scanner._check_and_add_cooldown("match_expiry_test")

    # Forcer l'expiration en reculant le timestamp
    scanner.cooldown_cache["match_expiry_test"] = datetime.now() - timedelta(seconds=1)

    # Doit retourner False (expiré)
    result = scanner._check_and_add_cooldown("match_expiry_test")
    if result is False:
        r.ok("Cooldown expiré retourne False (re-notifie)")
    else:
        r.fail("Cooldown expiré retourne False", f"Reçu: {result}")


# ─── TEST 3: Déduplication totals multi-lignes ───────────────────────────────

def test_deduplication_totals_multilignes(r: TestResults):
    print("\n[TEST 3] Déduplication totals — plusieurs lignes simultanées")
    scanner = make_scanner(cooldown_minutes=5)

    # Event avec 3 lignes en arbitrage (Over/Under 2.5, 3.0, 3.5)
    # Pour créer un arbitrage : 1/over + 1/under < 1 → ex: 1/2.1 + 1/2.1 = 0.952 < 1
    event = make_event_with_totals([
        (2.5, 2.10, 2.10),  # arbitrage: L=0.952, profit=4.8%
        (3.0, 2.05, 2.05),  # arbitrage: L=0.976, profit=2.4%
        (3.5, 2.08, 2.08),  # arbitrage: L=0.962, profit=3.8%
    ])
    markets_data = scanner._extract_markets(event)

    # Premier scan : doit retourner UN seul surebet (le plus profitable = ligne 2.5 @ 4.8%)
    surebet1 = scanner._find_totals_arbitrage(
        markets_data.get("totals", {}), "Football", "Ligue 1", "PSG vs OM", "totals"
    )
    if surebet1 is not None:
        r.ok(f"Premier scan retourne 1 surebet (profit={surebet1.result.profit_pct:.1f}%)")
        if "2.5" in surebet1.market:
            r.ok("Le surebet retourné est la ligne la plus profitable (2.5 @ 4.8%)")
        else:
            r.fail("Ligne la plus profitable attendue", f"Reçu: {surebet1.market}")
    else:
        r.fail("Premier scan retourne un surebet", "Reçu: None")

    # Deuxième scan : même match/marché → cooldown → None
    surebet2 = scanner._find_totals_arbitrage(
        markets_data.get("totals", {}), "Football", "Ligue 1", "PSG vs OM", "totals"
    )
    if surebet2 is None:
        r.ok("Deuxième scan retourne None (cooldown actif)")
    else:
        r.fail("Deuxième scan retourne None", f"Reçu un surebet: {surebet2.market}")


# ─── TEST 4: Déduplication spreads multi-lignes ──────────────────────────────

def test_deduplication_spreads_multilignes(r: TestResults):
    print("\n[TEST 4] Déduplication spreads — plusieurs lignes simultanées")
    scanner = make_scanner(cooldown_minutes=5)

    # Créer les données de marché spreads manuellement
    market_data = {
        "PSG +1.5": [("Betclic", 1.95), ("Unibet", 1.98)],
        "OM -1.5": [("Betclic", 2.05), ("Unibet", 2.02)],
        "PSG +2.5": [("Betclic", 1.60), ("Unibet", 1.62)],
        "OM -2.5": [("Betclic", 2.50), ("Unibet", 2.48)],
    }

    # Arbitrage +1.5/-1.5 : 1/1.98 + 1/2.05 = 0.994 → profit ~0.6% (trop faible)
    # Arbitrage +2.5/-2.5 : 1/1.62 + 1/2.50 = 1.017 → pas un arbitrage
    # Donc aucun spread n'est en arbitrage → doit retourner None
    surebet = scanner._find_spreads_arbitrage(
        market_data, "Football", "Ligue 1", "PSG vs OM", "spreads"
    )
    if surebet is None:
        r.ok("Aucun arbitrage spread détecté (profit trop faible)")
    else:
        r.fail("Aucun arbitrage spread attendu", f"Reçu: {surebet.market}")

    # Test avec un vrai arbitrage spread
    market_data_arbitrage = {
        "PSG +1.5": [("Betclic", 2.10), ("Unibet", 2.08)],
        "OM -1.5": [("Betclic", 2.10), ("Unibet", 2.08)],
    }
    # 1/2.10 + 1/2.10 = 0.952 → profit ~4.8%
    surebet2 = scanner._find_spreads_arbitrage(
        market_data_arbitrage, "Football", "Ligue 1", "Lyon vs Monaco", "spreads"
    )
    if surebet2 is not None:
        r.ok(f"Arbitrage spread détecté (profit={surebet2.result.profit_pct:.1f}%)")
    else:
        r.fail("Arbitrage spread attendu", "Reçu: None")

    # Deuxième scan → cooldown
    surebet3 = scanner._find_spreads_arbitrage(
        market_data_arbitrage, "Football", "Ligue 1", "Lyon vs Monaco", "spreads"
    )
    if surebet3 is None:
        r.ok("Deuxième scan spreads retourne None (cooldown actif)")
    else:
        r.fail("Deuxième scan spreads retourne None", f"Reçu: {surebet3.market}")


# ─── TEST 5: Nouveaux créneaux scheduler ─────────────────────────────────────

def test_nouveaux_creneaux_scheduler(r: TestResults):
    print("\n[TEST 5] Nouveaux créneaux scheduler (nfl_night + late_evening)")

    # Vérifier que les nouveaux créneaux sont dans SCHEDULE_SLOTS
    if "nfl_night" in SCHEDULE_SLOTS:
        r.ok("Créneau 'nfl_night' présent dans SCHEDULE_SLOTS")
    else:
        r.fail("Créneau 'nfl_night' présent", "Absent de SCHEDULE_SLOTS")

    if "late_evening" in SCHEDULE_SLOTS:
        r.ok("Créneau 'late_evening' présent dans SCHEDULE_SLOTS")
    else:
        r.fail("Créneau 'late_evening' présent", "Absent de SCHEDULE_SLOTS")

    # Vérifier SLOT_PRIORITY
    if "nfl_night" in SLOT_PRIORITY and "late_evening" in SLOT_PRIORITY:
        r.ok("Les nouveaux créneaux sont dans SLOT_PRIORITY")
    else:
        r.fail("Nouveaux créneaux dans SLOT_PRIORITY", f"SLOT_PRIORITY={SLOT_PRIORITY}")

    # nfl_night doit être avant evening_weekday
    nfl_idx = SLOT_PRIORITY.index("nfl_night")
    eve_idx = SLOT_PRIORITY.index("evening_weekday")
    if nfl_idx < eve_idx:
        r.ok("nfl_night est prioritaire sur evening_weekday")
    else:
        r.fail("nfl_night prioritaire sur evening_weekday", f"nfl={nfl_idx}, eve={eve_idx}")

    # late_evening doit être après evening_weekday
    late_idx = SLOT_PRIORITY.index("late_evening")
    if late_idx > eve_idx:
        r.ok("late_evening est après evening_weekday")
    else:
        r.fail("late_evening après evening_weekday", f"late={late_idx}, eve={eve_idx}")

    # Vérifier les heures du créneau nfl_night
    nfl_hours = SCHEDULE_SLOTS["nfl_night"]["hours"]
    if nfl_hours == (1, 4):
        r.ok("nfl_night couvre bien 01h-04h CET")
    else:
        r.fail("nfl_night heures attendues (1, 4)", f"Reçu: {nfl_hours}")

    # Vérifier les sports prioritaires
    if "americanfootball_*" in SPORT_PRIORITY.get("nfl_night", []):
        r.ok("americanfootball_* est 1ère priorité dans nfl_night")
    else:
        r.fail("americanfootball_* 1ère priorité nfl_night", f"Reçu: {SPORT_PRIORITY.get('nfl_night')}")

    # Vérifier tennis dans evening_weekday
    if "tennis_*" in SPORT_PRIORITY.get("evening_weekday", []):
        r.ok("tennis_* ajouté à evening_weekday")
    else:
        r.fail("tennis_* dans evening_weekday", f"Reçu: {SPORT_PRIORITY.get('evening_weekday')}")

    # Vérifier soccer en 1ère position dans morning_realignment
    morning_sports = SPORT_PRIORITY.get("morning_realignment", [])
    if morning_sports and morning_sports[0] == "soccer_*":
        r.ok("soccer_* est 1ère priorité dans morning_realignment")
    else:
        r.fail("soccer_* 1ère priorité morning_realignment", f"Reçu: {morning_sports}")


# ─── TEST 6: Scheduler — détection des créneaux ──────────────────────────────

def test_scheduler_creneaux(r: TestResults):
    print("\n[TEST 6] SmartScheduler — détection des nouveaux créneaux")

    # Le scheduler accepte un now_func injectable — on l'utilise directement

    # Test nfl_night : lundi à 2h30 (weekday=0, hour=2)
    scheduler_nfl = SmartScheduler(now_func=lambda: datetime(2026, 3, 2, 2, 30))  # lundi
    slot_name, _ = scheduler_nfl.get_current_slot()
    if slot_name == "nfl_night":
        r.ok("Lundi 02h30 → créneau nfl_night détecté")
    else:
        r.fail("Lundi 02h30 → nfl_night", f"Reçu: {slot_name}")

    # Test late_evening : mardi à 22h00 (weekday=1, hour=22)
    scheduler_late = SmartScheduler(now_func=lambda: datetime(2026, 3, 3, 22, 0))  # mardi
    slot_name, _ = scheduler_late.get_current_slot()
    if slot_name == "late_evening":
        r.ok("Mardi 22h00 → créneau late_evening détecté")
    else:
        r.fail("Mardi 22h00 → late_evening", f"Reçu: {slot_name}")

    # Test live_weekend : samedi à 16h00 (weekday=5, hour=16)
    scheduler_we = SmartScheduler(now_func=lambda: datetime(2026, 3, 7, 16, 0))  # samedi
    slot_name, _ = scheduler_we.get_current_slot()
    if slot_name == "live_weekend":
        r.ok("Samedi 16h00 → créneau live_weekend détecté")
    else:
        r.fail("Samedi 16h00 → live_weekend", f"Reçu: {slot_name}")

    # Test default : mercredi à 4h (aucun créneau actif)
    scheduler_def = SmartScheduler(now_func=lambda: datetime(2026, 3, 4, 4, 0))  # mercredi
    slot_name, _ = scheduler_def.get_current_slot()
    if slot_name == "default":
        r.ok("Mercredi 04h00 → créneau default")
    else:
        r.fail("Mercredi 04h00 → default", f"Reçu: {slot_name}")


# ─── MAIN ────────────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("TESTS BUG FIXES — surebet_bot")
    print("=" * 60)

    r = TestResults()

    test_cooldown_atomique(r)
    test_cooldown_expiration(r)
    test_deduplication_totals_multilignes(r)
    test_deduplication_spreads_multilignes(r)
    test_nouveaux_creneaux_scheduler(r)
    test_scheduler_creneaux(r)

    success = r.summary()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
