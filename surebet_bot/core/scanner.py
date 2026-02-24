# Scanner de cotes et détection d'arbitrage - Version Corrigée
# Intègre le SmartScheduler pour un scan adaptatif

import asyncio
from datetime import datetime, timedelta
from typing import Optional
from dataclasses import dataclass, field
from collections import deque

from core.odds_client import OddsClient
from core.calculator import calculate_arbitrage, SurebetResult
from core.api_manager import APIManager
from core.scheduler import SmartScheduler
from notifications.telegram_bot import TelegramBot


@dataclass
class SurebetOpportunity:
    """Une opportunité de surebet détectée."""
    sport: str
    league: str
    match: str
    market: str
    outcomes: list[dict]  # [{bookmaker, name, odds}, ...]
    result: SurebetResult
    detected_at: datetime = field(default_factory=datetime.now)


class SurebetScanner:
    """
    Scanner asynchrone de surebets.
    
    - Scan toutes les SCAN_INTERVAL secondes
    - Détecte les arbitrages entre bookmakers
    - Cooldown pour éviter les doublons
    
    Correction majeure: Compare maintenant les outcomes OPPOSÉS
    (Over vs Under) au lieu des mêmes outcomes.
    """
    
    def __init__(
        self,
        api_manager: APIManager,
        telegram: TelegramBot,
        database = None,
        scan_interval: int = 10,
        cooldown_minutes: int = 5,
        bookmakers: list[str] = None,
        request_delay: float = 3.0,
        scheduler: SmartScheduler = None
    ):
        self.api_manager = api_manager
        self.telegram = telegram
        self.db = database
        self.scan_interval = scan_interval
        self.cooldown_minutes = cooldown_minutes
        self.bookmakers = bookmakers or []
        self.request_delay = request_delay
        
        # Smart Scheduler (optionnel — fallback sur scan_interval fixe)
        self.scheduler = scheduler or SmartScheduler()
        
        self.client: Optional[OddsClient] = None
        self.running = False
        # Limiter à 1000 surebets en mémoire pour éviter la croissance infinie
        self.surebets_found: deque = deque(maxlen=1000)
        self.cooldown_cache: dict[str, datetime] = {}
        
        # Stats
        self.scans_count = 0
        self.start_time: Optional[datetime] = None
        self.requests_remaining = 0
        self.errors_count = 0
        self.last_error = None
        self.api_exhausted = False  # Flag pour arrêter si plus de clés
        
        # Retry logic avec backoff
        self.waiting_for_key = False
        self.retry_count = 0
        self.max_backoff_minutes = 10  # Max 10 minutes entre les retries
        self.force_stop = False  # Arrêt forcé via Telegram
    
    def _get_client(self) -> OddsClient:
        """Crée/met à jour le client avec la clé active."""
        key = self.api_manager.current_key
        if self.client is None or self.client.api_key != key:
            if self.client:
                asyncio.create_task(self.client.close())
            self.client = OddsClient(key, request_delay=self.request_delay)
        return self.client
    
    def _is_in_cooldown(self, identifier: str) -> bool:
        """Vérifie si une opportunité est en cooldown."""
        if identifier not in self.cooldown_cache:
            return False
        
        expires = self.cooldown_cache[identifier]
        if datetime.now() > expires:
            del self.cooldown_cache[identifier]
            return False
        
        return True
    
    def _add_cooldown(self, identifier: str):
        """Ajoute une opportunité au cooldown."""
        expires = datetime.now() + timedelta(minutes=self.cooldown_minutes)
        self.cooldown_cache[identifier] = expires
    
    def _cleanup_cooldown_cache(self):
        """Nettoie le cache de cooldown des entrées expirées."""
        now = datetime.now()
        expired = [
            key for key, expires in self.cooldown_cache.items()
            if now > expires
        ]
        for key in expired:
            del self.cooldown_cache[key]
    
    async def _scan_sport(self, sport_key: str, sport_name: str, markets: str = "h2h,totals"):
        """
        Scanne un sport pour les surebets.
        
        Marchés supportés:
        - h2h: 1X2 / Moneyline (2-way ou 3-way)
        - totals: Over/Under (2-way)
        - spreads: Handicap (2-way)
        """
        client = self._get_client()
        
        if client is None:
            await self._handle_error("Aucune clé API disponible!")
            self.api_exhausted = True
            return []
        
        response = await client.get_odds(
            sport=sport_key,
            regions="eu,fr",
            markets=markets,
            bookmakers=self.bookmakers if self.bookmakers else None
        )
        
        # Mettre à jour le quota
        self.requests_remaining = response.requests_remaining
        
        # Enregistrer l'usage API dans la DB
        await self._log_api_usage(response.requests_used, response.requests_remaining)
        
        # Gérer les erreurs API
        if not response.success:
            error_msg = f"API Error {response.status_code}: {response.error or 'Unknown'}"
            print(f"[Scanner] ❌ {error_msg}")
            
            # Détecter les erreurs de quota (plusieurs codes possibles)
            quota_error = (
                response.status_code in [401, 402, 429] or
                "OUT_OF_USAGE_CREDITS" in (response.error or "") or
                "quota" in (response.error or "").lower()
            )
            
            if quota_error:
                old_key = self.api_manager.current_key
                success = await self.api_manager.handle_api_error(
                    response.status_code, 
                    response.error or ""
                )
                
                if success:
                    new_key = self.api_manager.current_key
                    await self.telegram.send_failover_notice(old_key, new_key)
                    print(f"[Scanner] ✅ Failover réussi: {old_key[:8]}... → {new_key[:8]}...")
                else:
                    # Plus de clés disponibles - on attend et on réessaie
                    await self._handle_error(
                        f"⚠️ QUOTA API ÉPUISÉ!\n\n"
                        f"Toutes les clés sont invalides.\n"
                        f"Tentative de génération en cours...\n\n"
                        f"Le bot réessaiera dans 5 minutes."
                    )
                    # NE PAS mettre api_exhausted = True, on va réessayer
                    self.waiting_for_key = True
            else:
                # Autre erreur - notifier sur Telegram
                await self._handle_error(f"Erreur API ({sport_name}): {error_msg}")
            
            return []
        
        surebets = []
        raw_odds_batch = []  # Pour enregistrer toutes les cotes
        
        for event in response.data or []:
            match_name = f"{event['home_team']} vs {event['away_team']}"
            
            # Collecter toutes les cotes par marché
            markets_data = self._extract_markets(event)
            
            # Enregistrer toutes les cotes brutes pour analyse
            for market_key, market_data in markets_data.items():
                for outcome_name, bookmaker_odds in market_data.items():
                    for bookmaker, odds_value in bookmaker_odds:
                        raw_odds_batch.append({
                            "sport": sport_name,
                            "match": match_name,
                            "market": market_key,
                            "bookmaker": bookmaker,
                            "outcome": outcome_name,
                            "odds": odds_value
                        })
            
            # Chercher les surebets pour chaque marché
            for market_key, market_data in markets_data.items():
                surebet = self._find_arbitrage(
                    market_data=market_data,
                    market_key=market_key,
                    sport=sport_name,
                    league=sport_name,
                    match=match_name
                )
                
                if surebet:
                    surebets.append(surebet)
        
        # Sauvegarder toutes les cotes brutes dans la DB
        await self._save_raw_odds_batch(raw_odds_batch)
        
        return surebets
    
    async def _handle_error(self, error_msg: str):
        """Gère une erreur: log + notification Telegram."""
        self.errors_count += 1
        self.last_error = error_msg
        print(f"[Scanner] ❌ {error_msg}")
        
        # Envoyer sur Telegram
        await self.telegram.send_error(error_msg)
        
        # Enregistrer dans la DB si disponible
        if self.db:
            try:
                await self.db.add_log("ERROR", error_msg)
            except Exception as e:
                # Logger l'erreur au lieu de l'ignorer silencieusement
                print(f"[Scanner] ⚠️ Impossible d'enregistrer le log en DB: {e}")
    
    async def _log_api_usage(self, used: int, remaining: int):
        """Enregistre l'usage API dans la DB."""
        if self.db and self.api_manager.current_key:
            try:
                await self.db.log_api_usage(
                    self.api_manager.current_key,
                    used,
                    remaining
                )
            except Exception as e:
                # Logger l'erreur au lieu de l'ignorer silencieusement
                print(f"[Scanner] ⚠️ Impossible d'enregistrer l'usage API en DB: {e}")
    
    async def _save_raw_odds_batch(self, raw_odds_batch: list[dict]):
        """Enregistre les cotes brutes dans la DB."""
        if self.db and raw_odds_batch:
            try:
                await self.db.save_raw_odds_batch(raw_odds_batch)
                print(f"[Scanner] 💾 {len(raw_odds_batch)} cotes enregistrées")
            except Exception as e:
                # Logger l'erreur avec plus de détails
                print(f"[Scanner] ⚠️ Erreur sauvegarde cotes: {e}")
                import traceback
                print(f"[Scanner] Traceback: {traceback.format_exc()}")
    
    async def _wait_and_retry_key_generation(self):
        """
        Attend avec backoff progressif et réessaie de générer une clé.
        
        Backoff: 1min, 2min, 3min... jusqu'à 10min
        Puis retry toutes les 10min indéfiniment.
        """
        self.retry_count += 1
        
        # Calculer le temps d'attente (1 à 10 min)
        wait_minutes = min(self.retry_count, self.max_backoff_minutes)
        wait_seconds = wait_minutes * 60
        
        print(f"[Scanner] ⏳ Attente {wait_minutes} minute(s) avant retry #{self.retry_count}...")
        await self.telegram.send_message(
            f"⏳ <b>Attente avant retry</b>\n\n"
            f"Retry #{self.retry_count}\n"
            f"Attente: {wait_minutes} minute(s)\n\n"
            f"Envoyez /stop pour arrêter le bot."
        )
        
        # Attendre (vérifier force_stop toutes les 30s)
        for _ in range(wait_seconds // 30):
            if self.force_stop:
                print("[Scanner] ⛔ Arrêt demandé via Telegram")
                return False
            await asyncio.sleep(30)
        
        # Réessayer de générer une clé
        print(f"[Scanner] 🔄 Tentative de génération de clé #{self.retry_count}...")
        await self.telegram.send_message(f"🔄 Tentative de génération de clé #{self.retry_count}...")
        
        success = await self.api_manager.generate_new_key()
        
        if success:
            self.api_manager.load_keys()
            self.waiting_for_key = False
            self.retry_count = 0
            
            new_key = self.api_manager.current_key
            print(f"[Scanner] ✅ Nouvelle clé générée: {new_key[:8]}...")
            await self.telegram.send_message(
                f"🎉 <b>Nouvelle clé API générée!</b>\n\n"
                f"🔑 Clé: {new_key[:8]}...\n"
                f"Le bot reprend le scan."
            )
            return True
        else:
            print(f"[Scanner] ❌ Génération échouée, prochain retry dans {min(self.retry_count + 1, 10)} min")
            return False
    
    def request_stop(self):
        """Demande l'arrêt du bot (appelé via Telegram)."""
        self.force_stop = True
        self.running = False
        print("[Scanner] ⛔ Arrêt demandé")
    
    def _extract_markets(self, event: dict) -> dict:
        """
        Extrait tous les marchés et cotes d'un événement.
        
        Returns:
            {
                "h2h": {
                    "Home Team": [(bookmaker, odds), ...],
                    "Away Team": [(bookmaker, odds), ...],
                    "Draw": [(bookmaker, odds), ...]
                },
                "totals": {
                    "Over 2.5": [(bookmaker, odds), ...],
                    "Under 2.5": [(bookmaker, odds), ...]
                }
            }
        """
        markets = {}
        
        for bookmaker in event.get("bookmakers", []):
            bookmaker_name = bookmaker.get("title", "Unknown")
            
            for market in bookmaker.get("markets", []):
                market_key = market.get("key", "h2h")
                
                if market_key not in markets:
                    markets[market_key] = {}
                
                for outcome in market.get("outcomes", []):
                    # Construire le nom complet de l'outcome
                    name = outcome.get("name", "Unknown")
                    point = outcome.get("point")
                    
                    if point is not None:
                        # Pour les totals/spreads, inclure la ligne
                        full_name = f"{name} {point}"
                    else:
                        full_name = name
                    
                    price = outcome.get("price", 0)
                    
                    if price > 1:
                        if full_name not in markets[market_key]:
                            markets[market_key][full_name] = []
                        markets[market_key][full_name].append((bookmaker_name, price))
        
        return markets
    
    def _find_arbitrage(
        self,
        market_data: dict,
        market_key: str,
        sport: str,
        league: str,
        match: str
    ) -> Optional[SurebetOpportunity]:
        """
        Cherche un arbitrage dans les données d'un marché.
        
        LOGIQUE CORRIGÉE:
        - Pour h2h 3-way: Compare Home vs Away vs Draw
        - Pour h2h 2-way: Compare Home vs Away
        - Pour totals: Compare Over X vs Under X
        - Pour spreads: Compare les handicaps opposés
        """
        if market_key == "totals":
            return self._find_totals_arbitrage(market_data, sport, league, match, market_key)
        elif market_key == "h2h":
            return self._find_h2h_arbitrage(market_data, sport, league, match, market_key)
        elif market_key == "spreads":
            return self._find_spreads_arbitrage(market_data, sport, league, match, market_key)
        
        return None
    
    def _find_totals_arbitrage(
        self,
        market_data: dict,
        sport: str,
        league: str,
        match: str,
        market_key: str
    ) -> Optional[SurebetOpportunity]:
        """
        Trouve un arbitrage sur les totals (Over/Under).
        
        On cherche: Meilleure cote Over X + Meilleure cote Under X
        où X est la même ligne (ex: 2.5 buts)
        """
        # Regrouper par ligne
        lines = {}
        for outcome_name, bookmaker_odds in market_data.items():
            parts = outcome_name.split()
            if len(parts) >= 2:
                side = parts[0]  # Over ou Under
                line = parts[1]  # 2.5
                
                if line not in lines:
                    lines[line] = {"Over": [], "Under": []}
                
                if side in lines[line]:
                    lines[line][side].extend(bookmaker_odds)
        
        # Chercher un arbitrage pour chaque ligne
        for line, sides in lines.items():
            if not sides["Over"] or not sides["Under"]:
                continue
            
            # Meilleure cote Over
            best_over = max(sides["Over"], key=lambda x: x[1])
            # Meilleure cote Under
            best_under = max(sides["Under"], key=lambda x: x[1])
            
            # Calculer l'arbitrage
            result = calculate_arbitrage([best_over[1], best_under[1]])
            
            if result.is_surebet:
                identifier = f"{match}_{market_key}_{line}"
                
                if self._is_in_cooldown(identifier):
                    continue
                
                self._add_cooldown(identifier)
                
                return SurebetOpportunity(
                    sport=sport,
                    league=league,
                    match=match,
                    market=f"Totals {line}",
                    outcomes=[
                        {"bookmaker": best_over[0], "name": f"Over {line}", "odds": best_over[1]},
                        {"bookmaker": best_under[0], "name": f"Under {line}", "odds": best_under[1]}
                    ],
                    result=result
                )
        
        return None
    
    def _find_h2h_arbitrage(
        self,
        market_data: dict,
        sport: str,
        league: str,
        match: str,
        market_key: str
    ) -> Optional[SurebetOpportunity]:
        """
        Trouve un arbitrage sur h2h (1X2 ou moneyline).
        
        Pour 3-way (football): Home + Draw + Away
        Pour 2-way (tennis, etc.): Home + Away
        """
        outcomes = list(market_data.keys())
        
        if len(outcomes) < 2:
            return None
        
        # Prendre la meilleure cote pour chaque outcome
        best_odds = []
        for outcome in outcomes:
            if market_data[outcome]:
                best = max(market_data[outcome], key=lambda x: x[1])
                best_odds.append({
                    "name": outcome,
                    "bookmaker": best[0],
                    "odds": best[1]
                })
        
        if len(best_odds) < 2:
            return None
        
        # Calculer l'arbitrage avec toutes les issues
        odds_values = [b["odds"] for b in best_odds]
        result = calculate_arbitrage(odds_values)
        
        if result.is_surebet:
            identifier = f"{match}_{market_key}"
            
            if self._is_in_cooldown(identifier):
                return None
            
            self._add_cooldown(identifier)
            
            return SurebetOpportunity(
                sport=sport,
                league=league,
                match=match,
                market="1X2" if len(best_odds) == 3 else "Moneyline",
                outcomes=[
                    {"bookmaker": b["bookmaker"], "name": b["name"], "odds": b["odds"]}
                    for b in best_odds
                ],
                result=result
            )
        
        return None
    
    def _find_spreads_arbitrage(
        self,
        market_data: dict,
        sport: str,
        league: str,
        match: str,
        market_key: str
    ) -> Optional[SurebetOpportunity]:
        """
        Trouve un arbitrage sur les spreads (handicaps).
        
        Les spreads sont symétriques: +1.5 pour l'un = -1.5 pour l'autre
        """
        # Regrouper par ligne absolue
        lines = {}
        for outcome_name, bookmaker_odds in market_data.items():
            parts = outcome_name.rsplit(" ", 1)
            if len(parts) >= 2:
                team = parts[0]
                try:
                    handicap = float(parts[1])
                    line_key = abs(handicap)
                    
                    if line_key not in lines:
                        lines[line_key] = {}
                    
                    if team not in lines[line_key]:
                        lines[line_key][team] = []
                    
                    lines[line_key][team].extend(bookmaker_odds)
                except ValueError:
                    continue
        
        # Chercher un arbitrage pour chaque ligne
        for line, teams in lines.items():
            team_names = list(teams.keys())
            if len(team_names) < 2:
                continue
            
            best_odds = []
            for team in team_names:
                if teams[team]:
                    best = max(teams[team], key=lambda x: x[1])
                    best_odds.append({
                        "name": team,
                        "bookmaker": best[0],
                        "odds": best[1]
                    })
            
            if len(best_odds) < 2:
                continue
            
            odds_values = [b["odds"] for b in best_odds]
            result = calculate_arbitrage(odds_values)
            
            if result.is_surebet:
                identifier = f"{match}_{market_key}_{line}"
                
                if self._is_in_cooldown(identifier):
                    continue
                
                self._add_cooldown(identifier)
                
                return SurebetOpportunity(
                    sport=sport,
                    league=league,
                    match=match,
                    market=f"Spread {line}",
                    outcomes=[
                        {"bookmaker": b["bookmaker"], "name": b["name"], "odds": b["odds"]}
                        for b in best_odds
                    ],
                    result=result
                )
        
        return None
    
    async def _notify_surebet(self, surebet: SurebetOpportunity):
        """Envoie une notification pour un surebet."""
        await self.telegram.send_surebet_alert(
            sport=surebet.sport,
            league=surebet.league,
            match=surebet.match,
            market=surebet.market,
            outcomes=surebet.outcomes,
            profit_pct=surebet.result.profit_pct,
            profit_base_100=surebet.result.profit_base_100,
            stakes=surebet.result.stakes
        )
    
    async def _save_surebet(self, surebet: SurebetOpportunity):
        """Sauvegarde un surebet en base de données."""
        if not self.db:
            return
        
        from data.database import SurebetRecord
        
        # Prendre les 2 premiers outcomes pour la DB
        o1 = surebet.outcomes[0] if len(surebet.outcomes) > 0 else {}
        o2 = surebet.outcomes[1] if len(surebet.outcomes) > 1 else {}
        
        record = SurebetRecord(
            id=None,
            detected_at=surebet.detected_at,
            sport=surebet.sport,
            league=surebet.league,
            match=surebet.match,
            market=surebet.market,
            bookmaker1=o1.get("bookmaker", ""),
            odds1=o1.get("odds", 0),
            bookmaker2=o2.get("bookmaker", ""),
            odds2=o2.get("odds", 0),
            profit_pct=surebet.result.profit_pct,
            profit_base_100=surebet.result.profit_base_100
        )
        
        await self.db.save_surebet(record)
    
    async def scan_once(self, sports: dict[str, str]):
        """Effectue un scan complet avec priorisation dynamique."""
        self.scans_count += 1
        # Nettoyer le cache de cooldown avant chaque scan
        self._cleanup_cooldown_cache()
        all_surebets = []
        
        # Prioriser les sports via le scheduler
        prioritized_sports = self.scheduler.prioritize_sports(sports)
        
        for sport_key, sport_name in prioritized_sports.items():
            # Vérifier si on doit arrêter
            if self.waiting_for_key or self.force_stop:
                print(f"[Scanner] ⛔ Pause du scan")
                break
            
            try:
                # Déterminer les marchés selon le sport
                if "soccer" in sport_key:
                    markets = "h2h,totals"
                elif "basketball" in sport_key or "football" in sport_key:
                    markets = "h2h,spreads,totals"
                else:
                    markets = "h2h"
                
                surebets = await self._scan_sport(sport_key, sport_name, markets)
                all_surebets.extend(surebets)
                
            except Exception as e:
                error_msg = f"Exception scan {sport_key}: {e}"
                await self._handle_error(error_msg)
        
        # Notifier et sauvegarder les nouveaux surebets
        for surebet in all_surebets:
            self.surebets_found.append(surebet)
            await self._notify_surebet(surebet)
            await self._save_surebet(surebet)
        
        return all_surebets
    
    async def run(self, sports: dict[str, str]):
        """Boucle principale du scanner avec scheduling intelligent.
        
        Comportement:
        - Adapte l'intervalle de scan selon le créneau (5s→15s)
        - Priorise les sports en fonction de l'heure
        - Notifie les changements de créneau sur Telegram
        - Alerte sur les matchs imminents (<1h) pour les compositions
        
        Retry:
        - Si toutes les clés sont épuisées, attend avec backoff (1→10 min)
        - S'arrête uniquement si force_stop == True (commande /stop)
        """
        self.running = True
        self.start_time = datetime.now()
        self.api_exhausted = False
        self.waiting_for_key = False
        self.force_stop = False
        self.retry_count = 0
        
        # Intervalle dynamique via scheduler
        current_interval = self.scheduler.get_scan_interval()
        slot_name, slot_config = self.scheduler.get_current_slot()
        
        print(f"Scanner démarré - Créneau: {slot_config['label']} ({current_interval}s)")
        print(f"Sports à scanner: {len(sports)}")
        print(f"Clé API active: {self.api_manager.current_key[:8] if self.api_manager.current_key else 'AUCUNE'}...")
        
        # Configurer les callbacks pour les commandes Telegram
        self.telegram.set_callbacks(
            stop_callback=self.request_stop,
            status_callback=self.get_stats
        )
        
        # Message de démarrage avec info scheduler
        await self.telegram.send_message(
            f"🟢 <b>Bot Surebet démarré!</b>\n\n"
            f"📊 Sports: {len(sports)}\n"
            f"🔑 Clés API: {self.api_manager.valid_keys_count}\n\n"
            f"{self.scheduler.get_status_message()}\n\n"
            f"Commandes: /stop /status /help"
        )
        
        # Initialiser la détection de changement de créneau
        self.scheduler.has_slot_changed()
        
        while self.running and not self.force_stop:
            # Vérifier les commandes Telegram
            await self.telegram.handle_commands()
            
            if self.force_stop:
                break
            
            # ── Détection changement de créneau ──
            changed, old_slot, new_slot = self.scheduler.has_slot_changed()
            if changed and old_slot is not None:
                msg = self.scheduler.get_slot_change_message(old_slot, new_slot)
                await self.telegram.send_message(msg)
                print(f"[Scheduler] 🔄 Créneau: {old_slot} → {new_slot}")
            
            # Mettre à jour l'intervalle dynamique
            current_interval = self.scheduler.get_scan_interval()
            
            # Si on attend une nouvelle clé, faire le retry avec backoff
            if self.waiting_for_key:
                success = await self._wait_and_retry_key_generation()
                if not success and not self.force_stop:
                    # Continue à réessayer
                    continue
                elif self.force_stop:
                    break
                # Sinon, on a une nouvelle clé, on reprend le scan
            
            try:
                surebets = await self.scan_once(sports)
                
                if surebets:
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] 🎯 {len(surebets)} surebet(s) trouvé(s)!")
                else:
                    slot_label = self.scheduler.get_current_slot()[1]['label']
                    print(
                        f"[{datetime.now().strftime('%H:%M:%S')}] "
                        f"Scan #{self.scans_count} - {slot_label} - "
                        f"API: {self.requests_remaining} restantes - "
                        f"Intervalle: {current_interval}s"
                    )
                
                # Alerte si quota bas
                if self.requests_remaining > 0 and self.requests_remaining < 50:
                    await self.telegram.send_api_warning(
                        self.requests_remaining,
                        self.api_manager.current_key or "N/A"
                    )
                
                await asyncio.sleep(current_interval)
                
            except Exception as e:
                await self._handle_error(f"Exception boucle principale: {e}")
                await asyncio.sleep(current_interval)
        
        # Message de fin avec stats scheduler
        if self.force_stop:
            sched_stats = self.scheduler.get_stats()
            await self.telegram.send_message(
                f"⛔ <b>Bot arrêté sur demande</b>\n\n"
                f"Scans effectués: {self.scans_count}\n"
                f"Surebets trouvés: {len(self.surebets_found)}\n"
                f"Erreurs: {self.errors_count}\n\n"
                f"📊 <b>Scheduler:</b>\n"
                f"Changements de créneau: {sched_stats['slot_changes']}\n"
                f"Matchs alertés: {sched_stats['notified_matches']}"
            )
        
        self.running = False
    
    async def stop(self):
        """Arrête le scanner."""
        self.running = False
        if self.client:
            await self.client.close()
        await self.telegram.send_message("🔴 <b>Bot Surebet arrêté</b>")
    
    def get_stats(self) -> dict:
        """Retourne les statistiques (incluant le scheduler)."""
        uptime = ""
        if self.start_time:
            delta = datetime.now() - self.start_time
            hours, remainder = divmod(delta.seconds, 3600)
            minutes, seconds = divmod(remainder, 60)
            uptime = f"{hours}h {minutes}m {seconds}s"
        
        stats = {
            "uptime": uptime,
            "scans_count": self.scans_count,
            "surebets_found": len(self.surebets_found),
            "requests_remaining": self.requests_remaining,
            "api_key": self.api_manager.current_key[:8] + "..." if self.api_manager.current_key else None,
            "valid_keys": self.api_manager.valid_keys_count,
        }
        
        # Ajouter les stats du scheduler
        if self.scheduler:
            stats["scheduler"] = self.scheduler.get_stats()
        
        return stats
