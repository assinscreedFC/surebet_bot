# ================================================================
#   SmartScheduler — Scheduling intelligent pour Surebet Bot
# ================================================================
#   Adapte dynamiquement le comportement du bot en fonction de
#   l'heure et du jour : intervalle de scan, priorisation des
#   sports, alertes compositions.
# ================================================================

import fnmatch
from datetime import datetime, timedelta
from typing import Optional

from constants import (
    SCHEDULE_SLOTS,
    SLOT_PRIORITY,
    SPORT_PRIORITY,
    LINEUP_ALERT_MINUTES,
)


class SmartScheduler:
    """
    Scheduler intelligent qui adapte le scan en temps réel.

    Fonctionnalités:
    - Détecte le créneau temporel actuel (live, soir, matin, etc.)
    - Retourne l'intervalle de scan optimal
    - Priorise les sports selon le créneau
    - Détecte les matchs imminents (< 60 min) pour l'alerte compo
    - Notifie les changements de créneau
    """

    def __init__(self, now_func=None):
        """
        Args:
            now_func: Fonction retournant l'heure actuelle (pour les tests).
                      Par défaut: datetime.now()
        """
        self._now_func = now_func or datetime.now
        self._current_slot_name: Optional[str] = None
        self._slot_change_count = 0
        self._notified_matches: set[str] = set()

    @property
    def now(self) -> datetime:
        """Heure actuelle (injectable pour les tests)."""
        return self._now_func()

    # ── Créneau actuel ───────────────────────────────────────

    def get_current_slot(self) -> tuple[str, dict]:
        """
        Détermine le créneau temporel actif.

        Évalue les créneaux dans l'ordre de SLOT_PRIORITY.
        Le premier créneau correspondant à jour+heure est retourné.

        Returns:
            (slot_name, slot_config) — ex: ("live_weekend", {...})
        """
        now = self.now
        weekday = now.weekday()  # 0=lundi, 6=dimanche
        hour = now.hour

        for slot_name in SLOT_PRIORITY:
            slot = SCHEDULE_SLOTS[slot_name]

            if weekday in slot["days"]:
                start_h, end_h = slot["hours"]
                if start_h <= hour < end_h:
                    return slot_name, slot

        # Fallback (ne devrait jamais arriver car "default" couvre 0-24)
        return "default", SCHEDULE_SLOTS["default"]

    def has_slot_changed(self) -> tuple[bool, Optional[str], Optional[str]]:
        """
        Vérifie si le créneau a changé depuis le dernier appel.

        Returns:
            (changed, old_slot_name, new_slot_name)
        """
        new_name, _ = self.get_current_slot()

        if self._current_slot_name is None:
            # Premier appel
            self._current_slot_name = new_name
            return True, None, new_name

        if new_name != self._current_slot_name:
            old = self._current_slot_name
            self._current_slot_name = new_name
            self._slot_change_count += 1
            return True, old, new_name

        return False, self._current_slot_name, self._current_slot_name

    # ── Intervalle de scan ───────────────────────────────────

    def get_scan_interval(self) -> int:
        """
        Retourne l'intervalle de scan optimal (en secondes)
        pour le créneau actuel.
        """
        _, slot = self.get_current_slot()
        return slot["scan_interval"]

    # ── Priorisation des sports ──────────────────────────────

    def prioritize_sports(self, sports: dict[str, str]) -> dict[str, str]:
        """
        Trie les sports par pertinence pour le créneau actuel.

        Les sports correspondant aux patterns prioritaires sont
        placés en premier. Les autres suivent dans leur ordre original.

        Args:
            sports: {sport_key: display_name} — ex: {"soccer_epl": "Premier League"}

        Returns:
            Nouveau dict trié par priorité
        """
        slot_name, _ = self.get_current_slot()
        patterns = SPORT_PRIORITY.get(slot_name, ["*"])

        prioritized = {}
        remaining = dict(sports)

        # Uniquement les sports qui matchent les patterns du créneau actuel
        # (les sports hors-pattern sont ignorés pour économiser le quota API)
        for pattern in patterns:
            for sport_key, display in list(remaining.items()):
                if fnmatch.fnmatch(sport_key, pattern):
                    prioritized[sport_key] = display
                    del remaining[sport_key]

        return prioritized

    # ── Matchs imminents (alerte composition) ────────────────

    def get_upcoming_matches(
        self, events: list[dict], minutes: int = None
    ) -> list[dict]:
        """
        Filtre les événements commençant dans les prochaines N minutes.

        Utile pour l'alerte composition (1h avant le match en football).

        Args:
            events: Liste d'événements API (avec "commence_time" ISO 8601)
            minutes: Seuil en minutes (défaut: LINEUP_ALERT_MINUTES=60)

        Returns:
            Liste des événements imminents non encore notifiés
        """
        if minutes is None:
            minutes = LINEUP_ALERT_MINUTES

        now = self.now
        threshold = now + timedelta(minutes=minutes)
        upcoming = []

        for event in events:
            commence = event.get("commence_time")
            if not commence:
                continue

            try:
                # Parse ISO 8601 (The Odds API format)
                if commence.endswith("Z"):
                    commence_dt = datetime.fromisoformat(
                        commence.replace("Z", "+00:00")
                    )
                    # Convertir en heure locale naïve pour comparer
                    commence_dt = commence_dt.replace(tzinfo=None)
                else:
                    commence_dt = datetime.fromisoformat(commence)
                    if commence_dt.tzinfo:
                        commence_dt = commence_dt.replace(tzinfo=None)
            except (ValueError, TypeError):
                continue

            # Match dans la fenêtre [maintenant, maintenant + N min]
            if now <= commence_dt <= threshold:
                event_id = event.get("id", "")
                if event_id not in self._notified_matches:
                    self._notified_matches.add(event_id)
                    upcoming.append(event)

        return upcoming

    def clear_notified_matches(self):
        """Réinitialise le cache des matchs notifiés (à appeler périodiquement)."""
        self._notified_matches.clear()

    # ── Messages de status ───────────────────────────────────

    def get_status_message(self) -> str:
        """
        Retourne un message Telegram formaté sur le créneau actif.
        """
        slot_name, slot = self.get_current_slot()
        now = self.now

        return (
            f"⏰ <b>Créneau actif:</b> {slot['label']}\n"
            f"📋 {slot['description']}\n"
            f"⚡ Intervalle: {slot['scan_interval']}s\n"
            f"🕐 Heure: {now.strftime('%H:%M')} | "
            f"{'Week-end' if now.weekday() >= 5 else 'Semaine'}"
        )

    def get_slot_change_message(
        self, old_name: Optional[str], new_name: str
    ) -> str:
        """
        Retourne un message Telegram pour un changement de créneau.
        """
        new_slot = SCHEDULE_SLOTS[new_name]

        if old_name is None:
            return (
                f"🟢 <b>Scheduler démarré</b>\n\n"
                f"Créneau: {new_slot['label']}\n"
                f"Intervalle: {new_slot['scan_interval']}s\n"
                f"{new_slot['description']}"
            )

        old_slot = SCHEDULE_SLOTS[old_name]
        return (
            f"🔄 <b>Changement de créneau</b>\n\n"
            f"Avant: {old_slot['label']} ({old_slot['scan_interval']}s)\n"
            f"Après: {new_slot['label']} ({new_slot['scan_interval']}s)\n\n"
            f"📋 {new_slot['description']}"
        )

    def get_lineup_alert_message(self, events: list[dict]) -> str:
        """
        Message Telegram pour les matchs imminents (alerte composition).
        """
        if not events:
            return ""

        lines = [f"📋 <b>Matchs dans moins de {LINEUP_ALERT_MINUTES} min</b>\n"]

        for event in events[:10]:  # Max 10 pour éviter les messages trop longs
            home = event.get("home_team", "?")
            away = event.get("away_team", "?")
            commence = event.get("commence_time", "")

            try:
                if commence.endswith("Z"):
                    dt = datetime.fromisoformat(commence.replace("Z", "+00:00"))
                    dt = dt.replace(tzinfo=None)
                else:
                    dt = datetime.fromisoformat(commence)
                    if dt.tzinfo:
                        dt = dt.replace(tzinfo=None)
                time_str = dt.strftime("%H:%M")
            except (ValueError, TypeError):
                time_str = "?"

            lines.append(f"⚽ {home} vs {away} — {time_str}")

        lines.append(
            f"\n💡 <i>Surveillez les compositions ! "
            f"Décalage de cotes possible.</i>"
        )

        return "\n".join(lines)

    # ── Stats ────────────────────────────────────────────────

    def get_stats(self) -> dict:
        """Retourne les stats du scheduler pour le status du bot."""
        slot_name, slot = self.get_current_slot()
        return {
            "current_slot": slot_name,
            "slot_label": slot["label"],
            "scan_interval": slot["scan_interval"],
            "slot_changes": self._slot_change_count,
            "notified_matches": len(self._notified_matches),
        }
