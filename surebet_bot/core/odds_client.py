# Client The Odds API - Version Complète (avec Rate Limiting)

import asyncio
import time
import aiohttp
from typing import Optional
from dataclasses import dataclass, field


@dataclass
class OddsResponse:
    """Réponse de l'API."""
    success: bool
    data: Optional[list] = None
    error: Optional[str] = None
    status_code: int = 0
    requests_remaining: int = 0
    requests_used: int = 0


class OddsClient:
    """
    Client asynchrone pour The Odds API.
    
    Rate limiting intégré:
    - asyncio.Lock pour forcer les requêtes séquentielles
    - Délai configurable entre chaque requête (défaut: 3s)
    
    Endpoints supportés:
    - GET /sports - Liste des sports
    - GET /sports/{sport}/events - Liste des événements
    - GET /sports/{sport}/odds - Cotes pour marchés de base (h2h, spreads, totals)
    - GET /sports/{sport}/events/{eventId}/odds - Cotes détaillées (player props)
    """
    
    BASE_URL = "https://api.the-odds-api.com/v4"
    
    def __init__(self, api_key: str, request_delay: float = 3.0):
        self.api_key = api_key
        self.request_delay = request_delay
        self._session: Optional[aiohttp.ClientSession] = None
        self._lock = asyncio.Lock()
        self._last_request_time: float = 0.0
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """Retourne ou crée une session HTTP."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session
    
    async def close(self):
        """Ferme la session HTTP."""
        if self._session and not self._session.closed:
            await self._session.close()
    
    async def _request(self, endpoint: str, params: dict = None) -> OddsResponse:
        """Effectue une requête GET avec rate limiting."""
        async with self._lock:  # Une seule requête à la fois
            # Respecter le délai minimum entre requêtes
            now = time.monotonic()
            elapsed = now - self._last_request_time
            if self._last_request_time > 0 and elapsed < self.request_delay:
                wait_time = self.request_delay - elapsed
                print(f"[OddsClient] ⏳ Rate limit: attente {wait_time:.1f}s...")
                await asyncio.sleep(wait_time)
            
            session = await self._get_session()
            
            params = params or {}
            params["apiKey"] = self.api_key
            
            try:
                async with session.get(f"{self.BASE_URL}/{endpoint}", params=params) as resp:
                    response = OddsResponse(
                        success=resp.status == 200,
                        status_code=resp.status,
                        requests_remaining=int(resp.headers.get("x-requests-remaining", 0)),
                        requests_used=int(resp.headers.get("x-requests-used", 0))
                    )
                    
                    if resp.status == 200:
                        response.data = await resp.json()
                    else:
                        response.error = await resp.text()
                    
                    self._last_request_time = time.monotonic()
                    return response
                    
            except Exception as e:
                self._last_request_time = time.monotonic()
                return OddsResponse(success=False, error=str(e))
    
    async def get_sports(self, all_sports: bool = False) -> OddsResponse:
        """
        Liste des sports disponibles.
        
        Args:
            all_sports: Si True, inclut les sports sans événements
        """
        params = {"all": "true"} if all_sports else {}
        return await self._request("sports", params)
    
    async def get_events(
        self,
        sport: str,
        date_format: str = "iso",
        commence_time_from: str = None,
        commence_time_to: str = None
    ) -> OddsResponse:
        """
        Récupère la liste des événements pour un sport.
        
        C'est nécessaire pour obtenir les eventId avant d'appeler
        get_event_odds() pour les player props.
        
        Args:
            sport: Clé du sport (ex: "soccer_france_ligue_one")
            date_format: Format des dates (iso ou unix)
            commence_time_from: Filtre date début (ISO 8601)
            commence_time_to: Filtre date fin (ISO 8601)
        """
        params = {"dateFormat": date_format}
        
        if commence_time_from:
            params["commenceTimeFrom"] = commence_time_from
        if commence_time_to:
            params["commenceTimeTo"] = commence_time_to
        
        return await self._request(f"sports/{sport}/events", params)
    
    async def get_odds(
        self,
        sport: str,
        regions: str = "eu",
        markets: str = "h2h",
        bookmakers: list[str] = None,
        odds_format: str = "decimal",
        event_ids: list[str] = None
    ) -> OddsResponse:
        """
        Récupère les cotes pour un sport (marchés de base).
        
        Marchés supportés:
        - h2h: Moneyline / 1X2
        - spreads: Handicap (principalement sports US)
        - totals: Over/Under (principalement sports US)
        - outrights: Futures (golf, etc.)
        
        Args:
            sport: Clé du sport (ex: "soccer_france_ligue_one")
            regions: Régions des bookmakers (eu, uk, us, au, fr)
            markets: Marchés séparés par virgule (h2h,spreads,totals)
            bookmakers: Liste spécifique de bookmakers
            odds_format: Format des cotes (decimal ou american)
            event_ids: Filtrer par IDs d'événements
        """
        params = {
            "regions": regions,
            "markets": markets,
            "oddsFormat": odds_format
        }
        
        if bookmakers:
            params["bookmakers"] = ",".join(bookmakers)
        
        if event_ids:
            params["eventIds"] = ",".join(event_ids)
        
        return await self._request(f"sports/{sport}/odds", params)
    
    async def get_event_odds(
        self,
        sport: str,
        event_id: str,
        regions: str = "eu",
        markets: str = "h2h",
        odds_format: str = "decimal"
    ) -> OddsResponse:
        """
        Récupère les cotes détaillées pour un événement spécifique.
        
        Utilisé pour les Player Props qui ne sont pas disponibles
        via l'endpoint /odds standard.
        
        Marchés Player Props Football:
        - player_goal_scorer_anytime
        - player_first_goal_scorer
        - player_shots
        - player_shots_on_target
        
        Marchés Player Props NBA:
        - player_points
        - player_rebounds
        - player_assists
        - player_threes
        - player_points_rebounds_assists
        
        Marchés Player Props NFL:
        - player_pass_tds
        - player_pass_yds
        - player_rush_yds
        - player_reception_yds
        - player_anytime_td
        
        Args:
            sport: Clé du sport
            event_id: ID de l'événement (obtenu via get_events())
            regions: Régions des bookmakers
            markets: Marchés player props
            odds_format: Format des cotes
        """
        params = {
            "regions": regions,
            "markets": markets,
            "oddsFormat": odds_format
        }
        return await self._request(f"sports/{sport}/events/{event_id}/odds", params)
    
    async def get_scores(self, sport: str, days_from: int = 1) -> OddsResponse:
        """Récupère les scores récents."""
        params = {"daysFrom": days_from}
        return await self._request(f"sports/{sport}/scores", params)
    
    async def get_event_markets(self, sport: str, event_id: str) -> OddsResponse:
        """
        Liste tous les marchés disponibles pour un événement.
        
        Utile pour découvrir quels player props sont disponibles.
        """
        return await self._request(f"sports/{sport}/events/{event_id}/markets")


# === TEST ===
if __name__ == "__main__":
    import asyncio
    
    async def test():
        # Utiliser la clé du fichier api_keys.txt
        client = OddsClient("1972bdce61e6fd1e7dbbbea1e937cfbc")
        
        print("=" * 60)
        print("TEST CLIENT API THE ODDS API")
        print("=" * 60)
        
        # Test 1: Liste des sports
        print("\n[1] Test GET /sports")
        resp = await client.get_sports()
        print(f"    Status: {'✓ OK' if resp.success else '✗ FAIL'}")
        print(f"    Requêtes restantes: {resp.requests_remaining}")
        
        if resp.success and resp.data:
            active_sports = [s for s in resp.data if not s.get("has_outrights")]
            print(f"    Sports actifs: {len(active_sports)}")
            for sport in active_sports[:5]:
                print(f"      - {sport['key']}: {sport['title']}")
        
        # Test 2: Events pour Ligue 1
        print("\n[2] Test GET /sports/{sport}/events")
        resp2 = await client.get_events("soccer_france_ligue_one")
        print(f"    Status: {'✓ OK' if resp2.success else '✗ FAIL'}")
        
        event_id = None
        if resp2.success and resp2.data:
            print(f"    Événements trouvés: {len(resp2.data)}")
            if resp2.data:
                event = resp2.data[0]
                event_id = event["id"]
                print(f"    Premier match: {event['home_team']} vs {event['away_team']}")
                print(f"    Event ID: {event_id}")
        
        # Test 3: Odds de base (h2h, totals)
        print("\n[3] Test GET /sports/{sport}/odds (h2h + totals)")
        resp3 = await client.get_odds(
            sport="soccer_france_ligue_one",
            regions="eu,fr",
            markets="h2h,totals"
        )
        print(f"    Status: {'✓ OK' if resp3.success else '✗ FAIL'}")
        
        if resp3.success and resp3.data:
            print(f"    Matches avec cotes: {len(resp3.data)}")
            if resp3.data:
                match = resp3.data[0]
                print(f"    Match: {match['home_team']} vs {match['away_team']}")
                print(f"    Bookmakers: {len(match.get('bookmakers', []))}")
                
                # Afficher les cotes
                for bm in match.get("bookmakers", [])[:2]:
                    print(f"      {bm['title']}:")
                    for market in bm.get("markets", []):
                        outcomes = ", ".join([
                            f"{o['name']}={o['price']}" 
                            for o in market.get("outcomes", [])[:3]
                        ])
                        print(f"        {market['key']}: {outcomes}")
        
        # Test 4: Event odds (player props si disponibles)
        if event_id:
            print("\n[4] Test GET /sports/{sport}/events/{id}/odds (player props)")
            resp4 = await client.get_event_odds(
                sport="soccer_france_ligue_one",
                event_id=event_id,
                regions="eu,fr",
                markets="player_goal_scorer_anytime"
            )
            print(f"    Status: {'✓ OK' if resp4.success else '✗ FAIL'}")
            
            if resp4.success and resp4.data:
                print(f"    Bookmakers avec props: {len(resp4.data.get('bookmakers', []))}")
            elif resp4.error:
                print(f"    Note: {resp4.error[:100]}...")
        
        await client.close()
        
        print("\n" + "=" * 60)
        print("TESTS TERMINÉS")
        print("=" * 60)
    
    asyncio.run(test())
