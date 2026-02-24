#!/usr/bin/env python3
"""
=================================================================
  TEST SCHEDULER — Smart Scheduling pour Surebet Bot
=================================================================
  Teste toutes les fonctionnalités du SmartScheduler :
  1. Détection de créneau (jour/heure)
  2. Intervalle dynamique
  3. Priorisation des sports
  4. Matchs imminents (alerte composition)
  5. Changement de créneau
  6. Messages Telegram formatés
  7. Edge cases (minuit, chevauchements)
=================================================================
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta

# Setup path
SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))


# ============================================================
# Utilitaires
# ============================================================

class TestResults:
    def __init__(self):
        self.tests = []
        self.passed = 0
        self.failed = 0

    def add(self, name, passed, details=""):
        status = "✅ PASS" if passed else "❌ FAIL"
        self.tests.append({"name": name, "status": status, "details": details})
        if passed:
            self.passed += 1
        else:
            self.failed += 1
        print(f"  {status} {name}")
        if details:
            for line in details.split("\n"):
                print(f"       {line}")

    def summary(self):
        total = self.passed + self.failed
        print("\n" + "=" * 60)
        print("  RÉSUMÉ DES TESTS SCHEDULER")
        print("=" * 60)
        print(f"  Total: {total} tests")
        print(f"  ✅ Passés: {self.passed}")
        print(f"  ❌ Échoués: {self.failed}")
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


def make_now(year=2026, month=2, day=23, hour=15, minute=0):
    """Helper pour créer une fonction now() prévisible."""
    dt = datetime(year, month, day, hour, minute)
    return lambda: dt


# ============================================================
# TEST 1: Détection de créneau
# ============================================================

def test_slot_detection():
    print("\n" + "─" * 60)
    print("  TEST 1: Détection de créneau")
    print("─" * 60)

    from core.scheduler import SmartScheduler

    # Samedi 15h → live_weekend
    sched = SmartScheduler(now_func=make_now(day=21, hour=15))  # 21 fév 2026 = samedi
    slot_name, slot = sched.get_current_slot()
    results.add(
        "Samedi 15h → live_weekend",
        slot_name == "live_weekend",
        f"Résultat: {slot_name} ({slot['label']})"
    )

    # Dimanche 20h → live_weekend
    sched = SmartScheduler(now_func=make_now(day=22, hour=20))  # dimanche
    slot_name, _ = sched.get_current_slot()
    results.add(
        "Dimanche 20h → live_weekend",
        slot_name == "live_weekend",
        f"Résultat: {slot_name}"
    )

    # Mardi 20h → evening_weekday
    sched = SmartScheduler(now_func=make_now(day=24, hour=20))  # mardi
    slot_name, _ = sched.get_current_slot()
    results.add(
        "Mardi 20h → evening_weekday",
        slot_name == "evening_weekday",
        f"Résultat: {slot_name}"
    )

    # Jeudi 18h → boosted_odds
    sched = SmartScheduler(now_func=make_now(day=26, hour=18))  # jeudi
    slot_name, _ = sched.get_current_slot()
    results.add(
        "Jeudi 18h → boosted_odds",
        slot_name == "boosted_odds",
        f"Résultat: {slot_name}"
    )

    # Mercredi 9h30 → morning_realignment
    sched = SmartScheduler(now_func=make_now(day=25, hour=9, minute=30))  # mercredi
    slot_name, _ = sched.get_current_slot()
    results.add(
        "Mercredi 9h30 → morning_realignment",
        slot_name == "morning_realignment",
        f"Résultat: {slot_name}"
    )

    # Mardi 3h → default (hors créneau)
    sched = SmartScheduler(now_func=make_now(day=24, hour=3))
    slot_name, _ = sched.get_current_slot()
    results.add(
        "Mardi 3h → default",
        slot_name == "default",
        f"Résultat: {slot_name}"
    )

    # Samedi 10h → pas live_weekend (avant 14h), devrait être morning_realignment
    # 10h est hors de (9,10) donc → default
    sched = SmartScheduler(now_func=make_now(day=21, hour=10))
    slot_name, _ = sched.get_current_slot()
    results.add(
        "Samedi 10h → default (entre matin et live)",
        slot_name == "default",
        f"Résultat: {slot_name}"
    )


# ============================================================
# TEST 2: Intervalle dynamique
# ============================================================

def test_scan_interval():
    print("\n" + "─" * 60)
    print("  TEST 2: Intervalle de scan dynamique")
    print("─" * 60)

    from core.scheduler import SmartScheduler

    # live_weekend → 5s
    sched = SmartScheduler(now_func=make_now(day=21, hour=15))
    interval = sched.get_scan_interval()
    results.add(
        "live_weekend → 5s",
        interval == 5,
        f"Intervalle: {interval}s"
    )

    # evening_weekday → 5s
    sched = SmartScheduler(now_func=make_now(day=24, hour=20))
    interval = sched.get_scan_interval()
    results.add(
        "evening_weekday → 5s",
        interval == 5,
        f"Intervalle: {interval}s"
    )

    # boosted_odds → 7s
    sched = SmartScheduler(now_func=make_now(day=26, hour=18))
    interval = sched.get_scan_interval()
    results.add(
        "boosted_odds → 7s",
        interval == 7,
        f"Intervalle: {interval}s"
    )

    # morning_realignment → 8s
    sched = SmartScheduler(now_func=make_now(day=25, hour=9))
    interval = sched.get_scan_interval()
    results.add(
        "morning_realignment → 8s",
        interval == 8,
        f"Intervalle: {interval}s"
    )

    # default → 15s
    sched = SmartScheduler(now_func=make_now(day=24, hour=3))
    interval = sched.get_scan_interval()
    results.add(
        "default → 15s",
        interval == 15,
        f"Intervalle: {interval}s"
    )


# ============================================================
# TEST 3: Priorisation des sports
# ============================================================

def test_sport_priority():
    print("\n" + "─" * 60)
    print("  TEST 3: Priorisation des sports")
    print("─" * 60)

    from core.scheduler import SmartScheduler

    sports = {
        "americanfootball_nfl": "NFL",
        "basketball_nba": "NBA",
        "soccer_epl": "Premier League",
        "soccer_france_ligue_one": "Ligue 1",
        "tennis_atp_wimbledon": "Wimbledon",
    }

    # evening_weekday → soccer, basketball prioritaires
    sched = SmartScheduler(now_func=make_now(day=24, hour=20))
    prioritized = sched.prioritize_sports(sports)
    keys = list(prioritized.keys())

    # soccer et basketball doivent être en premier
    soccer_basketball_first = all(
        k.startswith("soccer_") or k.startswith("basketball_")
        for k in keys[:3]
    )
    results.add(
        "Soir semaine: soccer/basketball en premier",
        soccer_basketball_first,
        f"Ordre: {keys}"
    )

    # morning_realignment → basketball, americanfootball, soccer
    sched = SmartScheduler(now_func=make_now(day=25, hour=9))
    prioritized = sched.prioritize_sports(sports)
    keys = list(prioritized.keys())

    results.add(
        "Matin: basketball/NFL en premier",
        keys[0].startswith("basketball_") or keys[0].startswith("americanfootball_"),
        f"Ordre: {keys}"
    )

    # default → pas de changement d'ordre
    sched = SmartScheduler(now_func=make_now(day=24, hour=3))
    prioritized = sched.prioritize_sports(sports)
    results.add(
        "Hors-créneau: tous les sports inclus",
        len(prioritized) == len(sports),
        f"Count: {len(prioritized)}/{len(sports)}"
    )


# ============================================================
# TEST 4: Matchs imminents (alerte composition)
# ============================================================

def test_upcoming_matches():
    print("\n" + "─" * 60)
    print("  TEST 4: Matchs imminents")
    print("─" * 60)

    from core.scheduler import SmartScheduler

    base_time = datetime(2026, 2, 23, 19, 0)
    sched = SmartScheduler(now_func=lambda: base_time)

    events = [
        # Match dans 30 min → IMMINENT
        {
            "id": "evt_1",
            "home_team": "PSG",
            "away_team": "OM",
            "commence_time": "2026-02-23T19:30:00Z",
        },
        # Match dans 2h → PAS imminent
        {
            "id": "evt_2",
            "home_team": "Lyon",
            "away_team": "Monaco",
            "commence_time": "2026-02-23T21:00:00Z",
        },
        # Match dans 45 min → IMMINENT
        {
            "id": "evt_3",
            "home_team": "Arsenal",
            "away_team": "Chelsea",
            "commence_time": "2026-02-23T19:45:00Z",
        },
        # Match déjà commencé → PAS imminent
        {
            "id": "evt_4",
            "home_team": "Barça",
            "away_team": "Real",
            "commence_time": "2026-02-23T18:00:00Z",
        },
    ]

    upcoming = sched.get_upcoming_matches(events, minutes=60)
    results.add(
        "Matchs dans 60 min: 2 matchs",
        len(upcoming) == 2,
        f"Trouvés: {len(upcoming)} — {[e['id'] for e in upcoming]}"
    )

    # Vérifier les bons matchs
    ids = {e["id"] for e in upcoming}
    results.add(
        "Bons matchs détectés (evt_1 + evt_3)",
        ids == {"evt_1", "evt_3"},
        f"IDs: {ids}"
    )

    # Deuxième appel → pas de doublons (déjà notifiés)
    upcoming2 = sched.get_upcoming_matches(events, minutes=60)
    results.add(
        "Pas de doublons au deuxième appel",
        len(upcoming2) == 0,
        f"Deuxième appel: {len(upcoming2)} matchs"
    )

    # Après clear → réinitialisation
    sched.clear_notified_matches()
    upcoming3 = sched.get_upcoming_matches(events, minutes=60)
    results.add(
        "Matchs retrouvés après clear",
        len(upcoming3) == 2,
        f"Après clear: {len(upcoming3)} matchs"
    )


# ============================================================
# TEST 5: Changement de créneau
# ============================================================

def test_slot_change():
    print("\n" + "─" * 60)
    print("  TEST 5: Changement de créneau")
    print("─" * 60)

    from core.scheduler import SmartScheduler

    current_time = [datetime(2026, 2, 24, 18, 0)]  # mardi 18h → boosted_odds

    def mock_now():
        return current_time[0]

    sched = SmartScheduler(now_func=mock_now)

    # Premier appel → changement (initialisation)
    changed, old, new = sched.has_slot_changed()
    results.add(
        "Premier appel: initialisation",
        changed and old is None and new == "boosted_odds",
        f"changed={changed}, old={old}, new={new}"
    )

    # Même heure → pas de changement
    changed, old, new = sched.has_slot_changed()
    results.add(
        "Même heure: pas de changement",
        not changed,
        f"changed={changed}"
    )

    # Changement vers evening_weekday (20h)
    current_time[0] = datetime(2026, 2, 24, 20, 0)
    changed, old, new = sched.has_slot_changed()
    results.add(
        "18h→20h: boosted_odds → evening_weekday",
        changed and old == "boosted_odds" and new == "evening_weekday",
        f"changed={changed}, old={old}, new={new}"
    )

    # Changement vers default (23h)
    current_time[0] = datetime(2026, 2, 24, 23, 0)
    changed, old, new = sched.has_slot_changed()
    results.add(
        "20h→23h: evening_weekday → default",
        changed and old == "evening_weekday" and new == "default",
        f"changed={changed}, old={old}, new={new}"
    )

    # Stats
    stats = sched.get_stats()
    results.add(
        "Stats: 3 changements comptés",
        stats["slot_changes"] == 3,
        f"slot_changes={stats['slot_changes']}"
    )


# ============================================================
# TEST 6: Messages Telegram
# ============================================================

def test_messages():
    print("\n" + "─" * 60)
    print("  TEST 6: Messages Telegram formatés")
    print("─" * 60)

    from core.scheduler import SmartScheduler

    sched = SmartScheduler(now_func=make_now(day=21, hour=15))

    # Status message
    msg = sched.get_status_message()
    results.add(
        "Status message contient le créneau",
        "LIVE Week-end" in msg and "15:00" in msg,
        f"Message: {msg[:100]}..."
    )

    # Slot change message (initialisation)
    msg = sched.get_slot_change_message(None, "live_weekend")
    results.add(
        "Slot change (init): contient 'démarré'",
        "démarré" in msg,
        f"Message: {msg[:80]}..."
    )

    # Slot change message (transition)
    msg = sched.get_slot_change_message("boosted_odds", "evening_weekday")
    results.add(
        "Slot change (transition): contient Avant/Après",
        "Avant" in msg and "Après" in msg and "Cotes Boostées" in msg,
        f"Message: {msg[:100]}..."
    )

    # Lineup alert message
    events = [
        {"home_team": "PSG", "away_team": "OM", "commence_time": "2026-02-23T19:30:00Z"},
        {"home_team": "Lyon", "away_team": "Monaco", "commence_time": "2026-02-23T19:45:00Z"},
    ]
    msg = sched.get_lineup_alert_message(events)
    results.add(
        "Lineup alert: contient les matchs",
        "PSG" in msg and "Lyon" in msg and "compositions" in msg.lower(),
        f"Message: {msg[:120]}..."
    )

    # Lineup alert vide
    msg = sched.get_lineup_alert_message([])
    results.add(
        "Lineup alert vide: string vide",
        msg == "",
        f"Message: '{msg}'"
    )


# ============================================================
# TEST 7: Edge cases
# ============================================================

def test_edge_cases():
    print("\n" + "─" * 60)
    print("  TEST 7: Edge cases")
    print("─" * 60)

    from core.scheduler import SmartScheduler

    # Minuit → default
    sched = SmartScheduler(now_func=make_now(day=24, hour=0))
    slot_name, _ = sched.get_current_slot()
    results.add(
        "Minuit → default",
        slot_name == "default",
        f"Résultat: {slot_name}"
    )

    # 23h59 → default
    sched = SmartScheduler(now_func=make_now(day=24, hour=23, minute=59))
    slot_name, _ = sched.get_current_slot()
    results.add(
        "23h59 → default",
        slot_name == "default",
        f"Résultat: {slot_name}"
    )

    # Chevauchement: samedi 19h → live_weekend (prioritaire sur boosted_odds)
    sched = SmartScheduler(now_func=make_now(day=21, hour=19))
    slot_name, _ = sched.get_current_slot()
    results.add(
        "Samedi 19h: live_weekend > boosted_odds (priorité)",
        slot_name == "live_weekend",
        f"Résultat: {slot_name}"
    )

    # Chevauchement: mardi 19h30 → evening_weekday (prioritaire sur boosted_odds) 
    sched = SmartScheduler(now_func=make_now(day=24, hour=19, minute=30))
    slot_name, _ = sched.get_current_slot()
    results.add(
        "Mardi 19h30: evening_weekday > boosted_odds (priorité)",
        slot_name == "evening_weekday",
        f"Résultat: {slot_name}"
    )

    # Priorisation avec dict vide
    sched = SmartScheduler(now_func=make_now(day=24, hour=20))
    prioritized = sched.prioritize_sports({})
    results.add(
        "Priorisation dict vide → dict vide",
        len(prioritized) == 0,
        f"Résultat: {prioritized}"
    )

    # Upcoming matches avec événement sans commence_time
    sched = SmartScheduler(now_func=make_now(day=23, hour=19))
    events = [{"id": "evt_bad", "home_team": "A", "away_team": "B"}]
    upcoming = sched.get_upcoming_matches(events, minutes=60)
    results.add(
        "Event sans commence_time → ignoré",
        len(upcoming) == 0,
        f"Résultat: {len(upcoming)}"
    )

    # Upcoming matches avec format de date invalide
    events = [{"id": "evt_bad2", "home_team": "A", "away_team": "B", "commence_time": "invalid"}]
    upcoming = sched.get_upcoming_matches(events, minutes=60)
    results.add(
        "Date invalide → ignoré",
        len(upcoming) == 0,
        f"Résultat: {len(upcoming)}"
    )


# ============================================================
# MAIN
# ============================================================

def main():
    print("=" * 60)
    print("  TEST SMARTSCHEDULER — Surebet Bot")
    print(f"  {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
    print("=" * 60)

    test_slot_detection()
    test_scan_interval()
    test_sport_priority()
    test_upcoming_matches()
    test_slot_change()
    test_messages()
    test_edge_cases()

    return results.summary()


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
